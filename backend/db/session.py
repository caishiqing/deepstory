"""
数据库会话管理

提供数据库会话的便捷访问
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from .base import AsyncSessionLocal


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    获取数据库会话的上下文管理器

    使用示例：
    ```python
    async with get_session() as session:
        user = await session.get(User, user_id)
    ```

    Yields:
        AsyncSession: 数据库会话
    """
    if not AsyncSessionLocal:
        raise RuntimeError("Database not initialized")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# 全局会话（仅用于非 FastAPI 上下文）
async_session = AsyncSessionLocal if AsyncSessionLocal else None
