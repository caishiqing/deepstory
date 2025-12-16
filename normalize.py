import hashlib
import pinyin
import re


# 高兴，悲伤，愤怒，害怕，厌恶，惊讶，中性
# ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm"]
emotion_map = {
    "happy": "happy",
    "sad": "sad",
    "angry": "angry",
    "fearful": "fearful",
    "disgusted": "disgusted",
    "surprised": "surprised",
    "calm": "normal",
    "neutral": "normal",
    "normal": "normal",
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

# 童年、少年、青年、成年、中年、老年
age_map = {
    "童年": "童年",
    "少年": "少年",
    "青年": "青年",
    "成年": "成年",
    "中年": "成年",
    "老年": "老年",
    "儿童": "童年",
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

# 清晨/上午/中午/下午/傍晚/夜晚/凌晨
time_map = {
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
    "morning": "morning",
    "noon": "noon",
    "afternoon": "afternoon",
    "evening": "evening",
    "night": "night",
    "midnight": "midnight",
}


def normalize_emotion(emotion) -> str:
    return emotion_map.get(emotion.lower().strip(), "normal")


def normalize_age(age) -> str:
    if not age:
        return "青年"
    return age_map.get(age.lower().strip(), "青年")


def normalize_name(name: str) -> str:
    # 中文名转化为拼音
    id = hashlib.md5(name.encode()).hexdigest()
    name = re.sub("[（\(].*?[）\)]", "", name).strip()
    name = name.replace("/", "").replace(" ", "")
    return pinyin.get(name, format="strip").lower() + id[-2:]


def normalize_time(time: str) -> str:
    time = re.split("[/-]", time)[-1]
    return time_map.get(time.lower(), "unkown")
