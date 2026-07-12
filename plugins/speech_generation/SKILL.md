---
name: speech_generation
description: 文生语音工具，将文字转换为语音文件。原生 TTS 端点优先，失败自动降级为 chat completions（适配 MiMo/kokoro 等非标准 TTS 模型）。支持多种语音风格和音频格式。
version: "1.3"
category: multimodal
enabled: true
tags: ["multimodal", "audio", "tts"]
---

# 文生语音 (Speech Generation)

将文字转换为自然语音文件并保存到本地。支持多种语音风格和音频格式。

## 插件路径

`plugins/speech_generation/`

## 工作方式

1. **原生 TTS 端点** → `client.audio.speech.create()`（OpenAI tts-1 / tts-1-hd）
2. 失败时自动降级为 **chat completions** → 文字作为用户消息发给专用模型，从响应中提取 base64 音频（支持 JSON 字段和裸 base64）

## 模型优先级

`speech_generation_model`（config.json 专用配置）> `"tts-1"`（默认）

配置后优先使用专用模型（如 `"hexgrad/kokoro-82m"`）；不配则使用 tts-1 走原生端点。

## 注册工具

| 工具名 | 描述 |
|--------|------|
| `speech_generate` | 将文字转换为语音文件并保存到本地 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 是 | — | 要转换的文字（最大 4096 字符） |
| `voice` | string | 否 | `"alloy"` | 语音风格/音色 ID。不同厂商音色完全不同，请根据当前 provider 配置的 TTS 模型选择对应音色 |
| `format` | string | 否 | `"mp3"` | 输出音频格式。常见值：mp3/opus/aac/flac/wav/pcm。具体取决于厂商支持 |
| `speed` | float | 否 | 1.0 | 语速倍率，通常 0.25-4.0，具体取决于厂商 |
| `output_dir` | string | 否 | `users/<user>/download/` | 输出目录 |

## 常见厂商音色参考

| 厂商 | 音色 ID 示例 |
|------|-------------|
| OpenAI | alloy / echo / fable / onyx / nova / shimmer |
| StepFun | ruanmengnvsheng / tianmeinvsheng / qingnianluoli / 等 |
| 其他厂商 | 请查阅厂商文档获取音色 ID 列表 |

## 结果说明

- 成功：返回保存后的本地文件路径
- chat 降级：从响应中提取 base64 音频并解码保存；无法解析时保存原始响应到 `.txt` 供排查
- 失败：返回 `ERROR:` 前缀的错误信息

## 支持的服务商

- **OpenAI 官方** — 原生 TTS 端点（tts-1 / tts-1-hd）
- **OpenRouter** — 配 `speech_generation_model` 后通过 chat 降级调用（如 `hexgrad/kokoro-82m`）
- **其他兼容厂商** — 配专用模型后自动降级到 chat completions
- **不支持时** — 可通过 `capabilities_override: ["speech_generation"]` 显式开启

## 典型场景

- 聊天回复转语音朗读
- 文字内容配音
- 通知/提醒语音播报

## 常见规范

- 输出目录默认为 `users/<user>/download/`
- 文字超过 4096 字符时可能被截断，长文本应分段处理
- 不同厂商的音色 ID 体系完全不同，不可混用

## 常见处理办法

- **音色无效**：检查当前 provider 配置的 TTS 模型，查阅厂商文档获取正确音色 ID
- **chat 降级无音频**：保存原始响应为 `.txt`，检查模型是否实际支持语音输出
- **格式不支持**：切换为常见格式 `mp3`，部分厂商仅支持少数格式

## 常见教训

- 非标准 TTS 模型（如 kokoro）的 `voice` 参数可能无效，会自动映射到默认音色
- chat 降级路径的响应格式因厂商而异，可能是 JSON 含 base64 字段，也可能是裸 base64
- `speed` 参数的可用范围因厂商而异，超范围可能被静默截断或报错