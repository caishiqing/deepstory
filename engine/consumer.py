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
from typing import Dict, List, Optional, Any, Set, TYPE_CHECKING
from loguru import logger

from utils import download_file

if TYPE_CHECKING:
    from .tracer import ResourceTracker


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
        """从资源结果中提取单个 URL"""
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


# ==================== 离线消费者 ====================

class OfflineConsumer(StreamingConsumer):
    """离线消费者 - 等待资源就绪并下载到本地（支持并行下载）

    继承 StreamingConsumer，复用 resolve_url 和 _extract_urls 方法。
    """

    def __init__(self, tracker: "ResourceTracker", audio_path: str, image_path: str):
        super().__init__(tracker)
        self.audio_path = audio_path
        self.image_path = image_path

        os.makedirs(audio_path, exist_ok=True)
        os.makedirs(image_path, exist_ok=True)

        # 下载缓存: key -> local_path
        self._downloaded: Dict[str, str] = {}

        # 并行下载相关
        self._running_tasks: Set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(10)

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
            self._background_download(download_task),
            name=key
        )
        self._running_tasks.add(async_task)
        logger.debug(f"Started background download: {key}")

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
        """实际执行下载（在信号量保护下调用）"""
        key = task.key

        # 对于角色立绘（包含 portrait_），下载所有图片并按 emotion 命名
        if "portrait_" in key:
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
            # 单个 URL（非立绘）
            url = urls[0]
            local_path = self._get_save_path(task.resource_type, task.tag, task.attribute, url)
            await self._do_download(url, local_path)
            self._downloaded[key] = local_path
            return local_path

    async def wait_all_downloads(self, concurrency: int = None) -> Dict[str, str]:
        """等待所有后台下载任务完成

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
        """从 URL 中提取 emotion 前缀

        URL 格式示例: https://xxx/happy_abc123.png -> happy
        """
        if not url:
            return None

        filename = url.split("/")[-1].split("?")[0]
        parts = filename.split("_")
        if len(parts) > 1:
            return parts[0]

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
            # 替换最后一个 stop music
            for i in range(len(self.script_lines) - 1, -1, -1):
                if self.script_lines[i].strip() == "stop music":
                    self.script_lines[i] = f'    play music {{AUDIO:{audio_key}}}'
                    break
        elif channel == "ambient":
            # 替换最后一个 stop ambient
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
