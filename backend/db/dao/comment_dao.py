"""
评论数据访问对象
"""

from typing import Optional, List, Tuple
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from backend.db.models.comment import StoryComment
from backend.utils.id_generator import generate_comment_id


class CommentDAO:
    """评论 DAO"""

    @staticmethod
    async def create(
        session: AsyncSession,
        story_id: str,
        user_id: str,
        content: str,
        parent_id: Optional[str] = None
    ) -> StoryComment:
        """
        创建评论

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID
            content: 评论内容
            parent_id: 父评论ID（回复）

        Returns:
            StoryComment: 新创建的评论对象
        """
        comment = StoryComment(
            id=generate_comment_id(),
            story_id=story_id,
            user_id=user_id,
            content=content,
            parent_id=parent_id,
            status="visible",
            like_count=0,
        )

        session.add(comment)
        await session.flush()

        return comment

    @staticmethod
    async def get_by_id(session: AsyncSession, comment_id: str) -> Optional[StoryComment]:
        """根据ID获取评论"""
        result = await session.execute(
            select(StoryComment).where(StoryComment.id == comment_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_story_comments(
        session: AsyncSession,
        story_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[StoryComment]:
        """
        获取故事的评论列表（仅顶级评论）

        Args:
            session: 数据库会话
            story_id: 故事ID
            limit: 每页数量
            offset: 偏移量

        Returns:
            评论列表
        """
        result = await session.execute(
            select(StoryComment)
            .where(
                and_(
                    StoryComment.story_id == story_id,
                    StoryComment.parent_id.is_(None),
                    StoryComment.status == "visible"
                )
            )
            .order_by(StoryComment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_replies(
        session: AsyncSession,
        parent_id: str,
        limit: int = 3
    ) -> List[StoryComment]:
        """
        获取评论的回复列表

        Args:
            session: 数据库会话
            parent_id: 父评论ID
            limit: 最多返回数量

        Returns:
            回复列表
        """
        result = await session.execute(
            select(StoryComment)
            .where(
                and_(
                    StoryComment.parent_id == parent_id,
                    StoryComment.status == "visible"
                )
            )
            .order_by(StoryComment.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_replies(session: AsyncSession, parent_id: str) -> int:
        """统计评论的回复数量"""
        result = await session.execute(
            select(func.count(StoryComment.id))
            .where(
                and_(
                    StoryComment.parent_id == parent_id,
                    StoryComment.status == "visible"
                )
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def soft_delete(session: AsyncSession, comment_id: str) -> bool:
        """
        软删除评论

        Args:
            session: 数据库会话
            comment_id: 评论ID

        Returns:
            是否删除成功
        """
        comment = await CommentDAO.get_by_id(session, comment_id)
        if not comment:
            return False

        comment.status = "hidden"
        comment.content = "该评论已删除"
        await session.flush()

        return True

    @staticmethod
    async def increment_like_count(session: AsyncSession, comment_id: str) -> bool:
        """增加评论点赞数"""
        comment = await CommentDAO.get_by_id(session, comment_id)
        if not comment:
            return False

        comment.like_count += 1
        await session.flush()
        return True

    @staticmethod
    async def decrement_like_count(session: AsyncSession, comment_id: str) -> bool:
        """减少评论点赞数"""
        comment = await CommentDAO.get_by_id(session, comment_id)
        if not comment:
            return False

        comment.like_count = max(0, comment.like_count - 1)
        await session.flush()
        return True

    @staticmethod
    async def get_user_comments(
        session: AsyncSession,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[StoryComment]:
        """获取用户的评论历史"""
        result = await session.execute(
            select(StoryComment)
            .where(
                and_(
                    StoryComment.user_id == user_id,
                    StoryComment.status == "visible"
                )
            )
            .order_by(StoryComment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
