"""
定价模块路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal

from backend.models import ApiResponse
from backend.api.deps import get_current_user, get_db_session
from backend.config.settings import settings
from backend.services.pricing_service import pricing_service

router = APIRouter()


class PricingUpdate(BaseModel):
    """定价更新请求"""
    pricing_type: str = Field(..., description="定价类型（free/paid）")
    price: Optional[float] = Field(None, ge=0, description="价格（灵感值）")


@router.patch("/story/{story_id}/pricing", response_model=ApiResponse)
async def set_pricing(
    story_id: str,
    data: PricingUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    设置故事定价

    - 需要 level >= 4 才能设置付费定价
    - 只有作者可以修改定价
    - 已有付费用户的故事，价格只能降低不能提高
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    # 验证定价类型
    if data.pricing_type not in ["free", "paid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TYPE", "message": "定价类型只能是 free 或 paid"}
        )

    price = Decimal(str(data.price)) if data.price is not None else None

    result = await pricing_service.set_pricing(
        session, story_id, current_user["user_id"], data.pricing_type, price
    )

    if not result.success:
        error_code = result.error.get("code")
        if error_code == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.error
            )
        elif error_code == "INSUFFICIENT_LEVEL":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.error
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error
            )

    return result


@router.post("/story/{story_id}/purchase", response_model=ApiResponse)
async def purchase_story(
    story_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    购买故事

    - 扣除用户余额
    - 70% 收入进入创作者账户（level 5+ 为 75%）
    - 购买后永久可阅读完整内容
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    result = await pricing_service.purchase_story(
        session, story_id, current_user["user_id"]
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return result


@router.get("/story/{story_id}/purchase", response_model=ApiResponse)
async def check_purchase_status(
    story_id: str,
    current_user: Optional[dict] = None,
    session: AsyncSession = Depends(get_db_session)
):
    """
    检查故事购买状态

    - 用于判断用户是否已购买某付费故事
    - 作者查看自己的故事时 purchased 始终为 true
    - 游客可查看（返回未购买）
    """
    if not settings.DATABASE_ENABLED:
        return ApiResponse(
            success=False,
            message="Database not enabled",
            error={"code": "DATABASE_DISABLED", "message": "数据库未启用"}
        )

    user_id = current_user["user_id"] if current_user else None

    result = await pricing_service.check_purchase_status(
        session, story_id, user_id
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )

    return result
