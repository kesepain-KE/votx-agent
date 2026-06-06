# Cloud Drive Access Guide

## User-Authorized Share Link Handling

When a user provides a cloud drive share link, they are authorizing access
to that specific resource. Use the appropriate tool for the service.

## Service-Specific Tools

### Google Drive
```bash
# File share URL: drive.google.com/file/d/FILE_ID/view
gdown FILE_ID
gdown --folder FOLDER_ID   # for folders
```

### OneDrive
```bash
# User's own OneDrive or shared links
rclone config   # set up OneDrive backend
rclone copy onedrive:/path ./local
```

### MEGA
```bash
# User's own MEGA account
megadl URL
rclone config   # set up MEGA backend
```

### 阿里云盘
- User provides share link and access code
- Extract direct download URL from the share page
- Use `aria2c` for high-speed download

### 百度网盘
- User provides share link and access code
- Use official client or user-authorized access token
- For advanced users: `rclone` with Baidu Netdisk backend (BaiduPCS-based)

### 夸克网盘
- User provides share link
- Use rclone or extract direct download URL → `aria2c`

## Generic rclone Setup
```bash
rclone config   # interactive setup, supports 40+ backends
rclone ls remote:path
rclone copy remote:path ./local --progress
```

## Important
- Only download from share links the user explicitly provides.
- Do not search for or suggest third-party cloud drive search engines that
  index unauthorized shared content.
- Respect share link expiration and access code requirements.
