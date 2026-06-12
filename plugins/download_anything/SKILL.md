---
name: download_anything
description: 通用下载编排器。下载公开可访问、开源授权或用户本人授权的数字资源；第一版提供 inspect_download_url、download_direct_file、download_video、list_downloads 四个工具。
---

# Download Anything

`download_anything` 是 VOTX Agent 的通用下载入口。它负责把下载请求路由到合适工具，并把结果默认保存到当前用户目录。

## 第一版工具

| 工具 | 用途 |
|------|------|
| `inspect_download_url` | 检查链接文件名、大小、Content-Type、是否支持断点续传 |
| `download_direct_file` | 下载普通 HTTP/HTTPS 直链文件 |
| `download_video` | 使用 `yt-dlp` 下载视频或音频 |
| `list_downloads` | 查看最近下载记录 |

## 默认输出目录

默认保存到：

```text
users/<name>/download/
```

当用户明确要求“保存到我的文件 / 文件池 / 给我查看的文件”时，`save_to="file"`，保存到：

```text
users/<name>/history/file/
```

设置环境变量后可输出到任意目录：

```text
VOTX_DOWNLOAD_ANYTHING_OUTSIDE_SANDBOX=1
```

## 超时规则

下载工具内部超时遵循统一优先级：

```text
users/<name>/config.json 的 tool.tool_timeout
> config/config_core.json 的 tool.tool_timeout
> 工具内默认值
```

其中直链/探测请求的工具内默认值可由 `DOWNLOAD_TIMEOUT` 指定，未设置时 30 秒；`yt-dlp` 视频下载的工具内默认值可由 `DOWNLOAD_VIDEO_TIMEOUT` 指定，未设置时 600 秒。

## 工具选择

### inspect_download_url

用户要求“看看这个链接是什么文件 / 多大 / 能不能下载 / 文件名是什么”时使用。

### download_direct_file

用户提供普通直链文件时使用，例如：

- PDF / ZIP / EXE / ISO
- GitHub Release asset 直链
- HuggingFace 文件直链
- 普通图片、文档、压缩包

支持 `network_scope`，默认 `public`。本机或局域网下载需显式传 `local` / `private` / `all`。

### download_video

用户要下载视频、音频或平台媒体时使用，底层是 `yt-dlp`：

- B站
- YouTube
- 抖音
- HLS/DASH URL
- 其他 yt-dlp 支持站点

常用参数：

| 参数 | 说明 |
|------|------|
| `format_spec` | yt-dlp 格式选择器 |
| `audio_only=true` | 提取 mp3 音频 |
| `write_subs=true` | 下载字幕 |
| `cookies_file` | 用户本人账号导出的 cookies.txt |

### list_downloads

下载后或用户问“最近下载了什么”时使用。

## 合规边界

- 只下载公开可访问、开源授权、用户本人拥有访问权或用户本人账号授权的内容。
- 不提供 DRM 绕过、破解软件、盗版资源站点规避访问控制等方法。
- cookies 只用于用户自己的账号，且由用户明确提供。
- 下载文件不会自动执行。
- 文件名会做 basename/非法字符清理，防路径穿越。

## 后续扩展

第二阶段可增加：

```text
download_audio
download_gallery
download_site_assets
download_cloud_file
```

参考资料：

- `references/ebooks.md`
- `references/video.md`
- `references/music.md`
- `references/software.md`
- `references/cloud-search.md`
