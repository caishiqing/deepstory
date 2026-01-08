"""
角色相关数据模型
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class CharacterSource(str, Enum):
    """角色来源"""
    DEFAULT = "DEFAULT"      # 平台通用角色
    USER = "USER"           # 用户自定义
    AI = "AI"              # AI生成


class CharacterCreate(BaseModel):
    """创建角色请求"""
    name: str = Field(..., description="角色名称")
    gender: Optional[str] = Field(None, description="性别")
    age: Optional[str] = Field(None, description="年龄段")
    description: Optional[str] = Field(None, description="角色描述")
    prompt: Optional[str] = Field(None, description="外观描述（用于立绘生成）")


class CharacterModel(BaseModel):
    """角色完整模型"""
    id: str = Field(..., alias="character_id", description="角色ID")
    user_id: Optional[str] = Field(None, description="用户ID（平台角色为NULL）")
    story_id: Optional[str] = Field(None, description="故事ID（平台角色为NULL）")
    source: CharacterSource = Field(..., description="角色来源")
    name: str = Field(..., description="角色名称")
    gender: Optional[str] = Field(None, description="性别")
    prompt: Optional[str] = Field(None, description="外观描述")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息（AI预测）")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True
        populate_by_name = True


class CharacterPortrait(BaseModel):
    """角色立绘"""
    id: str = Field(..., description="立绘ID")
    character_id: str = Field(..., description="角色ID")
    resource_id: str = Field(..., description="资源ID")
    age: str = Field(..., description="年龄段")
    tag: str = Field(..., description="属性标签（情绪/状态）")
    is_default: bool = Field(False, description="是否为默认立绘")
    url: Optional[str] = Field(None, description="资源URL")

    class Config:
        from_attributes = True
