"""
资源就绪追踪器

简单的异步资源管理工具，用于等待异步资源就绪并获取结果。
"""

import asyncio
from typing import Dict, Any, Optional
from loguru import logger


class ResourceTracker:
    """资源就绪追踪器

    用于管理异步资源的就绪状态和结果值。
    典型使用场景：等待异步任务完成并获取其结果。

    Example:
        tracker = ResourceTracker()

        # 注册资源
        tracker.register("user_voice")

        # 在后台任务中标记就绪
        await process_user()
        tracker.set_ready("user_voice", "温柔的女声")

        # 在其他地方等待并获取结果
        voice = await tracker.get("user_voice")  # 返回 "温柔的女声"
    """

    def __init__(self):
        # 存储事件和结果值
        self._events: Dict[str, asyncio.Event] = {}
        self._results: Dict[str, Any] = {}

    def register(self, key: str) -> None:
        """注册一个资源键

        Args:
            key: 资源的唯一标识符
        """
        if key not in self._events:
            self._events[key] = asyncio.Event()
            self._results[key] = None
            logger.debug(f"Registered resource: {key}")

    def set_ready(self, key: str, result: Any = None) -> None:
        """标记资源已就绪，并设置结果值

        Args:
            key: 资源的唯一标识符
            result: 资源的结果值（可选）
        """
        # 自动注册（如果未注册）
        if key not in self._events:
            self.register(key)

        # 设置结果并触发事件
        self._results[key] = result
        self._events[key].set()
        logger.debug(f"Resource ready: {key}")

    async def get(self,
                  key: str,
                  timeout: Optional[float] = None,
                  default: Any = None) -> Any:
        """阻塞式获取资源结果

        如果资源未就绪，会等待直到就绪或超时。

        Args:
            key: 资源的唯一标识符
            timeout: 超时时间（秒），None 表示永不超时
            default: 超时时返回的默认值

        Returns:
            资源的结果值，如果超时则返回 default
        """
        # 自动注册（如果未注册）
        if key not in self._events:
            self.register(key)

        try:
            # 等待资源就绪
            if timeout is not None:
                await asyncio.wait_for(
                    self._events[key].wait(),
                    timeout=timeout
                )
            else:
                await self._events[key].wait()

            # 返回结果
            result = self._results[key]
            logger.debug(f"Got resource: {key} = {result}")
            return result

        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for resource: {key} (timeout={timeout}s), returning default value")
            return default

    def is_ready(self, key: str) -> bool:
        """检查资源是否已就绪（非阻塞）

        Args:
            key: 资源的唯一标识符

        Returns:
            True 表示已就绪，False 表示未就绪或不存在
        """
        if key not in self._events:
            return False
        return self._events[key].is_set()

    def get_nowait(self, key: str, default: Any = None) -> Any:
        """非阻塞式获取资源结果

        如果资源未就绪，立即返回 default。

        Args:
            key: 资源的唯一标识符
            default: 资源未就绪时返回的默认值

        Returns:
            资源的结果值，如果未就绪则返回 default
        """
        if key not in self._events or not self._events[key].is_set():
            return default
        return self._results[key]

    def clear(self, key: str) -> None:
        """清除指定资源的状态

        Args:
            key: 资源的唯一标识符
        """
        if key in self._events:
            del self._events[key]
            del self._results[key]
            logger.debug(f"Cleared resource: {key}")

    def clear_all(self) -> None:
        """清除所有资源的状态"""
        count = len(self._events)
        self._events.clear()
        self._results.clear()
        logger.debug(f"Cleared all resources ({count} total)")
