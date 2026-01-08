"""
故事相关数据模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class StoryType(str, Enum):
    """故事类型"""
    LINEAR = "linear"          # 线性叙事
    INTERACTIVE = "interactive"  # 互动叙事


class StoryStatus(str, Enum):
    """故事状态"""
    PENDING = "pending"        # 待生成（think 和 script 未生成）
    GENERATING = "generating"  # 生成中（正在生成详细内容）
    DYNAMIC = "dynamic"        # 动态分支中（仅 interactive 类型）
    COMPLETED = "completed"    # 已完成
    ERROR = "error"           # 生成失败


class PricingType(str, Enum):
    """定价类型"""
    FREE = "free"
    PAID = "paid"


class StoryCreate(BaseModel):
    """创建故事请求"""
    prompt_id: str = Field(..., description="创意ID")
    type: StoryType = Field(StoryType.LINEAR, description="故事类型")


class StoryPricing(BaseModel):
    """故事定价信息"""
    pricing_type: PricingType = Field(..., description="定价类型")
    price: float = Field(0.0, description="价格（灵感值）")
    purchased: bool = Field(False, description="当前用户是否已购买")


class StoryAuthor(BaseModel):
    """故事作者信息"""
    user_id: str
    username: str
    level: int


class CharacterInfo(BaseModel):
    """角色信息（简化版）"""
    character_id: str
    name: str
    name_color: str
    source: str  # user_defined / ai_generated


class StoryModel(BaseModel):
    """故事完整模型"""
    id: str = Field(..., alias="story_id", description="故事ID")
    prompt_id: str = Field(..., description="创意ID")
    user_id: str = Field(..., description="用户ID")
    type: StoryType = Field(..., description="故事类型")
    title: Optional[str] = Field(None, description="故事标题")
    status: StoryStatus = Field(..., description="故事状态")
    visibility: str = Field("private", description="可见性（private/published）")
    pricing_type: PricingType = Field(PricingType.FREE, description="定价类型")
    price: float = Field(0.0, description="价格")
    cover_url: Optional[str] = Field(None, description="封面URL")
    play_count: int = Field(0, description="播放次数")
    like_count: int = Field(0, description="点赞数")
    favorite_count: int = Field(0, description="收藏数")
    share_count: int = Field(0, description="分享数")
    comment_count: int = Field(0, description="评论数")
    created_at: datetime = Field(..., description="创建时间")
    published_at: Optional[datetime] = Field(None, description="发布时间")

    class Config:
        from_attributes = True
        populate_by_name = True


class StoryDetail(StoryModel):
    """故事详情（包含关联信息）"""
    prompt: Optional[Dict[str, Any]] = Field(None, description="创意信息（简化）")
    characters: List[CharacterInfo] = Field(default_factory=list, description="角色列表")
    pricing: StoryPricing = Field(..., description="定价信息")
    author: StoryAuthor = Field(..., description="作者信息")


class StoryListItem(BaseModel):
    """故事列表项"""
    story_id: str
    type: StoryType
    title: Optional[str]
    cover_url: Optional[str]
    status: StoryStatus
    author: StoryAuthor
    play_count: int
    like_count: int
    favorite_count: int
    pricing_type: PricingType
    price: float
    created_at: datetime
    published_at: Optional[datetime] = None


class StoryStatusResponse(BaseModel):
    """故事状态查询响应"""
    story_id: str
    status: StoryStatus
    progress: int = Field(0, description="生成进度 0-100")
    message: str = Field("", description="当前阶段描述")
    retry_after: int = Field(10, description="建议下次轮询间隔（秒）")
