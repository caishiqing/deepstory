"""
角色立绘表 ORM 模型
"""

from sqlalchemy import Column, String, Boolean, TIMESTAMP, ForeignKey, Index
from datetime import datetime

from backend.db.base import Base


class CharacterPortrait(Base):
    """角色立绘表"""
    __tablename__ = "character_portraits"

    # 主键
    id = Column(String(64), primary_key=True, comment="立绘ID")

    # 外键
    character_id = Column(String(64), ForeignKey("characters.id"), nullable=False, comment="所属角色")
    resource_id = Column(String(64), ForeignKey("resources.id"), nullable=False, comment="关联资源")

    # 立绘信息
    age = Column(String(20), nullable=False, comment="年龄段")
    tag = Column(String(128), nullable=False, comment="属性标签")
    is_default = Column(Boolean, nullable=False, default=False, comment="是否为默认立绘")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_portraits_character', 'character_id'),
        Index('idx_portraits_age', 'character_id', 'age'),
        Index('idx_portraits_default', 'character_id', 'is_default'),
    )
