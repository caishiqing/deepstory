import xml.etree.ElementTree as ET
from loguru import logger
from lxml import etree
import asyncio
import pinyin
import uuid
import json
import os
import re
from typing import Union, Dict, List, Optional

from tasks import get_task_manager
from tracer import ResourceTracker
from endpoints import dify, mediahub
import normalize
import utils
from cache import init_redis, Cache
from models import SceneInfo, CharacterInfo, StoryInfo, ChapterInfo


RENPY_TEMPLATE = """
init python:
    renpy.music.register_channel("ambient", "music", loop=True, stop_on_mute=True, tight=False)
    
label start:
    "{title}"
{script}
label ending:
    "故事结束！"
    return
"""


class StoryPipeline:
    def __init__(self,
                 story_input: dict,
                 project_path: str,
                 title: str = None,
                 request_id: str = None,
                 narration_voice: str = None,
                 default_age: str = "青年",
                 default_gender: str = "male",
                 default_voice: str = "清脆明亮的声音"):

        self.project_path = project_path
        self.title = title
        self.audio_path = os.path.join(self.project_path, "audio")
        self.image_path = os.path.join(self.project_path, "images")
        os.makedirs(self.audio_path, exist_ok=True)
        os.makedirs(self.image_path, exist_ok=True)

        self.narration_voice = narration_voice
        self.request_id = request_id or str(uuid.uuid4())
        self.xml_parser = utils.XMLParser()
        self.characters, self.scenes = {}, {}
        self.voices = {}

        self.default_age = default_age
        self.default_gender = default_gender
        self.default_voice = default_voice

        self.task_manager = None
        self.resource_tracker = ResourceTracker()
        self.cache = Cache()

        # 预加载缓存数据
        self.session_id = self.cache.get(self._redis_key("session"))
        self.think = self.cache.get(self._redis_key("think"), default="")
        self.script = self.cache.get(self._redis_key("script"), default="")

        self.script_generator = dify.script_client(session_id=self.session_id)

        self.logline = story_input.get("logline")
        self.roles = utils.format_roles(story_input.get("roles"))
        self.tags = utils.format_tags(story_input.get("tags"))

        for role in story_input.get("roles", []):
            self.characters.setdefault(role["name"], role)

    def voice_resource_key(self, name: str, age: str):
        return f"voice_{self.request_id}_{name}_{age}"

    def _redis_key(self, field: str):
        return f"story:{self.request_id}:{field}"

    @property
    def story_prompt(self):
        """获取完整的故事提示词"""
        if not self.logline or not self.roles or not self.tags or not self.think:
            raise Exception("Story is not complete")

        return utils.format_story(self.logline,
                                  self.roles,
                                  self.tags,
                                  think=self.think,
                                  script=self.script)

    def character_tag(self, character_name: str, character_age: str = None):
        if character_age:
            return normalize.normalize_name(character_name) + " " + pinyin.get(character_age, format="strip")
        else:
            return normalize.normalize_name(character_name)

    async def scene_drawing(self, scene_info: Union[Dict, ET.Element]):
        """场景绘图"""
        if not self.task_manager:
            logger.warning("Task manager is not initialized!")
            return

        scene_title = scene_info.get("title")
        scene_location = scene_info.get("location")
        scene_time = scene_info.get("time")
        bg_tag = f"{scene_location} - {scene_time}"

        if bg_tag in self.scenes:
            return

        scene_details = await dify.scene_details(self.story_prompt, bg_tag)
        scene_prompt = utils.format_scene_prompt(scene_details)
        self.scenes.setdefault(bg_tag, {})["prompt"] = scene_prompt
        self.scenes[bg_tag].update(scene_details)

        bg_id = utils.get_bg_id(scene_location, scene_time)
        logger.info(f"Scene drawing: {scene_title} - {scene_location} - {scene_time} - {bg_id}")

        await self.task_manager.submit_task(
            "tasks.scene_drawing",
            args=[self.image_path, "bg", bg_id, scene_prompt],
            queue="image_generation"
        )

    async def character_portrait(self, character_info: Union[Dict, ET.Element]):
        """角色立绘"""
        if not self.task_manager:
            logger.warning("Task manager is not initialized!")
            return

        character_name = character_info.get("name")
        character_age = character_info.get("age")
        voice_resource_key = self.voice_resource_key(character_name, character_age)
        self.resource_tracker.register(voice_resource_key)

        if character_name in self.characters and self.characters[character_name].get("periods"):
            details = self.characters[character_name]["periods"].get(character_age)
            if details:
                self.resource_tracker.set_ready(voice_resource_key, details.get("voice", self.default_voice))
                return

        self.characters.setdefault(character_name, {})
        self.characters[character_name].setdefault("periods", {})

        character = f"{character_name} - {character_age}"
        story_prompt = self.story_prompt
        character_details = await dify.character_details(story_prompt, character)
        self.resource_tracker.set_ready(voice_resource_key, character_details.get("voice", self.default_voice))
        character_prompt = utils.format_character_prompt(character_details)

        if character_details.get("gender") and not self.characters[character_name].get("gender"):
            # 角色超出设计范围则尝试从画像中获取性别
            self.characters[character_name]["gender"] = character_details["gender"]

        self.characters[character_name]["periods"][character_age] = {"prompt": character_prompt}
        self.characters[character_name]["periods"][character_age].update(character_details)
        logger.info(f"Character portrait: {character_name} - {character_age} - {character_prompt[:20]}...")

        await self.task_manager.submit_task(
            "tasks.character_portrait",
            args=[self.image_path, self.character_tag(character_name, character_age), character_prompt],
            queue="image_generation"
        )

    async def check_voice(self,
                          name: str,
                          age: str,
                          timeout: float = 600.0):
        """获取指定角色的音色"""
        voice_resource_key = self.voice_resource_key(name, age)
        self.resource_tracker.register(voice_resource_key)
        description = await self.resource_tracker.get(
            voice_resource_key, timeout=timeout, default=self.default_voice
        )
        return description

    async def match_voice(self, description: str, gender: str, age: str):
        # 查看音色缓存
        key = f"{description}-{gender}-{age}"
        if self.voices.get(key):
            return self.voices[key]

        results = await mediahub.search_voice(description, gender=gender, age=age)
        if not results and (gender or age):
            # 降级搜索
            results = await mediahub.search_voice(description)

        if not results:
            raise Exception(f"Can not search voice for {description} - {gender} - {age}")

        for result in results:
            # 音色去重
            voice_id = result["voice_id"]
            if voice_id not in self.voices.values():
                self.voices[key] = voice_id
                return voice_id

        return results[0]["voice_id"]

    async def _enqueue_scenes(self):
        """解析 script 并将场景信息推入队列"""
        if not self.script:
            return

        story = ET.fromstring(self.script)
        story_info = StoryInfo(title=story.get("title"))
        self.cache.push(self._redis_key("storylets"), story_info.to_dict(), ttl=86400)

        for seq_idx, sequence in enumerate(story.findall('sequence')):
            seq_idx += 1
            chapter_info = ChapterInfo(idx=seq_idx, title=sequence.get("title"))
            self.cache.push(self._redis_key("storylets"), chapter_info.to_dict(), ttl=86400)

            for scene_idx, scene in enumerate(sequence.findall('scene')):
                scene_idx += 1
                # 收集场景中的角色信息
                characters = [
                    CharacterInfo(
                        name=character.get("name"),
                        age=character.get("age")
                    )
                    for character in scene.findall("character")
                ]

                # 创建场景信息模型
                scene_info = SceneInfo(
                    index=f"{seq_idx}{scene_idx}",
                    title=scene.get("title"),
                    location=scene.get("location"),
                    time=scene.get("time"),
                    content=ET.tostring(scene, encoding="utf8", xml_declaration=False).decode(),
                    characters=characters
                )

                # 推入队列（Pydantic 模型会自动序列化为 dict）
                self.cache.push(self._redis_key("storylets"), scene_info.to_dict(), ttl=86400)

    async def infer_story(self):
        """推理生成故事内容（think 和 script）"""
        # 检查是否已有缓存
        if self.think and self.script:
            # 如果已有缓存但队列为空，重新入队
            if self.cache.queue_len(self._redis_key("storylets")) == 0:
                await self._enqueue_scenes()
            return

        async for chunk in dify.plan_story(self.logline, self.roles, self.tags):
            if chunk.get("type") == "think":
                self.think = chunk.get("content")
                # 立即写入缓存
                self.cache.set(self._redis_key("think"), self.think, ttl=86400)

            elif chunk.get("type") == "output":
                for event in self.xml_parser.stream(chunk.get("content")):
                    if event["event"] == "start" and event["tag"] == "story":
                        self.title = event["attrib"].get("title")

                    if event["event"] == "start" and event["tag"] == "scene":
                        await self.scene_drawing(event["attrib"])

                    elif event["event"] == "end" and event["tag"] == "character":
                        if event["attrib"].get("name") in self.characters:
                            # 脚本设计中的角色直接做任务立绘
                            await self.character_portrait(event["attrib"])

                    elif event["event"] == "end" and event["tag"] == "story":
                        self.script = event["xml_text"]
                        # 立即写入缓存
                        self.cache.set(self._redis_key("script"), self.script, ttl=86400)

                        all_characters = re.findall(r"<character name=\"(.*?)\" age=\"(.*?)\">", event["xml_text"])
                        for character in all_characters:
                            character_name = character[0]
                            character_age = character[1]
                            if character_name not in self.characters:
                                # 剧本新增的辅助角色需要先获取完整的脚本
                                self.characters.setdefault(character_name, {})["age"] = character_age
                                await self.character_portrait({"name": character_name, "age": character_age})

                        # 将所有场景推入队列
                        await self._enqueue_scenes()

    async def run(self):
        await self.infer_story()
        self.task_manager = await get_task_manager()

        # 从队列中处理场景
        while self.cache.queue_len(self._redis_key("storylets")) > 0:
            # 从队列弹出场景信息
            scene_data = self.cache.pop(self._redis_key("storylets"))
            if scene_data["tag"] != "scene":
                continue
            if not scene_data:
                break

            # 反序列化为 SceneInfo 模型
            scene_info = SceneInfo.from_dict(scene_data)
            logger.info(f"Processing scene from queue: {scene_info.title} ({scene_info.index})")
            yield f"label scene_{scene_info.index}"

            # 记录每个角色当前的年龄
            for character in scene_info.characters:
                if character.name in self.characters:
                    self.characters[character.name]["age"] = character.age

            # 为每一个场景生成剧本
            self.xml_parser.reset()
            event_idx = 0

            try:
                # 分场剧本推理
                story_prompt_text = self.story_prompt
                async for chunk in self.script_generator.stream(
                    query=scene_info.content,
                    inputs={"story": story_prompt_text}
                ):
                    if self.session_id is None and self.script_generator.conversation_id is not None:
                        # 记录故事会话ID
                        self.session_id = self.script_generator.conversation_id
                        self.cache.set(self._redis_key("session"), self.session_id, ttl=86400)

                    for event in self.xml_parser.stream(chunk):
                        event_idx += 1
                        event_index = f"{scene_info.index}{event_idx}"

                        if event["event"] == "start" and event["tag"] == "scene":
                            bg_tag = utils.get_bg_id(scene_info.location, scene_info.time)
                            yield f"scene bg {bg_tag}"

                            music = event["attrib"].get("music")
                            ambient = event["attrib"].get("ambient")

                            if music and music.lower() not in {"无", "none", "null"}:
                                # 背景音乐
                                music_path = os.path.join(self.audio_path, f"m{scene_info.index}.mp3")
                                logger.info(f"Music audio generating: {music} - {music_path}")
                                await self.task_manager.submit_task(
                                    "tasks.sound_audio",
                                    args=[music, "music", music_path],
                                    queue="audio_processing"
                                )
                                yield f"play music m{scene_info.index}"
                            else:
                                yield "stop music"

                            if ambient and ambient.lower() not in {"无", "none", "null"}:
                                # 环境音效
                                ambient_path = os.path.join(self.audio_path, f"a{scene_info.index}.mp3")
                                logger.info(f"Ambient audio generating: {ambient} - {ambient_path}")
                                await self.task_manager.submit_task(
                                    "tasks.sound_audio",
                                    args=[ambient, "ambient", ambient_path],
                                    queue="audio_processing"
                                )
                                yield f"play ambient a{scene_info.index}"
                            else:
                                yield "stop ambient"

                        elif event["event"] == "end" and event["tag"] in ("dialogue", "monologue"):
                            # 对话配音
                            character_name = event["attrib"].get("character")
                            default_gender = utils.infer_gender(character_name) or self.default_gender
                            default_age = utils.infer_age(character_name) or self.default_age

                            if character_name in self.characters:
                                character_gender = self.characters[character_name].get("gender", default_gender)
                                character_age = self.characters[character_name].get("age", default_age)
                                character_age = normalize.normalize_age(character_age)
                                character_voice = await self.check_voice(character_name, character_age)
                            else:
                                character_gender = default_gender
                                character_age = default_age
                                character_voice = self.default_voice

                            voice_id = await self.match_voice(character_voice, character_gender, character_age)
                            emotion = normalize.normalize_emotion(event["attrib"].get("emotion", "normal"))
                            dialogue_text = utils.clean_text(event["text"])
                            dialogue_path = os.path.join(self.audio_path, f"d{event_index}.mp3")
                            voice_effect = "monologue" if event["tag"] == "monologue" else None

                            logger.info(f"Dialogue audio generating: {character_name} - {character_age} - {emotion} - {dialogue_path}")
                            await self.task_manager.submit_task(
                                "tasks.dialogue_asr",
                                args=[voice_id, dialogue_text, dialogue_path],
                                kwargs={"emotion": emotion, "voice_effect": voice_effect},
                                queue="audio_processing"
                            )

                            # 展示人物图像、展示对话文本、播放对话语音
                            yield f"voice d{event_index}"
                            yield f"show {self.character_tag(character_name, character_age)} {emotion}"
                            yield f'"{character_name}" "{dialogue_text}"'
                            yield f"hide {normalize.normalize_name(character_name)}"

                        elif event["event"] == "end" and event["tag"] == "sound":
                            # 音效检索
                            sound_description = utils.clean_sound_description(event["text"])
                            sound_path = os.path.join(self.audio_path, f"s{event_index}.mp3")
                            logger.info(f"Sound audio generating: {sound_description} - {sound_path}")
                            await self.task_manager.submit_task(
                                "tasks.sound_audio",
                                args=[sound_description, "action", sound_path],
                                queue="audio_processing"
                            )
                            yield f"play audio s{event_index}"

                        elif event["event"] == "end" and event["tag"] in ("action", "narration"):
                            # 旁白解说
                            narration_text = utils.clean_text(event["text"])
                            if self.narration_voice:
                                narration_path = os.path.join(self.audio_path, f"n{event_index}.mp3")
                                await self.task_manager.submit_task(
                                    "tasks.dialogue_asr",
                                    args=[self.narration_voice, narration_text, narration_path],
                                    kwargs={"emotion": "normal"},
                                    queue="audio_processing"
                                )
                                yield f"voice n{event_index}"

                            yield f'"{narration_text}"'
            except etree.XMLSyntaxError:
                # 跳过解析错误的场景
                continue


async def test():
    from tasks.task_manager import get_task_manager
    from test_tasks import wait_for_all_tasks_complete

    # 初始化 Redis
    try:
        await init_redis()
        logger.info("Redis 初始化成功")
    except Exception as e:
        logger.warning(f"Redis 初始化失败，将不使用缓存: {e}")

    file = "data\末世重生之病娇人偶师.json"
    story = json.load(open(file, encoding="utf-8"))

    # 运行测试
    project_path = "projects/demo/game"
    pipeline = StoryPipeline(story, project_path, narration_voice="story-tell-man")
    pipeline.task_manager = await get_task_manager()

    cleared = await pipeline.task_manager.clear_all_queues()
    print(f"Cleared: {cleared}")

    lines = []
    async for line in pipeline.run():
        lines.append(line)

    file_name = os.path.split(file)[-1].split(".")[0]
    os.makedirs("logs/scripts", exist_ok=True)
    story_prompt_text = pipeline.story_prompt
    with open(os.path.join("logs/scripts", f"{file_name}.txt"), "w", encoding="utf-8") as fp:
        fp.write(story_prompt_text)

    await wait_for_all_tasks_complete(pipeline.task_manager, check_interval=10.0, timeout=7200.0)
    await pipeline.task_manager.shutdown()

    script = ""
    for line in lines:
        # 检查对话音频文件是否存在
        if line.startswith("voice"):
            dialogue_path = os.path.join(pipeline.audio_path, f"{line.split()[-1]}.mp3")
            if not os.path.isfile(dialogue_path):
                logger.warning(f"对话音频文件不存在，跳过: {dialogue_path}")
                continue

        # 检查动作音效文件是否存在
        if line.startswith("play audio"):
            audio_file = line.split()[-1]
            audio_path = os.path.join(pipeline.audio_path, f"{audio_file}.mp3")
            if not os.path.isfile(audio_path):
                logger.warning(f"动作音效文件不存在，跳过: {audio_path}")
                continue

        # 检查背景音乐文件是否存在
        if line.startswith("play music"):
            music_file = line.split()[-1]
            music_path = os.path.join(pipeline.audio_path, f"{music_file}.mp3")
            if not os.path.isfile(music_path):
                logger.warning(f"背景音乐文件不存在，跳过: {music_path}")
                line = "stop music"

        # 检查环境音效文件是否存在
        if line.startswith("play ambient"):
            ambient_file = line.split()[-1]
            ambient_path = os.path.join(pipeline.audio_path, f"{ambient_file}.mp3")
            if not os.path.isfile(ambient_path):
                logger.warning(f"环境音效文件不存在，跳过: {ambient_path}")
                line = "stop ambient"

        if line.startswith("label"):
            script += "\n" + line + ":\n"
        else:
            script += "    " + line + "\n"

    title = pipeline.title or "故事开始了。"
    script = RENPY_TEMPLATE.format(title=title, script=script)

    with open(os.path.join(project_path, "script.rpy"), "w", encoding="utf-8") as fp:
        fp.write(script)


if __name__ == "__main__":
    asyncio.run(test())
