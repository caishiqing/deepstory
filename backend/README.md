# DeepStory Backend - 业务层模块

## 模块结构

```
backend/
├── app.py                 # FastAPI 应用入口
├── config/
│   ├── settings.py        # 全局配置
│   └── narrative.py       # 叙事配置（转场、角色颜色等）
├── models/                # 数据模型（Pydantic）
│   ├── user.py
│   ├── prompt.py
│   ├── story.py
│   ├── character.py
│   ├── resource.py
│   └── response.py        # 统一响应格式
├── api/                   # API 路由（按模块分组）
│   ├── deps.py           # 依赖注入（认证）
│   └── v1/
│       ├── user.py       # 用户模块
│       ├── prompt.py     # 创意模块
│       └── story.py      # 故事模块（核心 SSE）
└── services/              # 业务逻辑层
    ├── sse_service.py    # SSE 事件封装
    └── narrative_service.py  # 叙事引擎服务

## 快速开始

### 1. 启动应用

```bash
# 开发模式（自动重载）
python -m uvicorn backend.app:app --reload --port 8000

# 或直接运行
python backend/app.py
```

### 2. 访问文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 3. 测试 SSE 流式接口

```bash
# 使用 curl 测试
curl -N http://localhost:8000/api/v1/story/story_001/stream

# 使用浏览器 EventSource
const es = new EventSource('http://localhost:8000/api/v1/story/story_001/stream');
es.addEventListener('story_event', (e) => {
  const event = JSON.parse(e.data);
  console.log(event);
});
```

## 配置说明

### 环境变量（.env）

```bash
# 应用配置
DEBUG=true
API_V1_PREFIX=/api/v1

# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/deepstory

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_EXPIRE_MINUTES=10080

# AI 服务
DIFY_API_KEY=your-dify-key
MEDIAHUB_BASE_URL=http://localhost:8080
```

### 叙事配置（narrative.py）

可在 `backend/config/narrative.py` 中配置：

- **转场效果**：场景/章节切换的默认转场
- **角色颜色**：按性别自动分配角色名字颜色
- **默认参数**：AFM、音量、文字速度等

## 核心功能

### 1. SSE 事件流

`SSEService` 负责将 `StoryEngine` 产出的事件转换为 API 规范的 SSE 格式：

```python
from backend.services import SSEService, NarrativeService

# 生成故事事件流
narrative_service = NarrativeService()
events = await narrative_service.generate_story_stream(...)

# 转换为 SSE 格式
sse_service = SSEService()
sse_stream = sse_service.stream_events(events, story_id="...")

# 返回给前端
return StreamingResponse(sse_stream, media_type="text/event-stream")
```

### 2. 自动资源等待

`NarrativeService` 使用 `StreamingConsumer`，自动等待资源就绪后输出完整事件：

- 事件按顺序输出（保证叙事顺序）
- 资源异步并行生成（不阻塞）
- 输出的事件已包含资源 URL

### 3. 全局配置管理

- **settings**: 应用全局配置（数据库、Redis、JWT等）
- **narrative_config**: 叙事配置（转场、角色颜色等）

```python
from backend.config import settings, narrative_config

# 获取转场配置
transition = narrative_config.get_scene_start_transition()

# 获取角色颜色
color = narrative_config.get_character_color(gender="female")
```

## API 路由设计

### 按前缀分组

- `/api/v1/user/*` - 用户模块
- `/api/v1/prompt/*` - 创意输入模块
- `/api/v1/story/*` - 故事模块（核心）
- `/api/v1/explore/*` - 广场模块（TODO）
- `/api/v1/search/*` - 搜索模块（TODO）

### 核心接口

#### 1. 创建故事

```
POST /api/v1/story/create
Body: {"prompt_id": "...", "type": "linear"}
```

#### 2. 查询状态（创作阶段轮询）

```
GET /api/v1/story/{story_id}/status
```

#### 3. SSE 流式推送（消费阶段）

```
GET /api/v1/story/{story_id}/stream?from_sequence_id=...
```

## TODO

- [ ] 完善数据库操作层（SQLAlchemy Models）
- [ ] 实现用户认证逻辑（JWT生成/验证）
- [ ] 实现创意/故事的 CRUD 逻辑
- [ ] 添加广场、搜索、评论等模块路由
- [ ] 实现断点续传逻辑
- [ ] 添加限流中间件
- [ ] 完善错误处理和日志
- [ ] 添加单元测试

## 开发指南

### 添加新路由模块

1. 在 `backend/models/` 创建数据模型
2. 在 `backend/api/v1/` 创建路由文件
3. 在 `backend/api/v1/__init__.py` 注册路由

```python
# 1. 创建模型（backend/models/comment.py）
class CommentModel(BaseModel):
    ...

# 2. 创建路由（backend/api/v1/comment.py）
router = APIRouter()

@router.get("/{comment_id}")
async def get_comment(...):
    ...

# 3. 注册路由（backend/api/v1/__init__.py）
from .comment import router as comment_router
api_router.include_router(comment_router, prefix="/comment", tags=["comment"])
```

### 扩展 SSE 事件

在 `backend/services/sse_service.py` 的 `_convert_to_sse` 方法中添加新事件类型的处理逻辑。

## 部署

```bash
# 使用 gunicorn + uvicorn
gunicorn backend.app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

