"""HTTP 网络请求工具 — GET/POST + 网页正文读取。"""
from html.parser import HTMLParser
import json
import os
import re
import ssl
import urllib.error
import urllib.request

from run.tool import register_tool
from plugins._common import err, get_effective_tool_timeout

_MAX_RESPONSE_BYTES = 0  # 0 = 不限制
_VERIFY_SSL = os.environ.get("HTTP_VERIFY_SSL", "1") != "0"
_READ_STRATEGIES = {"auto", "direct", "reader"}
_READER_SERVICES = {"auto", "jina", "markdown_new", "defuddle"}
_MAX_WEB_READ_CHARS = 100000
_DEFAULT_WEB_READ_CHARS = 20000

_READER_URLS = {
    "jina": "https://r.jina.ai/{url}",
    "markdown_new": "https://markdown.new/{url}",
    "defuddle": "https://defuddle.md/{url}",
}


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


_HTTP_TIMEOUT_DEFAULT = _env_int("HTTP_TIMEOUT", 15)


def _request_timeout() -> int:
    return get_effective_tool_timeout(_HTTP_TIMEOUT_DEFAULT)


def _ssl_ctx():
    if _VERIFY_SSL:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get_proxy() -> str | None:
    os_env = (
        os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or
        os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""
    )
    if os_env:
        return os_env
    if os.name == "nt":
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


def _decode_response(raw: bytes, content_type: str, headers) -> str:
    charset = ""
    try:
        charset = headers.get_content_charset() or ""
    except Exception:
        pass
    if not charset:
        match = re.search(r"charset=([^;\s]+)", content_type, re.I)
        if match:
            charset = match.group(1).strip("\"'")
    if not charset:
        charset = "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _request_error(e: Exception) -> str:
    hint = ""
    text = str(e)
    if "CERTIFICATE" in text.upper() or "SSL" in text.upper():
        hint = " (SSL 证书验证失败)"
    elif "timed out" in text.lower():
        hint = " (连接超时)"
    return f"HTTP 请求失败: {e}{hint}"


def _do_request_full(url: str, method: str = "GET", body: bytes | None = None,
                     headers: dict | None = None) -> dict:
    """发送 HTTP 请求，返回正文和响应元信息。"""
    try:
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("User-Agent", "votx-agent/1.0")
        if headers:
            for k, v in headers.items():
                req.add_header(str(k), str(v))

        proxy_url = _get_proxy()
        handlers = []
        if proxy_url:
            handlers.append(urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
        ctx = _ssl_ctx()
        if ctx:
            handlers.append(urllib.request.HTTPSHandler(context=ctx))
        opener = urllib.request.build_opener(*handlers) if handlers else urllib.request.build_opener()

        with opener.open(req, timeout=_request_timeout()) as resp:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                total += len(chunk)
                if _MAX_RESPONSE_BYTES > 0 and total > _MAX_RESPONSE_BYTES:
                    return {"ok": False, "error": f"响应体超过 {_MAX_RESPONSE_BYTES // 1024 // 1024}MB 限制，已截断"}
                chunks.append(chunk)

            raw = b"".join(chunks)
            content_type = resp.headers.get("Content-Type", "")
            text = _decode_response(raw, content_type, resp.headers)
            return {
                "ok": True,
                "url": resp.geturl(),
                "status": getattr(resp, "status", 200),
                "headers": dict(resp.headers.items()),
                "content_type": content_type,
                "text": text,
                "bytes": len(raw),
            }
    except urllib.error.URLError as e:
        return {"ok": False, "error": _request_error(e)}
    except Exception as e:
        return {"ok": False, "error": _request_error(e)}


def _do_request(url: str, method: str = "GET", body: bytes | None = None,
                headers: dict | None = None) -> str:
    result = _do_request_full(url, method, body, headers)
    if not result.get("ok"):
        return err(result.get("error", "HTTP 请求失败"))
    return result.get("text", "")


def _parse_headers(headers_str: str) -> dict | None:
    if not headers_str or not headers_str.strip():
        return None
    try:
        parsed = json.loads(headers_str)
        if not isinstance(parsed, dict):
            raise ValueError("headers 必须是 JSON object")
        return parsed
    except json.JSONDecodeError as e:
        raise ValueError(f"headers 不是合法 JSON: {e}") from e


class _ReadableHTMLParser(HTMLParser):
    _SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "template", "nav", "footer", "header"}
    _BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "div", "dl", "fieldset",
        "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
        "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table",
        "td", "th", "tr", "ul",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag in self._BLOCK_TAGS and not self._skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in self._BLOCK_TAGS and not self._skip_depth:
            self.parts.append("\n")

    def handle_data(self, data):
        if not data or self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
            return
        self.parts.append(data)


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _looks_like_html(text: str, content_type: str = "") -> bool:
    if "html" in (content_type or "").lower():
        return True
    sample = text[:500].lstrip().lower()
    return sample.startswith("<!doctype html") or sample.startswith("<html") or "<body" in sample


def _extract_readable_text(text: str, content_type: str = "") -> tuple[str, str]:
    if not text:
        return "", ""
    if not _looks_like_html(text, content_type):
        return _clean_text(text), ""

    parser = _ReadableHTMLParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return _clean_text(re.sub(r"<[^>]+>", " ", text)), ""

    title = _clean_text(" ".join(parser.title_parts))
    body = _clean_text(" ".join(parser.parts))
    return body, title


def _looks_blocked_or_empty(text: str) -> bool:
    if len(text.strip()) < 120:
        return True
    sample = text[:4000].lower()
    blocked = ["captcha", "access denied", "403 forbidden", "enable javascript",
                "just a moment", "cloudflare", "verify you are human"]
    return any(m in sample for m in blocked)


def _clamp_max_chars(max_chars) -> int:
    try:
        value = int(max_chars)
    except (TypeError, ValueError):
        value = _DEFAULT_WEB_READ_CHARS
    if value <= 0:
        return _DEFAULT_WEB_READ_CHARS
    return min(value, _MAX_WEB_READ_CHARS)


def _format_web_read(title: str, url: str, source: str, status: str, text: str, max_chars: int) -> str:
    original_len = len(text)
    shown = text[:max_chars]
    if original_len > max_chars:
        status = "partial"
        shown += f"\n... (截断，共 {original_len} 字符)"
    return (
        f"Title: {title or '(无标题)'}\n"
        f"URL: {url}\n"
        f"Source: {source}\n"
        f"Status: {status}\n"
        f"Chars: {min(original_len, max_chars)}/{max_chars}\n\n"
        f"{shown}"
    )


def _empty_direct_explanation(text: str, content_type: str) -> str:
    if _looks_like_html(text, content_type):
        sample = text[:3000].lower()
        if 'id="root"' in sample or 'type="module"' in sample:
            return (
                "direct 抓取成功，但 HTML 中没有服务端渲染的可读正文。\n"
                "这通常是 React/Vue 等 SPA 页面：HTTP 返回的是入口 HTML 空壳，"
                "实际内容需要浏览器执行 JavaScript 后才会渲染。"
            )
        return "direct 抓取成功，但 HTML 中没有提取到可读正文。"
    return "direct 抓取成功，但响应体为空或没有可读文本。"


def http_get(url: str, headers: str = "") -> str:
    """发送 HTTP GET 请求。"""
    try:
        hdrs = _parse_headers(headers)
    except ValueError as e:
        return err(str(e))
    return _do_request(url, "GET", headers=hdrs)


def http_post(url: str, body: str = "", headers: str = "") -> str:
    """发送 HTTP POST 请求。"""
    try:
        hdrs = _parse_headers(headers)
    except ValueError as e:
        return err(str(e))
    data = body.encode("utf-8") if body else None
    return _do_request(url, "POST", body=data, headers=hdrs)


def _read_direct(url: str, headers: dict | None, max_chars: int) -> tuple[bool, str, str, bool]:
    result = _do_request_full(url, "GET", headers=headers)
    if not result.get("ok"):
        return False, "", result.get("error", "direct 读取失败"), False

    body, title = _extract_readable_text(result.get("text", ""), result.get("content_type", ""))
    if not body:
        output = _format_web_read(
            title=title, url=result.get("url") or url, source="direct",
            status="partial", text=_empty_direct_explanation(result.get("text", ""), result.get("content_type", "")),
            max_chars=max_chars,
        )
        return True, output, "", False

    useful = not _looks_blocked_or_empty(body)
    output = _format_web_read(
        title=title, url=result.get("url") or url, source="direct",
        status="success", text=body, max_chars=max_chars,
    )
    return True, output, "", useful


def _reader_service_order(reader_service: str) -> list[str]:
    service = (reader_service or "auto").strip().lower()
    if service not in _READER_SERVICES:
        service = "auto"
    if service == "auto":
        return ["jina", "markdown_new", "defuddle"]
    return [service]


def _read_with_reader(url: str, reader_service: str, max_chars: int) -> tuple[bool, str, str]:
    errors = []
    for service in _reader_service_order(reader_service):
        service_url = _READER_URLS[service].format(url=url)
        result = _do_request_full(service_url, "GET")
        if not result.get("ok"):
            errors.append(f"{service}: {result.get('error', 'reader 读取失败')}")
            continue
        body, title = _extract_readable_text(result.get("text", ""), result.get("content_type", ""))
        if body:
            output = _format_web_read(
                title=title, url=url, source=service,
                status="success", text=body, max_chars=max_chars,
            )
            return True, output, ""
        errors.append(f"{service}: 返回内容为空")
    return False, "", "; ".join(errors)


def web_read(url: str, strategy: str = "auto", reader_service: str = "auto",
             max_chars: int = _DEFAULT_WEB_READ_CHARS, headers: str = "") -> str:
    """读取网页正文文字或 Markdown，不返回网页源码。"""
    strategy = (strategy or "auto").strip().lower()
    if strategy not in _READ_STRATEGIES:
        strategy = "auto"
    max_len = _clamp_max_chars(max_chars)

    try:
        hdrs = _parse_headers(headers)
    except ValueError as e:
        return err(str(e))

    direct_error = ""
    if strategy in {"auto", "direct"}:
        ok, output, direct_error, useful = _read_direct(url, hdrs, max_len)
        if ok:
            if strategy == "direct" or useful:
                return output
        elif strategy == "direct":
            return err(direct_error)

    if strategy in {"auto", "reader"}:
        ok, output, reader_error = _read_with_reader(url, reader_service, max_len)
        if ok:
            return output
        if direct_error:
            return err(f"direct 失败: {direct_error}; reader 失败: {reader_error}")
        return err(f"reader 失败: {reader_error}")

    return err("网页读取失败")


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "发送 HTTP GET 请求，返回原始响应内容。当需要调用 API、获取 JSON 数据、调试接口、查看 HTTP 响应原始内容、下载文本时使用。",
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
            "description": "发送 HTTP POST 请求，返回原始响应内容。当需要向 API 提交数据、发送 JSON 请求体、提交表单、调用需要 POST 的接口时使用。",
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
    {
        "type": "function",
        "function": {
            "name": "web_read",
            "description": "读取网页正文文字或 Markdown，不返回网页源码。当需要阅读文章、博客、新闻、在线文档、网页转文字、提取网页内容时使用。优先本地解析，公网 direct 失败后可使用 reader 服务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要读取的网页 URL，仅支持 http/https"},
                    "strategy": {
                        "type": "string",
                        "enum": ["auto", "direct", "reader"],
                        "description": "auto 先 direct 后 reader；direct 只本地解析；reader 只使用第三方 reader",
                    },
                    "reader_service": {
                        "type": "string",
                        "enum": ["auto", "jina", "markdown_new", "defuddle"],
                        "description": "第三方网页转正文服务",
                    },
                    "max_chars": {
                        "type": "integer", "description": "返回正文最大字符数，默认 20000，上限 100000",
                    },
                    "headers": {
                        "type": "string", "description": "JSON 格式请求头，可选，仅 direct 抓取时使用",
                    },
                },
                "required": ["url"],
            },
        },
    },
]

HANDLERS = {"http_get": http_get, "http_post": http_post, "web_read": web_read}


def register():
    for s in SCHEMAS:
        register_tool(s, HANDLERS[s["function"]["name"]])
