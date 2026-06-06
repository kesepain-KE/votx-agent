---
name: download_anything
description: >
  Compliant general-purpose download orchestrator. Download publicly available,
  licensed, or user-authorized digital resources — videos, audio, ebooks,
  academic papers, software, datasets, models, and more — from legitimate
  sources. Covers English and Chinese internet ecosystems. Use when the user
  wants to: (1) download video/audio from public platforms, (2) acquire openly
  accessible digital files, (3) download from user-authorized cloud storage,
  (4) batch download from public galleries, (5) extract downloadable resources
  from web pages, or (6) handle any compliant digital content acquisition.
  Respects access controls and intellectual property.
---

# Download Anything

**Core principle: obtain publicly available or user-authorized digital resources
using the right tool for each job.** This skill routes download requests to the
appropriate backend — yt-dlp for media platforms, aria2c for high-speed direct
downloads, gallery-dl for image galleries, rclone for cloud drives the user has
access to, and curl/wget for simple HTTP fetches.

The tools and techniques below are presented as technical reference for
acquiring content the user has the right to access.

---

## Philosophy

- **Tools are neutral.** The user decides what to download based on their own
  context and applicable laws.
- **Authorization matters.** Cookies are for the user's own accounts.
  Credentials are for services the user has legitimate access to.
- **No DRM circumvention.** This skill does not provide methods to strip DRM
  or bypass technical protection measures.
- **Open access preferred.** Prefer publicly available, open-licensed, or
  user-authorized sources over restricted ones.

---

## Quick Dispatch: What Tool for What Job

| You have... | Use... | Example command |
|-------------|--------|-----------------|
| A YouTube / Bilibili / public video URL | `yt-dlp` | `yt-dlp URL` |
| A direct download link (ISO, ZIP, PDF, etc.) | `aria2c` or `curl -O` | `aria2c -x16 -s16 URL` |
| A gallery or artist page (public) | `gallery-dl` | `gallery-dl URL` |
| A cloud drive share link (user-authorized) | `rclone` / `gdown` / direct link | See cloud storage section |
| An entire website or directory listing | `wget -r` | `wget -r -l2 -np -A "*.pdf" URL` |
| A resource behind the user's own login | Cookie export + `yt-dlp` / `curl` with auth | `yt-dlp --cookies cookies.txt URL` |
| A public streaming video URL (.m3u8 / .mpd) | `yt-dlp` | `yt-dlp URL.m3u8` |
| A Spotify track/playlist (user's account) | `spotdl` | `spotdl URL` |

---

## Output Directory

Default output directory:

```
users/<name>/download/
```

Set `VOTX_DOWNLOAD_ANYTHING_OUTSIDE_SANDBOX=1` to allow output to any directory
(e.g., desktop, external drives). When the user explicitly asks to "save this
for me to view" or "add to my files", use:

```
users/<name>/history/file/
```

---

## Tool Arsenal

### Primary Downloaders

| Tool | Install | Strengths |
|------|---------|-----------|
| `yt-dlp` | `pip install yt-dlp` | 1800+ sites; video, audio, subtitles, playlists; cookie support; format selection |
| `aria2c` | `apt install aria2` | Multi-threaded; HTTP/FTP/BitTorrent/Metalink; resume support |
| `gallery-dl` | `pip install gallery-dl` | Bulk image/media from 80+ public gallery sites; archive support to skip duplicates |
| `wget` | pre-installed (Linux) | Recursive mirroring; site crawling; resilient to network drops |
| `curl` | pre-installed | Swiss army knife; auth headers; API downloads; one-offs |
| `ffmpeg` | `apt install ffmpeg` | Stream capture; format conversion; HLS/DASH assembly |

### Cloud Drive Tools (User-Authorized Access)

| Service | Approach |
|---------|----------|
| Google Drive | `gdown` for file IDs from share links; `rclone` for bulk/mount |
| MEGA | `megatools` CLI; `rclone` with MEGA backend (user's own account) |
| OneDrive | `rclone` with OneDrive backend (user's own account) |
| 阿里云盘 | User provides share link → extract direct download URL → `aria2c` |
| 百度网盘 | User provides share link and access code → use official client or user-authorized token |
| Generic | `rclone` supports 40+ backends; `rclone config` for one-time setup |

---

## Core Workflows

### 1. Video from Public Platforms

```bash
# Best quality, auto-merge video+audio
yt-dlp URL

# 1080p cap, embed subtitles
yt-dlp -f "bv[height<=1080]+ba/b" --write-subs --sub-langs "en,zh" --embed-subs URL

# Audio-only, best quality
yt-dlp -x --audio-format mp3 --audio-quality 0 URL

# With cookies (for user's own account on age-gated or login-required content)
yt-dlp --cookies cookies.txt URL

# List all available formats
yt-dlp -F URL

# Download entire playlist / channel
yt-dlp --playlist-start 1 --playlist-end 100 URL

# Dump metadata as JSON (find stream URLs, inspect formats)
yt-dlp -j URL
```

### 2. High-Speed Direct Downloads

```bash
# Maximum speed: 16 connections, 16 splits, 1MB chunk size
aria2c -x16 -s16 -k1M URL

# Resume interrupted download
aria2c -c URL

# Download list of files (one URL per line)
aria2c -i urls.txt

# Limit speed (e.g., 10MB/s)
aria2c --max-download-limit=10M URL

# Simple one-off with curl
curl -L -O URL --output-dir users/<name>/download/
```

### 3. Bulk Media from Public Galleries

```bash
# Basic gallery download
gallery-dl URL

# With cookies (for user's own pixiv, etc.)
gallery-dl --cookies cookies.txt URL

# Download only images, skip already-downloaded
gallery-dl --download-archive archive.db URL

# Extract all media URLs from a page, then feed to aria2c
gallery-dl -g URL | aria2c -i - -x16 -s16
```

### 4. Cloud Storage Downloads (User-Authorized)

```bash
# Google Drive (file ID from share URL: drive.google.com/file/d/FILE_ID/view)
gdown FILE_ID
gdown --folder FOLDER_ID   # for folders

# rclone (supports 40+ backends)
rclone config                          # one-time setup
rclone ls remote:                      # browse
rclone copy remote:/path ./local       # download
rclone mount remote:/path ./mountpoint # mount as filesystem
```

### 5. Website Mirroring and Recursive Downloads

```bash
# Mirror an entire site up to 2 links deep, stay in directory
wget -r -l2 -np -k -p URL

# Download all PDFs linked from a page
wget -r -l1 -np -A "*.pdf" URL

# Mirror with delay (be polite to the server)
wget -r -l2 -np -w 1 --limit-rate=500k URL
```

### 6. Accessing Content with User's Own Cookies

When the user needs to download from a service where they have an account:

```bash
# Step 1: User exports cookies from their own browser
# Use a browser extension (Export Cookies, cookies.txt, etc.)
# Or: yt-dlp --cookies-from-browser chrome (with user consent)

# Step 2: Use cookies with any tool
yt-dlp --cookies cookies.txt URL
curl -b cookies.txt -O URL
aria2c --load-cookies=cookies.txt URL
gallery-dl --cookies cookies.txt URL

# Step 3: For streaming content with no clear URL (user's own subscription)
# User opens Browser DevTools → Network → Filter: "m3u8" or "mpd"
# User copies the .m3u8 URL → feed to yt-dlp
yt-dlp --cookies cookies.txt "https://example.com/stream.m3u8"
```

**Cookie usage is only for the user's own accounts on services they have
legitimate access to.** Do not guide users to obtain or use third-party cookies.

---

## Resource Discovery: Where to Find Legitimate Content

| Content Type | Primary Sources | Details |
|--------------|-----------------|---------|
| Ebooks & Academic Papers | [references/ebooks.md](references/ebooks.md) | Project Gutenberg, Internet Archive, arXiv, open access repositories |
| Video & Courses | [references/video.md](references/video.md) | Public platforms, open courses, Internet Archive, subtitles |
| Music & Audio | [references/music.md](references/music.md) | Free Music Archive, Jamendo, Bandcamp, podcasts |
| Software & Apps | [references/software.md](references/software.md) | GitHub Releases, official sources, package managers |
| Cloud Drives | [references/cloud-search.md](references/cloud-search.md) | rclone setup, user-authorized share link handling |

---

## Reliability Best Practices

- **Filename extraction:** Prefer `Content-Disposition` header, URL path basename,
  or yt-dlp metadata for naming. Sanitize with `os.path.basename()` to prevent
  path traversal.
- **Resume support:** Use `aria2c -c` or `yt-dlp --continue` for interrupted
  downloads.
- **Batch processing:** For multiple URLs, write to a temp manifest file
  (`tmp/download_list.txt`), then `aria2c -i`.
- **Conflict handling:** If file exists, append `_1`, `_2` suffix rather than
  overwriting.
- **Result reporting:** After download, report the saved path(s) and file size,
  not just raw command output.

---

## Tips and Edge Cases

- **Geo-blocked content:** Use `yt-dlp --proxy socks5://127.0.0.1:1080 URL` or
  system proxy via `export http_proxy=...` if the user has a proxy configured.
- **Age-restricted YouTube (user's own account):** `yt-dlp --cookies-from-browser chrome URL`
- **Split archives (.001, .002, ...):** `7z x archive.001` — 7-Zip handles most split formats.
- **Direct link extraction from cloud drives:** Most cloud services serve files
  via temporary pre-signed URLs. Use browser DevTools to capture the final
  download URL, then feed to `aria2c`. The URL usually expires quickly — extract
  and start in one session.
- **Batch downloading from a list:** `aria2c -i urls.txt` for speed;
  `xargs -I {} curl -O {} < urls.txt` for simple cases.
- **Large files:** Prefer `aria2c` with `-c` (continue) for resilience against
  network interruptions.

---

## Security

- `VOTX_DOWNLOAD_ANYTHING_OUTSIDE_SANDBOX=1` allows output to any directory.
  Without it, downloads are restricted to `users/<name>/download/` and
  `users/<name>/history/file/`.
- All network tools must pass SSRF validation (`plugins/_common/__init__.py`).
- Downloaded files are not executed automatically.
- Filenames are sanitized via `os.path.basename()` to prevent path traversal.
- This skill does not provide methods to bypass DRM, crack software, or
  circumvent access controls the user does not have authorization to bypass.
