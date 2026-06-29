---
name: image_edit
description: 图像编辑工具，使用当前 provider 的 image_edit 能力对本地图片按提示词编辑并保存结果。
version: "1.0"
category: multimodal
enabled: true
tags: ["multimodal", "image", "edit"]
---

# 图像编辑 (Image Edit)

按提示词编辑本地图片，并把结果保存到当前用户下载目录或指定输出目录。

## 模型优先级

`image_edit_model`（config.json 专用配置）> provider 默认图像编辑模型。

## 工具

| 工具名 | 描述 |
|--------|------|
| `image_edit` | 根据输入图片和提示词编辑图片并保存到本地 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `image` | string | 是 | - | 本地图片路径 |
| `prompt` | string | 是 | - | 编辑要求 |
| `response_format` | string | 否 | `"url"` | `url` 或 `b64_json` |
| `size` | string | 否 | `""` | 可选，目标尺寸，格式为 宽x高，如 `1920x1080` |
| `output_dir` | string | 否 | `users/<user>/download/` | 输出目录 |
| `filename` | string | 否 | 自动生成 | 文件名前缀 |

## 输出

返回 JSON 数组，每项包含保存后的 `path`、原始 `url`（如有）、`revised_prompt`、`finish_reason` 和 `seed`。
