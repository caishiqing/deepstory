"""
API 依赖注入 - 认证、数据库连接等
"""

from typing import Optional, AsyncIterator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.base import get_db

# JWT 认证
security = HTTPBearer()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """
    获取数据库会话（依赖注入用）

    Yields:
        AsyncSession: 数据库会话
    """
    if not settings.DATABASE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not enabled"
        )

    async for session in get_db():
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    从 JWT Token 中解析当前用户

    Returns:
        用户信息字典 {"user_id": "...", "username": "..."}
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        return {
            "user_id": user_id,
            "username": payload.get("username", "")
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    可选的用户认证（未登录时返回 None）
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
