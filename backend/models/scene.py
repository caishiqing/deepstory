"""
场景相关数据模型
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SceneBase(BaseModel):
    """场景基础模型"""
    story_id: str = Field(..., description="所属故事ID")
    scene_id: str = Field(..., description="场景ID（故事内唯一）")
    scene_name: Optional[str] = Field(None, description="场景名称")
    background_resource_id: Optional[str] = Field(None, description="背景资源ID")
    music_resource_id: Optional[str] = Field(None, description="音乐资源ID")
    ambient_resource_id: Optional[str] = Field(None, description="环境音资源ID")
    transition_config: Optional[Dict[str, Any]] = Field(None, description="转场配置")


class SceneCreate(SceneBase):
    """创建场景请求"""
    pass


class SceneUpdate(BaseModel):
    """更新场景请求"""
    scene_name: Optional[str] = None
    background_resource_id: Optional[str] = None
    music_resource_id: Optional[str] = None
    ambient_resource_id: Optional[str] = None
    transition_config: Optional[Dict[str, Any]] = None


class SceneResponse(SceneBase):
    """场景响应"""
    id: int = Field(..., description="自增ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True
