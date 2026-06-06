---
name: video_download
description: 使用 yt-dlp 下载视频。用户提到下载视频、B站、YouTube、抖音等平台的视频时使用。支持指定输出目录、文件名、格式选择。默认受沙箱保护，VOTX_VIDEO_DOWNLOAD_OUTSIDE_SANDBOX=1 可输出到任意目录。
compatibility: 需要 yt-dlp (pip install yt-dlp)
---

# 视频下载

优先调用 `download_video(url, output_dir="", filename="", format_spec="")` 工具，其内部使用 yt-dlp 且已做沙箱和文件名安全处理。

## 工具调用

```
download_video(url="<视频URL>", output_dir="<输出目录>", filename="<文件名>", format_spec="<格式>")
```

- `output_dir`：默认受沙箱限制（仅项目/用户目录）。设置 `VOTX_VIDEO_DOWNLOAD_OUTSIDE_SANDBOX=1` 后允许输出到任意目录。
- `filename`：会自动取 basename 防路径穿越，不需要手动拼路径。
- `format_spec`：可省略，默认最佳 mp4；可选如 `bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best`。

## 必要时 shell 调试

如果工具调用失败，可用 shell 命令调试：

```bash
# 查看可用格式
yt-dlp -F "<视频URL>"

# 基本下载（默认进入当前工作目录）
yt-dlp "<视频URL>"
```

## 关键事项

- **B站视频必须用引号包裹 URL**，因为 URL 含 `?` 等特殊字符。
- **Windows 路径用双引号包裹**: `"C:\Users\xxx\Desktop\视频.%(ext)s"`。
- 下载完成后用 `list_dir` 确认文件存在。
- 如果下载失败，先用 `-F` 查看可用格式，然后指定 `-f` 格式代码。
- **不要反复试同一个命令**——失败后先看错误信息，调整参数再试。
