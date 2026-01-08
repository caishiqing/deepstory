"""
资源相关数据模型
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ResourceType(str, Enum):
    """资源类型"""
    IMAGE = "image"      # 图像（背景、立绘）
    AUDIO = "audio"      # 音频（音乐、音效、配音）
    VIDEO = "video"      # 视频


class ResourceModel(BaseModel):
    """资源模型"""
    id: str = Field(..., alias="resource_id", description="资源ID")
    story_id: Optional[str] = Field(None, description="故事ID")
    character_id: Optional[str] = Field(None, description="角色ID（立绘）")
    type: ResourceType = Field(..., description="资源类型")
    url: str = Field(..., description="资源URL")
    size: Optional[int] = Field(None, description="文件大小（字节）")
    duration: Optional[float] = Field(None, description="时长（秒，音视频）")
    width: Optional[int] = Field(None, description="宽度（图像）")
    height: Optional[int] = Field(None, description="高度（图像）")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True
        populate_by_name = True
