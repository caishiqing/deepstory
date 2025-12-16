"""
数据模型定义

使用 Pydantic 定义项目中的数据结构
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from abc import abstractmethod
import asyncio


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
    title: str = Field(..., description="场景标题")
    location: str = Field(..., description="场景地点")
    time: str = Field(..., description="场景时间")
    content: str = Field(..., description="场景内容（XML）")
    characters: List[CharacterInfo] = Field(default_factory=list, description="场景中的角色列表")


class Dialogue(BaseModelWithHelpers):
    character: str = Field(..., description="角色名称")
    text: str = Field(..., description="对话文本")
    image: Optional[str] = Field(default=None, description="对话图片url")
    voice: Optional[str] = Field(default=None, description="对话语音url")


class Narration(BaseModelWithHelpers):
    text: str = Field(..., description="旁白文本")
    voice: Optional[str] = Field(default=None, description="旁白语音url")


class Scene(BaseModelWithHelpers):
    title: str = Field(..., description="场景标题")
    background: Optional[str] = Field(default=None, description="背景图片url")


class StoryEvent(BaseModel):
    event_id: str

    class Config:
        # 允许 asyncio.Future 等非标准类型
        arbitrary_types_allowed = True
        from_attributes = True

    @abstractmethod
    async def acquire(self):
        """获取资源占位符值"""


class DialogueEvent(StoryEvent):
    character: str
    text: str
    image_future: asyncio.Future[str]
    voice_future: asyncio.Future[str]

    async def acquire(self):
        image_url, voice_url = await asyncio.gather(
            self.image_future,
            self.voice_future,
        )
        return Dialogue(character=self.character,
                        text=self.text,
                        image=image_url,
                        voice=voice_url)
