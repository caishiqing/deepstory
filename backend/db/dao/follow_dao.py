"""
关注关系数据访问对象
"""

from typing import List, Tuple
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.follow import UserFollow
from backend.db.models.user import User


class FollowDAO:
    """关注关系 DAO"""

    @staticmethod
    async def create(
        session: AsyncSession,
        follower_id: str,
        following_id: str
    ) -> UserFollow:
        """
        创建关注关系

        Args:
            session: 数据库会话
            follower_id: 关注者ID
            following_id: 被关注者ID

        Returns:
            UserFollow: 新创建的关注关系
        """
        follow = UserFollow(
            follower_id=follower_id,
            following_id=following_id,
        )

        session.add(follow)
        await session.flush()

        return follow

    @staticmethod
    async def delete(
        session: AsyncSession,
        follower_id: str,
        following_id: str
    ) -> bool:
        """
        删除关注关系

        Args:
            session: 数据库会话
            follower_id: 关注者ID
            following_id: 被关注者ID

        Returns:
            是否删除成功
        """
        result = await session.execute(
            select(UserFollow).where(
                and_(
                    UserFollow.follower_id == follower_id,
                    UserFollow.following_id == following_id
                )
            )
        )
        follow = result.scalar_one_or_none()

        if not follow:
            return False

        await session.delete(follow)
        await session.flush()
        return True

    @staticmethod
    async def is_following(
        session: AsyncSession,
        follower_id: str,
        following_id: str
    ) -> bool:
        """
        检查是否已关注

        Args:
            session: 数据库会话
            follower_id: 关注者ID
            following_id: 被关注者ID

        Returns:
            是否已关注
        """
        result = await session.execute(
            select(func.count(UserFollow.id)).where(
                and_(
                    UserFollow.follower_id == follower_id,
                    UserFollow.following_id == following_id
                )
            )
        )
        count = result.scalar()
        return count > 0

    @staticmethod
    async def get_following_list(
        session: AsyncSession,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Tuple[User, UserFollow]]:
        """
        获取用户的关注列表

        Args:
            session: 数据库会话
            user_id: 用户ID
            limit: 每页数量
            offset: 偏移量

        Returns:
            (被关注用户, 关注关系) 元组列表
        """
        result = await session.execute(
            select(User, UserFollow)
            .join(UserFollow, User.id == UserFollow.following_id)
            .where(UserFollow.follower_id == user_id)
            .order_by(UserFollow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    @staticmethod
    async def get_follower_list(
        session: AsyncSession,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Tuple[User, UserFollow]]:
        """
        获取用户的粉丝列表

        Args:
            session: 数据库会话
            user_id: 用户ID
            limit: 每页数量
            offset: 偏移量

        Returns:
            (粉丝用户, 关注关系) 元组列表
        """
        result = await session.execute(
            select(User, UserFollow)
            .join(UserFollow, User.id == UserFollow.follower_id)
            .where(UserFollow.following_id == user_id)
            .order_by(UserFollow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    @staticmethod
    async def count_following(session: AsyncSession, user_id: str) -> int:
        """统计用户关注的人数"""
        result = await session.execute(
            select(func.count(UserFollow.id)).where(
                UserFollow.follower_id == user_id
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def count_followers(session: AsyncSession, user_id: str) -> int:
        """统计用户的粉丝数"""
        result = await session.execute(
            select(func.count(UserFollow.id)).where(
                UserFollow.following_id == user_id
            )
        )
        return result.scalar() or 0
