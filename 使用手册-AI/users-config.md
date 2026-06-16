# 用户配置文件

每个用户都有独立目录：

```text
users/<用户名>/
```

用户目录保存模型配置、聊天历史、文件、任务计划、个人知识和记忆。更新程序不会覆盖 `users/`。

## 目录结构

常见结构：

```text
users/<用户名>/
├── config.json
├── self_soul.md
├── avatar/
├── download/          ← 智能体生成、导出、下载的默认输出
├── knowledge/
├── history/
│   ├── chat/
│   ├── log/
│   ├── archive/
│   └── file/          ← 用户上传文件、外部消息附件、用户原始材料
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
- `knowledge/`：用户个人知识库。
- `history/chat/`：聊天历史。
- `history/log/`：工具日志、附件日志等。
- `download/`：智能体生成、导出、下载的默认输出目录（报告、文档、表格、图片、语音、视频、压缩包等）。
- `avatar/`：用户头像图片（支持 jpg/png/webp/gif）。
- `history/file/`：Web 上传文件、外部消息附件、用户原始材料。智能体新生成的可交付文件默认不放这里。
- `task-plan/`：智能体任务计划文件。
- `tasks/`：定时任务文件。
- `improve/`：auto_improve 的记忆和规则数据。

## 创建用户

可以通过 Web 创建，也可以使用命令：

```bash
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
    "type": "openai",
    "model": "deepseek-v4-flash",
    "api_key": "",
    "base_url": "https://api.deepseek.com",
    "stream": true,
    "think": false
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
openai     OpenAI 兼容接口，例如 OpenAI、DeepSeek、硅基流动、OpenRouter 等
anthropic  Anthropic Claude 接口
```

`python set_user.py add` 创建用户时只显示：

```text
1. deepseek-v4-flash   — 快速便宜
2. deepseek-v4-pro     — 更强推理
3. 其他厂商            — OpenAI 兼容接口
4. 其他厂商            — Anthropic 兼容接口
```

选择其他厂商后，需要填写 `base_url` 和 `api_key`。脚本会尝试读取厂商拥有的模型列表并展示；如果接口不可用或模型不完整，用户可以手动额外添加模型名。

OpenAI 兼容示例：

```json
{
  "provider": {
    "type": "openai",
    "model": "deepseek-v4-flash",
    "api_key": "<你的 API Key>",
    "base_url": "https://api.deepseek.com",
    "stream": true,
    "think": false
  }
}
```

Anthropic 示例：

```json
{
  "provider": {
    "type": "anthropic",
    "model": "claude-3-5-sonnet-latest",
    "api_key": "<你的 API Key>",
    "base_url": "",
    "stream": true
  }
}
```

如果 `api_key` 留空，程序会尝试读取环境变量。优先级见下文。

## 环境变量优先级

通常建议在用户 `config.json` 中配置模型。环境变量适合 Docker、服务器或临时覆盖。

OpenAI 兼容接口：

```text
api_key:  config.json provider.api_key > DEEPSEEK_API_KEY > OPENAI_API_KEY
base_url: config.json provider.base_url > DEEPSEEK_BASE_URL > 默认值
```

Anthropic：

```text
api_key:  config.json provider.api_key > ANTHROPIC_API_KEY
base_url: config.json provider.base_url > ANTHROPIC_BASE_URL
```

`VOTX_PROVIDER` 可以覆盖服务商类型，但日常使用更推荐直接改用户配置。

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
    "type": "openai",
    "model": "gpt-4o",
    "api_key": "<你的 API Key>",
    "base_url": "https://api.openai.com/v1",
    "capabilities_override": [
      "vision",
      "audio_transcription",
      "image_generation",
      "speech_generation"
    ],
    "audio_transcription_model": "whisper-1",
    "image_generation_model": "dall-e-3",
    "speech_generation_model": "tts-1"
  }
}
```

调用优先级：

```text
专用模型配置 > 默认聊天模型
```

例如语音生成会优先使用 `speech_generation_model`，没有配置时才尝试默认模型或返回不支持。

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

- `data`: 是否保存聊天历史。
- `log`: 是否保存工具调用和运行日志。

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
- `enabled`: 工具白名单，留空表示不限制。
- `deny`: 工具黑名单。

如果同一个工具同时出现在白名单和黑名单，建议以黑名单为准，避免误调用。

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
