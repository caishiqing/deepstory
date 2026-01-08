"""
基于 Redis 和 Semaphore 的异步任务管理模块

功能特性：
1. 任务信息持久化，支持服务重启恢复
2. 队列级分组并发控制
3. 简单的 submit_task 接口
4. 自动重试机制
5. 任务状态跟踪
"""

import asyncio
import json
import time
import uuid
import traceback
import importlib
import os
from typing import Dict, Any, Optional, Callable, List, Union
import redis.asyncio as redis
import yaml
from loguru import logger

from .models import TaskStatus, TaskInfo
from cache import init_redis, get_redis_client, close_redis, RedisKeys


class QueueManager:
    """队列级并发控制管理器"""

    def __init__(self, queue_config: Dict[str, Any]):
        self.name = queue_config['name']
        self.max_jobs = queue_config['max_jobs']
        self.job_timeout = queue_config['job_timeout']
        self.keep_result = queue_config['keep_result']
        self.max_tries = queue_config['max_tries']
        self.retry_delay = queue_config['retry_delay']

        # 核心：使用 Semaphore 控制并发数
        self.semaphore = asyncio.Semaphore(self.max_jobs)
        self.active_tasks = set()

    @property
    def current_running_count(self) -> int:
        """当前运行中的任务数"""
        return self.max_jobs - self.semaphore._value


class TaskManager:
    """异步任务管理器主类"""

    def __init__(self, config_path: str = None):
        config_path = config_path or "config.yaml"
        self.config = self._load_config(config_path)
        self.redis_client: Optional[redis.Redis] = None
        self.queue_managers: Dict[str, QueueManager] = {}
        self.running = False
        self.workers: List[asyncio.Task] = []

        # 初始化队列管理器
        self._init_queue_managers()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise

    def _init_queue_managers(self):
        """初始化队列管理器"""
        for queue_name, queue_config in self.config['queues'].items():
            self.queue_managers[queue_name] = QueueManager(queue_config)
            logger.info(f"Initialized queue manager: {queue_name} (max_jobs: {queue_config['max_jobs']})")

    async def initialize(self):
        """初始化 Redis 连接和恢复任务"""
        await self._connect_redis()
        await self._recover_tasks()
        logger.info("TaskManager initialized successfully")

    async def _connect_redis(self):
        """建立 Redis 连接（使用共享的 Redis 客户端）"""
        # 使用共享的 Redis 连接
        self.redis_client = await init_redis()
        logger.debug("TaskManager using shared Redis client")

    async def _recover_tasks(self):
        """从 Redis 恢复未完成的任务"""
        logger.info("Recovering unfinished tasks...")

        recovered_count = 0
        for queue_name in self.queue_managers.keys():
            # 获取运行中的任务（进程重启前）
            running_tasks = await self.redis_client.smembers(RedisKeys.running_tasks(queue_name))

            for task_id in running_tasks:
                try:
                    task_key = RedisKeys.task_info(task_id)
                    task_data = await self.redis_client.get(task_key)
                    if task_data:
                        task_info = TaskInfo.model_validate_json(task_data)

                        # 重置为待处理状态
                        task_info.status = TaskStatus.PENDING
                        task_info.started_at = None

                        # 更新状态并重新加入队列
                        await self._update_task_info(task_info)
                        await self.redis_client.lpush(RedisKeys.queue(queue_name), task_id)
                        await self.redis_client.srem(RedisKeys.running_tasks(queue_name), task_id)

                        recovered_count += 1
                        logger.debug(f"Recovered task {task_id} in queue {queue_name}")

                except Exception as e:
                    logger.error(f"Failed to recover task {task_id}: {e}")

        logger.info(f"Task recovery completed: {recovered_count} tasks recovered")

    async def submit_task(self,
                          function: str,
                          args: List[Any] = None,
                          kwargs: Dict[str, Any] = None,
                          queue: str = "default") -> str:
        """
        提交任务到指定队列

        Args:
            function: 函数名（支持模块.函数名格式）
            args: 位置参数列表
            kwargs: 关键字参数字典
            queue: 队列名称

        Returns:
            任务ID
        """
        if queue not in self.queue_managers:
            raise ValueError(f"Unknown queue: {queue}. Available: {list(self.queue_managers.keys())}")

        args = args or []
        kwargs = kwargs or {}

        # 创建任务信息
        task_id = str(uuid.uuid4())
        queue_config = self.config['queues'][queue]

        task_info = TaskInfo(
            task_id=task_id,
            queue_name=queue,
            function_name=function,
            args=args,
            kwargs=kwargs,
            status=TaskStatus.PENDING,
            created_at=time.time(),
            max_tries=queue_config['max_tries']
        )

        # 持久化任务信息
        await self._update_task_info(task_info)

        # 加入队列
        await self.redis_client.lpush(RedisKeys.queue(queue), task_id)

        logger.info(f"Task {task_id} submitted to queue {queue}: {function}")
        return task_id

    async def _update_task_info(self, task_info: TaskInfo):
        """更新任务信息到 Redis"""
        # 直接使用 Pydantic 内置序列化
        serialized_data = task_info.model_dump_json(exclude_none=False)

        # 使用独立的 key: tasks:info:{task_id}
        task_key = RedisKeys.task_info(task_info.task_id)

        # 设置过期时间，优先使用队列配置，默认24小时
        queue_config = self.config['queues'][task_info.queue_name]
        expire_time = queue_config.get('keep_result', 24 * 3600)  # 默认24小时

        # 使用 setex 同时设置值和过期时间
        await self.redis_client.setex(task_key, expire_time, serialized_data)

    async def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        task_key = RedisKeys.task_info(task_id)
        task_data = await self.redis_client.get(task_key)
        if task_data:
            return TaskInfo.model_validate_json(task_data)
        return None

    async def start_workers(self, workers_per_queue: Dict[str, int] = None):
        """
        启动 Worker 进程

        Args:
            workers_per_queue: 每个队列的 Worker 数量，如 {"image_generation": 1, "audio_processing": 2}
                             如果未指定，每个队列启动1个 Worker
        """
        self.running = True

        if not workers_per_queue:
            workers_per_queue = {}
            for queue_name, queue_manager in self.queue_managers.items():
                workers_per_queue[queue_name] = queue_manager.max_jobs

        for queue_name in self.queue_managers.keys():
            worker_count = workers_per_queue.get(queue_name, 1)

            for i in range(worker_count):
                worker_id = f"{queue_name}-worker-{i+1}"
                worker_task = asyncio.create_task(self._worker_loop(queue_name, worker_id))
                self.workers.append(worker_task)
                logger.info(f"Started worker: {worker_id}")

        logger.info(f"All workers started: {len(self.workers)} workers across {len(self.queue_managers)} queues")

    async def _worker_loop(self, queue_name: str, worker_id: str):
        """Worker 主循环"""
        queue_manager = self.queue_managers[queue_name]

        logger.info(f"Worker {worker_id} started for queue {queue_name}")

        while self.running:
            try:
                # 从队列获取任务（阻塞式，超时3秒）
                result = await self.redis_client.brpop(RedisKeys.queue(queue_name), timeout=3)

                if not result:
                    continue  # 超时，继续等待

                _, task_id = result

                # 在信号量控制下执行任务（关键：并发控制）
                async with queue_manager.semaphore:
                    await self._execute_task(task_id, queue_name, worker_id)

            except Exception as e:
                logger.error(f"Worker {worker_id} encountered error: {e}")
                await asyncio.sleep(1)

        logger.info(f"Worker {worker_id} stopped")

    async def _execute_task(self, task_id: str, queue_name: str, worker_id: str):
        """执行单个任务"""
        task_info = None

        try:
            # 获取任务信息
            task_info = await self.get_task_status(task_id)
            if not task_info:
                logger.warning(f"Task {task_id} not found")
                return

            # 更新任务状态为运行中
            task_info.status = TaskStatus.RUNNING
            task_info.started_at = time.time()
            await self._update_task_info(task_info)

            # 将任务加入运行中集合
            await self.redis_client.sadd(RedisKeys.running_tasks(queue_name), task_id)

            logger.info(f"[{worker_id}] Executing task {task_id}: {task_info.function_name}")

            # 执行任务函数
            result = await self._call_function(
                task_info.function_name,
                task_info.args,
                task_info.kwargs,
                queue_name
            )

            # 任务成功完成
            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = time.time()
            # Pydantic 会自动处理结果的序列化问题
            task_info.result = result

            logger.info(f"[{worker_id}] Task {task_id} completed successfully")

        except Exception as e:
            # 任务执行失败
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"[{worker_id}] Task {task_id} failed: {error_msg}")

            if task_info:
                task_info.error = error_msg
                await self._handle_task_failure(task_info, queue_name)

        finally:
            if task_info:
                # 从运行中集合移除
                await self.redis_client.srem(RedisKeys.running_tasks(queue_name), task_id)

                # 更新最终的任务信息，添加异常处理
                try:
                    await self._update_task_info(task_info)
                except Exception as update_error:
                    logger.error(f"Failed to update task info for {task_id}: {update_error}")

    async def _call_function(self, function_name: str, args: List[Any], kwargs: Dict[str, Any], queue_name: str) -> Any:
        """动态调用函数"""
        try:
            # 解析模块和函数名
            if '.' in function_name:
                module_name, func_name = function_name.rsplit('.', 1)
                module = importlib.import_module(module_name)
                func = getattr(module, func_name)
            else:
                # 尝试从全局命名空间获取函数
                import sys
                current_module = sys.modules.get('__main__')
                if current_module and hasattr(current_module, function_name):
                    func = getattr(current_module, function_name)
                else:
                    raise AttributeError(f"Function '{function_name}' not found")

            # 获取超时配置
            queue_config = self.config['queues'][queue_name]
            timeout = queue_config['job_timeout']

            # 调用函数（支持同步和异步函数）
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            else:
                # 对于同步函数，在线程池中执行以避免阻塞
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                    timeout=timeout
                )

            return result

        except asyncio.TimeoutError:
            raise Exception(f"Task timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Function execution failed: {function_name}, error: {e}")
            raise

    async def _handle_task_failure(self, task_info: TaskInfo, queue_name: str):
        """处理任务失败和重试逻辑"""
        task_info.retry_count += 1

        if task_info.retry_count < task_info.max_tries:
            # 还可以重试
            task_info.status = TaskStatus.RETRYING

            # 计算重试延迟
            queue_config = self.config['queues'][queue_name]
            retry_delays = queue_config['retry_delay']

            # 选择适当的延迟时间
            if task_info.retry_count <= len(retry_delays):
                delay = retry_delays[task_info.retry_count - 1]
            else:
                delay = retry_delays[-1]  # 使用最后一个延迟值

            logger.info(f"Task {task_info.task_id} will retry in {delay}s (attempt {task_info.retry_count}/{task_info.max_tries})")

            # 更新状态并延迟重新入队
            await self._update_task_info(task_info)

            # 异步延迟重新入队
            asyncio.create_task(self._delayed_requeue(task_info.task_id, queue_name, delay))
        else:
            # 重试次数用完，标记为永久失败
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = time.time()
            logger.error(f"Task {task_info.task_id} permanently failed after {task_info.retry_count} attempts")

    async def _delayed_requeue(self, task_id: str, queue_name: str, delay: int):
        """延迟重新入队任务"""
        await asyncio.sleep(delay)

        # 重新获取任务信息并设置为 PENDING
        task_info = await self.get_task_status(task_id)
        if task_info and task_info.status == TaskStatus.RETRYING:
            task_info.status = TaskStatus.PENDING
            await self._update_task_info(task_info)
            # 使用 rpush 让重试任务插队到队列前端（靠近 brpop 取出端）
            await self.redis_client.rpush(RedisKeys.queue(queue_name), task_id)
            logger.info(f"Task {task_id} requeued for retry (priority)")

    async def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        stats = {}

        for queue_name, manager in self.queue_managers.items():
            # 队列中等待的任务数
            queue_length = await self.redis_client.llen(RedisKeys.queue(queue_name))

            # 正在运行的任务数
            running_tasks = await self.redis_client.scard(RedisKeys.running_tasks(queue_name))

            stats[queue_name] = {
                "pending_tasks": queue_length,
                "running_tasks": running_tasks,
                "max_concurrent_jobs": manager.max_jobs,
                "available_slots": manager.semaphore._value,
                "current_running_count": manager.current_running_count
            }

        return stats

    async def has_active_tasks(self) -> bool:
        """
        检查是否还有活动任务（等待中或运行中）

        Returns:
            bool: True表示还有任务在执行或等待，False表示所有队列都空闲
        """
        for queue_name in self.queue_managers.keys():
            # 检查队列中等待的任务数
            queue_length = await self.redis_client.llen(RedisKeys.queue(queue_name))

            # 检查正在运行的任务数
            running_tasks = await self.redis_client.scard(RedisKeys.running_tasks(queue_name))

            # 如果任何队列有等待或运行中的任务，返回True
            if queue_length > 0 or running_tasks > 0:
                return True

        return False

    async def cleanup_completed_tasks(self, older_than_hours: int = 24):
        """
        清理已完成的旧任务
        注意：由于改为独立key且有过期时间，这个方法主要用于强制清理
        """
        logger.info("Starting manual cleanup of completed tasks...")
        cleaned_count = 0

        # 由于无法直接获取所有 tasks:info:* keys，
        # 我们依赖 Redis 的自动过期机制
        # 这个方法现在主要用于清理运行中任务集合的残留数据

        for queue_name in self.queue_managers.keys():
            try:
                # 清理可能残留的运行中任务集合
                running_key = RedisKeys.running_tasks(queue_name)
                running_tasks = await self.redis_client.smembers(running_key)

                for task_id in running_tasks:
                    # 检查任务信息是否还存在
                    task_key = RedisKeys.task_info(task_id)
                    exists = await self.redis_client.exists(task_key)

                    if not exists:
                        # 任务信息已过期但仍在运行集合中，清理它
                        await self.redis_client.srem(running_key, task_id)
                        cleaned_count += 1
                        logger.debug(f"Cleaned orphaned running task: {task_id}")

            except Exception as e:
                logger.error(f"Error cleaning queue {queue_name}: {e}")

        logger.info(f"Manual cleanup completed: {cleaned_count} orphaned records cleaned")
        return cleaned_count

    async def clear_all_queues(self):
        """
        清空所有Redis队列和相关数据（用于测试前清理）
        """
        logger.info("Clearing all Redis queues and task data...")
        cleared_items = {
            'queues': 0,
            'running_tasks': 0,
            'task_info': 0
        }

        try:
            # 1. 清空所有队列
            for queue_name in self.queue_managers.keys():
                queue_key = RedisKeys.queue(queue_name)
                queue_length = await self.redis_client.llen(queue_key)
                if queue_length > 0:
                    await self.redis_client.delete(queue_key)
                    cleared_items['queues'] += queue_length
                    logger.debug(f"Cleared queue {queue_name}: {queue_length} tasks")

            # 2. 清空所有运行中任务集合
            for queue_name in self.queue_managers.keys():
                running_key = RedisKeys.running_tasks(queue_name)
                running_count = await self.redis_client.scard(running_key)
                if running_count > 0:
                    await self.redis_client.delete(running_key)
                    cleared_items['running_tasks'] += running_count
                    logger.debug(f"Cleared running tasks for {queue_name}: {running_count} tasks")

            # 3. 清空所有任务信息（通过模式匹配）
            task_keys = []
            cursor = 0
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match="tasks:info:*",
                    count=1000
                )
                task_keys.extend(keys)
                if cursor == 0:
                    break

            if task_keys:
                await self.redis_client.delete(*task_keys)
                cleared_items['task_info'] = len(task_keys)
                logger.debug(f"Cleared task info keys: {len(task_keys)} items")

            logger.info(f"Queue clearing completed: {cleared_items}")
            return cleared_items

        except Exception as e:
            logger.error(f"Error clearing queues: {e}")
            raise

    async def shutdown(self):
        """优雅关闭任务管理器"""
        logger.info("Shutting down TaskManager...")

        # 停止接受新任务
        self.running = False

        # 等待所有 Worker 完成当前任务
        if self.workers:
            logger.info("Waiting for workers to complete current tasks...")
            await asyncio.gather(*self.workers, return_exceptions=True)
            logger.info("All workers stopped")

        # 关闭共享的 Redis 连接
        # 注意：这会关闭全局的 Redis 连接，影响其他使用者
        await close_redis()

        logger.info("TaskManager shutdown complete")


# 全局任务管理器实例
_task_manager_instance = None


async def get_task_manager() -> TaskManager:
    """获取全局任务管理器实例"""
    global _task_manager_instance

    if _task_manager_instance is None:
        _task_manager_instance = TaskManager()
        await _task_manager_instance.initialize()
        await _task_manager_instance.start_workers()

    return _task_manager_instance


# 便捷接口函数
# 直接使用 TaskManager 实例的方法，不再提供过度封装的全局函数
# 示例用法：
# task_manager = await get_task_manager()
# task_id = await task_manager.submit_task(function, args, kwargs, queue)
# task_info = await task_manager.get_task_status(task_id)
# stats = await task_manager.get_queue_stats()
