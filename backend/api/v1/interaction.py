"""
互动模块路由（点赞、收藏）
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.api.deps import get_current_user, get_db_session
from backend.config.settings import settings
from backend.services.interaction_service import interaction_service

router = APIRouter()


@router.post("/story/{story_id}/like", response_model=ApiResponse)
async def like_story(
    story_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    点赞故事

    - 需要登录
    - 不能重复点赞
    - 作者获得 +2 经验值
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await interaction_service.like_story(
        session, story_id, current_user["user_id"]
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.delete("/story/{story_id}/like", response_model=ApiResponse)
async def unlike_story(
    story_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    取消点赞故事

    - 需要登录
    - 必须已点赞
    - 作者失去 -2 经验值
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await interaction_service.unlike_story(
        session, story_id, current_user["user_id"]
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.post("/story/{story_id}/favorite", response_model=ApiResponse)
async def favorite_story(
    story_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    收藏故事

    - 需要登录
    - 不能重复收藏
    - 作者获得 +3 经验值
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await interaction_service.favorite_story(
        session, story_id, current_user["user_id"]
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.delete("/story/{story_id}/favorite", response_model=ApiResponse)
async def unfavorite_story(
    story_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    取消收藏故事

    - 需要登录
    - 必须已收藏
    - 作者失去 -3 经验值
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await interaction_service.unfavorite_story(
        session, story_id, current_user["user_id"]
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.get("/user/favorites", response_model=ApiResponse)
async def get_user_favorites(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取用户收藏的故事列表

    - 需要登录
    - 返回当前用户收藏的故事
    - 支持分页
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await interaction_service.get_user_favorites(
        session, current_user["user_id"], current_user["user_id"], limit, offset
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result
