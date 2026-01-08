"""
广场模块路由（首页推荐）
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.api.deps import get_db_session, get_current_user_optional
from backend.config.settings import settings
from backend.db.dao import StoryDAO, UserDAO

router = APIRouter()


@router.get("/stories", response_model=ApiResponse)
async def get_explore_stories(
    type: Optional[str] = Query(None, description="故事类型（linear/interactive）"),
    sort: str = Query("latest", description="排序方式（latest/popular/recommended）"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取广场故事列表
    
    - 无需登录即可访问
    - 只返回已发布的故事
    - 支持类型筛选和排序
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )
    
    # 验证排序方式
    if sort not in ["latest", "popular", "recommended"]:
        return ApiResponse(
            success=False,
            message="Invalid sort parameter",
            error={"code": "INVALID_SORT", "message": "排序方式只能是 latest/popular/recommended"}
        )
    
    # 验证类型
    if type and type not in ["linear", "interactive"]:
        return ApiResponse(
            success=False,
            message="Invalid type parameter",
            error={"code": "INVALID_TYPE", "message": "故事类型只能是 linear/interactive"}
        )
    
    # 计算偏移量
    offset = (page - 1) * limit
    
    # 获取故事列表
    stories, total = await StoryDAO.get_published_stories(
        session, type, sort, limit, offset
    )
    
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
            "status": story.status,
            "author": {
                "user_id": author.id if author else story.user_id,
                "username": author.username if author else "未知用户"
            },
            "published_at": story.published_at.isoformat() if story.published_at else None,
            "play_count": story.play_count,
            "like_count": story.like_count,
            "favorite_count": story.favorite_count,
            "pricing_type": story.pricing_type,
            "price": float(story.price)
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

