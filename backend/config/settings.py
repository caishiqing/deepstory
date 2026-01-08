"""
应用全局配置

从 config.yaml 加载配置，支持环境变量覆盖
"""

import yaml
from pathlib import Path
from typing import Optional, List
import os


class Settings:
    """应用全局配置（从 config.yaml 加载）"""

    def __init__(self):
        # 加载 config.yaml
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

    # ==================== 应用基础配置 ====================
    @property
    def APP_NAME(self) -> str:
        return os.getenv("APP_NAME", self._config["app"]["name"])

    @property
    def APP_VERSION(self) -> str:
        return os.getenv("APP_VERSION", self._config["app"]["version"])

    @property
    def API_V1_PREFIX(self) -> str:
        return os.getenv("API_V1_PREFIX", self._config["app"]["api_prefix"])

    @property
    def DEBUG(self) -> bool:
        debug_str = os.getenv("DEBUG", str(self._config["app"]["debug"]))
        return debug_str.lower() in ("true", "1", "yes")

    # ==================== 数据库配置 ====================
    @property
    def DATABASE_ENABLED(self) -> bool:
        enabled_str = os.getenv("DATABASE_ENABLED", str(self._config["database"]["enabled"]))
        return enabled_str.lower() in ("true", "1", "yes")

    @property
    def DATABASE_URL(self) -> Optional[str]:
        if not self.DATABASE_ENABLED:
            return None
        return os.getenv("DATABASE_URL", self._config["database"]["url"])

    @property
    def DATABASE_POOL_SIZE(self) -> int:
        return int(os.getenv("DATABASE_POOL_SIZE", self._config["database"]["pool_size"]))

    @property
    def DATABASE_MAX_OVERFLOW(self) -> int:
        return int(os.getenv("DATABASE_MAX_OVERFLOW", self._config["database"]["max_overflow"]))

    # ==================== Redis 配置 ====================
    @property
    def REDIS_HOST(self) -> str:
        return os.getenv("REDIS_HOST", self._config["redis"]["host"])

    @property
    def REDIS_PORT(self) -> int:
        return int(os.getenv("REDIS_PORT", self._config["redis"]["port"]))

    @property
    def REDIS_DB(self) -> int:
        return int(os.getenv("REDIS_DB", self._config["redis"]["database"]))

    @property
    def REDIS_PASSWORD(self) -> Optional[str]:
        return os.getenv("REDIS_PASSWORD", self._config["redis"]["password"])

    # ==================== JWT 认证配置 ====================
    @property
    def JWT_SECRET_KEY(self) -> str:
        return os.getenv("JWT_SECRET_KEY", self._config["jwt"]["secret_key"])

    @property
    def JWT_ALGORITHM(self) -> str:
        return os.getenv("JWT_ALGORITHM", self._config["jwt"]["algorithm"])

    @property
    def JWT_EXPIRE_MINUTES(self) -> int:
        return int(os.getenv("JWT_EXPIRE_MINUTES", self._config["jwt"]["expire_minutes"]))

    # ==================== CORS 配置 ====================
    @property
    def CORS_ORIGINS(self) -> List[str]:
        env_origins = os.getenv("CORS_ORIGINS")
        if env_origins:
            return [origin.strip() for origin in env_origins.split(",")]
        return self._config["cors"]["origins"]

    # ==================== SSE 配置 ====================
    @property
    def SSE_HEARTBEAT_INTERVAL(self) -> int:
        return int(os.getenv("SSE_HEARTBEAT_INTERVAL", self._config["sse"]["heartbeat_interval"]))

    @property
    def SSE_RETRY_TIMEOUT(self) -> int:
        return int(os.getenv("SSE_RETRY_TIMEOUT", self._config["sse"]["retry_timeout"]))

    # ==================== 业务规则配置 ====================
    @property
    def RATE_LIMIT_PER_MINUTE(self) -> int:
        return int(os.getenv("RATE_LIMIT_PER_MINUTE", self._config["business"]["rate_limit_per_minute"]))

    @property
    def RATE_LIMIT_PER_HOUR(self) -> int:
        return int(os.getenv("RATE_LIMIT_PER_HOUR", self._config["business"]["rate_limit_per_hour"]))

    @property
    def DEFAULT_PAGE_SIZE(self) -> int:
        return int(os.getenv("DEFAULT_PAGE_SIZE", self._config["business"]["default_page_size"]))

    @property
    def MAX_PAGE_SIZE(self) -> int:
        return int(os.getenv("MAX_PAGE_SIZE", self._config["business"]["max_page_size"]))


# 全局配置实例
settings = Settings()
