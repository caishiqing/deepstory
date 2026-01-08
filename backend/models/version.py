"""
故事版本相关数据模型（互动叙事专用）
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class StoryVersionBase(BaseModel):
    """故事版本基础模型"""
    story_id: str = Field(..., description="所属故事ID")
    prev_id: Optional[str] = Field(None, description="父版本ID")
    pioneer_user_id: str = Field(..., description="开拓者用户ID")
    fork_sequence_id: Optional[str] = Field(None, description="分叉点的choice事件sequence_id")
    option_id: Optional[str] = Field(None, description="在分叉点选择的选项ID")
    current_sequence_id: str = Field(..., description="当前位置的sequence_id（开拓高水位）")
    current_event_type: str = Field(..., description="当前位置的事件类型")
    view_count: int = Field(0, description="访问/播放次数")


class StoryVersionCreate(StoryVersionBase):
    """创建故事版本请求"""
    pass


class StoryVersionResponse(StoryVersionBase):
    """故事版本响应"""
    id: str = Field(..., description="版本ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True
