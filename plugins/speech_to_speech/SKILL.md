---
name: speech_to_speech
description: 语音生语音工具，使用当前 provider 的 speech_to_speech 能力转换本地音频并保存结果。
version: "1.0"
category: multimodal
enabled: true
tags: ["multimodal", "audio", "speech-to-speech"]
---

# 语音生语音

把本地音频按提示词或语音参数转换为新的音频文件。

## 工具

| 工具名 | 描述 |
|--------|------|
| `speech_to_speech` | 输入音频，输出转换后的音频 |

## 说明

需要 provider 支持 `speech_to_speech` 能力，并配置 `speech_to_speech_model`。
