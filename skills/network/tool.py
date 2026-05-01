"""HTTP 网络请求工具 — GET/POST，内置 SSRF 防护

SSRF 多层防护:
  1. 协议白名单 (仅 http/https)
  2. 主机名非空校验
  3. DNS 解析全部 IP 逐一检查（防多 IP 绕过）
  4. 禁用自动重定向，每跳重新校验目标
"""
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
_MAX_REDIRECTS = 5


def _is_private(host: str) -> bool:
    """检测主机是否为内网/回环地址。

    对域名执行 DNS 解析，检查返回的全部 IP（而非仅第一个），
    只要有一个是内网地址就拒绝。解析失败则保守拒绝。
    """
    try:
        ip = ipaddress.ip_address(host)
        # 已经是 IP 字面量，直接检查
        for net in _PRIVATE_NETS:
            if ip in net:
                return True
        return False
    except ValueError:
        pass

    # 域名 → DNS 解析全部 IP
    try:
        addrs = socket.getaddrinfo(host, None)
    except Exception:
        return True  # 解析失败，保守拒绝

    for info in addrs:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for net in _PRIVATE_NETS:
            if ip in net:
                return True
    return False


class _NoAutoRedirectHandler(_req.HTTPRedirectHandler):
    """禁用自动重定向——由调用方手动逐跳校验。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

    def http_error_301(self, req, fp, code, msg, headers):
        return self._hold(req, fp, code, msg, headers)

    def http_error_302(self, req, fp, code, msg, headers):
        return self._hold(req, fp, code, msg, headers)

    def http_error_303(self, req, fp, code, msg, headers):
        return self._hold(req, fp, code, msg, headers)

    def http_error_307(self, req, fp, code, msg, headers):
        return self._hold(req, fp, code, msg, headers)

    def http_error_308(self, req, fp, code, msg, headers):
        return self._hold(req, fp, code, msg, headers)

    def _hold(self, req, fp, code, msg, headers):
        return fp


def _do_request(url: str, method: str = "GET", body: bytes | None = None,
                headers: dict | None = None) -> str:
    """发送单次 HTTP 请求（不跟随重定向），返回响应体文字。

    对 3xx 响应，返回 Location 头让调用方手动跟进并重新校验。
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return err(f"协议不受支持: {parsed.scheme}（仅允许 http/https）")
    if not parsed.hostname:
        return err("URL 缺少主机名")

    if _is_private(parsed.hostname):
        return err(f"SSRF 拦截: 禁止访问内网地址 ({parsed.hostname})")

    try:
        req = _req.Request(url, data=body, method=method)
        req.add_header("User-Agent", "kesepain-Agent/1.0")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)

        opener = _req.build_opener(_NoAutoRedirectHandler)
        with opener.open(req, timeout=_TIMEOUT) as resp:
            status = resp.status
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")

            if 300 <= status < 400:
                location = resp.getheader("Location", "")
                if not location:
                    return err(f"HTTP {status} 重定向但缺少 Location 头")
                # 处理相对 URL
                from urllib.parse import urljoin
                next_url = urljoin(url, location)
                return err(f"__REDIRECT__{next_url}")

            return truncate(text)
    except Exception as e:
        return err(f"HTTP 请求失败: {e}")


def _safe_request(url: str, method: str = "GET", body: str = "",
                  headers: dict | None = None) -> str:
    """发送 HTTP 请求，带完整 SSRF 防护和逐跳重定向校验。"""
    if not HAS_URLLIB:
        return err("urllib 不可用")

    data = body.encode("utf-8") if body else None
    current_url = url
    seen = {url}
    hops = 0

    while hops < _MAX_REDIRECTS:
        result = _do_request(current_url, method, data, headers)
        if result.startswith("__REDIRECT__"):
            next_url = result[len("__REDIRECT__"):]
            # 循环检测
            if next_url in seen:
                return err(f"重定向循环: {next_url}")
            seen.add(next_url)
            # GET on redirect (302/303 change POST to GET)
            if method == "POST":
                method = "GET"
                data = None
            current_url = next_url
            hops += 1
            continue
        return result

    return err(f"重定向次数超过上限 ({_MAX_REDIRECTS})")


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
    try:
        hdrs = _parse_headers(headers)
    except ValueError as e:
        return err(str(e))
    return _safe_request(url, "GET", headers=hdrs)


def http_post(url: str, body: str = "", headers: str = "") -> str:
    """发送 HTTP POST 请求"""
    try:
        hdrs = _parse_headers(headers)
    except ValueError as e:
        return err(str(e))
    return _safe_request(url, "POST", body=body, headers=hdrs)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "发送 HTTP GET 请求。内置 SSRF 全 IP 检查 + 逐跳重定向校验。响应上限 8000 字符。",
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
