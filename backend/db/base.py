"""
数据库基础配置

包含 Base 类、数据库引擎初始化等
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from backend.config.settings import settings

# 声明式基类
Base = declarative_base()

# 异步引擎（用于 asyncpg）
async_engine = None
AsyncSessionLocal = None


def get_database_url(async_mode: bool = True) -> str:
    """
    获取数据库连接 URL

    Args:
        async_mode: 是否使用异步模式

    Returns:
        数据库连接 URL
    """
    if not settings.DATABASE_ENABLED or not settings.DATABASE_URL:
        raise RuntimeError("Database is not enabled or DATABASE_URL is not set")

    url = settings.DATABASE_URL

    # 异步模式：postgresql:// -> postgresql+asyncpg://
    if async_mode and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://")

    return url


async def init_db():
    """
    初始化数据库连接

    创建异步引擎和会话工厂
    """
    global async_engine, AsyncSessionLocal

    if not settings.DATABASE_ENABLED:
        return

    # 创建异步引擎
    async_engine = create_async_engine(
        get_database_url(async_mode=True),
        echo=settings.DEBUG,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
    )

    # 创建异步会话工厂
    AsyncSessionLocal = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_db():
    """关闭数据库连接"""
    global async_engine

    if async_engine:
        await async_engine.dispose()
        async_engine = None


async def get_db():
    """
    获取数据库会话（依赖注入用）

    Yields:
        AsyncSession: 数据库会话
    """
    if not AsyncSessionLocal:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
