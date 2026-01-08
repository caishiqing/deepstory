"""
评论相关数据模型
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class CommentStatus(str, Enum):
    """评论状态"""
    VISIBLE = "visible"    # 正常显示
    HIDDEN = "hidden"      # 用户删除
    REMOVED = "removed"    # 违规删除


class CommentBase(BaseModel):
    """评论基础模型"""
    story_id: str = Field(..., description="故事ID")
    content: str = Field(..., min_length=1, max_length=500, description="评论内容")
    parent_id: Optional[str] = Field(None, description="父评论ID")


class CommentCreate(CommentBase):
    """创建评论请求"""
    pass


class CommentUser(BaseModel):
    """评论用户信息"""
    user_id: str
    username: str


class CommentReply(BaseModel):
    """评论回复"""
    comment_id: str
    user: CommentUser
    content: str
    like_count: int
    is_liked: bool
    created_at: datetime


class CommentResponse(CommentBase):
    """评论响应"""
    id: str = Field(..., alias="comment_id", description="评论ID")
    user: CommentUser
    like_count: int = Field(0, description="点赞数")
    is_liked: bool = Field(False, description="当前用户是否已点赞")
    reply_count: int = Field(0, description="回复数")
    replies: List[CommentReply] = Field(default_factory=list, description="回复列表（最多3条）")
    status: CommentStatus = Field(CommentStatus.VISIBLE, description="状态")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
