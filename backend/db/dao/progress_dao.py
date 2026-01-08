"""
进度数据访问对象
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from backend.db.models.progress import UserStoryProgress


class ProgressDAO:
    """进度 DAO"""

    @staticmethod
    async def save(
        session: AsyncSession,
        user_id: str,
        story_id: str,
        current_sequence_id: str,
        current_version_id: Optional[str] = None,
        current_chapter_id: Optional[str] = None,
        current_scene_id: Optional[str] = None,
        play_time: Optional[int] = None
    ) -> UserStoryProgress:
        """
        保存进度

        如果进度已存在则更新，否则创建新进度
        """
        # 查找现有进度
        result = await session.execute(
            select(UserStoryProgress).where(
                UserStoryProgress.user_id == user_id,
                UserStoryProgress.story_id == story_id
            )
        )
        progress = result.scalar_one_or_none()

        if progress:
            # 更新现有进度
            progress.current_sequence_id = current_sequence_id
            progress.current_version_id = current_version_id
            progress.current_chapter_id = current_chapter_id
            progress.current_scene_id = current_scene_id
            if play_time is not None:
                progress.play_time = play_time
            progress.last_played_at = datetime.utcnow()
        else:
            # 创建新进度
            progress = UserStoryProgress(
                user_id=user_id,
                story_id=story_id,
                current_sequence_id=current_sequence_id,
                current_version_id=current_version_id,
                current_chapter_id=current_chapter_id,
                current_scene_id=current_scene_id,
                play_time=play_time or 0,
            )
            session.add(progress)

        await session.flush()
        return progress

    @staticmethod
    async def get(
        session: AsyncSession,
        user_id: str,
        story_id: str
    ) -> Optional[UserStoryProgress]:
        """获取进度"""
        result = await session.execute(
            select(UserStoryProgress).where(
                UserStoryProgress.user_id == user_id,
                UserStoryProgress.story_id == story_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(
        session: AsyncSession,
        user_id: str,
        story_id: str
    ) -> bool:
        """删除进度"""
        progress = await ProgressDAO.get(session, user_id, story_id)
        if not progress:
            return False

        await session.delete(progress)
        await session.flush()
        return True
