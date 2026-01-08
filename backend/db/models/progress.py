"""
用户进度表 ORM 模型
"""

from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey, Index, UniqueConstraint
from datetime import datetime

from backend.db.base import Base


class UserStoryProgress(Base):
    """用户进度表"""
    __tablename__ = "user_story_progress"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")

    # 外键
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="用户ID")
    story_id = Column(String(64), ForeignKey("stories.id"), nullable=False, comment="故事ID")
    current_version_id = Column(String(64), nullable=True, comment="当前活跃的分支版本ID")

    # 进度信息
    current_sequence_id = Column(String(128), nullable=True, comment="当前事件的sequence_id")
    current_chapter_id = Column(String(64), nullable=True, comment="当前章节ID")
    current_scene_id = Column(String(64), nullable=True, comment="当前场景ID")
    play_time = Column(Integer, nullable=False, default=0, comment="累计播放时长（秒）")

    # 时间戳
    started_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="开始时间")
    last_played_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="最后播放时间")

    # 约束和索引
    __table_args__ = (
        UniqueConstraint('user_id', 'story_id', name='uk_user_story_progress'),
        Index('idx_progress_user', 'user_id'),
        Index('idx_progress_last_played', 'user_id', 'last_played_at', postgresql_ops={'last_played_at': 'DESC'}),
        Index('idx_progress_version', 'current_version_id'),
    )
