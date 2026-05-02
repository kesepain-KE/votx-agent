---
name: vision
description: 图像识别与分析。使用 OpenAI GPT-4o-mini 多模态模型分析图片内容。当用户上传图片、需要识别图像内容、提取图片文字、分析截图时使用。
compatibility: 需要 OPENAI_API_KEY 和 openai 库（pip install openai）
---

# Vision Skill — 图像识别

使用 OpenAI GPT-4o-mini 多模态模型分析图片内容。

## 功能

- 图片内容描述与识别
- 图片中文字提取（OCR）
- 截图分析与理解
- 图表/表格/流程图解读

## 使用方式

通过 `run_command` 调用 `scripts/vision_infer.py` 脚本，传入图片路径和分析提示词：

```bash
# 基础用法：描述图片
python skills/vision/scripts/vision_infer.py <image_path>

# 带提示词：指定分析任务
python skills/vision/scripts/vision_infer.py <image_path> "提取图片中的文字"
python skills/vision/scripts/vision_infer.py <image_path> "解读这个图表"
python skills/vision/scripts/vision_infer.py <image_path> "这是什么类型的文件/界面/场景？"
```

## 前置条件

1. 在 `.env` 中配置 `OPENAI_API_KEY=sk-your-key`
2. 确保 `openai` 库已安装：`pip install openai`
3. 可选配置代理：`HTTP_PROXY` / `HTTPS_PROXY` 环境变量

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 是 | OpenAI API Key |
| `OPENAI_BASE_URL` | 否 | 自定义 API 地址 |
| `VISION_MODEL` | 否 | 模型名（默认 gpt-4o-mini） |
| `HTTP_PROXY` | 否 | HTTP 代理 |
| `HTTPS_PROXY` | 否 | HTTPS 代理 |

## 注意事项

- 支持 jpg/png/webp/gif 等常见图片格式
- 图片通过 base64 编码发送，单张建议不超过 20MB
- 输出自动限制 3000 token
- 如果未安装 openai 库，脚本会返回安装提示
- 路径优先用相对路径（如 `users/kesepain/history/file/photo.jpg`）
