# 前端实现文档

> **文档定位**：前端技术实现细节、核心模块、关键代码
> 
> **相关文档**：[README.md](./README.md) | [api.md](./api.md) | [backend.md](./backend.md)

---

## 核心设计原则

### 叙事队列 + 媒体轨道架构

前端采用**叙事队列调度 + 媒体轨道播放**的分离架构：

```
┌─────────────────────────────────────────────────────────────┐
│                      NarrativeQueue                         │
│                      （叙事队列）                             │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ dialogue │ play_    │ narration│ scene_   │ dialogue │  │
│  │ (阻塞)   │ sound    │ (阻塞)   │ start    │ (阻塞)   │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
│       ↓          ↓          ↓          ↓          ↓        │
└─────────────────────────────────────────────────────────────┘
        ↓          ↓          ↓          ↓
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │TextTrack│ │AudioTrack│ │TextTrack│ │VisualTrack│
   └────────┘ └────────┘ └────────┘ └────────┘
```

| 组件 | 职责 | 说明 |
|------|------|------|
| **NarrativeQueue** | 叙事流程调度 | 顺序处理事件，叙事事件阻塞队列 |
| **TextTrack** | 文本播放 | 对话/旁白文字渲染 |
| **VisualTrack** | 视觉播放 | 场景、图像、视频 |
| **AudioTrack** | 音频播放 | 语音、音乐、音效、环境音 |

### 事件标签系统

通过标签属性标记事件特性，支持扩展：

```typescript
// ============================================
// 解耦设计：事件 → 资源 → 轨道
// ============================================

// 1. 事件元数据：只关心是否阻塞叙事队列
interface EventMetadata {
  narrative: boolean;  // 是否阻塞叙事队列（需要等待用户点击/AFM）
}

const EVENT_REGISTRY: Record<string, EventMetadata> = {
  // 叙事事件（阻塞队列）
  'dialogue':    { narrative: true },
  'narration':   { narrative: true },
  'choice':      { narrative: true },
  
  // 非叙事事件（不阻塞队列）
  'scene_start': { narrative: false },
  'scene_end':   { narrative: false },
  'show':        { narrative: false },
  'hide':        { narrative: false },
  'play_video':  { narrative: false },
  'play_audio':  { narrative: false },  // 支持 channel: sound/music/ambient
  'stop_audio':  { narrative: false },
  'story_start': { narrative: false },
  'story_end':   { narrative: false },
  'chapter_start': { narrative: false },
  'chapter_end': { narrative: false },
};

// 2. 资源类型 → 轨道映射
type ResourceType = 'text' | 'voice' | 'image' | 'video' | 'music' | 'ambient' | 'sound' | 'background';
type TrackType = 'text' | 'visual' | 'audio';

const RESOURCE_TRACK_MAP: Record<ResourceType, TrackType> = {
  'text':       'text',
  'voice':      'audio',
  'image':      'visual',
  'video':      'visual',
  'music':      'audio',
  'ambient':    'audio',
  'sound':      'audio',
  'background': 'visual',
};

// 3. 资源播放器映射（资源类型 → 具体播放方法）
interface ResourcePlayer {
  text:       (content: any) => void;
  voice:      (audio: any) => void;
  image:      (character: string, image: any) => void;
  video:      (url: string) => void;
  music:      (audio: any) => void;
  ambient:    (audio: any) => void;
  sound:      (audio: any) => void;
  background: (bg: any) => void;
}
```

### 阻塞规则

#### 1. 叙事队列阻塞（NarrativeQueue）

| 条件 | 阻塞行为 |
|------|---------|
| `narrative: true` | 阻塞队列，等待 AFM 或用户点击 |
| `narrative: false` | 触发后立即处理下一个事件 |

#### 2. 轨道内阻塞（由各轨道控制）

| 轨道 | 资源类型 | 阻塞规则 |
|------|---------|---------|
| **TextTrack** | 文本 | 替换式（新文本替换旧文本）|
| **VisualTrack** | 场景 | 替换式 |
| | 图像 | 图层叠加，不阻塞 |
| | 视频 | 阻塞直到播放完成 |
| **AudioTrack** | music | 替换式，循环 |
| | voice | 替换式 |
| | ambient | 替换式，循环 |
| | sound | 多重播放，不阻塞 |

### 执行流程示例

```
事件: dialogue { text: "你好", voice: {...}, show: {...} }

dispatchEvent 处理:
  ├─ content.text 存在 → TextTrack.showDialogue("你好")
  ├─ content.voice 存在 → AudioTrack.playVoice({...})
  └─ content.show 存在 → VisualTrack.showCharacter({...})
```

```
事件序列: [narration, play_audio, play_audio, dialogue]

NarrativeQueue 处理（叙事锁机制）:

1. narration (narrative=true)
   ├─ 叙事锁已释放 → dispatchEvent() 根据资源分发
   │   ├─ content.text → TextTrack
   │   └─ content.voice → AudioTrack
   └─ 【加锁】
   
2. play_audio (narrative=false)
   ├─ dispatchEvent() → content.audio → AudioTrack
   └─ 立即处理下一个
   
3. play_audio (narrative=false)
   ├─ dispatchEvent() → content.audio → AudioTrack
   └─ 立即处理下一个
   
4. dialogue (narrative=true)
   └─ 等待叙事锁释放...
   
   ──── 用户点击/AFM → 释放锁 ────
   
   └─ dispatchEvent() → 【加锁】
```

**核心原则**：
- 事件只定义资源，不关心轨道
- 资源类型决定分发到哪个轨道
- narrative 标签决定是否阻塞叙事队列

---

## 核心架构

### 架构图

```
SSE 推送（后端）
    ↓
DataManager（接收事件）
    ↓
BufferController（缓冲控制）
    ↓
NarrativeQueue（叙事队列）──────────────────────────────────┐
    │                                                       │
    │  顺序处理所有事件                                      │
    │  ├─ narrative=true  → 阻塞（等待 AFM/用户点击）        │
    │  └─ narrative=false → 触发后立即处理下一个             │
    │                                                       │
    ├──► TextTrack（文本轨道）                               │
    │      └─ 文本渲染、打字机效果                           │
    │                                                       │
    ├──► VisualTrack（视觉轨道）                             │
    │      ├─ scene → 替换背景                              │
    │      ├─ image → 图层叠加                              │
    │      └─ video → 阻塞播放完成                          │
    │                                                       │
    └──► AudioTrack（音频轨道）                              │
           ├─ voice  → 替换式                               │
           ├─ music  → 替换式，循环                         │
           ├─ ambient→ 替换式，循环                         │
           └─ sound  → 多重播放                             │
    ↓
用户界面
```

### 核心模块

| 模块 | 职责 |
|------|------|
| **EventCache** | 事件持久化缓存（IndexedDB），支持离线播放 |
| **ConnectionManager** | 连接生命周期管理，分阶段按需连接 |
| **DataManager** | SSE 连接管理，事件接收 |
| **BufferController** | 缓冲控制，场景级缓冲策略 |
| **NarrativeQueue** | 叙事流程调度，阻塞/非阻塞控制 |
| **ProgressTracker** | 进度同步，延迟写入优化 |
| **TextTrack** | 文本轨道，文字渲染（打字机效果）|
| **VisualTrack** | 视觉轨道，场景/图像/视频播放 |
| **AudioTrack** | 音频轨道，多通道音频管理 |
| **ResourcePool** | 资源下载（并发控制、自动重试）|
| **LayerManager** | 图层管理（显示/隐藏元素）|

---

## 模块实现

### 0. EventCache - 事件持久化缓存

**职责**：将事件持久化到 IndexedDB，支持离线播放和断点续传

```typescript
interface CachedEvent {
  sequence_id: string;       // 主键
  story_id: string;          // 故事ID（索引）
  path_id: string;           // 分支路径
  event_type: string;
  content: object;
  timestamp: string;
  cached_at: number;         // 缓存时间戳
}

class EventCache {
  private db: IDBDatabase | null = null;
  private readonly DB_NAME = 'story_events_cache';
  private readonly STORE_NAME = 'events';
  private readonly DB_VERSION = 1;

  /**
   * 初始化 IndexedDB
   */
  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains(this.STORE_NAME)) {
          const store = db.createObjectStore(this.STORE_NAME, { keyPath: 'sequence_id' });
          
          // 索引：按故事查询，按序列排序
          store.createIndex('story_sequence', ['story_id', 'sequence_id'], { unique: true });
          // 索引：按故事和路径过滤
          store.createIndex('story_path', ['story_id', 'path_id'], { unique: false });
          // 索引：按缓存时间（用于清理过期数据）
          store.createIndex('cached_at', 'cached_at', { unique: false });
        }
      };
    });
  }

  /**
   * 批量存储事件
   */
  async saveEvents(events: SSEEvent[]): Promise<void> {
    if (!this.db || events.length === 0) return;
    
    const tx = this.db.transaction(this.STORE_NAME, 'readwrite');
    const store = tx.objectStore(this.STORE_NAME);
    
    const now = Date.now();
    for (const event of events) {
      const cachedEvent: CachedEvent = {
        sequence_id: event.sequence_id,
        story_id: event.content.story_id || this.extractStoryId(event.sequence_id),
        path_id: event.path_id,
        event_type: event.event_type,
        content: event.content,
        timestamp: event.timestamp,
        cached_at: now
      };
      store.put(cachedEvent);
    }
    
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  /**
   * 获取故事的所有缓存事件（按 sequence_id 排序）
   */
  async getEvents(storyId: string, pathId?: string): Promise<CachedEvent[]> {
    if (!this.db) return [];
    
    const tx = this.db.transaction(this.STORE_NAME, 'readonly');
    const store = tx.objectStore(this.STORE_NAME);
    const index = pathId 
      ? store.index('story_path')
      : store.index('story_sequence');
    
    const range = pathId
      ? IDBKeyRange.only([storyId, pathId])
      : IDBKeyRange.bound([storyId, ''], [storyId, '\uffff']);
    
    return new Promise((resolve, reject) => {
      const request = index.getAll(range);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * 获取最后缓存的 sequence_id
   */
  async getLastSequenceId(storyId: string): Promise<string | null> {
    const events = await this.getEvents(storyId);
    if (events.length === 0) return null;
    
    // ULID 按字典序排序即为时间顺序
    events.sort((a, b) => b.sequence_id.localeCompare(a.sequence_id));
    return events[0].sequence_id;
  }

  /**
   * 获取指定 sequence_id 之后的事件
   */
  async getEventsAfter(storyId: string, sequenceId: string): Promise<CachedEvent[]> {
    const events = await this.getEvents(storyId);
    return events
      .filter(e => e.sequence_id > sequenceId)
      .sort((a, b) => a.sequence_id.localeCompare(b.sequence_id));
  }

  /**
   * 清理过期缓存（默认 7 天）
   */
  async cleanExpired(maxAge: number = 7 * 24 * 60 * 60 * 1000): Promise<void> {
    if (!this.db) return;
    
    const tx = this.db.transaction(this.STORE_NAME, 'readwrite');
    const store = tx.objectStore(this.STORE_NAME);
    const index = store.index('cached_at');
    
    const expireTime = Date.now() - maxAge;
    const range = IDBKeyRange.upperBound(expireTime);
    
    return new Promise((resolve, reject) => {
      const request = index.openCursor(range);
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
        if (cursor) {
          cursor.delete();
          cursor.continue();
        }
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  /**
   * 清理指定故事的缓存
   */
  async clearStoryCache(storyId: string): Promise<void> {
    if (!this.db) return;
    
    const tx = this.db.transaction(this.STORE_NAME, 'readwrite');
    const store = tx.objectStore(this.STORE_NAME);
    const index = store.index('story_sequence');
    
    const range = IDBKeyRange.bound([storyId, ''], [storyId, '\uffff']);
    
    return new Promise((resolve, reject) => {
      const request = index.openCursor(range);
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
        if (cursor) {
          cursor.delete();
          cursor.continue();
        }
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  /**
   * 检查故事是否有缓存
   */
  async hasCache(storyId: string): Promise<boolean> {
    const events = await this.getEvents(storyId);
    return events.length > 0;
  }

  private extractStoryId(sequenceId: string): string {
    // 从 sequence_id 中提取 story_id（如果有前缀的话）
    // 如果使用纯 ULID，需要从其他地方获取 story_id
    return sequenceId.split('_')[0] || '';
  }
}
```

---

### 0.1 ConnectionManager - 连接生命周期管理

**职责**：管理故事的连接生命周期，实现分阶段按需连接策略

**核心设计**：
- **创作阶段**：短轮询（10秒间隔）查询状态，不建立 SSE
- **消费阶段**：统一缓冲策略，首次/继续观看使用相同逻辑
- **智能连接**：缓存不足时建立 SSE，缓存充足时断开 SSE

**统一缓冲策略**：

首次观看和继续观看使用**完全相同的缓冲策略**，区别仅在于本地缓存的命中情况：

| 场景 | 缓存状态 | 行为 |
|------|---------|------|
| **首次观看** | 无缓存 | 建立 SSE，接收事件并缓存到 IndexedDB |
| **继续观看** | 有缓存 | 从缓存读取，缓存不足时 SSE 增量补充 |

**缓存生命周期**：
- 缓存持久化到 IndexedDB，默认 7 天过期
- 应用启动时后台清理过期缓存
- 用户可手动清理特定故事的缓存

```typescript
type ConnectionState = 
  | 'IDLE'           // 无连接
  | 'POLLING'        // 创作阶段：轮询状态
  | 'STREAMING'      // 消费阶段：SSE 接收中
  | 'CACHE_PLAYING'  // 使用本地缓存播放
  | 'COMPLETED';     // 故事完成

interface StoryStatus {
  status: 'pending' | 'generating' | 'ready' | 'dynamic' | 'completed' | 'error';
  progress: number;
  message: string;
  events_count: number;
  retry_after: number;
}

interface ConnectionManagerOptions {
  pollInterval?: number;      // 轮询间隔（毫秒），默认 10000
  highWatermark?: number;     // 高水位（断开 SSE），默认 20
  lowWatermark?: number;      // 低水位（重连 SSE），默认 5
}

class ConnectionManager {
  private state: ConnectionState = 'IDLE';
  private storyId: string = '';
  private eventCache: EventCache;
  private dataManager: DataManager;
  private bufferController: BufferController;
  private pollTimer: number | null = null;
  
  // 配置
  private pollInterval: number;
  private highWatermark: number;
  private lowWatermark: number;
  
  // 回调
  private onStateChange?: (state: ConnectionState) => void;
  private onStatusUpdate?: (status: StoryStatus) => void;
  private onError?: (error: Error) => void;

  constructor(
    eventCache: EventCache,
    dataManager: DataManager,
    bufferController: BufferController,
    options: ConnectionManagerOptions = {}
  ) {
    this.eventCache = eventCache;
    this.dataManager = dataManager;
    this.bufferController = bufferController;
    
    this.pollInterval = options.pollInterval ?? 10000;  // 10秒
    this.highWatermark = options.highWatermark ?? 20;
    this.lowWatermark = options.lowWatermark ?? 5;
  }

  /**
   * 启动故事（智能选择连接方式）
   */
  async start(storyId: string): Promise<void> {
    this.storyId = storyId;
    
    try {
      // 1. 检查故事状态
      const status = await this.fetchStatus(storyId);
      
      if (status.status === 'pending' || status.status === 'generating') {
        // 创作阶段：启动轮询
        this.startPolling(storyId);
        return;
      }
      
      if (status.status === 'error') {
        this.handleError(new Error(status.message));
        return;
      }
      
      // 2. 消费阶段：检查本地缓存
      await this.startConsumption(storyId);
      
    } catch (error) {
      this.handleError(error as Error);
    }
  }

  /**
   * 停止所有连接
   */
  stop(): void {
    this.stopPolling();
    this.dataManager.disconnect();
    this.setState('IDLE');
  }

  /**
   * 获取当前状态
   */
  getState(): ConnectionState {
    return this.state;
  }

  /**
   * 设置状态变化回调
   */
  setOnStateChange(callback: (state: ConnectionState) => void): void {
    this.onStateChange = callback;
  }

  /**
   * 设置状态更新回调（轮询期间）
   */
  setOnStatusUpdate(callback: (status: StoryStatus) => void): void {
    this.onStatusUpdate = callback;
  }

  /**
   * 设置错误回调
   */
  setOnError(callback: (error: Error) => void): void {
    this.onError = callback;
  }

  /**
   * 通知缓冲状态变化（由 BufferController 调用）
   */
  onBufferLevelChange(unplayedCount: number): void {
    if (this.state === 'STREAMING' && unplayedCount >= this.highWatermark) {
      // 缓存充足，断开 SSE
      console.log(`📦 缓存充足 (${unplayedCount} >= ${this.highWatermark})，断开 SSE`);
      this.pauseStreaming();
    } else if (this.state === 'CACHE_PLAYING' && unplayedCount <= this.lowWatermark) {
      // 缓存不足，重连 SSE
      console.log(`📦 缓存不足 (${unplayedCount} <= ${this.lowWatermark})，重连 SSE`);
      this.resumeStreaming();
    }
  }

  // ============ 私有方法 ============

  private setState(state: ConnectionState): void {
    if (this.state !== state) {
      console.log(`🔄 连接状态: ${this.state} → ${state}`);
      this.state = state;
      this.onStateChange?.(state);
    }
  }

  /**
   * 创作阶段：轮询
   */
  private startPolling(storyId: string): void {
    this.setState('POLLING');
    
    const poll = async () => {
      try {
        const status = await this.fetchStatus(storyId);
        this.onStatusUpdate?.(status);
        
        if (status.status === 'ready' || status.status === 'dynamic') {
          // 生成完成，切换到消费阶段
          console.log('✅ 故事生成完成，进入消费阶段');
          this.stopPolling();
          await this.startConsumption(storyId);
          return;
        }
        
        if (status.status === 'error') {
          this.stopPolling();
          this.handleError(new Error(status.message));
          return;
        }
        
        // 继续轮询（使用服务端建议的间隔，默认 10 秒）
        const interval = (status.retry_after ?? 10) * 1000;
        this.pollTimer = window.setTimeout(poll, interval);
        
      } catch (error) {
        // 网络错误，继续重试
        console.warn('轮询失败，稍后重试:', error);
        this.pollTimer = window.setTimeout(poll, this.pollInterval);
      }
    };
    
    poll();
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
  }

  /**
   * 消费阶段：检查缓存并决定连接策略
   */
  private async startConsumption(storyId: string): Promise<void> {
    // 检查本地缓存
    const cachedEvents = await this.eventCache.getEvents(storyId);
    const lastSequenceId = await this.eventCache.getLastSequenceId(storyId);
    
    console.log(`📂 本地缓存: ${cachedEvents.length} 个事件`);
    
    if (cachedEvents.length > 0) {
      // 有缓存：先播放缓存
      this.setState('CACHE_PLAYING');
      
      // 将缓存事件推送到 BufferController
      for (const event of cachedEvents) {
        this.bufferController.receive(event as unknown as SSEEvent);
      }
      
      // 检查是否需要补充
      const unplayedCount = this.bufferController.getUnplayedCount();
      if (unplayedCount <= this.lowWatermark) {
        // 缓存不足，建立 SSE 增量接收
        this.startStreaming(storyId, lastSequenceId);
      }
    } else {
      // 无缓存：建立 SSE
      this.startStreaming(storyId, null);
    }
  }

  /**
   * 消费阶段：SSE 流式接收
   */
  private async startStreaming(storyId: string, fromSequenceId: string | null): Promise<void> {
    this.setState('STREAMING');
    
    // 注册事件处理
    this.dataManager.onStoryEventReceived(async (event) => {
      // 缓存到 IndexedDB
      await this.eventCache.saveEvents([event]);
      
      // 推送到 BufferController
      this.bufferController.receive(event);
      
      // 检查是否故事结束
      if (event.event_type === 'story_end') {
        this.setState('COMPLETED');
        this.dataManager.disconnect();
      }
    });
    
    // 建立连接
    this.dataManager.connect(storyId, fromSequenceId ?? undefined);
  }

  /**
   * 暂停 SSE（缓存充足时）
   */
  private pauseStreaming(): void {
    this.dataManager.disconnect();
    this.setState('CACHE_PLAYING');
  }

  /**
   * 恢复 SSE（缓存不足时）
   */
  private async resumeStreaming(): Promise<void> {
    const lastSequenceId = await this.eventCache.getLastSequenceId(this.storyId);
    this.startStreaming(this.storyId, lastSequenceId);
  }

  private async fetchStatus(storyId: string): Promise<StoryStatus> {
    const response = await fetch(`/api/v1/story/${storyId}/status`);
    if (!response.ok) {
      throw new Error(`获取状态失败: ${response.status}`);
    }
    const data = await response.json();
    return data.data;
  }

  private handleError(error: Error): void {
    console.error('❌ 连接错误:', error);
    this.onError?.(error);
  }
}
```

**使用示例**：

```typescript
// 应用启动时初始化缓存
const eventCache = new EventCache();
await eventCache.init();

// 后台清理过期缓存（7 天）
eventCache.cleanExpired().catch(console.warn);

const dataManager = new DataManager();
const bufferController = new BufferController(narrativeQueue, resourcePool);

const connectionManager = new ConnectionManager(eventCache, dataManager, bufferController, {
  pollInterval: 10000,   // 10秒轮询
  highWatermark: 20,     // 缓存 20 个事件后断开 SSE
  lowWatermark: 5        // 剩余 5 个事件时重连 SSE
});

// 状态回调
connectionManager.setOnStateChange((state) => {
  console.log(`连接状态: ${state}`);
  
  if (state === 'POLLING') {
    showLoadingScreen('正在生成故事...');
  } else if (state === 'STREAMING' || state === 'CACHE_PLAYING') {
    hideLoadingScreen();
  }
});

// 轮询进度回调
connectionManager.setOnStatusUpdate((status) => {
  updateProgressBar(status.progress);
  updateStatusMessage(status.message);
});

// 错误回调
connectionManager.setOnError((error) => {
  showErrorNotification(error.message);
});

// 缓冲控制器通知连接管理器
bufferController.setOnBufferLevelChange((count) => {
  connectionManager.onBufferLevelChange(count);
});

// 启动故事
await connectionManager.start('story_001');

// 用户退出时
window.addEventListener('beforeunload', () => {
  connectionManager.stop();
});
```

#### 统一缓冲策略：缓存命中与未命中

**核心原则**：首次观看和继续观看使用**完全相同的缓冲策略**，区别仅在于本地缓存的命中情况：

| 场景 | 缓存状态 | 缓冲行为 | 用户体验 |
|------|---------|---------|---------|
| **继续观看** | 有缓存 | 直接从 IndexedDB 读取 | 秒播，立即从上次位置开始 |
| **首次观看** | 无缓存 | 建立 SSE 接收并缓存 | 可选展示序幕掩盖加载 |

**策略统一性**：
- 两种场景都使用相同的高低水位控制
- 两种场景都会将事件持久化到 IndexedDB
- 两种场景都支持断点续传

**序幕加载（可选）**：首次观看时可展示序幕界面掩盖初始缓冲，这是用户体验优化而非核心策略。

```typescript
interface StoryMeta {
  story_id: string;
  title: string;
  logline: string;
  themes: {
    genre: string;
    tone: string;
  };
  characters: Array<{
    name: string;
    avatar_url?: string;
  }>;
}

class PlayPageController {
  private connectionManager: ConnectionManager;
  private eventCache: EventCache;
  private prologueUI: PrologueUI;
  
  /**
   * 进入播放页面
   */
  async enterPlayPage(storyId: string, storyMeta: StoryMeta): Promise<void> {
    // 1. 检查本地缓存
    const cachedEvents = await this.eventCache.getEvents(storyId);
    const hasCached = cachedEvents.length > 0;
    
    if (hasCached) {
      // 继续观看：秒播
      await this.startImmediate(storyId, cachedEvents);
    } else {
      // 首次观看：序幕加载
      await this.startWithPrologue(storyId, storyMeta);
    }
  }
  
  /**
   * 继续观看：秒播（有缓存）
   */
  private async startImmediate(storyId: string, cachedEvents: CachedEvent[]): Promise<void> {
    console.log('🎬 继续观看 - 秒播模式');
    
    // 读取上次进度
    const progress = await this.getLocalProgress(storyId);
    
    // 立即开始播放
    this.narrativeQueue.loadFromCache(cachedEvents, progress.current_sequence_id);
    this.narrativeQueue.play();
    
    // 后台检查是否需要补充更多事件
    const unplayedCount = this.bufferController.getUnplayedCount();
    if (unplayedCount <= 5) {
      await this.connectionManager.start(storyId);
    }
  }
  
  /**
   * 首次观看：序幕加载（无缓存）
   */
  private async startWithPrologue(storyId: string, storyMeta: StoryMeta): Promise<void> {
    console.log('🎬 首次观看 - 序幕加载模式');
    
    // 1. 显示序幕界面
    this.prologueUI.show({
      title: storyMeta.title,
      logline: storyMeta.logline,
      genre: storyMeta.themes.genre,
      tone: storyMeta.themes.tone,
      characters: storyMeta.characters
    });
    
    // 2. 后台开始加载
    const bufferReady = new Promise<void>((resolve) => {
      this.bufferController.setOnBufferReady(() => resolve());
    });
    
    await this.connectionManager.start(storyId);
    
    // 3. 等待用户点击"开始"或序幕动画结束
    const userReady = this.prologueUI.waitForStart();
    
    // 4. 两个条件都满足后开始播放
    await Promise.all([bufferReady, userReady]);
    
    // 5. 隐藏序幕，开始正式播放
    this.prologueUI.hide();
    this.narrativeQueue.play();
  }
}
```

#### 序幕界面（PrologueUI）

```typescript
interface PrologueData {
  title: string;
  logline: string;
  genre: string;
  tone: string;
  characters: Array<{ name: string; avatar_url?: string }>;
}

class PrologueUI {
  private container: HTMLElement;
  private startButton: HTMLButtonElement;
  private startPromise: Promise<void> | null = null;
  private startResolve: (() => void) | null = null;
  
  /**
   * 显示序幕界面
   */
  show(data: PrologueData): void {
    // 渲染序幕内容
    this.container.innerHTML = `
      <div class="prologue">
        <div class="prologue-backdrop"></div>
        <div class="prologue-content">
          <h1 class="prologue-title">${data.title}</h1>
          <p class="prologue-genre">${data.genre} · ${data.tone}</p>
          <p class="prologue-logline">${data.logline}</p>
          ${this.renderCharacters(data.characters)}
          <button class="prologue-start-btn">开始故事</button>
          <div class="prologue-loading">
            <span class="loading-spinner"></span>
            <span class="loading-text">正在准备...</span>
          </div>
        </div>
      </div>
    `;
    
    this.container.classList.add('visible');
    
    // 播放氛围音乐（可选）
    this.playAmbientMusic(data.genre);
    
    // 启动序幕动画
    this.startAnimation();
  }
  
  /**
   * 等待用户点击开始
   */
  waitForStart(): Promise<void> {
    this.startPromise = new Promise((resolve) => {
      this.startResolve = resolve;
      
      // 绑定按钮点击
      this.startButton = this.container.querySelector('.prologue-start-btn')!;
      this.startButton.addEventListener('click', () => {
        this.startResolve?.();
      });
      
      // 或者等待动画完成后自动开始（5秒）
      setTimeout(() => {
        this.startResolve?.();
      }, 5000);
    });
    
    return this.startPromise;
  }
  
  /**
   * 更新加载状态
   */
  updateLoadingStatus(message: string, ready: boolean): void {
    const loadingText = this.container.querySelector('.loading-text');
    if (loadingText) {
      loadingText.textContent = message;
    }
    
    if (ready) {
      this.startButton.disabled = false;
      this.startButton.textContent = '开始故事';
    }
  }
  
  /**
   * 隐藏序幕
   */
  hide(): void {
    this.container.classList.add('fade-out');
    setTimeout(() => {
      this.container.classList.remove('visible', 'fade-out');
    }, 500);
  }
  
  private renderCharacters(characters: Array<{ name: string; avatar_url?: string }>): string {
    if (!characters.length) return '';
    
    return `
      <div class="prologue-characters">
        ${characters.slice(0, 3).map(c => `
          <div class="character-card">
            ${c.avatar_url ? `<img src="${c.avatar_url}" alt="${c.name}">` : ''}
            <span>${c.name}</span>
          </div>
        `).join('')}
      </div>
    `;
  }
  
  private startAnimation(): void {
    // 标题淡入、文字逐步显示等动画效果
    const elements = this.container.querySelectorAll('.prologue-content > *');
    elements.forEach((el, i) => {
      (el as HTMLElement).style.animationDelay = `${i * 0.3}s`;
    });
  }
  
  private playAmbientMusic(genre: string): void {
    // 根据类型播放对应的氛围音乐
    // 可选功能
  }
}
```

**序幕设计要点**：
- 🎨 **视觉氛围**：背景模糊/渐变，营造沉浸感
- ⏱️ **时间控制**：3-5 秒，足够缓冲但不过长
- 🎵 **音乐预热**：可选播放背景音乐
- 📱 **交互反馈**：加载状态 → 准备就绪 → 开始按钮激活

---

### 0.2 DataManager - SSE 连接管理

**职责**：连接 SSE，接收事件，按事件类型分发

```typescript
class DataManager {
  private eventSource: EventSource | null = null;
  private onStoryEvent?: (event: SSEEvent) => void;
  private onSystemEvent?: (event: SSEEvent) => void;

  /**
   * 连接 SSE 端点
   */
  connect(storyId: string, fromSequenceId?: string): void {
    const url = fromSequenceId
      ? `/api/v1/story/${storyId}/stream?from_sequence_id=${fromSequenceId}`
      : `/api/v1/story/${storyId}/stream`;

    this.eventSource = new EventSource(url);

    // 监听 story_event（故事内容事件）
    this.eventSource.addEventListener('story_event', (e) => {
      const event: SSEEvent = JSON.parse(e.data);
      console.log(`📖 收到 Story 事件: ${event.event_type}`);
      
      if (this.onStoryEvent) {
        this.onStoryEvent(event);
      }
    });

    // 监听 system_event（系统状态事件）
    this.eventSource.addEventListener('system_event', (e) => {
      const event: SSEEvent = JSON.parse(e.data);
      console.log(`⚙️ 收到 System 事件: ${event.event_type}`);
      
      if (this.onSystemEvent) {
        this.onSystemEvent(event);
      }
    });

    // 连接打开
    this.eventSource.onopen = () => {
      console.log('✅ SSE 连接已建立');
    };

    // 连接错误
    this.eventSource.onerror = (error) => {
      console.error('❌ SSE 连接错误:', error);
      // 浏览器会自动重连
    };
  }

  /**
   * 注册 Story 事件处理器
   */
  onStoryEventReceived(handler: (event: SSEEvent) => void): void {
    this.onStoryEvent = handler;
  }

  /**
   * 注册 System 事件处理器
   */
  onSystemEventReceived(handler: (event: SSEEvent) => void): void {
    this.onSystemEvent = handler;
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}
```

**使用示例**：

```typescript
// 从用户设置读取音量配置
const userSettings = await getUserSettings();
const volumeConfig: AudioGlobalConfig = {
  voice_volume: userSettings.voice_volume,
  music_volume: userSettings.music_volume,
  sound_volume: userSettings.sound_volume,
  ambient_volume: userSettings.ambient_volume
};

// 初始化各组件
const resourcePool = new ResourcePool({ maxConcurrent: 6 });
const layerManager = new LayerManager();
const textTrack = new TextTrack();
const visualTrack = new VisualTrack(resourcePool, layerManager);
const audioTrack = new AudioTrack(resourcePool, volumeConfig);

// 叙事队列（核心调度器）
const narrativeQueue = new NarrativeQueue({
  textTrack,
  visualTrack,
  audioTrack,
  resourcePool
});

// 从用户设置配置叙事队列
narrativeQueue.setAFM(userSettings.afm_enable, userSettings.afm_time);
narrativeQueue.setChoiceTimeout(userSettings.choice_timeout);

// 缓冲控制器（配置缓冲大小）
const bufferController = new BufferController(narrativeQueue, resourcePool, {
  narrativeBufferSize: 10  // 缓存10个叙事事件后开始播放（默认值）
});

// 缓冲状态变化回调（更新 UI）
bufferController.setOnStateChange((state) => {
  if (state === 'buffering') {
    showLoadingScreen('正在加载...');
  } else if (state === 'waiting') {
    showLoadingScreen('缓冲中...');
  } else {
    hideLoadingScreen();
  }
});

// 叙事队列空时通知缓冲控制器
narrativeQueue.setOnQueueEmpty(() => {
  bufferController.onBufferEmpty();
});

const dataManager = new DataManager();

// Story 事件 → 缓冲控制器
dataManager.onStoryEventReceived((event) => {
  bufferController.receive(event);
});

// System 事件 → 更新UI状态
dataManager.onSystemEventReceived((event) => {
  if (event.event_type === 'heartbeat') {
    updateConnectionStatus('active');
  } else if (event.event_type === 'error') {
    showErrorNotification(event.content.message);
  }
});

// 连接
dataManager.connect('story_001');

// 处理用户选择（分支跳转）
narrativeQueue.setOnChoice(async (selectedOption) => {
  // 从选项中获取目标分支的 path_id
  const targetPathId = selectedOption.path_id;
  
  // 切换当前播放路径（核心！）
  // 切换后，后续匹配该 path_id 的事件将被播放
  // 如果该分支已预生成，资源已下载，立即无缝播放
  bufferController.switchPath(targetPathId);
  
  // 通知后端用户选择（记录进度、触发未生成分支的生成）
  await api.post(`/story/${storyId}/choice`, {
    option_id: selectedOption.option_id
  });
  
  console.log(`用户选择分支: ${selectedOption.option_id}, 切换路径: ${targetPathId}`);
});
```

---

### 0.3 BufferController - 缓冲控制器

**职责**：控制播放时机，确保有足够的缓冲避免卡顿；管理分支路径过滤

**核心设计**：
- **path_id 过滤**：只播放匹配 `currentPathId` 的事件，其他分支事件仅预下载资源
- **统一模型**：线性叙事和互动叙事使用相同逻辑（线性叙事 path_id 恒为 `"root0000"`）

**缓冲策略（事件级缓冲）**：
- **初始缓冲**：缓存 N 个**当前路径的**叙事事件 OR 遇到第一个 choice 事件后开始播放
- **追赶缓冲**：播放速度超过生产速度时暂停，缓存 N 个叙事事件 OR 遇到 choice 事件后继续
- **N 默认值**：10（可配置）

**叙事事件定义**：`dialogue`、`narration`、`choice`（即 `narrative: true` 的事件）

```typescript
type BufferState = 'buffering' | 'playing' | 'waiting';

// 事件类型注册表（判断是否为叙事事件）
const NARRATIVE_EVENTS = new Set(['dialogue', 'narration', 'choice']);

interface BufferControllerOptions {
  narrativeBufferSize?: number;  // 叙事事件缓冲数量，默认 10
}

class BufferController {
  private state: BufferState = 'buffering';
  private eventBuffer: SSEEvent[] = [];
  private narrativeQueue: NarrativeQueue;
  private resourcePool: ResourcePool;
  private onStateChange?: (state: BufferState) => void;
  
  // 缓冲配置
  private narrativeBufferSize: number;
  
  // 统计缓冲区中的叙事事件数量（仅当前路径）
  private narrativeEventCount = 0;
  
  // 当前播放路径（线性叙事恒为 "root0000"，互动叙事选择后切换）
  private currentPathId: string = 'root0000';

  constructor(
    narrativeQueue: NarrativeQueue, 
    resourcePool: ResourcePool,
    options: BufferControllerOptions = {}
  ) {
    this.narrativeQueue = narrativeQueue;
    this.resourcePool = resourcePool;
    this.narrativeBufferSize = options.narrativeBufferSize ?? 10;
  }

  /**
   * 接收事件（来自 DataManager）
   * 
   * 处理逻辑：
   * 1. 始终预加载资源（无论哪个分支）
   * 2. 只有 path_id 匹配的事件才加入缓冲区
   * 3. 其他分支的事件仅下载资源，不播放
   */
  receive(event: SSEEvent): void {
    // 始终预加载资源（包括其他分支，保证选择后无延迟）
    this.preloadResources(event);
    
    // 只处理当前路径的事件
    if (event.path_id !== this.currentPathId) {
      console.log(`🔀 跳过非当前路径事件: ${event.path_id} (当前: ${this.currentPathId})`);
      return;
    }
    
    // 加入缓冲区
    this.eventBuffer.push(event);
    
    // 如果是叙事事件，增加计数
    if (NARRATIVE_EVENTS.has(event.event_type)) {
      this.narrativeEventCount++;
      // 通知缓冲水位变化
      this.notifyBufferLevelChange();
    }
    
    // 检查是否可以开始/继续播放
    this.checkBufferReady(event);
  }

  /**
   * 切换当前播放路径（用户选择分支时调用）
   * 
   * @param pathId 新的路径ID
   */
  switchPath(pathId: string): void {
    console.log(`🔀 切换路径: ${this.currentPathId} → ${pathId}`);
    this.currentPathId = pathId;
    
    // 如果当前有新路径的缓冲事件（预生成的），立即处理
    // 注意：由于之前的事件已被跳过，需要从 DataManager 的历史中重新获取
    // 实际实现中可能需要 DataManager 维护一个全量事件缓存
  }

  /**
   * 获取当前路径ID
   */
  getCurrentPathId(): string {
    return this.currentPathId;
  }

  /**
   * 获取未播放的叙事事件数量（供 ConnectionManager 使用）
   */
  getUnplayedCount(): number {
    return this.narrativeEventCount + this.narrativeQueue.getQueueLength();
  }

  /**
   * 设置缓冲水位变化回调（供 ConnectionManager 使用）
   */
  setOnBufferLevelChange(callback: (count: number) => void): void {
    this.onBufferLevelChange = callback;
  }

  private onBufferLevelChange?: (count: number) => void;

  /**
   * 通知缓冲水位变化
   */
  private notifyBufferLevelChange(): void {
    if (this.onBufferLevelChange) {
      const count = this.getUnplayedCount();
      this.onBufferLevelChange(count);
    }
  }

  /**
   * 检查缓冲区是否就绪
   * 
   * 触发条件：
   * 1. 缓存了 N 个叙事事件
   * 2. 遇到 choice 事件（分支选项会阻塞播放）
   */
  private checkBufferReady(event: SSEEvent): void {
    const isBufferReady = 
      this.narrativeEventCount >= this.narrativeBufferSize || 
      event.event_type === 'choice';
    
    if (!isBufferReady) {
      return;
    }
    
    if (this.state === 'buffering') {
      console.log(`📦 初始缓冲完成（叙事事件: ${this.narrativeEventCount}），开始播放`);
      this.state = 'playing';
      this.flushBuffer();
      this.onStateChange?.('playing');
    } else if (this.state === 'waiting') {
      console.log(`📦 追赶缓冲完成（叙事事件: ${this.narrativeEventCount}），继续播放`);
      this.state = 'playing';
      this.flushBuffer();
      this.narrativeQueue.resume();
      this.onStateChange?.('playing');
    }
  }

  /**
   * 分发缓冲区中的所有事件到叙事队列
   */
  private flushBuffer(): void {
    while (this.eventBuffer.length > 0) {
      const event = this.eventBuffer.shift()!;
      this.narrativeQueue.enqueue(event);
    }
    // 重置计数
    this.narrativeEventCount = 0;
    // 通知缓冲水位变化
    this.notifyBufferLevelChange();
  }

  /**
   * 叙事队列通知：队列空
   */
  onBufferEmpty(): void {
    if (this.state === 'playing') {
      console.log('⏳ 播放速度超过生产速度，等待缓冲...');
      this.state = 'waiting';
      this.narrativeQueue.pause();
      this.onStateChange?.('waiting');
    }
  }

  /**
   * 预加载事件所需资源（无论哪个分支都预加载）
   */
  private preloadResources(event: SSEEvent): void {
    const urls = this.extractResourceUrls(event);
    urls.forEach(({ url, type }) => {
      this.resourcePool.download(url, type);
    });
  }

  private extractResourceUrls(event: SSEEvent): Array<{url: string, type: ResourceType}> {
    const urls: Array<{url: string, type: ResourceType}> = [];
    
    if (event.content?.show?.url) {
      // 通过文件扩展名判断资源类型
      const isVideo = this.isVideoUrl(event.content.show.url);
      urls.push({ 
        url: event.content.show.url, 
        type: isVideo ? 'video' : 'image' 
      });
    }
    if (event.content?.voice?.url) {
      urls.push({ url: event.content.voice.url, type: 'audio' });
    }
    if (event.content?.audio?.url) {
      urls.push({ url: event.content.audio.url, type: 'audio' });
    }
    if (event.content?.background?.url) {
      urls.push({ url: event.content.background.url, type: 'image' });
    }
    if (event.content?.music?.url) {
      urls.push({ url: event.content.music.url, type: 'audio' });
    }
    if (event.content?.ambient?.url) {
      urls.push({ url: event.content.ambient.url, type: 'audio' });
    }
    
    return urls;
  }

  setOnStateChange(callback: (state: BufferState) => void): void {
    this.onStateChange = callback;
  }

  getState(): BufferState {
    return this.state;
  }

  /**
   * 通过URL扩展名判断是否为视频
   */
  private isVideoUrl(url: string): boolean {
    const videoExtensions = ['.webm', '.mp4', '.ogv'];
    const urlLower = url.toLowerCase();
    return videoExtensions.some(ext => urlLower.includes(ext));
  }
}
```

---

### 0.2 NarrativeQueue - 叙事队列

**职责**：叙事流程调度，顺序处理所有事件，根据事件标签决定阻塞行为

**核心逻辑**：
- `narrative: true` → 阻塞队列（等待 AFM 或用户点击）
- `narrative: false` → 触发后立即处理下一个事件

```typescript
// 事件元数据
interface EventMetadata {
  narrative: boolean;  // 是否阻塞叙事队列
}

// 事件类型注册表
const EVENT_REGISTRY: Record<string, EventMetadata> = {
  // 叙事事件（阻塞队列）
  'dialogue':    { narrative: true },
  'narration':   { narrative: true },
  'choice':      { narrative: true },
  
  // 视频事件（视觉轨道内替换式，不阻塞叙事队列）
  'play_video':  { narrative: false },
  
  // 非叙事事件（不阻塞队列）
  'scene_start': { narrative: false },
  'scene_end':   { narrative: false },
  'show':        { narrative: false },
  'hide':        { narrative: false },
  'play_audio':  { narrative: false },  // 支持 channel: sound/music/ambient
  'stop_audio':  { narrative: false },
  'story_start': { narrative: false },
  'story_end':   { narrative: false },
  'chapter_start': { narrative: false },
  'chapter_end': { narrative: false },
};

interface NarrativeQueueOptions {
  textTrack: TextTrack;
  visualTrack: VisualTrack;
  audioTrack: AudioTrack;
  resourcePool: ResourcePool;
}

class NarrativeQueue {
  private queue: SSEEvent[] = [];
  private isProcessing = false;
  private isPaused = false;
  
  private textTrack: TextTrack;
  private visualTrack: VisualTrack;
  private audioTrack: AudioTrack;
  private resourcePool: ResourcePool;
  
  private onQueueEmpty?: () => void;
  
  // 叙事锁：控制叙事事件之间的阻塞
  private narrativeLock: Promise<void> = Promise.resolve();
  
  // 用户配置
  private afmEnabled = true;
  private afmDelay = 500;
  private choiceTimeout = 30;  // 选项超时时间（秒）

  constructor(options: NarrativeQueueOptions) {
    this.textTrack = options.textTrack;
    this.visualTrack = options.visualTrack;
    this.audioTrack = options.audioTrack;
    this.resourcePool = options.resourcePool;
  }

  /**
   * 入队事件
   */
  enqueue(event: SSEEvent): void {
    this.queue.push(event);
    
    if (!this.isProcessing && !this.isPaused) {
      this.processNext();
    }
  }

  /**
   * 处理下一个事件（递归调用）
   */
  private processNext(): void {
    if (this.queue.length === 0 || this.isPaused) {
      this.isProcessing = false;
      this.onQueueEmpty?.();
      return;
    }
    
    this.isProcessing = true;
    const event = this.queue.shift()!;
    const metadata = EVENT_REGISTRY[event.event_type];
    
    if (!metadata) {
      console.warn(`未知事件类型: ${event.event_type}`);
      this.processNext();
      return;
    }
    
    if (metadata.narrative) {
      // 叙事事件：等待叙事锁释放后执行
      this.narrativeLock.then(() => {
        // 执行事件（可能涉及多个轨道：文本+语音+图像）
        this.dispatchEvent(event);
        
        // 创建新的叙事锁，等待用户点击/AFM
        this.narrativeLock = this.waitForNarrativeComplete(event);
        
        // 叙事锁释放后，继续处理下一个
        this.narrativeLock.then(() => this.processNext());
      });
    } else {
      // 非叙事事件：直接执行，立即处理下一个
      this.dispatchEvent(event);
      this.processNext();
    }
  }

  /**
   * 分发事件：遍历事件中的资源，根据资源类型分发到对应轨道
   * 事件不需要知道有哪些轨道，只需要定义有哪些资源
   */
  private dispatchEvent(event: SSEEvent): void {
    const content = event.content;
    
    // 遍历资源，根据资源类型分发到对应轨道
    // 文本资源 → TextTrack
    if (content.text !== undefined) {
      if (content.character_name) {
        this.textTrack.showDialogue(content.character_name, content.text, content.character_color);
      } else {
        this.textTrack.showNarration(content.text);
      }
    }
    
    // 选项资源 → TextTrack
    if (content.options) {
      this.textTrack.showChoice(content.prompt, content.options);
    }
    
    // 语音资源 → AudioTrack
    if (content.voice?.url) {
      this.audioTrack.playVoice(content.voice);
    }
    
    // 角色展示资源 → VisualTrack（支持静态图、动图、视频）
    if (content.show?.url) {
      this.visualTrack.showCharacter(content.character_id, content.show);
    }
    
    // 背景资源 → VisualTrack
    if (content.background?.url) {
      this.visualTrack.setScene(content.background);
    }
    
    // 音乐资源 → AudioTrack（scene_start 中的 music）
    if (content.music?.url) {
      this.audioTrack.playMusic(content.music);
    }
    
    // 环境音资源 → AudioTrack（scene_start 中的 ambient）
    if (content.ambient?.url) {
      this.audioTrack.playAmbient(content.ambient);
    }
    
    // play_audio 事件：根据 channel 分发到对应播放器
    if (content.audio?.url) {
      const channel = content.channel || 'sound';
      switch (channel) {
        case 'music':
          this.audioTrack.playMusic(content.audio);
          break;
        case 'ambient':
          this.audioTrack.playAmbient(content.audio);
          break;
        case 'sound':
        default:
          this.audioTrack.playSound(content.audio);
          break;
      }
    }
    
    // 视频资源 → VisualTrack (play_video事件，视觉轨道内替换式播放，不阻塞叙事队列)
    if (event.event_type === 'play_video' && content.video?.url) {
      this.visualTrack.playVideo(content.video.url);  // 不使用 await，不阻塞叙事队列
    }
    
    // 显示/隐藏元素
    if (content.element && event.event_type === 'show') {
      this.visualTrack.showElement(content.layer, content.element);
    }
    if (content.element_id && event.event_type === 'hide') {
      this.visualTrack.hideElement(content.layer, content.element_id);
    }
    
    // 场景结束
    if (event.event_type === 'scene_end') {
      this.visualTrack.endScene(content.transition);
    }
    
    // 停止音频
    if (event.event_type === 'stop_audio') {
      this.audioTrack.stop(content.channel, content.fade_out);
    }
  }


  /**
   * 等待叙事事件完成（AFM 或用户点击）
   */
  private async waitForNarrativeComplete(event: SSEEvent): Promise<void> {
    if (event.event_type === 'choice') {
      // 选项：等待用户选择（带超时）
      const defaultOptionId = event.content.options[0]?.option_id;
      const selectedOptionId = await this.textTrack.waitForChoice(this.choiceTimeout, defaultOptionId);
      
      // 获取选中选项的 next_sequence_id（分支跳转）
      const selectedOption = event.content.options.find(
        o => o.option_id === selectedOptionId
      );
      
      if (selectedOption?.next_sequence_id) {
        // 通知 DataManager 准备接收新分支的事件
        // SSE 流会根据 choice 自动推送对应分支的事件
        console.log(`分支跳转: ${selectedOptionId} → ${selectedOption.next_sequence_id}`);
        
        // 保存用户选择到服务端
        await this.saveUserChoice(event.content.story_id, selectedOptionId);
      }
    } else {
      // 对话/旁白：AFM 或用户点击
      await this.waitForAdvance(event);
    }
    
    // 事件结束清理
    this.cleanupAfterEvent(event);
  }
  
  /**
   * 保存用户选择
   */
  private async saveUserChoice(storyId: string, choiceId: string): Promise<void> {
    try {
      await fetch(`/api/v1/story/${storyId}/choice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ option_id: optionId })
      });
    } catch (error) {
      console.error('保存用户选择失败:', error);
    }
  }

  /**
   * 等待推进（AFM 或用户点击）
   */
  private async waitForAdvance(event: SSEEvent): Promise<void> {
    const hasVoice = !!event.content?.voice?.url;
    
    if (this.afmEnabled && hasVoice) {
      // AFM 模式：等待语音播完 + 延迟
      await this.audioTrack.waitForVoiceComplete();
      await this.sleep(this.afmDelay);
    } else {
      // 手动模式：等待用户点击
      await this.textTrack.waitForClick();
    }
  }

  /**
   * 事件结束后清理
   */
  private cleanupAfterEvent(event: SSEEvent): void {
    // 停止语音
    this.audioTrack.stopVoice();
    
    // 隐藏角色图像（如果设置了 auto_hide）
    if (event.event_type === 'dialogue' && event.content?.auto_hide !== false) {
      this.visualTrack.hideCharacter(event.content.character_id);
    }
    
    // 清除文本
    this.textTrack.clear();
  }

  /**
   * 暂停队列
   */
  pause(): void {
    this.isPaused = true;
  }

  /**
   * 恢复队列
   */
  resume(): void {
    this.isPaused = false;
    if (!this.isProcessing && this.queue.length > 0) {
      this.process();
    }
  }

  /**
   * 设置队列空回调
   */
  setOnQueueEmpty(callback: () => void): void {
    this.onQueueEmpty = callback;
  }

  /**
   * 设置 AFM 配置
   */
  setAFM(enabled: boolean, delay: number = 500): void {
    this.afmEnabled = enabled;
    this.afmDelay = delay;
  }

  /**
   * 设置菜单超时时间
   */
  setMenuTimeout(timeout: number): void {
    this.choiceTimeout = timeout;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

---

### 0.3 ProgressTracker - 进度同步

**职责**：管理用户播放进度，采用延迟同步策略优化性能

**设计原则**：
- ❌ **不是每次点击都同步**：避免高频写入带来的性能问题
- ✅ **关键点同步**：仅在 `choice`、`scene_start`、`chapter_start`、`story_end` 时同步
- ✅ **退出时同步**：用户关闭页面时通过 `sendBeacon` 保存进度

**性能对比**：

| 策略 | 每秒写入量（1000并发用户） |
|------|--------------------------|
| 每次点击都写 | ~200 次/秒 |
| 关键点 + 退出时同步 | ~10-20 次/秒 |

```typescript
class ProgressTracker {
  private storyId: string;
  private versionId: string;
  private lastSyncedSequenceId: string = '';
  private currentSequenceId: string = '';
  
  // 关键事件类型（触发同步）
  private readonly SYNC_EVENTS = new Set([
    'choice', 'scene_start', 'chapter_start', 'story_end'
  ]);
  
  constructor(storyId: string, versionId: string) {
    this.storyId = storyId;
    this.versionId = versionId;
    
    // 注册页面卸载事件
    window.addEventListener('beforeunload', () => this.onBeforeUnload());
    window.addEventListener('pagehide', () => this.onBeforeUnload());
  }
  
  /**
   * 事件播放完成时调用
   */
  onEventPlayed(event: SSEEvent): void {
    this.currentSequenceId = event.sequence_id;
    
    // 关键点同步
    if (this.SYNC_EVENTS.has(event.event_type)) {
      this.syncToServer();
    }
  }
  
  /**
   * 同步进度到服务器
   */
  private async syncToServer(): Promise<void> {
    if (this.currentSequenceId === this.lastSyncedSequenceId) return;
    
    try {
      await fetch(`/api/v1/story/${this.storyId}/progress`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version_id: this.versionId,
          current_sequence_id: this.currentSequenceId
        })
      });
      
      this.lastSyncedSequenceId = this.currentSequenceId;
    } catch (error) {
      console.warn('Progress sync failed:', error);
      // 失败不阻塞，下次关键点会重试
    }
  }
  
  /**
   * 页面卸载时同步（使用 sendBeacon 确保可靠发送）
   */
  private onBeforeUnload(): void {
    if (this.currentSequenceId === this.lastSyncedSequenceId) return;
    
    // sendBeacon 在页面卸载时仍能可靠发送
    const success = navigator.sendBeacon(
      `/api/v1/story/${this.storyId}/progress`,
      JSON.stringify({
        version_id: this.versionId,
        current_sequence_id: this.currentSequenceId
      })
    );
    
    if (success) {
      this.lastSyncedSequenceId = this.currentSequenceId;
    }
  }
  
  /**
   * 更新当前版本（用户做选择后切换到新版本）
   */
  setVersion(versionId: string): void {
    this.versionId = versionId;
  }
  
  /**
   * 清理资源
   */
  destroy(): void {
    window.removeEventListener('beforeunload', () => this.onBeforeUnload());
    window.removeEventListener('pagehide', () => this.onBeforeUnload());
  }
}
```

**使用示例**：

```typescript
// 初始化
const progressTracker = new ProgressTracker(storyId, versionId);

// NarrativeQueue 播放事件后调用
narrativeQueue.onEventComplete = (event) => {
  progressTracker.onEventPlayed(event);
};

// 用户做选择后，切换到新版本
progressTracker.setVersion(newVersionId);
```

> **注意**：采用延迟同步策略后，用户在两个关键点之间断开可能丢失少量进度（最多回退到上一个场景/章节起点）。对于互动叙事场景，这是可接受的体验。

---

### 1. ResourcePool - 资源池

**职责**：异步下载和缓存所有媒体资源（图像、视频、音频）

**特性**：
- 并发控制：最多同时下载 N 个资源（可配置，默认 6）
- 自动重试：下载失败自动重试（最多 3 次）
- 容错处理：下载失败不阻塞叙事，返回 null

```typescript
type ResourceType = 'image' | 'video' | 'audio';

interface DownloadTask {
  url: string;
  type: ResourceType;
  resolve: (value: any) => void;
  reject: (error: any) => void;
}

class ResourcePool {
  private loadedResources: Map<string, any> = new Map();
  private loadingPromises: Map<string, Promise<any>> = new Map();
  
  // 并发控制
  private maxConcurrent: number;
  private activeCount = 0;
  private queue: DownloadTask[] = [];
  
  // 重试配置
  private maxRetries = 3;

  constructor(options: { maxConcurrent?: number } = {}) {
    this.maxConcurrent = options.maxConcurrent ?? 6;
  }

  /**
   * 下载资源（自动排队、重试、容错）
   */
  async download(url: string, type: ResourceType): Promise<any> {
    // 已加载，直接返回
    if (this.loadedResources.has(url)) {
      return this.loadedResources.get(url);
    }

    // 正在加载，复用 Promise
    if (this.loadingPromises.has(url)) {
      return this.loadingPromises.get(url)!;
    }

    // 加入下载队列
    const promise = new Promise<any>((resolve, reject) => {
      this.queue.push({ url, type, resolve, reject });
    });
    
    this.loadingPromises.set(url, promise);
    this.processQueue();
    
    return promise;
  }

  /**
   * 处理下载队列
   */
  private processQueue(): void {
    while (this.activeCount < this.maxConcurrent && this.queue.length > 0) {
      const task = this.queue.shift()!;
      this.activeCount++;
      
      this.downloadWithRetry(task.url, task.type)
        .then(resource => {
          this.loadedResources.set(task.url, resource);
          task.resolve(resource);
        })
        .catch(error => {
          console.warn(`资源下载失败（已重试${this.maxRetries}次）: ${task.url}`);
          task.resolve(null);  // 失败返回 null，不阻塞叙事
        })
        .finally(() => {
          this.loadingPromises.delete(task.url);
          this.activeCount--;
          this.processQueue();
        });
    }
  }

  /**
   * 带重试的下载
   */
  private async downloadWithRetry(url: string, type: ResourceType): Promise<any> {
    let lastError: Error | null = null;
    
    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await this.doDownload(url, type);
      } catch (error) {
        lastError = error as Error;
        console.warn(`资源下载失败（第${attempt}次）: ${url}`);
        
        if (attempt < this.maxRetries) {
          // 指数退避：1s, 2s, 4s...
          await this.sleep(1000 * Math.pow(2, attempt - 1));
        }
      }
    }
    
    throw lastError;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private async doDownload(url: string, type: ResourceType): Promise<any> {
    switch (type) {
      case 'image':
        return new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = () => reject(new Error(`图像加载失败: ${url}`));
          img.src = url;
        });

      case 'video':
        return new Promise((resolve, reject) => {
          const video = document.createElement('video');
          video.preload = 'auto';
          video.muted = true;
          video.playsInline = true;
          video.crossOrigin = 'anonymous';
          video.addEventListener('canplaythrough', () => resolve(video), { once: true });
          video.addEventListener('error', () => reject(new Error(`视频加载失败: ${url}`)), { once: true });
          video.src = url;
        });

      case 'audio':
        return new Promise((resolve, reject) => {
          const audio = new Audio();
          audio.preload = 'auto';
          audio.addEventListener('canplaythrough', () => resolve(audio), { once: true });
          audio.addEventListener('error', () => reject(new Error(`音频加载失败: ${url}`)), { once: true });
          audio.src = url;
        });

      default:
        throw new Error(`未知资源类型: ${type}`);
    }
  }

  /**
   * 等待资源就绪
   * 返回资源或 null（如果下载失败）
   */
  async waitFor(url: string): Promise<any> {
    if (this.loadedResources.has(url)) {
      return this.loadedResources.get(url);
    }
    if (this.loadingPromises.has(url)) {
      return this.loadingPromises.get(url);
    }
    // 资源未在队列中，返回 null
    console.warn(`资源未预加载: ${url}`);
    return null;
  }
}
```

---

### 2. NarrativeEventParser - 叙事事件解析器

**职责**：将叙事事件解析为原子操作 + 资源列表 + 清理规则

```typescript
interface ParsedEvent {
  operations: AtomicOperation[];
  resources: Array<{ url: string; type: 'image' | 'audio'; key: string }>;
  cleanup?: {
    on_complete: AtomicOperation[];
  };
}

class NarrativeEventParser {
  parse(event: NarrativeEvent): ParsedEvent {
    switch (event.event_type) {
      case 'story_start':
        return this.parseStoryStart(event);
      case 'story_end':
        return this.parseStoryEnd(event);
      case 'chapter_start':
        return this.parseChapterStart(event);
      case 'chapter_end':
        return this.parseChapterEnd(event);
      case 'scene_start':
        return this.parseSceneStart(event);
      case 'scene_end':
        return this.parseSceneEnd(event);
      case 'play_audio':
        return this.parsePlaySound(event);
      case 'narration':
        return this.parseNarration(event);
      case 'dialogue':
        return this.parseDialogue(event);
      case 'choice':
        return this.parseMenu(event);
      default:
        throw new Error(`未知事件类型: ${event.event_type}`);
    }
  }

  /**
   * 解析 story_start 事件
   */
  private parseStoryStart(event: StoryStartEvent): ParsedEvent {
    // 显示故事标题等信息
    return {
      operations: [
        { type: 'show_story_title', title: event.content.title, theme: event.content.theme }
      ],
      resources: []
    };
  }

  /**
   * 解析 story_end 事件
   */
  private parseStoryEnd(event: StoryEndEvent): ParsedEvent {
    // 显示故事结束信息
    return {
      operations: [
        { type: 'show_ending', message: event.content.message }
      ],
      resources: []
    };
  }

  /**
   * 解析 chapter_start 事件
   */
  private parseChapterStart(event: ChapterStartEvent): ParsedEvent {
    // 显示章节标题
    return {
      operations: [
        { type: 'show_chapter_title', title: event.content.title, chapter_number: event.content.chapter_number }
      ],
      resources: []
    };
  }

  /**
   * 解析 chapter_end 事件
   */
  private parseChapterEnd(event: ChapterEndEvent): ParsedEvent {
    // 显示章节结束信息
    return {
      operations: [
        { type: 'show_chapter_end', message: event.content.message }
      ],
      resources: []
    };
  }

  /**
   * 解析 scene_start 事件
   */
  private parseSceneStart(event: SceneStartEvent): ParsedEvent {
    const operations = [];
    const resources = [];

    // 清理操作
    operations.push({ type: 'stop', channel: 'music' });
    operations.push({ type: 'stop', channel: 'sound', sound_type: 'ambient' });
    operations.push({ type: 'hide_all' });

    // 显示背景
    operations.push({
      type: 'show',
      element_id: `bg_${event.content.scene_id}`,
      element_type: 'background',
      url: event.content.background.url,
      key: `bg_${event.content.scene_id}`
    });
    resources.push({
      url: event.content.background.url,
      type: 'image',
      key: `bg_${event.content.scene_id}`
    });

    // 获取转场淡入时间
    const fadeInDuration = event.content.transition?.duration;

    // 播放音乐
    if (event.content.music) {
      operations.push({
        type: 'play',
        channel: 'music',
        url: event.content.music.url,
        key: `music_${event.content.scene_id}`
      });
      resources.push({
        url: event.content.music.url,
        type: 'audio',
        key: `music_${event.content.scene_id}`
      });
    }

    // 播放环境音
    if (event.content.ambient) {
      operations.push({
        type: 'play',
        channel: 'ambient',
        url: event.content.ambient.url,
        key: `ambient_${event.content.scene_id}`
      });
      resources.push({
        url: event.content.ambient.url,
        type: 'audio',
        key: `ambient_${event.content.scene_id}`
      });
    }

    return { operations, resources };
  }

  /**
   * 解析 dialogue 事件
   * 
   * 支持角色图像类型：
   * - 静态图像：PNG/JPG/WebP
   * - 动态图像：GIF/APNG/WebP动画
   * - 视频角色：透明WebM（通过URL扩展名自动判断）
   */
  private parseDialogue(event: DialogueEvent): ParsedEvent {
    const operations = [];
    const resources = [];

    // 显示角色（支持静态图、动图、视频）
    if (event.content.show) {
      // 通过URL扩展名判断是否为视频
      const isVideo = this.isVideoUrl(event.content.show.url);
      
      operations.push({
        type: 'show',
        element_id: event.content.character_id,
        element_type: 'character',
        url: event.content.show.url,
        position: event.content.show.position,
        // 视频特有属性（仅当有video_config时使用）
        ...(event.content.show.video_config && {
          loop: event.content.show.video_config.loop ?? true,
          muted: event.content.show.video_config.muted ?? true,
          autoplay: event.content.show.video_config.autoplay ?? true,
        }),
        key: `char_${event.content.character_id}`
      });
      
      // 根据URL扩展名判断资源类型
      resources.push({
        url: event.content.show.url,
        type: isVideo ? 'video' : 'image',
        key: `char_${event.content.character_id}`
      });
    }

    // 播放配音
    if (event.content.voice) {
      operations.push({
        type: 'play',
        channel: 'voice',
        url: event.content.voice.url,
        key: `voice_${event.sequence_id}`
      });
      resources.push({
        url: event.content.voice.url,
        type: 'audio',
        key: `voice_${event.sequence_id}`
      });
    }

    // 显示文字
    operations.push({
      type: 'say',
      role: event.content.character_name,
      content: event.content.text,
      roleColor: event.content.character_color,
      voice_duration: event.content.voice?.duration
      // AFM 参数由全局设置提供，见 executeAtomicOperation
    });

    // 清理规则
    const cleanup = {
      on_complete: [
        { type: 'stop', channel: 'voice' },
        ...(event.content.auto_hide !== false && event.content.show
          ? [{ type: 'hide', element_id: event.content.character_id }]
          : [])
      ]
    };

    return { operations, resources, cleanup };
  }

  /**
   * 通过URL扩展名判断是否为视频
   */
  private isVideoUrl(url: string): boolean {
    const videoExtensions = ['.webm', '.mp4', '.ogv'];
    const urlLower = url.toLowerCase();
    return videoExtensions.some(ext => urlLower.includes(ext));
  }

  /**
   * 解析 narration 事件
   */
  private parseNarration(event: NarrationEvent): ParsedEvent {
    const operations = [];
    const resources = [];

    // 播放配音
    if (event.content.voice) {
      operations.push({
        type: 'play',
        channel: 'voice',
        url: event.content.voice.url,
        key: `voice_${event.sequence_id}`
      });
      resources.push({
        url: event.content.voice.url,
        type: 'audio',
        key: `voice_${event.sequence_id}`
      });
    }

    // 显示文字
    operations.push({
      type: 'say',
      role: undefined,
      content: event.content.text,
      voice_duration: event.content.voice?.duration
      // AFM 参数由全局设置提供
    });

    // 清理规则
    const cleanup = {
      on_complete: [{ type: 'stop', channel: 'voice' }]
    };

    return { operations, resources, cleanup };
  }

  /**
   * 解析 play_audio 事件
   */
  private parsePlaySound(event: PlaySoundEvent): ParsedEvent {
    const channel = event.content.channel || 'sound';
    
    const operations = [{
      type: 'play',
      channel: channel,
      url: event.content.url,
      key: `${channel}_${event.sequence_id}`
    }];

    const resources = [{
      url: event.content.url,
      type: 'audio',
      key: `${channel}_${event.sequence_id}`
    }];

    // sound 通道播放完自动停止，music/ambient 循环播放不清理
    const cleanup = channel === 'sound'
      ? undefined  // sound 播放完自动从池中移除，无需清理
      : undefined;

    return { operations, resources, cleanup };
  }
}
```

---

### 3. TextTrack - 文本轨道

**职责**：处理文本渲染（对话/旁白/菜单），提供打字机效果和用户交互

**阻塞规则**：文本替换式播放（新文本替换旧文本，同一时刻只显示一段）

```typescript
interface TextContent {
  speaker?: string;
  speakerColor?: string;
  text: string;
}

interface MenuChoice {
  option_id: string;
  text: string;
}

class TextTrack {
  private container: HTMLElement;
  private speakerElement: HTMLElement;
  private textElement: HTMLElement;
  private optionsContainer: HTMLElement;
  
  // 配置
  private textSpeed = 50;  // 每字符毫秒数
  
  // 交互 Promise
  private clickResolver?: () => void;
  private choiceResolver?: (choiceId: string) => void;
  
  // 中断控制
  private currentAbortController: AbortController | null = null;

  constructor(container: HTMLElement) {
    this.container = container;
    this.speakerElement = container.querySelector('.speaker')!;
    this.textElement = container.querySelector('.text')!;
    this.optionsContainer = container.querySelector('.options')!;
    
    // 绑定点击事件
    this.container.addEventListener('click', () => this.onClick());
  }

  /**
   * 显示对话文本
   */
  async showDialogue(character: string, text: string, color?: string): Promise<void> {
    this.speakerElement.textContent = character;
    if (color) {
      this.speakerElement.style.color = color;
    }
    await this.typeText(text);
  }

  /**
   * 显示旁白文本
   */
  async showNarration(text: string): Promise<void> {
    this.speakerElement.textContent = '';
    await this.typeText(text);
  }

  /**
   * 显示选项
   */
  showChoice(prompt: string, options: ChoiceOption[]): void {
    this.textElement.textContent = prompt;
    this.optionsContainer.innerHTML = '';
    
    options.forEach(option => {
      const btn = document.createElement('button');
      btn.textContent = option.text;
      btn.className = 'option-button';
      btn.onclick = () => this.onOptionSelected(option.option_id);
      this.optionsContainer.appendChild(btn);
    });
    
    this.optionsContainer.style.display = 'block';
  }

  /**
   * 等待用户选择（菜单）
   * 
   * @param timeout 超时时间（秒），来自用户设置
   * @param defaultOptionId 默认选项ID（通常是 options[0].option_id）
   */
  waitForChoice(timeout: number, defaultOptionId: string): Promise<string> {
    return new Promise(resolve => {
      this.choiceResolver = resolve;
      
      // 设置超时自动选择
      setTimeout(() => {
        if (this.choiceResolver) {
          console.log(`⏱️ 菜单超时，自动选择默认选项: ${defaultChoiceId}`);
          this.choiceResolver(defaultChoiceId);
          this.choiceResolver = undefined;
        }
      }, timeout * 1000);
    });
  }

  /**
   * 等待用户点击
   */
  waitForClick(): Promise<void> {
    return new Promise(resolve => {
      this.clickResolver = resolve;
    });
  }

  /**
   * 清除文本
   */
  clear(): void {
    this.speakerElement.textContent = '';
    this.textElement.textContent = '';
    this.optionsContainer.innerHTML = '';
    this.optionsContainer.style.display = 'none';
  }

  /**
   * 跳过当前打字效果
   */
  skip(): void {
    if (this.currentAbortController) {
      this.currentAbortController.abort();
    }
  }

  /**
   * 设置文字速度
   */
  setTextSpeed(msPerChar: number): void {
    this.textSpeed = msPerChar;
  }

  /**
   * 打字机效果
   */
  private async typeText(text: string): Promise<void> {
    this.textElement.textContent = '';
    this.currentAbortController = new AbortController();
    const signal = this.currentAbortController.signal;
    
    for (let i = 0; i < text.length; i++) {
      if (signal.aborted) {
        // 被跳过，立即显示全部文本
        this.textElement.textContent = text;
        break;
      }
      
      this.textElement.textContent += text[i];
      await this.sleep(this.textSpeed);
    }
    
    this.currentAbortController = null;
  }

  /**
   * 点击事件处理
   */
  private onClick(): void {
    if (this.currentAbortController) {
      // 正在打字，跳过
      this.skip();
    } else if (this.clickResolver) {
      // 等待点击，触发
      this.clickResolver();
      this.clickResolver = undefined;
    }
  }

  /**
   * 选项选择事件处理
   */
  private onChoiceSelected(choiceId: string): void {
    if (this.choiceResolver) {
      this.choiceResolver(choiceId);
      this.choiceResolver = undefined;
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

---

### 4. VisualTrack - 视觉轨道

**职责**：处理视觉元素（场景、角色图像、视频）

**阻塞规则**：
| 资源类型 | 阻塞行为 |
|---------|---------|
| 场景 | 替换式 |
| 图像 | 图层叠加，不阻塞 |
| 视频 | 阻塞直到播放完成 |

```typescript
interface ImageConfig {
  url: string;
  position?: 'left' | 'center' | 'right';
  expression?: string;
  // 视频角色配置（可选，仅当角色为视频时提供）
  video_config?: {
    loop?: boolean;      // 是否循环播放，默认 true
    muted?: boolean;     // 是否静音，默认 true
    autoplay?: boolean;  // 是否自动播放，默认 true
  };
}

class VisualTrack {
  private resourcePool: ResourcePool;
  private layerManager: LayerManager;
  
  // 当前显示的角色图像（用于自动隐藏）
  private characterImages: Map<string, string> = new Map();

  constructor(resourcePool: ResourcePool, layerManager: LayerManager) {
    this.resourcePool = resourcePool;
    this.layerManager = layerManager;
  }

  /**
   * 设置场景背景（替换式）
   */
  async setScene(background: { url: string; transition?: any }): Promise<void> {
    console.log('🎬 设置场景');
    
    // 清理旧场景
    this.layerManager.hideAll();
    this.characterImages.clear();
    
    // 等待背景资源
    const bg = await this.resourcePool.waitFor(background.url);
    if (!bg) {
      console.warn('背景资源未加载');
      return;
    }
    
    // 显示新背景
    await this.layerManager.showElement('background', bg, {
      layer: 'background',
      transition: background.transition
    });
  }

  /**
   * 结束场景
   * @param transition 转场配置（type: fade_out, duration: 秒）
   */
  async endScene(transition?: { type: string; duration: number }): Promise<void> {
    console.log('🎬 结束场景');
    
    // 使用 hideElement 隐藏背景，支持可配置的转场时长
    await this.layerManager.hideElement('background', transition);
  }

  /**
   * 显示角色图像（图层叠加，不阻塞）
   */
  async showCharacter(characterId: string, image: ImageConfig): Promise<void> {
    console.log(`🎭 显示角色: ${characterId}`);
    
    const elementId = `${characterId}_${image.expression || 'default'}`;
    
    const resource = await this.resourcePool.waitFor(image.url);
    if (!resource) {
      console.warn(`角色图像未加载: ${characterId}`);
      return;
    }
    
    // 记录当前角色的图像
    this.characterImages.set(characterId, elementId);
    
    await this.layerManager.showElement(elementId, resource, {
      layer: 'characters',
      position: image.position || 'center',
      // 如果有video_config，传递视频配置
      ...(image.video_config && {
        loop: image.video_config.loop ?? true,
        muted: image.video_config.muted ?? true,
        autoplay: image.video_config.autoplay ?? true
      })
    });
  }

  /**
   * 隐藏角色图像
   */
  async hideCharacter(characterId: string): Promise<void> {
    const elementId = this.characterImages.get(characterId);
    if (elementId) {
      await this.layerManager.hideElement(elementId);
      this.characterImages.delete(characterId);
    }
  }

  /**
   * 显示通用元素
   */
  async showElement(layer: string, element: any): Promise<void> {
    const resource = await this.resourcePool.waitFor(element.url);
    if (!resource) return;
    
    await this.layerManager.showElement(element.id, resource, {
      layer,
      position: element.position
    });
  }

  /**
   * 隐藏元素
   */
  async hideElement(layer: string, elementId: string): Promise<void> {
    await this.layerManager.hideElement(elementId);
  }

  /**
   * 播放视频（阻塞直到完成）
   */
  async playVideo(url: string): Promise<void> {
    console.log('🎬 播放视频');
    
    const video = await this.resourcePool.waitFor(url);
    if (!video) {
      console.warn('视频资源未加载');
      return;
    }
    
    // 显示视频
    await this.layerManager.showElement('video-player', video, {
      layer: 'video',
      mediaType: 'video'
    });
    
    // 等待播放完成
    await new Promise<void>(resolve => {
      video.play();
      video.addEventListener('ended', () => {
        this.layerManager.hideElement('video-player');
        resolve();
      }, { once: true });
    });
  }
}
```

---

### 5. AudioTrack - 音频轨道

**职责**：多通道音频管理（语音、音乐、音效、环境音）

**通道规则**（由全局配置控制）：
| 通道 | 播放模式 | 循环 | 音量来源 | 说明 |
|------|---------|------|----------|------|
| voice | 替换式 | 否 | voice_volume | 新语音停止旧语音 |
| music | 替换式 | 是 | music_volume | 背景音乐，循环播放 |
| ambient | 替换式 | 是 | ambient_volume | 环境音，循环播放 |
| sound | 多重播放 | 否 | sound_volume | 可同时播放多个音效 |

**全局配置**（从用户设置读取）：
```typescript
interface AudioGlobalConfig {
  voice_volume: number;    // 配音音量，默认 1.0
  music_volume: number;    // 音乐音量，默认 0.7
  sound_volume: number;    // 音效音量，默认 1.0
  ambient_volume: number;  // 环境音音量，默认 0.7
}
```

**说明**：
- 事件中不再包含 `volume` 和 `loop` 参数
- 音量和循环播放规则由前端全局配置和通道类型决定
- 用户可通过设置界面调整各通道音量

```typescript
interface AudioConfig {
  url: string;
}

class AudioTrack {
  // 全局音量配置
  private volumeConfig: AudioGlobalConfig;
  
  private resourcePool: ResourcePool;
  
  // 单播通道（替换式）
  private singleChannels: Map<string, HTMLAudioElement> = new Map();
  
  // 音效池（多重播放）
  private soundPool: Set<HTMLAudioElement> = new Set();
  
  // 语音完成 Promise
  private voiceEndResolver?: () => void;

  constructor(resourcePool: ResourcePool, volumeConfig: AudioGlobalConfig) {
    this.resourcePool = resourcePool;
    this.volumeConfig = volumeConfig;
  }

  /**
   * 更新音量配置
   */
  updateVolumeConfig(config: AudioGlobalConfig): void {
    this.volumeConfig = config;
    
    // 更新当前播放中的音频音量
    this.singleChannels.forEach((audio, channel) => {
      switch (channel) {
        case 'voice':
          audio.volume = config.voice_volume;
          break;
        case 'music':
          audio.volume = config.music_volume;
          break;
        case 'ambient':
          audio.volume = config.ambient_volume || config.sound_volume;
          break;
      }
    });
  }

  /**
   * 播放语音（替换式）
   */
  async playVoice(voice: AudioConfig): Promise<void> {
    console.log('🎤 播放语音');
    
    // 停止当前语音
    this.stopVoice();
    
    const audio = await this.resourcePool.waitFor(voice.url);
    if (!audio) return;
    
    audio.volume = this.volumeConfig.voice_volume;
    this.singleChannels.set('voice', audio);
    
    // 语音结束回调
    audio.addEventListener('ended', () => {
      if (this.voiceEndResolver) {
        this.voiceEndResolver();
        this.voiceEndResolver = undefined;
      }
    }, { once: true });
    
    audio.play();
  }

  /**
   * 等待语音播放完成
   */
  waitForVoiceComplete(): Promise<void> {
    const voice = this.singleChannels.get('voice');
    if (!voice || voice.ended) {
      return Promise.resolve();
    }
    
    return new Promise(resolve => {
      this.voiceEndResolver = resolve;
    });
  }

  /**
   * 停止语音
   */
  stopVoice(): void {
    this.stopChannel('voice');
  }

  /**
   * 播放背景音乐（替换式，循环）
   */
  async playMusic(music: AudioConfig): Promise<void> {
    console.log('🎵 播放音乐');
    
    this.stopChannel('music');
    
    const audio = await this.resourcePool.waitFor(music.url);
    if (!audio) return;
    
    audio.volume = this.volumeConfig.music_volume;
    audio.loop = true;
    this.singleChannels.set('music', audio);
    
    audio.play();
  }

  /**
   * 播放环境音（替换式，循环）
   */
  async playAmbient(ambient: AudioConfig): Promise<void> {
    console.log('🌿 播放环境音');
    
    this.stopChannel('ambient');
    
    const audio = await this.resourcePool.waitFor(ambient.url);
    if (!audio) return;
    
    audio.volume = this.volumeConfig.ambient_volume;
    audio.loop = true;
    this.singleChannels.set('ambient', audio);
    
    audio.play();
  }

  /**
   * 播放音效（多重播放，即发即忘）
   */
  async playSound(sound: AudioConfig): Promise<void> {
    console.log('🔊 播放音效');
    
    const audio = await this.resourcePool.waitFor(sound.url);
    if (!audio) return;
    
    // 克隆音频元素以支持多重播放
    const clone = audio.cloneNode() as HTMLAudioElement;
    clone.volume = this.volumeConfig.sound_volume;
    clone.loop = false;  // 音效不循环
    
    this.soundPool.add(clone);
    
    clone.addEventListener('ended', () => {
      this.soundPool.delete(clone);
    }, { once: true });
    
    clone.play();
  }

  /**
   * 停止通道
   */
  stop(channel: string, fadeOut?: number): void {
    if (channel === 'sound') {
      // 停止所有音效
      this.soundPool.forEach(audio => {
        this.stopAudio(audio, fadeOut);
      });
      this.soundPool.clear();
    } else {
      this.stopChannel(channel, fadeOut);
    }
  }

  /**
   * 停止单播通道
   */
  private stopChannel(channel: string, fadeOut?: number): void {
    const audio = this.singleChannels.get(channel);
    if (audio) {
      this.stopAudio(audio, fadeOut);
      this.singleChannels.delete(channel);
    }
  }

  /**
   * 停止单个音频
   */
  private async stopAudio(audio: HTMLAudioElement, fadeOut?: number): Promise<void> {
    if (fadeOut && fadeOut > 0) {
      await this.fadeOut(audio, fadeOut);
    }
    audio.pause();
    audio.currentTime = 0;
  }

  /**
   * 淡入效果
   * @param audio 音频元素
   * @param duration 持续时间（秒）
   */
  private async fadeIn(audio: HTMLAudioElement, duration?: number): Promise<void> {
    if (!duration || duration <= 0) return;
    
    const targetVolume = audio.volume;
    audio.volume = 0;
    
    const steps = 20;
    const stepTime = (duration * 1000) / steps;  // 转换为毫秒
    const stepVolume = targetVolume / steps;
    
    for (let i = 0; i < steps; i++) {
      await this.sleep(stepTime);
      audio.volume = Math.min(audio.volume + stepVolume, targetVolume);
    }
  }

  /**
   * 淡出效果
   * @param audio 音频元素
   * @param duration 持续时间（秒）
   */
  private async fadeOut(audio: HTMLAudioElement, duration: number): Promise<void> {
    const startVolume = audio.volume;
    const steps = 20;
    const stepTime = (duration * 1000) / steps;  // 转换为毫秒
    const stepVolume = startVolume / steps;
    
    for (let i = 0; i < steps; i++) {
      await this.sleep(stepTime);
      audio.volume = Math.max(audio.volume - stepVolume, 0);
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

---

## 原子组件

### LayerManager - 图层管理

**支持图像和视频角色的显示/隐藏**

```typescript
interface TransitionOptions {
  type?: 'fade_in' | 'fade_out' | 'none';
  duration?: number;  // 秒，默认 0.3s
}

interface ShowElementOptions {
  layer?: 'background' | 'characters' | 'effects';  // 图层类型
  position?: 'left' | 'center' | 'right';
  mediaType?: 'image' | 'animated_image' | 'video';
  loop?: boolean;
  muted?: boolean;
  autoplay?: boolean;
  transition?: TransitionOptions;
}

class LayerManager {
  private layers: Map<string, HTMLElement> = new Map();

  /**
   * 显示元素（图像或视频角色）
   * @param elementId 元素ID
   * @param element 图像或视频元素
   * @param options 显示选项
   */
  async showElement(
    elementId: string,
    element: HTMLImageElement | HTMLVideoElement,
    options: ShowElementOptions = {}
  ): Promise<void> {
    const container = document.getElementById('layer-container');
    const { 
      position = 'center', 
      mediaType, 
      loop = true, 
      muted = true, 
      autoplay = true,
      transition = { type: 'fade_in', duration: 0.3 }
    } = options;
    
    // 如果已存在同ID元素，先移除
    if (this.layers.has(elementId)) {
      await this.hideElement(elementId);
    }
    
    element.id = elementId;
    element.style.position = 'absolute';
    element.style.opacity = '0';
    element.style.bottom = '0';
    
    // 设置水平位置
    switch (position) {
      case 'left':
        element.style.left = '15%';
        element.style.transform = 'translateX(-50%)';
        break;
      case 'right':
        element.style.left = '85%';
        element.style.transform = 'translateX(-50%)';
        break;
      default:  // center
        element.style.left = '50%';
        element.style.transform = 'translateX(-50%)';
    }
    
    // 视频角色特殊处理
    if (element instanceof HTMLVideoElement) {
      element.loop = loop;
      element.muted = muted;
      element.playsInline = true;
      
      if (autoplay) {
        try {
          await element.play();
        } catch (e) {
          console.warn('视频自动播放失败，可能需要用户交互:', e);
        }
      }
    }
    
    container?.appendChild(element);
    this.layers.set(elementId, element);
    
    // 淡入动画（支持可配置时长）
    if (transition.type !== 'none') {
      await this.fadeIn(element, transition.duration);
    } else {
      element.style.opacity = '1';
    }
  }

  /**
   * 隐藏元素
   * @param elementId 元素ID
   * @param transition 转场配置
   */
  async hideElement(elementId: string, transition?: TransitionOptions): Promise<void> {
    const element = this.layers.get(elementId);
    if (element) {
      // 如果是视频，先暂停播放
      if (element instanceof HTMLVideoElement) {
        element.pause();
        element.currentTime = 0;
      }
      
      const duration = transition?.duration ?? 0.3;
      if (transition?.type !== 'none') {
        await this.fadeOut(element, duration);
      }
      element.remove();
      this.layers.delete(elementId);
    }
  }

  /**
   * 隐藏所有元素
   */
  hideAll(): void {
    this.layers.forEach((element) => {
      // 暂停所有视频
      if (element instanceof HTMLVideoElement) {
        element.pause();
      }
      element.remove();
    });
    this.layers.clear();
  }

  /**
   * 淡入效果
   * @param element 目标元素
   * @param duration 持续时间（秒），默认 0.3s
   */
  private async fadeIn(element: HTMLElement, duration: number = 0.3): Promise<void> {
    return new Promise(resolve => {
      element.style.transition = `opacity ${duration}s`;
      element.style.opacity = '1';
      setTimeout(resolve, duration * 1000);
    });
  }

  /**
   * 淡出效果
   * @param element 目标元素
   * @param duration 持续时间（秒），默认 0.3s
   */
  private async fadeOut(element: HTMLElement, duration: number = 0.3): Promise<void> {
    return new Promise(resolve => {
      element.style.transition = `opacity ${duration}s`;
      element.style.opacity = '0';
      setTimeout(resolve, duration * 1000);
    });
  }
}
```

### AudioManager - 多通道音频管理

**支持三种通道类型**：
- `music`：替换式，循环播放
- `sound`：多重播放，即发即忘
- `ambient`：替换式，循环播放
- `voice`：替换式，对话语音

```typescript
interface PlayOptions {
  soundId?: string;
  volume?: number;
  loop?: boolean;
  fadeIn?: number;
}

class AudioManager {
  // 替换式通道（music, ambient, voice）
  private singleChannels: Map<string, HTMLAudioElement> = new Map();
  // 多重播放通道（sound）- 可同时播放多个
  private soundPool: Map<string, HTMLAudioElement> = new Map();

  /**
   * 播放音频
   */
  play(channel: string, audio: HTMLAudioElement, options: PlayOptions = {}): void {
    const { soundId, volume = 1.0, loop = false, fadeIn } = options;

    audio.volume = fadeIn ? 0 : volume;
    audio.loop = loop;

    if (channel === 'sound') {
      // sound 通道：多重播放，可同时播放多个
      const id = soundId || `sound_${Date.now()}`;
      this.soundPool.set(id, audio);
      
      audio.play();
      
      // 播放完成后自动清理（非循环）
      if (!loop) {
        audio.addEventListener('ended', () => {
          this.soundPool.delete(id);
        }, { once: true });
      }
    } else {
      // 其他通道：替换式，新音频替换旧音频
      if (this.singleChannels.has(channel)) {
        const old = this.singleChannels.get(channel)!;
        old.pause();
        old.currentTime = 0;
      }
      
      this.singleChannels.set(channel, audio);
      audio.play();
    }

    // 淡入效果
    if (fadeIn) {
      this.fadeIn(audio, volume, fadeIn);
    }
  }

  /**
   * 注册音频到通道（用于 voice 等需要追踪的场景）
   */
  registerAudio(channel: string, audio: HTMLAudioElement): void {
    if (this.singleChannels.has(channel)) {
      const old = this.singleChannels.get(channel)!;
      old.pause();
    }
    this.singleChannels.set(channel, audio);
  }

  /**
   * 停止音频
   */
  stop(channel: string, soundId?: string, fadeOut?: number): void {
    if (channel === 'sound' && soundId) {
      // 停止特定音效
      const audio = this.soundPool.get(soundId);
      if (audio) {
        if (fadeOut) {
          this.fadeOutAndStop(audio, fadeOut);
        } else {
          audio.pause();
        }
        this.soundPool.delete(soundId);
      }
    } else if (channel === 'sound') {
      // 停止所有音效
      this.soundPool.forEach(audio => {
        audio.pause();
      });
      this.soundPool.clear();
    } else {
      // 停止单通道音频
      const audio = this.singleChannels.get(channel);
      if (audio) {
        if (fadeOut) {
          this.fadeOutAndStop(audio, fadeOut);
        } else {
          audio.pause();
          audio.currentTime = 0;
        }
        this.singleChannels.delete(channel);
      }
    }
  }

  private fadeIn(audio: HTMLAudioElement, targetVolume: number, duration: number): void {
    const step = 0.05;
    const interval = (duration * 1000) / (targetVolume / step);
    
    const timer = setInterval(() => {
      if (audio.volume < targetVolume - step) {
        audio.volume += step;
      } else {
        audio.volume = targetVolume;
        clearInterval(timer);
      }
    }, interval);
  }

  private fadeOutAndStop(audio: HTMLAudioElement, duration: number): void {
    const step = 0.05;
    const interval = (duration * 1000) / (audio.volume / step);
    
    const timer = setInterval(() => {
      if (audio.volume > step) {
        audio.volume -= step;
      } else {
        clearInterval(timer);
        audio.pause();
        audio.currentTime = 0;
      }
    }, interval);
  }
}
```

### TextRenderer - 文字渲染

**支持中断机制，用户点击推进时立即停止打字机效果和AFM等待**

```typescript
class TextRenderer {
  private currentDialogue: DialogueData | null = null;
  private isTyping = false;

  /**
   * 显示对话
   * @param data 对话数据
   * @param signal 中断信号（用户点击推进时触发）
   */
  async showDialogue(data: DialogueData, signal?: AbortSignal): Promise<void> {
    this.currentDialogue = data;
    this.isTyping = true;

    try {
      // 打字机效果（可中断）
      await this.typewriterEffect(data.text, data.textSpeed, signal);
      this.isTyping = false;

      // 检查是否被中断
      if (signal?.aborted) {
        this.showFullText(data.text);  // 立即显示完整文本
        return;
      }

      // AFM 延迟（可中断）
      if (data.afmEnable) {
        const delay = this.calculateAfmDelay(data.text, data.afmTime, data.voiceDuration);
        await this.interruptableSleep(delay, signal);
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        this.showFullText(data.text);  // 被中断时显示完整文本
        this.isTyping = false;
        throw e;  // 向上传递中断信号
      }
      throw e;
    }
  }

  /**
   * 立即显示完整文本（跳过打字机效果）
   */
  private showFullText(text: string): void {
    const container = document.getElementById('dialogue-text');
    if (container) {
      container.textContent = text;
    }
  }

  /**
   * 打字机效果（可中断）
   */
  private async typewriterEffect(text: string, speed: number, signal?: AbortSignal): Promise<void> {
    const container = document.getElementById('dialogue-text');
    if (!container) return;
    
    container.textContent = '';

    for (let i = 0; i < text.length; i++) {
      // 检查中断信号
      if (signal?.aborted) {
        throw new DOMException('Typewriter aborted', 'AbortError');
      }
      
      container.textContent += text[i];
      await this.sleep(1000 / speed);
    }
  }

  /**
   * 计算 AFM 延迟时间
   * - 如果有配音，等待配音播完 + 额外延迟
   * - 如果没有配音，根据文本长度计算
   */
  private calculateAfmDelay(text: string, afmTime: number, voiceDuration?: number): number {
    if (voiceDuration) {
      // 配音时长（毫秒）+ 额外延迟
      return voiceDuration * 1000 + afmTime * 100;
    } else {
      // 基础延迟 + 每字符延迟
      return 1000 + text.length * afmTime * 10;
    }
  }

  /**
   * 可中断的延迟
   */
  private interruptableSleep(ms: number, signal?: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) {
        reject(new DOMException('Sleep aborted', 'AbortError'));
        return;
      }

      const timer = setTimeout(resolve, ms);

      signal?.addEventListener('abort', () => {
        clearTimeout(timer);
        reject(new DOMException('Sleep aborted', 'AbortError'));
      }, { once: true });
    });
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

---

## 完整流程示例

### dialogue 事件处理（角色展示）

```
1. 收到 dialogue 事件（show 字段包含静态图、动图或视频）
    ↓
2. NarrativeEventParser 解析
   operations: [show(character), play(voice), say(text)]
   resources: [{url, type: 'image'}, {url, type: 'audio'}]
   cleanup: [stop(voice), hide(image)]
    ↓
3. ResourcePool 并行等待资源
   await Promise.all([
     resourcePool.waitFor(image.url),  // 返回 HTMLImageElement
     resourcePool.waitFor(voice.url)
   ])
    ↓
4. 执行原子操作
   - layerManager.showElement(image)  // 显示图像
   - audio.play()                     // 播放配音
   - textRenderer.showDialogue(...)   // 打字机+AFM
    ↓
5. 执行清理
   - audioManager.stop('voice')
   - layerManager.hideElement(character_id)
```

### dialogue 事件处理（视频角色）

```
1. 收到 dialogue 事件（media.type = 'video'）
    ↓
2. NarrativeEventParser 解析
   operations: [show(video, {loop, muted, autoplay}), play(voice), say(text)]
   resources: [{url, type: 'video'}, {url, type: 'audio'}]
   cleanup: [stop(voice), hide(video)]
    ↓
3. ResourcePool 并行等待资源
   await Promise.all([
     resourcePool.waitFor(video.url),  // 返回 HTMLVideoElement
     resourcePool.waitFor(voice.url)
   ])
    ↓
4. 执行原子操作
   - layerManager.showElement(video, {loop: true, muted: true, autoplay: true})
     └─ video.play() 自动播放透明视频角色
   - audio.play()                     // 播放配音（与视频分离）
   - textRenderer.showDialogue(...)   // 打字机+AFM
    ↓
5. 执行清理
   - audioManager.stop('voice')
   - layerManager.hideElement(character_id)
     └─ video.pause() 暂停视频
```

> **视频角色说明**：
> - 视频角色使用透明 WebM 格式，支持 Alpha 通道
> - 视频默认静音（`muted: true`），配音由独立的 voice 字段提供
> - 视频循环播放（`loop: true`），角色持续动态展示
> - 前端使用 `<video>` 标签渲染，自动与背景/其他元素合成

---

## 用户交互控制

### 交互行为定义

| 操作 | 行为 | 说明 |
|------|------|------|
| **点击推进** | 跳过当前事件 | 停止配音、跳过打字机效果和AFM等待，执行清理后进入下一事件 |
| **暂停** | 暂停播放队列 | 当前事件播放完成后暂停，不自动进入下一事件 |
| **继续** | 继续播放队列 | 从暂停状态恢复，继续处理后续事件 |

### 用户交互流程

```
用户点击推进
    ↓
playbackQueue.skipCurrent()
    ↓
AbortController.abort() 触发中断信号
    ↓
TextRenderer 收到中断信号
    ├─ 停止打字机效果
    ├─ 立即显示完整文本
    └─ 跳过 AFM 等待
    ↓
PlaybackQueue 执行清理规则
    ├─ 停止配音 audioManager.stop('voice')
    └─ 隐藏角色 layerManager.hideElement(...)
    ↓
自动进入下一事件（AFM 模式保持不变）
```

### 使用示例

```typescript
// 初始化播放队列
const playbackQueue = new PlaybackQueue(resourcePool, context);

// 绑定用户交互事件
document.addEventListener('click', () => {
  playbackQueue.skipCurrent();  // 点击推进
});

document.getElementById('pause-btn')?.addEventListener('click', () => {
  if (playbackQueue.paused) {
    playbackQueue.resume();  // 继续
  } else {
    playbackQueue.pause();   // 暂停
  }
});

// 接收事件并入队
dataManager.onStoryEventReceived((event) => {
  playbackQueue.enqueue(event);
});
```

### 暂停状态 UI 提示

```typescript
// 监听暂停状态变化，更新 UI
useEffect(() => {
  const updateUI = () => {
    setPauseButtonText(playbackQueue.paused ? '▶️ 继续' : '⏸️ 暂停');
  };
  // 可通过事件或轮询监听状态
}, []);
```

---

## 技术栈

- **框架**：React 18+ (TypeScript)
- **状态管理**：Zustand
- **资源缓存**：IndexedDB
- **音频管理**：Howler.js
- **构建工具**：Vite

---

**详细的 API 接口请参考 api.md**
