"""Vision Skill — 使用 OpenAI GPT-4o-mini 识别图片内容"""
import base64
import os
import json
from pathlib import Path
from openai import OpenAI
from run.tool import register_tool
from skills._common import err, truncate, safe_path


def _load_env():
    """加载 .env 文件（系统已支持的格式）"""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key not in os.environ:
                os.environ[key.strip()] = val.strip()


def _encode_image(image_path: str) -> str:
    """读取图片并编码为 base64"""
    p = safe_path(image_path)
    if p is None or not p.exists():
        raise FileNotFoundError(f"图片不存在: {image_path}")
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def vision_infer(image_path: str, prompt: str = "请描述这张图片的内容") -> str:
    """使用 GPT-4o-mini 分析图片内容"""
    try:
        _load_env()
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return err("未配置 OPENAI_API_KEY，请在 .env 中设置")

        base64_image = _encode_image(image_path)

        # 用环境变量方式设置代理
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:10090"
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10090"

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=3000,
            timeout=60,
        )

        result = response.choices[0].message.content
        return truncate(result)
    except Exception as e:
        return err(f"图片识别失败: {e}")


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "vision_infer",
            "description": "使用 GPT-4o-mini 多模态模型分析图片，支持描述内容、提取文字、解读截图等",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "图片文件路径（支持 jpg/png/webp 等格式）",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "分析提示词，如「请描述这张图片」「提取图片中的文字」「解读这个图表」",
                    },
                },
                "required": ["image_path"],
            },
        },
    },
]

HANDLERS = {
    "vision_infer": vision_infer,
}


def register():
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
