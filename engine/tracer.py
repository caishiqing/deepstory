"""
资源追踪器

统一的异步资源管理工具，基于 asyncio.Future 实现。
支持持久化到 Redis，服务重启后可恢复。

支持两种使用方式：
1. 直接模式：手动设置结果（用于快速资源如音色匹配）
2. 任务模式：提交到 TaskManager 并自动追踪（用于耗时资源如图像、音频）
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from loguru import logger

from cache import get_redis_client

if TYPE_CHECKING:
    from tasks.task_manager import TaskManager


@dataclass
class TrackedResource:
    """被追踪的资源"""
    key: str                                  # 资源唯一标识
    future: asyncio.Future                    # Future 对象
    task_id: Optional[str] = None             # 关联的任务 ID（任务模式）
    queue: Optional[str] = None               # 任务队列名称
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class ResourceTracker:
    """统一资源追踪器（支持持久化）

    基于 asyncio.Future 的资源追踪，支持：
    - 直接设置结果（快速资源）
    - 任务提交并追踪（耗时资源）
    - Redis 持久化（服务重启后可恢复）

    Example (任务模式):
        tracker = ResourceTracker(task_manager, request_id="abc123")
        await tracker.initialize()  # 从 Redis 恢复
        await tracker.start_polling()

        # 提交任务并追踪
        await tracker.submit(
            key="image_alice",
            function="tasks.character_portrait",
            args=["alice", "description..."],
            queue="image_generation"
        )

        # 等待结果
        result = await tracker.get("image_alice")  # ResourceResult
    """

    def __init__(self,
                 task_manager: "TaskManager" = None,
                 request_id: str = "",
                 poll_interval: float = 1.0):
        """
        Args:
            task_manager: 任务管理器（任务模式需要）
            request_id: 请求 ID（用于 Redis key 前缀）
            poll_interval: 轮询间隔（秒）
        """
        self.task_manager = task_manager
        self.request_id = request_id
        self.poll_interval = poll_interval

        # 追踪中的资源: key -> TrackedResource
        self._resources: Dict[str, TrackedResource] = {}

        # 轮询任务
        self._polling_task: Optional[asyncio.Task] = None
        self._polling = False

        # Redis 客户端
        self._redis = None

    def _redis_key(self, suffix: str) -> str:
        """生成 Redis 键"""
        return f"tracker:{self.request_id}:{suffix}"

    async def initialize(self):
        """初始化：连接 Redis 并恢复状态"""
        self._redis = get_redis_client()
        if self._redis:
            await self._recover_from_redis()

    async def _recover_from_redis(self):
        """从 Redis 恢复资源映射"""
        if not self._redis:
            return

        try:
            # 获取所有资源映射
            mapping = await self._redis.hgetall(self._redis_key("resources"))
            if not mapping:
                return

            recovered = 0
            for key, data_str in mapping.items():
                if isinstance(key, bytes):
                    key = key.decode()
                if isinstance(data_str, bytes):
                    data_str = data_str.decode()

                try:
                    data = json.loads(data_str)
                    task_id = data.get("task_id")
                    queue = data.get("queue")

                    # 创建 Future
                    loop = asyncio.get_event_loop()
                    future = loop.create_future()

                    self._resources[key] = TrackedResource(
                        key=key,
                        future=future,
                        task_id=task_id,
                        queue=queue
                    )
                    recovered += 1

                except Exception as e:
                    logger.warning(f"Failed to recover resource {key}: {e}")

            if recovered > 0:
                logger.info(f"Recovered {recovered} resources from Redis")

        except Exception as e:
            logger.error(f"Failed to recover resources from Redis: {e}")

    async def _persist_resource(self, key: str, task_id: str = None, queue: str = None):
        """持久化资源映射到 Redis"""
        if not self._redis:
            return

        try:
            data = {"task_id": task_id, "queue": queue}
            await self._redis.hset(
                self._redis_key("resources"),
                key,
                json.dumps(data)
            )
        except Exception as e:
            logger.warning(f"Failed to persist resource {key}: {e}")

    async def _remove_resource_from_redis(self, key: str):
        """从 Redis 删除资源映射"""
        if not self._redis:
            return

        try:
            await self._redis.hdel(self._redis_key("resources"), key)
        except Exception as e:
            logger.warning(f"Failed to remove resource {key} from Redis: {e}")

    # ==================== 直接模式 ====================

    def register(self, key: str) -> asyncio.Future:
        """注册资源并返回 Future

        Args:
            key: 资源唯一标识

        Returns:
            asyncio.Future: 可等待的 Future
        """
        if key in self._resources:
            return self._resources[key].future

        loop = asyncio.get_event_loop()
        future = loop.create_future()

        self._resources[key] = TrackedResource(key=key, future=future)
        logger.debug(f"Registered resource: {key}")

        return future

    def set_result(self, key: str, result: Any) -> None:
        """设置资源结果

        Args:
            key: 资源唯一标识
            result: 资源结果值
        """
        if key not in self._resources:
            self.register(key)

        resource = self._resources[key]
        if not resource.future.done():
            resource.future.set_result(result)
            logger.debug(f"Resource result set: {key}")

    def set_exception(self, key: str, exception: Exception) -> None:
        """设置资源异常

        Args:
            key: 资源唯一标识
            exception: 异常对象
        """
        if key not in self._resources:
            self.register(key)

        resource = self._resources[key]
        if not resource.future.done():
            resource.future.set_exception(exception)
            logger.debug(f"Resource exception set: {key}")

    # ==================== 任务模式 ====================

    async def submit(self,
                     key: str,
                     function: str,
                     args: List[Any] = None,
                     kwargs: Dict[str, Any] = None,
                     queue: str = "default") -> asyncio.Future:
        """提交任务并追踪

        Args:
            key: 资源唯一标识
            function: 任务函数名
            args: 位置参数
            kwargs: 关键字参数
            queue: 队列名称

        Returns:
            asyncio.Future: 可等待的 Future
        """
        if self.task_manager is None:
            raise RuntimeError("TaskManager not provided, cannot submit task")

        # 检查是否已存在且未完成
        if key in self._resources and not self._resources[key].future.done():
            logger.warning(f"Resource {key} already tracked, returning existing future")
            return self._resources[key].future

        # 提交到持久化队列
        task_id = await self.task_manager.submit_task(
            function=function,
            args=args or [],
            kwargs=kwargs or {},
            queue=queue
        )

        # 创建 Future 和追踪记录
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        self._resources[key] = TrackedResource(
            key=key,
            future=future,
            task_id=task_id,
            queue=queue
        )

        # 持久化到 Redis
        await self._persist_resource(key, task_id, queue)

        logger.debug(f"Submitted and tracking: {key} -> task {task_id}")
        return future

    async def start_polling(self):
        """启动任务状态轮询"""
        if self._polling:
            return

        self._polling = True
        self._polling_task = asyncio.create_task(self._poll_loop())
        logger.info("ResourceTracker polling started")

    async def stop_polling(self):
        """停止轮询"""
        self._polling = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        logger.info("ResourceTracker polling stopped")

    async def _poll_loop(self):
        """后台轮询任务状态"""
        from tasks.models import TaskStatus

        while self._polling:
            try:
                for key, resource in list(self._resources.items()):
                    # 跳过非任务模式或已完成的资源
                    if resource.task_id is None or resource.future.done():
                        continue

                    try:
                        task_info = await self.task_manager.get_task_status(resource.task_id)

                        if task_info is None:
                            logger.warning(f"Task {resource.task_id} not found for {key}")
                            resource.future.set_exception(
                                Exception(f"Task {resource.task_id} not found")
                            )
                            continue

                        if task_info.status == TaskStatus.COMPLETED:
                            resource.future.set_result(task_info.result)
                            logger.debug(f"Resource ready (from task): {key}")

                        elif task_info.status == TaskStatus.FAILED:
                            error_msg = task_info.error or "Task failed"
                            resource.future.set_exception(Exception(error_msg))
                            logger.warning(f"Resource failed: {key} - {error_msg}")

                    except Exception as e:
                        logger.error(f"Error polling task {resource.task_id}: {e}")

                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                await asyncio.sleep(self.poll_interval)

    # ==================== 通用方法 ====================

    async def get(self,
                  key: str,
                  timeout: Optional[float] = None,
                  default: Any = None) -> Any:
        """等待并获取资源结果

        Args:
            key: 资源唯一标识
            timeout: 超时时间（秒）
            default: 超时时返回的默认值

        Returns:
            资源结果值
        """
        if key not in self._resources:
            self.register(key)

        future = self._resources[key].future

        try:
            if timeout is not None:
                return await asyncio.wait_for(future, timeout=timeout)
            return await future
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for resource: {key} (timeout={timeout}s)")
            return default
        except asyncio.CancelledError:
            logger.warning(f"Cancelled waiting for resource: {key}")
            return default
        except Exception as e:
            logger.error(f"Error getting resource {key}: {e}")
            return default

    def get_nowait(self, key: str, default: Any = None) -> Any:
        """非阻塞获取结果

        Args:
            key: 资源唯一标识
            default: 未就绪时返回的默认值

        Returns:
            资源结果值，未就绪则返回 default
        """
        if key not in self._resources:
            return default

        future = self._resources[key].future
        if future.done():
            try:
                return future.result()
            except Exception:
                return default
        return default

    def is_ready(self, key: str) -> bool:
        """检查资源是否已就绪"""
        if key not in self._resources:
            return False
        return self._resources[key].future.done()

    async def clear(self, key: str) -> None:
        """清除指定资源"""
        if key in self._resources:
            del self._resources[key]
            await self._remove_resource_from_redis(key)
            logger.debug(f"Cleared resource: {key}")

    async def clear_completed(self) -> int:
        """清理已完成的资源"""
        completed = [k for k, r in self._resources.items() if r.future.done()]
        for key in completed:
            del self._resources[key]
            await self._remove_resource_from_redis(key)

        if completed:
            logger.debug(f"Cleared {len(completed)} completed resources")
        return len(completed)

    async def clear_all(self) -> None:
        """清除所有资源"""
        count = len(self._resources)
        self._resources.clear()

        # 清除 Redis 中的映射
        if self._redis:
            try:
                await self._redis.delete(self._redis_key("resources"))
            except Exception as e:
                logger.warning(f"Failed to clear resources from Redis: {e}")

        logger.debug(f"Cleared all resources ({count} total)")

    # ==================== 状态属性 ====================

    @property
    def pending_count(self) -> int:
        """待完成的资源数"""
        return sum(1 for r in self._resources.values() if not r.future.done())

    @property
    def total_count(self) -> int:
        """追踪中的资源总数"""
        return len(self._resources)

    @property
    def task_count(self) -> int:
        """任务模式的资源数"""
        return sum(1 for r in self._resources.values() if r.task_id is not None)
