"""
RunningHub 图像生成任务

任务执行层：只负责调用外部 API，返回 ResourceResult（URL）。
不做下载，下载由消费层处理。
"""
from endpoints.runninghub import create_runninghub_task, get_runninghub_task_status, get_runninghub_task_result
from .models import TaskStatus, ResourceResult, ImageResourceResult, PortraitResourceResult
from .async_task_handler import AsyncTask, TaskExecutor
from tasks.logger_config import task_logger
import asyncio
import re
from loguru import logger
from typing import Any, Optional

# RunningHub 任务完成后等待时间（秒），模拟原来的下载操作，让配额释放
RUNNINGHUB_COOLDOWN = 5


class RunningHubTask(AsyncTask):
    """RunningHub 图像生成任务"""

    def __init__(self, task_id: str = None):
        super().__init__(task_id)
        logger.info(f"RunningHubTask initialized: task_id='{task_id}'")

    async def _create(self, **kwargs) -> str:
        """创建 RunningHub 任务"""
        workflow_id = kwargs.get("workflow_id")
        node_info_list = kwargs.get("node_info_list")
        add_metadata = kwargs.get("add_metadata", True)
        webhook_url = kwargs.get("webhook_url")
        instance_type = kwargs.get("instance_type")
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

            # 收集所有 URL，从文件名提取标签作为 key
            url_map = {}
            for data in self._result["data"]:
                if data.get("fileUrl"):
                    url = data["fileUrl"]
                    # 从文件名提取标签（情绪、场景类型等）
                    label = _extract_label_from_filename(url)
                    # 同一标签保留第一个 URL（避免重复）
                    if label not in url_map:
                        url_map[label] = url

            return ResourceResult(
                resource_type="image",
                url_map=url_map,
                metadata={"task_id": self.task_id, "file_count": len(url_map)}
            )

        elif status in [TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
            logger.warning(f"Task ended with status {status.value}: task_id={self.task_id}")
            return None


def _extract_label_from_filename(url: str) -> str:
    """从文件 URL 中提取前缀标签

    通用标签提取逻辑，适用于所有 RunningHub 任务：
    - 角色立绘：happy / sad / surprised / fearful / disgusted / angry / normal
    - 场景背景：outdoor / indoor / forest / city 等
    - 其他资源：任意自定义标签

    URL 命名规则：{label}_xxxxx.png

    示例：
    - https://xxx/fearful_00007.png -> fearful
    - https://xxx/outdoor_scene123.jpg -> outdoor
    - https://xxx/normal_test.png -> normal
    """
    try:
        filename = url.split("/")[-1].split("?")[0]  # 提取文件名
        name_without_ext = filename.rsplit(".", 1)[0]  # 去除扩展名

        # 提取前缀标签（第一个下划线前的部分）
        parts = name_without_ext.split("_")
        if len(parts) > 1 and parts[0]:
            return parts[0].lower()

        # 如果没有下划线，整个文件名就是标签
        return name_without_ext.lower() if name_without_ext else "default"

    except Exception as e:
        logger.warning(f"Failed to extract label from URL {url}: {e}")
        return "default"


@task_logger("character_portrait")
async def character_portrait(description: str, character_name: str = None, age: str = None) -> PortraitResourceResult:
    """角色立绘（多情绪）

    Args:
        description: 角色描述提示词
        character_name: 角色名（可选，用于 metadata）
        age: 年龄段（可选，用于 metadata）

    Returns:
        PortraitResourceResult: 包含多个情绪图像 URL 的结果
    """
    logger.info(f"Character portrait: desc_len={len(description)}, character={character_name}, age={age}")

    task = RunningHubTask()
    executor = TaskExecutor()

    params = {
        "workflow_id": "1997665824230019074",
        "node_info_list": [{"nodeId": "215", "fieldName": "String", "fieldValue": description}],
        "instance_type": "plus"
    }

    try:
        task_result = await executor.execute_task(task, task_params=params)
        base_result: ResourceResult = task_result.result

        # 底层 callback 已经提取了标签，直接使用 url_map
        logger.info(f"Character portrait completed: {len(base_result.url_map)} emotions detected: {list(base_result.url_map.keys())}")

        return PortraitResourceResult(
            character=character_name,
            age=age,
            url_map=base_result.url_map,
            metadata={
                "task_id": base_result.metadata.get("task_id"),
                "total_images": len(base_result.url_map)
            }
        )
    finally:
        # 无论成功还是失败，都等待 RunningHub 配额释放
        await asyncio.sleep(RUNNINGHUB_COOLDOWN)


@task_logger("scene_drawing")
async def scene_drawing(description: str) -> ImageResourceResult:
    """场景绘图

    Args:
        description: 场景描述提示词

    Returns:
        ImageResourceResult: 包含图像 URL 的结果
    """
    logger.info(f"Scene drawing: desc_len={len(description)}")

    task = RunningHubTask()
    executor = TaskExecutor()

    params = {
        "workflow_id": "1953068722455048194",
        "node_info_list": [{"nodeId": "80", "fieldName": "String", "fieldValue": description}]
    }

    try:
        task_result = await executor.execute_task(task, task_params=params)
        base_result: ResourceResult = task_result.result

        # 底层 callback 已经提取了标签，直接使用 url_map
        return ImageResourceResult(
            url_map=base_result.url_map,
            metadata=base_result.metadata
        )
    finally:
        # 无论成功还是失败，都等待 RunningHub 配额释放
        await asyncio.sleep(RUNNINGHUB_COOLDOWN)
