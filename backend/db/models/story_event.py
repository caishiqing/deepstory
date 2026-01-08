"""
故事事件表 ORM 模型
"""

from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from backend.db.base import Base


class StoryEvent(Base):
    """故事事件表"""
    __tablename__ = "story_events"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")

    # 外键
    story_id = Column(String(64), ForeignKey("stories.id"), nullable=False, comment="所属故事")

    # 序列信息
    sequence_id = Column(String(128), unique=True, nullable=False, comment="全局唯一序列ID")
    next_sequence_id = Column(String(128), nullable=True, comment="下一个事件的序列ID")

    # 事件信息
    event_category = Column(String(20), nullable=False, comment="事件类别")
    event_type = Column(String(50), nullable=False, comment="具体事件类型")
    content = Column(JSONB, nullable=False, comment="事件内容")

    # 关联信息
    chapter_id = Column(String(64), nullable=True, comment="所属章节ID")
    scene_id = Column(String(64), nullable=True, comment="所属场景ID")

    # 时间戳
    timestamp = Column(String(30), nullable=False, comment="事件时间戳")
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_story_events_sequence', 'sequence_id'),
        Index('idx_story_events_story', 'story_id', 'event_type'),
        Index('idx_story_events_chapter', 'story_id', 'chapter_id'),
        Index('idx_story_events_scene', 'story_id', 'scene_id'),
    )
