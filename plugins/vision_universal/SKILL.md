---
name: vision_universal
description: 通用识图工具，支持本地图片和远程URL。原生多模态端点优先，兼容所有OpenAI格式的多模态API（GPT-4o、MiMo、Claude等）。当用户需要分析图片、提取图中文字、识别图片内容时使用。
version: "1.1"
category: multimodal
enabled: true
tags: ["multimodal", "vision", "image-analysis"]
---

# 通用识图 (Vision Universal)

使用多模态模型分析图片内容，支持多图和单图。

## 工作方式

直接调用 `provider.respond()` 将图片注入 chat messages，走多模态模型的 Chat Completions API，无需额外配置。

## 模型优先级

`vision_model`（config.json 专用配置）> 默认聊天模型 `model`

如配置 `"vision_model": "xiaomi/mimo-v2.5"`，识图使用 MiMo；不配则使用聊天模型自动检测。

## 工具

| 工具名 | 描述 |
|--------|------|
| `vision_analyze` | 分析单张或多张图片，支持本地文件和远程 URL |
| `vision_universal` | 兼容旧名，功能同上 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `images` | string[] | 否 | — | 图片路径列表（本地文件路径或 http/https URL） |
| `image` | string | 否 | — | 单张图片路径（兼容旧参数，优先使用 images） |
| `prompt` | string | 否 | "描述这些图片的内容" | 分析提示词 |
| `detail` | string | 否 | "auto" | 图片解析精度（仅 OpenAI 系列支持） |

## 支持格式

jpg、png、gif、webp、bmp（本地自动转 base64）、远程 http/https URL。

## 支持的服务商

- **OpenAI 官方** — 原生多模态端点
- **OpenRouter** — 配专用模型即可（如 `qwen/qwen2.5-vl`、`xiaomi/mimo-v2.5`）
- **Anthropic Claude** — 原生多模态端点
- **其他兼容厂商** — 聊天模型名命中多模态关键词（gpt-4o、gemini、vision 等）即自动开启

## 典型场景

- **描述图片** — 默认 prompt
- **OCR 提取** — `prompt="提取图片中的所有文字"`
- **图表分析** — `prompt="分析这个图表的数据趋势"`
- **内容问答** — `prompt="图片中有几个人？他们在做什么？"`
- **多图对比** — `images=["before.jpg", "after.jpg"]`

## 前置条件

用户的 `config.json` 中模型需支持多模态（如 `mimo-v2.5`、`gpt-4o`、`claude-3-5-sonnet` 等），或配了 `vision_model`。
