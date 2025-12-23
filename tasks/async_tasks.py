"""
RunningHub 图像生成任务

任务执行层：只负责调用外部 API，返回 ResourceResult（URL）。
不做下载，下载由消费层处理。
"""
from endpoints.runninghub import create_runninghub_task, get_runninghub_task_status, get_runninghub_task_result
from .models import TaskStatus, ResourceResult
from .async_task_handler import AsyncTask, TaskExecutor
from tasks.logger_config import task_logger
import asyncio
from loguru import logger
from typing import Any, Optional

# RunningHub 任务完成后等待时间（秒），模拟原来的下载操作，让配额释放
RUNNINGHUB_COOLDOWN = 5


class RunningHubTask(AsyncTask):
    """RunningHub 图像生成任务"""

    def __init__(self, tag: str, attribute: str = None, task_id: str = None):
        super().__init__(task_id)
        self.tag = tag
        self.attribute = attribute
        logger.info(f"RunningHubTask initialized: tag='{tag}', attribute='{attribute}'")

    async def _create(self, **kwargs) -> str:
        """创建 RunningHub 任务"""
        workflow_id = kwargs.get("workflow_id")
        node_info_list = kwargs.get("node_info_list")
        add_metadata = kwargs.get("add_metadata", True)
        webhook_url = kwargs.get("webhook_url")
        instance_type = kwargs.get("instance_type", "plus")
        use_personal_queue = kwargs.get("use_personal_queue", True)

        try:
            response = await create_runninghub_task(
                workflow_id,
                node_info_list=node_info_list,
                add_metadata=add_metadata,
                webhook_url=webhook_url,
                instance_type=instance_type,
                use_personal_queue=use_personal_queue
            )
            return response["taskId"]
        except Exception as e:
            logger.error(f"Failed to create RunningHub task: {e}")
            raise

    async def _get_status(self, task_id: str) -> TaskStatus:
        """获取任务状态"""
        try:
            response = await get_runninghub_task_status(task_id)
            raw_status = response.get("data", "").lower() if response else "failed"
            return self._normalize_status(raw_status)
        except Exception as e:
            logger.error(f"Failed to get status for task {task_id}: {e}")
            return TaskStatus.FAILED

    async def _get_result(self, task_id: str) -> Any:
        """获取任务结果"""
        try:
            result = await get_runninghub_task_result(task_id)
            if not result or not result.get("data"):
                raise Exception(f"No result data for task {task_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to get result for task {task_id}: {e}")
            raise

    async def callback(self, status: TaskStatus) -> Optional[ResourceResult]:
        """状态变化回调 - 返回 ResourceResult"""
        if status == TaskStatus.COMPLETED:
            if self._result is None:
                self._result = await self.get_result(self.task_id)

            if not self._result or "data" not in self._result:
                raise Exception("No result data available")

            # 收集所有 URL
            urls = [data["fileUrl"] for data in self._result["data"] if data.get("fileUrl")]

            return ResourceResult(
                resource_type="image",
                urls=urls,
                tag=self.tag,
                attribute=self.attribute,
                metadata={"task_id": self.task_id, "file_count": len(urls)}
            )

        elif status in [TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
            logger.warning(f"Task ended with status {status.value}: {self.tag}")
            return None


@task_logger("character_portrait")
async def character_portrait(tag: str, description: str) -> ResourceResult:
    """角色立绘

    Args:
        tag: 角色标签（如 'peter5a qingnian'）
        description: 角色描述提示词

    Returns:
        ResourceResult: 包含图像 URL 的结果
    """
    logger.info(f"Character portrait: {tag}")

    task = RunningHubTask(tag)
    executor = TaskExecutor()

    params = {
        "workflow_id": "1997665824230019074",
        "node_info_list": [{"nodeId": "215", "fieldName": "String", "fieldValue": description}]
    }

    try:
        task_result = await executor.execute_task(task, task_params=params)
        return task_result.result  # 提取 ResourceResult
    finally:
        # 无论成功还是失败，都等待 RunningHub 配额释放
        await asyncio.sleep(RUNNINGHUB_COOLDOWN)


@task_logger("scene_drawing")
async def scene_drawing(tag: str, attribute: str, description: str) -> ResourceResult:
    """场景绘图

    Args:
        tag: 场景标签（如 'bg'）
        attribute: 场景属性（如 'bg1234'）
        description: 场景描述提示词

    Returns:
        ResourceResult: 包含图像 URL 的结果
    """
    logger.info(f"Scene drawing: {tag} {attribute}")

    task = RunningHubTask(tag, attribute)
    executor = TaskExecutor()

    params = {
        "workflow_id": "1953068722455048194",
        "node_info_list": [{"nodeId": "80", "fieldName": "String", "fieldValue": description}]
    }

    try:
        task_result = await executor.execute_task(task, task_params=params)
        return task_result.result  # 提取 ResourceResult
    finally:
        # 无论成功还是失败，都等待 RunningHub 配额释放
        await asyncio.sleep(RUNNINGHUB_COOLDOWN)
