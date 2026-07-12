---
name: image_generation
description: 文生图工具，根据文字描述生成图片并保存到本地。原生 images 端点优先，失败自动降级为 chat completions（适配非标准图像生成模型）。支持多种尺寸和质量。
version: "1.3"
category: multimodal
enabled: true
tags: ["multimodal", "image", "generation"]
---

# 文生图 (Image Generation)

根据文字描述生成图片并保存到本地。支持多种尺寸和质量。

## 插件路径

`plugins/image_generation/`

## 工作方式

1. **原生 images 端点** → `client.images.generate()`（DALL-E 等标准模型）
2. 失败时自动降级为 **chat completions** → prompt 作为用户消息发给专用模型，从响应中提取图片（JSON/base64/URL）

## 模型优先级

`image_generation_model`（config.json 专用配置）> `"dall-e-3"`（默认）

配置后优先使用专用模型；不配则使用 dall-e-3 走原生端点。

## 注册工具

| 工具名 | 描述 |
|--------|------|
| `image_generate` | 根据文字描述生成图片并保存到本地 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `prompt` | string | 是 | — | 图片描述 |
| `size` | string | 否 | `"1024x1024"` | 图片尺寸，格式为 宽x高。具体可选尺寸取决于厂商模型支持 |
| `quality` | string | 否 | `"standard"` | 图片质量。常见值：standard / hd。具体取决于厂商支持 |
| `n` | integer | 否 | 1 | 生成数量。具体可生成的数量取决于厂商模型支持 |
| `output_dir` | string | 否 | `users/<user>/download/` | 输出目录 |
| `filename` | string | 否 | 自动生成 | 文件名前缀（自动追加序号和 `.png`） |

## 结果说明

- 成功：返回 JSON 数组，每项包含 `url`（原始 URL）、`b64_json`（base64 数据）、`revised_prompt`（模型修正后的提示词）
- 保存路径：文件保存到 `output_dir` 或默认 `users/<user>/download/`
- chat 降级：响应无法解析为图片时，返回内容作为 `revised_prompt`
- 失败：返回 `ERROR:` 前缀的错误信息

## 支持的服务商

- **OpenAI 官方** — 原生 images 端点（DALL-E 2/3）
- **OpenRouter / 其他兼容厂商** — 配 `image_generation_model` 后通过 chat 降级调用
- **不支持时** — 可通过 `capabilities_override: ["image_generation"]` 显式开启

## 常见规范

- 输出目录默认保存到 `users/<user>/download/`
- 同时支持 URL 下载和 base64 解码两种返回格式
- `prompt` 描述越具体，生成质量越高

## 常见处理办法

- **尺寸不支持**：切换为常见尺寸 `1024x1024`，部分厂商仅支持固定尺寸
- **quality 参数无效**：非 DALL-E 模型可能不支持 `hd`，使用 `standard`
- **chat 降级无图片**：检查 `image_generation_model` 配置的模型是否实际支持图像输出

## 常见教训

- `n` 的上限因厂商而异，超出限制可能被静默截断或报错
- chat 降级路径的响应格式因厂商而异，可能是 JSON 含 base64 字段，也可能是 URL
- 部分 DALL-E 3 模型会自动改写 prompt（`revised_prompt`），最终图片可能与原始描述有偏差