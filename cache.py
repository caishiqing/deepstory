"""
Redis 缓存管理模块

提供 Redis 连接管理和缓存功能
"""

import asyncio
import functools
import hashlib
import json
from typing import Any, Callable, Optional, Dict
import redis.asyncio as redis_async
import redis
import yaml
from loguru import logger


# ==================== Redis 连接管理 ====================

# 异步 Redis 客户端（用于 task_manager 等）
_redis_client_async: Optional[redis_async.Redis] = None
# 同步 Redis 客户端（用于 Cache 类）
_redis_client_sync: Optional[redis.Redis] = None
_redis_config: Optional[Dict[str, Any]] = None


async def init_redis(config_path: str = "config.yaml") -> redis_async.Redis:
    """
    初始化异步 Redis 连接（单例模式）
    用于 task_manager 等需要异步的场景

    Args:
        config_path: 配置文件路径

    Returns:
        异步 Redis 客户端实例
    """
    global _redis_client_async, _redis_config

    if _redis_client_async is not None:
        return _redis_client_async

    # 加载配置
    if _redis_config is None:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                _redis_config = config.get('redis', {})
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise

    # 创建异步 Redis 客户端
    _redis_client_async = redis_async.Redis(
        host=_redis_config.get('host', 'localhost'),
        port=_redis_config.get('port', 6379),
        db=_redis_config.get('database', 0),
        password=_redis_config.get('password'),
        max_connections=_redis_config.get('max_connections', 20),
        decode_responses=True
    )

    # 测试连接
    try:
        await _redis_client_async.ping()
        logger.info("Async Redis connection established")
    except Exception as e:
        logger.error(f"Async Redis connection failed: {e}")
        _redis_client_async = None
        raise

    return _redis_client_async


def init_redis_sync(config_path: str = "config.yaml") -> redis.Redis:
    """
    初始化同步 Redis 连接（单例模式）
    用于 Cache 类等同步场景

    Args:
        config_path: 配置文件路径

    Returns:
        同步 Redis 客户端实例
    """
    global _redis_client_sync, _redis_config

    if _redis_client_sync is not None:
        return _redis_client_sync

    # 加载配置
    if _redis_config is None:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                _redis_config = config.get('redis', {})
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise

    # 创建同步 Redis 客户端
    _redis_client_sync = redis.Redis(
        host=_redis_config.get('host', 'localhost'),
        port=_redis_config.get('port', 6379),
        db=_redis_config.get('database', 0),
        password=_redis_config.get('password'),
        max_connections=_redis_config.get('max_connections', 20),
        decode_responses=True
    )

    # 测试连接
    try:
        _redis_client_sync.ping()
        logger.info("Sync Redis connection established")
    except Exception as e:
        logger.error(f"Sync Redis connection failed: {e}")
        _redis_client_sync = None
        raise

    return _redis_client_sync


def get_redis_client() -> Optional[redis_async.Redis]:
    """
    获取异步 Redis 客户端实例

    Returns:
        异步 Redis 客户端实例，如果未初始化则返回 None
    """
    return _redis_client_async


def get_redis_client_sync() -> Optional[redis.Redis]:
    """
    获取同步 Redis 客户端实例

    Returns:
        同步 Redis 客户端实例，如果未初始化则返回 None
    """
    return _redis_client_sync


async def close_redis():
    """关闭 Redis 连接"""
    global _redis_client_async, _redis_client_sync

    if _redis_client_async is not None:
        await _redis_client_async.close()
        logger.info("Async Redis connection closed")
        _redis_client_async = None

    if _redis_client_sync is not None:
        _redis_client_sync.close()
        logger.info("Sync Redis connection closed")
        _redis_client_sync = None


# ==================== Redis 键名生成器 ====================

class RedisKeys:
    """统一的Redis键名生成器"""

    @staticmethod
    def task_info(task_id: str) -> str:
        """任务信息键"""
        return f"tasks:info:{task_id}"

    @staticmethod
    def queue(queue_name: str) -> str:
        """队列键"""
        return f"queue:{queue_name}"

    @staticmethod
    def running_tasks(queue_name: str) -> str:
        """运行中任务集合键"""
        return f"tasks:running:{queue_name}"

    @staticmethod
    def cache(key_prefix: str, func_name: str, params_hash: str) -> str:
        """缓存键"""
        return f"{key_prefix}:{func_name}:{params_hash}"


# ==================== 缓存类 ====================

class Cache:
    """简洁的同步 Redis 缓存接口"""

    def __init__(self,
                 redis_client: Optional[redis.Redis] = None,
                 config_path: str = "config.yaml"):
        """
        初始化缓存实例

        Args:
            redis_client: Redis 客户端实例，如果为 None 则自动从配置加载
            config_path: 配置文件路径
        """
        if redis_client is None:
            # 尝试获取已初始化的同步客户端
            redis_client = get_redis_client_sync()
            # 如果还没初始化，则自动初始化
            if redis_client is None:
                redis_client = init_redis_sync(config_path)

        self.redis = redis_client

    @staticmethod
    def _serialize(value: Any) -> str:
        """序列化：字符串直接返回，其他类型必须 JSON 可序列化"""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值（自动序列化）
            ttl: 过期时间（秒），None 表示永不过期
        """
        if self.redis is None:
            return

        serialized = self._serialize(value)
        if ttl:
            self.redis.setex(key, ttl, serialized)
        else:
            self.redis.set(key, serialized)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存

        Args:
            key: 缓存键
            default: 默认值（缓存不存在时返回）

        Returns:
            缓存值（自动反序列化）
        """
        if self.redis is None:
            return default

        value = self.redis.get(key)
        if value is None:
            return default

        # 自动反序列化：尝试 JSON，失败则返回原值
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value

    def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否删除成功（True 表示删除了至少一个键）
        """
        if self.redis is None:
            return False

        result = self.redis.delete(key)
        return result > 0

    def exists(self, key: str) -> bool:
        """
        检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            缓存是否存在
        """
        if self.redis is None:
            return False

        result = self.redis.exists(key)
        return result > 0

    def expire(self, key: str, ttl: int) -> bool:
        """
        设置/更新缓存过期时间

        Args:
            key: 缓存键
            ttl: 过期时间（秒）

        Returns:
            是否设置成功
        """
        if self.redis is None:
            return False

        return self.redis.expire(key, ttl)

    def get_or_set(self, key: str, default_factory: Callable, ttl: Optional[int] = None) -> Any:
        """
        获取缓存，如果不存在则调用 default_factory 生成并缓存

        Args:
            key: 缓存键
            default_factory: 生成默认值的可调用对象（同步函数）
            ttl: 过期时间（秒），None 表示永不过期

        Returns:
            缓存值或生成的值
        """
        # 先尝试获取
        value = self.get(key)

        if value is not None:
            return value

        # 缓存不存在，调用 default_factory 生成
        value = default_factory()

        # 设置缓存
        self.set(key, value, ttl)

        return value

    def push(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        推入队列（FIFO）

        Args:
            key: 队列键
            value: 要推入的值（自动序列化）
            ttl: 过期时间（秒），每次推入都会重置过期时间
        """
        if self.redis is None:
            return

        serialized = self._serialize(value)
        self.redis.rpush(key, serialized)

        # 重置过期时间
        if ttl:
            self.redis.expire(key, ttl)

    def pop(self, key: str, default: Any = None) -> Any:
        """
        从队列弹出元素（FIFO）

        Args:
            key: 队列键
            default: 队列为空时返回的默认值

        Returns:
            弹出的元素（自动反序列化），队列为空则返回 default
        """
        if self.redis is None:
            return default

        value = self.redis.lpop(key)
        if value is None:
            return default

        # 自动反序列化
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value

    def queue_len(self, key: str) -> int:
        """
        获取队列长度

        Args:
            key: 队列键

        Returns:
            队列中元素的数量
        """
        if self.redis is None:
            return 0
        return self.redis.llen(key)

    def queue_peek(self, key: str, default: Any = None) -> Any:
        """
        查看队列头部元素（不弹出）

        Args:
            key: 队列键
            default: 队列为空时返回的默认值

        Returns:
            队列头部元素（自动反序列化），队列为空则返回 default
        """
        if self.redis is None:
            return default

        value = self.redis.lindex(key, 0)
        if value is None:
            return default

        # 自动反序列化
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value


# ==================== 缓存装饰器 ====================

def redis_cache(ttl: int = 3600, key_prefix: str = "cache"):
    """
    Redis 缓存装饰器

    Args:
        ttl: 缓存过期时间(秒)，默认 3600 秒(1小时)
        key_prefix: 缓存键前缀，默认 "cache"

    Usage:
        @redis_cache(ttl=3600, key_prefix="voice")
        async def search_voice(query: str, gender: str = None):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取 Redis 客户端
            redis_client = get_redis_client()

            # 如果 Redis 未初始化，直接执行函数（不使用缓存）
            if redis_client is None:
                logger.debug(f"Redis not available, executing {func.__name__} without cache")
                return await func(*args, **kwargs)

            # 生成缓存键
            # 将参数转换为可哈希的字符串
            cache_params = {
                "args": args,
                "kwargs": {k: v for k, v in kwargs.items() if v is not None}  # 只包含非None参数
            }
            params_str = json.dumps(cache_params, sort_keys=True, ensure_ascii=False)
            params_hash = hashlib.md5(params_str.encode()).hexdigest()
            cache_key = RedisKeys.cache(key_prefix, func.__name__, params_hash)

            try:
                # 尝试从缓存获取
                cached_value = await redis_client.get(cache_key)
                if cached_value:
                    logger.info(f"Cache hit: {func.__name__} (key: {cache_key[:50]}...)")
                    return json.loads(cached_value)
            except Exception as e:
                logger.warning(f"Failed to get cache for {func.__name__}: {e}")

            # 缓存未命中，执行函数
            logger.debug(f"Cache miss: {func.__name__}, executing function")
            result = await func(*args, **kwargs)

            try:
                # 存入缓存
                if result is not None:  # 只缓存非 None 结果
                    cached_data = json.dumps(result, ensure_ascii=False)
                    await redis_client.setex(cache_key, ttl, cached_data)
                    logger.debug(f"Cached result for {func.__name__} (TTL: {ttl}s)")
            except Exception as e:
                logger.warning(f"Failed to set cache for {func.__name__}: {e}")

            return result

        return wrapper
    return decorator


# ==================== 缓存管理工具 ====================

async def clear_cache_by_prefix(prefix: str) -> int:
    """
    清除指定前缀的所有缓存

    Args:
        prefix: 缓存键前缀

    Returns:
        清除的缓存数量
    """
    redis_client = get_redis_client()

    if redis_client is None:
        logger.warning("Redis not available, cannot clear cache")
        return 0

    try:
        # 使用 SCAN 命令查找所有匹配的键
        keys = []
        cursor = 0
        while True:
            cursor, batch_keys = await redis_client.scan(
                cursor=cursor,
                match=f"{prefix}:*",
                count=1000
            )
            keys.extend(batch_keys)
            if cursor == 0:
                break

        # 删除找到的键
        if keys:
            deleted = await redis_client.delete(*keys)
            logger.info(f"Cleared {deleted} cache entries with prefix '{prefix}'")
            return deleted
        else:
            logger.info(f"No cache entries found with prefix '{prefix}'")
            return 0

    except Exception as e:
        logger.error(f"Failed to clear cache with prefix '{prefix}': {e}")
        return 0


async def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息

    Returns:
        缓存统计信息字典
    """
    redis_client = get_redis_client()

    if redis_client is None:
        return {"status": "unavailable"}

    try:
        info = await redis_client.info()
        return {
            "status": "connected",
            "used_memory": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_keys": await redis_client.dbsize(),
            "uptime_days": info.get("uptime_in_days", 0)
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {"status": "error", "error": str(e)}
