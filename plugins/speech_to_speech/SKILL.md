---
name: speech_to_speech
description: 语音生语音工具，使用当前 provider 的 speech_to_speech 能力转换本地音频并保存结果。
version: "1.2"
category: multimodal
enabled: true
tags: ["multimodal", "audio", "speech-to-speech"]
---

# 语音生语音 (Speech to Speech)

把本地音频按提示词或语音参数转换为新的音频文件。

## 插件路径

`plugins/speech_to_speech/`

## 注册工具

| 工具名 | 描述 |
|--------|------|
| `speech_to_speech` | 输入本地音频，按提示词或音色参数转换并保存结果 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `audio` | string | 是 | — | 本地音频文件路径 |
| `prompt` | string | 否 | `""` | 转换要求（如"用温柔女声"） |
| `instruction` | string | 否 | `""` | 语气、风格等全局指令 |
| `voice` | string | 否 | `""` | 目标音色 ID。不同厂商音色完全不同，请根据当前 provider 配置的模型传入 |
| `format` | string | 否 | `"mp3"` | 输出音频格式。常见值：mp3/wav/flac/opus/pcm。具体取决于厂商支持 |
| `output_dir` | string | 否 | `users/<user>/download/` | 输出目录 |

## 结果说明

- 成功：返回保存后的本地文件路径
- 失败：返回 `ERROR:` 前缀的错误信息
- 能力不支持：提示需要配置 `speech_to_speech_model` 或开启 `capabilities_override: ["speech_to_speech"]`

## 前置条件

- 需要 provider 支持 `speech_to_speech` 能力
- 需配置 `speech_to_speech_model`（config.json 专用配置）
- 输入音频文件需存在于本地文件系统

## 典型场景

- 语音变声（男声转女声等）
- 语音风格转换（朗读风格转为对话风格等）
- 语音后处理

## 常见规范

- 输出目录默认为 `users/<user>/download/`
- 不同厂商的音色 ID 体系完全不同，请查阅厂商文档获取音色列表
- `prompt` 和 `instruction` 的作用因厂商而异，部分厂商可能不使用

## 常见处理办法

- **能力不支持**：检查 provider 配置，确认 `speech_to_speech_model` 已设置
- **文件不存在**：检查音频路径是否正确
- **音色无效**：查阅当前 provider 对应模型的音色文档

## 常见教训

- 并非所有 provider 都支持 speech_to_speech，使用前需确认能力声明
- `prompt` 和 `instruction` 参数的效果依赖厂商实现，部分厂商可能忽略
- 输出格式取决于厂商支持，不支持的格式可能静默回退为默认格式