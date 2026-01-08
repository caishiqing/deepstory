"""
交易流水表 ORM 模型（分区表）
"""

from sqlalchemy import Column, String, Integer, DECIMAL, Text, TIMESTAMP, ForeignKey, Index
from datetime import datetime

from backend.db.base import Base


class WalletTransaction(Base):
    """交易流水表（按月分区）"""
    __tablename__ = "wallet_transactions"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")

    # 外键
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, comment="用户ID")
    story_id = Column(String(64), ForeignKey("stories.id"), nullable=True, comment="关联故事（可选）")

    # 交易信息
    transaction_type = Column(String(20), nullable=False, comment="交易类型")
    amount = Column(DECIMAL(10, 2), nullable=False, comment="交易金额")
    balance_after = Column(DECIMAL(10, 2), nullable=False, comment="交易后余额")
    description = Column(Text, nullable=True, comment="交易描述")

    # 外部订单号
    external_order_id = Column(String(128), nullable=True, comment="外部订单号")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="交易时间")

    # 索引（注意：分区表通过 init_db.py 或 app.py 自动创建）
    __table_args__ = (
        Index('idx_transactions_user', 'user_id', 'created_at', postgresql_ops={'created_at': 'DESC'}),
        Index('idx_transactions_story', 'story_id', 'created_at', postgresql_ops={'created_at': 'DESC'}),
        Index('idx_transactions_type', 'transaction_type', 'created_at'),
        Index('idx_transactions_external', 'external_order_id'),
    )
