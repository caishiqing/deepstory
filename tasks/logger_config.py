"""
任务日志配置模块
为不同类型的任务创建独立的日志文件
"""
import os
from loguru import logger
from functools import wraps
import asyncio

# 日志文件存储目录
LOG_DIR = "logs/tasks"
os.makedirs(LOG_DIR, exist_ok=True)

# 为每种任务类型配置独立的日志文件
TASK_LOGGERS = {
    "character_portrait": f"{LOG_DIR}/character_portrait.log",
    "scene_drawing": f"{LOG_DIR}/scene_drawing.log",
    "dialogue_asr": f"{LOG_DIR}/dialogue_asr.log",
    "sound_audio": f"{LOG_DIR}/sound_audio.log",
}

# 配置每个任务类型的日志
for task_type, log_file in TASK_LOGGERS.items():
    logger.add(
        log_file,
        rotation="10 MB",  # 日志文件达到 10MB 时轮转
        retention="7 days",  # 保留 7 天
        compression="zip",  # 压缩旧日志
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        filter=lambda record, task=task_type: record["extra"].get("task_type") == task
    )


def task_logger(task_type: str):
    """
    装饰器：为任务函数添加专属日志上下文

    用法:
        @task_logger("character_portrait")
        async def character_portrait(...):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 绑定任务类型到日志上下文
            with logger.contextualize(task_type=task_type):
                logger.info(f"🚀 Starting {task_type} task")
                try:
                    result = await func(*args, **kwargs)
                    logger.info(f"✅ Completed {task_type} task")
                    return result
                except Exception as e:
                    logger.error(f"❌ Failed {task_type} task: {e}")
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with logger.contextualize(task_type=task_type):
                logger.info(f"🚀 Starting {task_type} task")
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"✅ Completed {task_type} task")
                    return result
                except Exception as e:
                    logger.error(f"❌ Failed {task_type} task: {e}")
                    raise

        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
