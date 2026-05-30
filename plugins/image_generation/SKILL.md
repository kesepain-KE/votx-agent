---
name: image_generation
description: 文生图工具，根据文字描述生成图片并保存到本地。原生 images 端点优先，失败自动降级为 chat completions（适配非标准图像生成模型）。支持多种尺寸和质量。
version: "1.1"
category: multimodal
enabled: true
tags: ["multimodal", "image", "generation"]
---

# 文生图 (Image Generation)

根据文字描述生成图片并保存到本地。支持多种尺寸和质量。

## 工作方式

1. **原生 images 端点** → `client.images.generate()`（DALL-E 等标准模型）
2. 失败时自动降级为 **chat completions** → prompt 作为用户消息发给专用模型，从响应中提取图片（JSON/base64/URL）

## 模型优先级

`image_generation_model`（config.json 专用配置）> `"dall-e-3"`（默认）

配置后优先使用专用模型；不配则使用 dall-e-3 走原生端点。

## 工具

| 工具名 | 描述 |
|--------|------|
| `image_generate` | 根据文字描述生成图片并保存到本地 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `prompt` | string | 是 | — | 图片描述 |
| `size` | string | 否 | `"1024x1024"` | 图片尺寸 |
| `quality` | string | 否 | `"standard"` | `standard` 标准 / `hd` 高清（仅 DALL-E 3） |
| `n` | integer | 否 | 1 | 生成数量 1-4 |
| `output_dir` | string | 否 | `users/<user>/generated/images/` | 输出目录 |
| `filename` | string | 否 | 自动生成 | 文件名前缀（自动追加序号和 .png） |

## 输出

返回 JSON 数组，每项包含：
- `url`: 原始 URL（如有）
- `b64_json`: base64 编码的图片数据（如有）
- `revised_prompt`: 模型修正后的提示词

## 支持的服务商

- **OpenAI 官方** — 原生 images 端点（DALL-E 2/3）
- **OpenRouter / 其他兼容厂商** — 配 `image_generation_model` 后通过 chat 降级调用
- **不支持时** — 可通过 `capabilities_override: ["image_generation"]` 显式开启

## 注意事项

- 输出目录受沙箱保护
- 同时支持 URL 下载和 base64 解码两种返回格式
- chat 降级响应无法解析为图片时，返回内容作为 `revised_prompt`
