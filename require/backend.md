# 后端数据模型文档

> **文档定位**：后端数据模型、表结构设计
> 
> **相关文档**：[README.md](./README.md) | [api.md](./api.md) | [frontend.md](./frontend.md)

---

## 数据模型

### ER 关系图

```
┌──────────────┐
│     User     │
├──────────────┤
│ id (PK)      │
│ username     │
│ email        │
│ settings     │
└──────┬───────┘
       │
       │ 拥有多个创意和故事
       │
       ├─────────────────────────────────────────────┐
       │                                              │
       ▼                                              ▼
┌────────────────┐                           ┌──────────────┐
│ StoryPrompt    │ 1                       * │    Story     │
│（创意输入）     │◄──────────────────────────│              │
├────────────────┤  prompt_id               ├──────────────┤
│ id (PK)        │                           │ id (PK)      │
│ user_id (FK)   │                           │ prompt_id(FK)│
│ logline        │                           │ user_id (FK) │
│ characters[]   │                           │ type         │
│ themes{}       │                           │ title/status │
└────────┬───────┘                           └──────┬───────┘
         │                                          │
         │                                           │
         │ 引用角色                                   │
         │                                           │
         └─────────────────────┐                     │
                               │                     │
                               ▼                     ▼
                         ┌──────────────┐      ┌──────────────┐
                         │  Character   │      │  StoryEvent  │
                         ├──────────────┤      ├──────────────┤
                         │ id (PK)      │      │ story_id(FK) │
                         │ user_id (FK) │      │ sequence_id  │
                         │ story_id(FK) │      │ event_type   │
                         │ source       │      │ content      │
                         │ name         │      └──────────────┘
                         │ gender       │
                         │ prompt       │
                         │ details{}    │
                         └──────┬───────┘
                                │
                                │ 1:N
                                ▼
                         ┌──────────────────┐
                         │CharacterPortrait │
                         │  (角色立绘)       │
                         ├──────────────────┤
                         │ id (PK)          │
                         │ character_id(FK) │
                         │ resource_id (FK) │
                         │ age              │
                         │ tag              │
                         │ is_default       │
                         └────────┬─────────┘
                                  │
                                  │ 关联资源
                                  ▼
       ┌────────────────────────────────────────────────┐
       │                        │                        │
       ▼                        ▼                        ▼
┌──────────────┐         ┌──────────────┐        ┌──────────────┐
│UserStoryProg │         │   Resource   │        │    Scene     │
├──────────────┤         ├──────────────┤        ├──────────────┤
│ user_id (FK) │         │ story_id(FK) │        │ story_id(FK) │
│ story_id(FK) │         │ url          │        │ scene_id     │
│ version_id   │         │ type         │        │ bg_res_id(FK)│
│ sequence_id  │         │ character_id │        │ music_res_id │
│ chapter_id   │         └──────────────┘        └──────────────┘
│ scene_id     │
└──────┬───────┘
       │
       │ 关联版本
       ▼
┌──────────────────┐
│  StoryVersion    │
│  (分支版本)       │
├──────────────────┤
│ id (PK)          │
│ story_id (FK)    │
│ prev_id (FK)     │
│ pioneer_user_id  │
│ fork_sequence_id │
│ option_id        │
│ current_seq_id   │
│ current_evt_type │
│ view_count       │
└──────────────────┘

┌──────────────┐
│GlobalSettings│
├──────────────┤
│ id (PK)      │
│ key          │
│ value        │
└──────────────┘
```

**关系说明**：
- **User → StoryPrompt**: 1对多，用户可以创建多个创意输入
- **StoryPrompt → Story**: 1对多，一个创意可以生成多个不同的故事
- **User → Story**: 1对多，用户拥有多个故事
- **Story → StoryVersion**: 1对多，一个故事有多个分支版本（**仅 type=interactive**）
- **StoryVersion → StoryVersion**: 自引用，通过 prev_id 形成版本链
- **User → StoryVersion**: 1对多，用户可以开拓多个分支（pioneer_user_id）
- **UserStoryProgress → StoryVersion**: 多对1，用户进度指向当前活跃版本（**仅 type=interactive**）
- **Story → Character**: 1对多，每个故事有多个角色
- **Character → CharacterPortrait**: 1对多，一个角色有多个立绘（不同年龄段、不同属性）
- **CharacterPortrait → Resource**: 多对1，立绘关联到资源表
- **StoryPrompt ⇢ Character**: 引用关系，创意中的角色ID必须存在于角色表
- **Story.type**:
  - `linear`: 线性叙事，无分支，不使用 story_versions 表
  - `interactive`: 互动叙事，支持分支，使用 story_versions 表
- **Character.source**: 
  - `DEFAULT`: 平台通用角色（user_id/story_id 为 NULL）
  - `USER`: 用户自定义角色
  - `AI`: AI生成角色
- **Character.prompt**: 角色外观描述，用于生成所有立绘
- **CharacterPortrait.age**: 支持多年龄段
- **CharacterPortrait.tag**: 单一属性标签
- **立绘生成**：组合 `prompt + tag` 生成

---

## 数据库表结构

### 扩展插件

全文搜索功能需要安装 pg_jieba 中文分词插件：

```sql
-- 安装插件（需管理员权限）
CREATE EXTENSION pg_jieba;

-- 验证安装
SELECT to_tsvector('jiebacfg', 'AI驱动的Visual Novel系统');
-- 预期结果: 'ai':1 'novel':4 'visual':3 '驱动':2 '系统':5
```

**说明**：pg_jieba 基于结巴分词，自动处理中英文混合文本。

---

### 1. 用户表（users）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | 用户ID |
| username | VARCHAR(64) | UNIQUE, NOT NULL | 用户名 |
| email | VARCHAR(128) | UNIQUE, NOT NULL | 邮箱 |
| password_hash | VARCHAR(256) | NOT NULL | 密码哈希 |
| settings | JSONB | DEFAULT | 用户设置（文字速度、音量等）|
| status | VARCHAR(20) | DEFAULT 'active' | 用户状态 |
| create_count | INTEGER | DEFAULT 0 | 创作故事数量 |
| view_count | INTEGER | DEFAULT 0 | 浏览故事数量 |
| like_count | INTEGER | DEFAULT 0 | 点赞故事数量 |
| favorite_count | INTEGER | DEFAULT 0 | 收藏故事数量 |
| share_count | INTEGER | DEFAULT 0 | 分享故事数量 |
| following_count | INTEGER | DEFAULT 0 | 关注数 |
| follower_count | INTEGER | DEFAULT 0 | 粉丝数 |
| level | INTEGER | DEFAULT 1 | 用户级别 |
| experience | INTEGER | DEFAULT 0 | 经验值 |
| balance | DECIMAL(10,2) | DEFAULT 0 | 灵感值余额 |
| total_recharged | DECIMAL(10,2) | DEFAULT 0 | 累计充值 |
| total_consumed | DECIMAL(10,2) | DEFAULT 0 | 累计消费 |
| search_vector | TSVECTOR | NULL | 全文搜索向量 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW | 更新时间 |
| deleted_at | TIMESTAMP | NULL | 注销时间 |

**用户状态枚举**：
- `active`：正常（默认）
- `suspended`：封禁（违规，可恢复）
- `deleted`：注销（用户主动注销）

**运营统计字段**：
- `create_count`：用户创作的故事总数，创建故事时 +1
- `view_count`：用户浏览的故事总数，进入故事时 +1（同一故事多次进入累计）
- `like_count`：用户点赞的故事总数，点赞 +1，取消点赞 -1
- `favorite_count`：用户收藏的故事总数，收藏 +1，取消收藏 -1
- `share_count`：用户分享故事的总次数，分享时 +1

**社交统计字段**：
- `following_count`：用户关注的人数，关注 +1，取消关注 -1
- `follower_count`：用户的粉丝数，被关注 +1，被取消关注 -1

**成长体系字段**：
- `level`：用户级别（1-10），决定权限和资源配额
- `experience`：经验值，通过创作、互动等行为积累
- `balance`：灵感值余额，用于消费 AIGC 算力
- `total_recharged`：累计充值的灵感值
- `total_consumed`：累计消费的灵感值

**用户级别体系**：

| 级别 | 经验值要求 | 权益 |
|------|-----------|------|
| 1 | 0 | 基础创作（每日限额 5 次）|
| 2 | 100 | 提升创作限额至 10 次/日 |
| 3 | 500 | 提升创作限额至 20 次/日 |
| 4 | 1500 | 解锁故事定价权 |
| 5 | 5000 | 更高分成比例（75%）|
| 6+ | ... | 更多高级功能 |

**经验值获取**：

| 行为 | 经验值 |
|------|--------|
| 每日签到 | +5 |
| 完成一个故事创作 | +20 |
| 故事被播放（每100次）| +10 |
| 故事被点赞 | +2 |
| 故事被收藏 | +3 |

**settings 字段结构**：
```json
{
  "text_speed": 50,
  "afm_enable": true,
  "afm_time": 15,
  "voice_volume": 1.0,
  "music_volume": 0.7,
  "sound_volume": 1.0,
  "ambient_volume": 0.7,
  "choice_timeout": 30
}
```

**字段说明**：
- `text_speed`：文字显示速度（字符/秒）
- `afm_enable`：是否启用自动推进
- `afm_time`：自动推进延迟（秒）
- `voice_volume`：配音音量（0-1），默认 1.0
- `music_volume`：音乐音量（0-1），默认 0.7
- `sound_volume`：音效音量（0-1），默认 1.0
- `ambient_volume`：环境音音量（0-1），默认 0.7
- `choice_timeout`：选项超时时间（秒），超时后自动选择第一个选项

**索引**：
- `idx_users_email`: `(email)`
- `idx_users_username`: `(username)`
- `idx_users_status`: `(status)`
- `idx_users_search`: `(search_vector)` USING GIN - 全文搜索

**搜索向量更新**（触发器）：
```sql
-- 用户名变更时自动更新搜索向量
CREATE FUNCTION users_search_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector := to_tsvector('jiebacfg', coalesce(NEW.username, ''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_search_update 
  BEFORE INSERT OR UPDATE OF username ON users
  FOR EACH ROW EXECUTE FUNCTION users_search_trigger();
```

---

### 2. 创意输入表（story_prompts）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | 创意ID |
| user_id | VARCHAR(64) | FK, NOT NULL | 所属用户 |
| logline | TEXT | NOT NULL | 一句话梗概（故事核心概念）|
| characters | JSONB | NOT NULL | 角色ID列表 |
| character_inputs | JSONB | NOT NULL | 用户输入的角色原始信息 |
| relationships | JSONB | NULL | 角色关系列表 |
| themes | JSONB | NOT NULL | 主题配置（多维度）|
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW | 更新时间 |

**characters 字段**（角色ID列表，后端处理后生成）：
```json
["char_001", "char_002", "char_003"]
```
- 由后端根据 character_inputs 创建角色后生成
- 角色ID对应 characters 表的 id

**character_inputs 字段**（用户输入的角色原始信息）：
```json
[
  {
    "name": "艾莉丝",
    "basic_info": {
      "gender": "女",
      "age": "青年",
      "identity": "量子物理学家"
    },
    "description": "冷静理性的科学家，对时间裂缝有独特见解"
  },
  {
    "name": "鲍勃",
    "basic_info": {
      "gender": "男",
      "age": "成年",
      "identity": "时空工程师，主角的上司"
    },
    "description": "热情冲动的冒险家，愿意为爱穿越时空"
  }
]
```

**relationships 字段**（角色关系列表）：
```json
[
  {
    "subject": "char_001",
    "object": "char_002",
    "relationship": "同事兼暗恋对象"
  }
]
```
- 创建时使用角色名称，后端处理后转换为角色ID

**themes 字段结构**（多维度主题配置）：
```json
{
  "genre": "科幻爱情",
  "tone": "轻松幽默",
  "setting": "未来都市",
  "style": "赛博朋克",
  "tags": ["时间旅行", "AI伦理", "都市奇幻"]
}
```

**约束**：
- FOREIGN KEY: `user_id` → `users.id`
- characters 中的角色ID必须存在于 characters 表中

**索引**：
- `idx_prompts_user_id`: `(user_id)`
- `idx_prompts_created_at`: `(created_at DESC)`

---

### 3. 故事表（stories）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | 故事ID |
| prompt_id | VARCHAR(64) | FK, NOT NULL | 关联的创意输入 |
| user_id | VARCHAR(64) | FK, NOT NULL | 所属用户 |
| type | ENUM | NOT NULL, DEFAULT 'linear' | 故事类型：linear / interactive |
| title | VARCHAR(256) | NULL | 故事标题（AI生成，可能为空）|
| cover_url | VARCHAR(512) | NULL | 封面图片URL |
| think | TEXT | NULL | AI思考规划内容 |
| script | TEXT | NULL | AI生成的结构化故事脚本 |
| status | ENUM | NOT NULL | 生成状态：pending/generating/dynamic/completed/error |
| visibility | VARCHAR(20) | DEFAULT 'draft' | 可见性状态 |
| published_at | TIMESTAMP | NULL | 发布时间 |
| play_count | INTEGER | DEFAULT 0 | 播放次数 |
| like_count | INTEGER | DEFAULT 0 | 点赞数 |
| favorite_count | INTEGER | DEFAULT 0 | 收藏数 |
| share_count | INTEGER | DEFAULT 0 | 分享次数 |
| comment_count | INTEGER | DEFAULT 0 | 评论数 |
| pricing_type | VARCHAR(20) | DEFAULT 'free' | 定价类型 |
| price | DECIMAL(10,2) | DEFAULT 0 | 价格（灵感值）|
| total_revenue | DECIMAL(10,2) | DEFAULT 0 | 累计收入（灵感值）|
| search_vector | TSVECTOR | NULL | 全文搜索向量 |
| error_message | TEXT | NULL | 错误信息 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW | 更新时间 |
| completed_at | TIMESTAMP | NULL | 完成时间 |
| deleted_at | TIMESTAMP | NULL | 删除/下架时间 |

**类型枚举**：
- `linear`: 线性叙事（无分支互动，不记录版本）
- `interactive`: 互动叙事（支持分支选择，记录版本）

**定价类型枚举（pricing_type）**：
- `free`: 免费（默认）
- `paid`: 付费（需要一次性支付全部价格）

**生成状态枚举（status）**：
- `pending`: 待生成（think 和 script 未生成）
- `generating`: 生成中（think 和 script 已生成，正在生成详细内容）
- `dynamic`: 动态分支中（**仅 interactive 类型**，遇到用户选择分支后进入）
- `completed`: 已完成（到达 story_end 事件）
- `error`: 生成失败

**可见性状态枚举（visibility）**：
- `draft`: 草稿（仅作者可见，默认）
- `published`: 已发布（公开可见，出现在广场）
- `hidden`: 隐藏（作者主动隐藏，不公开）
- `removed`: 下架（违规，管理员操作）
- `deleted`: 删除（软删除）

**业务规则**：
- 用户注销时，其故事自动设为 `visibility='hidden'`
- 用户恢复时，故事需手动恢复发布状态
- `removed` 状态需通知作者并说明原因

**定价规则**：
- 仅 `level >= 4` 的用户可设置定价（定价权）
- 付费故事的用户购买后永久可读
- 创作者获得收入的 70% 分成（level 5+ 为 75%）
- 平台抽成用于运营和算力成本

**约束**：
- FOREIGN KEY: `prompt_id` → `story_prompts.id`
- FOREIGN KEY: `user_id` → `users.id`

**索引**：
- `idx_stories_prompt_id`: `(prompt_id)`
- `idx_stories_user_id`: `(user_id)`
- `idx_stories_type`: `(type)`
- `idx_stories_status`: `(status)`
- `idx_stories_visibility`: `(visibility)`
- `idx_stories_pricing_type`: `(pricing_type)` - 付费筛选
- `idx_stories_created_at`: `(created_at DESC)`
- `idx_stories_user_created`: `(user_id, created_at DESC)`
- `idx_stories_published`: `(visibility, published_at DESC)` - 广场推荐查询
- `idx_stories_search`: `(search_vector)` USING GIN - 全文搜索

**搜索向量更新**（触发器）：
```sql
-- 故事标题变更时自动更新搜索向量（结合创意表的 logline）
CREATE FUNCTION stories_search_trigger() RETURNS trigger AS $$
DECLARE
  logline_text TEXT;
BEGIN
  -- 获取关联创意的 logline
  SELECT logline INTO logline_text FROM story_prompts WHERE id = NEW.prompt_id;
  
  NEW.search_vector := to_tsvector('jiebacfg', 
    coalesce(NEW.title, '') || ' ' || coalesce(logline_text, ''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER stories_search_update 
  BEFORE INSERT OR UPDATE OF title ON stories
  FOR EACH ROW EXECUTE FUNCTION stories_search_trigger();
```

**说明**：
- 一个创意（prompt）可以生成多个不同的故事
- title 允许为空，AI生成过程中可能尚未确定标题
- think 存储AI的思考规划内容，用于：
  - 记录AI对创意的理解和分析
  - 保存故事构思和创作思路
  - 包含对主题、风格、角色、冲突等方面的思考
- script 存储AI生成的结构化故事脚本，用于：
  - 保存基于思考后产出的结构化大纲
  - 后续编辑或重新生成时作为参考
  - 包含章节大纲、场景设计、角色弧光、关键剧情点等

**线性叙事 vs 互动叙事**：

| 特性 | linear（线性叙事）| interactive（互动叙事）|
|------|------------------|----------------------|
| 分支选择 | ❌ 无 choice 事件 | ✅ 支持 choice 事件 |
| story_versions | ❌ 不记录 | ✅ 记录版本树 |
| dynamic 状态 | ❌ 不适用 | ✅ 遇到 choice 后进入 |
| 性能开销 | 最小（无版本管理）| 正常（按需记录分支）|

**发布规则**：

| 故事类型 | 发布条件 | 说明 |
|---------|---------|------|
| `linear` | `status = completed` | 线性叙事必须完成才能发布 |
| `interactive` | `status IN (dynamic, completed)` | 互动叙事创作完成（有内容）即可发布 |

**发布说明**：
- `is_published = true` 的故事会出现在广场（首页推荐）
- 发布后其他用户可以浏览和播放
- 线性叙事：必须到达 `story_end`（completed 状态）才能发布
- 互动叙事：只要有可播放内容（dynamic 或 completed）即可发布
- 发布后仍可继续创作（互动叙事可继续探索新分支）

**状态流转逻辑**：

```
=== type = linear（线性叙事）===

pending (初始状态)
   │ think 和 script 生成完成
   ▼
generating (生成详细内容)
   │ 到达 story_end
   ▼
completed (故事结束)

error (任何阶段都可能出错)


=== type = interactive（互动叙事）===

pending (初始状态)
   │ think 和 script 生成完成
   ▼
generating (生成详细内容)
   │ 遇到 choice 事件（用户选择分支）
   ▼
dynamic (动态分支中)
   │ ┌─ 继续遇到 choice → 保持 dynamic
   │ └─ 到达 story_end 事件 → completed
   ▼
completed (故事结束)

error (任何阶段都可能出错)
```

**注**：
- **线性叙事**：generating → completed，无 dynamic 状态，不记录 story_versions
- **互动叙事**：遇到 choice 进入 dynamic 状态，记录 story_versions
- 完成条件：到达 story_end 事件

---

### 4. 故事事件表（story_events）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增ID |
| story_id | VARCHAR(64) | FK, NOT NULL | 所属故事 |
| sequence_id | VARCHAR(128) | UNIQUE, NOT NULL | 全局唯一序列ID（ULID或UUID）|
| next_sequence_id | VARCHAR(128) | NULL | 下一个事件的序列ID |
| event_category | VARCHAR(20) | NOT NULL | story / system |
| event_type | VARCHAR(50) | NOT NULL | 具体事件类型 |
| content | JSONB | NOT NULL | 事件内容 |
| chapter_id | VARCHAR(64) | NULL | 所属章节 |
| scene_id | VARCHAR(64) | NULL | 所属场景 |
| timestamp | VARCHAR(30) | NOT NULL | 事件时间戳 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |

**event_type 枚举**：
- Story 事件：`story_start`, `story_end`, `chapter_start`, `chapter_end`, `scene_start`, `scene_end`, `dialogue`, `narration`, `play_audio`, `play_video`, `choice`
- System 事件：`heartbeat`, `error`

**链式遍历字段说明**：
- `sequence_id`：全局唯一ID（ULID/UUID），不编码业务逻辑
- `next_sequence_id`：指向下一个事件的 sequence_id（链表指针）
  - 线性事件：指向下一个事件
  - choice 事件：为 NULL（分支跳转信息在 options 中指定）
  - story_end 事件：为 NULL（终点）

**索引**：
- `idx_story_events_sequence`: `(sequence_id)` - 链式遍历核心索引
- `idx_story_events_story`: `(story_id, event_type)` - 查询故事起点
- `idx_story_events_chapter`: `(story_id, chapter_id)`
- `idx_story_events_scene`: `(story_id, scene_id)`

---

### 事件链式结构与遍历

#### 链式结构示例

**线性故事**（单链表）：
```
seq_001: story_start
    └─► next: seq_002
seq_002: dialogue
    └─► next: seq_003
seq_003: dialogue
    └─► next: seq_004
seq_004: story_end
    └─► next: NULL（终点）
```

**分支故事**（树形链表）：
```
seq_001: story_start
    └─► next: seq_002
seq_002: dialogue
    └─► next: seq_003
seq_003: choice (next = NULL)
    ├─► option_a.next_sequence_id: seq_a01
    └─► option_b.next_sequence_id: seq_b01

seq_a01: dialogue (分支A)
    └─► next: seq_a02
seq_a02: story_end
    └─► next: NULL

seq_b01: dialogue (分支B)
    └─► next: seq_b02
seq_b02: choice (next = NULL)
    ├─► option_c.next_sequence_id: seq_c01
    └─► option_d.next_sequence_id: seq_d01
  ...
```

#### 链式遍历算法（游戏模式）

```python
def traverse_story(story_id: str, start_sequence_id: str = None):
    """
    链式遍历故事事件（游戏模式）
    
    每次遇到 choice 事件都等待用户重新选择
    
    Args:
        story_id: 故事ID
        start_sequence_id: 起点事件ID（用于断点续传），默认从头开始
    
    时间复杂度：O(n)，n为遍历的事件数
    空间复杂度：O(1)，无需加载全部事件
    """
    # 1. 确定起点
    if start_sequence_id:
        # 断点续传：从指定事件开始
        current_event = db.query(StoryEvent).filter_by(
            sequence_id=start_sequence_id
        ).one()
    else:
        # 从头开始：查询 story_start 事件
        current_event = db.query(StoryEvent).filter_by(
            story_id=story_id,
            event_type='story_start'
        ).one()
    
    # 2. 链式遍历
    while current_event:
        # 推送事件到前端（SSE）
        yield current_event
        
        # 3. 确定下一个事件
        if current_event.event_type == 'choice':
            # 等待用户选择（暂停 SSE 推送）
            option_id = await wait_for_user_choice()
            
            # 从 options 中获取 next_sequence_id
            option = next(
                o for o in current_event.content['options'] 
                if o['option_id'] == option_id
            )
            next_seq_id = option['next_sequence_id']
            
            # 检查分支是否已生成
            next_event = db.query(StoryEvent).filter_by(
                sequence_id=next_seq_id
            ).first()
            
            if not next_event:
                # 分支未生成，触发 AI 动态生成
                await generate_branch(story_id, option_id, next_seq_id)
            
        elif current_event.event_type == 'story_end':
            # 故事结束（当前分支）
            break
            
        else:
            # 普通事件：使用 next_sequence_id
            next_seq_id = current_event.next_sequence_id
        
        # 4. 查询下一个事件（O(1) 查询）
        if next_seq_id:
            current_event = db.query(StoryEvent).filter_by(
                sequence_id=next_seq_id
            ).one_or_none()
            
            if not current_event:
                logger.error(f"Event not found: {next_seq_id}")
                break
        else:
            break
```

**推进策略**：
- 线性事件：自动推进到下一个（通过 next_sequence_id）
- choice 事件：暂停推送，等待用户选择
- 用户选择后：根据 option.next_sequence_id 跳转到对应分支
- story_end：停止推送（当前分支结束）

#### 查询性能

**关键索引**：
```sql
-- 必需：链式遍历核心索引（O(1) 查询）
CREATE UNIQUE INDEX idx_story_events_sequence ON story_events(sequence_id);

-- 必需：查询故事起点（O(1) 查询）
CREATE INDEX idx_story_events_start ON story_events(story_id, event_type);
```

**查询效率**：
- 查询起点：`O(1)` - 精确查询 `(story_id, event_type='story_start')`
- 链式遍历：`O(n)` - n 次 O(1) 查询，总时间复杂度 O(n)
- 无需全表扫描，无需排序，性能最优

#### 数据一致性

**约束**：
```sql
-- sequence_id 全局唯一
ALTER TABLE story_events ADD CONSTRAINT uk_sequence_id UNIQUE (sequence_id);
```

#### 数据示例

**线性故事**：
```sql
-- 事件1：故事开始
INSERT INTO story_events (
  story_id, sequence_id, next_sequence_id, event_type, content
) VALUES (
  'story_abc123', '01JG8XYZ001', '01JG8XYZ002',
  'story_start', '{"story_id":"story_abc123","title":"时空之旅"}'
);

-- 事件2：对话
INSERT INTO story_events (
  story_id, sequence_id, next_sequence_id, event_type, content
) VALUES (
  'story_abc123', '01JG8XYZ002', '01JG8XYZ003',
  'dialogue', '{"character_name":"艾莉丝","text":"..."}'
);

-- 事件3：故事结束
INSERT INTO story_events (
  story_id, sequence_id, next_sequence_id, event_type, content
) VALUES (
  'story_abc123', '01JG8XYZ003', NULL,
  'story_end', '{"story_id":"story_abc123"}'
);
```

**分支故事**：
```sql
-- 分支点：choice 事件（next_sequence_id 为 NULL，分支信息在 options 中）
INSERT INTO story_events (
  story_id, sequence_id, next_sequence_id, event_type, content
) VALUES (
  'story_abc123', '01JG8XYZ003', NULL,
  'choice', '{
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
  }'
);

-- 分支A 事件
INSERT INTO story_events (
  story_id, sequence_id, next_sequence_id, event_type, content
) VALUES (
  'story_abc123', '01JG8Y12ABC', '01JG8Y12BCD',
  'dialogue', '{"text":"你按下了按钮..."}'
);

-- 分支B 事件
INSERT INTO story_events (
  story_id, sequence_id, next_sequence_id, event_type, content
) VALUES (
  'story_abc123', '01JG8Y34DEF', '01JG8Y34EFG',
  'dialogue', '{"text":"你决定离开..."}'
);
```

#### 原生AI互动叙事：无状态游戏模式

**核心设计**：
- 只记录当前状态（current_event_id）
- 不记录历史选择
- 通过统一的有向图链式遍历推进

**断点续传**：
```python
def resume_from_progress(story_id: str, user_id: str):
    """从断点继续"""
    progress = get_user_progress(user_id, story_id)
    
    # 从断点事件开始链式遍历
    for event in traverse_story(story_id, start_sequence_id=progress.current_event_id):
        yield event
        # 遇到 choice → 暂停推送，等待用户选择
        # 用户选择后 → 根据 option.next_sequence_id 继续
```

**游玩流程**：
```
第一次游玩：
  story_start → dialogue → choice [用户选A] → dialogue_A → 退出
  保存：current_event_id = dialogue_A 的 sequence_id

第二次游玩（断点续传）：
  从 dialogue_A 的 sequence_id 继续 
  → ... → 遇到新 choice → 用户重新选择（可能选B，结局不同）
  保存：更新 current_event_id 为新位置

第三次游玩：
  可以从头开始（探索不同路径）
  或从上次断点继续
```

**特点**：
- ✅ **简洁性**：只关注"用户在哪里"，不关注"用户怎么来的"
- ✅ **灵活性**：每次遇到分支都是新的选择
- ✅ **可重玩**：用户可以多次游玩，每次探索不同路径
- ✅ **原生AI**：故事由AI动态生成，没有预设路径

#### 核心优势

1. ✅ **高效遍历**：O(n) 时间复杂度，只查询需要的事件
2. ✅ **精确跳转**：通过 next_sequence_id 直接定位，无需搜索
3. ✅ **极简结构**：只需 sequence_id + next_sequence_id 形成链表
4. ✅ **按需生成**：分支可以在用户选择时动态生成
5. ✅ **数据复用**：已生成的分支可以被其他用户复用
6. ✅ **统一模型**：线性故事和分支故事使用相同的链式结构
7. ✅ **断点续传**：从 current_event_id 继续，遇到 choice 重新选择（游戏模式）
8. ✅ **前端过滤**：SSE 事件携带 path_id，前端按当前路径过滤播放

---

### 5. 角色表（characters）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | 角色ID |
| user_id | VARCHAR(64) | FK, NULL | 所属用户（平台角色为NULL）|
| story_id | VARCHAR(64) | FK, NULL | 所属故事（平台角色为NULL）|
| source | ENUM | NOT NULL | 来源：DEFAULT / USER / AI |
| name | VARCHAR(64) | NOT NULL | 角色名 |
| gender | ENUM | NOT NULL | 性别：male / female |
| name_color | VARCHAR(10) | NULL | 名字颜色（#ff6b9d）|
| voice_id | VARCHAR(64) | NULL | TTS 音色ID |
| details | JSONB | NULL | 角色详细信息（多维度，含各年龄段提示词）|
| default_position | VARCHAR(16) | DEFAULT 'center' | 默认位置 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |

**gender 枚举**：
- `male`: 男性
- `female`: 女性

**source 枚举**：
- `DEFAULT`: 平台提供的通用角色（user_id 和 story_id 为 NULL）
- `USER`: 用户在创意输入中定义的角色
- `AI`: AI在故事生成过程中补充的角色

**details 字段说明**：
- 存储角色的详细信息，包括基本信息、外观描述、各年龄段的图像生成提示词等
- 按年龄段（childhood / adolescence / youth / adult / elderly）分别存储提示词，用于生成对应年龄段的角色立绘
- AI 在"开始创作"时根据角色信息预测生成该字段内容

**约束**：
- FOREIGN KEY: `user_id` → `users.id` (允许 NULL)
- FOREIGN KEY: `story_id` → `stories.id` (允许 NULL)
- CHECK: `(source = 'DEFAULT' AND user_id IS NULL AND story_id IS NULL) OR (source != 'DEFAULT')`

**索引**：
- `idx_characters_user_id`: `(user_id)`
- `idx_characters_story`: `(story_id)`
- `idx_characters_source`: `(source)`
- `idx_characters_gender`: `(gender)`

**角色类型说明**：
- **平台角色**（source=platform）：user_id 和 story_id 都为 NULL，供所有用户使用
- **用户角色**（source=user_defined）：用户在创意输入中定义，可在多个故事中复用
- **AI角色**（source=ai_generated）：AI在故事生成过程中补充，属于特定故事

---

### 6. 角色立绘表（character_portraits）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | 立绘ID |
| character_id | VARCHAR(64) | FK, NOT NULL | 所属角色 |
| resource_id | VARCHAR(64) | FK, NOT NULL | 关联资源 |
| age | ENUM | NOT NULL | 年龄段 |
| tag | VARCHAR(128) | NOT NULL | 属性标签（单一维度）|
| is_default | BOOLEAN | DEFAULT FALSE | 是否为默认立绘 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |

**age 枚举**（年龄段）：
- `childhood`: 童年（0-12岁）
- `adolescence`: 少年（13-17岁）
- `youth`: 青年（18-30岁）
- `adult`: 成年（31-50岁）
- `elderly`: 老年（51岁以上）

**tag 字段说明**（属性标签，单一维度）：
- 用于描述立绘的主要特征或情绪状态
- 示例值：`happy`, `sad`, `angry`, `worried`, `neutral`, `surprised`, `smile`, `serious`, `normal` 等

**约束**：
- FOREIGN KEY: `character_id` → `characters.id`
- FOREIGN KEY: `resource_id` → `resources.id`
- UNIQUE: 每个角色在同一年龄段只能有一个默认立绘 `(character_id, age, is_default)` WHERE `is_default = TRUE`

**索引**：
- `idx_portraits_character`: `(character_id)`
- `idx_portraits_age`: `(character_id, age)`
- `idx_portraits_default`: `(character_id, is_default)`

**说明**：
- 一个角色可以有多个立绘（不同年龄段、不同属性）
- 同一年龄段可以有多个立绘（不同情绪、表情等）
- `is_default` 标记该年龄段的默认立绘
- `tag` 描述立绘的主要特征（如 happy, sad, worried, normal 等）

---

### 7. 资源表（resources）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | 资源ID |
| story_id | VARCHAR(64) | FK, NOT NULL | 所属故事 |
| type | ENUM | NOT NULL | image/animated_image/video/audio/voice |
| url | VARCHAR(512) | NOT NULL | CDN URL |
| format | VARCHAR(16) | NULL | webp/ogg/mp4等 |
| size_bytes | INTEGER | NULL | 文件大小 |
| duration | FLOAT | NULL | 时长（音视频）|
| width | INTEGER | NULL | 宽度（图像/视频）|
| height | INTEGER | NULL | 高度（图像/视频）|
| character_id | VARCHAR(64) | NULL | 关联角色 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |

**type 枚举**：
- `image`: 静态图像
- `animated_image`: 动态图像
- `video`: 视频
- `audio`: 音频（音乐、音效）
- `voice`: 配音

**索引**：
- `idx_resources_story`: `(story_id)`
- `idx_resources_type`: `(type)`
- `idx_resources_character`: `(character_id)`

---

### 8. 场景表（scenes）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增ID |
| story_id | VARCHAR(64) | FK, NOT NULL | 所属故事 |
| scene_id | VARCHAR(64) | NOT NULL | 场景ID（故事内唯一）|
| scene_name | VARCHAR(128) | NULL | 场景名称 |
| background_resource_id | VARCHAR(64) | FK, NULL | 背景资源ID |
| music_resource_id | VARCHAR(64) | FK, NULL | 音乐资源ID |
| ambient_resource_id | VARCHAR(64) | FK, NULL | 环境音资源ID |
| transition_config | JSONB | NULL | 转场配置（优先级高于全局配置）|
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW | 更新时间 |

**transition_config 字段结构**：
```json
{
  "fade_in": {
    "type": "fade_in",
    "duration": 1.5
  },
  "fade_out": {
    "type": "fade_out",
    "duration": 1.0
  }
}
```

**说明**：
- 场景关联故事的背景、音乐、环境音资源（通过 resources 表）
- 人物立绘不在场景表中管理，由 dialogue 事件动态控制
- `transition_config` 为 NULL 时使用全局转场配置
- 场景可后期编辑修改资源和转场参数

**约束**：
- UNIQUE: `(story_id, scene_id)`
- FOREIGN KEY: `background_resource_id` → `resources.id`
- FOREIGN KEY: `music_resource_id` → `resources.id`
- FOREIGN KEY: `ambient_resource_id` → `resources.id`

**索引**：
- `idx_scenes_story`: `(story_id)`
- `idx_scenes_scene_id`: `(story_id, scene_id)`

---

### 9. 全局配置表（global_settings）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增ID |
| key | VARCHAR(64) | UNIQUE, NOT NULL | 配置键 |
| value | JSONB | NOT NULL | 配置值 |
| description | TEXT | NULL | 配置说明 |
| updated_at | TIMESTAMP | DEFAULT NOW | 更新时间 |

**预设配置项**：

1. **全局转场配置**（`transition.default`）：
```json
{
  "fade_in": {
    "type": "fade_in",
    "duration": 1.5
  },
  "fade_out": {
    "type": "fade_out",
    "duration": 1.0
  }
}
```

2. **角色显示配置**（`character.default`）：
```json
{
  "position": "center",
  "auto_hide": true
}
```

3. **角色颜色配置**（`character.colors`）：
```json
{
  "default": "#ffffff",
  "colors": [
    "#ff6b9d",
    "#6b9dff",
    "#9dff6b",
    "#ff9d6b",
    "#9d6bff",
    "#6bffff"
  ]
}
```

**说明**：
- `character.default` - 角色立绘的默认显示位置和自动隐藏行为
- `character.colors` - 角色名字颜色配置，系统会从颜色池中自动分配给新角色
- 事件中未指定的 `character_color` 和 `position` 使用全局默认值

**索引**：
- `idx_global_settings_key`: `(key)`

---

### 10. 用户进度表（user_story_progress）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增ID |
| user_id | VARCHAR(64) | FK, NOT NULL | 用户ID |
| story_id | VARCHAR(64) | FK, NOT NULL | 故事ID |
| current_version_id | VARCHAR(64) | FK, NULL | 当前活跃的分支版本ID |
| current_sequence_id | VARCHAR(128) | NULL | 用户播放进度（当前事件的 sequence_id）|
| current_chapter_id | VARCHAR(64) | NULL | 当前章节ID |
| current_scene_id | VARCHAR(64) | NULL | 当前场景ID |
| play_time | INTEGER | DEFAULT 0 | 累计播放时长（秒）|
| started_at | TIMESTAMP | DEFAULT NOW | 开始时间 |
| last_played_at | TIMESTAMP | DEFAULT NOW | 最后播放时间 |

**约束**：
- UNIQUE: `(user_id, story_id)`
- FOREIGN KEY: `current_version_id` → `story_versions.id`

**索引**：
- `idx_progress_user`: `(user_id)`
- `idx_progress_last_played`: `(user_id, last_played_at DESC)`
- `idx_progress_version`: `(current_version_id)`

**设计原则：版本化分支管理 + 延迟同步**

本系统采用**版本化分支模式**，通过 `story_versions` 表管理用户的分支路径：

- `current_version_id`：指向用户当前活跃的分支版本（断点续传的核心）
- `current_chapter_id`：当前章节（用于UI展示，如"继续第三章"）
- `current_scene_id`：当前场景（用于恢复场景状态：背景、音乐等）
- ✅ **通过版本链追溯历史选择**：递归 `story_versions.prev_id` 可还原完整选择路径
- ✅ **支持分支共享**：其他用户可以播放已开拓的分支版本

**线性叙事 vs 互动叙事**：

| 故事类型 | current_version_id | 说明 |
|---------|-------------------|------|
| `linear` | NULL | 无分支，不使用版本管理 |
| `interactive` | 指向 story_versions.id | 有分支，记录当前活跃版本 |

**同步策略（性能优化）**：
- ❌ **不是每次点击都写库**：避免高频写入带来的性能问题
- ✅ **关键点同步**：仅在 `choice`、`scene_start`、`chapter_start`、`story_end` 时同步
- ✅ **退出时同步**：用户关闭页面时通过 `sendBeacon` 保存进度
- ⚠️ **可接受的进度丢失**：最多回退到上一个场景/章节起点

**章节说明**：
- **线性故事**：章节是预设的，顺序推进
- **动态分支故事**：章节可以在不同分支中动态生成，用户在不同路径可能经历不同的章节

---

### 11. 故事版本表（story_versions）

> **适用范围**：仅 `type = interactive` 的故事使用此表。`type = linear` 的线性叙事不记录版本。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | 版本ID |
| story_id | VARCHAR(64) | FK, NOT NULL | 所属故事（必须是 interactive 类型）|
| prev_id | VARCHAR(64) | FK, NULL | 父版本（root版本为NULL）|
| pioneer_user_id | VARCHAR(64) | FK, NOT NULL | 开拓者用户ID |
| fork_sequence_id | VARCHAR(128) | NULL | 分叉点的 choice 事件 sequence_id |
| option_id | VARCHAR(64) | NULL | 在分叉点选择的选项ID |
| current_sequence_id | VARCHAR(128) | NOT NULL | 当前位置的 sequence_id |
| current_event_type | VARCHAR(50) | NOT NULL | 当前位置的事件类型 |
| view_count | INTEGER | DEFAULT 0 | 访问/播放次数 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW | 更新时间 |

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `prev_id` | 静态 | 链式追溯，形成版本树 |
| `pioneer_user_id` | 静态 | 记录谁最先开拓了这个分支 |
| `fork_sequence_id` | 静态 | 从哪个 choice 事件分叉出来的 |
| `option_id` | 静态 | 在那个 choice 选择了什么选项 |
| `current_sequence_id` | 动态 | **开拓高水位**：该版本被探索到的最远位置 |
| `current_event_type` | 动态 | 开拓高水位的事件类型（用于判断版本状态）|
| `view_count` | 动态 | 该版本被用户访问/播放的次数（用于热度统计）|

**关于 `current_sequence_id` 的语义**：
- 这是**开拓进度**，不是用户的播放进度
- 只有当用户推进到比当前值更远的位置时才更新
- 重播已有内容不会触发更新，大幅减少写入频率
- 用户个人的播放进度存储在 `user_story_progress` 表中

**约束**：
- FOREIGN KEY: `story_id` → `stories.id`
- FOREIGN KEY: `prev_id` → `story_versions.id`
- FOREIGN KEY: `pioneer_user_id` → `users.id`

**索引**：
- `idx_versions_story`: `(story_id)`
- `idx_versions_prev`: `(prev_id)`
- `idx_versions_pioneer`: `(pioneer_user_id)`
- `idx_versions_fork`: `(story_id, fork_sequence_id, option_id)`

**版本状态判断**：
```python
if version.current_event_type == 'story_end':
    # 已完结，可以完整播放
elif version.current_event_type == 'choice':
    # 停在选择点，可以继续探索或分叉
else:
    # 生成中 / 中途离开
```

**版本链示例**：
```
v_001 (root)
  pioneer: user_A
  fork: NULL
  current: story_end
    │
    └─► v_002 (fork from choice_010, chose option_a)
          pioneer: user_A
          current: dialogue_020
            │
            └─► v_003 (fork from choice_030, chose option_x)
                  pioneer: user_B  ← 其他用户也可以成为开拓者
                  current: story_end
```

**追溯完整选择路径**：
```python
def get_choice_path(version_id: str) -> list:
    """递归追溯版本链，重建完整的选择路径"""
    path = []
    v = db.get_version(version_id)
    
    while v:
        if v.fork_sequence_id:  # 非 root 版本
            path.insert(0, {
                "choice_id": v.fork_sequence_id,
                "option_id": v.option_id
            })
        v = db.get_version(v.prev_id) if v.prev_id else None
    
    return path
```

**更新逻辑**：

> 以下逻辑仅适用于 `type = interactive` 的互动叙事。`type = linear` 的线性叙事不使用 `story_versions` 表。

1. **创建互动故事时** → 创建 root 版本：
```sql
-- 仅当 stories.type = 'interactive' 时执行
INSERT INTO story_versions (id, story_id, prev_id, pioneer_user_id, 
  fork_sequence_id, option_id, current_sequence_id, current_event_type)
VALUES ('v_001', 'story_001', NULL, 'user_A', 
  NULL, NULL, 'seq_001', 'story_start');
```

2. **用户开拓新内容时** → 更新版本的开拓进度（仅当推进到比当前更远时）：
```python
def on_user_advance(user_id, version_id, new_sequence_id):
    version = db.get(version_id)
    
    # 只有当用户推进到比开拓进度更远时，才更新版本
    if is_ahead_of(new_sequence_id, version.current_sequence_id):
        # 开拓新内容 → 更新版本（低频）
        db.execute("""
            UPDATE story_versions 
            SET current_sequence_id = %s, current_event_type = %s, updated_at = NOW()
            WHERE id = %s
        """, [new_sequence_id, get_event_type(new_sequence_id), version_id])
    
    # 用户播放进度 → 使用延迟同步策略（见下文）
```

> **性能优化**：如果用户只是"重播"已有内容（别人开拓过的），不会触发版本更新。只有"开拓新内容"时才写库。

3. **用户在 choice 做选择时** → 创建新版本：
```sql
INSERT INTO story_versions (id, story_id, prev_id, pioneer_user_id,
  fork_sequence_id, option_id, current_sequence_id, current_event_type)
VALUES ('v_002', 'story_001', 'v_001', 'user_A',
  'choice_010', 'option_a', 'seq_011', 'dialogue');

-- 同时更新用户进度指向新版本
UPDATE user_story_progress 
SET current_version_id = 'v_002'
WHERE user_id = 'user_A' AND story_id = 'story_001';
```

4. **其他用户播放已有分支** → 复用版本，无需创建：
```sql
-- 用户B 播放 用户A 开拓的 v_002 分支
UPDATE user_story_progress 
SET current_version_id = 'v_002'
WHERE user_id = 'user_B' AND story_id = 'story_001';
```

5. **其他用户在已有分支上做不同选择** → 成为新开拓者：
```sql
-- 用户B 在 v_002 的 choice_030 选择了 option_y（用户A 之前没选过）
INSERT INTO story_versions (id, story_id, prev_id, pioneer_user_id,
  fork_sequence_id, option_id, current_sequence_id, current_event_type)
VALUES ('v_004', 'story_001', 'v_002', 'user_B',  -- user_B 成为开拓者
  'choice_030', 'option_y', 'seq_031', 'dialogue');
```

---

### 12. 评论表（story_comments）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | 评论ID |
| story_id | VARCHAR(64) | FK, NOT NULL | 故事ID |
| user_id | VARCHAR(64) | FK, NOT NULL | 评论用户 |
| parent_id | VARCHAR(64) | FK, NULL | 父评论ID（支持回复）|
| content | TEXT | NOT NULL | 评论内容（1-500字符）|
| like_count | INTEGER | DEFAULT 0 | 点赞数 |
| status | VARCHAR(20) | DEFAULT 'visible' | 状态 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW | 更新时间 |

**状态枚举**：
- `visible`：正常显示（默认）
- `hidden`：用户删除（软删除）
- `removed`：违规删除（管理员操作）

**约束**：
- FOREIGN KEY: `story_id` → `stories.id`
- FOREIGN KEY: `user_id` → `users.id`
- FOREIGN KEY: `parent_id` → `story_comments.id`

**索引**：
- `idx_comments_story`: `(story_id, status, created_at DESC)` - 故事评论列表
- `idx_comments_user`: `(user_id, created_at DESC)` - 用户评论历史
- `idx_comments_parent`: `(parent_id)` - 回复查询

**业务规则**：
- 仅登录用户可评论
- 评论内容 1-500 字符
- 回复层级最多 2 层（评论 → 回复，回复不可再回复）
- 用户删除为软删除（`status='hidden'`），内容显示为"该评论已删除"

---

### 13. 关注关系表（user_follows）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增ID |
| follower_id | VARCHAR(64) | FK, NOT NULL | 关注者（粉丝）|
| following_id | VARCHAR(64) | FK, NOT NULL | 被关注者（创作者）|
| created_at | TIMESTAMP | DEFAULT NOW | 关注时间 |

**约束**：
- UNIQUE: `(follower_id, following_id)` - 不能重复关注
- CHECK: `follower_id != following_id` - 不能关注自己
- FOREIGN KEY: `follower_id` → `users.id`
- FOREIGN KEY: `following_id` → `users.id`

**索引**：
- `idx_follows_follower`: `(follower_id, created_at DESC)` - 我的关注列表
- `idx_follows_following`: `(following_id, created_at DESC)` - 我的粉丝列表

**说明**：
- 关注关系独立于故事行为，不记录到 `user_behavior_logs`
- 关注/取消关注时同步更新双方的 `following_count` 和 `follower_count`

---

### 14. 用户行为表（user_behavior_logs）

> 记录用户与故事的交叉行为，用于行为统计和个性化推荐。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGSERIAL | PK | 自增ID |
| user_id | VARCHAR(64) | FK, NOT NULL | 用户ID |
| story_id | VARCHAR(64) | FK, NOT NULL | 故事ID |
| action | VARCHAR(32) | NOT NULL | 行为类型 |
| metadata | JSONB | NULL | 行为附加信息 |
| created_at | TIMESTAMP | DEFAULT NOW | 行为时间（分区键）|

**行为类型（action）**：

| 行为 | 说明 | metadata 示例 |
|------|------|---------------|
| `create` | 创建故事 | `{"prompt_id": "..."}` |
| `enter` | 进入故事 | `{"version_id": "...", "from": "explore"}` |
| `exit` | 退出故事 | `{"play_time": 120, "current_event_id": "..."}` |
| `complete` | 完成故事 | `{"version_id": "...", "total_time": 3600}` |
| `like` | 点赞 | `{}` |
| `unlike` | 取消点赞 | `{}` |
| `favorite` | 收藏 | `{}` |
| `unfavorite` | 取消收藏 | `{}` |
| `share` | 分享 | `{"platform": "wechat"}` |
| `choice` | 选择分支 | `{"choice_id": "...", "option_id": "..."}` |
| `comment` | 发表评论 | `{"comment_id": "..."}` |
| `comment_like` | 点赞评论 | `{"comment_id": "..."}` |
| `comment_unlike` | 取消点赞评论 | `{"comment_id": "..."}` |
| `purchase` | 购买故事 | `{"price": 50.00, "transaction_id": "..."}` |
| `tip` | 打赏创作者 | `{"amount": 10.00, "transaction_id": "..."}` |

> **注意**：`purchase` 行为同时用于判断用户是否已购买某故事（替代独立的购买记录表），查询时按 `(user_id, story_id, action='purchase')` 检索。

**记录时机**：

| 行为 | 触发接口/时机 |
|------|--------------|
| `create` | `POST /story/create` 创建故事时 |
| `enter` | SSE 连接建立时 |
| `exit` | `POST /story/{story_id}/progress` 保存进度时 |
| `complete` | 后端推送 `story_end` 事件时 |
| `like` / `unlike` | `POST/DELETE /story/{story_id}/like` |
| `favorite` / `unfavorite` | `POST/DELETE /story/{story_id}/favorite` |
| `share` | `POST /story/{story_id}/share` |
| `choice` | 后端处理分支选择请求时 |
| `comment` | `POST /story/{story_id}/comments` |
| `comment_like` / `comment_unlike` | `POST/DELETE /comment/{comment_id}/like` |
| `purchase` | `POST /story/{story_id}/purchase` |
| `tip` | `POST /story/{story_id}/tip` |

> 所有行为由后端在处理相关请求时自动记录，前端无需额外调用埋点接口。

**约束**：
- FOREIGN KEY: `user_id` → `users.id`
- FOREIGN KEY: `story_id` → `stories.id`

**索引**：
- `idx_behavior_user_time`: `(user_id, created_at DESC)` - 用户行为时间线
- `idx_behavior_story`: `(story_id, action)` - 故事行为统计
- `idx_behavior_action_time`: `(action, created_at DESC)` - 按行为类型查询
- `idx_behavior_user_story_action`: `(user_id, story_id, action)` - 用户购买/收藏状态查询

**分区策略**：
- 按 `created_at` 月份分区，便于历史数据归档和数仓同步

```sql
CREATE TABLE user_behavior_logs (
    id BIGSERIAL,
    user_id VARCHAR(64) NOT NULL,
    story_id VARCHAR(64) NOT NULL,
    action VARCHAR(32) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 创建月份分区
CREATE TABLE user_behavior_logs_2025_01 
    PARTITION OF user_behavior_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE user_behavior_logs_2025_02 
    PARTITION OF user_behavior_logs
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
-- ... 按需创建更多分区
```

**使用场景**：

1. **行为统计**：
```sql
-- 统计故事的各项行为数量
SELECT action, COUNT(*) 
FROM user_behavior_logs 
WHERE story_id = 'story_001' 
GROUP BY action;
```

2. **个性化推荐**：
```sql
-- 获取用户最近交互的故事（用于协同过滤）
SELECT DISTINCT story_id, MAX(created_at) as last_interaction
FROM user_behavior_logs
WHERE user_id = 'user_001' 
  AND action IN ('enter', 'like', 'favorite')
GROUP BY story_id
ORDER BY last_interaction DESC
LIMIT 50;
```

3. **用户画像**：
```sql
-- 分析用户偏好的故事主题
SELECT s.themes, COUNT(*) as interaction_count
FROM user_behavior_logs ubl
JOIN stories s ON ubl.story_id = s.id
WHERE ubl.user_id = 'user_001'
GROUP BY s.themes
ORDER BY interaction_count DESC;
```

---

### 进度同步策略（性能优化）

为避免每次用户点击"下一步"都写数据库，采用**延迟同步策略**：

#### 写入时机

| 场景 | 写入内容 | 频率 |
|------|---------|------|
| **关键点同步** | `user_story_progress` | 低频 |
| **退出时同步** | `user_story_progress` | 每次退出 |
| **开拓新内容** | `story_versions.current_*` | 仅开拓时 |
| **分叉选择** | INSERT `story_versions` | 仅分叉时 |

#### 关键点定义

以下事件类型触发进度同步：
- `choice`：用户做选择
- `scene_start`：进入新场景
- `chapter_start`：进入新章节
- `story_end`：故事结束

#### 性能对比

| 策略 | 每秒写入量（1000并发用户） |
|------|--------------------------|
| 每次点击都写 | ~200 次/秒 |
| 关键点 + 退出时同步 | ~10-20 次/秒 |

> **注意**：采用延迟同步策略后，用户在两个关键点之间断开可能丢失少量进度（最多回退到上一个场景/章节起点）。对于互动叙事场景，这是可接受的体验。
>
> **前端实现**：详见 [frontend.md](./frontend.md) 中的 `ProgressTracker` 类。

---

### 15. 交易流水表（wallet_transactions）

> 记录用户灵感值的所有变动，包括充值、消费、收入等。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGSERIAL | PK | 流水ID |
| user_id | VARCHAR(64) | FK, NOT NULL | 用户ID |
| type | VARCHAR(32) | NOT NULL | 交易类型 |
| amount | DECIMAL(10,2) | NOT NULL | 金额（正数为收入，负数为支出）|
| balance_after | DECIMAL(10,2) | NOT NULL | 交易后余额 |
| related_id | VARCHAR(64) | NULL | 关联ID（订单ID、故事ID等）|
| description | VARCHAR(256) | NULL | 交易描述 |
| created_at | TIMESTAMP | DEFAULT NOW | 交易时间 |

**交易类型（type）**：

| 类型 | 说明 | amount | related_id |
|------|------|--------|------------|
| `recharge` | 充值 | +N | 充值订单ID |
| `purchase` | 购买故事 | -N | 故事ID |
| `income` | 创作收入（他人购买）| +N | 故事ID |
| `tip_out` | 打赏支出 | -N | 故事ID |
| `tip_in` | 打赏收入 | +N | 故事ID |
| `refund` | 退款 | +N | 原交易ID |
| `reward` | 系统奖励 | +N | 活动ID |
| `daily_bonus` | 每日签到奖励 | +N | NULL |

**约束**：
- FOREIGN KEY: `user_id` → `users.id`

**索引**：
- `idx_transactions_user_time`: `(user_id, created_at DESC)` - 用户账单查询
- `idx_transactions_type`: `(type, created_at DESC)` - 按类型统计
- `idx_transactions_related`: `(related_id)` - 关联查询

**分区策略**：
- 按 `created_at` 月份分区，便于财务对账和归档

```sql
CREATE TABLE wallet_transactions (
    id BIGSERIAL,
    user_id VARCHAR(64) NOT NULL,
    type VARCHAR(32) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    balance_after DECIMAL(10,2) NOT NULL,
    related_id VARCHAR(64),
    description VARCHAR(256),
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

---

## Redis 数据结构

### 1. Redis Stream（故事事件队列）

**Key**: `story:{story_id}:events`

**结构**：
```
XADD story:story_001:events * event <json_event>
```

**字段**：
- `event`: JSON 格式的事件数据

**特性**：
- 消息ID：自动生成（时间戳-序号）
- TTL：7天
- 持久化：AOF

**示例**：
```bash
XADD story:story_001:events * event '{"sequence_id":"story_001_seq_001","event_type":"dialogue",...}'
```

### 2. 故事状态缓存

**Key**: `story:{story_id}:status`

**类型**：String

**值**：
```json
{
                    "status": "generating",
  "progress": 30,
  "message": "AI正在生成..."
}
```

**TTL**：1小时

---

## 场景管理与转场配置

### 场景生成流程

```
AI 生成剧本
     │
     ├─ 解析场景信息（scene_id, 背景描述, 音乐风格等）
     │
     ▼
并发生成场景资源
     ├─ 生成背景图像 → 上传 CDN → 写入 resources 表
     ├─ 生成/选择音乐 → 上传 CDN → 写入 resources 表
     └─ 生成/选择环境音 → 上传 CDN → 写入 resources 表
     │
     ▼
创建场景记录
     ├─ 写入 scenes 表
     ├─ 关联资源 ID（background_resource_id, music_resource_id, ambient_resource_id）
     └─ transition_config 为 NULL（使用全局配置）
     │
     ▼
生成 scene_start 事件
     ├─ 从 scenes 表读取资源 URL
     ├─ 读取转场配置（场景配置 > 全局配置）
     └─ 推送到 Redis Stream
```

### 转场配置优先级

```
1. 场景独立配置（scenes.transition_config）
   ↓ 如果为 NULL
2. 全局默认配置（global_settings['transition.default']）
   ↓ 如果不存在
3. 硬编码默认值（fade_in: 1.5s, fade_out: 1.0s）
```

### 转场配置示例

**全局配置**（`global_settings` 表）：
```json
{
  "key": "transition.default",
  "value": {
    "fade_in": {
      "type": "fade_in",
      "duration": 1.5
    },
    "fade_out": {
      "type": "fade_out",
      "duration": 1.0
    }
  }
}
```

**场景独立配置**（`scenes.transition_config`）：
```json
{
  "fade_in": {
    "type": "fade_in",
    "duration": 2.0
  },
  "fade_out": {
    "type": "fade_out",
    "duration": 1.5
  }
}
```

### 场景编辑功能

**支持编辑的字段**：
- 场景资源（背景、音乐、环境音）
- 转场配置（transition_config）

**编辑流程**：
```
1. GET /scenes/{scene_id} - 获取场景详情
2. PATCH /scenes/{scene_id} - 更新场景配置
   {
     "music_resource_id": "new_music_123",
     "transition_config": {
       "fade_in": { "type": "fade_in", "duration": 2.0 }
     }
   }
3. 下次播放该故事时，从数据库重建事件流时应用新配置
```

**说明**：音量和循环播放由前端全局配置控制，不在场景中存储

---

## 角色配置管理

### 角色颜色分配策略

```
生成对话事件时：
  ├─ 检查 character_id 是否已分配颜色
  │   ├─ 已分配 → 使用已有颜色
  │   └─ 未分配 → 从全局颜色池中分配
  │
  └─ 事件中可选指定 character_color（覆盖默认）
```

### 角色显示配置优先级

```
1. 事件中指定的 position/auto_hide
   ↓ 如果未指定
2. 全局默认配置（global_settings['character.default']）
   ↓ 如果不存在
3. 硬编码默认值（position: "center", auto_hide: true）
```

### 配置使用示例

**dialogue 事件生成**：
```python
# 获取全局配置
character_config = get_global_setting('character.default')
character_colors = get_global_setting('character.colors')

# 分配角色颜色（首次出现）
if character_id not in assigned_colors:
    color = character_colors['colors'][len(assigned_colors) % len(character_colors['colors'])]
    assigned_colors[character_id] = color

# 生成事件（使用全局默认值）
event = {
    "character_id": character_id,
    "character_name": character_name,
    "character_color": assigned_colors[character_id],  # 使用分配的颜色
    "image": {
        "url": image_url,
        "position": character_config.get('position', 'center')  # 使用全局默认
    },
    "auto_hide": character_config.get('auto_hide', True)  # 使用全局默认
}
```

---

## 数据一致性策略

### 双写机制

**目的**：保证数据可靠性和性能

```
AI 生成事件
     │
     ├──────────┬──────────┐
     │          │          │
     ▼          ▼          ▼
 Redis      PostgreSQL   CDN
（实时）     （持久化）   （资源）
  
- Redis：快速推送，7天TTL
- PostgreSQL：长期存储，永久保留
- CDN：静态资源托管
```

### 故障恢复

| 场景 | 恢复策略 |
|------|---------|
| Redis 数据丢失 | 从 PostgreSQL 重建 |
| PostgreSQL 故障 | Redis 数据可用，异步补写 |
| 生成中断 | 标记为 error，允许重试 |
| CDN 资源失败 | 事件不推送，等待重试 |

---

## 性能优化

### 数据库优化

- ✅ **分区表**：按时间分区 `story_events` 表
- ✅ **JSONB 索引**：对 `content` 字段常用字段建立 GIN 索引
- ✅ **连接池**：复用数据库连接
- ✅ **批量写入**：使用 `COPY` 或批量 INSERT

### Redis 优化

- ✅ **Stream 自动清理**：设置 TTL 7天
- ✅ **集群部署**：水平扩展，支持高并发
- ✅ **持久化策略**：AOF 模式，每秒同步

### CDN 优化

- ✅ **资源压缩**：WebP（图像）、OGG（音频）
- ✅ **分区域部署**：多地域 CDN 节点
- ✅ **缓存策略**：强缓存，1年过期

---

**详细的 API 接口请参考 [api.md](./api.md)**

