"""
数据模型定义

使用 Pydantic 定义项目中的数据结构
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BaseModelWithHelpers(BaseModel):
    """基础模型类，提供通用的序列化/反序列化方法"""

    class Config:
        # 允许从字典创建
        from_attributes = True

    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建实例"""
        return cls.model_validate(data)

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str):
        """从 JSON 字符串创建实例"""
        return cls.model_validate_json(json_str)


# ==================== 故事创意输入模型 ====================

class Character(BaseModelWithHelpers):
    """角色输入数据"""
    name: str = Field(..., description="角色名称")
    gender: str = Field(..., description="性别")
    age: str = Field(..., description="年龄")
    appearance: str = Field(..., description="外貌")
    identity: str = Field(..., description="身份")
    nickname: Optional[str] = Field(None, description="昵称")
    background: Optional[str] = Field(None, description="背景")
    regional: Optional[str] = Field(None, description="地域文化")
    explicit_character: Optional[str] = Field(None, description="显性性格")
    implicit_character: Optional[str] = Field(None, description="隐性性格")
    values: Optional[str] = Field(None, description="价值观")
    motivation: Optional[str] = Field(None, description="目标与动机")
    fear: Optional[str] = Field(None, description="深层恐惧")
    desire: Optional[str] = Field(None, description="深层欲望")
    relationship: Optional[str] = Field(None, description="关系")
    secret: Optional[str] = Field(None, description="秘密与谎言")
    behavior_habit: Optional[str] = Field(None, description="行为习惯")
    decision_style: Optional[str] = Field(None, description="决策风格")
    word_preference: Optional[str] = Field(None, description="用词偏好")
    reaction: Optional[str] = Field(None, description="感官特质")
    inner_conflict: Optional[str] = Field(None, description="内在冲突")
    outer_conflict: Optional[str] = Field(None, description="外在冲突")
    symbol: Optional[str] = Field(None, description="象征意义")
    connection: Optional[str] = Field(None, description="观众共情点")


class Relationship(BaseModelWithHelpers):
    """人物关系数据"""
    subject: str = Field(..., description="关系主体")
    object: str = Field(..., description="关系客体")
    relationship: str = Field(..., description="关系描述")


class StoryTags(BaseModelWithHelpers):
    """故事类型标签"""
    type: Optional[List[str]] = Field(None, description="题材类型")
    kernel: Optional[List[str]] = Field(None, description="核心母题")
    emotion: Optional[List[str]] = Field(None, description="情感基调")
    discussion: Optional[List[str]] = Field(None, description="社会议题")
    structure: Optional[List[str]] = Field(None, description="叙事结构")
    culture: Optional[List[str]] = Field(None, description="地域文化背景")


class StoryInput(BaseModelWithHelpers):
    """故事创意输入 - 统一的数据模型

    用于定义故事创作的原始输入数据，包括一句话梗概、角色列表、人物关系和类型标签。
    这是所有故事创作流程的起点。
    """
    logline: str = Field(..., description="一句话梗概")
    characters: List[Character] = Field(..., description="角色列表")
    relationships: Optional[List[Relationship]] = Field(default=None, description="人物关系列表")
    tags: StoryTags = Field(..., description="故事类型标签")


# ==================== 故事生成输出模型 ====================


class StoryInfo(BaseModelWithHelpers):
    """故事信息"""
    tag: str = "story"
    title: str = Field(..., description="故事标题")
    type: Optional[str] = None


class ChapterInfo(BaseModelWithHelpers):
    tag: str = "sequence"
    idx: int = Field(..., description="章节索引")
    title: str = Field(..., description="章节标题")


class CharacterInfo(BaseModelWithHelpers):
    """角色信息"""
    tag: str = "character"
    name: str = Field(..., description="角色名称")
    age: str = Field(..., description="角色年龄段")


class SceneInfo(BaseModelWithHelpers):
    """场景信息"""
    tag: str = "scene"
    index: str = Field(..., description="场景组合索引（如'01'）")
    scene_id: str = Field(default="", description="场景业务ID（如'laboratory'）")
    title: str = Field(..., description="场景标题")
    location: str = Field(..., description="场景地点")
    time: str = Field(..., description="场景时间")
    content: str = Field(..., description="场景内容（XML）")
    characters: List[CharacterInfo] = Field(default_factory=list, description="场景中的角色列表")
