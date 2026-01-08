"""
故事事件相关数据模型
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class StoryEventBase(BaseModel):
    """故事事件基础模型"""
    story_id: str = Field(..., description="所属故事ID")
    sequence_id: str = Field(..., description="全局唯一序列ID（ULID）")
    next_sequence_id: Optional[str] = Field(None, description="下一个事件的序列ID")
    event_category: str = Field(..., description="事件类别（story/system）")
    event_type: str = Field(..., description="具体事件类型")
    content: Dict[str, Any] = Field(..., description="事件内容")
    chapter_id: Optional[str] = Field(None, description="所属章节ID")
    scene_id: Optional[str] = Field(None, description="所属场景ID")
    timestamp: str = Field(..., description="事件时间戳")


class StoryEventCreate(StoryEventBase):
    """创建故事事件请求"""
    pass


class StoryEventResponse(StoryEventBase):
    """故事事件响应"""
    id: int = Field(..., description="自增ID")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True
