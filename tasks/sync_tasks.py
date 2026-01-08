"""
音频生成任务

任务执行层：只负责调用 API，返回 ResourceResult（URL）。
不做下载，下载和文件命名由消费层处理。
"""
from endpoints.mediahub import get_audio_download_url, search_audio, text_to_speech
from tasks.logger_config import task_logger
from .models import ResourceResult, AudioResourceResult
from loguru import logger


@task_logger("dialogue_asr")
async def dialogue_asr(voice_id: str,
                       text: str,
                       emotion: str = None,
                       voice_effect: str = None) -> AudioResourceResult:
    """对话配音

    Args:
        voice_id: 音色 ID
        text: 要合成的文本
        emotion: 情绪类型
        voice_effect: 声音特效

    Returns:
        AudioResourceResult: 包含音频 URL 和时长的结果
    """
    logger.info(f"Dialogue ASR: voice_id={voice_id}, text_len={len(text)}")

    try:
        tts_result = await text_to_speech(
            text=text,
            voice_id=voice_id,
            emotion=emotion or "normal",
            voice_effect=voice_effect
        )

        audio_url = tts_result["audio_url"]
        audio_duration = tts_result.get("audio_length")  # 从 TTS 结果中提取时长

        return AudioResourceResult(
            resource_type="audio",
            url_map={"default": audio_url},
            duration=audio_duration,
            voice_id=voice_id,
            emotion=emotion,
            voice_effect=voice_effect,
            text_length=len(text)
        )

    except Exception as e:
        logger.error(f"Failed to generate dialogue audio: {e}")
        raise


@task_logger("sound_audio")
async def sound_audio(sound_description: str,
                      sound_type: str) -> AudioResourceResult:
    """音效检索

    Args:
        sound_description: 音效描述
        sound_type: 音效类型（music/ambient/action）

    Returns:
        AudioResourceResult: 包含音频 URL 的结果（搜索不到时 urls 为空）
    """
    logger.info(f"Sound audio: '{sound_description}' ({sound_type})")

    try:
        sound = await search_audio(sound_description, audio_type=sound_type)

        if not sound:
            logger.warning(f"No {sound_type} found for: '{sound_description}'")
            return AudioResourceResult(
                resource_type="audio",
                url_map={},
                sound_type=sound_type,
                metadata={"description": sound_description, "found": False}
            )

        audio_url = await get_audio_download_url(sound["id"])

        if not audio_url:
            raise Exception(f"No download URL for audio: {sound['id']}")

        # 从音频库获取时长信息（如果有）
        audio_duration = sound.get("duration")

        return AudioResourceResult(
            resource_type="audio",
            url_map={"default": audio_url},
            duration=audio_duration,
            sound_type=sound_type,
            metadata={
                "description": sound_description,
                "sound_id": sound["id"],
                "found": True
            }
        )

    except Exception as e:
        logger.error(f"Failed to process sound audio: {e}")
        raise
