"""
关注服务

处理用户关注相关业务逻辑
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.db.dao import FollowDAO, UserDAO


class FollowService:
    """关注服务"""

    @staticmethod
    async def follow_user(
        session: AsyncSession,
        follower_id: str,
        following_id: str
    ) -> ApiResponse:
        """
        关注用户

        Args:
            session: 数据库会话
            follower_id: 关注者ID
            following_id: 被关注者ID

        Returns:
            API响应
        """
        # 不能关注自己
        if follower_id == following_id:
            return ApiResponse(
                success=False,
                message="Cannot follow yourself",
                error={"code": "INVALID_OPERATION", "message": "不能关注自己"}
            )

        # 检查被关注用户是否存在
        following_user = await UserDAO.get_by_id(session, following_id)
        if not following_user:
            return ApiResponse(
                success=False,
                message="User not found",
                error={"code": "USER_NOT_FOUND", "message": "用户不存在"}
            )

        # 检查是否已关注
        is_following = await FollowDAO.is_following(session, follower_id, following_id)
        if is_following:
            return ApiResponse(
                success=False,
                message="Already following",
                error={"code": "ALREADY_FOLLOWING", "message": "已经关注了"}
            )

        # 创建关注关系
        await FollowDAO.create(session, follower_id, following_id)

        # 更新双方的关注/粉丝数
        follower = await UserDAO.get_by_id(session, follower_id)
        if follower:
            follower.following_count += 1

        following_user.follower_count += 1

        await session.flush()

        return ApiResponse(
            success=True,
            message="Followed successfully",
            data={"is_following": True}
        )

    @staticmethod
    async def unfollow_user(
        session: AsyncSession,
        follower_id: str,
        following_id: str
    ) -> ApiResponse:
        """
        取消关注用户

        Args:
            session: 数据库会话
            follower_id: 关注者ID
            following_id: 被关注者ID

        Returns:
            API响应
        """
        # 检查是否已关注
        is_following = await FollowDAO.is_following(session, follower_id, following_id)
        if not is_following:
            return ApiResponse(
                success=False,
                message="Not following",
                error={"code": "NOT_FOLLOWING", "message": "还未关注"}
            )

        # 删除关注关系
        success = await FollowDAO.delete(session, follower_id, following_id)
        if not success:
            return ApiResponse(
                success=False,
                message="Failed to unfollow",
                error={"code": "UNFOLLOW_FAILED", "message": "取消关注失败"}
            )

        # 更新双方的关注/粉丝数
        follower = await UserDAO.get_by_id(session, follower_id)
        if follower:
            follower.following_count = max(0, follower.following_count - 1)

        following_user = await UserDAO.get_by_id(session, following_id)
        if following_user:
            following_user.follower_count = max(0, following_user.follower_count - 1)

        await session.flush()

        return ApiResponse(
            success=True,
            message="Unfollowed successfully",
            data={"is_following": False}
        )

    @staticmethod
    async def get_following_list(
        session: AsyncSession,
        user_id: str,
        current_user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> ApiResponse:
        """
        获取用户的关注列表

        Args:
            session: 数据库会话
            user_id: 用户ID
            current_user_id: 当前用户ID（用于判断是否关注）
            limit: 每页数量
            offset: 偏移量

        Returns:
            API响应，包含关注列表
        """
        # 获取关注列表
        following_list = await FollowDAO.get_following_list(session, user_id, limit, offset)

        # 构建响应数据
        users = []
        for user, follow in following_list:
            # 检查当前用户是否关注了列表中的用户
            is_following = False
            if current_user_id and current_user_id != user.id:
                is_following = await FollowDAO.is_following(session, current_user_id, user.id)

            users.append({
                "user_id": user.id,
                "username": user.username,
                "follower_count": user.follower_count,
                "following_count": user.following_count,
                "is_following": is_following,
                "followed_at": follow.created_at.isoformat()
            })

        return ApiResponse(
            success=True,
            data={
                "users": users,
                "total": len(users),
                "limit": limit,
                "offset": offset
            }
        )

    @staticmethod
    async def get_follower_list(
        session: AsyncSession,
        user_id: str,
        current_user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> ApiResponse:
        """
        获取用户的粉丝列表

        Args:
            session: 数据库会话
            user_id: 用户ID
            current_user_id: 当前用户ID（用于判断是否关注）
            limit: 每页数量
            offset: 偏移量

        Returns:
            API响应，包含粉丝列表
        """
        # 获取粉丝列表
        follower_list = await FollowDAO.get_follower_list(session, user_id, limit, offset)

        # 构建响应数据
        users = []
        for user, follow in follower_list:
            # 检查当前用户是否关注了列表中的用户
            is_following = False
            if current_user_id and current_user_id != user.id:
                is_following = await FollowDAO.is_following(session, current_user_id, user.id)

            users.append({
                "user_id": user.id,
                "username": user.username,
                "follower_count": user.follower_count,
                "following_count": user.following_count,
                "is_following": is_following,
                "followed_at": follow.created_at.isoformat()
            })

        return ApiResponse(
            success=True,
            data={
                "users": users,
                "total": len(users),
                "limit": limit,
                "offset": offset
            }
        )


# 全局关注服务实例
follow_service = FollowService()
