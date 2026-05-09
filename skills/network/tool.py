"""HTTP 网络请求工具 — GET/POST，自动检测系统代理"""
import json
import os
import platform
import ssl
import urllib.error

from run.tool import register_tool
from skills._common import err, validate_url, MAX_RESPONSE_BYTES

try:
    import urllib.request as _req
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "15"))
_VERIFY_SSL = os.environ.get("HTTP_VERIFY_SSL", "1") != "0"


def _ssl_ctx():
    """SSL 上下文，HTTP_VERIFY_SSL=0 时跳过证书验证"""
    if _VERIFY_SSL:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get_proxy() -> str | None:
    """获取系统代理 URL，优先级: 环境变量 > Windows 注册表"""
    proxy = (
        os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or
        os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""
    )
    if proxy:
        return proxy

    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if proxy_enable:
                proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
                winreg.CloseKey(key)
                if proxy_server:
                    return f"http://{proxy_server}"
            winreg.CloseKey(key)
        except Exception:
            pass
    return None


class _SafeRedirectHandler(_req.HTTPRedirectHandler):
    """在跟随重定向前校验目标 URL 安全性，防止 SSRF 重定向绕过。"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url_err = validate_url(newurl)
        if url_err:
            raise urllib.error.URLError(f"SSRF 阻断: 重定向目标不安全 - {url_err}")
        return _req.HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl)


def _do_request(url: str, method: str = "GET", body: bytes | None = None,
                headers: dict | None = None) -> str:
    """发送 HTTP 请求，自动走系统代理，含 SSRF 防护"""
    try:
        req = _req.Request(url, data=body, method=method)
        req.add_header("User-Agent", "votx-agent/1.0")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)

        proxy_url = _get_proxy()
        handlers = [_SafeRedirectHandler()]
        if proxy_url:
            handlers.append(_req.ProxyHandler({"http": proxy_url, "https": proxy_url}))
        ctx = _ssl_ctx()
        if ctx:
            handlers.append(_req.HTTPSHandler(context=ctx))
        opener = _req.build_opener(*handlers)

        with opener.open(req, timeout=_TIMEOUT) as resp:
            cl_header = resp.headers.get("Content-Length")
            if cl_header:
                try:
                    if int(cl_header) > MAX_RESPONSE_BYTES:
                        return err(
                            f"响应体过大 ({int(cl_header)} bytes / "
                            f"{MAX_RESPONSE_BYTES // 1024 // 1024}MB 限制)，拒绝下载")
                except ValueError:
                    pass

            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    return err(
                        f"响应体超过 {MAX_RESPONSE_BYTES // 1024 // 1024}MB 限制，已截断")
                chunks.append(chunk)
            raw = b"".join(chunks)
            text = raw.decode("utf-8", errors="replace")
            return text
    except urllib.error.URLError as e:
        hint = ""
        if "CERTIFICATE" in str(e).upper() or "SSL" in str(e).upper():
            hint = " (SSL 证书验证失败)"
        elif "timed out" in str(e).lower():
            hint = " (连接超时，可能需要开启代理/VPN)"
        return err(f"HTTP 请求失败: {e}{hint}")
    except Exception as e:
        return err(f"HTTP 请求失败: {e}")


def _parse_headers(headers_str: str) -> dict | None:
    """安全解析 headers JSON，失败返回包含错误信息的 dict 供上层处理。"""
    if not headers_str or not headers_str.strip():
        return None
    try:
        parsed = json.loads(headers_str)
        if not isinstance(parsed, dict):
            return None
        return parsed
    except json.JSONDecodeError as e:
        raise ValueError(f"headers 不是合法 JSON: {e}")


def http_get(url: str, headers: str = "") -> str:
    """发送 HTTP GET 请求"""
    url_err = validate_url(url)
    if url_err:
        return err(url_err)
    try:
        hdrs = _parse_headers(headers)
    except ValueError as e:
        return err(str(e))
    return _do_request(url, "GET", headers=hdrs)


def http_post(url: str, body: str = "", headers: str = "") -> str:
    """发送 HTTP POST 请求"""
    url_err = validate_url(url)
    if url_err:
        return err(url_err)
    try:
        hdrs = _parse_headers(headers)
    except ValueError as e:
        return err(str(e))
    data = body.encode("utf-8") if body else None
    return _do_request(url, "POST", body=data, headers=hdrs)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "发送 HTTP GET 请求，自动处理重定向。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "请求 URL"},
                    "headers": {"type": "string", "description": "JSON 格式的请求头（可选）"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_post",
            "description": "发送 HTTP POST 请求，自动处理重定向。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "请求 URL"},
                    "body": {"type": "string", "description": "请求体内容"},
                    "headers": {"type": "string", "description": "JSON 格式的请求头（可选）"},
                },
                "required": ["url", "body"],
            },
        },
    },
]

HANDLERS = {"http_get": http_get, "http_post": http_post}


def register():
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
