"""
评论表 ORM 模型
"""

from sqlalchemy import Column, String, Text, Integer, TIMESTAMP, ForeignKey, Index
from datetime import datetime

from backend.db.base import Base


class StoryComment(Base):
    """评论表"""
    __tablename__ = "story_comments"

    # 主键
    id = Column(String(64), primary_key=True, comment="评论ID")

    # 外键
    story_id = Column(String(64), ForeignKey("stories.id"), nullable=False, comment="故事ID")
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="评论用户")
    parent_id = Column(String(64), ForeignKey("story_comments.id"), nullable=True, comment="父评论ID")

    # 评论内容
    content = Column(Text, nullable=False, comment="评论内容（1-500字符）")

    # 统计
    like_count = Column(Integer, nullable=False, default=0, comment="点赞数")

    # 状态
    status = Column(String(20), nullable=False, default="visible", comment="状态")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 索引
    __table_args__ = (
        Index('idx_comments_story', 'story_id', 'status', 'created_at', postgresql_ops={'created_at': 'DESC'}),
        Index('idx_comments_user', 'user_id', 'created_at', postgresql_ops={'created_at': 'DESC'}),
        Index('idx_comments_parent', 'parent_id'),
    )
