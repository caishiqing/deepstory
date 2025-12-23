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
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_enum_values=True,
    )

    resource_type: str = Field(..., description="资源类型: image/audio/voice")
    urls: List[str] = Field(default_factory=list, description="资源 URL 列表")

    # Ren'Py 资源命名相关
    tag: str = Field("", description="资源标签（如角色名拼音）")
    attribute: Optional[str] = Field(None, description="资源属性（如情绪、年龄）")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    @property
    def primary_url(self) -> Optional[str]:
        """获取主要 URL（第一个）"""
        return self.urls[0] if self.urls else None

    def get_renpy_name(self, index: int = 0) -> str:
        """生成 Ren'Py 兼容的资源名称

        Args:
            index: URL 索引（当有多个 URL 时）

        Returns:
            Ren'Py 资源名称，如 'peter qingnian' 或 'bg bg1234'
        """
        if self.attribute:
            return f"{self.tag} {self.attribute}"
        return self.tag


# 所有数据模型现在都可以直接使用 Pydantic 的内置序列化方法：
# - model.model_dump_json() 转为 JSON 字符串
# - model.model_dump() 转为字典
# - Model.model_validate_json(json_str) 从 JSON 创建模型
# - Model.model_validate(dict_data) 从字典创建模型
