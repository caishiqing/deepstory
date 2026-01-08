"""
用户数据访问对象
"""

from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.user import User
from backend.utils.id_generator import generate_user_id
from backend.utils.auth import get_password_hash


class UserDAO:
    """用户 DAO"""

    @staticmethod
    async def create(
        session: AsyncSession,
        username: str,
        email: Optional[str],
        phone: Optional[str],
        password: str,
        settings: dict
    ) -> User:
        """
        创建用户

        Args:
            session: 数据库会话
            username: 用户名
            email: 邮箱
            phone: 手机号
            password: 密码
            settings: 用户设置

        Returns:
            User: 新创建的用户对象
        """
        user = User(
            id=generate_user_id(),
            username=username,
            email=email,
            phone=phone,
            password_hash=get_password_hash(password),
            settings=settings,
            status="active",
            level=1,
            experience=0,
            balance=0.0,
        )

        session.add(user)
        await session.flush()

        return user

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
        """根据ID获取用户"""
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(session: AsyncSession, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        result = await session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_settings(session: AsyncSession, user_id: str, settings: dict) -> bool:
        """更新用户设置"""
        user = await UserDAO.get_by_id(session, user_id)
        if not user:
            return False

        # 合并设置
        user.settings = {**user.settings, **settings}
        await session.flush()

        return True

    @staticmethod
    async def update_balance(
        session: AsyncSession,
        user_id: str,
        amount: float,
        balance_after: float
    ) -> bool:
        """
        更新用户余额

        Args:
            session: 数据库会话
            user_id: 用户ID
            amount: 变动金额（正数为增加，负数为减少）
            balance_after: 变动后的余额

        Returns:
            是否更新成功
        """
        user = await UserDAO.get_by_id(session, user_id)
        if not user:
            return False

        user.balance = balance_after

        # 更新累计充值/消费
        if amount > 0:
            user.total_recharged += amount
        else:
            user.total_consumed += abs(amount)

        await session.flush()
        return True

    @staticmethod
    async def search_users(
        session: AsyncSession,
        keyword: str,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[User], int]:
        """
        全文搜索用户
        
        Args:
            session: 数据库会话
            keyword: 搜索关键词
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            (用户列表, 总数)
        """
        # 使用 pg_jieba 全文搜索或模糊搜索
        # 只搜索状态正常的用户
        query = select(User).where(
            User.status == "active",
            User.username.ilike(f"%{keyword}%")
        ).order_by(User.created_at.desc())
        
        # 获取总数
        count_query = select(func.count()).select_from(User).where(
            User.status == "active",
            User.username.ilike(f"%{keyword}%")
        )
        
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页查询
        result = await session.execute(query.limit(limit).offset(offset))
        users = list(result.scalars().all())
        
        return users, total
