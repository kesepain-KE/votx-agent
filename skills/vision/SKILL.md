---
name: vision
description: 图像识别与分析技能。通过 OpenAI GPT-4o-mini 多模态模型分析图片内容。当用户上传图片、需要识别图像内容、提取图片文字、分析截图时使用。
compatibility: 需要 OPENAI_API_KEY（GPT-4o-mini 模型）
---
# Vision Skill — 图像识别

使用 OpenAI GPT-4o-mini 多模态模型分析图片内容。

## 功能
- 图片内容描述与识别
- 图片中文字提取（OCR）
- 截图分析与理解
- 图表/表格/流程图解读

## 使用方式
调用 `vision_infer` 工具，传入图片路径和分析提示词。
