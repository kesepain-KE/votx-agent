---
name: download-anything
description: >
  Find and download virtually any digital resource from the internet — ebooks, academic papers,
  movies, TV shows, music, software, images, fonts, courses, and more. Covers both English and
  Chinese internet ecosystems. Includes CLI tool workflows (yt-dlp, aria2, gallery-dl, spotdl),
  resource site directories, cloud drive search engines (百度/阿里/夸克网盘搜索), and search
  techniques (Google dorks). Use when the user wants to: (1) download a video, audio, or media
  from a URL, (2) find and download an ebook or academic paper, (3) find and download software,
  (4) search for any digital resource, (5) batch download images or media from a gallery/site,
  (6) download torrents or magnet links, (7) find free stock assets (images, video, audio, fonts),
  (8) search Chinese cloud drives for resources, or (9) any task involving finding or downloading
  digital content from the internet.
---
# Download Anything

Find it. Download it. Any resource, any format.

## Toolkit

| Tool | Install | Purpose |
|------|---------|---------|
| `yt-dlp` | `pip install yt-dlp` | Video/audio from 1800+ sites |
| `aria2c` | `conda install -c conda-forge aria2` | Multi-thread downloads, torrents |
| `gallery-dl` | `pip install gallery-dl` | Batch image/media |
| `wget` | pre-installed | Recursive downloads |
| `curl` | pre-installed | HTTP requests |
| `ffmpeg` | `pip install ffmpeg` | Media conversion |

## Decision Tree

| Want to download... | Approach |
|---------------------|----------|
| YouTube / social media video | Use `download_video` tool |
| Audio from any video URL | `yt-dlp -x --audio-format mp3 URL` |
| Images from gallery/artist page | `gallery-dl URL` |
| A direct file URL | `aria2c -x16 -s16 -k1M URL` |
| An ebook or paper | Search Anna's Archive / Z-Library → download |
| A movie or TV show | Torrent sites / DDL |
| Software or app | Official site / FossHub / GitHub Releases |
| Chinese cloud drive resources | 百度/阿里/夸克网盘搜索 |
| Stock images/video/audio | Unsplash / Pixabay / Pexels |

## Quick One-Liners

```bash
# Best quality video
yt-dlp -f "bv*+ba/b" URL

# 1080p video + subtitles
yt-dlp -f "bv[height<=1080]+ba/b" --write-subs --sub-langs "en,zh" URL

# Extract audio as MP3
yt-dlp -x --audio-format mp3 URL

# Fast file download (16 connections)
aria2c -x16 -s16 -k1M URL

# Batch images from gallery
gallery-dl URL

# All PDFs from a page
wget -r -l1 -A "*.pdf" URL

# Video metadata as JSON
yt-dlp -j URL
```

## References

| File | Content |
|------|---------|
| [references/ebooks.md](references/ebooks.md) | Ebook sites, academic papers, audiobooks |
| [references/video.md](references/video.md) | Torrent sites, DDL, subtitles |
| [references/music.md](references/music.md) | Free music download tools |
| [references/software.md](references/software.md) | Software archives |
| [references/cloud-search.md](references/cloud-search.md) | Chinese cloud drive search |
