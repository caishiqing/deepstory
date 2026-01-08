"""
用户表 ORM 模型
"""

from sqlalchemy import Column, String, Integer, DECIMAL, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from datetime import datetime

from backend.db.base import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    # 主键
    id = Column(String(64), primary_key=True, comment="用户ID")

    # 基本信息
    username = Column(String(64), unique=True, nullable=False, comment="用户名")
    email = Column(String(128), unique=True, nullable=False, comment="邮箱")
    phone = Column(String(32), unique=True, nullable=True, comment="手机号")
    password_hash = Column(String(256), nullable=False, comment="密码哈希")

    # 用户设置
    settings = Column(JSONB, nullable=False, default={}, comment="用户设置")

    # 状态
    status = Column(String(20), nullable=False, default="active", comment="用户状态")

    # 统计字段
    create_count = Column(Integer, nullable=False, default=0, comment="创作故事数量")
    view_count = Column(Integer, nullable=False, default=0, comment="浏览故事数量")
    like_count = Column(Integer, nullable=False, default=0, comment="点赞故事数量")
    favorite_count = Column(Integer, nullable=False, default=0, comment="收藏故事数量")
    share_count = Column(Integer, nullable=False, default=0, comment="分享故事数量")
    following_count = Column(Integer, nullable=False, default=0, comment="关注数")
    follower_count = Column(Integer, nullable=False, default=0, comment="粉丝数")

    # 成长体系
    level = Column(Integer, nullable=False, default=1, comment="用户级别")
    experience = Column(Integer, nullable=False, default=0, comment="经验值")
    balance = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment="灵感值余额")
    total_recharged = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment="累计充值")
    total_consumed = Column(DECIMAL(10, 2), nullable=False, default=0.00, comment="累计消费")

    # 全文搜索
    search_vector = Column(TSVECTOR, nullable=True, comment="全文搜索向量")

    # 时间戳
    created_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    deleted_at = Column(TIMESTAMP, nullable=True, comment="注销时间")

    # 索引
    __table_args__ = (
        Index('idx_users_email', 'email'),
        Index('idx_users_username', 'username'),
        Index('idx_users_phone', 'phone'),
        Index('idx_users_status', 'status'),
        Index('idx_users_search', 'search_vector', postgresql_using='gin'),
    )
