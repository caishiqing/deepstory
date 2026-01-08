"""
评论服务

处理评论相关业务逻辑
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.db.dao import CommentDAO, InteractionDAO, UserDAO, StoryDAO


class CommentService:
    """评论服务"""

    @staticmethod
    async def get_story_comments(
        session: AsyncSession,
        story_id: str,
        current_user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> ApiResponse:
        """
        获取故事评论列表

        Args:
            session: 数据库会话
            story_id: 故事ID
            current_user_id: 当前用户ID（可选，用于判断点赞状态）
            limit: 每页数量
            offset: 偏移量

        Returns:
            API响应，包含评论列表
        """
        # 获取顶级评论
        comments = await CommentDAO.get_story_comments(session, story_id, limit, offset)

        # 构建响应数据
        comment_list = []
        for comment in comments:
            # 获取评论用户信息
            user = await UserDAO.get_by_id(session, comment.user_id)
            if not user:
                continue

            # 获取回复列表（最多3条）
            replies = await CommentDAO.get_replies(session, comment.id, limit=3)
            reply_count = await CommentDAO.count_replies(session, comment.id)

            # 构建回复数据
            reply_list = []
            for reply in replies:
                reply_user = await UserDAO.get_by_id(session, reply.user_id)
                if not reply_user:
                    continue

                # 检查当前用户是否点赞了该回复
                is_liked = False
                if current_user_id:
                    is_liked = await InteractionDAO.is_comment_liked(
                        session, current_user_id, reply.id
                    )

                reply_list.append({
                    "comment_id": reply.id,
                    "user": {
                        "user_id": reply_user.id,
                        "username": reply_user.username
                    },
                    "content": reply.content,
                    "like_count": reply.like_count,
                    "is_liked": is_liked,
                    "created_at": reply.created_at.isoformat()
                })

            # 检查当前用户是否点赞了该评论
            is_liked = False
            if current_user_id:
                is_liked = await InteractionDAO.is_comment_liked(
                    session, current_user_id, comment.id
                )

            comment_list.append({
                "comment_id": comment.id,
                "user": {
                    "user_id": user.id,
                    "username": user.username
                },
                "content": comment.content,
                "like_count": comment.like_count,
                "is_liked": is_liked,
                "reply_count": reply_count,
                "replies": reply_list,
                "status": comment.status,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat()
            })

        return ApiResponse(
            success=True,
            data={
                "comments": comment_list,
                "total": len(comment_list),
                "limit": limit,
                "offset": offset
            }
        )

    @staticmethod
    async def create_comment(
        session: AsyncSession,
        story_id: str,
        user_id: str,
        content: str,
        parent_id: Optional[str] = None
    ) -> ApiResponse:
        """
        发表评论

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID
            content: 评论内容
            parent_id: 父评论ID（回复）

        Returns:
            API响应，包含新创建的评论
        """
        # 验证内容长度
        if not content or len(content) < 1 or len(content) > 500:
            return ApiResponse(
                success=False,
                message="Comment content must be 1-500 characters",
                error={"code": "INVALID_CONTENT", "message": "评论内容必须为1-500字符"}
            )

        # 验证故事是否存在
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 如果是回复，验证父评论是否存在
        if parent_id:
            parent_comment = await CommentDAO.get_by_id(session, parent_id)
            if not parent_comment:
                return ApiResponse(
                    success=False,
                    message="Parent comment not found",
                    error={"code": "PARENT_NOT_FOUND", "message": "父评论不存在"}
                )

            # 检查回复层级（不允许回复的回复）
            if parent_comment.parent_id is not None:
                return ApiResponse(
                    success=False,
                    message="Cannot reply to a reply",
                    error={"code": "MAX_DEPTH_EXCEEDED", "message": "不能回复回复"}
                )

        # 创建评论
        comment = await CommentDAO.create(session, story_id, user_id, content, parent_id)

        # 更新故事评论数
        story.comment_count += 1
        await session.flush()

        # 记录行为日志
        await InteractionDAO.log_action(
            session, user_id, story_id, "comment",
            metadata={"comment_id": comment.id}
        )

        # 获取用户信息
        user = await UserDAO.get_by_id(session, user_id)

        return ApiResponse(
            success=True,
            message="Comment created",
            data={
                "comment_id": comment.id,
                "user": {
                    "user_id": user.id,
                    "username": user.username
                },
                "content": comment.content,
                "created_at": comment.created_at.isoformat()
            }
        )

    @staticmethod
    async def delete_comment(
        session: AsyncSession,
        comment_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        删除评论（软删除）

        Args:
            session: 数据库会话
            comment_id: 评论ID
            user_id: 用户ID

        Returns:
            API响应
        """
        # 获取评论
        comment = await CommentDAO.get_by_id(session, comment_id)
        if not comment:
            return ApiResponse(
                success=False,
                message="Comment not found",
                error={"code": "COMMENT_NOT_FOUND", "message": "评论不存在"}
            )

        # 检查权限
        if comment.user_id != user_id:
            return ApiResponse(
                success=False,
                message="Permission denied",
                error={"code": "PERMISSION_DENIED", "message": "无权限删除"}
            )

        # 软删除
        success = await CommentDAO.soft_delete(session, comment_id)
        if not success:
            return ApiResponse(
                success=False,
                message="Failed to delete comment",
                error={"code": "DELETE_FAILED", "message": "删除失败"}
            )

        # 更新故事评论数
        story = await StoryDAO.get_by_id(session, comment.story_id)
        if story:
            story.comment_count = max(0, story.comment_count - 1)
            await session.flush()

        return ApiResponse(
            success=True,
            message="Comment deleted"
        )

    @staticmethod
    async def like_comment(
        session: AsyncSession,
        comment_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        点赞评论

        Args:
            session: 数据库会话
            comment_id: 评论ID
            user_id: 用户ID

        Returns:
            API响应
        """
        # 检查评论是否存在
        comment = await CommentDAO.get_by_id(session, comment_id)
        if not comment:
            return ApiResponse(
                success=False,
                message="Comment not found",
                error={"code": "COMMENT_NOT_FOUND", "message": "评论不存在"}
            )

        # 检查是否已点赞
        is_liked = await InteractionDAO.is_comment_liked(session, user_id, comment_id)
        if is_liked:
            return ApiResponse(
                success=False,
                message="Already liked",
                error={"code": "ALREADY_LIKED", "message": "已经点赞过了"}
            )

        # 增加点赞数
        await CommentDAO.increment_like_count(session, comment_id)

        # 记录行为日志
        await InteractionDAO.log_action(
            session, user_id, comment.story_id, "comment_like",
            metadata={"comment_id": comment_id}
        )

        return ApiResponse(
            success=True,
            message="Comment liked",
            data={"is_liked": True}
        )

    @staticmethod
    async def unlike_comment(
        session: AsyncSession,
        comment_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        取消点赞评论

        Args:
            session: 数据库会话
            comment_id: 评论ID
            user_id: 用户ID

        Returns:
            API响应
        """
        # 检查评论是否存在
        comment = await CommentDAO.get_by_id(session, comment_id)
        if not comment:
            return ApiResponse(
                success=False,
                message="Comment not found",
                error={"code": "COMMENT_NOT_FOUND", "message": "评论不存在"}
            )

        # 检查是否已点赞
        is_liked = await InteractionDAO.is_comment_liked(session, user_id, comment_id)
        if not is_liked:
            return ApiResponse(
                success=False,
                message="Not liked yet",
                error={"code": "NOT_LIKED", "message": "还未点赞"}
            )

        # 减少点赞数
        await CommentDAO.decrement_like_count(session, comment_id)

        # 记录行为日志
        await InteractionDAO.log_action(
            session, user_id, comment.story_id, "comment_unlike",
            metadata={"comment_id": comment_id}
        )

        return ApiResponse(
            success=True,
            message="Comment unliked",
            data={"is_liked": False}
        )


# 全局评论服务实例
comment_service = CommentService()
