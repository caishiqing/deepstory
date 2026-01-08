"""
钱包数据访问对象
"""

from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from backend.db.models.wallet_transaction import WalletTransaction
from backend.db.models.user import User


class WalletDAO:
    """钱包 DAO"""

    @staticmethod
    async def create_transaction(
        session: AsyncSession,
        user_id: str,
        transaction_type: str,
        amount: Decimal,
        balance_after: Decimal,
        description: str,
        story_id: Optional[str] = None,
        external_order_id: Optional[str] = None
    ) -> WalletTransaction:
        """
        创建交易记录

        Args:
            session: 数据库会话
            user_id: 用户ID
            transaction_type: 交易类型
            amount: 交易金额（正数为收入，负数为支出）
            balance_after: 交易后余额
            description: 交易描述
            story_id: 关联故事ID
            external_order_id: 外部订单号

        Returns:
            WalletTransaction: 交易记录
        """
        transaction = WalletTransaction(
            user_id=user_id,
            story_id=story_id,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=balance_after,
            description=description,
            external_order_id=external_order_id
        )

        session.add(transaction)
        await session.flush()

        return transaction

    @staticmethod
    async def get_user_balance(session: AsyncSession, user_id: str) -> Decimal:
        """获取用户余额"""
        user = await session.get(User, user_id)
        if not user:
            return Decimal("0.00")
        return user.balance

    @staticmethod
    async def update_balance(
        session: AsyncSession,
        user_id: str,
        amount: Decimal
    ) -> Decimal:
        """
        更新用户余额

        Args:
            session: 数据库会话
            user_id: 用户ID
            amount: 变动金额（正数增加，负数减少）

        Returns:
            更新后的余额
        """
        user = await session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # 更新余额
        user.balance += amount

        # 更新累计充值/消费
        if amount > 0:
            user.total_recharged += amount
        else:
            user.total_consumed += abs(amount)

        await session.flush()

        return user.balance

    @staticmethod
    async def get_transactions(
        session: AsyncSession,
        user_id: str,
        transaction_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[WalletTransaction]:
        """
        获取用户交易记录

        Args:
            session: 数据库会话
            user_id: 用户ID
            transaction_type: 交易类型筛选（可选）
            limit: 每页数量
            offset: 偏移量

        Returns:
            交易记录列表
        """
        query = select(WalletTransaction).where(
            WalletTransaction.user_id == user_id
        )

        if transaction_type:
            query = query.where(WalletTransaction.transaction_type == transaction_type)

        query = query.order_by(WalletTransaction.created_at.desc()).limit(limit).offset(offset)

        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def check_sufficient_balance(
        session: AsyncSession,
        user_id: str,
        required_amount: Decimal
    ) -> bool:
        """检查用户余额是否足够"""
        balance = await WalletDAO.get_user_balance(session, user_id)
        return balance >= required_amount

    @staticmethod
    async def recharge(
        session: AsyncSession,
        user_id: str,
        amount: Decimal,
        external_order_id: str
    ) -> WalletTransaction:
        """
        充值

        Args:
            session: 数据库会话
            user_id: 用户ID
            amount: 充值金额
            external_order_id: 外部订单号

        Returns:
            交易记录
        """
        # 更新余额
        balance_after = await WalletDAO.update_balance(session, user_id, amount)

        # 创建交易记录
        transaction = await WalletDAO.create_transaction(
            session=session,
            user_id=user_id,
            transaction_type="recharge",
            amount=amount,
            balance_after=balance_after,
            description=f"充值灵感值 {amount}",
            external_order_id=external_order_id
        )

        return transaction

    @staticmethod
    async def purchase_story(
        session: AsyncSession,
        user_id: str,
        story_id: str,
        price: Decimal,
        story_title: str
    ) -> WalletTransaction:
        """
        购买故事（扣款）

        Args:
            session: 数据库会话
            user_id: 用户ID
            story_id: 故事ID
            price: 价格
            story_title: 故事标题

        Returns:
            交易记录
        """
        # 检查余额
        if not await WalletDAO.check_sufficient_balance(session, user_id, price):
            raise ValueError("Insufficient balance")

        # 更新余额
        balance_after = await WalletDAO.update_balance(session, user_id, -price)

        # 创建交易记录
        transaction = await WalletDAO.create_transaction(
            session=session,
            user_id=user_id,
            transaction_type="purchase",
            amount=-price,
            balance_after=balance_after,
            description=f"购买故事《{story_title}》",
            story_id=story_id
        )

        return transaction

    @staticmethod
    async def receive_income(
        session: AsyncSession,
        user_id: str,
        story_id: str,
        amount: Decimal,
        story_title: str
    ) -> WalletTransaction:
        """
        接收创作收入

        Args:
            session: 数据库会话
            user_id: 用户ID（创作者）
            story_id: 故事ID
            amount: 收入金额
            story_title: 故事标题

        Returns:
            交易记录
        """
        # 更新余额
        balance_after = await WalletDAO.update_balance(session, user_id, amount)

        # 创建交易记录
        transaction = await WalletDAO.create_transaction(
            session=session,
            user_id=user_id,
            transaction_type="income",
            amount=amount,
            balance_after=balance_after,
            description=f"《{story_title}》被购买",
            story_id=story_id
        )

        return transaction

    @staticmethod
    async def tip_out(
        session: AsyncSession,
        user_id: str,
        story_id: str,
        amount: Decimal,
        story_title: str
    ) -> WalletTransaction:
        """
        打赏支出

        Args:
            session: 数据库会话
            user_id: 用户ID（打赏者）
            story_id: 故事ID
            amount: 打赏金额
            story_title: 故事标题

        Returns:
            交易记录
        """
        # 检查余额
        if not await WalletDAO.check_sufficient_balance(session, user_id, amount):
            raise ValueError("Insufficient balance")

        # 更新余额
        balance_after = await WalletDAO.update_balance(session, user_id, -amount)

        # 创建交易记录
        transaction = await WalletDAO.create_transaction(
            session=session,
            user_id=user_id,
            transaction_type="tip_out",
            amount=-amount,
            balance_after=balance_after,
            description=f"打赏《{story_title}》",
            story_id=story_id
        )

        return transaction

    @staticmethod
    async def tip_in(
        session: AsyncSession,
        user_id: str,
        story_id: str,
        amount: Decimal,
        story_title: str
    ) -> WalletTransaction:
        """
        打赏收入

        Args:
            session: 数据库会话
            user_id: 用户ID（创作者）
            story_id: 故事ID
            amount: 打赏金额
            story_title: 故事标题

        Returns:
            交易记录
        """
        # 更新余额
        balance_after = await WalletDAO.update_balance(session, user_id, amount)

        # 创建交易记录
        transaction = await WalletDAO.create_transaction(
            session=session,
            user_id=user_id,
            transaction_type="tip_in",
            amount=amount,
            balance_after=balance_after,
            description=f"收到《{story_title}》的打赏",
            story_id=story_id
        )

        return transaction
