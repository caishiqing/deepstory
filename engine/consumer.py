"""
消费适配层

处理资源等待和下载，用于离线项目生成。
事件包含资源 key，Consumer 负责等待资源就绪并下载。

支持：
1. OfflineConsumer - 等待资源 + 下载到本地（支持并行下载）
2. RenpyConsumer - Ren'Py 项目生成
"""

import asyncio
import base64
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, TYPE_CHECKING
from loguru import logger

from utils import download_file

if TYPE_CHECKING:
    from .tracer import ResourceTracker


# ==================== 下载结果 ====================

@dataclass
class DownloadedResource:
    """已下载的资源"""
    url: str
    local_path: str
    resource_type: str = "unknown"


@dataclass
class DownloadTask:
    """待下载任务"""
    key: str
    resource_type: str
    tag: str
    attribute: Optional[str] = None
    timeout: float = 6000.0


# ==================== 离线消费者 ====================

class OfflineConsumer:
    """离线消费者 - 等待资源就绪并下载到本地（支持并行下载）"""

    def __init__(self, tracker: "ResourceTracker", audio_path: str, image_path: str):
        self.tracker = tracker
        self.audio_path = audio_path
        self.image_path = image_path

        os.makedirs(audio_path, exist_ok=True)
        os.makedirs(image_path, exist_ok=True)

        # 下载缓存: key -> local_path
        self._downloaded: Dict[str, str] = {}

        # 并行下载相关
        self._running_tasks: Set[asyncio.Task] = set()  # 正在执行的下载任务
        self._semaphore = asyncio.Semaphore(10)  # 控制并发下载数

    async def resolve_url(self, key: str, timeout: float = 3600.0) -> Optional[str]:
        """等待资源就绪并返回 URL（不下载）

        用于 SSE 流式推送场景，只需要 URL 不需要下载。

        Args:
            key: 资源 key
            timeout: 等待超时（秒）

        Returns:
            资源 URL，失败返回 None
        """
        if not key:
            return None

        try:
            result = await self.tracker.get(key, timeout=timeout)
            if result is None:
                logger.warning(f"Resource not ready: {key}")
                return None

            url = self._extract_url(result)
            if not url:
                logger.warning(f"No URL in result for {key}")
            return url

        except Exception as e:
            logger.error(f"Failed to resolve URL for {key}: {e}")
            return None

    def schedule_download(self,
                          key: str,
                          resource_type: str,
                          tag: str,
                          attribute: str = None,
                          timeout: float = 6000.0):
        """调度下载任务（非阻塞，立即在后台启动）

        立即启动后台协程等待资源就绪并下载，不阻塞调用者。
        使用 wait_all_downloads() 等待所有任务完成。

        Args:
            key: 资源 key
            resource_type: 资源类型 (image/audio/voice)
            tag: 资源标签（用于文件命名）
            attribute: 资源属性（如情绪）
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
            self._background_download(download_task),
            name=key
        )
        self._running_tasks.add(async_task)
        logger.debug(f"Started background download: {key}")

    async def _background_download(self, task: DownloadTask) -> Optional[str]:
        """后台下载任务

        先等待资源就绪（不占用信号量），资源就绪后再获取信号量进行实际下载。
        这样可以避免等待资源时占用信号量导致其他已就绪资源无法下载。
        """
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
        """实际执行下载（在信号量保护下调用）"""
        key = task.key

        # 对于角色立绘（portrait_），下载所有图片并按 emotion 命名
        if key.startswith("portrait_") and len(urls) > 1:
            first_path = None
            for url in urls:
                emotion = self._extract_emotion_from_url(url)
                local_path = self._get_save_path(task.resource_type, task.tag, emotion, url)
                await self._do_download(url, local_path)
                if first_path is None:
                    first_path = local_path

            logger.info(f"Downloaded {len(urls)} images for {key}")
            self._downloaded[key] = first_path
            return first_path
        else:
            # 单个 URL（非立绘或只有一张图）
            url = urls[0]
            local_path = self._get_save_path(task.resource_type, task.tag, task.attribute, url)
            await self._do_download(url, local_path)
            self._downloaded[key] = local_path
            return local_path

    async def wait_all_downloads(self, concurrency: int = None) -> Dict[str, str]:
        """等待所有后台下载任务完成

        Args:
            concurrency: 已废弃，并发由初始化时的信号量控制

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

    async def _resolve_and_download_single(self, task: DownloadTask) -> Optional[str]:
        """执行单个下载任务（内部方法）

        对于图片资源（portrait_开头），会下载所有 URL 并按 emotion 命名。
        """
        key = task.key

        # 双重检查缓存
        if key in self._downloaded:
            return self._downloaded[key]

        try:
            # 等待资源就绪
            result = await self.tracker.get(key, timeout=task.timeout)
            if result is None:
                logger.warning(f"Resource not ready: {key}")
                return None

            # 提取所有 URL
            urls = self._extract_urls(result)
            if not urls:
                # 详细记录结果类型以便调试
                result_type = type(result).__name__
                if hasattr(result, 'urls'):
                    logger.warning(f"No URL in result for {key}: {result_type}, urls={result.urls}")
                else:
                    logger.warning(f"No URL in result for {key}: {result_type}, value={result}")
                return None

            # 对于角色立绘（portrait_），下载所有图片并按 emotion 命名
            if key.startswith("portrait_") and len(urls) > 1:
                first_path = None
                for url in urls:
                    # 从 URL 提取 emotion
                    emotion = self._extract_emotion_from_url(url)
                    # 确定保存路径（emotion 作为 attribute）
                    local_path = self._get_save_path(task.resource_type, task.tag, emotion, url)
                    # 下载
                    await self._do_download(url, local_path)
                    if first_path is None:
                        first_path = local_path

                logger.info(f"Downloaded {len(urls)} images for {key}")
                self._downloaded[key] = first_path
                return first_path
            else:
                # 单个 URL（非立绘或只有一张图）
                url = urls[0]
                local_path = self._get_save_path(task.resource_type, task.tag, task.attribute, url)
                await self._do_download(url, local_path)
                self._downloaded[key] = local_path
                return local_path

        except Exception as e:
            logger.error(f"Failed to download {key}: {e}")
            return None

    async def resolve_and_download(self,
                                   key: str,
                                   resource_type: str,
                                   tag: str,
                                   attribute: str = None,
                                   timeout: float = 3600.0) -> Optional[str]:
        """等待资源就绪并下载到本地（阻塞模式）

        Args:
            key: 资源 key
            resource_type: 资源类型 (image/audio/voice)
            tag: 资源标签（用于文件命名）
            attribute: 资源属性（如情绪）
            timeout: 等待超时（秒）

        Returns:
            本地路径，失败返回 None
        """
        task = DownloadTask(
            key=key,
            resource_type=resource_type,
            tag=tag,
            attribute=attribute,
            timeout=timeout
        )
        return await self._resolve_and_download_single(task)

    def _extract_url(self, result: Any) -> Optional[str]:
        """从资源结果中提取单个 URL（兼容旧逻辑）"""
        urls = self._extract_urls(result)
        return urls[0] if urls else None

    def _extract_urls(self, result: Any) -> List[str]:
        """从资源结果中提取所有 URL"""
        if result is None:
            return []

        # ResourceResult 对象
        if hasattr(result, "urls"):
            return result.urls or []

        # 字典格式
        if isinstance(result, dict):
            return result.get("urls", [])

        # 字符串（直接是 URL）
        if isinstance(result, str):
            return [result]

        return []

    def _extract_emotion_from_url(self, url: str) -> Optional[str]:
        """从 URL 中提取 emotion 前缀

        URL 格式示例: https://xxx/happy_abc123.png -> happy
        """
        if not url:
            return None

        # 获取文件名部分
        filename = url.split("/")[-1].split("?")[0]

        # 按下划线分割，取第一部分作为 emotion
        parts = filename.split("_")
        if len(parts) > 1:
            return parts[0]

        return None

    async def download(self,
                       url: str,
                       resource_type: str,
                       tag: str,
                       attribute: str = None) -> Optional[str]:
        """直接下载 URL 资源到本地（不通过 tracker）

        Args:
            url: 资源 URL
            resource_type: 资源类型 (image/audio/voice)
            tag: 资源标签（用于文件命名）
            attribute: 资源属性（如情绪）

        Returns:
            本地路径，失败返回 None
        """
        if not url:
            return None

        # 检查缓存
        if url in self._downloaded:
            return self._downloaded[url]

        try:
            # 确定保存路径
            local_path = self._get_save_path(resource_type, tag, attribute, url)

            # 下载
            await self._do_download(url, local_path)

            self._downloaded[url] = local_path
            return local_path

        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None

    def _get_save_path(self, resource_type: str, tag: str, attribute: str, url: str) -> str:
        """根据资源类型确定保存路径"""
        # 从 URL 获取扩展名
        if url.startswith("data:"):
            ext = "mp3"  # data URI 默认 mp3
        else:
            ext = url.split(".")[-1].split("?")[0]
            if len(ext) > 5:
                ext = "png" if resource_type == "image" else "mp3"

        # 根据资源类型选择目录和文件名
        if resource_type in ("voice", "audio"):
            directory = self.audio_path
        else:  # image
            directory = self.image_path

        if attribute:
            filename = f"{tag} {attribute}.{ext}"
        else:
            filename = f"{tag}.{ext}"

        return os.path.join(directory, filename)

    async def _do_download(self, url: str, local_path: str):
        """执行下载"""
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

    def get_local_path(self, url: str) -> Optional[str]:
        """获取资源的本地路径"""
        return self._downloaded.get(url)

    def is_downloaded(self, url: str) -> bool:
        """检查资源是否已下载"""
        return url in self._downloaded


# ==================== SSE 流式消费者 ====================

class StreamingConsumer:
    """SSE 流式消费者 - 等待资源 URL 就绪后顺序推送

    特点：
    - 顺序推送叙事事件（保证故事顺序）
    - 每个事件等待其资源 URL 就绪后再 yield
    - 不影响生产任务并发（任务早已提交到后台队列）
    - 不下载资源，只返回 URL（客户端自己加载）
    """

    def __init__(self, tracker: "ResourceTracker"):
        self.tracker = tracker
        # URL 缓存: key -> url
        self._resolved: Dict[str, str] = {}

    async def resolve_url(self, key: str, timeout: float = 3600.0) -> Optional[str]:
        """等待资源就绪并返回 URL"""
        if not key:
            return None

        # 检查缓存
        if key in self._resolved:
            return self._resolved[key]

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

    def _extract_url(self, result: Any) -> Optional[str]:
        """从资源结果中提取 URL"""
        if result is None:
            return None

        if hasattr(result, "primary_url"):
            return result.primary_url

        if isinstance(result, dict):
            urls = result.get("urls", [])
            return urls[0] if urls else None

        if isinstance(result, str):
            return result

        return None


# ==================== Ren'Py 消费者 ====================

class RenpyConsumer(OfflineConsumer):
    """Ren'Py 项目生成消费者"""

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
        is_chapter_start = False

        self.project_path = project_path
        self.script_lines: List[str] = []

    def add_chapter(self, index: int, title: str):
        """添加章节"""
        self.script_lines.append(f"\nlabel chapter_{index}:")
        self.script_lines.append(f'    "第{index}章: {title}"')
        self.is_chapter_start = True

    def add_scene(self, index: str, bg_id: str, has_music: bool, has_ambient: bool):
        """添加场景"""
        self.script_lines.append(f"\nlabel scene_{index}:")
        self.script_lines.append(f"    scene bg {bg_id}")
        if self.is_chapter_start:
            self.script_lines.append(f"    with fade")
            self.is_chapter_start = False

        if has_music:
            self.script_lines.append(f'    play music m{index}')
        else:
            self.script_lines.append("    stop music")

        if has_ambient:
            self.script_lines.append(f'    play ambient a{index}')
        else:
            self.script_lines.append("    stop ambient")

    def add_dialogue(self, character: str, character_tag: str, text: str,
                     emotion: str, voice_tag: str = None):
        """添加对话"""
        if voice_tag:
            self.script_lines.append(f'    voice {voice_tag}')

        self.script_lines.append(f"    show {character_tag} {emotion}")
        self.script_lines.append(f'    "{character}" "{text}"')

        # 隐藏角色（使用基础标签）
        base_tag = character_tag.split()[0]
        self.script_lines.append(f"    hide {base_tag}")

    def add_narration(self, text: str, voice_tag: str = None):
        """添加旁白"""
        if voice_tag:
            self.script_lines.append(f'    voice {voice_tag}')
        self.script_lines.append(f'    "{text}"')

    def add_sound(self, sound_tag: str):
        """添加音效"""
        self.script_lines.append(f'    play audio {sound_tag}')

    def add_ending(self):
        """添加结尾跳转"""
        self.script_lines.append("\n    jump ending")

    def generate_script(self, title: str) -> str:
        """生成完整脚本（会检查资源文件是否存在）"""
        audios = set()
        for file in os.listdir(self.audio_path):
            audios.add(file.split(".")[0])

        validated_lines = []

        for line in self.script_lines:
            stripped = line.strip()

            # 检查对话音频文件是否存在
            if stripped.startswith("voice "):
                voice_tag = stripped.split()[-1]
                if not voice_tag in audios:
                    logger.warning(f"对话音频文件不存在，跳过: {voice_tag}")
                    continue

            # 检查动作音效文件是否存在
            elif stripped.startswith("play audio "):
                audio_tag = stripped.split()[-1]
                if not audio_tag in audios:
                    logger.warning(f"动作音效文件不存在，跳过: {audio_tag}")
                    continue

            # 检查背景音乐文件是否存在
            elif stripped.startswith("play music "):
                music_tag = stripped.split()[-1]
                if not music_tag in audios:
                    logger.warning(f"背景音乐文件不存在，替换为 stop music: {music_tag}")
                    line = line.replace(stripped, "stop music")

            # 检查环境音效文件是否存在
            elif stripped.startswith("play ambient "):
                ambient_tag = stripped.split()[-1]
                if not ambient_tag in audios:
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
