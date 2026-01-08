"""
Redis 客户端

提供 Redis 连接和常用操作的封装
"""

import redis.asyncio as aioredis
from typing import Optional
from backend.config.settings import settings


class RedisClient:
    """Redis 异步客户端封装"""

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        """建立 Redis 连接"""
        if self._client is None:
            self._client = await aioredis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                password=settings.REDIS_PASSWORD,
                encoding="utf-8",
                decode_responses=True
            )

    async def close(self):
        """关闭 Redis 连接"""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        """获取 Redis 客户端实例"""
        if self._client is None:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """获取键值"""
        return await self.client.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None):
        """设置键值"""
        await self.client.set(key, value, ex=ex)

    async def delete(self, *keys: str):
        """删除键"""
        await self.client.delete(*keys)

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return bool(await self.client.exists(key))

    async def expire(self, key: str, seconds: int):
        """设置键的过期时间"""
        await self.client.expire(key, seconds)


# 全局 Redis 客户端实例
redis_client = RedisClient()
