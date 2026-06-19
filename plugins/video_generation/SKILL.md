---
name: video_generation
description: 视频生成工具，支持文生视频、图生视频、视频生视频任务创建、状态查询和结果下载。
version: "1.0"
category: multimodal
enabled: true
tags: ["multimodal", "video", "generation"]
---

# 视频生成

通过当前 provider 的 `video_generation` 能力创建异步视频任务。需要配置 `video_generation_model`。

## 工具

| 工具名 | 描述 |
|--------|------|
| `video_generate` | 创建文生视频、图生视频或视频生视频任务 |
| `video_status` | 查询视频任务状态 |
| `video_download` | 下载视频任务结果 |
