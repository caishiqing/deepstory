"""
数据库 ORM 模型

导出所有 SQLAlchemy 模型类
"""

from backend.db.base import Base

# 导入所有模型（确保 Base 知道所有表）
from .user import User
from .story_prompt import StoryPrompt
from .story import Story
from .story_event import StoryEvent
from .character import Character
from .character_portrait import CharacterPortrait
from .resource import Resource
from .progress import UserStoryProgress
from .story_version import StoryVersion
from .scene import Scene
from .comment import StoryComment
from .follow import UserFollow
from .behavior_log import UserBehaviorLog
from .wallet_transaction import WalletTransaction
from .global_setting import GlobalSetting

__all__ = [
    # Base
    "Base",

    # Models
    "User",
    "StoryPrompt",
    "Story",
    "StoryEvent",
    "Character",
    "CharacterPortrait",
    "Resource",
    "UserStoryProgress",
    "StoryVersion",
    "Scene",
    "StoryComment",
    "UserFollow",
    "UserBehaviorLog",
    "WalletTransaction",
    "GlobalSetting",
]
