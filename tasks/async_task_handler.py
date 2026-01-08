import asyncio
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, List, Set, Callable
from dataclasses import field
import time

from .models import TaskStatus, TaskResult, PollingConfig, TaskCallback, TaskTimeoutError, TaskExecutionError


class AsyncTask(ABC):
    """异步任务抽象基类"""

    def __init__(self, task_id: str = None):
        self.task_id = task_id
        self.created_at = time.time()
        self._status = TaskStatus.PENDING
        self._result = None
        self._error = None

    @abstractmethod
    async def _create(self, **kwargs) -> str:
        """创建任务，返回任务ID"""
        pass

    @abstractmethod
    async def _get_status(self, task_id: str) -> TaskStatus:
        """获取任务状态"""
        pass

    @abstractmethod
    async def _get_result(self, task_id: str) -> Any:
        """获取任务结果"""
        pass

    async def create(self, **kwargs) -> str:
        """创建任务，返回任务ID"""
        self.task_id = await self._create(**kwargs)
        return self.task_id

    async def get_status(self, task_id: str) -> TaskStatus:
        """获取任务状态"""
        self._status = await self._get_status(task_id)
        return self._status

    async def get_result(self, task_id: str) -> Any:
        """获取任务结果"""
        if self._result is not None:
            return self._result
        else:
            self._result = await self._get_result(task_id)
            return self._result

    async def cancel(self, task_id: str) -> bool:
        """取消任务（可选实现）"""
        return False

    async def callback(self, status: TaskStatus) -> None:
        """状态变化回调（子类可重写）"""
        pass

    def _normalize_status(self, raw_status: str) -> TaskStatus:
        """将API返回的状态转换为标准状态"""
        status_mapping = {
            "queued": TaskStatus.QUEUED,
            "running": TaskStatus.RUNNING,
            "completed": TaskStatus.COMPLETED,
            "success": TaskStatus.COMPLETED,
            "successed": TaskStatus.COMPLETED,
            "error": TaskStatus.FAILED,
            "failed": TaskStatus.FAILED,
            "cancelled": TaskStatus.CANCELLED,
            "pending": TaskStatus.PENDING,
        }

        normalized = raw_status.lower()
        return status_mapping.get(normalized, TaskStatus.PENDING)


class TaskPoller:
    """任务轮询器"""

    def __init__(self, config: PollingConfig = None):
        self.config = config or PollingConfig()

    async def poll_until_complete(
        self,
        task: AsyncTask,
        task_id: str,
        on_progress: Optional[Callable[[Dict], None]] = None
    ) -> TaskResult:
        """轮询直到任务完成"""

        start_time = time.time()
        current_interval = self.config.initial_interval
        attempts = 0
        last_status = None

        while attempts < self.config.max_attempts:
            try:
                # 检查总超时
                if time.time() - start_time > self.config.timeout:
                    logger.warning(f"Task {task_id} polling timeout after {self.config.timeout}s")
                    return TaskResult(
                        task_id=task_id,
                        status=TaskStatus.TIMEOUT,
                        error=f"Polling timeout after {self.config.timeout}s"
                    )

                # 获取任务状态
                current_status = await task.get_status(task_id)

                # 进度回调（可选）
                if on_progress:
                    progress_info = {
                        "task_id": task_id,
                        "status": current_status.value,
                        "attempts": attempts,
                        "elapsed_time": time.time() - start_time
                    }
                    on_progress(progress_info)

                # 状态变化回调（非终态时）
                if current_status != last_status and current_status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    await task.callback(current_status)
                    last_status = current_status

                # 检查终态
                if current_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    try:
                        if current_status == TaskStatus.COMPLETED:
                            # 调用 callback 获取结构化结果（如 ResourceResult）
                            callback_result = await task.callback(current_status)
                            return TaskResult(
                                task_id=task_id,
                                status=current_status,
                                result=callback_result,  # 使用 callback 返回的结构化结果
                                completed_at=time.time()
                            )
                        else:
                            await task.callback(current_status)
                            return TaskResult(
                                task_id=task_id,
                                status=current_status,
                                error=f"Task ended with status: {current_status.value}",
                                completed_at=time.time()
                            )
                    except Exception as e:
                        logger.error(f"Error getting result for task {task_id}: {e}")
                        return TaskResult(
                            task_id=task_id,
                            status=TaskStatus.FAILED,
                            error=str(e),
                            completed_at=time.time()  # 模型会自动转换
                        )

                # 等待下次轮询
                await asyncio.sleep(current_interval)
                attempts += 1

                # 调整轮询间隔（指数退避）
                if self.config.exponential_backoff:
                    current_interval = min(
                        current_interval * self.config.backoff_factor,
                        self.config.max_interval
                    )

            except Exception as e:
                logger.error(f"Error polling task {task_id} (attempt {attempts}): {e}")
                attempts += 1
                await asyncio.sleep(current_interval)

        # 超过最大轮询次数
        return TaskResult(
            task_id=task_id,
            status=TaskStatus.TIMEOUT,
            error=f"Maximum polling attempts ({self.config.max_attempts}) exceeded"
        )


class TaskExecutor:
    """任务执行器 - 整合任务创建、轮询和结果获取的完整流程"""

    def __init__(self, polling_config: PollingConfig = None):
        self.polling_config = polling_config or PollingConfig()
        self.poller = TaskPoller(self.polling_config)

    async def execute_task(
        self,
        task: AsyncTask,
        task_params: Dict[str, Any] = None,
        on_progress: Optional[Callable[[Dict], None]] = None
    ) -> TaskResult:
        """
        执行单个任务的完整流程

        Args:
            task: 要执行的任务实例
            task_params: 任务参数
            on_progress: 进度回调函数 (progress_info) -> None

        Returns:
            TaskResult: 任务执行结果
        """
        task_params = task_params or {}

        try:
            # 步骤1: 创建任务
            logger.info(f"Creating task with params: {task_params}")
            task_id = await task.create(**task_params)
            logger.info(f"Task created with ID: {task_id}")

            # 步骤2: 轮询任务状态直到完成
            logger.info(f"Starting to poll task {task_id}")
            result = await self.poller.poll_until_complete(
                task=task,
                task_id=task_id,
                on_progress=on_progress
            )

            logger.info(f"Task {task_id} completed with status: {result.status}")

            # 检查任务是否成功完成
            if result.status == TaskStatus.COMPLETED:
                return result
            else:
                # 任务失败、取消或超时，抛出异常触发 task_manager 重试
                error_msg = result.error or f"Task ended with status: {result.status.value}"
                logger.error(f"Task {task_id} failed: {error_msg}")
                raise Exception(error_msg)

        except Exception as e:
            logger.error(f"Error executing task: {e}")
            # 抛出异常，让 task_manager 捕获并触发重试机制
            raise
