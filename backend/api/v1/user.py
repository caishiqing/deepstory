"""
用户模块路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ApiResponse, UserCreate, UserLogin, UserSettings
from backend.api.deps import get_current_user, get_db_session
from backend.config.settings import settings
from backend.services.user_service import user_service

router = APIRouter()


@router.post("/register", response_model=ApiResponse)
async def register(
    data: UserCreate,
    session: AsyncSession = Depends(get_db_session)
):
    """
    用户注册

    - **username**: 用户名（3-64字符）
    - **email**: 邮箱（可选，与phone至少填一个）
    - **phone**: 手机号（可选，与email至少填一个）
    - **password**: 密码（至少6字符）
    - **verification_code**: 验证码（使用手机号注册时必填）
    """
    if settings.DATABASE_ENABLED:
        result = await user_service.register(session, data)
    else:
        result = await user_service.register(data)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )
    return result


@router.post("/login", response_model=ApiResponse)
async def login(
    data: UserLogin,
    session: AsyncSession = Depends(get_db_session)
):
    """
    用户登录

    支持三种登录方式：
    1. 邮箱 + 密码
    2. 手机号 + 密码
    3. 手机号 + 验证码
    """
    if settings.DATABASE_ENABLED:
        result = await user_service.login(session, data)
    else:
        result = await user_service.login(data)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error
        )
    return result


@router.get("/settings", response_model=ApiResponse)
async def get_settings(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """获取用户设置"""
    if settings.DATABASE_ENABLED:
        result = await user_service.get_settings(session, current_user["user_id"])
    else:
        result = await user_service.get_settings(current_user["user_id"])

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )
    return result


@router.patch("/settings", response_model=ApiResponse)
async def update_settings(
    user_settings: UserSettings,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    更新用户设置

    可更新的字段：
    - text_speed: 文字显示速度
    - afm_enable: 是否启用自动推进
    - afm_time: 自动推进延迟
    - voice_volume: 配音音量
    - music_volume: 音乐音量
    - sound_volume: 音效音量
    - ambient_volume: 环境音音量
    - choice_timeout: 选项超时时间
    """
    if settings.DATABASE_ENABLED:
        result = await user_service.update_settings(session, current_user["user_id"], user_settings)
    else:
        result = await user_service.update_settings(current_user["user_id"], user_settings)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )
    return result


@router.get("/wallet", response_model=ApiResponse)
async def get_wallet(
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
    - can_set_price: 是否拥有定价权（level >= 4）
    """
    if settings.DATABASE_ENABLED:
        result = await user_service.get_wallet(session, current_user["user_id"])
    else:
        result = await user_service.get_wallet(current_user["user_id"])

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.error
        )
    return result
    return ApiResponse(
        success=True,
        data={
            "user_id": "user_001",
            "token": "mock_token"
        },
        message="Login successful"
    )


@router.get("/settings", response_model=ApiResponse[dict])
async def get_settings(current_user: dict = Depends(get_current_user)):
    """获取用户设置"""
    # TODO: 从数据库获取
    return ApiResponse(
        success=True,
        data={
            "text_speed": 50,
            "afm_enable": True,
            "voice_volume": 1.0
        }
    )
