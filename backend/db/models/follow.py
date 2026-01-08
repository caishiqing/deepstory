"""
关注关系表 ORM 模型
"""

from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey, Index, UniqueConstraint, CheckConstraint
from datetime import datetime

from backend.db.base import Base


class UserFollow(Base):
    """关注关系表"""
    __tablename__ = "user_follows"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")

    # 外键
    follower_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="关注者（粉丝）")
    following_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="被关注者（创作者）")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="关注时间")

    # 约束和索引
    __table_args__ = (
        UniqueConstraint('follower_id', 'following_id', name='uk_follower_following'),
        CheckConstraint('follower_id != following_id', name='ck_cannot_follow_self'),
        Index('idx_follows_follower', 'follower_id', 'created_at', postgresql_ops={'created_at': 'DESC'}),
        Index('idx_follows_following', 'following_id', 'created_at', postgresql_ops={'created_at': 'DESC'}),
    )
