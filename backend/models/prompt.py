"""
创意输入相关数据模型
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class CharacterBasicInfo(BaseModel):
    """角色基础信息"""
    gender: str = Field(..., description="性别")
    age: int = Field(..., description="年龄")
    occupation: Optional[str] = Field(None, description="职业")


class CharacterInput(BaseModel):
    """用户输入的角色信息"""
    name: str = Field(..., description="角色名称")
    basic_info: CharacterBasicInfo = Field(..., description="基础信息")
    description: str = Field(..., description="角色描述")


class CharacterRelationship(BaseModel):
    """角色关系"""
    subject: str = Field(..., description="主体角色（名称或ID）")
    object: str = Field(..., description="客体角色（名称或ID）")
    relationship: str = Field(..., description="关系描述")


class ThemesConfig(BaseModel):
    """主题配置"""
    genre: str = Field(..., description="题材类型")
    tone: str = Field(..., description="情感基调")
    setting: str = Field(..., description="世界观设定")
    style: Optional[str] = Field(None, description="叙事风格")
    tags: List[str] = Field(default_factory=list, description="标签列表")


class PromptBase(BaseModel):
    """创意输入基础模型"""
    logline: str = Field(..., description="一句话梗概")
    characters: List[CharacterInput] = Field(..., description="角色列表")
    relationships: Optional[List[CharacterRelationship]] = Field(None, description="角色关系")
    themes: ThemesConfig = Field(..., description="主题配置")


class PromptCreate(PromptBase):
    """创建创意输入请求"""
    pass


class PromptUpdate(BaseModel):
    """更新创意输入请求（所有字段可选）"""
    logline: Optional[str] = None
    characters: Optional[List[CharacterInput]] = None
    relationships: Optional[List[CharacterRelationship]] = None
    themes: Optional[ThemesConfig] = None


class PromptModel(PromptBase):
    """创意输入完整模型"""
    id: str = Field(..., description="创意ID（prompt_id）")
    user_id: str = Field(..., description="用户ID")
    character_ids: List[str] = Field(default_factory=list, description="角色ID列表")
    stories_count: int = Field(0, description="关联的故事数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class PromptListItem(BaseModel):
    """创意列表项"""
    prompt_id: str
    logline: str
    stories_count: int
    created_at: datetime
