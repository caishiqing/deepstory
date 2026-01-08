"""
钱包服务

处理充值、交易记录等业务逻辑
"""

from typing import Optional
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.db.dao import WalletDAO, UserDAO, StoryDAO, InteractionDAO


class WalletService:
    """钱包服务"""

    @staticmethod
    async def get_wallet_info(
        session: AsyncSession,
        user_id: str
    ) -> ApiResponse:
        """
        获取钱包信息

        Args:
            session: 数据库会话
            user_id: 用户ID

        Returns:
            API响应，包含钱包信息
        """
        user = await UserDAO.get_by_id(session, user_id)
        if not user:
            return ApiResponse(
                success=False,
                message="User not found",
                error={"code": "USER_NOT_FOUND", "message": "用户不存在"}
            )

        # 计算下一级别所需经验值
        next_level_exp_map = {1: 100, 2: 500, 3: 1500, 4: 5000, 5: 10000}
        next_level_exp = next_level_exp_map.get(user.level, 999999)

        return ApiResponse(
            success=True,
            data={
                "balance": float(user.balance),
                "level": user.level,
                "experience": user.experience,
                "next_level_exp": next_level_exp,
                "total_recharged": float(user.total_recharged),
                "total_consumed": float(user.total_consumed),
                "can_set_price": user.level >= 4
            }
        )

    @staticmethod
    async def get_transactions(
        session: AsyncSession,
        user_id: str,
        transaction_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> ApiResponse:
        """
        获取交易记录

        Args:
            session: 数据库会话
            user_id: 用户ID
            transaction_type: 交易类型筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            API响应，包含交易记录
        """
        transactions = await WalletDAO.get_transactions(
            session, user_id, transaction_type, limit, offset
        )

        transaction_list = []
        for tx in transactions:
            transaction_list.append({
                "id": str(tx.id),
                "type": tx.transaction_type,
                "amount": float(tx.amount),
                "balance_after": float(tx.balance_after),
                "description": tx.description,
                "related_id": tx.story_id,
                "created_at": tx.created_at.isoformat()
            })

        return ApiResponse(
            success=True,
            data={
                "transactions": transaction_list,
                "total": len(transaction_list),
                "limit": limit,
                "offset": offset
            }
        )

    @staticmethod
    async def recharge(
        session: AsyncSession,
        user_id: str,
        amount: Decimal,
        payment_method: str = "alipay"
    ) -> ApiResponse:
        """
        充值灵感值

        Args:
            session: 数据库会话
            user_id: 用户ID
            amount: 充值金额
            payment_method: 支付方式

        Returns:
            API响应，包含支付链接
        """
        if amount <= 0:
            return ApiResponse(
                success=False,
                message="Invalid amount",
                error={"code": "INVALID_AMOUNT", "message": "充值金额必须大于0"}
            )

        # 生成外部订单号（实际应该调用支付平台API）
        import uuid
        external_order_id = f"ORDER_{uuid.uuid4().hex[:16].upper()}"

        # 创建充值记录（实际应该在支付回调中创建）
        # 这里简化处理，直接充值
        transaction = await WalletDAO.recharge(
            session, user_id, amount, external_order_id
        )

        # 实际应该返回支付链接
        return ApiResponse(
            success=True,
            message="Recharge initiated",
            data={
                "order_id": external_order_id,
                "amount": float(amount),
                "payment_url": f"https://payment.example.com/pay/{external_order_id}",
                "expires_at": "2025-01-15T10:30:00.000Z"
            }
        )

    @staticmethod
    async def tip_story(
        session: AsyncSession,
        user_id: str,
        story_id: str,
        amount: Decimal
    ) -> ApiResponse:
        """
        打赏故事

        Args:
            session: 数据库会话
            user_id: 用户ID（打赏者）
            story_id: 故事ID
            amount: 打赏金额

        Returns:
            API响应
        """
        if amount <= 0:
            return ApiResponse(
                success=False,
                message="Invalid amount",
                error={"code": "INVALID_AMOUNT", "message": "打赏金额必须大于0"}
            )

        # 检查故事是否存在
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 不能打赏自己的故事
        if story.user_id == user_id:
            return ApiResponse(
                success=False,
                message="Cannot tip your own story",
                error={"code": "INVALID_OPERATION", "message": "不能打赏自己的故事"}
            )

        # 检查余额
        if not await WalletDAO.check_sufficient_balance(session, user_id, amount):
            return ApiResponse(
                success=False,
                message="Insufficient balance",
                error={"code": "INSUFFICIENT_BALANCE", "message": "余额不足"}
            )

        # 打赏支出
        await WalletDAO.tip_out(
            session, user_id, story_id, amount, story.title or "未命名故事"
        )

        # 打赏收入（100% 给创作者）
        await WalletDAO.tip_in(
            session, story.user_id, story_id, amount, story.title or "未命名故事"
        )

        # 记录行为日志
        await InteractionDAO.log_action(
            session, user_id, story_id, "tip",
            metadata={"amount": float(amount)}
        )

        # 给创作者增加经验值
        author = await UserDAO.get_by_id(session, story.user_id)
        if author:
            # 打赏金额每 10 灵感值 = 1 经验值
            exp_gain = int(amount / 10)
            author.experience += exp_gain
            await session.flush()

        return ApiResponse(
            success=True,
            message="Tip sent successfully",
            data={
                "amount": float(amount),
                "recipient": {
                    "user_id": story.user_id,
                    "username": author.username if author else "未知用户"
                }
            }
        )


# 全局钱包服务实例
wallet_service = WalletService()
