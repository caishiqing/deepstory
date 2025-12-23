"""
音频生成任务

任务执行层：只负责调用 API，返回 ResourceResult（URL 或 data URI）。
不做下载，下载由消费层处理。
"""
from endpoints.mediahub import get_audio_download_url, search_audio, text_to_speech
from tasks.logger_config import task_logger
from .models import ResourceResult
from loguru import logger
import uuid


@task_logger("dialogue_asr")
async def dialogue_asr(voice_id: str,
                       text: str,
                       tag: str = None,
                       emotion: str = None,
                       voice_effect: str = None) -> ResourceResult:
    """对话配音

    Args:
        voice_id: 音色 ID
        text: 要合成的文本
        tag: 资源标签
        emotion: 情绪类型
        voice_effect: 声音特效

    Returns:
        ResourceResult: 包含音频 data URI 的结果
    """
    tag = tag or f"dialogue_{uuid.uuid4().hex[:8]}"
    logger.info(f"Dialogue ASR: voice_id={voice_id}, tag={tag}")

    try:
        tts_result = await text_to_speech(
            text=text,
            voice_id=voice_id,
            emotion=emotion or "normal",
            voice_effect=voice_effect
        )

        audio_url = tts_result["audio_url"]

        return ResourceResult(
            resource_type="voice",
            urls=[audio_url],
            tag=tag,
            attribute=emotion,
            metadata={
                "voice_id": voice_id,
                "text_length": len(text),
                "voice_effect": voice_effect
            }
        )

    except Exception as e:
        logger.error(f"Failed to generate dialogue audio: {e}")
        raise


@task_logger("sound_audio")
async def sound_audio(sound_description: str,
                      sound_type: str,
                      tag: str = None) -> ResourceResult:
    """音效检索

    Args:
        sound_description: 音效描述
        sound_type: 音效类型（music/ambient/action）
        tag: 资源标签

    Returns:
        ResourceResult: 包含音频 URL 的结果（搜索不到时 urls 为空）
    """
    tag = tag or f"{sound_type}_{uuid.uuid4().hex[:8]}"
    logger.info(f"Sound audio: '{sound_description}' ({sound_type}), tag={tag}")

    try:
        sound = await search_audio(sound_description, audio_type=sound_type)

        if not sound:
            logger.warning(f"No {sound_type} found for: '{sound_description}'")
            return ResourceResult(
                resource_type="audio",
                urls=[],
                tag=tag,
                metadata={"sound_type": sound_type, "description": sound_description, "found": False}
            )

        audio_url = await get_audio_download_url(sound["id"])

        if not audio_url:
            raise Exception(f"No download URL for audio: {sound['id']}")

        return ResourceResult(
            resource_type="audio",
            urls=[audio_url],
            tag=tag,
            metadata={
                "sound_type": sound_type,
                "description": sound_description,
                "sound_id": sound["id"],
                "found": True
            }
        )

    except Exception as e:
        logger.error(f"Failed to process sound audio: {e}")
        raise
