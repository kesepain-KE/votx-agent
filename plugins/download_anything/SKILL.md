---
name: download_anything
description: 通用下载编排器。下载公开可访问、开源授权或用户本人授权的数字资源；提供 inspect_download_url、download_direct_file、download_video、list_downloads 四个工具。
version: "1.1"
category: download
enabled: true
tags: ["download", "file", "video", "yt-dlp"]
---

# Download Anything (通用下载)

`download_anything` 是 VOTX Agent 的通用下载入口。负责把下载请求路由到合适工具，并把结果默认保存到当前用户目录。

## 插件路径

`plugins/download_anything/`

## 注册工具

| 工具 | 用途 |
|------|------|
| `inspect_download_url` | 检查链接文件名、大小、Content-Type、是否支持断点续传 |
| `download_direct_file` | 下载普通 HTTP/HTTPS 直链文件 |
| `download_video` | 使用 `yt-dlp` 下载视频或音频 |
| `list_downloads` | 查看最近下载记录 |

## 参数详解

### inspect_download_url

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 下载 URL |
| `network_scope` | string | 否 | 网络作用域：public / local / private / all，默认 public |

### download_direct_file

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 直链 URL |
| `output_dir` | string | 否 | 输出目录 |
| `filename` | string | 否 | 保存文件名 |
| `overwrite` | bool | 否 | 是否覆盖已有文件 |
| `headers` | string | 否 | JSON 格式请求头 |
| `network_scope` | string | 否 | 网络作用域，默认 public |
| `save_to` | enum | 否 | `download`（保存到用户 download）或 `file`（保存到 history/file） |

### download_video

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `url` | string | 是 | 视频 URL（B站/YouTube/抖音等 yt-dlp 支持的平台） |
| `output_dir` | string | 否 | 输出目录 |
| `filename` | string | 否 | 输出文件名模板 |
| `format_spec` | string | 否 | yt-dlp 格式选择器 |
| `audio_only` | bool | 否 | 是否仅提取 mp3 音频 |
| `write_subs` | bool | 否 | 是否下载字幕 |
| `cookies_file` | string | 否 | cookies.txt 文件路径（仅限用户自己账号） |
| `save_to` | enum | 否 | `download` 或 `file` |

### list_downloads

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `limit` | int | 否 | 返回记录数，默认 20，上限 100 |

## 结果说明

- `inspect_download_url`：返回文件名、大小、Content-Type、是否支持断点续传等信息
- `download_direct_file` / `download_video`：返回保存路径和下载状态
- `list_downloads`：返回最近下载记录列表
- 失败：返回 `ERROR:` 前缀的错误信息

## 默认输出目录

```text
users/<name>/download/         ← 默认（save_to="download"）
users/<name>/history/file/      ← 用户要求保存到文件池时（save_to="file"）
```

设置 `VOTX_DOWNLOAD_ANYTHING_OUTSIDE_SANDBOX=1` 可输出到任意目录。

## 超时规则

```text
用户 config.json 的 tool.tool_timeout
> config/config_core.json 的 tool.tool_timeout
> 工具内默认值
```

直链/探测默认超时 30 秒（`DOWNLOAD_TIMEOUT`），yt-dlp 视频下载默认 600 秒（`DOWNLOAD_VIDEO_TIMEOUT`）。

## 常见规范

- 用户提供直链文件（PDF/ZIP/EXE/图片等）时用 `download_direct_file`
- 用户要下载平台视频（B站/YouTube/抖音等）时用 `download_video`
- 下载前不确定文件类型时先用 `inspect_download_url` 检查
- `cookies_file` 仅用于用户自己的账号，由用户明确提供

## 常见处理办法

- **下载被拒（403/401）**：检查 URL 是否需要认证，或提供 `headers` / `cookies_file`
- **视频下载失败**：确认 yt-dlp 已安装且为最新版本（`pip install -U yt-dlp`）
- **内网下载被拒**：显式传入 `network_scope="local"` 或 `"private"` 或 `"all"`
- **文件名非法**：工具自动做 basename/非法字符清理，防路径穿越

## 常见教训

- `download_video` 依赖 `yt-dlp`，未安装时会报错
- `audio_only=true` 会将视频转换为 mp3 格式，忽略视频流
- `save_to` 的 `file` 选项保存到 `history/file/`，适合用户上传文件场景
- 下载文件不会自动执行，需用户或智能体另行处理
- 合规边界：只下载公开可访问、开源授权、用户本人拥有访问权的内容