"""
用户进度相关数据模型
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class UserStoryProgressBase(BaseModel):
    """用户进度基础模型"""
    user_id: str = Field(..., description="用户ID")
    story_id: str = Field(..., description="故事ID")
    current_version_id: Optional[str] = Field(None, description="当前活跃的分支版本ID（仅互动叙事）")
    current_sequence_id: Optional[str] = Field(None, description="当前事件的sequence_id")
    current_chapter_id: Optional[str] = Field(None, description="当前章节ID")
    current_scene_id: Optional[str] = Field(None, description="当前场景ID")
    play_time: int = Field(0, description="累计播放时长（秒）")


class ProgressSave(BaseModel):
    """保存进度请求"""
    current_event_id: str = Field(..., description="当前事件的sequence_id")
    current_version_id: Optional[str] = Field(None, description="当前分支版本ID（互动叙事必填）")
    current_chapter_id: Optional[str] = Field(None, description="当前章节ID")
    current_scene_id: Optional[str] = Field(None, description="当前场景ID")
    play_time: Optional[int] = Field(None, description="累计播放时长（秒）")


class ProgressResponse(UserStoryProgressBase):
    """进度响应"""
    id: int = Field(..., description="自增ID")
    started_at: datetime = Field(..., description="开始时间")
    last_played_at: datetime = Field(..., description="最后播放时间")

    class Config:
        from_attributes = True
