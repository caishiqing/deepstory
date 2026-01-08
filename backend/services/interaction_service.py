"""
互动服务

处理点赞、收藏等互动业务逻辑
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.db.dao import InteractionDAO, StoryDAO, UserDAO


class InteractionService:
    """互动服务"""

    @staticmethod
    async def like_story(
        session: AsyncSession,
        story_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        点赞故事

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID

        Returns:
            API响应
        """
        # 检查故事是否存在
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 检查是否已点赞
        is_liked = await InteractionDAO.is_liked(session, user_id, story_id)
        if is_liked:
            return ApiResponse(
                success=False,
                message="Already liked",
                error={"code": "ALREADY_LIKED", "message": "已经点赞过了"}
            )

        # 记录点赞行为
        await InteractionDAO.log_action(session, user_id, story_id, "like")

        # 更新故事点赞数
        story.like_count += 1

        # 更新用户点赞数
        user = await UserDAO.get_by_id(session, user_id)
        if user:
            user.like_count += 1

        # 给故事作者增加经验值（+2）
        author = await UserDAO.get_by_id(session, story.user_id)
        if author:
            author.experience += 2

        await session.flush()

        return ApiResponse(
            success=True,
            message="Story liked",
            data={"is_liked": True}
        )

    @staticmethod
    async def unlike_story(
        session: AsyncSession,
        story_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        取消点赞故事

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID

        Returns:
            API响应
        """
        # 检查故事是否存在
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 检查是否已点赞
        is_liked = await InteractionDAO.is_liked(session, user_id, story_id)
        if not is_liked:
            return ApiResponse(
                success=False,
                message="Not liked yet",
                error={"code": "NOT_LIKED", "message": "还未点赞"}
            )

        # 记录取消点赞行为
        await InteractionDAO.log_action(session, user_id, story_id, "unlike")

        # 更新故事点赞数
        story.like_count = max(0, story.like_count - 1)

        # 更新用户点赞数
        user = await UserDAO.get_by_id(session, user_id)
        if user:
            user.like_count = max(0, user.like_count - 1)

        # 减少故事作者经验值（-2）
        author = await UserDAO.get_by_id(session, story.user_id)
        if author:
            author.experience = max(0, author.experience - 2)

        await session.flush()

        return ApiResponse(
            success=True,
            message="Story unliked",
            data={"is_liked": False}
        )

    @staticmethod
    async def favorite_story(
        session: AsyncSession,
        story_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        收藏故事

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID

        Returns:
            API响应
        """
        # 检查故事是否存在
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 检查是否已收藏
        is_favorited = await InteractionDAO.is_favorited(session, user_id, story_id)
        if is_favorited:
            return ApiResponse(
                success=False,
                message="Already favorited",
                error={"code": "ALREADY_FAVORITED", "message": "已经收藏过了"}
            )

        # 记录收藏行为
        await InteractionDAO.log_action(session, user_id, story_id, "favorite")

        # 更新故事收藏数
        story.favorite_count += 1

        # 更新用户收藏数
        user = await UserDAO.get_by_id(session, user_id)
        if user:
            user.favorite_count += 1

        # 给故事作者增加经验值（+3）
        author = await UserDAO.get_by_id(session, story.user_id)
        if author:
            author.experience += 3

        await session.flush()

        return ApiResponse(
            success=True,
            message="Story favorited",
            data={"is_favorited": True}
        )

    @staticmethod
    async def unfavorite_story(
        session: AsyncSession,
        story_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        取消收藏故事

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID

        Returns:
            API响应
        """
        # 检查故事是否存在
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 检查是否已收藏
        is_favorited = await InteractionDAO.is_favorited(session, user_id, story_id)
        if not is_favorited:
            return ApiResponse(
                success=False,
                message="Not favorited yet",
                error={"code": "NOT_FAVORITED", "message": "还未收藏"}
            )

        # 记录取消收藏行为
        await InteractionDAO.log_action(session, user_id, story_id, "unfavorite")

        # 更新故事收藏数
        story.favorite_count = max(0, story.favorite_count - 1)

        # 更新用户收藏数
        user = await UserDAO.get_by_id(session, user_id)
        if user:
            user.favorite_count = max(0, user.favorite_count - 1)

        # 减少故事作者经验值（-3）
        author = await UserDAO.get_by_id(session, story.user_id)
        if author:
            author.experience = max(0, author.experience - 3)

        await session.flush()

        return ApiResponse(
            success=True,
            message="Story unfavorited",
            data={"is_favorited": False}
        )

    @staticmethod
    async def get_user_favorites(
        session: AsyncSession,
        user_id: str,
        current_user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> ApiResponse:
        """
        获取用户收藏的故事列表

        Args:
            session: 数据库会话
            user_id: 用户ID
            current_user_id: 当前用户ID（用于判断互动状态）
            limit: 每页数量
            offset: 偏移量

        Returns:
            API响应，包含故事列表
        """
        # 获取收藏列表
        stories = await InteractionDAO.get_user_favorites(session, user_id, limit, offset)

        # 构建响应数据
        story_list = []
        for story in stories:
            # 获取作者信息
            author = await UserDAO.get_by_id(session, story.user_id)

            # 检查当前用户的互动状态
            is_liked = False
            is_favorited = False
            if current_user_id:
                is_liked = await InteractionDAO.is_liked(session, current_user_id, story.id)
                is_favorited = await InteractionDAO.is_favorited(session, current_user_id, story.id)

            story_list.append({
                "story_id": story.id,
                "title": story.title,
                "cover_url": story.cover_url,
                "type": story.type,
                "author": {
                    "user_id": author.id,
                    "username": author.username
                } if author else None,
                "play_count": story.play_count,
                "like_count": story.like_count,
                "favorite_count": story.favorite_count,
                "is_liked": is_liked,
                "is_favorited": is_favorited,
                "pricing_type": story.pricing_type,
                "price": float(story.price),
                "created_at": story.created_at.isoformat()
            })

        return ApiResponse(
            success=True,
            data={
                "stories": story_list,
                "total": len(story_list),
                "limit": limit,
                "offset": offset
            }
        )


# 全局互动服务实例
interaction_service = InteractionService()
