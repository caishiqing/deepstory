"""
数据访问对象（DAO）层

封装数据库操作，提供给服务层使用
"""

from .user_dao import UserDAO
from .story_dao import StoryDAO
from .prompt_dao import PromptDAO
from .progress_dao import ProgressDAO
from .comment_dao import CommentDAO
from .follow_dao import FollowDAO
from .interaction_dao import InteractionDAO
from .wallet_dao import WalletDAO

__all__ = [
    "UserDAO",
    "StoryDAO",
    "PromptDAO",
    "ProgressDAO",
    "CommentDAO",
    "FollowDAO",
    "InteractionDAO",
    "WalletDAO",
]
