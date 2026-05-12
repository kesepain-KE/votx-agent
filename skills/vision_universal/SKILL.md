---
name: vision_universal
description: 通用识图工具 — 支持本地图片和远程URL，兼容所有OpenAI格式的多模态API（GPT-4o、MiMo、Claude等）。当用户需要分析图片、提取图中文字、识别图片内容时使用。
---

# 通用识图 (Vision Universal)

直接调用多模态模型的 Chat Completions API 分析图片，无需额外配置。

## 使用方式

```python
analyze_image("path/to/image.jpg")
analyze_image("https://example.com/photo.png", "图中有什么文字？")
analyze_image("chart.jpg", "分析图表趋势", model="gpt-4o")
```

## 参数

| 参数 | 类型 | 必需 | 默认值 |
|------|------|------|--------|
| `image_path` | string | 是 | — |
| `prompt` | string | 否 | "描述这张图片的内容" |
| `model` | string | 否 | 用户配置的 model |
| `max_tokens` | integer | 否 | 1500 |

## 支持格式

jpg, png, gif, webp, bmp（本地自动转 base64）、远程 http/https URL。

## 典型场景

- **描述图片** — 默认 prompt
- **OCR 提取** — `prompt="提取图片中的所有文字"`
- **图表分析** — `prompt="分析这个图表的数据趋势"`
- **内容问答** — `prompt="图片中有几个人？他们在做什么？"`

## 前置条件

用户的 `config.json` 中 provider.model 需支持多模态（如 `mimo-v2.5`、`gpt-4o`、`claude-3-5-sonnet` 等）。
