"""
SSE 事件封装服务

将 Engine 产出的事件转换为符合 API 规范的 SSE 格式
"""

import json
import asyncio
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from engine import (
    NarrativeEvent,
    StoryStartEvent,
    StoryEndEvent,
    ChapterStartEvent,
    ChapterEndEvent,
    SceneStartEvent,
    SceneEndEvent,
    DialogueEvent,
    NarrationEvent,
    AudioEvent,
)
from backend.config import narrative_config


class SSEService:
    """SSE 事件服务"""

    def __init__(self):
        self.narrative_config = narrative_config

    async def stream_events(
        self,
        events: AsyncIterator[NarrativeEvent],
        story_id: str,
        path_id: str = "root0000",
        character_map: Optional[Dict[str, Dict[str, str]]] = None
    ) -> AsyncIterator[str]:
        """
        流式输出 SSE 事件

        Args:
            events: 叙事引擎产出的事件流
            story_id: 故事ID
            path_id: 路径ID（分支标识）
            character_map: 角色映射 {character_name: {id, color}}

        Yields:
            SSE 格式的事件字符串
        """
        sequence_counter = 1
        last_heartbeat = asyncio.get_event_loop().time()

        try:
            async for event in events:
                # 生成 sequence_id
                sequence_id = f"{story_id}_seq_{sequence_counter:04d}"
                sequence_counter += 1

                # 转换为 SSE 事件
                sse_event = self._convert_to_sse(
                    event,
                    sequence_id=sequence_id,
                    path_id=path_id,
                    character_map=character_map or {}
                )

                if sse_event:
                    yield self._format_sse(sse_event)
                    last_heartbeat = asyncio.get_event_loop().time()

                # 心跳包（30秒无事件时发送）
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > 30:
                    yield self._format_heartbeat()
                    last_heartbeat = current_time

        except Exception as e:
            logger.error(f"SSE streaming error: {e}")
            yield self._format_error("AI_GENERATION_FAILED", str(e))

    def _convert_to_sse(
        self,
        event: NarrativeEvent,
        sequence_id: str,
        path_id: str,
        character_map: Dict[str, Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """
        将引擎事件转换为 API 格式

        返回标准 SSE 事件结构：
        {
            "sequence_id": "...",
            "path_id": "...",
            "event_category": "story",
            "event_type": "...",
            "timestamp": "...",
            "content": {...}
        }
        """
        timestamp = datetime.utcnow().isoformat() + "Z"

        # story_start
        if isinstance(event, StoryStartEvent):
            return {
                "sequence_id": sequence_id,
                "path_id": path_id,
                "event_category": "story",
                "event_type": "story_start",
                "timestamp": timestamp,
                "content": {
                    "story_id": sequence_id.split("_seq_")[0],
                    "title": event.title,
                    "message": "故事即将开始..."
                }
            }

        # story_end
        elif isinstance(event, StoryEndEvent):
            return {
                "sequence_id": sequence_id,
                "path_id": path_id,
                "event_category": "story",
                "event_type": "story_end",
                "timestamp": timestamp,
                "content": {
                    "story_id": sequence_id.split("_seq_")[0],
                    "message": "故事已完结"
                }
            }

        # chapter_start
        elif isinstance(event, ChapterStartEvent):
            return {
                "sequence_id": sequence_id,
                "path_id": path_id,
                "event_category": "story",
                "event_type": "chapter_start",
                "timestamp": timestamp,
                "content": {
                    "chapter_id": f"chapter_{event.chapter_index}",
                    "chapter_number": event.chapter_index,
                    "title": event.title,
                    "message": "新的篇章即将展开..."
                }
            }

        # chapter_end
        elif isinstance(event, ChapterEndEvent):
            return {
                "sequence_id": sequence_id,
                "path_id": path_id,
                "event_category": "story",
                "event_type": "chapter_end",
                "timestamp": timestamp,
                "content": {
                    "chapter_id": f"chapter_{event.chapter_index}",
                    "chapter_number": event.chapter_index,
                    "message": f"第{event.chapter_index}章完结"
                }
            }

        # scene_start
        elif isinstance(event, SceneStartEvent):
            content = {
                "scene_id": event.scene_id,
                "scene_name": event.title,
                "background": {
                    "url": event.background_url
                } if event.background_url else None,
                "transition": self.narrative_config.get_scene_start_transition()
            }

            # 添加音乐和环境音（如果有）
            # 注：这里需要从 AudioEvent 中提取，或在 SceneStartEvent 中补充

            return {
                "sequence_id": sequence_id,
                "path_id": path_id,
                "event_category": "story",
                "event_type": "scene_start",
                "timestamp": timestamp,
                "content": content
            }

        # scene_end
        elif isinstance(event, SceneEndEvent):
            return {
                "sequence_id": sequence_id,
                "path_id": path_id,
                "event_category": "story",
                "event_type": "scene_end",
                "timestamp": timestamp,
                "content": {
                    "scene_id": event.scene_id,
                    "transition": self.narrative_config.get_scene_end_transition()
                }
            }

        # dialogue
        elif isinstance(event, DialogueEvent):
            char_info = character_map.get(event.character, {})
            character_id = char_info.get("id", f"char_{event.character}")
            character_color = char_info.get("color", self.narrative_config.get_character_color())

            content = {
                "character_id": character_id,
                "character_name": event.character,
                "character_color": character_color,
                "text": event.text,
                "emotion": event.emotion,
                "auto_hide": True
            }

            # 添加立绘
            if event.image_url:
                content["show"] = {
                    "url": event.image_url,
                    "position": event.portrait_position or self.narrative_config.default_portrait_position
                }

            # 添加配音
            if event.voice_url:
                content["voice"] = {
                    "voice_id": event.voice_id,
                    "url": event.voice_url,
                    "duration": event.voice_duration
                }

            return {
                "sequence_id": sequence_id,
                "path_id": path_id,
                "event_category": "story",
                "event_type": "dialogue",
                "timestamp": timestamp,
                "content": content
            }

        # narration
        elif isinstance(event, NarrationEvent):
            content = {
                "text": event.text,
                "window": "show"
            }

            # 添加配音
            if event.voice_url:
                content["voice"] = {
                    "voice_id": event.voice_id,
                    "url": event.voice_url,
                    "duration": event.voice_duration
                }

            return {
                "sequence_id": sequence_id,
                "path_id": path_id,
                "event_category": "story",
                "event_type": "narration",
                "timestamp": timestamp,
                "content": content
            }

        # play_audio (音频事件)
        elif isinstance(event, AudioEvent):
            if event.audio_url:
                return {
                    "sequence_id": sequence_id,
                    "path_id": path_id,
                    "event_category": "story",
                    "event_type": "play_audio",
                    "timestamp": timestamp,
                    "content": {
                        "channel": event.channel or "sound",
                        "url": event.audio_url
                    }
                }

        return None

    def format_story_event(
        self,
        event: NarrativeEvent,
        sequence_id: str = None,
        path_id: str = "root0000",
        character_map: Optional[Dict[str, Dict[str, str]]] = None
    ) -> str:
        """
        格式化单个故事事件为 SSE 消息（公开方法）

        Args:
            event: 叙事事件
            sequence_id: 序列ID（可选，不提供则自动生成）
            path_id: 路径ID
            character_map: 角色映射

        Returns:
            SSE 格式的字符串
        """
        # 自动生成 sequence_id
        if sequence_id is None:
            sequence_id = f"seq_{int(asyncio.get_event_loop().time() * 1000)}"

        # 转换为 SSE 事件
        sse_event = self._convert_to_sse(
            event,
            sequence_id=sequence_id,
            path_id=path_id,
            character_map=character_map or {}
        )

        # 格式化并返回
        if sse_event:
            return self._format_sse(sse_event)

        # 如果事件不需要推送，返回空字符串
        return ""

    def _format_sse(self, event: Dict[str, Any]) -> str:
        """格式化为 SSE 消息"""
        sequence_id = event.get("sequence_id", "")
        event_data = json.dumps(event, ensure_ascii=False)

        return f"event: story_event\nid: {sequence_id}\ndata: {event_data}\n\n"

    def format_error_event(self, error_code: str, message: str) -> str:
        """
        格式化错误事件为 SSE 消息（公开方法）

        Args:
            error_code: 错误代码
            message: 错误消息

        Returns:
            SSE 格式的错误消息
        """
        return self._format_error(error_code, message)

    def _format_heartbeat(self) -> str:
        """格式化心跳包"""
        heartbeat = {
            "sequence_id": f"heartbeat_{int(asyncio.get_event_loop().time())}",
            "event_category": "system",
            "event_type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "content": {
                "server_time": datetime.utcnow().isoformat() + "Z"
            }
        }
        data = json.dumps(heartbeat, ensure_ascii=False)
        return f"event: system_event\ndata: {data}\n\n"

    def _format_error(self, error_code: str, message: str) -> str:
        """格式化错误消息"""
        error = {
            "sequence_id": f"error_{int(asyncio.get_event_loop().time())}",
            "event_category": "system",
            "event_type": "error",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "content": {
                "error_code": error_code,
                "message": message,
                "retry_after": 5
            }
        }
        data = json.dumps(error, ensure_ascii=False)
        return f"event: system_event\ndata: {data}\n\n"
