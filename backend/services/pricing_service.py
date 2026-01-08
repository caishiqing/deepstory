"""
定价服务

处理故事定价、购买等业务逻辑
"""

from typing import Optional
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse
from backend.db.dao import StoryDAO, UserDAO, WalletDAO, InteractionDAO


class PricingService:
    """定价服务"""

    @staticmethod
    async def set_pricing(
        session: AsyncSession,
        story_id: str,
        user_id: str,
        pricing_type: str,
        price: Optional[Decimal] = None
    ) -> ApiResponse:
        """
        设置故事定价

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID
            pricing_type: 定价类型（free/paid）
            price: 价格（灵感值）

        Returns:
            API响应
        """
        # 获取故事
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 检查权限
        if story.user_id != user_id:
            return ApiResponse(
                success=False,
                message="Permission denied",
                error={"code": "PERMISSION_DENIED", "message": "无权限操作"}
            )

        # 获取用户信息
        user = await UserDAO.get_by_id(session, user_id)
        if not user:
            return ApiResponse(
                success=False,
                message="User not found",
                error={"code": "USER_NOT_FOUND", "message": "用户不存在"}
            )

        # 检查定价权限
        if pricing_type == "paid" and user.level < 4:
            return ApiResponse(
                success=False,
                message="Insufficient level",
                error={
                    "code": "INSUFFICIENT_LEVEL",
                    "message": "需要达到等级 4 才能设置付费定价"
                }
            )

        # 验证价格
        if pricing_type == "paid":
            if price is None or price <= 0:
                return ApiResponse(
                    success=False,
                    message="Invalid price",
                    error={"code": "INVALID_PRICE", "message": "付费故事价格必须大于0"}
                )

            # 如果已有付费用户，价格只能降低不能提高
            if story.pricing_type == "paid" and price > story.price:
                return ApiResponse(
                    success=False,
                    message="Price can only be decreased",
                    error={"code": "PRICE_INCREASE_NOT_ALLOWED", "message": "价格只能降低不能提高"}
                )
        else:
            price = Decimal("0.00")

        # 更新定价
        story.pricing_type = pricing_type
        story.price = price
        await session.flush()

        return ApiResponse(
            success=True,
            message="Pricing updated",
            data={
                "story_id": story_id,
                "pricing_type": pricing_type,
                "price": float(price)
            }
        )

    @staticmethod
    async def purchase_story(
        session: AsyncSession,
        story_id: str,
        user_id: str
    ) -> ApiResponse:
        """
        购买故事

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID

        Returns:
            API响应
        """
        # 获取故事
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 检查是否为免费故事
        if story.pricing_type == "free":
            return ApiResponse(
                success=False,
                message="Story is free",
                error={"code": "INVALID_OPERATION", "message": "该故事是免费的"}
            )

        # 检查是否为作者本人
        if story.user_id == user_id:
            return ApiResponse(
                success=False,
                message="Cannot purchase your own story",
                error={"code": "INVALID_OPERATION", "message": "不能购买自己的故事"}
            )

        # 检查是否已购买
        is_purchased = await InteractionDAO.is_liked(session, user_id, story_id)
        # 实际应该检查 purchase 行为，这里暂时使用 like 代替
        # TODO: 添加专门的购买状态检查方法

        # 检查余额
        if not await WalletDAO.check_sufficient_balance(session, user_id, story.price):
            return ApiResponse(
                success=False,
                message="Insufficient balance",
                error={"code": "INSUFFICIENT_BALANCE", "message": "余额不足"}
            )

        # 扣除用户余额
        await WalletDAO.purchase_story(
            session, user_id, story_id, story.price, story.title or "未命名故事"
        )

        # 计算创作者收入（70% 或 75%）
        author = await UserDAO.get_by_id(session, story.user_id)
        if author:
            revenue_rate = Decimal("0.75") if author.level >= 5 else Decimal("0.70")
            author_income = story.price * revenue_rate

            # 给创作者增加收入
            await WalletDAO.receive_income(
                session, story.user_id, story_id, author_income, story.title or "未命名故事"
            )

            # 更新故事总收入
            story.total_revenue += author_income

            # 给创作者增加经验值（每 50 灵感值 = 10 经验）
            exp_gain = int(author_income / 5)
            author.experience += exp_gain

        # 更新故事播放数（购买即可播放）
        story.play_count += 1

        # 记录购买行为
        await InteractionDAO.log_action(
            session, user_id, story_id, "purchase",
            metadata={"price": float(story.price)}
        )

        await session.flush()

        return ApiResponse(
            success=True,
            message="Purchase successful",
            data={
                "story_id": story_id,
                "price": float(story.price),
                "purchased": True
            }
        )

    @staticmethod
    async def check_purchase_status(
        session: AsyncSession,
        story_id: str,
        user_id: Optional[str] = None
    ) -> ApiResponse:
        """
        检查故事购买状态

        Args:
            session: 数据库会话
            story_id: 故事ID
            user_id: 用户ID（可选）

        Returns:
            API响应，包含购买状态
        """
        # 获取故事
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return ApiResponse(
                success=False,
                message="Story not found",
                error={"code": "STORY_NOT_FOUND", "message": "故事不存在"}
            )

        # 如果是免费故事或作者本人，始终返回已购买
        if story.pricing_type == "free" or (user_id and story.user_id == user_id):
            return ApiResponse(
                success=True,
                data={
                    "purchased": True,
                    "price": float(story.price)
                }
            )

        # 如果未登录，返回未购买
        if not user_id:
            return ApiResponse(
                success=True,
                data={
                    "purchased": False,
                    "price": float(story.price)
                }
            )

        # 检查购买记录
        # TODO: 实现专门的购买状态检查
        # 暂时简化处理
        purchased = False
        purchased_at = None

        return ApiResponse(
            success=True,
            data={
                "purchased": purchased,
                "purchased_at": purchased_at,
                "price": float(story.price)
            }
        )


# 全局定价服务实例
pricing_service = PricingService()
