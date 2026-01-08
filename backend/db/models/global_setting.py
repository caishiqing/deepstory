"""
全局配置表 ORM 模型
"""

from sqlalchemy import Column, String, Text, TIMESTAMP
from datetime import datetime

from backend.db.base import Base


class GlobalSetting(Base):
    """全局配置表"""
    __tablename__ = "global_settings"

    # 主键
    key = Column(String(128), primary_key=True, comment="配置键")

    # 配置值
    value = Column(Text, nullable=False, comment="配置值（JSON字符串）")
    description = Column(Text, nullable=True, comment="配置描述")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
