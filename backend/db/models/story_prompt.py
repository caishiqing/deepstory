"""
创意输入表 ORM 模型
"""

from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from backend.db.base import Base


class StoryPrompt(Base):
    """创意输入表"""
    __tablename__ = "story_prompts"

    # 主键
    id = Column(String(64), primary_key=True, comment="创意ID")

    # 外键
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="所属用户")

    # 创意内容
    logline = Column(Text, nullable=False, comment="一句话梗概")
    characters = Column(JSONB, nullable=False, comment="角色ID列表")
    character_inputs = Column(JSONB, nullable=False, comment="用户输入的角色原始信息")
    relationships = Column(JSONB, nullable=True, comment="角色关系列表")
    themes = Column(JSONB, nullable=False, comment="主题配置")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 索引
    __table_args__ = (
        Index('idx_prompts_user_id', 'user_id'),
        Index('idx_prompts_created_at', 'created_at', postgresql_ops={'created_at': 'DESC'}),
    )
