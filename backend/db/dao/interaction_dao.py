"""
用户互动数据访问对象（点赞、收藏）
"""

from typing import List, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.behavior_log import UserBehaviorLog
from backend.db.models.story import Story


class InteractionDAO:
    """互动 DAO（点赞、收藏）"""

    @staticmethod
    async def log_action(
        session: AsyncSession,
        user_id: str,
        story_id: str,
        action: str,
        metadata: Optional[dict] = None
    ) -> UserBehaviorLog:
        """
        记录用户行为

        Args:
            session: 数据库会话
            user_id: 用户ID
            story_id: 故事ID
            action: 行为类型（like/unlike/favorite/unfavorite）
            metadata: 附加信息

        Returns:
            UserBehaviorLog: 行为日志
        """
        log = UserBehaviorLog(
            user_id=user_id,
            story_id=story_id,
            action=action,
            metadata=metadata or {}
        )

        session.add(log)
        await session.flush()

        return log

    @staticmethod
    async def is_liked(
        session: AsyncSession,
        user_id: str,
        story_id: str
    ) -> bool:
        """
        检查用户是否已点赞故事

        通过查询最近的 like/unlike 行为判断
        """
        result = await session.execute(
            select(UserBehaviorLog.action)
            .where(
                and_(
                    UserBehaviorLog.user_id == user_id,
                    UserBehaviorLog.story_id == story_id,
                    UserBehaviorLog.action.in_(["like", "unlike"])
                )
            )
            .order_by(UserBehaviorLog.created_at.desc())
            .limit(1)
        )
        last_action = result.scalar_one_or_none()
        return last_action == "like"

    @staticmethod
    async def is_favorited(
        session: AsyncSession,
        user_id: str,
        story_id: str
    ) -> bool:
        """
        检查用户是否已收藏故事

        通过查询最近的 favorite/unfavorite 行为判断
        """
        result = await session.execute(
            select(UserBehaviorLog.action)
            .where(
                and_(
                    UserBehaviorLog.user_id == user_id,
                    UserBehaviorLog.story_id == story_id,
                    UserBehaviorLog.action.in_(["favorite", "unfavorite"])
                )
            )
            .order_by(UserBehaviorLog.created_at.desc())
            .limit(1)
        )
        last_action = result.scalar_one_or_none()
        return last_action == "favorite"

    @staticmethod
    async def get_user_favorites(
        session: AsyncSession,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Story]:
        """
        获取用户收藏的故事列表

        Args:
            session: 数据库会话
            user_id: 用户ID
            limit: 每页数量
            offset: 偏移量

        Returns:
            故事列表
        """
        # 子查询：获取用户收藏的故事ID
        subquery = (
            select(
                UserBehaviorLog.story_id,
                func.max(UserBehaviorLog.created_at).label('last_action_time')
            )
            .where(
                and_(
                    UserBehaviorLog.user_id == user_id,
                    UserBehaviorLog.action.in_(["favorite", "unfavorite"])
                )
            )
            .group_by(UserBehaviorLog.story_id)
            .subquery()
        )

        # 获取最后一次行为是 favorite 的故事
        result = await session.execute(
            select(Story)
            .join(
                UserBehaviorLog,
                and_(
                    Story.id == UserBehaviorLog.story_id,
                    UserBehaviorLog.user_id == user_id,
                    UserBehaviorLog.action == "favorite"
                )
            )
            .join(
                subquery,
                and_(
                    Story.id == subquery.c.story_id,
                    UserBehaviorLog.created_at == subquery.c.last_action_time
                )
            )
            .order_by(UserBehaviorLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def is_comment_liked(
        session: AsyncSession,
        user_id: str,
        comment_id: str
    ) -> bool:
        """
        检查用户是否已点赞评论

        通过查询最近的 comment_like/comment_unlike 行为判断
        """
        result = await session.execute(
            select(UserBehaviorLog.action)
            .where(
                and_(
                    UserBehaviorLog.user_id == user_id,
                    UserBehaviorLog.action.in_(["comment_like", "comment_unlike"]),
                    UserBehaviorLog.metadata["comment_id"].astext == comment_id
                )
            )
            .order_by(UserBehaviorLog.created_at.desc())
            .limit(1)
        )
        last_action = result.scalar_one_or_none()
        return last_action == "comment_like"
