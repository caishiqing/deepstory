"""
叙事服务 - 封装 StoryEngine 和 StreamingConsumer

提供高层API供路由层调用
"""

from typing import AsyncIterator, Optional, Dict, Any
from loguru import logger

from engine import StoryEngine, StreamingConsumer, StoryInput
from cache import init_redis
from backend.config.narrative import NarrativeConfig


class NarrativeService:
    """叙事服务"""

    def __init__(self, resource_timeout: float = None):
        """
        Args:
            resource_timeout: 资源等待超时时间（秒），None 则使用配置默认值
        """
        self.default_narration_voice = NarrativeConfig.DEFAULT_NARRATION_VOICE
        self.resource_timeout = resource_timeout or NarrativeConfig.RESOURCE_TIMEOUT

    async def create_story_engine(
        self,
        story_input: StoryInput,
        request_id: str,
        narration_voice: Optional[str] = None
    ) -> StoryEngine:
        """
        创建故事引擎实例

        Args:
            story_input: 故事创意输入模型
            request_id: 请求ID
            narration_voice: 旁白音色ID

        Returns:
            StoryEngine 实例
        """
        engine = StoryEngine(
            story_input=story_input,
            request_id=request_id,
            narration_voice=narration_voice or self.default_narration_voice
        )

        await engine.initialize()
        return engine

    async def generate_story_stream(
        self,
        story_input: StoryInput,
        request_id: str,
        narration_voice: Optional[str] = None
    ) -> AsyncIterator:
        """
        流式生成故事（包含资源URL）

        Args:
            story_input: 故事创意输入模型
            request_id: 请求ID
            narration_voice: 旁白音色ID

        Yields:
            完整的叙事事件（包含资源URL）
        """
        engine = None
        try:
            # 创建引擎
            engine = await self.create_story_engine(
                story_input=story_input,
                request_id=request_id,
                narration_voice=narration_voice
            )

            # 创建流式消费者
            consumer = StreamingConsumer(engine.tracker, resource_timeout=self.resource_timeout)

            # 清空任务队列（可选）
            if engine.task_manager:
                await engine.task_manager.clear_all_queues()

            # 流式输出事件（自动等待资源就绪）
            async for event in consumer.stream(engine):
                yield event

        except Exception as e:
            logger.error(f"Story generation error: {e}")
            raise

        finally:
            # 关闭引擎
            if engine:
                await engine.shutdown()

    async def get_story_status(self, request_id: str) -> Dict[str, Any]:
        """
        获取故事生成状态（创作阶段轮询用）

        Args:
            request_id: 请求ID

        Returns:
            状态信息字典
        """
        # TODO: 从 Redis/数据库查询状态
        # 这里需要结合实际存储实现
        return {
            "status": "generating",
            "progress": 50,
            "message": "Generating script...",
            "retry_after": 10
        }

    def prepare_story_input(
        self,
        logline: str,
        characters: list,
        tags: dict,
        relationships: list = None
    ) -> StoryInput:
        """
        准备故事输入（创建 StoryInput 模型）

        Args:
            logline: 一句话梗概
            characters: 角色列表（字典列表）
            tags: 标签配置（字典）
            relationships: 人物关系列表（字典列表，可选）

        Returns:
            StoryInput 模型实例
        """
        from engine.models import Character, Relationship, StoryTags

        return StoryInput(
            logline=logline,
            characters=[Character(**char) for char in characters],
            tags=StoryTags(**tags),
            relationships=[Relationship(**rel) for rel in relationships] if relationships else None
        )
