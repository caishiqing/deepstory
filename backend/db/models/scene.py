"""
场景表 ORM 模型
"""

from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from backend.db.base import Base


class Scene(Base):
    """场景表"""
    __tablename__ = "scenes"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增ID")

    # 外键
    story_id = Column(String(64), ForeignKey("stories.id"), nullable=False, comment="所属故事")
    scene_id = Column(String(64), nullable=False, comment="场景ID（故事内唯一）")

    # 基本信息
    scene_name = Column(String(128), nullable=True, comment="场景名称")

    # 资源关联
    background_resource_id = Column(String(64), ForeignKey("resources.id"), nullable=True, comment="背景资源ID")
    music_resource_id = Column(String(64), ForeignKey("resources.id"), nullable=True, comment="音乐资源ID")
    ambient_resource_id = Column(String(64), ForeignKey("resources.id"), nullable=True, comment="环境音资源ID")

    # 转场配置
    transition_config = Column(JSONB, nullable=True, comment="转场配置")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 约束和索引
    __table_args__ = (
        UniqueConstraint('story_id', 'scene_id', name='uk_story_scene'),
        Index('idx_scenes_story', 'story_id'),
        Index('idx_scenes_scene_id', 'story_id', 'scene_id'),
    )
