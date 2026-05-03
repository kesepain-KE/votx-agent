---
name: vision
description: 图像识别与分析。使用 OpenAI 多模态模型分析图片内容。支持本地文件（base64）和远程 URL、多图片、detail 参数。
compatibility: 需要 OPENAI_API_KEY，仅依赖 Python 内置库（urllib + base64）
---

# Vision Skill — 图像识别

使用 OpenAI 多模态模型分析图片内容。支持 gpt-4o、gpt-4o-mini 等视觉模型。

## 功能

- 图片内容描述与识别
- 图片中文字提取（OCR）
- 截图分析与理解
- 图表/表格/流程图解读
- 多图片对比分析
- 远程图片 URL 分析

## 使用方式

通过 `run_command` 调用 `scripts/vision_infer.py` 脚本。

### 基本用法

```cmd
python skills/vision/scripts/vision_infer.py <图片路径或URL> [提示词]
```

- **本地路径**：相对路径（相对项目根）或绝对路径，自动 base64 编码
- **远程 URL**：`https://...` 开头的链接，直接传给 API
- **多图片**：逗号分隔多个路径/URL，如 `img1.jpg,img2.png,https://example.com/photo.jpg`

### 可选参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--detail` | auto / low / high | 图像细节级别，默认 auto |
| `--model` | 模型名 | 覆盖 VISION_MODEL 环境变量 |

### detail 说明

- **auto**（默认）：根据图片大小自动选择 low 或 high
- **low**：低分辨率模式（512x512，约 85 token/张），更快更省
- **high**：高分辨率模式（先看全景再分 512x512 瓦片，约 170 token/瓦片），适合细节分析

### 示例

```cmd
REM 单张本地图片
python skills/vision/scripts/vision_infer.py users/<用户名>/history/file/photo.jpg
python skills/vision/scripts/vision_infer.py users/<用户名>/history/file/photo.jpg "提取图片中的文字"

REM 远程 URL
python skills/vision/scripts/vision_infer.py https://example.com/diagram.png "解读这个图表"

REM 多图片对比
python skills/vision/scripts/vision_infer.py img1.jpg,img2.jpg "比较两张图的差异"

REM 高细节模式
python skills/vision/scripts/vision_infer.py --detail high photo.jpg "详细描述"

REM 指定模型
python skills/vision/scripts/vision_infer.py --model gpt-4o photo.jpg
```

如果 `run_command` 的 shell 找不到 python，显式指定 Anaconda 路径：

```cmd
D:\Anaconda\envs\votx\python.exe skills/vision/scripts/vision_infer.py <路径> [提示词]
```

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 是 | OpenAI API Key（脚本自动从项目根 `.env` 加载） |
| `OPENAI_BASE_URL` | 否 | 自定义 API 地址（兼容 DeepSeek 等第三方视觉 API） |
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

jpg, jpeg, png, webp, gif, bmp, ico, svg（自动检测 MIME 类型）

## 注意事项

- 本地路径优先用相对路径（相对项目根目录），脚本自动解析
- 单张图片建议不超过 20MB（base64 编码后）
- 长时间对话中建议用 URL 而非 base64（避免重复传输）
- 高分辨率模式下短边建议 < 768px，长边 < 2000px
- 非拉丁文字（日文、韩文等）识别效果可能不佳
- 不适合专业医疗影像分析
- 输出限制 3000 token
- 无外部依赖（仅 urllib + base64，Python 内置）
