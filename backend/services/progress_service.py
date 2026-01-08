"""
进度服务

处理用户进度保存、查询、断点续传等业务逻辑
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ProgressSave, ApiResponse
from backend.db.dao import ProgressDAO


class ProgressService:
    """进度服务"""

    @staticmethod
    async def save_progress(
        session: AsyncSession,
        user_id: str,
        story_id: str,
        progress_data: ProgressSave
    ) -> ApiResponse:
        """
        保存用户进度

        Args:
            session: 数据库会话
            user_id: 用户ID
            story_id: 故事ID
            progress_data: 进度数据

        Returns:
            API响应，包含保存后的进度信息
        """
        progress = await ProgressDAO.save(
            session=session,
            user_id=user_id,
            story_id=story_id,
            current_sequence_id=progress_data.current_event_id,
            current_version_id=progress_data.current_version_id,
            current_chapter_id=progress_data.current_chapter_id,
            current_scene_id=progress_data.current_scene_id,
            play_time=progress_data.play_time
        )

        return ApiResponse(
            success=True,
            message="Progress saved",
            data={
                "story_id": progress.story_id,
                "current_event_id": progress.current_sequence_id,
                "current_version_id": progress.current_version_id,
                "current_chapter_id": progress.current_chapter_id,
                "current_scene_id": progress.current_scene_id,
                "play_time": progress.play_time,
                "last_played_at": progress.last_played_at.isoformat(),
            }
        )

    @staticmethod
    async def get_progress(
        session: AsyncSession,
        user_id: str,
        story_id: str
    ) -> ApiResponse:
        """
        获取用户进度

        Args:
            session: 数据库会话
            user_id: 用户ID
            story_id: 故事ID

        Returns:
            API响应，包含进度信息
        """
        progress = await ProgressDAO.get(session, user_id, story_id)

        if not progress:
            return ApiResponse(
                success=False,
                message="Progress not found",
                error={"code": "PROGRESS_NOT_FOUND", "message": "进度不存在"}
            )

        return ApiResponse(
            success=True,
            data={
                "story_id": progress.story_id,
                "current_event_id": progress.current_sequence_id,
                "current_version_id": progress.current_version_id,
                "current_chapter_id": progress.current_chapter_id,
                "current_scene_id": progress.current_scene_id,
                "play_time": progress.play_time,
                "started_at": progress.started_at.isoformat(),
                "last_played_at": progress.last_played_at.isoformat(),
            }
        )

    @staticmethod
    async def delete_progress(
        session: AsyncSession,
        user_id: str,
        story_id: str
    ) -> ApiResponse:
        """
        删除用户进度

        Args:
            session: 数据库会话
            user_id: 用户ID
            story_id: 故事ID

        Returns:
            API响应
        """
        success = await ProgressDAO.delete(session, user_id, story_id)

        if not success:
            return ApiResponse(
                success=False,
                message="Progress not found",
                error={"code": "PROGRESS_NOT_FOUND", "message": "进度不存在"}
            )

        return ApiResponse(
            success=True,
            message="Progress deleted"
        )


# 全局进度服务实例
progress_service = ProgressService()
