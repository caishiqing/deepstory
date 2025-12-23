"""
流式叙事引擎（生产者）

后端流式生成引擎，将故事内容和资源生成解耦。

核心设计：
1. 事件即时 yield（不等待资源生成）
2. 资源后台并发生成
3. 每个事件携带资源引用（resource_key），消费者可按需等待
4. 支持断点恢复（通过 Redis 持久化）
"""

import xml.etree.ElementTree as ET
from loguru import logger
from lxml import etree
import asyncio
import pinyin
import uuid
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, AsyncIterator, Union

from tasks import get_task_manager, TaskManager
from .tracer import ResourceTracker
from endpoints import dify, mediahub
import normalize
import utils
from cache import Cache
from .models import SceneInfo, CharacterInfo, StoryInfo, ChapterInfo


# ==================== 事件定义 ====================

@dataclass
class NarrativeEvent:
    """叙事事件基类"""
    event_id: str
    event_type: str

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type
        }


@dataclass
class StoryStartEvent(NarrativeEvent):
    """故事开始事件"""
    event_type: str = "story_start"
    title: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "title": self.title}


@dataclass
class ChapterStartEvent(NarrativeEvent):
    """章节开始事件"""
    event_type: str = "chapter_start"
    chapter_index: int = 0
    title: str = ""

    def to_dict(self) -> dict:
        return {**super().to_dict(), "chapter_index": self.chapter_index, "title": self.title}


@dataclass
class SceneStartEvent(NarrativeEvent):
    """场景开始事件"""
    event_type: str = "scene_start"
    scene_index: str = ""
    title: str = ""
    location: str = ""
    time: str = ""
    bg_id: str = ""

    # 资源 key（由 Consumer 等待就绪后获取 URL）
    background_key: Optional[str] = None
    music_key: Optional[str] = None
    ambient_key: Optional[str] = None

    # 音乐/音效描述（前端可用于显示）
    music_desc: Optional[str] = None
    ambient_desc: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "scene_index": self.scene_index,
            "title": self.title,
            "location": self.location,
            "time": self.time,
            "bg_id": self.bg_id,
            "background_key": self.background_key,
            "music_key": self.music_key,
            "ambient_key": self.ambient_key,
            "music_desc": self.music_desc,
            "ambient_desc": self.ambient_desc
        }


@dataclass
class DialogueEvent(NarrativeEvent):
    """对话事件"""
    event_type: str = "dialogue"
    character: str = ""
    character_tag: str = ""
    text: str = ""
    emotion: str = "normal"
    is_monologue: bool = False

    # 资源 key（由 Consumer 等待就绪后获取 URL）
    voice_key: Optional[str] = None
    image_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "character": self.character,
            "character_tag": self.character_tag,
            "text": self.text,
            "emotion": self.emotion,
            "is_monologue": self.is_monologue,
            "voice_key": self.voice_key,
            "image_key": self.image_key
        }


@dataclass
class NarrationEvent(NarrativeEvent):
    """旁白/动作事件"""
    event_type: str = "narration"
    text: str = ""

    # 资源 key（可选，有旁白配音时）
    voice_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "text": self.text,
            "voice_key": self.voice_key
        }


@dataclass
class SoundEvent(NarrativeEvent):
    """音效事件"""
    event_type: str = "sound"
    description: str = ""

    # 资源 key
    sound_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            **super().to_dict(),
            "description": self.description,
            "sound_key": self.sound_key
        }


@dataclass
class StoryEndEvent(NarrativeEvent):
    """故事结束事件"""
    event_type: str = "story_end"

    def to_dict(self) -> dict:
        return super().to_dict()


# ==================== 流式叙事引擎 ====================

class StoryEngine:
    """流式叙事引擎

    核心功能：
    1. 故事脚本预生成（plan_story）
    2. 场景绘图和角色立绘（提前生成）
    3. 分场剧本推理（流式）
    4. 事件流式输出（每个事件包含资源引用）

    使用方式：
        engine = StoryEngine(story_input, request_id="xxx")
        await engine.initialize()

        async for event in engine.run():
            # event 是 NarrativeEvent 子类
            # 可以立即处理事件，资源通过 engine.tracker.get(key) 等待
            print(event.to_dict())

            if event.voice_key:
                voice_result = await engine.tracker.get(event.voice_key)
    """

    def __init__(self,
                 story_input: dict,
                 request_id: str = None,
                 narration_voice: str = None,
                 default_age: str = "青年",
                 default_gender: str = "male",
                 default_voice: str = "清脆明亮的声音",
                 cache_ttl: int = 86400):
        """
        Args:
            story_input: 故事输入（包含 logline, roles, tags）
            request_id: 请求 ID（用于缓存隔离）
            narration_voice: 旁白音色 ID
            default_age: 默认年龄段
            default_gender: 默认性别
            default_voice: 默认音色描述
            cache_ttl: 缓存过期时间（秒），默认 86400（24小时）
        """
        self.request_id = request_id or str(uuid.uuid4())
        self.cache_ttl = cache_ttl
        self.narration_voice = narration_voice
        self.default_age = default_age
        self.default_gender = default_gender
        self.default_voice = default_voice

        # XML 解析器
        self.xml_parser = utils.XMLParser()

        # 角色和场景信息
        self.characters: Dict[str, dict] = {}
        self.scenes: Dict[str, dict] = {}
        self.voices: Dict[str, str] = {}  # voice_key -> voice_id 缓存

        # 故事内容
        self.title = None
        self.think = ""
        self.script = ""

        # 故事输入
        self.logline = story_input.get("logline")
        self.roles = utils.format_roles(story_input.get("roles"))
        self.tags = utils.format_tags(story_input.get("tags"))

        # 预加载角色
        for role in story_input.get("roles", []):
            self.characters.setdefault(role["name"], role)

        # 任务管理和资源追踪
        self.task_manager: Optional[TaskManager] = None
        self.tracker: Optional[ResourceTracker] = None

        # 缓存
        self.cache = Cache()

        # Dify 客户端
        self.session_id = self.cache.get(self._redis_key("session"))
        self.script_generator = dify.script_client(session_id=self.session_id)

        # 预加载缓存
        cached_think = self.cache.get(self._redis_key("think"), default="")
        cached_script = self.cache.get(self._redis_key("script"), default="")
        if cached_think:
            self.think = cached_think
        if cached_script:
            self.script = cached_script

        # 从 Redis 加载持久化数据
        self._load_persisted_data()

    def _redis_key(self, field: str) -> str:
        """生成 Redis 键"""
        return f"story:{self.request_id}:{field}"

    def _load_persisted_data(self):
        """从 Redis 加载持久化的角色/场景/音色数据"""
        # 加载角色信息
        cached_characters = self.cache.get(self._redis_key("characters"), default=None)
        if cached_characters and isinstance(cached_characters, dict):
            # 合并而不是覆盖（保留 story_input 中的角色基础信息）
            for name, data in cached_characters.items():
                self.characters.setdefault(name, {}).update(data)
            logger.debug(f"Loaded {len(cached_characters)} characters from cache")

        # 加载场景信息
        cached_scenes = self.cache.get(self._redis_key("scenes"), default=None)
        if cached_scenes and isinstance(cached_scenes, dict):
            self.scenes.update(cached_scenes)
            logger.debug(f"Loaded {len(cached_scenes)} scenes from cache")

        # 加载音色 ID 缓存
        cached_voices = self.cache.get(self._redis_key("voices"), default=None)
        if cached_voices and isinstance(cached_voices, dict):
            self.voices.update(cached_voices)
            logger.debug(f"Loaded {len(cached_voices)} voice mappings from cache")

    def _save_characters(self):
        """保存角色信息到 Redis"""
        self.cache.set(self._redis_key("characters"), self.characters, ttl=self.cache_ttl)

    def _save_scenes(self):
        """保存场景信息到 Redis"""
        self.cache.set(self._redis_key("scenes"), self.scenes, ttl=self.cache_ttl)

    def _save_voices(self):
        """保存音色 ID 缓存到 Redis"""
        self.cache.set(self._redis_key("voices"), self.voices, ttl=self.cache_ttl)

    def _voice_resource_key(self, name: str, age: str) -> str:
        """生成音色资源键"""
        return f"voice_{self.request_id}_{name}_{age}"

    def _character_tag(self, name: str, age: str = None) -> str:
        """生成角色标签（Ren'Py 兼容）"""
        if age:
            return normalize.normalize_name(name) + " " + pinyin.get(age, format="strip")
        return normalize.normalize_name(name)

    @property
    def story_prompt(self) -> str:
        """获取完整的故事提示词"""
        if not self.logline or not self.roles or not self.tags or not self.think:
            raise Exception("Story is not complete")

        return utils.format_story(
            self.logline, self.roles, self.tags,
            think=self.think, script=self.script
        )

    async def initialize(self):
        """初始化引擎（获取 TaskManager，启动资源追踪）"""
        self.task_manager = await get_task_manager()
        self.tracker = ResourceTracker(
            self.task_manager,
            request_id=self.request_id,
            poll_interval=1.0
        )
        await self.tracker.initialize()  # 从 Redis 恢复资源映射
        await self.tracker.start_polling()
        logger.info(f"StoryEngine initialized: request_id={self.request_id}")

    async def shutdown(self):
        """关闭引擎"""
        if self.tracker:
            await self.tracker.stop_polling()
        if self.task_manager:
            await self.task_manager.shutdown()
        logger.info("StoryEngine shutdown")

    # ==================== 资源生成方法 ====================

    async def _generate_scene_background(self, scene_info: dict) -> Optional[str]:
        """生成场景背景，返回资源 key"""
        location = scene_info.get("location")
        time = scene_info.get("time")
        bg_tag = f"{location} - {time}"

        if bg_tag in self.scenes:
            return None  # 已生成

        # 获取场景详情
        scene_details = await dify.scene_details(self.story_prompt, bg_tag)
        scene_prompt = utils.format_scene_prompt(scene_details)
        self.scenes.setdefault(bg_tag, {})["prompt"] = scene_prompt
        self.scenes[bg_tag].update(scene_details)

        # 持久化场景信息
        self._save_scenes()

        bg_id = utils.get_bg_id(location, time)
        resource_key = f"bg_{bg_id}"

        logger.info(f"Scene drawing: {location} - {time} -> {bg_id}")

        await self.tracker.submit(
            key=resource_key,
            function="tasks.scene_drawing",
            args=["bg", bg_id, scene_prompt],
            queue="image_generation"
        )

        return resource_key

    async def _generate_character_portrait(self, character_info: dict) -> Optional[str]:
        """生成角色立绘，返回资源 key"""
        name = character_info.get("name")
        age = character_info.get("age")
        voice_key = self._voice_resource_key(name, age)

        # 注册音色资源
        self.tracker.register(voice_key)

        # 检查是否已有详情
        if name in self.characters and self.characters[name].get("periods"):
            details = self.characters[name]["periods"].get(age)
            if details:
                self.tracker.set_result(voice_key, details.get("voice", self.default_voice))
                return None  # 已生成

        # 初始化角色数据
        self.characters.setdefault(name, {})
        self.characters[name].setdefault("periods", {})

        # 获取角色详情
        character = f"{name} - {age}"
        character_details = await dify.character_details(self.story_prompt, character)
        self.tracker.set_result(voice_key, character_details.get("voice", self.default_voice))

        character_prompt = utils.format_character_prompt(character_details)

        # 更新角色信息
        if character_details.get("gender") and not self.characters[name].get("gender"):
            self.characters[name]["gender"] = character_details["gender"]

        self.characters[name]["periods"][age] = {"prompt": character_prompt}
        self.characters[name]["periods"][age].update(character_details)

        # 持久化角色信息
        self._save_characters()

        # 提交立绘任务
        tag = self._character_tag(name, age)
        resource_key = f"portrait_{tag}"

        logger.info(f"Character portrait: {name} - {age}")

        await self.tracker.submit(
            key=resource_key,
            function="tasks.character_portrait",
            args=[tag, character_prompt],
            queue="image_generation"
        )

        return resource_key

    async def _get_voice_id(self, name: str, age: str, gender: str) -> str:
        """获取角色音色 ID"""
        # 只有脚本范围内的角色才等待获取音色描述
        # 超出脚本范围的角色直接使用默认音色描述
        if name in self.characters:
            voice_key = self._voice_resource_key(name, age)
            voice_desc = await self.tracker.get(voice_key, timeout=600, default=self.default_voice)
        else:
            voice_desc = self.default_voice

        # 查找或匹配音色
        cache_key = f"{voice_desc}-{gender}-{age}"
        if cache_key in self.voices:
            return self.voices[cache_key]

        results = await mediahub.search_voice(voice_desc, gender=gender, age=age)
        if not results and (gender or age):
            results = await mediahub.search_voice(voice_desc)

        if not results:
            raise Exception(f"Cannot find voice for {voice_desc} - {gender} - {age}")

        # 音色去重
        for result in results:
            voice_id = result["voice_id"]
            if voice_id not in self.voices.values():
                self.voices[cache_key] = voice_id
                # 持久化音色 ID 缓存
                self._save_voices()
                return voice_id

        return results[0]["voice_id"]

    # ==================== 故事生成流程 ====================

    async def _infer_story(self):
        """推理生成故事脚本（think + script）- 预处理阶段"""
        # 检查缓存
        if self.think and self.script:
            logger.info("Using cached story script")
            return

        async for chunk in dify.plan_story(self.logline, self.roles, self.tags):
            if chunk.get("type") == "think":
                self.think = chunk.get("content")
                self.cache.set(self._redis_key("think"), self.think, ttl=self.cache_ttl)

            elif chunk.get("type") == "output":
                for event in self.xml_parser.stream(chunk.get("content")):
                    if event["event"] == "start" and event["tag"] == "story":
                        self.title = event["attrib"].get("title")

                    elif event["event"] == "start" and event["tag"] == "scene":
                        # 提前生成场景背景
                        await self._generate_scene_background(event["attrib"])

                    elif event["event"] == "end" and event["tag"] == "character":
                        if event["attrib"].get("name") in self.characters:
                            await self._generate_character_portrait(event["attrib"])

                    elif event["event"] == "end" and event["tag"] == "story":
                        self.script = event["xml_text"]
                        self.cache.set(self._redis_key("script"), self.script, ttl=self.cache_ttl)

                        # 为新增的辅助角色生成立绘
                        all_chars = re.findall(r'<character name="(.*?)" age="(.*?)">', event["xml_text"])
                        for char_name, char_age in all_chars:
                            if char_name not in self.characters:
                                self.characters.setdefault(char_name, {})["age"] = char_age
                                await self._generate_character_portrait({"name": char_name, "age": char_age})

    async def _process_scene(self, scene_info: SceneInfo) -> AsyncIterator[NarrativeEvent]:
        """处理单个场景，流式输出事件"""
        # 更新角色年龄
        for char in scene_info.characters:
            if char.name in self.characters:
                self.characters[char.name]["age"] = char.age

        self.xml_parser.reset()
        event_idx = 0

        try:
            async for chunk in self.script_generator.stream(
                query=scene_info.content,
                inputs={"story": self.story_prompt}
            ):
                # 记录会话 ID
                if self.session_id is None and self.script_generator.conversation_id:
                    self.session_id = self.script_generator.conversation_id
                    self.cache.set(self._redis_key("session"), self.session_id, ttl=self.cache_ttl)

                for xml_event in self.xml_parser.stream(chunk):
                    event_idx += 1
                    event_index = f"{scene_info.index}{event_idx}"

                    # 场景开始
                    if xml_event["event"] == "start" and xml_event["tag"] == "scene":
                        bg_id = utils.get_bg_id(scene_info.location, scene_info.time)
                        music = xml_event["attrib"].get("music")
                        ambient = xml_event["attrib"].get("ambient")

                        # 背景音乐
                        music_key = None
                        if music and music.lower() not in {"无", "none", "null"}:
                            music_key = f"music_{scene_info.index}"
                            await self.tracker.submit(
                                key=music_key,
                                function="tasks.sound_audio",
                                args=[music, "music"],
                                kwargs={"tag": f"m{scene_info.index}"},
                                queue="audio_processing"
                            )

                        # 环境音效
                        ambient_key = None
                        if ambient and ambient.lower() not in {"无", "none", "null"}:
                            ambient_key = f"ambient_{scene_info.index}"
                            await self.tracker.submit(
                                key=ambient_key,
                                function="tasks.sound_audio",
                                args=[ambient, "ambient"],
                                kwargs={"tag": f"a{scene_info.index}"},
                                queue="audio_processing"
                            )

                        # 立即产出事件（资源 key，不等待 URL）
                        yield SceneStartEvent(
                            event_id=f"scene_{scene_info.index}",
                            scene_index=scene_info.index,
                            title=scene_info.title,
                            location=scene_info.location,
                            time=scene_info.time,
                            bg_id=bg_id,
                            background_key=f"bg_{bg_id}",
                            music_key=music_key,
                            ambient_key=ambient_key,
                            music_desc=music,
                            ambient_desc=ambient
                        )

                    # 对话/独白
                    elif xml_event["event"] == "end" and xml_event["tag"] in ("dialogue", "monologue"):
                        char_name = xml_event["attrib"].get("character")
                        default_gender = utils.infer_gender(char_name) or self.default_gender
                        default_age = utils.infer_age(char_name) or self.default_age

                        if char_name in self.characters:
                            char_gender = self.characters[char_name].get("gender", default_gender)
                            char_age = self.characters[char_name].get("age", default_age)
                            char_age = normalize.normalize_age(char_age)
                        else:
                            char_gender = default_gender
                            char_age = default_age

                        voice_id = await self._get_voice_id(char_name, char_age, char_gender)
                        emotion = normalize.normalize_emotion(xml_event["attrib"].get("emotion", "normal"))
                        text = utils.clean_text(xml_event["text"])
                        voice_effect = "monologue" if xml_event["tag"] == "monologue" else None

                        if not text:
                            with open('logs/temp.txt', 'a') as f:
                                f.write(xml_event["xml_text"] + "\n")

                        # 提交配音任务
                        voice_key = f"voice_{event_index}"
                        await self.tracker.submit(
                            key=voice_key,
                            function="tasks.dialogue_asr",
                            args=[voice_id, text],
                            kwargs={"tag": f"d{event_index}", "emotion": emotion, "voice_effect": voice_effect},
                            queue="audio_processing"
                        )

                        # 立即产出事件（资源 key，不等待 URL）
                        image_key = f"portrait_{self._character_tag(char_name, char_age)}"
                        yield DialogueEvent(
                            event_id=f"dialogue_{event_index}",
                            character=char_name,
                            character_tag=self._character_tag(char_name, char_age),
                            text=text,
                            emotion=emotion,
                            is_monologue=(xml_event["tag"] == "monologue"),
                            voice_key=voice_key,
                            image_key=image_key
                        )

                    # 音效
                    elif xml_event["event"] == "end" and xml_event["tag"] == "sound":
                        desc = utils.clean_sound_description(xml_event["text"])
                        sound_key = f"sound_{event_index}"

                        await self.tracker.submit(
                            key=sound_key,
                            function="tasks.sound_audio",
                            args=[desc, "action"],
                            kwargs={"tag": f"s{event_index}"},
                            queue="audio_processing"
                        )

                        # 立即产出事件（资源 key，不等待 URL）
                        yield SoundEvent(
                            event_id=f"sound_{event_index}",
                            description=desc,
                            sound_key=sound_key
                        )

                    # 旁白/动作
                    elif xml_event["event"] == "end" and xml_event["tag"] in ("action", "narration"):
                        text = utils.clean_text(xml_event["text"])
                        voice_key = None

                        if not text:
                            with open('logs/temp.txt', 'a') as f:
                                f.write(xml_event["xml_text"] + "\n")

                        if self.narration_voice:
                            voice_key = f"narration_{event_index}"
                            await self.tracker.submit(
                                key=voice_key,
                                function="tasks.dialogue_asr",
                                args=[self.narration_voice, text],
                                kwargs={"tag": f"n{event_index}", "emotion": "normal"},
                                queue="audio_processing"
                            )

                        # 立即产出事件（资源 key，不等待 URL）
                        yield NarrationEvent(
                            event_id=f"narration_{event_index}",
                            text=text,
                            voice_key=voice_key
                        )

        except etree.XMLSyntaxError as e:
            logger.warning(f"XML parse error in scene {scene_info.index}: {e}")

    async def run(self) -> AsyncIterator[NarrativeEvent]:
        """运行引擎，流式输出事件"""
        # 1. 生成故事脚本（预生成场景和角色）
        await self._infer_story()

        # 2. 将场景推入队列
        await self._enqueue_scenes()

        # 3. 输出故事开始事件
        yield StoryStartEvent(
            event_id="story_start",
            title=self.title or "故事开始"
        )

        # 4. 从队列处理场景
        while self.cache.queue_len(self._redis_key("storylets")) > 0:
            scene_data = self.cache.pop(self._redis_key("storylets"))

            if scene_data["tag"] == "story":
                continue

            elif scene_data["tag"] == "sequence":
                yield ChapterStartEvent(
                    event_id=f"chapter_{scene_data['idx']}",
                    chapter_index=scene_data["idx"],
                    title=scene_data["title"]
                )

            elif scene_data["tag"] == "scene":
                scene_info = SceneInfo.from_dict(scene_data)
                logger.info(f"Processing scene: {scene_info.title} ({scene_info.index})")

                async for event in self._process_scene(scene_info):
                    yield event

        # 5. 输出故事结束事件
        yield StoryEndEvent(event_id="story_end")

    async def _enqueue_scenes(self):
        """将场景推入 Redis 队列"""
        if not self.script:
            return

        # 检查队列是否已有数据
        if self.cache.queue_len(self._redis_key("storylets")) > 0:
            return

        story = ET.fromstring(self.script)
        story_info = StoryInfo(title=story.get("title"))
        self.cache.push(self._redis_key("storylets"), story_info.to_dict(), ttl=self.cache_ttl)

        for seq_idx, sequence in enumerate(story.findall('sequence'), 1):
            chapter_info = ChapterInfo(idx=seq_idx, title=sequence.get("title"))
            self.cache.push(self._redis_key("storylets"), chapter_info.to_dict(), ttl=self.cache_ttl)

            for scene_idx, scene in enumerate(sequence.findall('scene'), 1):
                characters = [
                    CharacterInfo(name=c.get("name"), age=c.get("age"))
                    for c in scene.findall("character")
                ]

                scene_info = SceneInfo(
                    index=f"{seq_idx}{scene_idx}",
                    title=scene.get("title"),
                    location=scene.get("location"),
                    time=scene.get("time"),
                    content=ET.tostring(scene, encoding="utf8", xml_declaration=False).decode(),
                    characters=characters
                )
                self.cache.push(self._redis_key("storylets"), scene_info.to_dict(), ttl=self.cache_ttl)

    # ==================== 工具方法 ====================

    async def wait_all_resources(self, timeout: float = 3600.0):
        """等待所有资源生成完成"""
        logger.info(f"Waiting for all resources ({self.tracker.pending_count} pending)...")

        start_time = asyncio.get_event_loop().time()
        while self.tracker.pending_count > 0:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning(f"Timeout: {self.tracker.pending_count} resources still pending")
                break

            await asyncio.sleep(2.0)
            if int(elapsed) % 30 == 0 and elapsed > 0:
                logger.info(f"Progress: {self.tracker.pending_count} pending, {elapsed:.0f}s elapsed")

        logger.info("All resources completed")

    def get_stats(self) -> dict:
        """获取引擎统计信息"""
        return {
            "request_id": self.request_id,
            "title": self.title,
            "characters_count": len(self.characters),
            "scenes_count": len(self.scenes),
            "pending_resources": self.tracker.pending_count if self.tracker else 0,
            "total_resources": self.tracker.total_count if self.tracker else 0
        }
