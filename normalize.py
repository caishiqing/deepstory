"""标签标准化模块 - Enum 集成式设计"""
import hashlib
import pinyin
import re
from enum import Enum
from typing import Optional


# ==================== 映射表（在 Enum 外部定义以避免访问问题） ====================

_EMOTION_MAPPING = {
    # 英文
    "happy": "happy",
    "sad": "sad",
    "angry": "angry",
    "fearful": "fearful",
    "disgusted": "disgusted",
    "surprised": "surprised",
    "normal": "normal",
    "calm": "normal",
    "neutral": "normal",
    # 中文
    "高兴": "happy",
    "悲伤": "sad",
    "愤怒": "angry",
    "害怕": "fearful",
    "厌恶": "disgusted",
    "惊讶": "surprised",
    "中性": "normal",
    "正常": "normal",
    "镇定": "normal",
}

_AGE_MAPPING = {
    # 中文
    "童年": "童年",
    "少年": "少年",
    "青年": "青年",
    "成年": "成年",
    "中年": "成年",
    "老年": "老年",
    "儿童": "童年",
    # 英文
    "child": "童年",
    "teenager": "少年",
    "youth": "青年",
    "adult": "成年",
    "middle age": "成年",
    "middle aged": "成年",
    "mid-life": "成年",
    "old": "老年",
    "elderly": "老年",
}

_TIME_MAPPING = {
    # 中文
    "清晨": "morning",
    "早上": "morning",
    "上午": "morning",
    "中午": "noon",
    "下午": "afternoon",
    "傍晚": "evening",
    "夜晚": "night",
    "晚上": "night",
    "午夜": "midnight",
    "凌晨": "night",
    # 英文
    "morning": "morning",
    "noon": "noon",
    "afternoon": "afternoon",
    "evening": "evening",
    "night": "night",
    "midnight": "midnight",
}


# ==================== 情绪标签 ====================

class EmotionTag(str, Enum):
    """标准情绪标签（7种）- 集成映射表和标准化方法"""
    HAPPY = "happy"          # 高兴
    SAD = "sad"              # 悲伤
    ANGRY = "angry"          # 愤怒
    FEARFUL = "fearful"      # 害怕
    DISGUSTED = "disgusted"  # 厌恶
    SURPRISED = "surprised"  # 惊讶
    NORMAL = "normal"        # 正常/中性

    def __str__(self) -> str:
        """返回枚举值"""
        return self.value

    @classmethod
    def normalize(cls, emotion: str) -> "EmotionTag":
        """标准化输入为 EmotionTag 枚举

        Args:
            emotion: 输入的情绪（中英文、各种别名）

        Returns:
            EmotionTag 枚举对象

        Examples:
            >>> EmotionTag.normalize("高兴")
            EmotionTag.HAPPY
            >>> str(EmotionTag.normalize("calm"))
            "normal"
        """
        if not emotion:
            return cls.NORMAL

        normalized = emotion.lower().strip()
        value = _EMOTION_MAPPING.get(normalized, cls.NORMAL.value)
        return cls(value)

    @classmethod
    def to_str(cls, emotion: str) -> str:
        """标准化输入为字符串（向后兼容）

        Args:
            emotion: 输入的情绪

        Returns:
            标准化的情绪字符串
        """
        return cls.normalize(emotion).value


# ==================== 年龄段标签 ====================

class AgeTag(str, Enum):
    """标准年龄段标签（5种）- 集成映射表和标准化方法"""
    CHILD = "童年"      # 童年/儿童
    TEENAGER = "少年"   # 少年/青少年
    YOUTH = "青年"      # 青年
    ADULT = "成年"      # 成年/中年
    ELDERLY = "老年"    # 老年

    def __str__(self) -> str:
        return self.value

    @classmethod
    def normalize(cls, age: str) -> "AgeTag":
        """标准化输入为 AgeTag 枚举"""
        if not age:
            return cls.YOUTH

        normalized = age.lower().strip()
        value = _AGE_MAPPING.get(normalized, cls.YOUTH.value)
        return cls(value)

    @classmethod
    def to_str(cls, age: str) -> str:
        """标准化输入为字符串（向后兼容）"""
        return cls.normalize(age).value


# ==================== 时间段标签 ====================

class TimeTag(str, Enum):
    """标准时间段标签（6种）- 集成映射表和标准化方法"""
    MORNING = "morning"      # 清晨/早上/上午
    NOON = "noon"            # 中午
    AFTERNOON = "afternoon"  # 下午
    EVENING = "evening"      # 傍晚
    NIGHT = "night"          # 夜晚/晚上/凌晨
    MIDNIGHT = "midnight"    # 午夜

    def __str__(self) -> str:
        return self.value

    @classmethod
    def normalize(cls, time: str) -> "TimeTag":
        """标准化输入为 TimeTag 枚举"""
        if not time:
            return cls.MORNING

        # 提取时间部分（去除日期）
        time_part = re.split("[/-]", time)[-1]
        normalized = time_part.lower().strip()
        value = _TIME_MAPPING.get(normalized, cls.MORNING.value)
        return cls(value)

    @classmethod
    def to_str(cls, time: str) -> str:
        """标准化输入为字符串（向后兼容）"""
        return cls.normalize(time).value


# ==================== 向后兼容的函数接口 ====================

def normalize_emotion(emotion: str) -> str:
    """标准化情绪（向后兼容函数）

    Args:
        emotion: 输入的情绪

    Returns:
        标准化的情绪字符串
    """
    return EmotionTag.to_str(emotion)


def normalize_age(age: str) -> str:
    """标准化年龄段（向后兼容函数）

    Args:
        age: 输入的年龄段

    Returns:
        标准化的年龄段字符串
    """
    return AgeTag.to_str(age)


def normalize_time(time: str) -> str:
    """标准化时间段（向后兼容函数）

    Args:
        time: 输入的时间段

    Returns:
        标准化的时间段字符串
    """
    return TimeTag.to_str(time)


def normalize_name(name: str) -> str:
    """标准化角色名称（转拼音 + hash 后缀）

    Args:
        name: 角色名称（中文）

    Returns:
        标准化的名称标识符（拼音 + 2位hash）
    """
    id = hashlib.md5(name.encode()).hexdigest()
    name = re.sub("[（\(].*?[）\)]", "", name).strip()
    name = name.replace("/", "").replace(" ", "")
    return pinyin.get(name, format="strip").lower() + id[-2:]


# ==================== 向后兼容的字典（可选） ====================

emotion_map = _EMOTION_MAPPING
age_map = _AGE_MAPPING
time_map = _TIME_MAPPING
