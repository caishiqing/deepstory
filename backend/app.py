"""
FastAPI 应用入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from loguru import logger

from backend.config import settings
from backend.api import api_v1_router
from cache import init_redis

# 数据库相关导入
from sqlalchemy import text
if settings.DATABASE_ENABLED:
    from backend.db.base import init_db, close_db
    from backend.db import Base
    from sqlalchemy.ext.asyncio import create_async_engine


async def check_and_init_database():
    """检查并初始化数据库"""
    if not settings.DATABASE_ENABLED:
        logger.info("📦 Database disabled, skipping initialization")
        return

    try:
        logger.info("🔍 Checking database connection...")

        # 创建临时引擎用于检查
        from backend.db.base import get_database_url
        engine = create_async_engine(get_database_url(async_mode=True), echo=False)

        # 检查数据库连接
        async with engine.begin() as conn:
            # 检查 pg_jieba 扩展
            result = await conn.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'pg_jieba')")
            )
            pg_jieba_exists = result.scalar()

            # 检查核心表是否存在
            result = await conn.execute(
                text("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'users')")
            )
            tables_exist = result.scalar()

            if not pg_jieba_exists or not tables_exist:
                logger.warning("⚠️  Database not initialized, starting auto-initialization...")

                # 执行初始化
                if not pg_jieba_exists:
                    logger.info("📦 Creating pg_jieba extension...")
                    try:
                        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_jieba;"))
                        logger.info("✅ pg_jieba extension created")
                    except Exception as e:
                        logger.warning(f"⚠️  pg_jieba creation failed (may not be installed): {e}")

                if not tables_exist:
                    logger.info("📦 Creating database tables...")
                    # 导入所有模型以确保 Base 知道它们
                    from backend.db.models import (
                        User, StoryPrompt, Story, StoryEvent, Character,
                        CharacterPortrait, Resource, UserStoryProgress,
                        StoryVersion, Scene, StoryComment, UserFollow,
                        UserBehaviorLog, WalletTransaction, GlobalSetting
                    )

                    # 先手动创建分区表（SQLAlchemy 不支持自动创建分区表）
                    logger.info("📦 Creating partition tables...")
                    try:
                        # 创建用户行为日志分区父表
                        await conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS user_behavior_logs (
                                id SERIAL,
                                user_id VARCHAR(64) NOT NULL,
                                story_id VARCHAR(64),
                                action VARCHAR(50) NOT NULL,
                                metadata JSONB,
                                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                PRIMARY KEY (id, created_at)
                            ) PARTITION BY RANGE (created_at);
                        """))

                        # 创建交易流水分区父表
                        await conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS wallet_transactions (
                                id SERIAL,
                                user_id VARCHAR(64) NOT NULL,
                                story_id VARCHAR(64),
                                transaction_type VARCHAR(20) NOT NULL,
                                amount DECIMAL(10, 2) NOT NULL,
                                balance_after DECIMAL(10, 2) NOT NULL,
                                description TEXT,
                                external_order_id VARCHAR(128),
                                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                PRIMARY KEY (id, created_at)
                            ) PARTITION BY RANGE (created_at);
                        """))

                        # 创建当前月份的分区（避免插入失败）
                        from datetime import datetime as dt
                        now = dt.now()
                        year = now.year
                        month = now.month

                        start_date = f"{year}-{month:02d}-01"
                        if month == 12:
                            end_date = f"{year+1}-01-01"
                        else:
                            end_date = f"{year}-{month+1:02d}-01"

                        partition_name_logs = f"user_behavior_logs_y{year}m{month:02d}"
                        partition_name_trans = f"wallet_transactions_y{year}m{month:02d}"

                        await conn.execute(text(f"""
                            CREATE TABLE IF NOT EXISTS {partition_name_logs}
                            PARTITION OF user_behavior_logs
                            FOR VALUES FROM ('{start_date}') TO ('{end_date}');
                        """))

                        await conn.execute(text(f"""
                            CREATE TABLE IF NOT EXISTS {partition_name_trans}
                            PARTITION OF wallet_transactions
                            FOR VALUES FROM ('{start_date}') TO ('{end_date}');
                        """))

                        # 创建索引
                        await conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_behavior_user 
                            ON user_behavior_logs (user_id, created_at);
                        """))
                        await conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_behavior_story 
                            ON user_behavior_logs (story_id, created_at);
                        """))
                        await conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_behavior_action 
                            ON user_behavior_logs (action, created_at);
                        """))
                        await conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_transactions_user 
                            ON wallet_transactions (user_id, created_at DESC);
                        """))
                        await conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_transactions_story 
                            ON wallet_transactions (story_id, created_at DESC);
                        """))
                        await conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_transactions_type 
                            ON wallet_transactions (transaction_type, created_at);
                        """))
                        await conn.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_transactions_external 
                            ON wallet_transactions (external_order_id);
                        """))

                        logger.info(f"✅ Partition tables and indexes created (current: {year}-{month:02d})")
                    except Exception as e:
                        logger.warning(f"⚠️  Partition table creation failed: {e}")

                    # 创建其他所有表（跳过已创建的分区表）
                    # 移除分区表以避免重复创建
                    tables_to_create = [t for t in Base.metadata.tables.values()
                                        if t.name not in ('user_behavior_logs', 'wallet_transactions')]

                    from sqlalchemy.schema import CreateTable
                    for table in tables_to_create:
                        try:
                            await conn.execute(CreateTable(table, if_not_exists=True))
                        except Exception as e:
                            logger.warning(f"⚠️  Failed to create table {table.name}: {e}")

                    logger.info("✅ All tables created")

                    # 创建触发器
                    logger.info("📦 Creating search triggers...")
                    try:
                        # 用户表全文搜索触发器
                        await conn.execute(text("""
                            CREATE OR REPLACE FUNCTION users_search_trigger() RETURNS trigger AS $$
                            BEGIN
                                NEW.search_vector := to_tsvector('jiebacfg', COALESCE(NEW.username, ''));
                                RETURN NEW;
                            END;
                            $$ LANGUAGE plpgsql;
                        """))
                        await conn.execute(text("""
                            DROP TRIGGER IF EXISTS users_search_update ON users;
                            CREATE TRIGGER users_search_update
                            BEFORE INSERT OR UPDATE ON users
                            FOR EACH ROW EXECUTE FUNCTION users_search_trigger();
                        """))

                        # 故事表全文搜索触发器
                        await conn.execute(text("""
                            CREATE OR REPLACE FUNCTION stories_search_trigger() RETURNS trigger AS $$
                            BEGIN
                                NEW.search_vector := to_tsvector('jiebacfg', COALESCE(NEW.title, ''));
                                RETURN NEW;
                            END;
                            $$ LANGUAGE plpgsql;
                        """))
                        await conn.execute(text("""
                            DROP TRIGGER IF EXISTS stories_search_update ON stories;
                            CREATE TRIGGER stories_search_update
                            BEFORE INSERT OR UPDATE ON stories
                            FOR EACH ROW EXECUTE FUNCTION stories_search_trigger();
                        """))
                        logger.info("✅ Search triggers created")
                    except Exception as e:
                        logger.warning(f"⚠️  Trigger creation failed: {e}")

                    # 插入默认配置
                    logger.info("📦 Inserting default settings...")
                    await conn.execute(text("""
                        INSERT INTO global_settings (key, value, description)
                        VALUES 
                            ('default_scene_transition', '{"type": "fade_in", "duration": 1.5}', '默认场景开始转场'),
                            ('default_scene_end_transition', '{"type": "fade_out", "duration": 1.0}', '默认场景结束转场'),
                            ('default_chapter_transition', '{"type": "fade_in", "duration": 2.0}', '默认章节转场'),
                            ('character_color_pool', '["#ff6b9d", "#6b9dff", "#9dff6b", "#ff9d6b", "#9d6bff", "#6bffff"]', '角色名字颜色池')
                        ON CONFLICT (key) DO NOTHING;
                    """))
                    logger.info("✅ Default settings inserted")

                logger.success("🎉 Database auto-initialization completed!")
            else:
                logger.success("✅ Database already initialized")

        await engine.dispose()

        # 初始化应用的数据库连接池
        await init_db()
        logger.success("✅ Database connection pool initialized")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.warning("⚠️  Application will continue in memory mode")
        # 不抛出异常，允许应用继续运行（使用内存模式）


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 Starting DeepStory API...")

    # 初始化 Redis
    try:
        await init_redis()
        logger.success("✅ Redis initialized")
    except Exception as e:
        logger.error(f"❌ Redis init failed: {e}")

    # 检查并初始化数据库
    await check_and_init_database()

    logger.success("🎉 Application started successfully!")

    yield

    # 关闭时执行
    logger.info("👋 Shutting down...")

    if settings.DATABASE_ENABLED:
        try:
            await close_db()
            logger.info("✅ Database connections closed")
        except Exception as e:
            logger.error(f"❌ Database close failed: {e}")

    logger.success("✅ Application shutdown complete")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    """健康检查"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "ok"
    }


@app.get("/health")
async def health_check():
    """健康检查（详细）"""
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "services": {}
    }

    # 检查 Redis
    try:
        from cache import redis_client
        if redis_client:
            await redis_client.ping()
            health_status["services"]["redis"] = "healthy"
        else:
            health_status["services"]["redis"] = "not_initialized"
    except Exception as e:
        health_status["services"]["redis"] = "unhealthy"
        health_status["status"] = "degraded"

    # 检查数据库
    if settings.DATABASE_ENABLED:
        try:
            from backend.db.base import async_engine
            if async_engine:
                async with async_engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                health_status["services"]["database"] = "healthy"
            else:
                health_status["services"]["database"] = "not_initialized"
        except Exception as e:
            health_status["services"]["database"] = "unhealthy"
            health_status["status"] = "degraded"
    else:
        health_status["services"]["database"] = "disabled"

    return health_status


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": 500,
            "message": "Internal server error",
            "error": {
                "type": type(exc).__name__,
                "message": str(exc)
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
