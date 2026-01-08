from typing import List, Union, List, Dict
from lxml import etree
import hashlib
import re
import os
import asyncio
import functools
from datetime import datetime
import aiohttp
import aiofiles
from loguru import logger
import yaml


# ==================== 配置管理 ====================

_config_cache = None


def load_config(config_path: str = "config.yaml") -> dict:
    """
    加载配置文件（带缓存）

    Args:
        config_path: 配置文件路径，默认为 "config.yaml"

    Returns:
        dict: 配置字典
    """
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            _config_cache = yaml.safe_load(f)
            return _config_cache
    except Exception as e:
        logger.error(f"加载配置文件失败 {config_path}: {e}")
        return {}


def get_config_value(key_path: str, default=None) -> any:
    """
    获取配置值，支持点分隔的键路径

    Args:
        key_path: 配置键路径，例如 "global.audio_search_threshold"
        default: 默认值

    Returns:
        配置值，如果不存在则返回默认值

    Example:
        >>> get_config_value("global.audio_search_threshold", 0.5)
        0.5
    """
    config = load_config()
    keys = key_path.split(".")

    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


# ==================== 装饰器工具 ====================

def async_retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(Exception,)):
    """
    异步函数重试装饰器

    Args:
        max_attempts: 最大重试次数（包括首次尝试）
        delay: 初始延迟时间（秒）
        backoff: 延迟时间的指数退避因子
        exceptions: 需要重试的异常类型元组

    Example:
        @async_retry(max_attempts=3, delay=2.0, backoff=2.0)
        async def api_call():
            response = await client.post(...)
            return response
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(f"函数 {func.__name__} 在 {max_attempts} 次尝试后最终失败: {e}")
                        raise

                    logger.warning(f"函数 {func.__name__} 第 {attempt} 次尝试失败: {e}, 将在 {current_delay:.1f} 秒后重试...")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # 理论上不会到这里，但为了安全起见
            raise last_exception

        return wrapper
    return decorator


# ==================== 异步工具函数 ====================

async def download_file(url: str, file_path: str, timeout: int = 60) -> bool:
    """异步下载文件到指定路径

    Args:
        url: 文件下载地址
        file_path: 保存文件的完整路径
        timeout: 下载超时时间(秒)

    Returns:
        bool: 下载成功返回True，失败返回False
    """
    try:
        # 确保目标目录存在
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        # 创建超时配置
        timeout_config = aiohttp.ClientTimeout(total=timeout)

        # 异步下载文件
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.get(url) as response:
                response.raise_for_status()

                # 异步写入文件
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)

        logger.debug(f"Successfully downloaded: {file_path}")
        return True

    except aiohttp.ClientError as e:
        logger.error(f"下载失败 - 网络错误: {str(e)}")
        return False
    except OSError as e:
        logger.error(f"下载失败 - 文件操作错误: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"下载失败 - 未知错误: {str(e)}")
        return False


# ==================== 格式化工具函数 ====================

def format_character_prompt(character_detail: dict):
    details = [
        character_detail.get("setting", ""),
        character_detail.get("culture", ""),
        character_detail.get("appearance", ""),
        character_detail.get("figure", ""),
        character_detail.get("hair", ""),
        character_detail.get("clothing", "")
    ]
    return "\n".join(details)


def format_scene_prompt(scene_detail: dict):
    details = [
        scene_detail.get("setting", ""),
        scene_detail.get("style", ""),
        scene_detail.get("background", ""),
        scene_detail.get("color", ""),
        scene_detail.get("light", "")
    ]
    return "\n".join(details)


def format_characters(characters: List[dict], relationships: List[dict] = None):
    text = ""
    for i, role in enumerate(characters):
        if not role.get("name"):
            continue
        text += f"\n### {role['name']}\n"
        # if "function" in role:
        #     text += f"{role['function']}\n"
        if "nickname" in role:
            text += f"- 昵称：{role['nickname']}\n"
        if "gender" in role:
            text += f"- 性别：{role['gender']}\n"
        if "age" in role:
            text += f"- 年龄：{role['age']}\n"
        if "appearance" in role:
            text += f"- 外貌：{role['appearance']}\n"
        if "identity" in role:
            text += f"- 身份：{role['identity']}\n"
        if "background" in role:
            text += f"- 背景：{role['background']}\n"
        if "regional" in role:
            text += f"- 地域文化：{role['regional']}\n"
        if "explicit_character" in role:
            text += f"- 显性性格：{role['explicit_character']}\n"
        if "implicit_character" in role:
            text += f"- 隐性性格：{role['implicit_character']}\n"
        if "values" in role:
            text += f"- 价值观：{role['values']}\n"
        if "motivation" in role:
            text += f"- 目标与动机：{role['motivation']}\n"
        if "fear" in role:
            text += f"- 恐惧：{role['fear']}\n"
        if "desire" in role:
            text += f"- 欲望：{role['desire']}\n"
        if "relationship" in role:
            text += f"- 关系：{role['relationship']}\n"
        if "secret" in role:
            text += f"- 秘密与谎言：{role['secret']}\n"
        if "behavior_habit" in role:
            text += f"- 行为习惯：{role['behavior_habit']}\n"
        if "decision_style" in role:
            text += f"- 决策风格：{role['decision_style']}\n"
        if "word_preference" in role:
            text += f"- 用词偏好：{role['word_preference']}\n"
        if "reaction" in role:
            text += f"- 感官特质：{role['reaction']}\n"
        if "inner_conflict" in role:
            text += f"- 内在冲突：{role['inner_conflict']}\n"
        if "outer_conflict" in role:
            text += f"- 外在冲突：{role['outer_conflict']}\n"
        if "symbol" in role:
            text += f"- 象征意义：{role['symbol']}\n"
        if "connection" in role:
            text += f"- 观众共情点：{role['connection']}\n"

    if relationships:
        text += "\n**人物关系**:\n"
        for relation in relationships:
            text += f"- {relation['subject']} & {relation['object']}: {relation['relationship']}\n"

    return text.strip()


def format_tags(tags: dict):
    text = ""
    if "type" in tags:
        text += f"- 题材类型：{'、'.join(tags['type'])}\n"
    if "kernel" in tags:
        text += f"- 核心母题：{'、'.join(tags['kernel'])}\n"
    if "emotion" in tags:
        text += f"- 情感基调：{'、'.join(tags['emotion'])}\n"
    if "discussion" in tags:
        text += f"- 社会议题：{'、'.join(tags['discussion'])}\n"
    if "structure" in tags:
        text += f"- 叙事结构：{'、'.join(tags['structure'])}\n"
    if "culture" in tags:
        text += f"- 地域文化背景：{'、'.join(tags['culture'])}\n"

    return text.strip()


STORY_TEMPLATE = """
# 故事创意

## 一句话梗概
{logline}

## 角色列表
{characters}

## 类型标签
{tags}
"""


def format_story(logline: str,
                 characters: Union[str, List[Dict]],
                 tags: Union[str, Dict],
                 think: str = None,
                 script: str = None):

    if not isinstance(characters, str):
        characters = format_characters(characters)
    if not isinstance(tags, str):
        tags = format_tags(tags)

    story = STORY_TEMPLATE.format(logline=logline, characters=characters, tags=tags)
    if think:
        story += f"\n\n# 故事规划\n\n{think}"
    if script:
        story += f"\n\n# 故事脚本\n{script}"
    return story


def get_bg_id(location: str, time: str):
    id = hashlib.md5(f"{location} - {time}".encode()).hexdigest()
    return f"bg{id[:4]}"


def clean_sound_description(description: str):
    description = re.split("[ ,，、；]", description)[0]
    return description.strip().rstrip("的声音")


def clean_text(text: str):
    text = re.sub(r"（.*?）", "", text)
    text = text.replace('"', "")
    text = text.replace("%", "%%")
    return text


def infer_gender(text: str):
    if "女" in text or "female" in text.lower():
        return "female"
    if "男" in text or "male" in text.lower():
        return "male"


def infer_age(text: str):
    if "老" in text or "old" in text.lower():
        return "老年"
    if "青年" in text or "youth" in text.lower():
        return "青年"
    if "小孩" in text or "小朋友" in text or "child" in text.lower():
        return "童年"


class XMLParser:
    def __init__(self):
        self.parser = etree.XMLPullParser(events=('start', 'end'))
        self.xml_buffer = ""  # 保存所有输入的XML文本

    def _save_error_log(self, error: Exception):
        """将解析错误的XML文本保存到日志文件"""
        # 创建日志目录
        log_dir = "logs/xml"
        os.makedirs(log_dir, exist_ok=True)

        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_file = os.path.join(log_dir, f"parse_error_{timestamp}.xml")

        # 写入XML文本和错误信息
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("<!-- 解析错误信息 -->\n")
            f.write(f"<!-- 错误类型: {type(error).__name__} -->\n")
            f.write(f"<!-- 错误详情: {str(error)} -->\n")
            f.write("<!-- 时间: {} -->\n\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            f.write("<!-- XML内容 -->\n")
            f.write(self.xml_buffer)

        return log_file

    def stream(self, chunk: str):
        chunk = chunk.strip("`")
        if not chunk:
            return

        try:
            self.parser.feed(chunk)
            # 累积所有输入的XML文本
            self.xml_buffer += chunk

            for event, element in self.parser.read_events():
                # 获取元素的完整XML文本
                xml_text = etree.tostring(element, method='c14n').decode('utf-8')
                yield {
                    "event": event,
                    "tag": element.tag,
                    "attrib": dict(element.attrib),
                    "text": element.text,
                    "xml_text": xml_text
                }
        except etree.XMLSyntaxError as e:
            # 如果是空文档错误且缓冲区内容很少，说明还没开始真正的XML
            error_msg = str(e).lower()
            if ('empty' in error_msg or 'no element found' in error_msg) and len(self.xml_buffer.strip()) < 10:
                # 静默跳过，这是正常的流式场景（还在等待真正的XML内容）
                return

            # 其他真正的解析错误才记录日志
            log_file = self._save_error_log(e)
            print(f"XML 解析错误已记录到: {log_file}")
            raise
        except Exception as e:
            # 其他异常也记录
            log_file = self._save_error_log(e)
            print(f"XML 解析错误已记录到: {log_file}")
            raise

    def reset(self):
        """重置parser，以便可以解析新的文本流"""
        try:
            self.parser.close()
        except etree.XMLSyntaxError as e:
            # 如果XML不完整或有语法错误，记录日志但不影响重置
            log_file = self._save_error_log(e)
            print(f"重置时发现未完成的XML解析，已记录到: {log_file}")
        finally:
            # 无论close()是否成功，都创建新的parser
            self.parser = etree.XMLPullParser(events=('start', 'end'))
            self.xml_buffer = ""  # 清空缓冲区


def clean_xml(xml: str):
    xml = xml.strip().strip("`").strip()
    if xml.startswith("xml"):
        xml = xml[3:]

    return xml.strip()


if __name__ == "__main__":
    incomplete_chunks = [
        "<root>\n<it",      # 不完整的标签
        "em id='1'>",     # 标签的后半部分
        "内容",            # 文本内容
        "1</item>",       # 结束标签
        "\n<item id=",      # 不完整的属性
        "'2'>内容2",      # 属性和文本
        "</item>\n</ro",    # 不完整的结束标签
        "ot>"             # 结束
    ]
    parser = XMLParser()
    for chunk in incomplete_chunks:
        for data in parser.stream(chunk):
            print(data)
