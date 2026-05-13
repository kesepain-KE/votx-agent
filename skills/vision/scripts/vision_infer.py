"""Vision inference script using OpenAI-compatible multimodal API

用法: python vision_infer.py <图片路径或URL> [提示词]

- 支持本地文件（自动 base64 编码）和远程 URL
- 多图片用逗号分隔：path1.jpg,path2.png,https://example.com/photo.jpg
- 自动从项目 .env 读取 OPENAI_API_KEY / OPENAI_BASE_URL / VISION_MODEL
- 自动检测代理（环境变量 + Windows 注册表）
- 支持 --detail low|high|auto（默认 auto）
"""
import os, sys, base64, json, platform, ssl


# ======== 路径/URL 解析 ========

def get_project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "..", "..", ".."))


def resolve_input(raw: str) -> dict:
    """解析单个输入：URL 返回 {url: ...}，本地路径返回 {path: ...}"""
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return {"type": "url", "url": raw}

    # 本地路径：先尝试原路径，再尝试相对项目根
    if os.path.exists(raw):
        return {"type": "path", "path": os.path.abspath(raw)}

    candidate = os.path.join(get_project_root(), raw)
    if os.path.exists(candidate):
        return {"type": "path", "path": candidate}

    return {"type": "path", "path": os.path.abspath(raw), "missing": True}


# ======== 环境变量加载 ========

def load_env():
    """从项目根 .env 加载环境变量，不覆盖已有值"""
    env_path = os.path.join(get_project_root(), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key not in os.environ:
                os.environ[key] = val.strip()


# ======== 代理检测模块 ========

def get_system_proxy():
    """获取系统代理：环境变量优先，其次 Windows 注册表"""
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


def _make_ssl_ctx():
    """宽松 SSL 上下文（关闭证书验证）"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def test_proxy(proxy_url, target_url="https://www.baidu.com", timeout=5):
    """用百度测试代理连通性（不消耗 API 额度）"""
    if not proxy_url:
        return False
    try:
        req = urllib.request.Request(target_url)
        handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        ctx = _make_ssl_ctx()
        opener = urllib.request.build_opener(handler, urllib.request.HTTPSHandler(context=ctx))
        opener.open(req, timeout=timeout)
        return True
    except Exception:
        return False


def test_direct(target_url="https://www.baidu.com", timeout=5):
    """测试直连是否可用"""
    try:
        ctx = _make_ssl_ctx()
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        opener.open(target_url, timeout=timeout)
        return True
    except Exception:
        return False


def resolve_proxy():
    """检测并返回可用代理，失败则退出"""
    http_proxy, https_proxy = get_system_proxy()
    proxy_url = https_proxy or http_proxy

    if proxy_url:
        if test_proxy(proxy_url):
            return proxy_url
        else:
            print(f"提示: 系统代理 {proxy_url} 不可用，尝试直连...")
            if test_direct():
                return ""
            else:
                print("ERROR: 代理不可用且直连失败，请检查网络")
                sys.exit(1)
    else:
        if test_direct():
            return ""
        else:
            print("ERROR: 网络不可用（直连失败，且未配置可用代理）")
            sys.exit(1)


def _install_opener(proxy_url=""):
    """全局安装 opener（SSL 豁免 + 代理）"""
    ctx = _make_ssl_ctx()
    handlers = [urllib.request.HTTPSHandler(context=ctx)]
    if proxy_url:
        handlers.insert(0, urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
    urllib.request.install_opener(urllib.request.build_opener(*handlers))


# ======== 图像推理模块 ========

MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
    ".ico": "image/x-icon", ".svg": "image/svg+xml",
}


def _build_image_block(item: dict, detail: str) -> dict:
    """构建单个 image_url 内容块"""
    if item["type"] == "url":
        image_url = {"url": item["url"], "detail": detail}
    else:
        ext = os.path.splitext(item["path"])[1].lower()
        mime = MIME_MAP.get(ext, "image/png")
        b64 = base64.b64encode(open(item["path"], "rb").read()).decode("utf-8")
        size_kb = len(b64) * 3 // 4 // 1024
        if size_kb > 20000:
            print(f"WARNING: 图片较大 ({size_kb} KB)，建议压缩后重试")
        image_url = {"url": f"data:{mime};base64,{b64}", "detail": detail}

    return {"type": "image_url", "image_url": image_url}


def infer(inputs: list[str], prompt: str = "请详细描述这张图片的内容",
          detail: str = "auto", model: str = None):
    """执行视觉推理

    Args:
        inputs: 图片路径或 URL 列表（支持混合）
        prompt: 提示词
        detail: 图像细节级别 (auto/low/high)
        model: 模型名，默认从 VISION_MODEL 环境变量读取
    """
    load_env()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
    model = model or os.environ.get("VISION_MODEL", "gpt-4o-mini")

    if not api_key:
        print("ERROR: OPENAI_API_KEY 未设置（请在 .env 中配置）")
        return

    # 解析输入
    items = [resolve_input(s) for s in inputs]
    for item in items:
        if item.get("missing"):
            print(f"ERROR: 图片文件不存在: {item['path']}")
            return

    # 构建 content 数组
    content = [{"type": "text", "text": prompt}]
    for item in items:
        content.append(_build_image_block(item, detail))

    url = f"{base_url or 'https://api.openai.com'}/v1/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 3000,
    }).encode("utf-8")

    proxy_url = resolve_proxy()
    _install_opener(proxy_url)

    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })

    try:
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read())
        content_text = result["choices"][0]["message"]["content"]
        print(content_text)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"ERROR: HTTP {e.code} - {body}")
    except Exception as e:
        print(f"ERROR: {e}")


# ======== CLI 入口 ========

if __name__ == "__main__":
    import urllib.request, urllib.error

    args = sys.argv[1:]
    if not args:
        print("用法: python vision_infer.py <图片路径或URL> [提示词]")
        print()
        print("选项:")
        print("  --detail auto|low|high   图像细节级别（默认 auto）")
        print("  --model MODEL            模型名（默认 gpt-4o-mini）")
        print()
        print("单张图片:")
        print("  python vision_infer.py photo.jpg")
        print("  python vision_infer.py photo.jpg \"提取图片中的文字\"")
        print("  python vision_infer.py https://example.com/photo.jpg")
        print()
        print("多张图片（逗号分隔）:")
        print("  python vision_infer.py img1.jpg,img2.png \"比较两张图\"")
        print("  python vision_infer.py photo.jpg,https://example.com/diagram.png")
        sys.exit(1)

    # 解析可选参数
    inputs_raw = []
    prompt_parts = []
    detail = "auto"
    model = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--detail" and i + 1 < len(args):
            detail = args[i + 1]
            if detail not in ("auto", "low", "high"):
                print(f"ERROR: --detail 必须是 auto/low/high，收到: {detail}")
                sys.exit(1)
            i += 2
        elif a == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif not inputs_raw:
            # 第一个非选项参数 = 图片（可能含逗号分隔的多张）
            inputs_raw = a.split(",")
            i += 1
        else:
            # 后续非选项参数 = 提示词
            prompt_parts.append(a)
            i += 1

    if not inputs_raw:
        print("ERROR: 请提供图片路径或 URL")
        sys.exit(1)

    prompt = " ".join(prompt_parts) if prompt_parts else "请详细描述这张图片的内容"
    infer(inputs_raw, prompt, detail=detail, model=model)
