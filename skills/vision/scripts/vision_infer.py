"""Vision Infer — 使用 OpenAI GPT-4o-mini 识别图片内容

用法:
    python vision_infer.py <image_path> [prompt]
    python vision_infer.py photo.jpg "描述这张图片"
    python vision_infer.py screenshot.png

环境变量:
    OPENAI_API_KEY — OpenAI API Key（必需）
    OPENAI_BASE_URL — 自定义 API 地址（可选）
    VISION_MODEL    — 模型名（默认 gpt-4o-mini）
    HTTP_PROXY      — HTTP 代理（可选，如 http://127.0.0.1:10090）
    HTTPS_PROXY     — HTTPS 代理（可选）
"""
import base64
import os
import sys
from pathlib import Path


def _load_env():
    """加载项目根 .env 文件"""
    env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k not in os.environ:
                os.environ[k] = v.strip().strip('"').strip("'")


def main():
    if len(sys.argv) < 2:
        print("用法: python vision_infer.py <image_path> [prompt]", file=sys.stderr)
        print("示例: python vision_infer.py photo.jpg '描述这张图片'", file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "请描述这张图片的内容"

    if not os.path.exists(image_path):
        print(f"ERROR: 图片不存在: {image_path}", file=sys.stderr)
        sys.exit(1)

    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("ERROR: 未配置 OPENAI_API_KEY，请在 .env 中设置", file=sys.stderr)
        sys.exit(1)

    base_url = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("VISION_MODEL", "gpt-4o-mini")

    # 读取并编码图片
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url or None)
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                ],
            }],
            max_tokens=3000,
            timeout=120,
        )
        result = response.choices[0].message.content or ""
        print(result)
    except ImportError:
        print("ERROR: 缺少 openai 库，请运行: pip install openai", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: 图片识别失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
