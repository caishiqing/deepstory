"""
评论模块路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from backend.models import ApiResponse
from backend.api.deps import get_current_user, get_db_session
from backend.config.settings import settings
from backend.services.comment_service import comment_service

router = APIRouter()


class CommentCreate(BaseModel):
    """创建评论请求"""
    content: str = Field(..., min_length=1, max_length=500, description="评论内容")
    parent_id: Optional[str] = Field(None, description="父评论ID（回复）")


@router.get("/story/{story_id}/comments", response_model=ApiResponse)
async def get_story_comments(
    story_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = None,
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取故事评论列表

    - 游客可查看
    - 返回顶级评论及其前3条回复
    - 支持分页
    """
    # 尝试获取当前用户（可选）
    try:
        from backend.api.deps import security
        from fastapi import Request
        # 这里简化处理，实际应该通过依赖注入
        current_user_id = current_user["user_id"] if current_user else None
    except:
        current_user_id = None

    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await comment_service.get_story_comments(
        session, story_id, current_user_id, limit, offset
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result


@router.post("/story/{story_id}/comments", response_model=ApiResponse)
async def create_comment(
    story_id: str,
    data: CommentCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    发表评论

    - 需要登录
    - 评论内容 1-500 字符
    - 支持回复（最多2层）
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await comment_service.create_comment(
        session, story_id, current_user["user_id"], data.content, data.parent_id
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.delete("/comment/{comment_id}", response_model=ApiResponse)
async def delete_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    删除评论

    - 仅评论作者可删除
    - 软删除，内容显示为"该评论已删除"
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await comment_service.delete_comment(
        session, comment_id, current_user["user_id"]
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if result.error.get("code") == "PERMISSION_DENIED" else status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result


@router.post("/comment/{comment_id}/like", response_model=ApiResponse)
async def like_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    点赞评论

    - 需要登录
    - 不能重复点赞
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await comment_service.like_comment(
        session, comment_id, current_user["user_id"]
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.delete("/comment/{comment_id}/like", response_model=ApiResponse)
async def unlike_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    取消点赞评论

    - 需要登录
    - 必须已点赞
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await comment_service.unlike_comment(
        session, comment_id, current_user["user_id"]
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result
