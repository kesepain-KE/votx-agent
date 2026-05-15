# users 配置手册

每个用户是一个独立目录 `users/<用户名>/`，包含该用户的模型配置、对话历史、知识库和人设。

创建用户：运行 `python set_user.py` 或首次启动 `start_web.py` 时自动引导。

---

## 一、目录结构

```
users/<用户名>/
├── config.json          ← 核心配置文件（模型、历史、工具权限）
├── self_soul.md         ← 用户人设/角色描述（Markdown）
├── history/             ← 对话与操作历史
│   ├── chat/            ← Agent 对话存档
│   ├── log/             ← 工具调用日志
│   ├── archive/         ← 已归档对话
│   └── file/            ← Agent 产出的文件
├── download/            ← 用户文件下载目录
├── knowledge/           ← 用户独立知识库（Markdown）
├── task-plan/           ← 任务计划存储
├── tasks/               ← 定时任务存储
└── improve/             ← AI 自我改进 — 三层记忆体系
    ├── memory/          ← 用户记忆
    │   ├── permanent/   ← 永久记忆（长期保留）
    │   └── temporary/   ← 临时记忆（待审阅后转永久）
    ├── self-improving/  ← AI 行为改进记录
    │   ├── permanent/
    │   └── temporary/
    └── ontology/        ← 知识图谱
        ├── permanent/
        └── temporary/
```

---

## 二、config.json 配置项

```json
{
  "provider": { ... },
  "history": { ... },
  "tool": { ... },
  "task_plan": { ... }
}
```

### 2.1 provider — 模型供应商

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `type` | string | "openai" | 供应商类型，当前仅支持 `openai`（兼容 OpenAI API 格式） |
| `model` | string | — | 模型名称，如 `deepseek-v4-pro`, `deepseek-v4-flash`, `gpt-4o` |
| `api_key` | string | "" | API Key。留空则使用 `.env` 全局配置 |
| `base_url` | string | "" | API 地址。留空默认 DeepSeek，OpenAI 填 `https://api.openai.com/v1` |
| `think` | bool | false | 是否启用思考模式（DeepSeek 模型支持） |
| `stream` | bool | true | 是否启用流式输出 |
| `timeout` | int | 120 | 请求超时（秒） |
| `api_style` | string | "chat" | API 风格，固定 `chat` |

**常用模型配置示例：**

```json
// DeepSeek
{
  "provider": {
    "type": "openai",
    "model": "deepseek-v4-pro",
    "api_key": "sk-xxx",
    "base_url": "https://api.deepseek.com",
    "think": true,
    "stream": true,
    "timeout": 120,
    "api_style": "chat"
  }
}

// OpenAI
{
  "provider": {
    "type": "openai",
    "model": "gpt-4o",
    "api_key": "sk-xxx",
    "base_url": "https://api.openai.com/v1",
    "think": false,
    "stream": true,
    "timeout": 120,
    "api_style": "chat"
  }
}
```

### 2.2 history — 历史记录

| 字段 | 类型 | 说明 |
|------|------|------|
| `data` | string | 对话数据文件名，存于 `history/chat/` |
| `log` | string | 工具调用日志文件名，存于 `history/log/` |

```json
"history": {
  "data": "kesepain_chat_data.json",
  "log": "kesepain_chat_log.json"
}
```

### 2.3 tool — 工具权限

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `tool_timeout` | int | 240 | 工具调用超时（秒） |
| `enabled` | object | {} | 工具启用/禁用白名单。空对象 = 全部启用。`{"tool_name": true}` 仅启用指定工具 |
| `deny` | string[] | [] | 工具黑名单。`["shell", "http_post"]` 禁用指定工具 |

```json
// 全部启用（默认）
"tool": { "tool_timeout": 240, "enabled": {}, "deny": [] }

// 仅启用特定工具
"tool": { "tool_timeout": 240, "enabled": {"shell": true, "http_get": true}, "deny": [] }

// 禁用危险工具
"tool": { "tool_timeout": 240, "enabled": {}, "deny": ["shell", "http_post"] }
```

### 2.4 task_plan — 任务计划

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `accept_task` | bool | true | 是否允许 Agent 自动接受并执行任务计划 |

---

## 三、self_soul.md — 用户人设

Markdown 格式，定义 Agent 的角色、风格和行为约束。示例：

```markdown
# 用户人设覆盖

## 角色：猫猫小助手

定位：帮助用户解决问题的猫猫助手。

要求：
1. 回复简洁精炼
2. 不使用字符 # 和 *
3. 可使用颜文字和"喵"语气词

可用颜文字：(๑•̀ㅂ•́)و✧  (´·ω·`)  ₍˄·͈༝·͈˄*₎◞ ̑̑
```

---

## 四、knowledge — 知识库

用户独立知识库，存放 Markdown 文件。Agent 可以检索和引用这些文件。

```
knowledge/
└── data_structure.md   ← 示例：用户自定义的知识文档
```

---

## 五、improve — 三层记忆体系

Agent 自我改进机制，三层独立管理：

| 层级 | 目录 | 用途 |
|------|------|------|
| `memory` | `improve/memory/` | 用户记忆（偏好、习惯、上下文） |
| `self-improving` | `improve/self-improving/` | AI 行为改进（对话策略、回复质量） |
| `ontology` | `improve/ontology/` | 知识图谱（概念关系、知识点） |

每层分为两个阶段：
- **`temporary/`** — 临时记忆，AI 自动记录但需人工审阅确认
- **`permanent/`** — 永久记忆，已确认并长期生效

---

## 六、多用户管理

`users/` 下每个子目录对应一个独立用户：

```
users/
├── alice/
│   ├── config.json      ← alice 用 DeepSeek
│   └── ...
├── bob/
│   ├── config.json      ← bob 用 OpenAI
│   └── ...
```

- 每个用户拥有独立的对话历史、知识库和人设
- Web UI 登录时选择用户
- message 平台通过 `bound_users` 将外部账号映射到内部用户
