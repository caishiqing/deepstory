"""
数据模型模块

导出所有 Pydantic 数据模型，用于 API 请求/响应验证
"""

# 通用响应
from .response import ApiResponse, PaginationMeta

# 用户模块
from .user import UserModel, UserSettings, UserCreate, UserLogin, UserProfile

# 创意模块
from .prompt import PromptModel, PromptCreate, PromptUpdate, CharacterInput

# 故事模块
from .story import StoryModel, StoryCreate, StoryStatus, StoryType

# 角色模块
from .character import CharacterModel, CharacterCreate, CharacterSource

# 资源模块
from .resource import ResourceModel, ResourceType

# 事件模块（新增）
from .event import StoryEventBase, StoryEventCreate, StoryEventResponse

# 进度模块（新增）
from .progress import UserStoryProgressBase, ProgressSave, ProgressResponse

# 版本模块（新增）
from .version import StoryVersionBase, StoryVersionCreate, StoryVersionResponse

# 场景模块（新增）
from .scene import SceneBase, SceneCreate, SceneUpdate, SceneResponse

# 评论模块（新增）
from .comment import (
    CommentStatus, CommentBase, CommentCreate,
    CommentUser, CommentReply, CommentResponse
)

# 行为模块（新增）
from .behavior import (
    BehaviorAction, BehaviorLog,
    BehaviorLogCreate, BehaviorLogResponse
)

__all__ = [
    # Response
    "ApiResponse",
    "PaginationMeta",

    # User
    "UserModel",
    "UserSettings",
    "UserCreate",
    "UserLogin",
    "UserProfile",

    # Prompt
    "PromptModel",
    "PromptCreate",
    "PromptUpdate",
    "CharacterInput",

    # Story
    "StoryModel",
    "StoryCreate",
    "StoryStatus",
    "StoryType",

    # Character
    "CharacterModel",
    "CharacterCreate",
    "CharacterSource",

    # Resource
    "ResourceModel",
    "ResourceType",

    # Event (新增)
    "StoryEventBase",
    "StoryEventCreate",
    "StoryEventResponse",

    # Progress (新增)
    "UserStoryProgressBase",
    "ProgressSave",
    "ProgressResponse",

    # Version (新增)
    "StoryVersionBase",
    "StoryVersionCreate",
    "StoryVersionResponse",

    # Scene (新增)
    "SceneBase",
    "SceneCreate",
    "SceneUpdate",
    "SceneResponse",

    # Comment (新增)
    "CommentStatus",
    "CommentBase",
    "CommentCreate",
    "CommentUser",
    "CommentReply",
    "CommentResponse",

    # Behavior (新增)
    "BehaviorAction",
    "BehaviorLog",
    "BehaviorLogCreate",
    "BehaviorLogResponse",
]
