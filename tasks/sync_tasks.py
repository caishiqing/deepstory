from endpoints.mediahub import get_audio_download_url, search_audio, text_to_speech
from utils import download_file
from tasks.logger_config import task_logger
from urllib.parse import unquote
from loguru import logger
import binascii
import uuid
import os


@task_logger("dialogue_asr")
async def dialogue_asr(voice_id: str,
                       text: str,
                       save_path: str,
                       emotion: str = None,
                       voice_effect: str = None):
    """对话配音

    Args:
        voice_id: 音色ID（必需）
        text: 要合成的文本
        save_path: 保存路径
        emotion: 情绪类型（normal/happy/angry/sad/fearful/disgusted/surprised）
        voice_effect: 声音特效类型（none/monologue/robot/monster/telephone/cave/demon/radio）
    """
    if os.path.isdir(save_path):
        save_path = os.path.join(save_path, f"dialogue_{uuid.uuid4().hex[:8]}.mp3")
        logger.warning(f"Save path is a directory, using random name: {save_path}")

    logger.info(f"Starting dialogue ASR: voice_id={voice_id} -> {save_path}")

    try:
        # 文本转语音
        logger.debug(f"Converting text to speech: {len(text)} characters, emotion={emotion}, voice_effect={voice_effect}")
        tts_result = await text_to_speech(
            text=text,
            voice_id=voice_id,
            emotion=emotion or "normal",
            voice_effect=voice_effect
        )
        audio = tts_result["audio_hex"]

        # 保存音频文件
        audio_bytes = binascii.unhexlify(audio)
        with open(save_path, "wb") as f:
            f.write(audio_bytes)

        logger.info(f"Dialogue audio saved: {save_path} ({len(audio_bytes)} bytes)")

    except Exception as e:
        logger.error(f"Failed to generate dialogue audio: {e}")
        raise


@task_logger("sound_audio")
async def sound_audio(sound_description: str, sound_type: str, save_path: str):
    """音效检索

    注意：如果搜索不到匹配的音效（匹配度不够或没有相关素材），任务会成功完成但不生成文件。
    这不会视为失败，因为音效素材库可能没有合适的素材。
    """
    logger.info(f"Starting sound audio search: '{sound_description}' ({sound_type}) -> {save_path}")

    try:
        # 搜索音频
        logger.debug(f"Searching for {sound_type} audio: '{sound_description}'")
        sound = await search_audio(sound_description, audio_type=sound_type)

        if not sound:
            logger.warning(f"No {sound_type} found for description: '{sound_description}'")
            logger.info(f"Sound audio task completed without file generation (no matching audio found)")
            return  # 正常返回，不抛出异常

        logger.info(f"Found {sound_type}: {sound['id']}")

        # 获取下载链接
        logger.debug(f"Getting download URL for audio: {sound['id']}")
        audio_url = await get_audio_download_url(sound["id"])

        if not audio_url:
            logger.error(f"Failed to get download URL for audio: {sound['id']}")
            raise Exception(f"No download URL for audio: {sound['id']}")

        if os.path.isdir(save_path):
            audio_file = os.path.split(unquote(audio_url))[-1]
            save_path = os.path.join(save_path, audio_file)
            logger.warning(f"Save path is a directory, using audio file name: {save_path}")

        # 下载音频文件
        logger.debug(f"Downloading audio from: {audio_url}")
        success = await download_file(audio_url, save_path)

        if success:
            logger.info(f"Sound audio downloaded successfully: {save_path}")
        else:
            logger.error(f"Failed to download sound audio to: {save_path}")
            raise Exception(f"Download failed for: {audio_url}")

    except Exception as e:
        logger.error(f"Failed to process sound audio: {e}")
        raise
