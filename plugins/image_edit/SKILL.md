---
name: image_edit
description: 图像编辑工具，使用当前 provider 的 image_edit 能力对本地图片按提示词编辑并保存结果。
version: "1.1"
category: multimodal
enabled: true
tags: ["multimodal", "image", "edit"]
---

# 图像编辑 (Image Edit)

按提示词编辑本地图片，并把结果保存到当前用户下载目录或指定输出目录。

## 插件路径

`plugins/image_edit/`

## 模型优先级

`image_edit_model`（config.json 专用配置）> provider 默认图像编辑模型

## 注册工具

| 工具名 | 描述 |
|--------|------|
| `image_edit` | 根据输入图片和提示词编辑图片并保存到本地 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `image` | string | 是 | — | 本地图片路径 |
| `prompt` | string | 是 | — | 编辑要求（如"将背景换成蓝天"、"移除图中人物"） |
| `response_format` | string (enum) | 否 | `"url"` | 返回格式：`url` 或 `b64_json` |
| `size` | string | 否 | `""` | 可选，目标尺寸，格式为 宽x高，如 `1920x1080`。留空使用 API 默认 |
| `output_dir` | string | 否 | `users/<user>/download/` | 输出目录 |
| `filename` | string | 否 | 自动生成 | 文件名前缀（自动追加序号和 `.png`） |

## 结果说明

- 成功：返回 JSON 数组，每项包含保存后的 `path`、原始 `url`（如有）、`revised_prompt`、`finish_reason` 和 `seed`
- 失败：返回 `ERROR:` 前缀的错误信息
- 能力不支持：提示需要配置 `image_edit_model` 或开启 `capabilities_override: ["image_edit"]`

## 前置条件

- 需要 provider 支持 `image_edit` 能力
- 需配置 `image_edit_model`（config.json 专用配置）
- 输入图片需存在于本地文件系统

## 典型场景

- 图片局部修改（换背景、移除物体、添加元素）
- 图片风格转换（照片转油画、赛博朋克风格等）
- 图片修复（去水印、补全缺失区域）

## 常见规范

- 输出目录默认为 `users/<user>/download/`
- 编辑要求描述越具体效果越好
- `size` 参数留空时使用 API 默认尺寸

## 常见处理办法

- **能力不支持**：检查 `image_edit_model` 是否已配置
- **编辑效果不理想**：优化 `prompt`，使用更精确的描述
- **文件不存在**：检查图片路径是否正确

## 常见教训

- 并非所有 provider 都支持 image_edit，使用前需确认能力声明
- `response_format` 设为 `b64_json` 时响应体较大，网络条件差时建议用 `url`
- 编辑结果可能与预期有差异，部分模型对指令的理解有限