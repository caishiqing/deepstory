"""
角色表 ORM 模型
"""

from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from backend.db.base import Base


class Character(Base):
    """角色表"""
    __tablename__ = "characters"

    # 主键
    id = Column(String(64), primary_key=True, comment="角色ID")

    # 外键
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True, comment="所属用户（平台角色为NULL）")
    story_id = Column(String(64), ForeignKey("stories.id"), nullable=True, comment="所属故事（平台角色为NULL）")

    # 基本信息
    source = Column(String(20), nullable=False, comment="来源")
    name = Column(String(64), nullable=False, comment="角色名")
    gender = Column(String(10), nullable=False, comment="性别")
    name_color = Column(String(10), nullable=True, comment="名字颜色")
    voice_id = Column(String(64), nullable=True, comment="TTS音色ID")

    # 详细信息
    details = Column(JSONB, nullable=True, comment="角色详细信息")

    # 默认位置
    default_position = Column(String(16), nullable=False, default="center", comment="默认位置")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")

    # 约束：平台角色必须 user_id 和 story_id 都为 NULL
    __table_args__ = (
        CheckConstraint(
            "(source = 'DEFAULT' AND user_id IS NULL AND story_id IS NULL) OR (source != 'DEFAULT')",
            name="ck_character_source"
        ),
        Index('idx_characters_user_id', 'user_id'),
        Index('idx_characters_story', 'story_id'),
        Index('idx_characters_source', 'source'),
        Index('idx_characters_gender', 'gender'),
    )
