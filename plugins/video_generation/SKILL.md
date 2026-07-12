---
name: video_generation
description: 视频生成工具，支持文生视频、图生视频、视频生视频任务创建、状态查询和结果下载。
version: "1.1"
category: multimodal
enabled: true
tags: ["multimodal", "video", "generation"]
---

# 视频生成 (Video Generation)

通过当前 provider 的 `video_generation` 能力创建异步视频任务。需要配置 `video_generation_model`。

## 插件路径

`plugins/video_generation/`

## 注册工具

| 工具名 | 描述 |
|--------|------|
| `video_generate` | 创建文生视频、图生视频或视频生视频任务 |
| `video_status` | 查询视频生成任务状态 |
| `video_download` | 下载已完成任务的视频结果到本地 |

## 参数

### video_generate

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `prompt` | string | 否 | `""` | 视频描述或编辑要求 |
| `image` | string | 否 | `""` | 图片路径、URL 或 data URL，用于图生视频 |
| `video` | string | 否 | `""` | 视频路径、URL 或 data URL，用于视频生视频 |
| `duration` | integer | 否 | 0 | 可选视频时长 |
| `size` | string | 否 | `""` | 可选视频尺寸 |
| `negative_prompt` | string | 否 | `""` | 可选负向提示词 |
| `seed` | integer | 否 | 0 | 可选随机种子 |
| `model` | string | 否 | `""` | 可选模型 ID；留空使用 `provider.video_generation_model` |

### video_status

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `job_id` | string | 是 | — | 视频任务 ID |

### video_download

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `job_id` | string | 是 | — | 视频任务 ID |
| `output_dir` | string | 否 | `users/<user>/download/` | 输出目录 |
| `filename` | string | 否 | 自动生成 | 可选输出文件名 |

## 结果说明

### video_generate
- 成功：返回 JSON，含 `job_id` 和任务创建信息
- 失败：返回 `ERROR:` 前缀的错误信息

### video_status
- 成功：返回 JSON，含任务状态（pending/processing/completed/failed）和进度信息
- 失败：返回 `ERROR:` 前缀的错误信息

### video_download
- 成功：返回工具结果 JSON，含文件 artifact（下载路径）
- 失败：返回 `ERROR:` 前缀的错误信息

## 前置条件

- 需要 provider 支持 `video_generation` 能力
- 需配置 `video_generation_model`（config.json 专用配置）
- 视频生成是异步任务，需先 `generate` → 轮询 `status` → 完成后 `download`

## 典型流程

```text
1. video_generate(prompt=" cats playing in garden")  →  返回 job_id
2. video_status(job_id="xxx")                          →  等待 completed
3. video_download(job_id="xxx")                        →  保存到 download/
```

## 常见规范

- 生成模式由传入参数决定：只传 `prompt` = 文生视频，传 `image` = 图生视频，传 `video` = 视频生视频
- `image` 和 `video` 参数支持本地路径、HTTP URL 和 data URL
- 输出目录默认为 `users/<user>/download/`

## 常见处理办法

- **任务长时间 pending**：视频生成耗时较长（通常 30-180 秒），耐心轮询
- **任务失败**：检查 `prompt` 是否合规、模型是否支持当前参数组合
- **下载失败**：先用 `video_status` 确认任务状态为 `completed` 再下载

## 常见教训

- 视频生成是异步任务，不能一步到位，需走 generate → status → download 三步流程
- 下载前必须确认任务状态为 `completed`，否则会下载失败
- 部分 provider 对 `duration` 和 `size` 有严格限制，超范围参数可能被拒绝