"""
RunningHub 任务实现示例
"""
import os
from loguru import logger
from typing import Any, Dict
from utils import download_file
from tasks.logger_config import task_logger
from .async_task_handler import AsyncTask, TaskPoller, TaskExecutor
from .models import TaskStatus, PollingConfig
from endpoints.runninghub import create_runninghub_task, get_runninghub_task_status, get_runninghub_task_result


class RunningHubTask(AsyncTask):
    """RunningHub 图像生成任务"""

    def __init__(self, save_path: str, tag: str, attribute: str = None, task_id: str = None):
        super().__init__(task_id)
        self.save_path = save_path
        self.tag = tag
        self.attribute = attribute

        os.makedirs(self.save_path, exist_ok=True)
        logger.info(f"RunningHubTask initialized for tag '{tag}',attribute '{attribute}', save path: {self.save_path}")

    async def _create(self, **kwargs) -> str:
        """创建 RunningHub 任务"""
        workflow_id = kwargs.get("workflow_id")
        node_info_list = kwargs.get("node_info_list")
        add_metadata = kwargs.get("add_metadata", True)
        webhook_url = kwargs.get("webhook_url")
        instance_type = kwargs.get("instance_type", "plus")
        use_personal_queue = kwargs.get("use_personal_queue", True)

        logger.debug(f"Task parameters: workflow_id={workflow_id}, node_info_list={node_info_list}")

        try:
            # 调用现有的 create 函数
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
            logger.error(f"Failed to create RunningHub task for tag '{self.tag}', attribute '{self.attribute}': {e}")
            raise

    async def _get_status(self, task_id: str) -> TaskStatus:
        """获取任务状态"""
        try:
            response = await get_runninghub_task_status(task_id)
            raw_status = response.get("data", "").lower() if response else "failed"
            normalized_status = self._normalize_status(raw_status)
            logger.debug(f"Status: {raw_status} -> {normalized_status.value}")
            return normalized_status

        except Exception as e:
            logger.error(f"Failed to get status for task {task_id}: {e}")
            return TaskStatus.FAILED

    async def _get_result(self, task_id: str) -> Any:
        """获取任务结果"""
        try:
            result = await get_runninghub_task_result(task_id)
            if result and result.get("data"):
                file_count = len(result["data"])
                logger.debug(f"Retrieved {file_count} files from result")
            else:
                raise Exception(f"No result data found for task {task_id}! Message: {result.get('msg')}")

            return result

        except Exception as e:
            logger.error(f"Failed to get result for task {task_id}: {e}")
            raise

    async def callback(self, status: TaskStatus) -> None:
        """状态变化回调"""
        if status == TaskStatus.COMPLETED:
            logger.info(f"Starting file downloads for '{self.tag}', '{self.attribute}'")
            if self._result is None:
                if not self.task_id:
                    raise Exception(f"Task has not been created!")

                self._result = await self.get_result(self.task_id)

            if not self._result or "data" not in self._result:
                msg = f"No result data available for downloading!"
                logger.warning(msg)
                raise Exception(msg)

            for i, data in enumerate(self._result["data"], 1):
                try:
                    url = data["fileUrl"]
                    source_name = url.split("/")[-1]
                    prefix = source_name.split("_")[0]
                    attribute = self.attribute or prefix
                    extension = source_name.split(".")[-1]
                    save_name = f"{self.tag} {attribute}.{extension}"
                    save_path = os.path.join(self.save_path, save_name)

                    logger.debug(f"Downloading {i}/{len(self._result['data'])}: {save_name}")
                    await download_file(url, save_path)
                    logger.info(f"Downloaded: {save_name}")

                except Exception as e:
                    logger.error(f"Failed to download file {i}: {e}")

            logger.info(f"All files downloaded to {self.save_path}")

        elif status in [TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT]:
            msg = f"Task ended with status {status.value} for '{self.tag}', '{self.attribute}'"
            logger.warning(msg)
            # 不在 callback 中抛出异常，让 TaskExecutor 处理失败状态并触发重试


@task_logger("character_portrait")
async def character_portrait(save_path: str, tag: str, description: str):
    """角色立绘"""
    logger.info(f"Starting character portrait for '{tag}'")

    task = RunningHubTask(save_path, tag)
    executor = TaskExecutor()

    params = {
        "workflow_id": "1997665824230019074",
        "node_info_list": [{"nodeId": "215", "fieldName": "String", "fieldValue": description}]
    }

    return await executor.execute_task(task, task_params=params)


@task_logger("scene_drawing")
async def scene_drawing(save_path: str, tag: str, attribute: str, description: str):
    """场景绘图"""
    logger.info(f"Starting scene drawing for '{tag}', '{attribute}'")

    task = RunningHubTask(save_path, tag, attribute)
    executor = TaskExecutor()

    params = {
        "workflow_id": "1953068722455048194",
        "node_info_list": [{"nodeId": "80", "fieldName": "String", "fieldValue": description}]
    }

    return await executor.execute_task(task, task_params=params)
