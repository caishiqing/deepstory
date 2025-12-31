# AI驱动视觉小说系统 - API接口文档

> **文档定位**：定义 API 接口规范、SSE 事件格式、数据模型
> 
> **相关文档**：[README.md](./README.md) | [backend.md](./backend.md) | [frontend.md](./frontend.md)

---

## 核心概念

### 双层架构

- **后端**：推送事件（Story 事件）+ 资源 URL
- **前端**：叙事队列调度 + 媒体轨道播放 + 资源管理

### 事件分类

| SSE event 类型 | event_category | 包含的事件类型 | 说明 |
|---------------|----------------|---------------|------|
| `story_event` | `story` | story_start, story_end, chapter_start, chapter_end, scene_start, scene_end, dialogue, narration, play_audio, choice | 故事内容事件 |
| `system_event` | `system` | heartbeat, error | 系统状态事件 |

---

## RESTful API

### 基础信息

```yaml
基础URL: https://api.ai-visualnovel.com/api/v1
认证方式: Bearer Token (JWT)
Content-Type: application/json
```

**认证说明**：
- 除以下接口外，其他接口均需要登录（通过 `Authorization: Bearer <token>` 传递）
- **无需登录**：`POST /user/register`、`POST /user/login`、`POST /user/send-code`、`GET /explore/stories`
- 用户身份从 token 中解析，无需在请求中传递 `user_id`

---

### 用户模块

#### 1. 发送手机验证码

**接口**：`POST /user/send-code`

**请求**：
```json
{
  "phone": "+8613800138000",
  "type": "register"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `phone` | string | ✅ | 手机号，国际格式（如 +8613800138000）|
| `type` | string | ✅ | 验证码类型：`register` / `login` / `reset_password` |

**响应**：
```json
{
  "success": true,
  "data": {
    "expires_in": 300,
    "message": "验证码已发送"
  }
}
```

#### 2. 用户注册

**接口**：`POST /user/register`

**请求**：
```json
{
  "username": "player001",
  "email": "player@example.com",
  "phone": "+8613800138000",
  "verification_code": "123456",
  "password": "secure_password"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | ✅ | 用户名 |
| `email` | string | ❌ | 邮箱，与 `phone` 至少填一个 |
| `phone` | string | ❌ | 手机号，国际格式，与 `email` 至少填一个 |
| `verification_code` | string | ❌ | 验证码，使用手机号注册时必填 |
| `password` | string | ✅ | 密码 |

**响应**：
```json
{
  "success": true,
  "data": {
    "user_id": "user_abc123",
    "username": "player001",
    "email": "player@example.com",
    "phone": "+8613800138000",
    "token": "eyJhbGciOiJIUzI1NiIs..."
  }
}
```

#### 3. 用户登录

**接口**：`POST /user/login`

**请求（邮箱+密码）**：
```json
{
  "email": "player@example.com",
  "password": "secure_password"
}
```

**请求（手机号+密码）**：
```json
{
  "phone": "+8613800138000",
  "password": "secure_password"
}
```

**请求（手机号+验证码）**：
```json
{
  "phone": "+8613800138000",
  "verification_code": "123456"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `email` | string | ❌ | 邮箱，与 `phone` 二选一 |
| `phone` | string | ❌ | 手机号，国际格式，与 `email` 二选一 |
| `password` | string | ❌ | 密码，与 `verification_code` 二选一 |
| `verification_code` | string | ❌ | 验证码，与 `password` 二选一（仅手机号登录）|

**响应**：
```json
{
  "success": true,
  "data": {
    "user_id": "user_abc123",
    "username": "player001",
    "email": "player@example.com",
    "phone": "+8613800138000",
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "settings": {
      "text_speed": 50,
      "afm_enable": true,
      "afm_time": 15,
      "voice_volume": 1.0,
      "music_volume": 0.7,
      "sound_volume": 1.0,
      "ambient_volume": 0.7,
      "choice_timeout": 30
    }
  }
}
```

#### 4. 获取用户设置

**接口**：`GET /user/settings`

**响应**：
```json
{
  "success": true,
  "data": {
    "text_speed": 50,
    "afm_enable": true,
    "afm_time": 15,
    "voice_volume": 1.0,
    "music_volume": 0.7,
    "sound_volume": 1.0,
    "ambient_volume": 0.7,
    "choice_timeout": 30
  }
}
```

#### 5. 更新用户设置

**接口**：`PATCH /user/settings`

**请求**：
```json
{
  "text_speed": 60,
  "afm_enable": false,
  "voice_volume": 0.8
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "text_speed": 60,
    "afm_enable": false,
    "afm_time": 15,
    "voice_volume": 0.8,
    "music_volume": 0.7,
    "sound_volume": 1.0,
    "ambient_volume": 0.7,
    "choice_timeout": 30
  }
}
```

#### 7. 关注用户

**接口**：`POST /user/{user_id}/follow`

**响应**：
```json
{
  "success": true,
  "data": {
    "user_id": "user_xyz789",
    "is_following": true,
    "follower_count": 1001
  }
}
```

#### 8. 取消关注

**接口**：`DELETE /user/{user_id}/follow`

**响应**：
```json
{
  "success": true,
  "data": {
    "user_id": "user_xyz789",
    "is_following": false,
    "follower_count": 1000
  }
}
```

#### 9. 获取关注列表

**接口**：`GET /user/{user_id}/following`

**查询参数**：
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "users": [
      {
        "user_id": "user_abc123",
        "username": "创作者A",
        "follower_count": 5000,
        "create_count": 15,
        "is_following": true,
        "followed_at": "2025-01-01T10:00:00.000Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 50
    }
  }
}
```

#### 10. 获取粉丝列表

**接口**：`GET /user/{user_id}/followers`

**查询参数**：
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "users": [
      {
        "user_id": "user_def456",
        "username": "粉丝A",
        "follower_count": 100,
        "create_count": 3,
        "is_following": false,
        "followed_at": "2025-01-02T10:00:00.000Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 1000
    }
  }
}
```

**说明**：
- `is_following`：当前用户是否关注了列表中的用户（用于显示"互相关注"状态）

#### 11. 获取钱包信息

**接口**：`GET /user/wallet`

**响应**：
```json
{
  "success": true,
  "data": {
    "balance": 1500.00,
    "level": 4,
    "experience": 2350,
    "next_level_exp": 5000,
    "total_recharged": 2000.00,
    "total_consumed": 500.00,
    "can_set_price": true
  }
}
```

**字段说明**：
- `balance`：当前灵感值余额
- `level`：用户级别（1-10）
- `experience`：当前经验值
- `next_level_exp`：升级所需经验值
- `can_set_price`：是否拥有定价权（level >= 4）

#### 12. 获取交易记录

**接口**：`GET /user/wallet/transactions`

**查询参数**：
- `type`：交易类型筛选，可选（recharge/purchase/income/tip_out/tip_in/reward）
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "transactions": [
      {
        "id": "123456",
        "type": "purchase",
        "amount": -50.00,
        "balance_after": 1450.00,
        "description": "购买故事《星际迷途》",
        "related_id": "story_001",
        "created_at": "2025-01-15T10:00:00.000Z"
      },
      {
        "id": "123455",
        "type": "income",
        "amount": 35.00,
        "balance_after": 1500.00,
        "description": "《时空裂缝》被购买",
        "related_id": "story_002",
        "created_at": "2025-01-14T15:30:00.000Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 50
    }
  }
}
```

#### 13. 充值灵感值

**接口**：`POST /user/wallet/recharge`

**请求**：
```json
{
  "amount": 100.00,
  "payment_method": "wechat"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "order_id": "order_abc123",
    "amount": 100.00,
    "payment_url": "https://pay.example.com/...",
    "expires_at": "2025-01-15T10:30:00.000Z"
  },
  "message": "Payment order created."
}
```

**说明**：
- 返回第三方支付链接，前端跳转完成支付
- 支付成功后异步回调更新用户余额

#### 14. 购买故事

**接口**：`POST /story/{story_id}/purchase`

**响应**：
```json
{
  "success": true,
  "data": {
    "transaction_id": "789012",
    "price": 50.00,
    "balance_after": 1450.00
  },
  "message": "Purchase successful."
}
```

**错误响应**：
```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient balance."
  }
}
```

**说明**：
- 扣除用户余额，创建购买记录
- 70% 收入进入创作者账户（level 5+ 为 75%）
- 购买后永久可阅读完整内容

#### 15. 检查故事购买状态

**接口**：`GET /story/{story_id}/purchase`

**响应**：
```json
{
  "success": true,
  "data": {
    "purchased": true,
    "purchased_at": "2025-01-10T08:00:00.000Z",
    "price": 50.00
  }
}
```

**说明**：
- 用于判断用户是否已购买某付费故事
- 作者查看自己的故事时 `purchased` 始终为 `true`
- 后端从 `user_behavior_logs` 表查询 `action = 'purchase'` 的记录

#### 16. 打赏创作者

**接口**：`POST /story/{story_id}/tip`

**请求**：
```json
{
  "amount": 10.00
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "transaction_id": "789013",
    "amount": 10.00,
    "balance_after": 1440.00
  },
  "message": "Tip sent successfully."
}
```

**说明**：
- 打赏无最低金额限制
- 100% 进入创作者账户（平台不抽成打赏）
- 记录在行为日志中用于推荐

#### 17. 每日签到

**接口**：`POST /user/daily-checkin`

**响应**：
```json
{
  "success": true,
  "data": {
    "reward_exp": 5,
    "reward_balance": 1.00,
    "streak_days": 7,
    "balance_after": 1441.00,
    "experience_after": 2355
  },
  "message": "Check-in successful."
}
```

**说明**：
- 每日首次调用获得奖励，重复调用返回错误
- 连续签到可获得额外奖励（streak bonus）
- 同时获得经验值和少量灵感值

#### 18. 获取购买历史

**接口**：`GET /user/purchases`

**查询参数**：
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "stories": [
      {
        "story_id": "story_001",
        "title": "星际迷途",
        "cover_url": "https://cdn.example.com/covers/story_001.jpg",
        "author": {
          "user_id": "user_456",
          "username": "作者A"
        },
        "price": 50.00,
        "purchased_at": "2025-01-10T08:00:00.000Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 15
    }
  }
}
```

**说明**：
- 后端从 `user_behavior_logs` 表查询 `action = 'purchase'` 的记录
- `price` 从行为的 `metadata.price` 中获取

---

### 创意输入模块

#### 1. 创建创意输入

**接口**：`POST /prompt/create`

**请求**：
```json
{
  "logline": "一个关于时空穿越的科幻爱情故事，物理学家意外发现时间裂缝",
  "characters": [
    {
      "name": "艾莉丝",
      "basic_info": {
        "gender": "女",
        "age": 28,
        "occupation": "量子物理学家"
      },
      "description": "冷静理性的科学家，对时间裂缝有独特见解"
    },
    {
      "name": "鲍勃",
      "basic_info": {
        "gender": "男",
        "age": 32,
        "occupation": "时空工程师"
      },
      "description": "热情冲动的冒险家，愿意为爱穿越时空"
    }
  ],
  "relationships": [
    {
      "subject": "艾莉丝",
      "object": "鲍勃",
      "relationship": "同事兼暗恋对象"
    }
  ],
  "themes": {
    "genre": "科幻爱情",
    "tone": "浪漫悬疑",
    "setting": "2157年火星殖民地",
    "style": "赛博朋克",
    "tags": ["时间旅行", "量子纠缠", "命运抉择"]
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `logline` | string | ✅ | 一句话梗概（故事核心概念）|
| `characters` | List[dict] | ✅ | 角色列表，每个角色包含 name、basic_info、description |
| `relationships` | List[dict] | ❌ | 角色关系列表，每项包含 subject、object、relationship |
| `themes` | object | ✅ | 主题配置（genre、tone、setting、style、tags）|

**响应**：
```json
{
  "success": true,
  "created_at": "2025-01-01T10:00:00.000Z",
  "data": {
    "prompt_id": "prompt_001",
    "characters": ["char_alice", "char_bob"]
  },
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.prompt_id` | string | 创意ID，对应创意输入表的 id |
| `data.characters` | List[string] | 角色ID列表，对应角色表的 id |
| `created_at` | string | 创建时间（ISO 8601 格式）|

#### 2. 获取创意详情

**接口**：`GET /prompt/{prompt_id}`

**响应**：
```json
{
  "success": true,
  "data": {
    "prompt_id": "prompt_001",
    "logline": "一个关于时空穿越的科幻爱情故事，物理学家意外发现时间裂缝",
    "characters": ["char_alice", "char_bob"],
    "relationships": [
      {
        "subject": "char_alice",
        "object": "char_bob",
        "relationship": "同事兼暗恋对象"
      }
    ],
    "themes": {
      "genre": "科幻爱情",
      "tone": "浪漫悬疑",
      "setting": "2157年火星殖民地",
      "style": "赛博朋克",
      "tags": ["时间旅行", "量子纠缠", "命运抉择"]
    },
    "stories_count": 3,
    "created_at": "2025-01-01T10:00:00.000Z"
  }
}
```

**说明**：
- `characters`：角色ID列表，对应角色表的 id
- `relationships`：角色关系列表，subject/object 为角色ID

#### 3. 更新创意

**接口**：`PATCH /prompt/{prompt_id}`

**请求参数**：与创建创意接口相同，所有字段均为可选，仅更新提供的字段。

**响应**：与创建创意接口相同（`created_at` 替换为 `updated_at`）。

**说明**：
- `characters` 和 `relationships` 为完整替换，不支持增量更新
- 如果创意已有关联的故事，更新不会影响已生成的故事

---

### 创意模块业务流程

```
1. 创建创意（POST /prompt/create）
   用户填写创意信息 → 点击"保存" → 后端创建创意输入表记录
   → 同步创建角色表记录（name, basic_info, description）
   → 返回 prompt_id 和 characters（角色ID列表）

2. 编辑创意（PATCH /prompt/{prompt_id}）
   用户进入创意详情 → 编辑内容 → 点击"保存" → 后端更新创意输入表
   → 同步更新角色表（name, basic_info, description）
   → 返回更新后的 characters（角色ID列表）

3. 开始创作（POST /story/create）
   用户点击"开始创作" → 后端通过 AI 预测并更新每个角色的 details 字段
   → 进入正式故事生成流程
```

**角色表字段更新时机**：
| 字段 | 创建/编辑创意时 | 开始创作时（AI预测）|
|------|----------------|-------------------|
| name | ✅ | - |
| basic_info | ✅ | - |
| description | ✅ | - |
| details | - | ✅ |

#### 4. 获取用户创意列表

**接口**：`GET /user/prompts`

**查询参数**：
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "prompts": [
      {
        "prompt_id": "prompt_001",
        "logline": "一个关于时空穿越的科幻爱情故事...",
        "stories_count": 3,
        "created_at": "2025-01-01T10:00:00.000Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 5
    }
  }
}
```

---

### 故事模块

#### 1. 基于创意生成故事

**接口**：`POST /story/create`

**请求**：
```json
{
  "prompt_id": "prompt_001",
  "type": "interactive"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt_id` | string | ✅ | 创意ID |
| `type` | string | ❌ | 故事类型：`linear` / `interactive`，默认 `linear` |

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "prompt_id": "prompt_001",
    "type": "interactive",
    "title": null,
    "status": "pending",
    "sse_endpoint": "/api/v1/story/story_001/stream",
    "created_at": "2025-01-01T10:00:00.000Z"
  }
}
```

**说明**：
- `title` 初始为 null，AI 生成过程中会确定标题
- 一个创意可以多次调用此接口，生成不同版本的故事
- `type` 决定故事的叙事模式：
  - `linear`：线性叙事，无分支选择
  - `interactive`：互动叙事，支持分支选择

#### 2. 获取故事详情

**接口**：`GET /story/{story_id}`

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "prompt_id": "prompt_001",
    "type": "interactive",
    "title": "时空裂缝中的爱恋",
    "status": "dynamic",
    "created_at": "2025-01-01T10:00:00.000Z",
    "prompt": {
      "logline": "一个关于时空穿越的科幻爱情故事，物理学家意外发现时间裂缝",
      "themes": {
        "genre": "科幻爱情",
        "tone": "浪漫悬疑"
      }
    },
    "characters": [
      {
        "character_id": "char_alice",
        "name": "艾莉丝",
        "name_color": "#ff6b9d",
        "source": "user_defined"
      },
      {
        "character_id": "char_bob",
        "name": "鲍勃",
        "name_color": "#6b9dff",
        "source": "user_defined"
      },
      {
        "character_id": "char_ai_001",
        "name": "神秘访客",
        "name_color": "#9d6bff",
        "source": "ai_generated"
      }
    ],
    "pricing": {
      "pricing_type": "paid",
      "price": 50.00,
      "purchased": false
    },
    "author": {
      "user_id": "user_456",
      "username": "创作者A",
      "level": 5
    }
  }
}
```

**type 类型说明**：
- `linear`: 线性叙事（无分支选择）
- `interactive`: 互动叙事（支持分支选择）

**pricing 定价说明**：
- `pricing_type`: 定价类型（`free` / `paid`）
- `price`: 价格（灵感值），免费故事为 0
- `purchased`: 当前用户是否已购买（未登录或作者本人始终为 true）

**status 状态说明**：
- `pending`: 待生成（think 和 script 未生成）
- `generating`: 生成中（正在生成详细内容）
- `dynamic`: 动态分支中（**仅 interactive 类型**，遇到 choice 后进入）
- `completed`: 已完成（到达某个分支的结束点）
- `error`: 生成失败

**说明**：
- 不提供章节数、场景数、事件数等统计：AI驱动的故事支持无限分支，统计无意义
- `characters.source`: 
  - `user_defined`: 用户在创意输入中定义
  - `ai_generated`: AI 生成过程中补充的角色

#### 3. 查询故事状态（轻量）

**接口**：`GET /story/{story_id}/status`

**用途**：创作阶段轮询查询生成状态，避免 SSE 长连接空等

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "status": "generating",
    "progress": 30,
    "message": "Generating thinking ...",
    "retry_after": 10
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 故事状态：`pending` / `generating` / `dynamic` / `completed` / `error` |
| `progress` | number | 生成进度 0-100（仅 `generating` 状态有意义）|
| `message` | string | 当前阶段描述（见下方说明）|
| `retry_after` | number | 建议下次轮询间隔（秒），默认 10 |

**message 取值**：
| 阶段 | message | 说明 |
|------|---------|------|
| 生成 think 中 | `Generating thinking ...` | 还未生成 think |
| 生成 script 中 | `Generating script ...` | 已生成 think，还未生成 script |
| 创作完成 | `Create completed.` | 创作阶段完成，可进入消费阶段 |

**状态说明**：
- `pending`: 创作初始化中（生成 think 和 script）
- `generating`: 初始化完成，边生成边消费（可进入消费阶段）
- `dynamic`: 动态分支中（互动叙事，遇到 choice 后进入）
- `completed`: 故事已完结
- `error`: 生成失败

**轮询策略**：
- 创作阶段（`pending`）：前端每 10 秒轮询一次
- 当 `status != pending` 时，停止轮询，进入消费阶段
- 用户可在轮询期间离开页面，后台继续生成

#### 5. 获取用户故事列表

**接口**：`GET /user/stories`

**查询参数**：
- `prompt_id`：可选，按创意筛选
- `type`：可选，过滤类型（linear / interactive）
- `status`：可选，过滤状态（pending / generating / dynamic / completed / error）
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "stories": [
      {
        "story_id": "story_001",
        "prompt_id": "prompt_001",
        "type": "interactive",
        "title": "时空裂缝中的爱恋",
        "cover_url": "https://cdn.../story_001_cover.jpg",
        "status": "dynamic",
        "created_at": "2025-01-01T10:00:00.000Z",
        "play_count": 1024,
        "like_count": 256,
        "favorite_count": 128,
        "pricing_type": "paid",
        "price": 50.00,
        "total_revenue": 3500.00
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 5
    }
  }
}
```

**说明**：
- 列表接口仅返回基础信息，不含创意详情和进度信息
- `total_revenue`：累计收入（仅作者自己查看时返回）

#### 6. 删除故事

**接口**：`DELETE /story/{story_id}`

**响应**：
```json
{
  "success": true,
  "message": "故事已删除"
}
```

#### 7. 用户选择（分支）

**接口**：`POST /story/{story_id}/choice`

**请求**：
```json
{
  "option_id": "option_010_a"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "option_id": "option_010_a",
    "timestamp": "2025-01-01T10:35:10.000Z"
  }
}
```

#### 8. 发布故事

**接口**：`POST /story/{story_id}/publish`

**用途**：将故事发布到广场（首页推荐），其他用户可以消费
**请求**：无需请求体

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "is_published": true,
    "published_at": "2025-01-01T12:00:00.000Z"
  }
}
```

**发布规则**：

| 故事类型 | 发布条件 | 说明 |
|---------|---------|------|
| `linear` | `status = completed` | 线性叙事必须完成才能发布 |
| `interactive` | `status IN (dynamic, completed)` | 互动叙事有内容即可发布 |

**错误响应**：
```json
{
  "success": false,
  "code": 400,
  "message": "线性叙事必须完成后才能发布",
  "error": {
    "type": "PUBLISH_NOT_ALLOWED",
    "current_status": "generating"
  }
}
```

#### 9. 取消发布

**接口**：`DELETE /story/{story_id}/publish`

**响应**：
```json
{
  "success": true,
  "message": "Story unpublished."
}
```

#### 10. 设置故事定价

**接口**：`PATCH /story/{story_id}/pricing`

**请求**：
```json
{
  "pricing_type": "paid",
  "price": 50.00
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pricing_type` | string | ✅ | 定价类型：`free` / `paid` |
| `price` | number | ❌ | 价格（灵感值），`free` 类型时忽略 |

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "pricing_type": "paid",
    "price": 50.00
  },
  "message": "Pricing updated."
}
```

**权限要求**：
- 用户级别 >= 4 才能设置 `paid` 定价
- 只有故事作者可以修改定价
- 已有付费用户的故事，价格只能降低不能提高

**错误响应**：
```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_LEVEL",
    "message": "Level 4 or above required to set pricing."
  }
}
```

---

### 评论模块

#### 1. 获取故事评论列表

**接口**：`GET /story/{story_id}/comments`

**查询参数**：
- `page`：页码，默认 1
- `limit`：每页数量，默认 20
- `sort`：排序方式，`newest`（最新）/ `hottest`（最热），默认 newest

**响应**：
```json
{
  "success": true,
  "data": {
    "comments": [
      {
        "comment_id": "comment_001",
        "user": {
          "user_id": "user_abc123",
          "username": "用户A"
        },
        "content": "这个故事太精彩了！",
        "like_count": 15,
        "is_liked": false,
        "reply_count": 3,
        "created_at": "2025-01-02T10:00:00.000Z",
        "replies": [
          {
            "comment_id": "comment_002",
            "user": {
              "user_id": "user_xyz789",
              "username": "用户B"
            },
            "content": "同意！结局太感人了",
            "like_count": 5,
            "is_liked": false,
            "created_at": "2025-01-02T11:00:00.000Z"
          }
        ]
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 50
    }
  }
}
```

**说明**：
- 游客可查看评论，`is_liked` 始终为 false
- `replies` 最多返回 3 条，更多回复需单独请求
- 已删除评论显示为 `content: "该评论已删除"`

#### 2. 发表评论

**接口**：`POST /story/{story_id}/comments`

**请求**：
```json
{
  "content": "这个故事太精彩了！",
  "parent_id": null
}
```

**参数说明**：
- `content`：评论内容（1-500字符）
- `parent_id`：回复的父评论ID，顶级评论传 null

**响应**：
```json
{
  "success": true,
  "data": {
    "comment_id": "comment_001",
    "content": "这个故事太精彩了！",
    "created_at": "2025-01-02T10:00:00.000Z"
  }
}
```

#### 3. 删除评论

**接口**：`DELETE /comment/{comment_id}`

**响应**：
```json
{
  "success": true,
  "message": "Comment deleted."
}
```

**说明**：仅评论作者可删除自己的评论（软删除）

#### 4. 点赞评论

**接口**：`POST /comment/{comment_id}/like`

**响应**：
```json
{
  "success": true,
  "data": {
    "comment_id": "comment_001",
    "is_liked": true,
    "like_count": 16
  }
}
```

#### 5. 取消点赞评论

**接口**：`DELETE /comment/{comment_id}/like`

**响应**：
```json
{
  "success": true,
  "data": {
    "comment_id": "comment_001",
    "is_liked": false,
    "like_count": 15
  }
}
```

---

### 搜索模块

#### 1. 搜索故事

**接口**：`GET /search/stories`

**查询参数**：
- `q`：搜索关键词（必填）
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "stories": [
      {
        "story_id": "story_001",
        "type": "interactive",
        "title": "时空裂缝中的爱恋",
        "cover_url": "https://cdn.../story_001_cover.jpg",
        "author": {
          "user_id": "user_abc123",
          "username": "创作者A"
        },
        "play_count": 1234,
        "like_count": 256,
        "favorite_count": 128,
        "created_at": "2025-01-01T10:00:00.000Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 5
    }
  }
}
```

**说明**：
- 仅搜索 `visibility = 'published'` 且作者 `status = 'active'` 的故事
- 搜索范围：故事标题 + 创意简介（logline）
- 支持中英文混合搜索（使用 pg_jieba 分词）

#### 2. 搜索用户

**接口**：`GET /search/users`

**查询参数**：
- `q`：搜索关键词（必填）
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "users": [
      {
        "user_id": "user_abc123",
        "username": "创作者A",
        "create_count": 15,
        "like_count": 320
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 3
    }
  }
}
```

**说明**：
- 仅搜索 `status = 'active'` 的用户
- 搜索范围：用户名
- 支持中英文混合搜索

---

### 广场模块（首页推荐）

#### 1. 获取广场故事列表

**接口**：`GET /explore/stories`

**用途**：获取已发布的故事列表，用于首页推荐/广场展示

**查询参数**：
- `type`：可选，过滤类型（linear / interactive）
- `sort`：可选，排序方式（latest / popular / recommended），默认 latest
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**sort 说明**：
| 值 | 说明 |
|---|------|
| `latest` | 按发布时间降序（默认）|
| `popular` | 按热度排序（play_count、like_count 等综合）|
| `recommended` | 个性化推荐（基于用户行为，未登录则等同于 popular）|

**响应**：
```json
{
  "success": true,
  "data": {
    "stories": [
      {
        "story_id": "story_001",
        "type": "interactive",
        "title": "时空裂缝中的爱恋",
        "cover_url": "https://cdn.../story_001_cover.jpg",
        "status": "completed",
        "author": {
          "user_id": "user_abc123",
          "username": "创作者A"
        },
        "published_at": "2025-01-01T12:00:00.000Z",
        "play_count": 1024,
        "like_count": 256,
        "favorite_count": 128,
        "pricing_type": "paid",
        "price": 50.00
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 100
    }
  }
}
```

**说明**：
- 只返回 `visibility = 'published'` 的故事
- 列表不含创意信息，进入故事详情后可查询关联创意
- `pricing_type`：定价类型（`free` / `paid`），便于前端显示付费标识

#### 2. 收藏故事

**接口**：`POST /story/{story_id}/favorite`

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "is_favorited": true,
    "favorite_count": 129
  }
}
```

#### 3. 取消收藏

**接口**：`DELETE /story/{story_id}/favorite`

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "is_favorited": false,
    "favorite_count": 128
  }
}
```

#### 4. 获取用户收藏列表

**接口**：`GET /user/favorites`

**查询参数**：
- `page`：页码，默认 1
- `limit`：每页数量，默认 20

**响应**：
```json
{
  "success": true,
  "data": {
    "stories": [
      {
        "story_id": "story_001",
        "type": "interactive",
        "title": "时空裂缝中的爱恋",
        "cover_url": "https://cdn.../story_001_cover.jpg",
        "author": {
          "user_id": "user_abc123",
          "username": "创作者A"
        },
        "favorited_at": "2025-01-02T10:00:00.000Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 10
    }
  }
}
```

#### 5. 点赞故事

**接口**：`POST /story/{story_id}/like`

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "is_liked": true,
    "like_count": 256
  }
}
```

#### 6. 取消点赞

**接口**：`DELETE /story/{story_id}/like`

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "is_liked": false,
    "like_count": 255
  }
}
```

#### 7. 上报分享

**接口**：`POST /story/{story_id}/share`

**请求**：
```json
{
  "platform": "wechat"
}
```

**参数说明**：
- `platform`：分享平台（wechat/weibo/qq/link 等），用于统计分析

**响应**：
```json
{
  "success": true,
  "message": "Share recorded."
}
```

---

### 进度模块（存档）

#### 1. 保存进度

**接口**：`POST /story/{story_id}/progress`

**请求**：
```json
{
  "current_event_id": "01JG8XYZ042",
  "current_version_id": "version_abc123",
  "current_chapter_id": "chapter_3",
  "current_scene_id": "laboratory",
  "play_time": 600
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `current_event_id` | string | ✅ | 当前事件的 sequence_id（ULID格式）|
| `current_version_id` | string | ❌ | 当前分支版本ID（interactive 类型必填）|
| `current_chapter_id` | string | ❌ | 当前章节ID |
| `current_scene_id` | string | ❌ | 当前场景ID |
| `play_time` | number | ❌ | 累计播放时长（秒）|

**响应**：
```json
{
  "success": true,
  "data": {
    "progress_id": 1,
    "story_id": "story_001",
    "current_event_id": "01JG8XYZ042",
    "current_version_id": "version_abc123",
    "current_chapter_id": "chapter_3",
    "current_scene_id": "laboratory",
    "play_time": 600,
    "last_played_at": "2025-01-01T10:35:00.000Z"
  }
}
```

**说明**：
- 只关注当前状态（用户在哪里），不记录历史路径
- `current_version_id`：互动叙事必填，用于关联分支路径；线性叙事为 null
- 断点续传：从 `current_event_id` + `current_version_id` 继续链式遍历

#### 2. 获取进度

**接口**：`GET /story/{story_id}/progress`

**响应**：
```json
{
  "success": true,
  "data": {
    "story_id": "story_001",
    "current_event_id": "01JG8XYZ042",
    "current_version_id": "version_abc123",
    "current_chapter_id": "chapter_3",
    "current_scene_id": "laboratory",
    "play_time": 600,
    "started_at": "2025-01-01T10:00:00.000Z",
    "last_played_at": "2025-01-01T10:35:00.000Z"
  }
}
```

**说明**：
- 只返回当前状态，不返回历史路径
- `current_version_id`：互动叙事的分支版本ID，线性叙事为 null
- 断点续传使用 `current_event_id` + `current_version_id` 作为起点

#### 3. 从进度恢复（断点续传）

**接口**：`GET /story/{story_id}/stream?from_sequence_id={sequence_id}`

**说明**：
- 传入用户进度的 `current_event_id` 作为 `from_sequence_id` 参数
- 服务端从该事件的 sequence_id 开始链式遍历推送
- 服务端会同时推送当前场景的初始状态（背景、音乐等）
- 遇到 choice 事件时，用户需要重新选择（游戏模式）

**示例**：
```
GET /api/v1/story/story_001/stream?from_sequence_id=01JG8XYZ042

服务端：
  1. 查询 sequence_id='01JG8XYZ042' 的事件
  2. 推送该事件及其场景状态
  3. 通过 next_sequence_id 继续链式推送
  4. 遇到 choice 暂停，等待用户选择
```

---

## SSE 事件流

### 连接策略

故事生命周期分为**创作阶段**和**消费阶段**，采用不同的连接策略：

| 阶段 | 连接方式 | 说明 |
|------|---------|------|
| **创作阶段** | 短轮询（10秒） | 调用 `GET /story/{story_id}/status` 查询状态 |
| **消费阶段** | 按需 SSE | 本地缓存优先，缓存不足时建立 SSE |

**创作阶段**：
- 故事状态为 `pending` 时，使用短轮询
- 轮询间隔：10秒（服务端可通过 `retry_after` 调整）
- 用户可离开页面，后台继续生成

**消费阶段**：
- 故事状态 `!= pending` 时，进入消费阶段
- `generating`：边生成边消费，SSE 持续推送事件
- 优先从本地缓存（IndexedDB）播放
- 缓存不足时建立 SSE 增量接收
- 缓存充足时可断开 SSE，节省资源

### 连接接口

**接口**：`GET /story/{story_id}/stream`

**查询参数**：
- `from_sequence_id`：可选，从指定事件开始推送（用于断点续传）

**特点**：
- 持续推送故事事件（约10分钟完成）
- 支持断点续传（Last-Event-ID 或 from_sequence_id）
- 客户端本地缓存，播放时长30+分钟

### SSE 消息格式

所有 SSE 消息使用标准格式：

```
event: <event_type>
id: <message_id>
data: <json_payload>

```

**字段说明**：
- `event`：SSE 事件类型，用于客户端过滤（`story_event` 或 `system_event`）
- `id`：消息ID，用于断点续传
- `data`：JSON 格式的事件内容

---

## Story 事件（故事内容）

### 基础结构

```
event: story_event
id: story_001_seq_042
data: {
data:   "sequence_id": "story_001_seq_042",
data:   "path_id": "root0000",
data:   "event_category": "story",
data:   "event_type": "<specific_type>",
data:   "timestamp": "2025-01-01T10:35:00.000Z",
data:   "content": { ... }
data: }

```

**path_id 说明**：
- 用于前端过滤播放，只播放匹配 `currentPathId` 的事件
- 线性叙事：所有事件 `path_id = "root0000"`
- 互动叙事：每个分支有独立的 `path_id`（由 choice.option.path_id 指定）

### Story 事件类型（11种）

| 事件类型 | 用途 | 资源 | 自动清理 |
|---------|------|------|---------|
| `story_start` | 故事开始 | - | - |
| `story_end` | 故事结束 | - | 关闭SSE连接 |
| `chapter_start` | 章节开始 | - | - |
| `chapter_end` | 章节结束 | - | - |
| `scene_start` | 场景开始 | 背景图 + 音乐? + 环境音? | 清理上一场景 |
| `scene_end` | 场景结束 | - | 淡出音频 |
| `dialogue` | 对话 | 文字 + 图像? + 配音? | 停止配音、隐藏图像 |
| `narration` | 旁白 | 文字 + 配音? | 停止配音 |
| `play_audio` | 插入音效 | 音频 | 播放完自动停止 |
| `play_video` | 播放视频 | 视频 | 播放完自动停止 |
| `choice` | 用户选择 | 选项列表 | 强制暂停播放 |

---

### 1. story_start - 故事开始

```
event: story_event
id: story_001_start
data: {
data:   "sequence_id": "story_001_start",
data:   "path_id": "root0000",
data:   "event_category": "story",
data:   "event_type": "story_start",
data:   "timestamp": "2025-01-01T10:30:00.000Z",
data:   "content": {
data:     "story_id": "story_001",
data:     "title": "时间的秘密",
data:     "theme": "科幻悬疑",
data:     "message": "故事即将开始..."
data:   }
data: }

```

---

### 2. story_end - 故事结束

```
event: story_event
id: story_001_end
data: {
data:   "sequence_id": "story_001_end",
data:   "path_id": "root0000",
data:   "event_category": "story",
data:   "event_type": "story_end",
data:   "timestamp": "2025-01-01T11:30:00.000Z",
data:   "content": {
data:     "story_id": "story_001",
data:     "message": "故事已完结"
data:   }
data: }

```

> 注：story_end 推送后，服务端自动关闭 SSE 连接

---

### 3. chapter_start - 章节开始

**用途**：标记新章节开始

```
event: story_event
id: story_001_chapter_01
data: {
data:   "sequence_id": "story_001_chapter_01",
data:   "event_category": "story",
data:   "event_type": "chapter_start",
data:   "timestamp": "2025-01-01T10:32:00.000Z",
data:   "content": {
data:     "chapter_id": "chapter_1",
data:     "chapter_number": 1,
data:     "title": "第一章：神秘的实验室",
data:     "message": "新的篇章即将展开..."
data:   }
data: }

```

---

### 4. chapter_end - 章节结束

**用途**：标记章节结束

```
event: story_event
id: story_001_chapter_01_end
data: {
data:   "sequence_id": "story_001_chapter_01_end",
data:   "event_category": "story",
data:   "event_type": "chapter_end",
data:   "timestamp": "2025-01-01T10:40:00.000Z",
data:   "content": {
data:     "chapter_id": "chapter_1",
data:     "chapter_number": 1,
data:     "title": "第一章：神秘的实验室",
data:     "message": "第一章完结"
data:   }
data: }

```

---

### 5. scene_start - 场景开始

**用途**：开启新场景，设置背景、音乐、环境音

**自动清理**：停止上一场景的所有音频和元素

**转场说明**：
- `transition.type` 为 `fade_in` 时，场景元素（背景、音乐、环境音）淡入显示
- `transition.duration` 指定淡入时长（秒）
- 转场参数由后端从场景表或全局配置中读取

```
event: story_event
id: story_001_scene_01
data: {
data:   "sequence_id": "story_001_scene_01",
data:   "event_category": "story",
data:   "event_type": "scene_start",
data:   "timestamp": "2025-01-01T10:35:00.000Z",
data:   "content": {
data:     "scene_id": "laboratory",
data:     "scene_name": "神秘实验室",
data:     "background": {
data:       "url": "https://cdn.../lab_bg.jpg"
data:     },
data:     "music": {
data:       "url": "https://cdn.../mysterious_theme.ogg"
data:     },
data:     "ambient": {
data:       "url": "https://cdn.../lab_ambient.ogg"
data:     },
data:     "transition": {
data:       "type": "fade_in",
data:       "duration": 1.5
data:     }
data:   }
data: }

```

---

### 6. scene_end - 场景结束

**用途**：结束当前场景

**自动清理**：淡出音乐和环境音

**转场说明**：
- `transition.type` 为 `fade_out` 时，场景元素（背景、音乐、环境音）淡出消失
- `transition.duration` 指定淡出时长（秒）
- 转场参数由后端从场景表或全局配置中读取

```
event: story_event
id: story_001_scene_01_end
data: {
data:   "sequence_id": "story_001_scene_01_end",
data:   "event_category": "story",
data:   "event_type": "scene_end",
data:   "timestamp": "2025-01-01T10:45:00.000Z",
data:   "content": {
data:     "scene_id": "laboratory",
data:     "transition": {
data:       "type": "fade_out",
data:       "duration": 1.0
data:     }
data:   }
data: }

```

---

### 7. dialogue - 对话

**用途**：显示角色对话，可选图像和配音

```
event: story_event
id: story_001_seq_003
data: {
data:   "sequence_id": "story_001_seq_003",
data:   "path_id": "root0000",
data:   "event_category": "story",
data:   "event_type": "dialogue",
data:   "timestamp": "2025-01-01T10:35:03.000Z",
data:   "content": {
data:     "character_id": "char_alice",
data:     "character_name": "艾莉丝",
data:     "character_color": "#ff6b9d",
data:     "text": "这里...好像不太对劲。",
data:     "show": {
data:       "portrait_id": "portrait_alice_youth_003",
data:       "url": "https://cdn.../alice_youth_worried.webp",
data:       "position": "center"
data:     },
data:     "voice": {
data:       "voice_id": "voice_alice_003",
data:       "url": "https://cdn.../alice_003.ogg",
data:       "duration": 2.5
data:     },
data:     "emotion": "worried",
data:     "auto_hide": true
data:   }
data: }

```

**参数说明**：
- `character_id`：角色ID，用于标识角色
- `character_name`：角色名，显示在对话框中
- `character_color`：角色名字颜色，未指定时使用后端全局配置自动分配
- `show.portrait_id`：立绘ID，可选。AI 根据 emotion 从角色的立绘库中选择合适的立绘
- `show.url`：立绘资源URL
- `show.position`：角色立绘位置（left/center/right），未指定时使用全局默认值（center）
- `emotion`：情绪标签（如 happy, sad, angry, worried 等），用于：
  - AI 选择合适的立绘（匹配 portrait.tag）
  - 配音情绪控制
- `auto_hide`：对话结束后是否自动隐藏角色立绘，默认为 true

**立绘选择逻辑**：
1. AI 根据对话上下文确定角色情绪或状态（emotion）
2. 从角色的立绘库中查询匹配的立绘（tag 匹配 emotion）
3. 如果有多个匹配，选择最先创建的或优先级最高的
4. 如果没有匹配，使用该角色当前年龄段的默认立绘（is_default=true）

> 注：`show` 为可选字段。低频配置项（character_color、position）支持全局默认配置。

---

### 8. narration - 旁白

**用途**：显示旁白文字，可选配音

**自动清理**：配音播放完成后自动停止

```
event: story_event
id: story_001_seq_002
data: {
data:   "sequence_id": "story_001_seq_002",
data:   "event_category": "story",
data:   "event_type": "narration",
data:   "timestamp": "2025-01-01T10:35:02.000Z",
data:   "content": {
data:     "text": "夜深了，实验室里只剩下机器运转的声音...",
data:     "voice": {
data:       "voice_id": "voice_narration_001",
data:       "url": "https://cdn.../narration_001.ogg",
data:       "duration": 3.2
data:     },
data:     "emotion": "calm",
data:     "window": "show"
data:   }
data: }

```

---

### 9. play_audio - 播放音频

**用途**：播放音频资源，支持音效、音乐、环境音

**通道规则**：
| channel | 播放模式 | 说明 |
|---------|---------|------|
| `sound` | 多重播放 | 即发即忘，可同时播放多个 |
| `music` | 替换式 | 新音乐停止旧音乐，循环播放 |
| `ambient` | 替换式 | 环境音，循环播放 |

#### 示例1：播放音效

```
event: story_event
id: story_001_seq_004
data: {
data:   "sequence_id": "story_001_seq_004",
data:   "event_category": "story",
data:   "event_type": "play_audio",
data:   "timestamp": "2025-01-01T10:35:04.000Z",
data:   "content": {
data:     "channel": "sound",
data:     "url": "https://cdn.../door_open.ogg"
data:   }
data: }

```

#### 示例2：播放音乐（场景中途切换）

```
event: story_event
id: story_001_seq_005
data: {
data:   "sequence_id": "story_001_seq_005",
data:   "event_category": "story",
data:   "event_type": "play_audio",
data:   "timestamp": "2025-01-01T10:35:05.000Z",
data:   "content": {
data:     "channel": "music",
data:     "url": "https://cdn.../battle_theme.ogg"
data:   }
data: }

```

#### 示例3：播放环境音

```
event: story_event
id: story_001_seq_006
data: {
data:   "sequence_id": "story_001_seq_006",
data:   "event_category": "story",
data:   "event_type": "play_audio",
data:   "timestamp": "2025-01-01T10:35:06.000Z",
data:   "content": {
data:     "channel": "ambient",
data:     "url": "https://cdn.../rain.ogg"
data:   }
data: }

```

**字段说明**：
| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| channel | string | 否 | 音频通道：sound（默认）、music、ambient |
| url | string | 是 | 音频资源 URL |

**播放规则**（由前端全局配置控制）：
| 通道 | 循环播放 | 音量 | 说明 |
|------|---------|------|------|
| sound | 否 | 使用全局 sound_volume（默认1.0）| 一次性音效 |
| music | 是 | 使用全局 music_volume（默认0.7）| 背景音乐，循环播放 |
| ambient | 是 | 使用全局 ambient_volume（默认0.7）| 环境音，循环播放 |
| voice | 否 | 使用全局 voice_volume（默认1.0）| 配音，一次性播放 |


---

### 10. play_video - 播放视频

**用途**：播放全屏视频（过场动画、CG等）

**自动清理**：视频播放完成后自动停止

**阻塞行为**：阻塞叙事队列，等待视频播放完成

```
event: story_event
id: story_001_seq_020
data: {
data:   "sequence_id": "story_001_seq_020",
data:   "event_category": "story",
data:   "event_type": "play_video",
data:   "timestamp": "2025-01-01T10:35:20.000Z",
data:   "content": {
data:     "video": {
data:       "url": "https://cdn.../opening_cg.webm"
data:     },
data:     "skippable": true
data:   }
data: }

```

**字段说明**：
- `skippable`：是否允许用户跳过，默认 true

---

### 11. choice - 用户选择

**用途**：显示选择菜单，强制暂停播放，创建分支

**参数说明**：
- `prompt`：提示文字，可选
- `options`：选项列表，第一个选项为默认选项
- `options[].next_sequence_id`：选择该选项后跳转到的事件ID
- `options[].path_id`：该分支的路径ID，前端用于切换 `currentPathId`
- 超时时间由前端全局配置控制
- 超时后自动选择第一个选项（options[0]）

```
event: story_event
id: story_001_seq_010
data: {
data:   "sequence_id": "01JG8XYZABC123",
data:   "path_id": "root0000",
data:   "event_category": "story",
data:   "event_type": "choice",
data:   "timestamp": "2025-01-01T10:35:09.000Z",
data:   "content": {
data:     "prompt": "你要怎么回答艾莉丝？",
data:     "options": [
data:       {
data:         "option_id": "option_010_a",
data:         "text": "是的，我也感觉到了时间的异常",
data:         "next_sequence_id": "01JG8Y12DEF456",
data:         "path_id": "a1b2c3d4"
data:       },
data:       {
data:         "option_id": "option_010_b",
data:         "text": "也许只是你太累了",
data:         "next_sequence_id": "01JG8Y34GHI789",
data:         "path_id": "e5f6g7h8"
data:       }
data:     ]
data:   }
data: }

```

**分支跳转说明**：
- choice 事件本身的 `path_id` 是当前路径（如 `root0000`）
- 每个 option 包含 `path_id`，指向该分支的路径ID
- 用户选择后，前端切换 `currentPathId = option.path_id`
- 后续该 `path_id` 的事件将被播放（资源已预下载，无延迟）

---

## System 事件（系统状态）

### 基础结构

```
event: system_event
id: system_001
data: {
data:   "sequence_id": "system_001",
data:   "event_category": "system",
data:   "event_type": "<specific_type>",
data:   "timestamp": "2025-01-01T10:30:00.000Z",
data:   "content": { ... }
data: }

```

### System 事件类型（2种）

| 事件类型 | 用途 | 说明 |
|---------|------|------|
| `heartbeat` | 心跳包 | 保持连接活跃（每30秒）|
| `error` | 错误通知 | 系统错误 |

> **注**：创作阶段的等待状态通过短轮询 `GET /status` 接口获取，不再使用 SSE 事件。

---

### 1. heartbeat - 心跳包

```
event: system_event
id: heartbeat_001
data: {
data:   "sequence_id": "heartbeat_001",
data:   "event_category": "system",
data:   "event_type": "heartbeat",
data:   "timestamp": "2025-01-01T10:30:30.000Z",
data:   "content": {
data:     "server_time": "2025-01-01T10:30:30.000Z"
data:   }
data: }

```

---

### 2. error - 错误通知

```
event: system_event
id: error_001
data: {
data:   "sequence_id": "error_001",
data:   "event_category": "system",
data:   "event_type": "error",
data:   "timestamp": "2025-01-01T10:30:00.000Z",
data:   "content": {
data:     "error_code": "AI_GENERATION_FAILED",
data:     "message": "AI生成失败，请重试",
data:     "retry_after": 5
data:   }
data: }

```

---

## TypeScript 接口定义

### 基础类型

```typescript
// SSE 事件基础结构
interface SSEEvent {
  sequence_id: string;
  path_id: string;        // 分支路径ID（前端用于过滤播放）
  event_category: 'story' | 'system';
  event_type: StoryEventType | SystemEventType;
  timestamp: string;
  content: StoryEventContent | SystemEventContent;
}

// Story 事件类型
type StoryEventType =
  | 'story_start'
  | 'story_end'
  | 'chapter_start'
  | 'chapter_end'
  | 'scene_start'
  | 'scene_end'
  | 'dialogue'
  | 'narration'
  | 'play_audio'
  | 'play_video'
  | 'choice';

// System 事件类型
type SystemEventType =
  | 'heartbeat'
  | 'error';

// 转场效果
interface Transition {
  type: 'fade_in' | 'fade_out' | 'dissolve' | 'wipe' | 'none';
  duration: number;
}

```

### Story 事件接口

```typescript
// 1. 故事开始
interface StoryStartContent {
  story_id: string;
  title: string;
  theme?: string;
  message?: string;
}

// 2. 故事结束
interface StoryEndContent {
  story_id: string;
  message?: string;
}

// 3. 章节开始
interface ChapterStartContent {
  chapter_id: string;
  chapter_number: number;
  title: string;
  message?: string;
}

// 4. 章节结束
interface ChapterEndContent {
  chapter_id: string;
  chapter_number: number;
  title: string;
  message?: string;
}

// 5. 场景开始
interface SceneStartContent {
  scene_id: string;
  scene_name?: string;
  background: {
    url: string;
  };
  music?: {
    url: string;
  };
  ambient?: {
    url: string;
  };
  transition?: Transition;
}

// 6. 场景结束
interface SceneEndContent {
  scene_id: string;
  transition?: Transition;
}

// 7. 对话
interface DialogueContent {
  character_id: string;
  character_name: string;
  character_color?: string;
  text: string;
  show?: {  // 角色展示（支持静态图、动图、视频，前端根据 URL 扩展名判断类型）
    portrait_id?: string;  // 立绘ID（可选，AI根据emotion选择）
    url: string;
    position?: 'left' | 'center' | 'right';
    // 视频角色配置（可选，仅当角色为视频时提供）
    video_config?: {
      loop?: boolean;      // 是否循环播放，默认 true
      muted?: boolean;     // 是否静音，默认 true（配音由voice字段提供）
      autoplay?: boolean;  // 是否自动播放，默认 true
    };
  };
  voice?: {
    voice_id?: string;     // 语音ID（可选，用于追踪和缓存）
    url: string;           // 音频 URL
    duration?: number;     // 音频时长（秒），用于 AFM 计算
  };
  emotion?: string;  // 情绪标签（如 happy, sad, angry, worried 等），用于AI选择立绘
  auto_hide?: boolean;  // 对话结束后是否自动隐藏角色图像，默认 true
}

// 注：AFM（自动推进）参数由用户全局设置控制，不在事件中定义

// 8. 旁白
interface NarrationContent {
  text: string;
  voice?: {
    voice_id?: string;     // 语音ID（可选，用于追踪和缓存）
    url: string;           // 音频 URL
    duration?: number;     // 音频时长（秒），用于 AFM 计算
  };
  emotion?: string;  // 情绪标签（如 calm, tense, mysterious 等）
  window?: 'show' | 'hide' | 'auto';
}

// 9. 播放音频
interface PlayAudioContent {
  channel?: 'sound' | 'music' | 'ambient';  // 音频通道，默认 sound
  url: string;  // 音频 URL
}

// 注：音量和循环播放由前端全局配置和通道类型决定


// 10. 播放视频
interface PlayVideoContent {
  video: {
    url: string;  // 视频 URL
  };
  skippable?: boolean;  // 是否允许跳过，默认 true
}

// 11. 用户选择
interface ChoiceContent {
  prompt?: string;
  options: Array<{
    option_id: string;
    text: string;
    next_sequence_id: string;  // 选择该选项后跳转到的事件ID
    path_id: string;           // 该分支的路径ID（前端用于切换 currentPathId）
  }>;
}

// 注：
// - 默认选择为 options[0]，超时时间由前端全局配置控制
// - choice 事件的 next_sequence_id 字段为 NULL，分支跳转信息在 options 中
// - 每个 option 的 path_id 用于前端切换当前播放路径
```

### System 事件接口

```typescript
// 1. 故事初始化中
interface StoryInitializingContent {
  story_id: string;
  status: 'generating' | 'preparing';
  message: string;
  progress?: number;
}

// 2. 心跳包
interface HeartbeatContent {
  server_time: string;
}

// 3. 错误通知
interface ErrorContent {
  error_code: string;
  message: string;
  retry_after?: number;
}
```

---

## 完整事件流示例

### 线性故事示例

```
# Story 事件：故事开始
event: story_event
id: seq_01JG8XYZ001
data: {"sequence_id":"01JG8XYZ001","path_id":"root0000","event_type":"story_start",...}

# Story 事件：章节开始
event: story_event
id: seq_01JG8XYZ002
data: {"sequence_id":"01JG8XYZ002","path_id":"root0000","event_type":"chapter_start",...}

# Story 事件：场景开始
event: story_event
id: seq_01JG8XYZ003
data: {"sequence_id":"01JG8XYZ003","path_id":"root0000","event_type":"scene_start",...}

# Story 事件：对话
event: story_event
id: seq_01JG8XYZ004
data: {"sequence_id":"01JG8XYZ004","path_id":"root0000","event_type":"dialogue",...}

# Story 事件：故事结束
event: story_event
id: seq_01JG8XYZ005
data: {"sequence_id":"01JG8XYZ005","path_id":"root0000","event_type":"story_end",...}
```

### 分支故事示例

```
# 主路径 (path_id=root0000)
event: story_event
data: {
  "sequence_id": "01JG8XYZ001",
  "path_id": "root0000",
  "event_type": "story_start"
}

event: story_event
data: {
  "sequence_id": "01JG8XYZ002",
  "path_id": "root0000",
  "event_type": "dialogue",
  "content": {"text": "你发现了一个神秘的按钮..."}
}

# 分支点
event: story_event
data: {
  "sequence_id": "01JG8XYZ003",
  "path_id": "root0000",
  "event_type": "choice",
  "content": {
    "prompt": "你要按下按钮吗？",
    "options": [
      {
        "option_id": "option_press",
        "text": "按下按钮",
        "next_sequence_id": "01JG8Y12ABC",
        "path_id": "a1b2c3d4"
      },
      {
        "option_id": "option_ignore",
        "text": "忽略按钮",
        "next_sequence_id": "01JG8Y34DEF",
        "path_id": "e5f6g7h8"
      }
    ]
  }
}

# 分支A (path_id=a1b2c3d4)
event: story_event
data: {
  "sequence_id": "01JG8Y12ABC",
  "path_id": "a1b2c3d4",
  "event_type": "dialogue",
  "content": {"text": "你按下了按钮，突然一道光闪过..."}
}

# 分支B (path_id=e5f6g7h8)
event: story_event
data: {
  "sequence_id": "01JG8Y34DEF",
  "path_id": "e5f6g7h8",
  "event_type": "dialogue",
  "content": {"text": "你决定离开，但突然听到了奇怪的声音..."}
}
```

### 事件链式结构图

```
root0000 (主路径)
  ├─ story_start → next: 01JG8XYZ002
  ├─ dialogue → next: 01JG8XYZ003
  └─ choice (next: NULL)
       ├─ option_press → a1b2c3d4 (分支A)
       │                   ├─ dialogue → next: ...
       │                   ├─ dialogue → next: ...
       │                   └─ story_end (next: NULL)
       │
       └─ option_ignore → e5f6g7h8 (分支B)
                           ├─ dialogue → next: ...
                           ├─ choice (next: NULL)
                           │    ├─ option_c → c9d0e1f2
                           │    └─ option_d → g3h4i5j6
                           └─ ...
```

---

## 错误处理

### 标准错误响应

```json
{
  "success": false,
  "code": 400,
  "message": "请求参数错误",
  "error": {
    "type": "VALIDATION_ERROR",
    "details": [
      {
        "field": "user_id",
        "message": "用户ID不能为空"
      }
    ]
  }
}
```

### 常见错误码

| 错误码 | 说明 |
|-------|------|
| 400 | 请求参数错误 |
| 401 | 未授权（token 无效或过期）|
| 404 | 资源不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |

---

**文档版本**：v2.0 (叙事事件架构)
