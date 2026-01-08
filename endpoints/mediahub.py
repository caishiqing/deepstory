import aiohttp
import dotenv
import os
from typing import Optional, Dict, Any, Union, List

from utils import async_retry, get_config_value
from cache import redis_cache

dotenv.load_dotenv()


class MediaHubClient:

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("MEDIAHUB_BASE_URL", "http://localhost:5000")
        self.api_key = api_key or os.getenv("MEDIAHUB_API_KEY")

    @property
    def headers(self):
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def post(self, endpoint: str, payload: dict, timeout: int = 30):
        """发送POST请求"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status in [200, 201]:
                    return await response.json()
                else:
                    try:
                        error_data = await response.json()
                        raise Exception(f"MediaHub API Error {response.status}: {error_data}")
                    except Exception:
                        text = await response.text()
                        raise Exception(f"HTTP {response.status}: {text}")

    async def get(self, endpoint: str, params: dict = None, timeout: int = 30):
        """发送GET请求"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    try:
                        error_data = await response.json()
                        raise Exception(f"MediaHub API Error {response.status}: {error_data}")
                    except Exception:
                        text = await response.text()
                        raise Exception(f"HTTP {response.status}: {text}")


@redis_cache(ttl=3600, key_prefix="audio")
@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def search_audio(query: str,
                       audio_type: str = None,
                       tag: Union[str, List[str]] = None,
                       min_duration: int = None,
                       max_duration: int = None,
                       max_distance: float = None) -> Optional[Dict[str, Any]]:
    """音频搜索 - 返回最佳匹配结果

    Args:
        query: 搜索查询文本 (必需)
        audio_type: 音频类型过滤 (music, ambient, mood, action, transition)
        tag: 标签过滤 - 部分匹配
        min_duration: 最小时长(秒)
        max_duration: 最大时长(秒)
        max_distance: 最大匹配距离(0-1之间)，如果不指定则从配置文件中读取

    Returns:
        dict: 最佳匹配的音频素材信息，如果没有找到则返回None
    """
    client = MediaHubClient()

    # 如果未指定 max_distance，从配置文件中读取
    if max_distance is None:
        max_distance = get_config_value("global.audio_search_threshold", 0.4)

    # 音乐和氛围音对匹配精度并不敏感
    if audio_type in ["music", "mood"]:
        max_distance = None

    # 构建搜索参数
    payload = {
        "query": query,
        "limit": 1  # 只返回top1结果
    }

    # 添加可选参数
    if audio_type:
        payload["type"] = audio_type
        payload["enable_commercial"] = audio_type == "music" or None
    if tag:
        payload["tag"] = tag
    if min_duration is not None:
        payload["min_duration"] = min_duration
    if max_duration is not None:
        payload["max_duration"] = max_duration
    if max_distance is not None:
        payload["max_distance"] = max_distance

    results = await client.post("/audio/search", payload)
    # 返回第一个结果，如果列表为空则返回None
    return results[0] if results and len(results) > 0 else None


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_audio_download_url(audio_id: Union[int, str]) -> str:
    """获取音频下载地址

    Args:
        audio_id: 音频素材ID

    Returns:
        str: 音频文件下载URL
    """
    client = MediaHubClient()
    result = await client.get(f"/audio/{audio_id}/download-url")
    # 根据API规范，返回的是包含URL的对象，提取URL字段
    if isinstance(result, dict) and "url" in result:
        return result["url"]
    elif isinstance(result, dict) and "download_url" in result:
        return result["download_url"]
    else:
        # 如果结构不明确，返回整个结果
        return str(result)


@redis_cache(ttl=3600, key_prefix="voice")
@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def search_voice(query: str,
                       gender: str = None,
                       age: str = None,
                       limit: int = 10) -> Optional[Dict[str, Any]]:
    """声音搜索

    Args:
        query: 搜索查询文本 (必需)
        gender: 性别过滤 (male/female)
        age: 年龄范围过滤

    Returns:
        dict: 最佳匹配的声音信息，如果没有找到则返回None
    """
    client = MediaHubClient()

    # 构建搜索参数
    payload = {
        "query": query,
        "limit": limit
    }

    # 添加可选参数
    if gender:
        payload["gender"] = gender
    if age:
        payload["age"] = age

    results = await client.post("/voice/search", payload)
    return results


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def text_to_speech(text: str,
                         voice_id: str,
                         emotion: str = "normal",
                         emo_alpha: float = 1.0,
                         voice_effect: str = None) -> Optional[Dict[str, Any]]:
    """文本转语音 - TTS合成

    Args:
        text: 要合成的文本 (必需)
        voice_id: 角色voice_id (必需)
        emotion: 情绪 (可选: normal/happy/angry/sad/fearful/disgusted/surprised, 默认: normal)
        emo_alpha: 情绪强度 (0.0-1.0, 默认: 1.0)
        voice_effect: 声音特效类型 (可选: none/monologue/robot/monster/telephone/cave/demon/radio)
            - none: 无特效（默认）
            - monologue: 独白（明显混响）
            - robot: 机械音（机器人说话）
            - monster: 妖怪音（双声叠加，空灵高音）
            - telephone: 电话（现代手机通话，干净无噪音）
            - cave: 洞穴回声（多重延迟）
            - demon: 恶魔低沉（极低音高但保持清晰）
            - radio: 对讲机/收音机（带电流声滋滋声）

    Returns:
        dict: TTS响应，包含audio_url(音频下载地址)、audio_length、inference_time、rtf等信息
    """
    client = MediaHubClient()

    # 构建TTS请求参数
    payload = {
        "text": text,
        "voice_id": voice_id,
        "emotion": emotion,
        "emo_alpha": emo_alpha
    }

    # 添加可选的声音特效参数
    if voice_effect is not None:
        payload["voice_effect"] = voice_effect

    result = await client.post("/tts", payload, timeout=300)
    return result
