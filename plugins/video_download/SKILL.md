---
name: video_download
description: 使用 yt-dlp 下载视频。用户提到下载视频、B站、YouTube、抖音等平台的视频时使用。支持指定输出目录、文件名、格式选择。
compatibility: 需要 yt-dlp (pip install yt-dlp)
---

# 视频下载

使用 yt-dlp 下载各平台视频。

## 命令模板

### 基本下载（最常用）
```bash
yt-dlp -o "<输出目录>/%(title)s.%(ext)s" "<视频URL>"
```

### 指定输出路径和文件名
```bash
yt-dlp -o "<完整路径>.%(ext)s" "<视频URL>"
```

### 下载最佳 MP4 格式
```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" -o "<路径>.%(ext)s" "<URL>"
```

### 查看可用格式
```bash
yt-dlp -F "<视频URL>"
```

## 关键事项

- **B站视频必须用引号包裹 URL**，因为 URL 含 `?` 等特殊字符
- **Windows 路径用双引号包裹**: `"C:\Users\xxx\Desktop\视频.%(ext)s"`
- **%(title)s** 会被替换为视频标题，**%(ext)s** 为扩展名
- 下载完成后用 `list_dir` 确认文件存在
- 如果下载失败，先用 `-F` 查看可用格式，然后指定 `-f` 格式代码
- **不要反复试同一个命令**——失败后先看错误信息，调整参数再试
