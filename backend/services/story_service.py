"""
故事服务

处理故事创建、查询、SSE流、状态管理等业务逻辑
"""

from typing import Optional, AsyncIterator
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    StoryCreate, StoryStatus, StoryType, ApiResponse
)
from backend.db.dao import StoryDAO, PromptDAO
from backend.services.narrative_service import NarrativeService
from backend.services.sse_service import SSEService
from engine import StoryInput
from engine.models import Character, Relationship, StoryTags


class StoryService:
    """故事服务"""

    def __init__(self):
        self.narrative_service = NarrativeService()
        self.sse_service = SSEService()

    async def create_story(
        self,
        session: AsyncSession,
        user_id: str,
        story_data: StoryCreate
    ) -> ApiResponse:
        """
        创建故事

        Args:
            session: 数据库会话
            user_id: 用户ID
            story_data: 故事创建数据

        Returns:
            API响应，包含故事信息
        """
        # 创建故事记录
        story = await StoryDAO.create(
            session=session,
            prompt_id=story_data.prompt_id,
            user_id=user_id,
            story_type=story_data.type.value
        )

        # 返回SSE端点
        sse_endpoint = f"/api/v1/story/{story.id}/stream"

        return ApiResponse(
            success=True,
            message="Story created",
            data={
                "story_id": story.id,
                "prompt_id": story.prompt_id,
                "type": story.type,
                "title": story.title,
                "status": story.status,
                "sse_endpoint": sse_endpoint,
                "created_at": story.created_at.isoformat(),
            }
        )

    async def get_story(
        self,
        session: AsyncSession,
        story_id: str,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        获取故事详情

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 当前用户ID（可选）

        Returns:
            API响应，包含故事详情
        """
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        return ApiResponse(
            success=True,
            data={
                "id": story.id,
                "prompt_id": story.prompt_id,
                "user_id": story.user_id,
                "type": story.type,
                "title": story.title,
                "cover_url": story.cover_url,
                "status": story.status,
                "visibility": story.visibility,
                "play_count": story.play_count,
                "like_count": story.like_count,
                "favorite_count": story.favorite_count,
                "pricing_type": story.pricing_type,
                "price": float(story.price),
                "created_at": story.created_at.isoformat(),
            }
        )

    async def get_story_status(
        self,
        session: AsyncSession,
        story_id: str
    ) -> ApiResponse:
        """
        查询故事状态（轻量）

        用于创作阶段轮询查询生成状态

        Args:
            session: 数据库会话
            story_id: 故事ID

        Returns:
            API响应，包含状态信息
        """
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 根据状态返回不同的消息
        message_map = {
            StoryStatus.PENDING.value: "Generating thinking ...",
            StoryStatus.GENERATING.value: "Generating script ...",
            StoryStatus.DYNAMIC.value: "Create completed.",
            StoryStatus.COMPLETED.value: "Create completed.",
            StoryStatus.ERROR.value: "Generation failed.",
        }

        return ApiResponse(
            success=True,
            data={
                "story_id": story.id,
                "status": story.status,
                "progress": 0 if story.status == StoryStatus.PENDING.value else 100,
                "message": message_map.get(story.status, "Processing..."),
                "retry_after": 10,
            }
        )

    async def stream_story(
        self,
        session: AsyncSession,
        story_id: str,
        from_sequence_id: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        流式推送故事事件（SSE）

        Args:
            session: 数据库会话
            story_id: 故事ID
            from_sequence_id: 断点续传起点（可选）

        Yields:
            SSE格式的事件字符串
        """
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            # 推送错误事件
            error_event = self.sse_service.format_error_event(
                "STORY_NOT_FOUND",
                "Story not found"
            )
            yield error_event
            return

        # 更新故事状态为生成中
        if story.status == StoryStatus.PENDING.value:
            await StoryDAO.update_status(session, story_id, StoryStatus.GENERATING.value)

        # 获取关联的创意输入
        prompt = await PromptDAO.get_by_id(session, story.prompt_id)
        if not prompt:
            error_event = self.sse_service.format_error_event(
                "PROMPT_NOT_FOUND",
                "Story prompt not found"
            )
            yield error_event
            return

        # 构造故事输入模型
        story_input = StoryInput(
            logline=prompt.logline,
            characters=[Character(**char) for char in (prompt.character_inputs or [])],
            tags=StoryTags(**(prompt.themes or {})),
            relationships=None  # 暂时没有关系数据
        )

        # 通过 NarrativeService 获取事件流
        sequence_counter = 1
        try:
            async for event in self.narrative_service.generate_story_stream(
                story_input=story_input,
                request_id=story_id,
                narration_voice=None  # 使用默认旁白音色
            ):
                # 生成序列 ID
                sequence_id = f"{story_id}_seq_{sequence_counter:04d}"
                sequence_counter += 1

                # 转换为 SSE 格式
                sse_message = self.sse_service.format_story_event(
                    event=event,
                    sequence_id=sequence_id,
                    path_id="root0000"
                )

                # 只推送非空消息
                if sse_message:
                    yield sse_message

                # 如果是 story_end 事件，更新故事状态
                if event.event_type == "story_end":
                    await StoryDAO.update_status(session, story_id, StoryStatus.COMPLETED.value)
                    break
        except Exception as e:
            # 推送错误事件
            await StoryDAO.update_status(session, story_id, StoryStatus.ERROR.value, str(e))
            error_event = self.sse_service.format_error_event(
                "GENERATION_ERROR",
                str(e)
            )
            yield error_event

    async def publish_story(
        self,
        session: AsyncSession,
        story_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        发布故事

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID

        Returns:
            API响应
        """
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 检查权限
        if story.user_id != user_id:
            return ApiResponse(
                success=False,
                message="Permission denied",
                error={"code": "PERMISSION_DENIED", "message": "无权限操作"}
            )

        # 检查发布条件
        story_type = story.type
        story_status = story.status

        if story_type == StoryType.LINEAR.value and story_status != StoryStatus.COMPLETED.value:
            return ApiResponse(
                success=False,
                message="Linear story must be completed before publishing",
                error={"code": "PUBLISH_NOT_ALLOWED", "current_status": story_status}
            )

        if story_type == StoryType.INTERACTIVE.value and story_status not in [
            StoryStatus.DYNAMIC.value, StoryStatus.COMPLETED.value
        ]:
            return ApiResponse(
                success=False,
                message="Story must have content before publishing",
                error={"code": "PUBLISH_NOT_ALLOWED", "current_status": story_status}
            )

        # 发布故事
        await StoryDAO.publish(session, story_id)

        return ApiResponse(
            success=True,
            message="Story published",
            data={
                "story_id": story_id,
                "is_published": True,
                "published_at": datetime.utcnow().isoformat(),
            }
        )


# 全局故事服务实例
story_service = StoryService()
