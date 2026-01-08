"""
数据库初始化脚本

创建所有表、索引、触发器、分区等
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config.settings import settings
from backend.db.base import get_database_url
from backend.db.models import Base


async def create_pg_jieba_extension():
    """创建 pg_jieba 扩展（用于中文全文搜索）"""
    engine = create_async_engine(get_database_url(async_mode=True), echo=True)

    async with engine.begin() as conn:
        # 创建扩展
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_jieba;"))
        print("✅ pg_jieba extension created")

    await engine.dispose()


async def create_tables():
    """创建所有表"""
    engine = create_async_engine(get_database_url(async_mode=True), echo=True)

    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        print("✅ All tables created")

    await engine.dispose()


async def create_search_triggers():
    """创建全文搜索触发器"""
    engine = create_async_engine(get_database_url(async_mode=True), echo=True)

    async with engine.begin() as conn:
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

        print("✅ Search triggers created")

    await engine.dispose()


async def create_partitions():
    """创建分区表（按月分区）"""
    engine = create_async_engine(get_database_url(async_mode=True), echo=True)

    async with engine.begin() as conn:
        # 创建用户行为日志分区（示例：2024年1月到2026年12月）
        for year in range(2024, 2027):
            for month in range(1, 13):
                partition_name = f"user_behavior_logs_y{year}m{month:02d}"
                start_date = f"{year}-{month:02d}-01"

                # 计算下个月的第一天
                if month == 12:
                    end_date = f"{year+1}-01-01"
                else:
                    end_date = f"{year}-{month+1:02d}-01"

                await conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name}
                    PARTITION OF user_behavior_logs
                    FOR VALUES FROM ('{start_date}') TO ('{end_date}');
                """))

        # 创建交易流水分区（示例：2024年1月到2026年12月）
        for year in range(2024, 2027):
            for month in range(1, 13):
                partition_name = f"wallet_transactions_y{year}m{month:02d}"
                start_date = f"{year}-{month:02d}-01"

                # 计算下个月的第一天
                if month == 12:
                    end_date = f"{year+1}-01-01"
                else:
                    end_date = f"{year}-{month+1:02d}-01"

                await conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name}
                    PARTITION OF wallet_transactions
                    FOR VALUES FROM ('{start_date}') TO ('{end_date}');
                """))

        print("✅ Partitions created")

    await engine.dispose()


async def init_default_data():
    """初始化默认数据"""
    engine = create_async_engine(get_database_url(async_mode=True), echo=True)

    async with engine.begin() as conn:
        # 插入全局配置（默认转场效果等）
        await conn.execute(text("""
            INSERT INTO global_settings (key, value, description)
            VALUES 
                ('default_scene_transition', '{"type": "fade_in", "duration": 1.5}', '默认场景开始转场'),
                ('default_scene_end_transition', '{"type": "fade_out", "duration": 1.0}', '默认场景结束转场'),
                ('default_chapter_transition', '{"type": "fade_in", "duration": 2.0}', '默认章节转场'),
                ('character_color_pool', '["#ff6b9d", "#6b9dff", "#9dff6b", "#ff9d6b", "#9d6bff", "#6bffff"]', '角色名字颜色池')
            ON CONFLICT (key) DO NOTHING;
        """))

        print("✅ Default data inserted")

    await engine.dispose()


async def main():
    """主函数"""
    print("🚀 Starting database initialization...")
    print(f"Database URL: {get_database_url(async_mode=True)}")

    try:
        # 1. 创建 pg_jieba 扩展
        print("\n📦 Step 1: Creating pg_jieba extension...")
        await create_pg_jieba_extension()

        # 2. 创建所有表
        print("\n📦 Step 2: Creating tables...")
        await create_tables()

        # 3. 创建全文搜索触发器
        print("\n📦 Step 3: Creating search triggers...")
        await create_search_triggers()

        # 4. 创建分区
        print("\n📦 Step 4: Creating partitions...")
        await create_partitions()

        # 5. 初始化默认数据
        print("\n📦 Step 5: Inserting default data...")
        await init_default_data()

        print("\n✅ Database initialization completed successfully!")

    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
