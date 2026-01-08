"""
用户行为日志表 ORM 模型（分区表）
"""

from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from backend.db.base import Base


class UserBehaviorLog(Base):
    """用户行为日志表（按月分区）"""
    __tablename__ = "user_behavior_logs"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")

    # 外键
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="用户ID")
    story_id = Column(String(64), nullable=True, comment="故事ID（可选）")

    # 行为信息
    action = Column(String(50), nullable=False, comment="行为类型")
    metadata = Column(JSONB, nullable=True, comment="行为附加信息")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="行为时间")

    # 索引（注意：分区表通过 init_db.py 或 app.py 自动创建）
    __table_args__ = (
        Index('idx_behavior_user', 'user_id', 'created_at'),
        Index('idx_behavior_story', 'story_id', 'created_at'),
        Index('idx_behavior_action', 'action', 'created_at'),
    )
