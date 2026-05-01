"""HTTP 网络请求工具 — GET/POST，内置 SSRF 防护"""
import ipaddress
import json
import os
import socket
from urllib.parse import urlparse
from run.tool import register_tool
from skills._common import err, truncate

try:
    import urllib.request as _req
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

# 内网网段
_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
]
_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "15"))


def _is_private(host: str) -> bool:
    """检测主机是否为内网/回环地址"""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # 域名 → DNS 解析后再校验
        try:
            ip = ipaddress.ip_address(socket.getaddrinfo(host, None)[0][4][0])
        except Exception:
            return True  # 解析失败，保守拒绝
    for net in _PRIVATE_NETS:
        if ip in net:
            return True
    return False


def _safe_request(url: str, method: str = "GET", body: str = "", headers: dict = None) -> str:
    """发送 HTTP 请求，带 SSRF 防护"""
    if not HAS_URLLIB:
        return err("urllib 不可用")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return err(f"协议不受支持: {parsed.scheme}（仅允许 http/https）")
    if not parsed.hostname:
        return err("URL 缺少主机名")

    if _is_private(parsed.hostname):
        return err(f"SSRF 拦截: 禁止访问内网地址 ({parsed.hostname})")

    try:
        data = body.encode("utf-8") if body else None
        req = _req.Request(url, data=data, method=method)
        req.add_header("User-Agent", "kesepain-Agent/1.0")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        with _req.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            return truncate(text)
    except Exception as e:
        return err(f"HTTP 请求失败: {e}")


def http_get(url: str, headers: str = "") -> str:
    """发送 HTTP GET 请求"""
    hdrs = json.loads(headers) if headers.strip() else None
    return _safe_request(url, "GET", headers=hdrs)


def http_post(url: str, body: str = "", headers: str = "") -> str:
    """发送 HTTP POST 请求"""
    hdrs = json.loads(headers) if headers.strip() else None
    return _safe_request(url, "POST", body=body, headers=hdrs)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "发送 HTTP GET 请求。内置 SSRF 防护，拦截内网地址。响应上限 8000 字符。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "请求 URL（仅 http/https）"},
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
            "description": "发送 HTTP POST 请求。内置 SSRF 防护。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "请求 URL（仅 http/https）"},
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
