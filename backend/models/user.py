"""
用户相关数据模型
"""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from enum import Enum


class UserStatus(str, Enum):
    """用户状态"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class UserSettings(BaseModel):
    """用户设置"""
    text_speed: int = Field(50, description="文字显示速度（字符/秒）")
    afm_enable: bool = Field(True, description="是否启用自动推进")
    afm_time: int = Field(15, description="自动推进延迟（秒）")
    voice_volume: float = Field(1.0, ge=0, le=1, description="配音音量")
    music_volume: float = Field(0.7, ge=0, le=1, description="音乐音量")
    sound_volume: float = Field(1.0, ge=0, le=1, description="音效音量")
    ambient_volume: float = Field(0.7, ge=0, le=1, description="环境音音量")
    choice_timeout: int = Field(30, description="选项超时时间（秒）")


class UserBase(BaseModel):
    """用户基础信息"""
    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")


class UserCreate(UserBase):
    """用户注册请求"""
    password: str = Field(..., min_length=6, description="密码")
    verification_code: Optional[str] = Field(None, description="验证码（手机注册时必填）")


class UserLogin(BaseModel):
    """用户登录请求"""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    verification_code: Optional[str] = None


class UserModel(UserBase):
    """用户完整模型"""
    id: str = Field(..., description="用户ID")
    status: UserStatus = Field(UserStatus.ACTIVE, description="用户状态")
    settings: UserSettings = Field(default_factory=UserSettings, description="用户设置")
    level: int = Field(1, description="用户级别")
    experience: int = Field(0, description="经验值")
    balance: float = Field(0.0, description="灵感值余额")
    total_recharged: float = Field(0.0, description="累计充值")
    total_consumed: float = Field(0.0, description="累计消费")
    create_count: int = Field(0, description="创作故事数量")
    view_count: int = Field(0, description="浏览故事数量")
    like_count: int = Field(0, description="点赞故事数量")
    favorite_count: int = Field(0, description="收藏故事数量")
    share_count: int = Field(0, description="分享故事数量")
    following_count: int = Field(0, description="关注数")
    follower_count: int = Field(0, description="粉丝数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class UserProfile(BaseModel):
    """用户公开资料"""
    user_id: str
    username: str
    level: int
    create_count: int
    follower_count: int
    is_following: Optional[bool] = None


class WalletInfo(BaseModel):
    """钱包信息"""
    balance: float
    level: int
    experience: int
    next_level_exp: int
    total_recharged: float
    total_consumed: float
    can_set_price: bool  # level >= 4
