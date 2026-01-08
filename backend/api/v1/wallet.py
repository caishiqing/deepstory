"""
钱包模块路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal

from backend.models import ApiResponse
from backend.api.deps import get_current_user, get_db_session
from backend.config.settings import settings
from backend.services.wallet_service import wallet_service

router = APIRouter()


class RechargeRequest(BaseModel):
    """充值请求"""
    amount: float = Field(..., gt=0, description="充值金额")
    payment_method: str = Field("alipay", description="支付方式")


class TipRequest(BaseModel):
    """打赏请求"""
    amount: float = Field(..., gt=0, description="打赏金额")


@router.get("/wallet", response_model=ApiResponse)
async def get_wallet_info(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取钱包信息

    返回：
    - balance: 灵感值余额
    - level: 用户级别
    - experience: 当前经验值
    - next_level_exp: 升级所需经验值
    - total_recharged: 累计充值
    - total_consumed: 累计消费
    - can_set_price: 是否拥有定价权（level >= 4）
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await wallet_service.get_wallet_info(session, current_user["user_id"])

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result


@router.get("/wallet/transactions", response_model=ApiResponse)
async def get_transactions(
    type: Optional[str] = Query(None, description="交易类型筛选"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    获取交易记录

    - type: 交易类型筛选（recharge/purchase/income/tip_out/tip_in/reward）
    - 支持分页
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await wallet_service.get_transactions(
        session, current_user["user_id"], type, limit, offset
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result


@router.post("/wallet/recharge", response_model=ApiResponse)
async def recharge(
    data: RechargeRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    充值灵感值

    - 返回支付链接
    - 支付成功后异步回调更新余额
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await wallet_service.recharge(
        session, current_user["user_id"], Decimal(str(data.amount)), data.payment_method
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.post("/story/{story_id}/tip", response_model=ApiResponse)
async def tip_story(
    story_id: str,
    data: TipRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    打赏创作者

    - 100% 进入创作者账户
    - 不能打赏自己的故事
    - 需要足够的余额
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await wallet_service.tip_story(
        session, current_user["user_id"], story_id, Decimal(str(data.amount))
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result
