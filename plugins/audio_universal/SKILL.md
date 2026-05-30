---
name: audio_universal
description: 语音转文字工具，将音频文件转录为文本。原生 transcription 端点优先，失败自动降级为 chat completions（适配非标准语音识别模型）。支持多语言和时间戳。
version: "1.1"
category: multimodal
enabled: true
tags: ["multimodal", "audio", "transcription"]
---

# 语音转文字 (Audio Universal)

将音频文件转录为带可选时间戳的文本。支持多种语言和引导词。

## 工作方式

1. **原生 transcription 端点** → `client.audio.transcriptions.create()`（whisper-1 等标准模型）
2. 失败时自动降级为 **chat completions** → 音频 base64 编码后作为多模态消息发送给专用模型

## 模型优先级

`audio_transcription_model`（config.json 专用配置）> `"whisper-1"`（默认）

配置后优先使用专用模型；不配则使用 whisper-1 走原生端点。

## 工具

| 工具名 | 描述 |
|--------|------|
| `audio_transcribe` | 将音频文件转录为文本，支持语言指定、引导词和时间戳 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | string | 是 | — | 音频文件路径（本地文件） |
| `language` | string | 否 | 自动检测 | 语言代码（如 `zh`、`en`） |
| `prompt` | string | 否 | — | 引导词，帮助适应特定风格或上下文词汇 |
| `timestamp_granularity` | string | 否 | `"segment"` | `none`=纯文本、`segment`=段落级、`word`=单词级 |

## 支持的服务商

- **OpenAI 官方** — 原生 transcription 端点（whisper-1）
- **OpenRouter / 其他兼容厂商** — 配 `audio_transcription_model` 后通过 chat 降级调用
- **不支持时** — 可通过 `capabilities_override: ["audio_transcription"]` 显式开启

## 典型场景

- 会议录音转文字
- 语音消息转录
- 播客/采访转写
- 外语音频翻译前预处理

## 注意事项

- 文件路径受沙箱保护
- 时间戳选择 `word` 时输出可能非常大
- chat 降级路径使用 `input_audio` 多模态格式发送音频
