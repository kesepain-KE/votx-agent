---
name: vision_universal
description: 通用识图工具，支持本地图片和远程URL。原生多模态端点优先，兼容所有OpenAI格式的多模态API（GPT-4o、MiMo、Claude等）。当用户需要分析图片、提取图中文字、识别图片内容时使用。
version: "1.2"
category: multimodal
enabled: true
tags: ["multimodal", "vision", "image-analysis"]
---

# 通用识图 (Vision Universal)

使用多模态模型分析图片内容，支持多图和单图。

## 插件路径

`plugins/vision_universal/`

## 工作方式

直接调用 `provider.respond()` 将图片注入 chat messages，走多模态模型的 Chat Completions API，无需额外配置。

## 模型优先级

`vision_model`（config.json 专用配置）> 默认聊天模型 `model`

如配置 `"vision_model": "xiaomi/mimo-v2.5"`，识图使用 MiMo；不配则使用聊天模型自动检测。

## 注册工具

| 工具名 | 描述 |
|--------|------|
| `vision_analyze` | 分析单张或多张图片，支持本地文件和远程 URL |
| `vision_universal` | 兼容旧名，功能同 `vision_analyze`，优先使用 `images` 参数 |

`image` 参数为兼容旧调用保留，实际调用时优先使用 `images`（列表）。

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `images` | string[] | 否 | — | 图片路径列表（本地文件路径或 http/https URL）。优先使用此参数 |
| `image` | string | 否 | — | 单张图片路径（兼容旧参数，优先使用 `images`） |
| `prompt` | string | 否 | `"描述这些图片的内容"` | 分析提示词 |
| `detail` | string | 否 | `"auto"` | 图片解析精度。常见值：auto / low / high。仅 OpenAI 系列支持此参数，其他厂商忽略 |

## 结果说明

- 成功：返回模型对图片内容的分析结果（文本）
- 失败：返回 `ERROR:` 前缀的错误信息
- 能力不支持：提示需要配置 `vision_model` 或确认当前模型支持多模态

## 支持格式

jpg、png、gif、webp、bmp（本地自动转 base64）、远程 http/https URL

## 支持的服务商

- **OpenAI 官方** — 原生多模态端点
- **OpenRouter** — 配专用模型即可（如 `qwen/qwen2.5-vl`、`xiaomi/mimo-v2.5`）
- **Anthropic Claude** — 原生多模态端点
- **其他兼容厂商** — 聊天模型名命中多模态关键词（gpt-4o、gemini、vision 等）即自动开启

## 典型场景

| 场景 | prompt 示例 |
|------|-------------|
| 描述图片 | （默认）"描述这些图片的内容" |
| OCR 提取 | "提取图片中的所有文字" |
| 图表分析 | "分析这个图表的数据趋势" |
| 内容问答 | "图片中有几个人？他们在做什么？" |
| 多图对比 | `images=["before.jpg", "after.jpg"]` + "对比这两张图片的差异" |

## 常见规范

- 本地图片自动转为 base64 编码发送，远程 URL 直接传递
- 多图分析时一次调用传入多张图片，比逐张调用效率更高
- `prompt` 越具体分析结果越精准

## 常见处理办法

- **模型不支持多模态**：配置 `vision_model` 指定支持多模态的模型
- **图片格式不支持**：转换为常见格式（jpg/png/webp）后重试
- **远程 URL 超时**：下载图片到本地后使用本地路径调用

## 常见教训

- `detail` 参数仅 OpenAI 系列生效，其他厂商会忽略此参数
- 部分厂商对图片大小有限制，超大图片可能需要压缩后传入
- `image` 和 `images` 同时传入时，优先使用 `images` 列表