"""
ID 生成器

提供各种实体的唯一 ID 生成功能
"""

import ulid
from typing import Optional


def generate_ulid() -> str:
    """
    生成 ULID（Universally Unique Lexicographically Sortable Identifier）

    特点：
    - 128-bit 兼容性
    - 按时间排序
    - 规范化的字符串表示（26个字符）
    - 单调递增（相同毫秒内）

    Returns:
        ULID 字符串
    """
    return str(ulid.new())


def generate_user_id() -> str:
    """
    生成用户 ID

    格式：user_<ulid>
    示例：user_01ARZ3NDEKTSV4RRFFQ69G5FAV

    Returns:
        用户 ID
    """
    return f"user_{generate_ulid()}"


def generate_story_id() -> str:
    """
    生成故事 ID

    格式：story_<ulid>
    示例：story_01ARZ3NDEKTSV4RRFFQ69G5FAV

    Returns:
        故事 ID
    """
    return f"story_{generate_ulid()}"


def generate_prompt_id() -> str:
    """
    生成创意 ID

    格式：prompt_<ulid>
    示例：prompt_01ARZ3NDEKTSV4RRFFQ69G5FAV

    Returns:
        创意 ID
    """
    return f"prompt_{generate_ulid()}"


def generate_character_id(name: Optional[str] = None) -> str:
    """
    生成角色 ID

    格式：char_<ulid>
    示例：char_01ARZ3NDEKTSV4RRFFQ69G5FAV

    Args:
        name: 角色名称（可选，用于日志记录）

    Returns:
        角色 ID
    """
    return f"char_{generate_ulid()}"


def generate_version_id() -> str:
    """
    生成故事版本 ID

    格式：v_<ulid>
    示例：v_01ARZ3NDEKTSV4RRFFQ69G5FAV

    Returns:
        版本 ID
    """
    return f"v_{generate_ulid()}"


def generate_comment_id() -> str:
    """
    生成评论 ID

    格式：comment_<ulid>
    示例：comment_01ARZ3NDEKTSV4RRFFQ69G5FAV

    Returns:
        评论 ID
    """
    return f"comment_{generate_ulid()}"


def generate_resource_id() -> str:
    """
    生成资源 ID

    格式：res_<ulid>
    示例：res_01ARZ3NDEKTSV4RRFFQ69G5FAV

    Returns:
        资源 ID
    """
    return f"res_{generate_ulid()}"
