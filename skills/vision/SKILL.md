---
name: vision
description: 图像识别与分析。使用 OpenAI GPT-4o-mini 多模态模型分析图片内容。当用户上传图片、需要识别图像内容、提取图片文字、分析截图时使用。
compatibility: 需要 OPENAI_API_KEY，仅依赖 Python 内置库（urllib + base64）
---

# Vision Skill — 图像识别

使用 OpenAI GPT-4o-mini 多模态模型分析图片内容。

## 功能

- 图片内容描述与识别
- 图片中文字提取（OCR）
- 截图分析与理解
- 图表/表格/流程图解读

## 使用方式

通过 `run_command` 调用 `scripts/vision_infer.py` 脚本，传入图片路径和分析提示词。

**路径规则**：优先用相对路径（相对项目根目录 `E:\code\kesepain-Agent`）
- ✅ `users/kesepain/history/file/photo.jpg`（推荐）
- ❌ 避免用 `cd /d E:\...` 这类 Windows 绝对路径命令

**调用方式**（cmd 下）：
```cmd
python skills/vision/scripts/vision_infer.py <图片相对路径> [提示词]
```

**示例**：
```cmd
python skills/vision/scripts/vision_infer.py users/kesepain/history/file/photo.jpg
python skills/vision/scripts/vision_infer.py users/kesepain/history/file/photo.jpg "提取图片中的文字"
python skills/vision/scripts/vision_infer.py users/kesepain/history/file/screenshot.png "解读这个图表"
```

如果 `run_command` 的 shell 找不到 python，显式指定 Anaconda 路径：
```cmd
D:\Anaconda\envs\kesepain\python.exe skills/vision/scripts/vision_infer.py <路径> [提示词]
```

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 是 | OpenAI API Key（脚本自动从项目根 `.env` 加载） |
| `OPENAI_BASE_URL` | 否 | 自定义 API 地址 |
| `VISION_MODEL` | 否 | 模型名（默认 gpt-4o-mini） |

## 代理检测

脚本自动处理代理，流程：
1. 从项目根 `.env` 加载环境变量
2. 检查 `HTTPS_PROXY` / `HTTP_PROXY` 环境变量
3. 如果未设置，读取 Windows 注册表获取系统代理
4. 用百度（`https://www.baidu.com`）测试代理连通性（不消耗 API 额度）
5. 代理不可用时自动回退直连

无需手动配置代理。

## 支持的图片格式

jpg, jpeg, png, webp, gif, bmp, **ico**（自动检测 MIME 类型）

## 注意事项

- 路径优先用相对路径（相对项目根目录），脚本自动解析
- 单张图片建议不超过 20MB
- 输出限制 3000 token
- 无外部依赖（仅 urllib + base64，Python 内置）
