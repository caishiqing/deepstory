"""
关注模块路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.api.deps import get_current_user, get_db_session
from backend.config.settings import settings
from backend.services.follow_service import follow_service

router = APIRouter()


@router.post("/user/{user_id}/follow", response_model=ApiResponse)
async def follow_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    关注用户

    - 需要登录
    - 不能关注自己
    - 不能重复关注
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await follow_service.follow_user(
        session, current_user["user_id"], user_id
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.delete("/user/{user_id}/follow", response_model=ApiResponse)
async def unfollow_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    取消关注用户

    - 需要登录
    - 必须已关注
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await follow_service.unfollow_user(
        session, current_user["user_id"], user_id
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.get("/user/{user_id}/following", response_model=ApiResponse)
async def get_following_list(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = None,
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取用户的关注列表

    - 游客可查看
    - 返回用户关注的人
    - 支持分页
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    current_user_id = current_user["user_id"] if current_user else None

    result = await follow_service.get_following_list(
        session, user_id, current_user_id, limit, offset
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result


@router.get("/user/{user_id}/followers", response_model=ApiResponse)
async def get_follower_list(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = None,
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取用户的粉丝列表

    - 游客可查看
    - 返回关注该用户的人
    - 支持分页
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    current_user_id = current_user["user_id"] if current_user else None

    result = await follow_service.get_follower_list(
        session, user_id, current_user_id, limit, offset
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result
