---
name: speech_generation
description: 文生语音工具，将文字转换为语音文件。原生 TTS 端点优先，失败自动降级为 chat completions（适配 MiMo/kokoro 等非标准 TTS 模型）。支持多种语音风格和音频格式。
version: "1.1"
category: multimodal
enabled: true
tags: ["multimodal", "audio", "tts"]
---

# 文生语音 (Speech Generation)

将文字转换为自然语音文件并保存到本地。支持多种语音风格和音频格式。

## 工作方式

1. **原生 TTS 端点** → `client.audio.speech.create()`（OpenAI tts-1 / tts-1-hd）
2. 失败时自动降级为 **chat completions** → 文字作为用户消息发给专用模型，从响应中提取 base64 音频（支持 JSON 字段和裸 base64）

## 模型优先级

`speech_generation_model`（config.json 专用配置）> `"tts-1"`（默认）

配置后优先使用专用模型（如 `"hexgrad/kokoro-82m"`）；不配则使用 tts-1 走原生端点。

## 工具

| 工具名 | 描述 |
|--------|------|
| `speech_generate` | 将文字转换为语音文件并保存到本地 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 是 | — | 要转换的文字（最大 4096 字符） |
| `voice` | string | 否 | `"alloy"` | 语音风格（原生端点: alloy/echo/fable/onyx/nova/shimmer） |
| `voice` | string | 否 | `"alloy"` | 语音风格。支持 OpenAI 标准音色 (alloy/echo/fable/onyx/nova/shimmer) 及各厂商自定义音色 ID（如 StepFun 的 ruanmengnvsheng / tianmeinvsheng 等） || `format` | string | 否 | `"mp3"` | 输出格式: mp3/opus/aac/flac/wav/pcm |
| `speed` | float | 否 | 1.0 | 语速 0.25-4.0 |
| `output_dir` | string | 否 | `users/<user>/generated/audio/` | 输出目录 |

## 输出

返回保存后的本地文件路径。

## 支持的服务商

- **OpenAI 官方** — 原生 TTS 端点（tts-1 / tts-1-hd）
- **OpenRouter** — 配 `speech_generation_model` 后通过 chat 降级调用（如 `hexgrad/kokoro-82m`）
- **其他兼容厂商** — 配专用模型后自动降级到 chat completions
- **不支持时** — 可通过 `capabilities_override: ["speech_generation"]` 显式开启

## 典型场景

- 聊天回复转语音朗读
- 文字内容配音
- 通知/提醒语音播报

## 注意事项

- 输出目录受沙箱保护
- 文字超过 4096 字符时可能被截断
- chat 降级无法解析音频时，保存原始响应到 .txt 供排查
- 非标准 TTS 模型的 voice 参数可能无效（如 kokoro），会自动映射
