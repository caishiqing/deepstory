"""
故事表 ORM 模型
"""

from sqlalchemy import Column, String, Text, Integer, DECIMAL, TIMESTAMP, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from datetime import datetime

from backend.db.base import Base


class Story(Base):
    """故事表"""
    __tablename__ = "stories"

    # 主键
    id = Column(String(64), primary_key=True, comment="故事ID")

    # 外键
    prompt_id = Column(String(64), ForeignKey("story_prompts.id"), nullable=False, comment="关联的创意输入")
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="所属用户")

    # 基本信息
    type = Column(String(20), nullable=False, default="linear", comment="故事类型")
    title = Column(String(256), nullable=True, comment="故事标题")
    cover_url = Column(String(512), nullable=True, comment="封面图片URL")

    # AI生成内容
    think = Column(Text, nullable=True, comment="AI思考规划内容")
    script = Column(Text, nullable=True, comment="AI生成的结构化故事脚本")

    # 状态
    status = Column(String(20), nullable=False, default="pending", comment="生成状态")
    visibility = Column(String(20), nullable=False, default="draft", comment="可见性状态")
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 统计
    play_count = Column(Integer, nullable=False, default=0, comment="播放次数")
    like_count = Column(Integer, nullable=False, default=0, comment="点赞数")
    favorite_count = Column(Integer, nullable=False, default=0, comment="收藏数")
    share_count = Column(Integer, nullable=False, default=0, comment="分享次数")
    comment_count = Column(Integer, nullable=False, default=0, comment="评论数")

    # 定价
    pricing_type = Column(String(20), nullable=False, default="free", comment="定价类型")
    price = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment="价格")
    total_revenue = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment="累计收入")

    # 全文搜索
    search_vector = Column(TSVECTOR, nullable=True, comment="全文搜索向量")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    completed_at = Column(TIMESTAMP, nullable=True, comment="完成时间")
    published_at = Column(TIMESTAMP, nullable=True, comment="发布时间")
    deleted_at = Column(TIMESTAMP, nullable=True, comment="删除/下架时间")

    # 索引
    __table_args__ = (
        Index('idx_stories_prompt_id', 'prompt_id'),
        Index('idx_stories_user_id', 'user_id'),
        Index('idx_stories_type', 'type'),
        Index('idx_stories_status', 'status'),
        Index('idx_stories_visibility', 'visibility'),
        Index('idx_stories_pricing_type', 'pricing_type'),
        Index('idx_stories_created_at', 'created_at', postgresql_ops={'created_at': 'DESC'}),
        Index('idx_stories_user_created', 'user_id', 'created_at', postgresql_ops={'created_at': 'DESC'}),
        Index('idx_stories_published', 'visibility', 'published_at', postgresql_ops={'published_at': 'DESC'}),
        Index('idx_stories_search', 'search_vector', postgresql_using='gin'),
    )
