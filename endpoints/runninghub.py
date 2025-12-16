from loguru import logger
import aiohttp
import dotenv
import os

from utils import async_retry

dotenv.load_dotenv()


class RunningHubClient:

    def __init__(self, endpoint: str, api_key: str = None):
        self.endpoint = endpoint
        self.host = "www.runninghub.cn"
        self.api_key = api_key or os.getenv("RUNNINGHUB_API_KEY")

    @property
    def headers(self):
        return {
            "host": self.host,
            "Content-Type": "application/json"
        }

    async def invoke(self, payload: dict):
        # 统一添加 apiKey
        payload["apiKey"] = self.api_key

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://{self.host}/task/openapi/{self.endpoint}",
                json=payload,
                headers=self.headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    text = await response.text()
                    raise Exception(text)


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def create_runninghub_task(workflow_id: str,
                                 node_info_list: list = None,
                                 add_metadata: bool = True,
                                 webhook_url: str = None,
                                 instance_type: str = None,
                                 use_personal_queue: bool = False):
    """发起RunningHub ComfyUI任务（高级）

    Args:
        workflow_id: 工作流模板ID
        node_info_list: 节点参数修改列表，格式为[{"nodeId": "6", "fieldName": "text", "fieldValue": "1 girl in classroom"}]
        add_metadata: 是否在图片中写入元信息
        webhook_url: 任务完成后回调的URL
        instance_type: 发起任务指定实例类型（如"plus"）
        use_personal_queue: 独占类型任务是否入队

    Returns:
        dict: 任务创建响应数据，包含以下字段：
            - taskId (str): 创建的任务ID，可用于查询状态或获取结果
            - taskStatus (str): 初始状态，可能为：QUEUED、RUNNING、FAILED
            - clientId (str): 平台内部标识，用于排错，无需关注
            - netWssUrl (str): WebSocket地址（当前不稳定，不推荐使用）
            - promptTips (str): ComfyUI校验信息（字符串格式的JSON），可用于识别配置异常节点

    Example:
        {
            "taskId": "1910246754753896450",
            "taskStatus": "QUEUED",
            "clientId": "e825290b08ca2015b8f62f0bbdb5f5f6",
            "netWssUrl": null,
            "promptTips": "{\"result\": true, \"error\": null, \"outputs_to_execute\": [\"9\"], \"node_errors\": {}}"
        }
    """
    client = RunningHubClient("create")
    payload = {
        "workflowId": workflow_id
    }

    # 添加可选参数
    if node_info_list:
        payload["nodeInfoList"] = node_info_list
    if not add_metadata:
        payload["addMetadata"] = add_metadata
    if webhook_url:
        payload["webhookUrl"] = webhook_url
    if instance_type:
        payload["instanceType"] = instance_type
    if use_personal_queue:
        payload["usePersonalQueue"] = use_personal_queue

    result = await client.invoke(payload)
    if not result.get("data"):
        raise Exception(f"Failed to create RunningHub task: {result['msg']}")

    return result["data"]


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_runninghub_task_status(task_id: str):
    """获取任务状态

    Args:
        task_id: 任务ID

    Returns:
        dict: 任务状态响应数据，包含以下字段：
            - code (int): 状态码，0表示成功
            - msg (str): 提示信息
            - data (str): 任务状态信息，可能的状态包括：
                - QUEUED: 任务已排队等待执行
                - RUNNING: 任务正在执行中
                - COMPLETED: 任务执行完成
                - FAILED: 任务执行失败
                - CANCELLED: 任务已取消

    Example:
        {
            "code": 0,
            "msg": "success",
            "data": "RUNNING"
        }
    """
    client = RunningHubClient("status")
    payload = {
        "taskId": task_id
    }

    result = await client.invoke(payload)
    if result.get("code") != 0 or result.get("msg") != "success":
        raise Exception(f"Failed to get RunningHub task {task_id} status: {result['msg']}")

    return result


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_runninghub_task_result(task_id: str):
    """获取任务生成结果

    Args:
        task_id: 任务ID

    Returns:
        str: 任务结果文件URL

    Note:
        实际API返回的完整结构包含以下字段：
        - code (int): 状态码，0表示成功
        - msg (str): 提示信息
        - data (list): 结果数据列表，每个元素包含：
            - fileUrl (str): 生成文件的下载URL
            - fileType (str): 文件类型（如"png"、"jpg"等）
            - taskCostTime (int): 任务执行耗时
            - nodeId (str): 输出节点ID

    Example API Response:
        {
            "code": 0,
            "msg": "success",
            "data": [
                {
                    "fileUrl": "https://.../xxx.png",
                    "fileType": "png",
                    "taskCostTime": 0,
                    "nodeId": "9"
                }
            ]
        }
    """
    client = RunningHubClient("outputs")
    payload = {
        "taskId": task_id
    }

    result = await client.invoke(payload)
    if result.get("code") != 0 or result.get("msg") != "success":
        raise Exception(f"Failed to get RunningHub task {task_id} result: {result['msg']}")

    return result
