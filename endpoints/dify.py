import aiohttp
import json
import dotenv
import os
from utils import async_retry, clean_xml, format_characters, format_tags
from typing import Optional, Union, Dict, Any, AsyncGenerator, List
from engine.models import StoryInput
import xml.etree.ElementTree as ET
from xml.dom import minidom

dotenv.load_dotenv()


class DifyClient:
    """Dify API 基础客户端 - 提供底层 HTTP 调用能力"""

    def __init__(self, api_key: str = None, base_url: str = None, user: str = "story"):
        """
        初始化 Dify 客户端

        Args:
            api_key: Dify API Key，如果不提供则从环境变量 DIFY_API_KEY 读取
            base_url: Dify API Base URL，如果不提供则从环境变量 DIFY_BASE_URL 读取，默认为官方地址
            user: 用户标识，默认为 "story"
        """
        self.api_key = api_key or os.getenv("DIFY_API_KEY")
        self.base_url = base_url or os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1")
        self.user = user
        self.task_id = None

    @property
    def headers(self):
        """HTTP 请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def invoke_stream(
        self,
        endpoint: str,
        payload: dict,
        timeout: int = 6000
    ) -> AsyncGenerator[dict, None]:
        """
        流式调用 Dify API

        Args:
            endpoint: API 端点路径
            payload: 请求负载
            timeout: 超时时间（秒）

        Yields:
            dict: 流式响应的每个数据块
        """
        if not self.api_key:
            raise Exception("DIFY_API_KEY environment variable is not set")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/{endpoint}",
                json=payload,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    async for line in response.content:
                        if line:
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]  # 去掉 'data: ' 前缀
                                if data_str and data_str != '[DONE]':
                                    try:
                                        chunk = json.loads(data_str)
                                        # 自动捕获并缓存 task_id
                                        if chunk.get("task_id") and not self.task_id:
                                            self.task_id = chunk["task_id"]
                                        yield chunk
                                    except json.JSONDecodeError:
                                        continue
                else:
                    try:
                        error_data = await response.json()
                        raise Exception(f"Dify API Error: {error_data}")
                    except Exception:
                        text = await response.text()
                        raise Exception(f"HTTP {response.status}: {text}")

    async def invoke_blocking(self, endpoint: str, payload: dict, timeout: int = 6000) -> dict:
        """
        非流式调用 Dify API

        Args:
            endpoint: API 端点路径
            payload: 请求负载
            timeout: 超时时间（秒）

        Returns:
            dict: 完整的响应数据
        """
        if not self.api_key:
            raise Exception("DIFY_API_KEY environment variable is not set")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/{endpoint}",
                json=payload,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    try:
                        error_data = await response.json()
                        raise Exception(f"Dify API Error: {error_data}")
                    except Exception:
                        text = await response.text()
                        raise Exception(f"HTTP {response.status}: {text}")


class ChatflowClient(DifyClient):
    """Dify Chatflow 客户端 - 处理对话流"""

    def __init__(self,
                 api_key: str = None,
                 base_url: str = None,
                 user: str = "story",
                 conversation_id: str = None):
        """
        初始化 Chatflow 客户端

        Args:
            api_key: Dify API Key
            base_url: Dify API Base URL
            user: 用户标识
        """
        super().__init__(api_key, base_url, user)
        self.conversation_id = conversation_id

    async def stop(self):
        """
        停止当前正在运行的流式响应

        Returns:
            bool: 停止成功返回 True，否则返回 False

        Note:
            需要先有 task_id（通过流式响应获取）才能停止
        """
        if not self.task_id:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat-messages/{self.task_id}/stop",
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result") == "success"
                    return False
        except Exception:
            return False
        finally:
            self.task_id = None  # 清空 task_id

    async def stream(self,
                     query: str,
                     inputs: Optional[Dict[str, Any]] = None,
                     files: Optional[list] = None,
                     timeout: int = 6000):
        """
        流式运行 Chatflow

        Args:
            query: 用户输入/问题内容
            inputs: 输入参数，key-value 格式（可选）
            files: 上传的文件列表（可选）
            timeout: 超时时间（秒）

        Yields:
            str: 逐块返回的文本内容

        Note:
            - conversation_id 由客户端内部维护，首次为空，后续自动使用
            - 支持安全退出：异常时自动发送停止请求

        Example:
            client = ChatflowClient()
            async for chunk in client.stream(query="你好"):
                print(chunk, end="", flush=True)
        """
        payload = {
            "query": query,
            "user": self.user,
            "response_mode": "streaming"
        }

        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        if inputs:
            payload["inputs"] = inputs

        if files:
            payload["files"] = files

        try:
            async for chunk in self.invoke_stream("chat-messages", payload, timeout):
                # 自动更新 conversation_id
                if chunk.get("conversation_id"):
                    self.conversation_id = chunk["conversation_id"]
                # 只返回消息内容
                if chunk.get("event") == "message":
                    yield chunk.get("answer", "")
        except KeyboardInterrupt:
            # 用户手动中断（Ctrl+C）
            await self.stop()
            raise
        except GeneratorExit:
            # 生成器被关闭（如主动 break 等）
            await self.stop()
            raise
        except Exception:
            # 其他异常（如网络断开等）
            await self.stop()
            raise
        finally:
            # 正常结束也清空 task_id
            self.task_id = None

    async def invoke(self,
                     query: str,
                     inputs: Optional[Dict[str, Any]] = None,
                     files: Optional[list] = None,
                     timeout: int = 6000) -> dict:
        """
        非流式运行 Chatflow

        Args:
            query: 用户输入/问题内容
            inputs: 输入参数，key-value 格式（可选）
            files: 上传的文件列表（可选）
            timeout: 超时时间（秒）

        Returns:
            dict: 完整的响应数据

        Example:
            client = ChatflowClient()
            result = await client.invoke(query="你好")
            print(result.get("answer"))
        """
        payload = {
            "query": query,
            "user": self.user,
            "response_mode": "blocking"
        }

        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        if inputs:
            payload["inputs"] = inputs

        if files:
            payload["files"] = files

        result = await self.invoke_blocking("chat-messages", payload, timeout)

        # 自动更新 conversation_id
        if result.get("conversation_id"):
            self.conversation_id = result["conversation_id"]

        return result.get("answer", "")


class WorkflowClient(DifyClient):
    """Dify Workflow 客户端 - 处理工作流"""

    def __init__(self, api_key: str = None, base_url: str = None, user: str = "story"):
        """
        初始化 Workflow 客户端

        Args:
            api_key: Dify API Key
            base_url: Dify API Base URL
            user: 用户标识
        """
        super().__init__(api_key, base_url, user)

    async def stop(self):
        """
        停止当前正在运行的流式响应

        Returns:
            bool: 停止成功返回 True，否则返回 False

        Note:
            需要先有 task_id（通过流式响应获取）才能停止
        """
        if not self.task_id:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/workflows/tasks/{self.task_id}/stop",
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result") == "success"
                    return False
        except Exception:
            return False
        finally:
            self.task_id = None  # 清空 task_id

    async def stream(self,
                     inputs: Dict[str, Any],
                     files: Optional[list] = None,
                     timeout: int = 6000):
        """
        流式运行 Workflow

        Args:
            inputs: 输入参数，key-value 格式
            files: 上传的文件列表（可选）
            timeout: 超时时间（秒）

        Yields:
            str: 流式响应的文本内容

        Note:
            - 支持安全退出：异常时自动发送停止请求

        Example:
            client = WorkflowClient()
            async for text in client.stream(inputs={"query": "你好"}):
                print(text, end="", flush=True)
        """
        payload = {
            "inputs": inputs,
            "user": self.user,
            "response_mode": "streaming"
        }

        if files:
            payload["files"] = files

        try:
            async for chunk in self.invoke_stream("workflows/run", payload, timeout):
                if chunk.get("event") == "text_chunk":
                    yield chunk["data"]["text"]
        except KeyboardInterrupt:
            # 用户手动中断（Ctrl+C）
            await self.stop()
            raise
        except GeneratorExit:
            # 生成器被关闭（如主动 break 等）
            await self.stop()
            raise
        except Exception:
            # 其他异常（如网络断开等）
            await self.stop()
            raise
        finally:
            # 正常结束也清空 task_id
            self.task_id = None

    async def invoke(self,
                     inputs: Dict[str, Any],
                     files: Optional[list] = None,
                     timeout: int = 6000) -> dict:
        """
        非流式运行 Workflow

        Args:
            inputs: 输入参数，key-value 格式
            files: 上传的文件列表（可选）
            timeout: 超时时间（秒）

        Returns:
            dict: 完整的响应数据

        Example:
            client = WorkflowClient()
            result = await client.invoke(inputs={"query": "你好"})
            print(result.get("data"))
        """
        payload = {
            "inputs": inputs,
            "user": self.user,
            "response_mode": "blocking"
        }

        if files:
            payload["files"] = files

        result = await self.invoke_blocking("workflows/run", payload, timeout)
        return result["data"]["outputs"]


def parse_json(text_or_json: Union[str, dict]) -> dict:
    if isinstance(text_or_json, dict):
        return text_or_json

    text_or_json = text_or_json.strip()
    if text_or_json.startswith("```json"):
        return json.loads(text_or_json.strip("```json"))

    return json.loads(text_or_json)


@async_retry(max_attempts=3, delay=2.0)
async def character_details(story: str, character: str):
    """
    人物画像生成

    Args:
        story: 故事脚本
        character: 角色名称

    Returns:
        dict: 人物画像数据
    """
    client = WorkflowClient(api_key=os.getenv("DIFY_PORTRAIT_API_KEY"))
    inputs = {
        "story": story,
        "character": character,
        "task": "人物画像"
    }
    result = await client.invoke(inputs)
    return parse_json(result["character"])


@async_retry(max_attempts=3, delay=2.0)
async def scene_details(story: str, scene: str):
    """
    场景画像生成

    Args:
        story: 故事脚本
        scene: 场景信息

    Returns:
        dict: 场景画像数据
    """
    client = WorkflowClient(api_key=os.getenv("DIFY_PORTRAIT_API_KEY"))
    inputs = {
        "story": story,
        "scene": scene,
        "task": "场景画像"
    }
    result = await client.invoke(inputs)
    return parse_json(result["scene"])


@async_retry(max_attempts=3, delay=2.0)
async def help_character_design(logline: str, tags: dict, character: dict):
    """辅助角色设计"""
    client = WorkflowClient(api_key=os.getenv("DIFY_CHARACTER_DESIGN_API_KEY"))
    inputs = {
        "logline": logline,
        "tags": utils.format_tags(tags),
        "description": character.pop("description"),
        "profile": utils.format_characters([character]).strip()
    }
    result = await client.invoke(inputs)
    return parse_json(result["result"])


@async_retry(max_attempts=3, delay=2.0)
async def help_create(logline: str):
    """辅助创作"""
    client = ChatflowClient(api_key=os.getenv("DIFY_HELP_CREATE_API_KEY"))
    inputs = {
        "logline": logline
    }

    # 生成角色设计
    characters = await client.invoke("根据要求输出角色设计：", inputs)
    characters = parse_json(characters)

    # 生成人物关系
    relationships = await client.invoke("根据要求输出人物关系：", inputs)
    relationships = parse_json(relationships)

    # 生成主题标签
    tags = await client.invoke("根据要求输出主题标签：", inputs)
    tags = parse_json(tags)

    results = {
        "characters": characters,
        "relationships": relationships,
        "tags": tags
    }
    return results


async def infer_story(story_input: StoryInput):
    """
    故事脚本推理 - 流式生成

    Args:
        story_input: 故事创意输入模型

    Yields:
        dict: 包含 type 和 content 的字典
            - type: "think" 或 "output"
            - content: 文本内容
    """
    # 格式化输入
    characters_list = [char.to_dict() for char in story_input.characters]
    relationships_list = [rel.to_dict() for rel in story_input.relationships] if story_input.relationships else None
    tags_dict = story_input.tags.to_dict()

    formatted_characters = format_characters(characters_list, relationships_list)
    formatted_tags = format_tags(tags_dict)

    # client = ChatflowClient(api_key=os.getenv("DIFY_STORY_API_KEY"))
    client = ChatflowClient(api_key="app-ViqtQqjelym7hCWUxHDUkzSI")
    inputs = {
        "characters": formatted_characters,
        "tags": formatted_tags
    }

    think = ""
    async for chunk in client.stream(query=story_input.logline, inputs=inputs):
        if chunk.startswith("<think>"):
            think += chunk
            continue
        elif think and not think.endswith("</think>"):
            if "</think>" in chunk:
                think += chunk[:chunk.index("</think>")] + "</think>"
                yield {"type": "think", "content": think[len("<think>"):-len("</think>")]}
                yield {"type": "output", "content": chunk.split("</think>")[-1]}
            else:
                think += chunk
                continue
        else:
            yield {"type": "output", "content": chunk}


async def plan_story(story_input: StoryInput):
    """
    故事规划生成

    Args:
        story_input: 故事创意输入模型
    """
    # 格式化输入
    characters_list = [char.to_dict() for char in story_input.characters]
    relationships_list = [rel.to_dict() for rel in story_input.relationships] if story_input.relationships else None
    tags_dict = story_input.tags.to_dict()

    formatted_characters = format_characters(characters_list, relationships_list)
    formatted_tags = format_tags(tags_dict)

    client = ChatflowClient(api_key=os.getenv("DIFY_STORY_API_KEY"))
    inputs = {
        "logline": story_input.logline,
        "characters": formatted_characters,
        "tags": formatted_tags
    }

    # 获取摘要总结
    inputs["task"] = "摘要总结"
    summary = await client.invoke(query="根据要求输出摘要总结：", inputs=inputs)

    # 获取大纲规划
    inputs["task"] = "大纲规划"
    outline = await client.invoke(query="根据要求输出大纲规划：", inputs=inputs)

    # 获取脚本设计
    inputs["task"] = "脚本设计"
    script = await client.invoke(query="根据要求输出 xml 对象：", inputs=inputs)
    script = clean_xml(script)

    yield {"type": "think", "content": "\n\n".join([summary, outline])}

    yield {"type": "output", "content": script.split("\n")[0] + "\n"}

    script_et = ET.fromstring(script)
    inputs["task"] = "场景设计"
    for seq in script_et.findall("sequence"):
        query = f"根据要求为“段落{seq.get('id')} - {seq.get('title')}”补充完整场景脚本，输出 xml 对象："
        seq_script = await client.invoke(query=query, inputs=inputs)
        seq_script = clean_xml(seq_script)
        seq_complete = ET.fromstring(seq_script)
        for scene_src, scene_tgt in zip(seq.findall("scene"), seq_complete.findall("scene")):
            scene_src.set("action", scene_tgt.get("action"))
            for character in scene_tgt.findall('character'):
                scene_src.append(character)

        # seq_script = ET.tostring(seq, encoding="utf8", xml_declaration=False).decode()
        # reparsed = minidom.parseString(seq_script)
        # pretty_string = reparsed.toprettyxml(indent="    ")
        # for line in pretty_string.split('\n')[1:]:
        #     if line.strip():
        #         yield {"type": "output", "content": "    " + line + "\n"}
        seq_script_elem = seq  # seq 已经是 ET.Element
        ET.indent(seq_script_elem, space="    ")  # 就地格式化
        seq_script = ET.tostring(seq_script_elem, encoding="unicode")

        for line in seq_script.split('\n'):
            if line.strip():
                yield {"type": "output", "content": "    " + line + "\n"}

    yield {"type": "output", "content": script.split("\n")[-1]}


def script_client(session_id: str = None):
    return ChatflowClient(api_key=os.getenv("DIFY_SCRIPT_API_KEY"), conversation_id=session_id)
