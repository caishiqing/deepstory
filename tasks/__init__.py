"""
story.ai 任务管理包
"""

# 数据模型 - 统一数据类型定义
from .models import (
    TaskStatus, TaskInfo, TaskResult, PollingConfig, ResourceResult,
    TaskCallback, TaskTimeoutError, TaskExecutionError
)

# TaskManager - 任务管理器
from .task_manager import TaskManager, get_task_manager

# 传统异步任务框架
from .async_task_handler import AsyncTask, TaskPoller, TaskExecutor

# sync_tasks - 同步任务函数
from .sync_tasks import dialogue_asr, sound_audio

# async_tasks - 异步任务函数
from .async_tasks import RunningHubTask, character_portrait, scene_drawing
