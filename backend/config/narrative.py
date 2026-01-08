from typing import List


class NarrativeConfig:
    """叙事全局配置"""

    # ==================== 转场效果配置 ====================
    # 对应数据库配置键：global_settings['transition.default']
    DEFAULT_SCENE_START_TRANSITION = {
        "type": "fade_in",
        "duration": 1.5
    }

    DEFAULT_SCENE_END_TRANSITION = {
        "type": "fade_out",
        "duration": 1.0
    }

    # ==================== 角色显示配置 ====================
    # 对应数据库配置键：global_settings['character.default']
    DEFAULT_PORTRAIT_POSITION = "center"
    DEFAULT_AUTO_HIDE = True

    # 角色颜色池（循环分配给新角色）
    # 对应数据库配置键：global_settings['character.colors']
    CHARACTER_COLOR_POOL: List[str] = [
        "#ff6b9d",  # 粉红
        "#6b9dff",  # 蓝色
        "#9dff6b",  # 绿色
        "#ff9d6b",  # 橙色
        "#9d6bff",  # 紫色
        "#6bffff",  # 青色
    ]

    # ==================== 用户设置默认值 ====================
    # 注：这些值作为新用户的初始设置，用户可在前端修改
    # 对应用户表 users.settings 字段

    # 文字速度（字符/秒）
    DEFAULT_TEXT_SPEED = 50

    # 自动推进（AFM）
    DEFAULT_AFM_ENABLE = True
    DEFAULT_AFM_TIME = 15  # 秒

    # 音量配置
    DEFAULT_VOICE_VOLUME = 1.0
    DEFAULT_MUSIC_VOLUME = 0.7
    DEFAULT_SOUND_VOLUME = 1.0
    DEFAULT_AMBIENT_VOLUME = 0.7

    # 选择超时时间（秒）
    DEFAULT_CHOICE_TIMEOUT = 30

    # ==================== 旁白音色配置 ====================
    # 默认旁白音色ID（对应 MediaHub TTS 音色）
    DEFAULT_NARRATION_VOICE = "narrator_001"

    # ==================== 资源生成配置 ====================
    # 资源等待超时时间（秒）
    # SSE 推送事件时，等待每个资源就绪的最大时间
    RESOURCE_TIMEOUT = 3600.0  # 1 小时

    @classmethod
    def get_character_color(cls, index: int) -> str:
        """
        根据索引从颜色池中循环获取颜色

        Args:
            index: 角色索引（0, 1, 2, ...）

        Returns:
            角色颜色的十六进制值
        """
        return cls.CHARACTER_COLOR_POOL[index % len(cls.CHARACTER_COLOR_POOL)]

    @classmethod
    def get_default_user_settings(cls) -> dict:
        """
        获取新用户的默认设置

        Returns:
            用户设置字典（对应 users.settings 字段）
        """
        return {
            "text_speed": cls.DEFAULT_TEXT_SPEED,
            "afm_enable": cls.DEFAULT_AFM_ENABLE,
            "afm_time": cls.DEFAULT_AFM_TIME,
            "voice_volume": cls.DEFAULT_VOICE_VOLUME,
            "music_volume": cls.DEFAULT_MUSIC_VOLUME,
            "sound_volume": cls.DEFAULT_SOUND_VOLUME,
            "ambient_volume": cls.DEFAULT_AMBIENT_VOLUME,
            "choice_timeout": cls.DEFAULT_CHOICE_TIMEOUT,
        }


# 全局配置实例（单例）
narrative_config = NarrativeConfig()
