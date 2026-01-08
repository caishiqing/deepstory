"""
用户服务

处理用户注册、登录、设置等业务逻辑
"""

from typing import Optional
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    UserCreate, UserLogin, UserSettings, ApiResponse
)
from backend.utils.auth import verify_password, create_access_token
from backend.db.dao import UserDAO
from backend.config.narrative import narrative_config
from backend.config.settings import settings


class UserService:
    """用户服务"""

    @staticmethod
    async def register(session: AsyncSession, user_data: UserCreate) -> ApiResponse:
        """
        用户注册

        Args:
            session: 数据库会话
            user_data: 用户注册数据

        Returns:
            API响应，包含用户信息和token
        """
        # 检查邮箱是否已存在
        if user_data.email:
            existing_user = await UserDAO.get_by_email(session, user_data.email)
            if existing_user:
                return ApiResponse(
                    success=False,
                    message="Email already registered",
                    error={"code": "EMAIL_EXISTS", "message": "该邮箱已被注册"}
                )

        # 检查用户名是否已存在
        existing_user = await UserDAO.get_by_username(session, user_data.username)
        if existing_user:
            return ApiResponse(
                success=False,
                message="Username already taken",
                error={"code": "USERNAME_EXISTS", "message": "该用户名已被使用"}
            )

        # 获取默认用户设置
        default_settings = {
            "text_speed": 20,
            "afm_enable": True,
            "afm_time": 15,
            "voice_volume": 1.0,
            "music_volume": 0.7,
            "sound_volume": 1.0,
            "ambient_volume": 0.7,
            "choice_timeout": 10,
        }

        # 创建用户
        user = await UserDAO.create(
            session=session,
            username=user_data.username,
            email=user_data.email,
            phone=user_data.phone,
            password=user_data.password,
            settings=default_settings
        )

        # 生成 JWT token
        token = create_access_token(
            data={"sub": user.id, "username": user.username}
        )

        return ApiResponse(
            success=True,
            message="Registration successful",
            data={
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "token": token,
            }
        )

    @staticmethod
    async def login(session: AsyncSession, login_data: UserLogin) -> ApiResponse:
        """
        用户登录

        Args:
            session: 数据库会话
            login_data: 登录数据

        Returns:
            API响应，包含用户信息和token
        """
        # 查找用户
        user = None
        if login_data.email:
            user = await UserDAO.get_by_email(session, login_data.email)

        if not user:
            return ApiResponse(
                success=False,
                message="Invalid credentials",
                error={"code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误"}
            )

        # 验证密码
        if not login_data.password or not verify_password(login_data.password, user.password_hash):
            return ApiResponse(
                success=False,
                message="Invalid credentials",
                error={"code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误"}
            )

        # 生成 JWT token
        token = create_access_token(
            data={"sub": user.id, "username": user.username}
        )

        return ApiResponse(
            success=True,
            message="Login successful",
            data={
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "token": token,
                "settings": user.settings,
            }
        )

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: str) -> Optional[dict]:
        """
        根据ID获取用户

        Args:
            session: 数据库会话
            user_id: 用户ID

        Returns:
            用户数据，不存在返回None
        """
        user = await UserDAO.get_by_id(session, user_id)
        if not user:
            return None

        return {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "settings": user.settings,
            "level": user.level,
            "experience": user.experience,
            "balance": float(user.balance),
        }

    @staticmethod
    async def get_settings(session: AsyncSession, user_id: str) -> ApiResponse:
        """
        获取用户设置

        Args:
            session: 数据库会话
            user_id: 用户ID

        Returns:
            API响应，包含用户设置
        """
        user = await UserDAO.get_by_id(session, user_id)
        if not user:
            return ApiResponse(
                success=False,
                message="User not found",
                error={"code": "USER_NOT_FOUND", "message": "用户不存在"}
            )

        return ApiResponse(
            success=True,
            data=user.settings
        )

    @staticmethod
    async def update_settings(
        session: AsyncSession,
        user_id: str,
        settings: UserSettings
    ) -> ApiResponse:
        """
        更新用户设置

        Args:
            session: 数据库会话
            user_id: 用户ID
            settings: 新的设置

        Returns:
            API响应，包含更新后的设置
        """
        success = await UserDAO.update_settings(
            session, user_id, settings.model_dump(exclude_unset=True)
        )

        if not success:
            return ApiResponse(
                success=False,
                message="User not found",
                error={"code": "USER_NOT_FOUND", "message": "用户不存在"}
            )

        # 获取更新后的用户
        user = await UserDAO.get_by_id(session, user_id)

        return ApiResponse(
            success=True,
            message="Settings updated",
            data=user.settings
        )

    @staticmethod
    async def get_wallet(session: AsyncSession, user_id: str) -> ApiResponse:
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
                "can_set_price": user.level >= 4,
            }
        )


# 全局用户服务实例
user_service = UserService()
