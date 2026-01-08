"""
故事版本表 ORM 模型（互动叙事专用）
"""

from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey, Index
from datetime import datetime

from backend.db.base import Base


class StoryVersion(Base):
    """故事版本表（互动叙事专用）"""
    __tablename__ = "story_versions"

    # 主键
    id = Column(String(64), primary_key=True, comment="版本ID")

    # 外键
    story_id = Column(String(64), ForeignKey("stories.id"), nullable=False, comment="所属故事")
    prev_id = Column(String(64), ForeignKey("story_versions.id"), nullable=True, comment="父版本ID")
    pioneer_user_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="开拓者用户ID")

    # 分支信息
    fork_sequence_id = Column(String(128), nullable=True, comment="分叉点的choice事件sequence_id")
    option_id = Column(String(64), nullable=True, comment="在分叉点选择的选项ID")

    # 开拓进度
    current_sequence_id = Column(String(128), nullable=False, comment="当前位置的sequence_id")
    current_event_type = Column(String(50), nullable=False, comment="当前位置的事件类型")

    # 统计
    view_count = Column(Integer, nullable=False, default=0, comment="访问/播放次数")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 索引
    __table_args__ = (
        Index('idx_versions_story', 'story_id'),
        Index('idx_versions_prev', 'prev_id'),
        Index('idx_versions_pioneer', 'pioneer_user_id'),
        Index('idx_versions_fork', 'story_id', 'fork_sequence_id', 'option_id'),
    )
