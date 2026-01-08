"""
Tasks 包的统一数据模型定义

使用 Pydantic 实现更好的序列化支持，解决所有序列化问题
"""

import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union

from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic.json import pydantic_encoder


class TaskStatus(str, Enum):
    """任务状态枚举 - 继承str支持直接序列化"""
    PENDING = "pending"        # 等待开始
    QUEUED = "queued"         # 已排队
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败
    RETRYING = "retrying"     # 重试中
    CANCELLED = "cancelled"   # 已取消
    TIMEOUT = "timeout"       # 超时


class TaskInfo(BaseModel):
    """任务信息数据类 - 用于 TaskManager（Pydantic版本）"""

    model_config = ConfigDict(
        # 允许任意类型作为字段值
        arbitrary_types_allowed=True,
        # 使用枚举值进行序列化
        use_enum_values=True,
        # 严格模式
        validate_assignment=True,
    )

    task_id: str = Field(
        default_factory=lambda: f"{uuid.uuid4().hex[:8]}",
        description="任务唯一ID，自动生成默认值"
    )
    queue_name: str = Field(..., description="队列名称")
    function_name: str = Field(..., description="函数名称")
    args: List[Any] = Field(default_factory=list, description="位置参数")
    kwargs: Dict[str, Any] = Field(default_factory=dict, description="关键字参数")
    status: TaskStatus = Field(TaskStatus.PENDING, description="任务状态，默认为PENDING")
    created_at: float = Field(default_factory=time.time, description="创建时间戳")
    started_at: Optional[float] = Field(None, description="开始时间戳")
    completed_at: Optional[float] = Field(None, description="完成时间戳")
    result: Optional[Any] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")
    retry_count: int = Field(0, description="重试次数")
    max_tries: int = Field(3, description="最大重试次数")

    @field_validator('task_id')
    @classmethod
    def validate_task_id(cls, v):
        """自动处理 task_id 为 None 的情况"""
        if v is None or v == "":
            return f"task-{uuid.uuid4().hex[:8]}"
        return str(v)

    @field_validator('started_at', 'completed_at')
    @classmethod
    def validate_timestamps(cls, v):
        """自动处理时间类型转换问题"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.timestamp()
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return None

    @field_validator('result')
    @classmethod
    def serialize_result(cls, v):
        """自动处理结果的序列化"""
        if v is None:
            return v
        # 使用 pydantic 的编码器处理复杂对象
        try:
            import json
            json.dumps(v, default=pydantic_encoder)
            return v
        except (TypeError, ValueError):
            return str(v)

    def get_created_datetime(self) -> datetime:
        """获取创建时间的 datetime 对象"""
        return datetime.fromtimestamp(self.created_at)

    def get_started_datetime(self) -> Optional[datetime]:
        """获取开始时间的 datetime 对象"""
        return datetime.fromtimestamp(self.started_at) if self.started_at else None

    def get_completed_datetime(self) -> Optional[datetime]:
        """获取完成时间的 datetime 对象"""
        return datetime.fromtimestamp(self.completed_at) if self.completed_at else None


class TaskResult(BaseModel):
    """任务结果数据类 - 用于 AsyncTask 框架（Pydantic版本）"""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_enum_values=True,
        validate_assignment=True,
    )

    # 使用 default_factory 自动处理缺失的 task_id
    task_id: str = Field(
        default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}",
        description="任务ID，自动生成默认值"
    )
    status: TaskStatus = Field(..., description="任务状态")
    result: Optional[Any] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")
    created_at: float = Field(default_factory=time.time, description="创建时间戳")
    completed_at: Optional[float] = Field(None, description="完成时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    @field_validator('task_id')
    @classmethod
    def validate_task_id(cls, v):
        """自动处理 task_id 为 None 的情况"""
        if v is None or v == "":
            return f"task-{uuid.uuid4().hex[:8]}"
        return str(v)

    @field_validator('completed_at')
    @classmethod
    def validate_completed_at(cls, v):
        """自动处理时间类型转换问题"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.timestamp()  # datetime 转为时间戳
        if isinstance(v, (int, float)):
            return float(v)
        # 如果是字符串，尝试解析
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                pass
        # 默认返回当前时间戳
        return time.time()

    @field_validator('result')
    @classmethod
    def serialize_result(cls, v):
        """自动处理结果的序列化"""
        if v is None:
            return v
        try:
            import json
            json.dumps(v, default=pydantic_encoder)
            return v
        except (TypeError, ValueError):
            return str(v)

    def get_created_datetime(self) -> datetime:
        """获取创建时间的 datetime 对象"""
        return datetime.fromtimestamp(self.created_at)

    def get_completed_datetime(self) -> Optional[datetime]:
        """获取完成时间的 datetime 对象"""
        return datetime.fromtimestamp(self.completed_at) if self.completed_at else None


class PollingConfig(BaseModel):
    """轮询配置 - 用于 TaskPoller（Pydantic版本）"""

    initial_interval: float = Field(1.0, gt=0, description="初始轮询间隔(秒)")
    max_interval: float = Field(30.0, gt=0, description="最大轮询间隔(秒)")
    backoff_factor: float = Field(1.5, gt=1.0, description="退避因子")
    max_attempts: int = Field(100, gt=0, description="最大轮询次数")
    timeout: float = Field(3600.0, gt=0, description="总超时时间(秒)")
    exponential_backoff: bool = Field(True, description="是否使用指数退避")


class QueueConfig(BaseModel):
    """队列配置数据类（Pydantic版本）"""

    name: str = Field(..., description="队列名称")
    max_jobs: int = Field(..., gt=0, description="最大并发数")
    job_timeout: int = Field(..., gt=0, description="任务超时时间(秒)")
    keep_result: int = Field(..., gt=0, description="结果保存时间(秒)")
    max_tries: int = Field(..., gt=0, description="最大重试次数")
    retry_delay: List[int] = Field(..., description="重试延迟时间列表")


# 异常类定义
class TaskTimeoutError(Exception):
    """任务超时异常"""
    pass


class TaskExecutionError(Exception):
    """任务执行异常"""
    pass


# 类型别名定义
TaskCallback = Callable[[TaskResult], None]  # 任务完成回调函数类型


class ResourceResult(BaseModel):
    """资源生成结果 - 任务返回的统一格式

    所有资源生成任务（图像、音频等）都应返回此格式，
    包含资源 URL 和元数据，不再直接下载文件。
    文件命名由消费者（Consumer）自行决定。

    使用 url_map 统一管理资源 URL：
    - 单个 URL：{"default": "url"}
    - 多状态资源（如立绘）：{"happy": "url1", "sad": "url2"}
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_enum_values=True,
    )

    resource_type: str = Field(..., description="资源类型: image/audio/voice/portrait")
    url_map: Dict[str, str] = Field(default_factory=dict, description="状态 -> URL 映射")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    @property
    def primary_url(self) -> Optional[str]:
        """获取主要 URL（优先 default，否则第一个）"""
        if "default" in self.url_map:
            return self.url_map["default"]
        return next(iter(self.url_map.values()), None)

    @property
    def urls(self) -> List[str]:
        """获取所有 URL 列表"""
        return list(self.url_map.values())

    def get_url(self, key: str = "default", fallback: bool = True) -> Optional[str]:
        """获取指定 key 的 URL

        Args:
            key: URL 的 key（如 "default"、"happy" 等）
            fallback: 如果 key 不存在，是否回退到其他 URL

        Returns:
            URL 或 None

        智能兜底逻辑：
        1. 如果 url_map 只有一个 URL，直接返回（无论 key 是什么）
        2. 如果指定的 key 存在，返回对应的 URL
        3. 如果 key 不存在且 fallback=True，尝试回退到 "default" 或第一个 URL
        """
        # 智能兜底：如果只有一个 URL，直接返回
        if len(self.url_map) == 1:
            return next(iter(self.url_map.values()))

        # 优先使用指定的 key
        if key in self.url_map:
            return self.url_map[key]

        if not fallback:
            return None

        # 回退到 default
        if "default" in self.url_map:
            return self.url_map["default"]

        # 使用任意可用的 URL
        return next(iter(self.url_map.values()), None)


class AudioResourceResult(ResourceResult):
    """音频资源结果（配音、音乐、音效）

    专门用于音频类资源，包含时长、音色等关键信息
    通常只有一个 URL：{"default": "url"}
    """
    resource_type: str = "audio"
    duration: Optional[float] = Field(None, description="音频时长（秒）")
    voice_id: Optional[str] = Field(None, description="音色 ID")
    emotion: Optional[str] = Field(None, description="情绪类型")
    voice_effect: Optional[str] = Field(None, description="声音特效")
    text_length: Optional[int] = Field(None, description="文本长度")
    sound_type: Optional[str] = Field(None, description="音效类型（music/ambient/action）")


class ImageResourceResult(ResourceResult):
    """图像资源结果（背景等单图资源）

    通常只有一个 URL：{"default": "url"}
    """
    resource_type: str = "image"
    width: Optional[int] = Field(None, description="图像宽度")
    height: Optional[int] = Field(None, description="图像高度")


class PortraitResourceResult(ResourceResult):
    """角色立绘资源结果（多情绪）

    特点：
    - 一次生成多个情绪变体（利用 batch 优势）
    - 使用 url_map 存储情绪 -> URL 映射（继承自基类）
    - 事件引用时通过 emotion 精确提取所需 URL

    url_map 示例：{"happy": "url1", "sad": "url2", "normal": "url3"}
    """
    resource_type: str = "portrait"
    character: Optional[str] = Field(None, description="角色名")
    age: Optional[str] = Field(None, description="年龄段")
    width: Optional[int] = Field(None, description="图像宽度")
    height: Optional[int] = Field(None, description="图像高度")

    def get_emotion_url(self, emotion: str, fallback: bool = True) -> Optional[str]:
        """获取指定情绪的 URL

        Args:
            emotion: 目标情绪
            fallback: 是否在情绪不存在时回退到其他情绪

        Returns:
            URL 或 None
        """
        return self.get_url(emotion, fallback=fallback)


# 所有数据模型现在都可以直接使用 Pydantic 的内置序列化方法：
# - model.model_dump_json() 转为 JSON 字符串
# - model.model_dump() 转为字典
# - Model.model_validate_json(json_str) 从 JSON 创建模型
# - Model.model_validate(dict_data) 从字典创建模型
