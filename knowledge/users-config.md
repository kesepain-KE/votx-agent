# 用户配置文件

每个用户都有独立目录：

```text
users/<用户名>/
```

用户目录保存模型配置、聊天历史、文件、任务计划、个人知识和记忆。更新程序不会覆盖 `users/`。

## 目录结构

```text
users/<用户名>/
├── config.json
├── self_soul.md
├── avatar/            ← 用户头像图片
├── download/          ← 智能体生成、导出、下载的默认输出
├── knowledge/
├── history/
│   ├── chat/
│   ├── log/
│   ├── archive/
│   └── file/
├── task-plan/
├── tasks/
└── improve/
    ├── memory/
    │   ├── permanent/
    │   └── temporary/
    ├── self-improving/
    │   ├── permanent/
    │   └── temporary/
    └── ontology/
        ├── permanent/
        └── temporary/
```

说明：

- `config.json`：当前用户的模型、工具、技能、任务配置。
- `self_soul.md`：用户专属系统提示词/人格设定。
- `avatar/`：用户头像目录，放 `avatar.jpg/png/jpeg/webp/gif` 即可，前端自动读取。
- `download/`：智能体生成、导出、下载的默认输出目录（报告、文档、表格、图片、语音、视频、压缩包等）。
- `knowledge/`：用户个人知识库。
- `history/chat/`：聊天历史。
- `history/log/`：工具日志、附件日志等。
- `history/file/`：Web 上传文件、外部消息附件、用户原始材料。智能体新生成的可交付文件默认不放这里。
- `task-plan/`：智能体任务计划文件。
- `tasks/`：定时任务文件。
- `improve/`：auto_improve 的记忆和规则数据。

## 用户头像

用户头像通过文件方式配置，无需修改 `config.json`：

1. 在 `users/<用户名>/avatar/` 目录下放入图片文件。
2. 支持的格式和文件名：

| 格式 | 文件名 |
|------|--------|
| JPEG | `avatar.jpg` 或 `avatar.jpeg` |
| PNG | `avatar.png` |
| WebP | `avatar.webp` |
| GIF | `avatar.gif` |

3. 多个文件同时存在时的优先级：上面的表格从上到下，匹配第一个即返回。
4. 前端 Sidebar 和用户切换面板会自动显示头像。
5. 如果没有头像文件，前端显示用户名首字母作为默认头像。

Web API：

- `/api/avatar` — 当前登录用户的头像
- `/api/avatar/<用户名>` — 指定用户的头像（可跨用户访问）

## 创建用户

可以通过 Web 创建，也可以使用命令：

```text
python set_user.py add
```

创建后会生成：

```text
users/<用户名>/config.json
users/<用户名>/self_soul.md
users/<用户名>/avatar/
users/<用户名>/download/
users/<用户名>/knowledge/
users/<用户名>/history/chat/
users/<用户名>/history/log/
users/<用户名>/history/archive/
users/<用户名>/history/file/
users/<用户名>/task-plan/
users/<用户名>/tasks/
users/<用户名>/improve/
```

## config.json 基本结构

示例：

```json
{
  "provider": {
    "type": "kemo",
    "model": "stepfun-step-3.7-flash",
    "api_key": "",
    "base_url": "http://127.0.0.1:8741/v1",
    "stream": true,
    "timeout": 120
  },
  "history": {
    "data": true,
    "log": true
  },
  "tool": {
    "tool_timeout": 120,
    "enabled": [],
    "deny": []
  },
  "task_plan": {
    "accept_task": false
  },
  "skills": {
    "disabled_builtin": []
  }
}
```

## 模型配置

`provider.type` 表示服务商适配类型：

```text
kemo       Kemo LLM Adapter 本地多模态网关，统一路由所有模型和能力
```

`python set_user.py add` 创建用户时只显示 Kemo 配置入口，包括：

- Base URL（默认 `http://127.0.0.1:8741/v1`）
- API Key（对应 llm-adapter-kemo 的 `config/api_keys.json` 中的密钥）
- 模型选择（stepfun-step-3.7-flash 等，可手动输入其他模型名）

### 完整的 provider 字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | string | `"kemo"` | 服务商类型：仅支持 `"kemo"` |
| `model` | string | 必填 | 模型名称 |
| `api_key` | string | `""` | API 密钥，留空读取环境变量 |
| `base_url` | string | `http://127.0.0.1:8741/v1` | Kemo 网关地址 |
| `stream` | bool | `true` | 是否启用流式输出 |
| `timeout` | int | 120 | API 请求超时秒数 |
| `vision_model` | string | `""` | 专用视觉模型（留空使用默认聊天模型） |
| `audio_transcription_model` | string | `""` | 专用语音转文字模型 |
| `image_generation_model` | string | `""` | 专用文生图模型 |
| `image_edit_model` | string | `""` | 专用图像编辑模型 |
| `speech_generation_model` | string | `""` | 专用文生语音模型 |
| `speech_to_speech_model` | string | `""` | 专用语音生语音模型 |
| `video_generation_model` | string | `""` | 专用视频生成模型 |
| `embedding_model` | string | `""` | 专用文本嵌入模型 |
| `rerank_model` | string | `""` | 专用文档重排模型 |
| `capabilities_override` | array | - | 手动声明多模态能力，见下文 |

Kemo 配置示例：

```json
{
  "provider": {
    "type": "kemo",
    "model": "stepfun-step-3.7-flash",
    "api_key": "sk-kemo-deepseek",
    "base_url": "http://127.0.0.1:8741/v1",
    "stream": true,
    "timeout": 240,
    "vision_model": "stepfun-step-3.7-flash",
    "audio_transcription_model": "stepfun-stepaudio-2.5-asr",
    "speech_generation_model": "stepfun-stepaudio-2.5-tts"
  }
}
```

如果 `api_key` 留空，程序会尝试读取环境变量。优先级见下文。

## 环境变量优先级

通常建议在用户 `config.json` 中配置模型。环境变量适合本地服务或临时覆盖。

Kemo 本地网关：

```text
api_key:  config.json provider.api_key > KEMO_API_KEY
base_url: config.json provider.base_url > KEMO_BASE_URL > http://127.0.0.1:8741/v1
```

`VOTX_PROVIDER` 可以覆盖服务商类型（仅支持 `kemo`），但日常使用更推荐直接改用户配置。

## 多模态能力配置

VOTX Agent 支持把图像识别、语音识别、图像生成、语音生成拆成能力项。

能力名：

```text
vision
audio_transcription
image_generation
speech_generation
```

默认情况下，程序会根据 provider 和模型自动判断能力。高级用户可以手动声明：

```json
{
  "provider": {
    "type": "kemo",
    "model": "stepfun-step-3.7-flash",
    "api_key": "sk-kemo-deepseek",
    "base_url": "http://127.0.0.1:8741/v1",
    "capabilities_override": [
      "vision",
      "audio_transcription",
      "image_generation",
      "speech_generation"
    ],
    "vision_model": "",
    "audio_transcription_model": "stepfun-stepaudio-2.5-asr",
    "image_generation_model": "",
    "speech_generation_model": "stepfun-stepaudio-2.5-tts"
  }
}
```

调用优先级：

```text
专用模型配置 > 默认聊天模型
```

例如语音生成会优先使用 `speech_generation_model`，没有配置时才尝试默认模型或返回不支持。视觉识别同理，`vision_model` 优先于默认模型。

如果当前 provider 不支持某项能力，智能体会明确提示需要修改配置，而不会自动切换到其他 provider。

## 历史记录配置

```json
{
  "history": {
    "data": true,
    "log": true
  }
}
```

含义：

- `data`: 是否保存聊天历史。可以是布尔值，也可以是自定义文件名（如 `"alice_chat_data.json"`）。
- `log`: 是否保存工具调用和运行日志。可以是布尔值，也可以是自定义文件名（如 `"alice_chat_log.json"`）。

设置为 `true` 时使用默认文件路径，设置为 `false` 不保存，设置为字符串则使用自定义文件名。

## 工具配置

```json
{
  "tool": {
    "tool_timeout": 120,
    "enabled": [],
    "deny": []
  }
}
```

说明：

- `tool_timeout`: 单次工具调用超时时间，单位秒。
- `enabled`: 工具白名单。可以是数组 `[]`（不限制）或对象 `{}`（键值对映射）。留空表示不限制。
- `deny`: 工具黑名单，数组格式。

如果同一个工具同时出现在白名单和黑名单，以黑名单为准（deny 优先），避免误调用。

超时优先级：

```text
users/<用户名>/config.json 的 tool.tool_timeout
> config/config_core.json 的 tool.tool_timeout
> 工具运行器默认值 120 秒
```

少数工具可通过注册 meta 跳过全局工具超时，例如 `time.sleep`，它自身保留 30 分钟上限。

## 技能配置

内置技能在：

```text
plugins/
```

用户拓展技能在：

```text
skills/
```

用户可以禁用部分非核心内置技能：

```json
{
  "skills": {
    "disabled_builtin": [
      "tavily_search"
    ]
  }
}
```

核心技能不可禁用。当前核心保护名单：

```text
file
shell
time
network
task_plan
auto_improve
skill_creator
task_time
kb_retriever
```

用户自己创建的技能位于 `skills/<name>/`，更新程序不会覆盖。

## 任务计划配置

```json
{
  "task_plan": {
    "accept_task": false
  }
}
```

`accept_task` 控制复杂任务计划是否需要用户批准后执行。

建议：

- 日常个人助理：`false`，先审阅再执行。
- 自动化环境：谨慎设置为 `true`。

## self_soul.md

`self_soul.md` 是用户专属提示词，可写入长期偏好、身份背景、回复风格和工作边界。

示例：

```md
# 用户偏好

- 默认使用中文。
- 回答前先检查本地项目。
- 涉及文件修改时保持简洁说明。
```

不要把 API Key、密码、Token 等密钥写进 `self_soul.md`。

## 用户知识库

用户个人知识库：

```text
users/<用户名>/knowledge/
```

全局知识库：

```text
knowledge/
```

区别：

- 用户知识库只服务当前用户。
- 全局知识库服务整个系统。
- 更新程序会保留用户知识库。
- 全局 `knowledge/` 更新时会询问合并、跳过或全量覆盖。
- 用户知识库发生新增、修改、删除、重命名、移动后，必须更新 `users/<用户名>/knowledge/data_structure.md`。
- 全局知识库发生新增、修改、删除、重命名、移动后，必须更新 `knowledge/data_structure.md`。

## 修改配置后的生效方式

推荐：

1. 在 Web 配置页保存。
2. 或手动编辑 `users/<用户名>/config.json`。
3. 重启 Web 服务，或使用系统重载功能。

如果修改了模型 Key、base_url、外部消息路由等底层配置，建议直接重启服务。
