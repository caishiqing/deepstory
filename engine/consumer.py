"""
消费适配层

处理资源等待和下载，用于离线项目生成。
事件包含资源 key，Consumer 负责等待资源就绪并下载。

继承结构：
1. StreamingConsumer - 基类，等待资源 URL 就绪
2. OfflineConsumer - 继承 StreamingConsumer，添加下载功能
3. RenpyConsumer - 继承 OfflineConsumer，添加脚本生成（占位符替换）
"""

import asyncio
import base64
import hashlib
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Set, TYPE_CHECKING, AsyncIterator
from loguru import logger

from utils import download_file

if TYPE_CHECKING:
    from .tracer import ResourceTracker
    from .producer import NarrativeEvent


# ==================== 工具函数 ====================

def short_hash(s: str, length: int = 6) -> str:
    """生成短 hash（base36：数字+小写字母）"""
    h = hashlib.md5(s.encode()).hexdigest()
    n = int(h, 16)
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = ""
    while n > 0 and len(result) < length:
        result = chars[n % 36] + result
        n //= 36
    return result.zfill(length)


# ==================== 数据类 ====================

@dataclass
class DownloadTask:
    """待下载任务"""
    key: str
    resource_type: str
    tag: str
    attribute: Optional[str] = None
    timeout: float = 6000.0


# ==================== 流式消费者（基类） ====================

class StreamingConsumer:
    """SSE 流式消费者 - 等待资源 URL 就绪后顺序推送

    特点：
    - 顺序推送叙事事件（保证故事顺序）
    - 每个事件等待其资源 URL 就绪后再 yield
    - 不影响生产任务并发（任务早已提交到后台队列）
    - 不下载资源，只返回 URL（客户端自己加载）

    使用方式（SSE 服务）：
        consumer = StreamingConsumer(engine.tracker, resource_timeout=3600.0)
        async for event in consumer.stream(engine):
            # event 已包含资源 URL
            yield event.to_dict()
    """

    def __init__(self, tracker: "ResourceTracker", resource_timeout: float = 3600.0):
        """
        Args:
            tracker: 资源追踪器
            resource_timeout: 资源等待超时时间（秒），默认 3600（1小时）
        """
        self.tracker = tracker
        self.resource_timeout = resource_timeout
        # URL 缓存: key -> url
        self._resolved: Dict[str, str] = {}
        # 监控用：当前事件队列和状态
        self._event_queue = None
        self._current_event = {}

    async def stream(self, engine) -> "AsyncIterator[NarrativeEvent]":
        """
        流式消费 Engine 事件，等待资源就绪后输出完整事件

        特点：
        - 保持事件顺序（顺序等待资源）
        - 生产者跑在前面，确保所有资源任务能提前进入并行队列
        - 每个事件的资源就绪后才 yield
        - 输出的事件已包含资源 URL
        """
        from .producer import (
            DialogueEvent, NarrationEvent, AudioEvent, SceneStartEvent
        )

        # 引入异步队列，让 Producer 不受 Consumer 等待的影响
        queue = asyncio.Queue(maxsize=1000)
        self._event_queue = queue  # 暴露队列供监控使用

        async def _producer():
            """后台生产者：尽可能快地驱动引擎，把任务塞进 Redis"""
            try:
                async for event in engine.run():
                    await queue.put(event)
                await queue.put(None)  # 结束标志
            except Exception as e:
                logger.error(f"Producer error: {e}")
                await queue.put(e)

        # 启动后台任务
        producer_task = asyncio.create_task(_producer())

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                if isinstance(event, Exception):
                    raise event

                # 记录当前处理的事件（供监控使用）
                self._current_event = {'type': event.event_type, 'waiting_for': ''}

                # 等待当前事件的所有资源就绪并填充 URL
                if isinstance(event, DialogueEvent):
                    # 等待配音
                    if event.voice_key:
                        self._current_event['waiting_for'] = 'voice'
                        result = await self.tracker.get(event.voice_key, timeout=self.resource_timeout)
                        if result:
                            event.voice_url = self._extract_url(result)
                            # 提取时长（从 AudioResourceResult）
                            from tasks.models import AudioResourceResult
                            if isinstance(result, AudioResourceResult):
                                event.voice_duration = result.duration
                            elif isinstance(result, dict):
                                event.voice_duration = result.get("duration") or result.get("audio_length")
                        else:
                            logger.warning(f"No result for voice_key: {event.voice_key}")

                    # 等待立绘（根据情绪提取特定 URL）
                    if event.image_key:
                        self._current_event['waiting_for'] = 'image'
                        result = await self.tracker.get(event.image_key, timeout=self.resource_timeout)
                        if result:
                            # ✅ 根据对话的情绪提取对应的立绘 URL
                            event.image_url = self._extract_url(result, emotion=event.emotion)
                            # 保存完整结果到额外字段，供下载使用
                            event._portrait_result = result
                            event._image_result = result  # 保持向后兼容
                        else:
                            logger.warning(f"No result for image_key: {event.image_key}")

                elif isinstance(event, NarrationEvent):
                    if event.voice_key:
                        self._current_event['waiting_for'] = 'narration_voice'
                        result = await self.tracker.get(event.voice_key, timeout=self.resource_timeout)
                        if result:
                            event.voice_url = self._extract_url(result)
                            # 提取时长（从 AudioResourceResult）
                            from tasks.models import AudioResourceResult
                            if isinstance(result, AudioResourceResult):
                                event.voice_duration = result.duration
                            elif isinstance(result, dict):
                                event.voice_duration = result.get("duration") or result.get("audio_length")
                        else:
                            logger.warning(f"No result for voice_key: {event.voice_key}")

                elif isinstance(event, AudioEvent):
                    if event.audio_key:
                        self._current_event['waiting_for'] = 'audio'
                        event.audio_url = await self.resolve_url(event.audio_key, timeout=self.resource_timeout)

                elif isinstance(event, SceneStartEvent):
                    if event.background_key:
                        self._current_event['waiting_for'] = 'background'
                        event.background_url = await self.resolve_url(event.background_key, timeout=self.resource_timeout)

                # 清除等待状态
                self._current_event = {}

                # 输出完整事件
                yield event
        finally:
            # 确保任务被清理
            if not producer_task.done():
                producer_task.cancel()

    async def resolve_url(self, key: str, timeout: float = None) -> Optional[str]:
        """等待资源就绪并返回 URL

        Args:
            key: 资源 key
            timeout: 超时时间（秒），None 则使用实例默认值
        """
        if not key:
            return None

        # 检查缓存
        if key in self._resolved:
            return self._resolved[key]

        # 使用传入的 timeout 或实例默认值
        if timeout is None:
            timeout = self.resource_timeout

        try:
            result = await self.tracker.get(key, timeout=timeout)
            if result is None:
                logger.warning(f"Resource not ready: {key}")
                return None

            url = self._extract_url(result)
            if url:
                self._resolved[key] = url
            return url

        except Exception as e:
            logger.error(f"Failed to resolve URL for {key}: {e}")
            return None

    def _extract_url(self, result: Any, emotion: str = None) -> Optional[str]:
        """从资源结果中提取单个 URL

        Args:
            result: ResourceResult 对象或兼容格式
            emotion: 如果是 PortraitResourceResult，指定要提取的情绪

        Returns:
            URL 或 None
        """
        if result is None:
            return None

        # 导入强类型（延迟导入避免循环依赖）
        from tasks.models import AudioResourceResult, ImageResourceResult, PortraitResourceResult, ResourceResult

        # 处理可能的 JSON 字符串（Pydantic 序列化的副作用）
        if isinstance(result, str) and result.startswith("{"):
            try:
                import json
                result_dict = json.loads(result)
                # 根据 resource_type 重构为对应的类
                resource_type = result_dict.get("resource_type")
                if resource_type == "portrait":
                    result = PortraitResourceResult(**result_dict)
                elif resource_type == "audio":
                    result = AudioResourceResult(**result_dict)
                elif resource_type == "image":
                    result = ImageResourceResult(**result_dict)
                else:
                    result = ResourceResult(**result_dict)
            except Exception as e:
                logger.warning(f"Failed to parse JSON string to ResourceResult: {e}")

        # PortraitResourceResult：根据情绪提取
        if isinstance(result, PortraitResourceResult):
            if emotion:
                return result.get_emotion_url(emotion, fallback=True)
            return result.primary_url

        # 其他 ResourceResult：使用 primary_url
        if isinstance(result, ResourceResult):
            return result.primary_url

        # 字典格式
        if isinstance(result, dict):
            url_map = result.get("url_map", {})
            if url_map:
                if emotion and emotion in url_map:
                    return url_map[emotion]
                # 回退到 default
                if "default" in url_map:
                    return url_map["default"]
                # 使用任意可用 URL
                return next(iter(url_map.values()), None)
            return None

        # 字符串（直接是 URL）
        if isinstance(result, str):
            return result

        logger.warning(f"Unknown result format: {type(result)}")
        return None

    def _extract_urls(self, result: Any) -> List[str]:
        """从资源结果中提取所有 URL（用于下载）"""
        if result is None:
            return []

        from tasks.models import ResourceResult, PortraitResourceResult

        # 处理可能的 JSON 字符串
        if isinstance(result, str) and result.startswith("{"):
            try:
                import json
                result_dict = json.loads(result)
                resource_type = result_dict.get("resource_type")
                if resource_type == "portrait":
                    result = PortraitResourceResult(**result_dict)
                else:
                    result = ResourceResult(**result_dict)
            except Exception as e:
                logger.warning(f"Failed to parse JSON string: {e}")

        # ResourceResult 对象
        if isinstance(result, ResourceResult):
            return result.urls or []

        # 字典格式
        if isinstance(result, dict):
            url_map = result.get("url_map", {})
            return list(url_map.values()) if url_map else []

        # 字符串（单个 URL）
        if isinstance(result, str):
            return [result]

        return []


# ==================== 离线消费者 ====================

class OfflineConsumer(StreamingConsumer):
    """离线消费者 - 等待资源就绪并下载到本地（支持并行下载）

    继承 StreamingConsumer，复用 resolve_url 和 _extract_urls 方法。

    特点：
    - 按需下载：只下载被实际使用的资源
    - 对于立绘资源：只下载被引用的情绪图像
    """

    def __init__(self, tracker: "ResourceTracker", audio_path: str, image_path: str):
        super().__init__(tracker)
        self.audio_path = audio_path
        self.image_path = image_path

        os.makedirs(audio_path, exist_ok=True)
        os.makedirs(image_path, exist_ok=True)

        # 下载缓存: key -> local_path
        self._downloaded: Dict[str, str] = {}

        # 记录被使用的情绪（用于按需下载立绘）
        # portrait_key -> Set[emotion]
        self._used_emotions: Dict[str, Set[str]] = {}

        # 并行下载相关
        self._running_tasks: Set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(10)

    async def stream(self, engine) -> "AsyncIterator[NarrativeEvent]":
        """重写流式消费，记录被使用的情绪"""
        from .producer import DialogueEvent

        async for event in super().stream(engine):
            # 记录对话事件使用的情绪（用于按需下载立绘）
            if isinstance(event, DialogueEvent) and event.image_key and event.emotion:
                if event.image_key not in self._used_emotions:
                    self._used_emotions[event.image_key] = set()
                self._used_emotions[event.image_key].add(event.emotion)
                logger.debug(f"Recorded emotion '{event.emotion}' for {event.image_key}")

            yield event

    def schedule_download(self,
                          key: str,
                          resource_type: str,
                          tag: str,
                          attribute: str = None,
                          timeout: float = 6000.0):
        """调度下载任务（非阻塞，立即在后台启动）

        Args:
            key: 资源 key
            resource_type: 资源类型 (image/audio/voice)
            tag: 资源标签前缀（用于文件命名，音频会追加 URL hash）
            attribute: 资源属性（如情绪，用于图片命名）
            timeout: 等待超时（秒）
        """
        if not key:
            return

        # 已下载，跳过
        if key in self._downloaded:
            return

        # 检查是否已在运行中（通过 task name）
        for task in self._running_tasks:
            if task.get_name() == key:
                return

        # 立即启动后台下载任务
        download_task = DownloadTask(
            key=key,
            resource_type=resource_type,
            tag=tag,
            attribute=attribute,
            timeout=timeout
        )

        async_task = asyncio.create_task(
            self._background_download_with_cleanup(download_task),
            name=key
        )
        self._running_tasks.add(async_task)
        logger.debug(f"Started background download: {key}")

    async def _background_download_with_cleanup(self, task: DownloadTask) -> Optional[str]:
        """后台下载任务（带自动清理）"""
        try:
            result = await self._background_download(task)
            return result
        finally:
            # 任务完成后，从运行中集合移除
            for running_task in list(self._running_tasks):
                if running_task.get_name() == task.key:
                    self._running_tasks.discard(running_task)
                    break

    async def _background_download(self, task: DownloadTask) -> Optional[str]:
        """后台下载任务"""
        key = task.key

        # 双重检查缓存
        if key in self._downloaded:
            return self._downloaded[key]

        try:
            # 1. 等待资源就绪（不占用信号量）
            result = await self.tracker.get(key, timeout=task.timeout)
            if result is None:
                logger.warning(f"Resource not ready: {key}")
                return None

            # 2. 提取所有 URL
            urls = self._extract_urls(result)
            if not urls:
                result_type = type(result).__name__
                if hasattr(result, 'urls'):
                    logger.warning(f"No URL in result for {key}: {result_type}, urls={result.urls}")
                else:
                    logger.warning(f"No URL in result for {key}: {result_type}, value={result}")
                return None

            # 3. 资源就绪后，获取信号量进行实际下载
            async with self._semaphore:
                return await self._do_download_urls(task, urls)

        except Exception as e:
            logger.error(f"Failed to download {key}: {e}")
            return None

    async def _do_download_urls(self, task: DownloadTask, urls: List[str]) -> Optional[str]:
        """实际执行下载（在信号量保护下调用）

        对于立绘资源：只下载被实际使用的情绪图像
        """
        key = task.key

        # 对于角色立绘（包含 portrait_），按需下载
        if "portrait_" in key:
            # 获取该立绘被使用的情绪
            used_emotions = self._used_emotions.get(key, set())

            if not used_emotions:
                logger.warning(f"No emotions recorded for portrait {key}, downloading all")
                used_emotions = {self._extract_emotion_from_url(url) for url in urls}

            first_path = None
            downloaded_count = 0

            for url in urls:
                emotion = self._extract_emotion_from_url(url)
                # ✅ 只下载被使用的情绪
                if emotion in used_emotions:
                    local_path = self._get_save_path(task.resource_type, task.tag, emotion, url)
                    await self._do_download(url, local_path)
                    downloaded_count += 1
                    if first_path is None:
                        first_path = local_path
                else:
                    logger.debug(f"Skipping unused emotion '{emotion}' for {key}")

            logger.info(f"Downloaded {downloaded_count}/{len(urls)} images for {key} (used emotions: {used_emotions})")
            self._downloaded[key] = first_path
            return first_path
        else:
            # 单个 URL（非立绘）
            url = urls[0]
            local_path = self._get_save_path(task.resource_type, task.tag, task.attribute, url)
            await self._do_download(url, local_path)
            self._downloaded[key] = local_path
            return local_path

    async def wait_all_downloads(self, concurrency: int = None) -> Dict[str, str]:
        """等待所有后台下载任务完成（可选方法）

        注意：这个方法是可选的，下载任务会在后台自动完成。
        只有在需要确保所有资源都下载完成后再继续执行时才需要调用。

        Returns:
            Dict[key, local_path] 所有成功下载的资源
        """
        if not self._running_tasks:
            return self._downloaded.copy()

        total = len(self._running_tasks)
        logger.info(f"Waiting for {total} background downloads to complete...")

        # 等待所有后台任务完成
        results = await asyncio.gather(*self._running_tasks, return_exceptions=True)

        # 统计结果
        success = sum(1 for r in results if r is not None and not isinstance(r, Exception))
        failed = total - success
        logger.info(f"All downloads completed: {success} success, {failed} failed")

        # 清空任务集合
        self._running_tasks.clear()

        return self._downloaded.copy()

    def _extract_emotion_from_url(self, url: str) -> Optional[str]:
        """从 URL 中提取情绪标签

        URL 命名规则：{emotion}_xxxxx.png
        标准情绪标签：happy / sad / surprised / fearful / disgusted / angry / normal

        示例：
        - https://xxx/fearful_00007.png -> fearful
        - https://xxx/happy_abc123.png -> happy
        """
        if not url:
            return None

        try:
            filename = url.split("/")[-1].split("?")[0]  # 提取文件名
            name_without_ext = filename.rsplit(".", 1)[0]  # 去除扩展名

            # ✅ 直接从 URL 前缀提取情绪标签（第一个下划线前的部分）
            parts = name_without_ext.split("_")
            if len(parts) > 1 and parts[0]:
                return parts[0].lower()

            # 如果没有下划线，整个文件名就是情绪标签
            return name_without_ext.lower() if name_without_ext else None

        except Exception as e:
            logger.warning(f"Failed to extract emotion from URL {url}: {e}")
            return None

    def _get_save_path(self, resource_type: str, tag: str, attribute: str, url: str) -> str:
        """根据资源类型确定保存路径

        音频文件：使用 tag + URL hash 作为文件名（无下划线）
        图片文件：使用 tag + attribute 作为文件名
        """
        # 从 URL 获取扩展名
        if url.startswith("data:"):
            ext = "mp3"
        else:
            ext = url.split(".")[-1].split("?")[0]
            if len(ext) > 5:
                ext = "png" if resource_type == "image" else "mp3"

        # 根据资源类型选择目录和文件名
        if resource_type in ("voice", "audio"):
            directory = self.audio_path
            # 音频：tag + URL hash（无下划线）
            url_hash = short_hash(url)
            filename = f"{tag}{url_hash}.{ext}"
        else:
            directory = self.image_path
            # 图片：tag + attribute
            if attribute:
                filename = f"{tag} {attribute}.{ext}"
            else:
                filename = f"{tag}.{ext}"

        return os.path.join(directory, filename)

    async def _do_download(self, url: str, local_path: str):
        """执行下载"""
        # 检查目标文件是否已存在，存在则跳过下载
        if os.path.exists(local_path):
            logger.debug(f"File already exists, skip download: {local_path}")
            return

        if url.startswith("data:"):
            # Base64 data URI
            header, data = url.split(",", 1)
            audio_bytes = base64.b64decode(data)
            with open(local_path, "wb") as f:
                f.write(audio_bytes)
            logger.debug(f"Saved data URI: {local_path}")
        else:
            # HTTP URL
            await download_file(url, local_path)
            logger.debug(f"Downloaded: {local_path}")

    @property
    def downloaded_count(self) -> int:
        """已下载的资源数"""
        return len(self._downloaded)

    @property
    def downloading_count(self) -> int:
        """正在下载的资源数"""
        return len(self._running_tasks)

    def get_local_path(self, key: str) -> Optional[str]:
        """获取资源的本地路径"""
        return self._downloaded.get(key)

    def get_filename(self, key: str) -> Optional[str]:
        """获取资源的文件名（不含扩展名）"""
        local_path = self._downloaded.get(key)
        if local_path:
            return os.path.basename(local_path).rsplit(".", 1)[0]
        return None


# ==================== Ren'Py 消费者 ====================

class RenpyConsumer(OfflineConsumer):
    """Ren'Py 项目生成消费者

    特点：
    - 使用占位符机制：事件处理时写入 {VOICE:key}，生成脚本时替换为实际文件名
    - 音频文件名使用 URL hash，确保相同 URL 生成相同文件名
    """

    SCRIPT_TEMPLATE = """
init python:
    renpy.music.register_channel("ambient", "music", loop=True, stop_on_mute=True, tight=False)
    
label start:
    "{title}"
{script}
label ending:
    "故事结束！"
    return
"""

    def __init__(self, tracker: "ResourceTracker", project_path: str):
        audio_path = os.path.join(project_path, "audio")
        image_path = os.path.join(project_path, "images")
        super().__init__(tracker, audio_path, image_path)

        self.project_path = project_path
        self.script_lines: List[str] = []
        self.is_chapter_start = False

    async def download_and_save(
        self,
        url: str = None,
        resource_type: str = None,
        tag: str = None,
        attribute: str = None,
        key: str = None,
        result: Any = None
    ) -> Optional[str]:
        """
        同步下载并保存资源（用于顺序处理）

        Args:
            url: 资源 URL（单个，废弃，使用 result 替代）
            resource_type: 资源类型 (image/audio/voice)
            tag: 资源标签前缀
            attribute: 资源属性（如情绪）
            key: 资源 key（用于缓存）
            result: ResourceResult 对象或包含 URLs 的字典（推荐）

        Returns:
            本地文件路径，失败返回 None
        """
        # 检查是否已下载
        if key and key in self._downloaded:
            return self._downloaded[key]

        # 提取所有 URLs
        urls = []
        if result:
            urls = self._extract_urls(result)
        elif url:
            urls = [url]

        if not urls:
            return None

        try:
            # 对于角色立绘（包含 portrait_），按需下载
            if key and "portrait_" in key:
                # 获取该立绘被使用的情绪
                used_emotions = self._used_emotions.get(key, set())

                # 如果指定了 attribute（情绪），只下载该情绪
                if attribute:
                    used_emotions = {attribute}

                if not used_emotions:
                    logger.warning(f"No emotions specified for portrait {key}, downloading all")
                    used_emotions = {self._extract_emotion_from_url(u) for u in urls}

                first_path = None
                downloaded_count = 0

                for url_item in urls:
                    emotion = self._extract_emotion_from_url(url_item)
                    # ✅ 只下载被使用的情绪
                    if emotion in used_emotions:
                        local_path = self._get_save_path(resource_type, tag, emotion, url_item)
                        await self._do_download(url_item, local_path)
                        downloaded_count += 1
                        if first_path is None:
                            first_path = local_path

                logger.info(f"Downloaded {downloaded_count}/{len(urls)} images for {key} (emotions: {used_emotions})")
                # ⚠️ 只缓存成功下载的路径，避免存储 None
                if key and first_path:
                    self._downloaded[key] = first_path
                return first_path
            else:
                # 单个 URL（非立绘）
                url_item = urls[0]
                local_path = self._get_save_path(resource_type, tag, attribute, url_item)
                await self._do_download(url_item, local_path)

                if key:
                    self._downloaded[key] = local_path

                logger.debug(f"Downloaded and saved: {local_path}")
                return local_path

        except Exception as e:
            logger.error(f"Failed to download {key or url}: {e}")
            return None

    def add_chapter(self, index: int, title: str):
        """添加章节"""
        self.script_lines.append(f"\nlabel chapter_{index}:")
        self.script_lines.append(f'    "第{index}章: {title}"')
        self.is_chapter_start = True

    def add_scene(self, index: str, bg_id: str):
        """添加场景"""
        self.script_lines.append(f"\nlabel scene_{index}:")
        self.script_lines.append(f"    scene bg {bg_id}")
        if self.is_chapter_start:
            self.script_lines.append(f"    with Fade(1.0, 0, 1.0)")
            self.is_chapter_start = False
        # 默认停止音乐和环境音，后续 add_audio 会覆盖
        self.script_lines.append("    stop music")
        self.script_lines.append("    stop ambient")

    def add_dialogue(self, character: str, character_tag: str, text: str,
                     emotion: str, voice_key: str = None):
        """添加对话（使用资源 key 作为占位符）"""
        if voice_key:
            self.script_lines.append(f'    voice {{VOICE:{voice_key}}}')

        self.script_lines.append(f"    show {character_tag} {emotion}")
        self.script_lines.append(f'    "{character}" "{text}"')

        # 隐藏角色（使用基础标签）
        base_tag = character_tag.split()[0]
        self.script_lines.append(f"    hide {base_tag}")

    def add_narration(self, text: str, voice_key: str = None):
        """添加旁白（使用资源 key 作为占位符）"""
        if voice_key:
            self.script_lines.append(f'    voice {{VOICE:{voice_key}}}')
        self.script_lines.append(f'    "{text}"')

    def add_audio(self, channel: str, audio_key: str):
        """添加音频（使用资源 key 作为占位符）

        Args:
            channel: 通道类型 (music/ambient/sound)
            audio_key: 资源 key
        """
        if channel == "music":
            # 音乐中途插入，直接添加 play music
            self.script_lines.append(f'    play music {{AUDIO:{audio_key}}}')
        elif channel == "ambient":
            # 替换最后一个 stop ambient（环境音仍在场景开始时设置）
            for i in range(len(self.script_lines) - 1, -1, -1):
                if self.script_lines[i].strip() == "stop ambient":
                    self.script_lines[i] = f'    play ambient {{AUDIO:{audio_key}}}'
                    break
        elif channel == "sound":
            self.script_lines.append(f'    play audio {{AUDIO:{audio_key}}}')

    def add_ending(self):
        """添加结尾跳转"""
        self.script_lines.append("\n    jump ending")

    def generate_script(self, title: str) -> str:
        """生成完整脚本（替换占位符 + 检查资源文件）"""
        # 构建 key -> filename 映射
        key_to_filename = {}
        for key, local_path in self._downloaded.items():
            # ⚠️ 跳过下载失败或未下载的资源（local_path 可能为 None）
            if local_path is None:
                logger.warning(f"Skipping resource with None path: {key}")
                continue
            filename = os.path.basename(local_path).rsplit(".", 1)[0]
            key_to_filename[key] = filename

        # 获取已存在的音频文件
        audios = set()
        if os.path.exists(self.audio_path):
            for file in os.listdir(self.audio_path):
                audios.add(file.rsplit(".", 1)[0])

        validated_lines = []

        for line in self.script_lines:
            # 替换占位符 {VOICE:xxx} 和 {AUDIO:xxx}
            def replace_placeholder(match):
                key = match.group(1)
                return key_to_filename.get(key, f"MISSING_{key}")

            line = re.sub(r'\{(?:VOICE|AUDIO):([^}]+)\}', replace_placeholder, line)

            stripped = line.strip()

            # 检查对话音频文件是否存在
            if stripped.startswith("voice "):
                voice_tag = stripped.split()[-1]
                if voice_tag.startswith("MISSING_") or voice_tag not in audios:
                    logger.warning(f"对话音频文件不存在，跳过: {voice_tag}")
                    continue

            # 检查动作音效文件是否存在
            elif stripped.startswith("play audio "):
                audio_tag = stripped.split()[-1]
                if audio_tag.startswith("MISSING_") or audio_tag not in audios:
                    logger.warning(f"动作音效文件不存在，跳过: {audio_tag}")
                    continue

            # 检查背景音乐文件是否存在
            elif stripped.startswith("play music "):
                music_tag = stripped.split()[-1]
                if music_tag.startswith("MISSING_") or music_tag not in audios:
                    logger.warning(f"背景音乐文件不存在，替换为 stop music: {music_tag}")
                    line = line.replace(stripped, "stop music")

            # 检查环境音效文件是否存在
            elif stripped.startswith("play ambient "):
                ambient_tag = stripped.split()[-1]
                if ambient_tag.startswith("MISSING_") or ambient_tag not in audios:
                    logger.warning(f"环境音效文件不存在，替换为 stop ambient: {ambient_tag}")
                    line = line.replace(stripped, "stop ambient")

            validated_lines.append(line)

        script_content = "\n".join(validated_lines)
        return self.SCRIPT_TEMPLATE.format(title=title, script=script_content)

    def save_script(self, title: str) -> str:
        """保存脚本文件"""
        script = self.generate_script(title)
        script_path = os.path.join(self.project_path, "script.rpy")

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        logger.info(f"Script saved: {script_path}")
        return script_path
