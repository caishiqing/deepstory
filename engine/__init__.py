"""
Engine 包

流式叙事引擎的核心组件：
- producer: 事件生产者（StoryEngine）
- consumer: 资源消费（OfflineConsumer, RenpyConsumer, StreamingConsumer）
- tracer: 资源追踪器（ResourceTracker）
"""

# 生产者
from .producer import (
    StoryEngine,
    NarrativeEvent,
    StoryStartEvent,
    ChapterStartEvent,
    SceneStartEvent,
    DialogueEvent,
    NarrationEvent,
    SoundEvent,
    StoryEndEvent,
)

# 消费者
from .consumer import (
    OfflineConsumer,
    RenpyConsumer,
    StreamingConsumer,
    DownloadedResource,
)

# 追踪器
from .tracer import (
    ResourceTracker,
    TrackedResource,
)

__all__ = [
    # Producer
    "StoryEngine",
    "NarrativeEvent",
    "StoryStartEvent",
    "ChapterStartEvent",
    "SceneStartEvent",
    "DialogueEvent",
    "NarrationEvent",
    "SoundEvent",
    "StoryEndEvent",
    # Consumer
    "OfflineConsumer",
    "RenpyConsumer",
    "StreamingConsumer",
    "DownloadedResource",
    # Tracer
    "ResourceTracker",
    "TrackedResource",
]
