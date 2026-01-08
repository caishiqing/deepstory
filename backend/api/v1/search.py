"""
搜索模块路由
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.api.deps import get_db_session
from backend.config.settings import settings
from backend.db.dao import StoryDAO, UserDAO

router = APIRouter()


@router.get("/stories", response_model=ApiResponse)
async def search_stories(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session)
):
    """
    搜索故事
    
    - 搜索范围：故事标题
    - 只搜索已发布的故事
    - 支持中英文混合搜索
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )
    
    # 计算偏移量
    offset = (page - 1) * limit
    
    # 搜索故事
    stories, total = await StoryDAO.search_stories(session, q, limit, offset)
    
    # 构造响应数据
    story_list = []
    for story in stories:
        # 获取作者信息
        author = await UserDAO.get_by_id(session, story.user_id)
        
        story_list.append({
            "story_id": story.id,
            "type": story.type,
            "title": story.title or "未命名故事",
            "cover_url": story.cover_url,
            "author": {
                "user_id": author.id if author else story.user_id,
                "username": author.username if author else "未知用户"
            },
            "play_count": story.play_count,
            "like_count": story.like_count,
            "favorite_count": story.favorite_count,
            "created_at": story.created_at.isoformat()
        })
    
    return ApiResponse(
        success=True,
        data={
            "stories": story_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total
            }
        }
    )


@router.get("/users", response_model=ApiResponse)
async def search_users(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session)
):
    """
    搜索用户
    
    - 搜索范围：用户名
    - 只搜索状态正常的用户
    - 支持中英文混合搜索
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )
    
    # 计算偏移量
    offset = (page - 1) * limit
    
    # 搜索用户
    users, total = await UserDAO.search_users(session, q, limit, offset)
    
    # 构造响应数据
    user_list = []
    for user in users:
        user_list.append({
            "user_id": user.id,
            "username": user.username,
            "avatar_url": user.avatar_url,
            "level": user.level,
            "follower_count": user.follower_count,
            "story_count": user.story_count,
            "created_at": user.created_at.isoformat()
        })
    
    return ApiResponse(
        success=True,
        data={
            "users": user_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total
            }
        }
    )

