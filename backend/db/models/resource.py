"""
资源表 ORM 模型
"""

from sqlalchemy import Column, String, Integer, Float, TIMESTAMP, ForeignKey, Index
from datetime import datetime

from backend.db.base import Base


class Resource(Base):
    """资源表"""
    __tablename__ = "resources"

    # 主键
    id = Column(String(64), primary_key=True, comment="资源ID")

    # 外键
    story_id = Column(String(64), ForeignKey("stories.id"), nullable=False, comment="所属故事")
    character_id = Column(String(64), ForeignKey("characters.id"), nullable=True, comment="关联角色")

    # 资源信息
    type = Column(String(20), nullable=False, comment="资源类型")
    url = Column(String(512), nullable=False, comment="CDN URL")
    format = Column(String(16), nullable=True, comment="文件格式")

    # 元数据
    size_bytes = Column(Integer, nullable=True, comment="文件大小")
    duration = Column(Float, nullable=True, comment="时长（音视频）")
    width = Column(Integer, nullable=True, comment="宽度（图像/视频）")
    height = Column(Integer, nullable=True, comment="高度（图像/视频）")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_resources_story', 'story_id'),
        Index('idx_resources_type', 'type'),
        Index('idx_resources_character', 'character_id'),
    )
