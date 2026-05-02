"""Vision inference script using OpenAI GPT-4o-mini multimodal API

用法: python skills/vision/scripts/vision_infer.py <图片路径> [提示词]

- 路径支持相对路径（相对项目根目录）
- 自动从项目 .env 读取 OPENAI_API_KEY
- 自动检测 Windows 系统代理 / 环境变量代理
- 代理测试用百度（不消耗 API 额度）
"""
import os, sys, base64, json, platform

# ======== 路径解析 ========

def resolve_image_path(raw_path: str) -> str:
    """解析图片路径：如果不存在，尝试相对项目根目录"""
    if os.path.exists(raw_path):
        return os.path.abspath(raw_path)
    # 尝试相对项目根目录（脚本在 skills/vision/scripts/ 下，项目根在上三层）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
    candidate = os.path.join(project_root, raw_path)
    if os.path.exists(candidate):
        return candidate
    return os.path.abspath(raw_path)  # 原样返回，让后续报错更明确


# ======== 环境变量加载 ========

def load_env():
    """从项目根目录的 .env 文件加载环境变量"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
    env_path = os.path.join(project_root, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                # 不覆盖已有的环境变量
                if key not in os.environ:
                    os.environ[key] = val


# ======== 代理检测模块 ========

def get_system_proxy():
    """获取系统代理：优先环境变量，其次 Windows 注册表"""
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""

    if not https_proxy and platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            winreg.CloseKey(key)
            if proxy_enable and proxy_server:
                https_proxy = f"http://{proxy_server}"
                http_proxy = https_proxy
        except Exception:
            pass

    return http_proxy, https_proxy


def test_proxy(proxy_url, target_url="https://www.baidu.com", timeout=5):
    """测试代理是否可用（用百度，不消耗 API 额度）"""
    if not proxy_url:
        return False
    try:
        req = urllib.request.Request(target_url)
        handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener = urllib.request.build_opener(handler)
        opener.open(req, timeout=timeout)
        return True
    except Exception:
        return False


def test_direct(target_url="https://www.baidu.com", timeout=5):
    """测试直连是否可用"""
    try:
        urllib.request.urlopen(target_url, timeout=timeout)
        return True
    except Exception:
        return False


def resolve_proxy():
    """检测并返回可用代理，返回 (可用代理URL, 是否使用代理)"""
    http_proxy, https_proxy = get_system_proxy()
    proxy_url = https_proxy or http_proxy

    if proxy_url:
        if test_proxy(proxy_url):
            return proxy_url, True
        else:
            print(f"提示: 系统代理 {proxy_url} 不可用，尝试直连...")
            if test_direct():
                return "", False
            else:
                print("ERROR: 代理不可用且直连失败，请检查网络")
                print("提示：请检查代理软件是否开启，或设置 HTTPS_PROXY 环境变量")
                sys.exit(1)
    else:
        if test_direct():
            return "", False
        else:
            print("ERROR: 网络不可用（直连失败，且未配置可用代理）")
            print("提示：请检查代理软件是否开启，或设置 HTTPS_PROXY 环境变量")
            sys.exit(1)


# ======== 图像推理模块 ========

def infer(image_path_raw, prompt="请详细描述这张图片的内容"):
    load_env()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
    model = os.environ.get("VISION_MODEL", "gpt-4o-mini")

    if not api_key:
        print("ERROR: OPENAI_API_KEY 未设置（请在 .env 中配置）")
        return

    # 解析图片路径
    image_path = resolve_image_path(image_path_raw)
    if not os.path.exists(image_path):
        print(f"ERROR: 图片文件不存在: {image_path}")
        return

    url = f"{base_url or 'https://api.openai.com'}/v1/chat/completions"

    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
                ".ico": "image/x-icon"}
    mime = mime_map.get(ext, "image/png")

    base64_image = base64.b64encode(open(image_path, "rb").read()).decode("utf-8")
    size_kb = len(base64_image) * 3 // 4 // 1024
    if size_kb > 20000:
        print(f"ERROR: 图片过大 ({size_kb} KB)，建议压缩后重试")
        return

    data = json.dumps({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{base64_image}"}}
                ]
            }
        ],
        "max_tokens": 3000
    }).encode("utf-8")

    proxy_url, use_proxy = resolve_proxy()

    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    })

    if use_proxy:
        handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener = urllib.request.build_opener(handler)
    else:
        opener = urllib.request.build_opener()

    try:
        resp = opener.open(req, timeout=120)
        result = json.loads(resp.read())
        content = result["choices"][0]["message"]["content"]
        print(content)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"ERROR: HTTP {e.code} - {body}")
    except Exception as e:
        print(f"ERROR: {e}")


# ======== CLI 入口 ========

if __name__ == "__main__":
    import urllib.request, urllib.error

    if len(sys.argv) < 2:
        print("用法: python vision_infer.py <图片路径> [提示词]")
        print("示例: python skills/vision/scripts/vision_infer.py users/kesepain/history/file/photo.jpg")
        sys.exit(1)

    image_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "请详细描述这张图片的内容"
    infer(image_path, prompt)
