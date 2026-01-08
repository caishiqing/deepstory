"""
用户行为相关数据模型
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class BehaviorAction(str, Enum):
    """行为类型"""
    CREATE = "create"              # 创建故事
    ENTER = "enter"                # 进入故事
    EXIT = "exit"                  # 退出故事
    COMPLETE = "complete"          # 完成故事
    LIKE = "like"                  # 点赞
    UNLIKE = "unlike"              # 取消点赞
    FAVORITE = "favorite"          # 收藏
    UNFAVORITE = "unfavorite"      # 取消收藏
    SHARE = "share"                # 分享
    CHOICE = "choice"              # 选择分支
    COMMENT = "comment"            # 发表评论
    COMMENT_LIKE = "comment_like"  # 点赞评论
    COMMENT_UNLIKE = "comment_unlike"  # 取消点赞评论
    PURCHASE = "purchase"          # 购买故事
    TIP = "tip"                    # 打赏创作者


class BehaviorLog(BaseModel):
    """行为日志"""
    user_id: str = Field(..., description="用户ID")
    story_id: str = Field(..., description="故事ID")
    action: BehaviorAction = Field(..., description="行为类型")
    metadata: Optional[Dict[str, Any]] = Field(None, description="行为附加信息")


class BehaviorLogCreate(BehaviorLog):
    """创建行为日志请求"""
    pass


class BehaviorLogResponse(BehaviorLog):
    """行为日志响应"""
    id: int = Field(..., description="自增ID")
    created_at: datetime = Field(..., description="行为时间")

    class Config:
        from_attributes = True
