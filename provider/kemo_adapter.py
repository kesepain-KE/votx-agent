"""Kemo LLM Adapter provider — 完全独立的本地网关适配器。

所有通信用 urllib HTTP 直接调用 llm-adapter-kemo 端点。
不依赖 OpenAI SDK，不依赖市场 API。

ASR 降级策略：
  1. Kemo 网关 /v1/audio/transcriptions 优先
  2. 网关返回 404/501（未映射 ASR 路由）时 → StepFun 原生 SSE ASR
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import time as _time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Generator

from provider.base import BaseProvider, VALID_CAPABILITIES
from provider.schema import ProviderResponse, ToolCall


DEFAULT_KEMO_BASE_URL = "http://127.0.0.1:8741/v1"
DEFAULT_CHAT_MODEL = "stepfun-step-3.7-flash"
DEFAULT_ASR_MODEL = "stepfun-stepaudio-2.5-asr"
DEFAULT_TTS_MODEL = "stepfun-stepaudio-2.5-tts"
DEFAULT_IMAGE_EDIT_MODEL = "stepfun-step-image-edit-2"

MAX_RETRIES = 2
RETRY_DELAY = 1.0


def _normalize_base_url(base_url: str) -> str:
    base = (base_url or DEFAULT_KEMO_BASE_URL).strip().rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def _configured(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _error_message(body: str) -> str:
    try:
        data = json.loads(body)
    except Exception:
        return body[:500]
    detail = data.get("detail", data)
    if isinstance(detail, dict):
        err = detail.get("error", detail)
        if isinstance(err, dict):
            return str(err.get("message") or err.get("detail") or err)
        return str(err)
    return str(detail)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _multipart_body(fields: dict[str, str], files: list[tuple[str, str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----votx-kemo-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    for name, filename, data, content_type in files:
        safe_filename = filename.replace('"', "")
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{safe_filename}"\r\n'
            ).encode("utf-8")
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(data)
        chunks.append(b"\r\n")

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class KemoProvider(BaseProvider):
    """Kemo LLM Adapter 本地网关 Provider — 纯 HTTP，无 OpenAI SDK 依赖。

    用法::

        provider = KemoProvider(user_config, core_config)
        resp = provider.respond([{"role": "user", "content": "你好"}])
        for event in provider.respond_stream(messages):
            ...
    """

    def __init__(self, user_config: dict, core_config: dict | None = None):
        core = core_config or {}
        cfg = user_config.get("provider", {})

        api_key = _configured(cfg.get("api_key")) or os.environ.get("KEMO_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "Kemo API Key 未设置。请在 provider.api_key 中填写 Kemo 的 sk-kemo-* 密钥，"
                "或设置 KEMO_API_KEY。"
            )

        self.base_url: str = _normalize_base_url(
            _configured(cfg.get("base_url"))
            or os.environ.get("KEMO_BASE_URL", "")
            or DEFAULT_KEMO_BASE_URL
        )
        self.kemo_api_key: str = api_key
        self.model: str = _configured(cfg.get("model")) or DEFAULT_CHAT_MODEL
        self.stream: bool = cfg.get("stream", core.get("output", {}).get("stream", False))
        self.think: bool = True  # 始终开启思考功能
        self.timeout: int = cfg.get("timeout", 120)

        # 能力模型
        self.vision_model: str = _configured(cfg.get("vision_model")) or self.model
        self.audio_transcription_model: str = _configured(cfg.get("audio_transcription_model")) or DEFAULT_ASR_MODEL
        self.speech_generation_model: str = _configured(cfg.get("speech_generation_model")) or DEFAULT_TTS_MODEL
        self.image_generation_model: str = _configured(cfg.get("image_generation_model", ""))
        self.image_edit_model: str = _configured(cfg.get("image_edit_model")) or DEFAULT_IMAGE_EDIT_MODEL
        self.speech_to_speech_model: str = _configured(cfg.get("speech_to_speech_model", ""))
        self.video_generation_model: str = _configured(cfg.get("video_generation_model", ""))

        self.user_config: dict = user_config
        self.last_response: ProviderResponse | None = None
        self.last_usage: dict | None = None

    # ── BaseProvider 核心接口 ──

    def capabilities(self) -> set[str]:
        cfg = self.user_config.get("provider", {}) or {}
        override = cfg.get("capabilities_override")
        if override is not None:
            return {c for c in override if c in VALID_CAPABILITIES}

        caps: set[str] = set()
        if self.vision_model:
            caps.add("vision")
        if self.audio_transcription_model:
            caps.add("audio_transcription")
        if self.speech_generation_model:
            caps.add("speech_generation")
        if self.speech_to_speech_model:
            caps.add("speech_to_speech")
        if self.image_generation_model:
            caps.add("image_generation")
        if self.image_edit_model:
            caps.add("image_edit")
        if self.video_generation_model:
            caps.add("video_generation")
        return caps

    # ── Chat ──

    def respond(
        self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None
    ) -> ProviderResponse:
        """非流式聊天 — POST {base_url}/v1/chat/completions。"""
        effective_model = model or self.model
        body: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "stream": False,
        }
        body["reasoning_effort"] = "high"
        if tools:
            body["tools"] = tools

        payload = self._json_request("POST", "chat/completions", body)

        msg = payload.get("choices", [{}])[0].get("message", {})
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""

        tool_calls = []
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, AttributeError):
                args = {}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                input=args,
            ))

        self.last_usage = payload.get("usage")
        result = ProviderResponse(
            text=content,
            reasoning=reasoning,
            tool_calls=tool_calls,
            finish_reason=msg.get("finish_reason") or "",
            usage=self.last_usage,
        )
        self.last_response = result
        return result

    def respond_stream(
        self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None
    ) -> Generator[dict, None, None]:
        """流式聊天 — POST {base_url}/v1/chat/completions stream=True，手动解析 SSE。"""
        effective_model = model or self.model
        body: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "stream": True,
        }
        body["reasoning_effort"] = "high"
        if tools:
            body["tools"] = tools

        url = self._endpoint("chat/completions")
        headers = {
            "Authorization": f"Bearer {self.kemo_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        raw_body = _json_bytes(body)

        last_err = None
        response = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                request = urllib.request.Request(url, data=raw_body, headers=headers, method="POST")
                response = urllib.request.urlopen(request, timeout=self.timeout)
                break
            except urllib.error.HTTPError as exc:
                body_text = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Kemo chat stream failed ({exc.code}): {_error_message(body_text)}") from exc
            except (urllib.error.URLError, OSError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"Kemo chat stream 失败（已重试 {MAX_RETRIES} 次）: {e}") from e

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None

        buf = b""
        try:
            while True:
                chunk = response.read(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line_bytes, buf = buf.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        continue
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # usage（通常出现在最后）
                    if obj.get("usage"):
                        usage = obj["usage"]
                        if isinstance(usage, dict):
                            self.last_usage = {
                                "prompt_tokens": usage.get("prompt_tokens", 0),
                                "completion_tokens": usage.get("completion_tokens", 0),
                                "total_tokens": usage.get("total_tokens", 0),
                            }

                    choices = obj.get("choices", [])
                    for choice in choices:
                        delta = choice.get("delta", {})
                        if delta.get("reasoning_content"):
                            reasoning_parts.append(delta["reasoning_content"])
                            yield {"type": "thinking_chunk", "content": delta["reasoning_content"]}
                        if delta.get("content"):
                            content_parts.append(delta["content"])
                            yield {"type": "text_chunk", "content": delta["content"]}
                        for tc in delta.get("tool_calls", []) or []:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_map:
                                tool_calls_map[idx] = {
                                    "id": tc.get("id", ""),
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.get("id"):
                                tool_calls_map[idx]["id"] = tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                tool_calls_map[idx]["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                tool_calls_map[idx]["function"]["arguments"] += fn["arguments"]
        finally:
            if response:
                try:
                    response.close()
                except Exception:
                    pass

        content = "".join(content_parts)
        reasoning = "".join(reasoning_parts)

        tool_calls = []
        for idx in sorted(tool_calls_map):
            tc = tool_calls_map[idx]
            fn_name = tc["function"]["name"]
            fn_args_str = tc["function"]["arguments"]
            try:
                fn_args = json.loads(fn_args_str) if fn_args_str else {}
            except json.JSONDecodeError:
                fn_args = {}
            tool_calls.append(ToolCall(id=tc["id"], name=fn_name, input=fn_args))

        result = ProviderResponse(
            text=content,
            reasoning=reasoning,
            tool_calls=tool_calls,
            usage=self.last_usage,
        )
        self.last_response = result
        return

    # ── HTTP 内部工具 ──

    def _endpoint(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _json_request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = self._endpoint(path)
        headers = {
            "Authorization": f"Bearer {self.kemo_api_key}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            data = _json_bytes(payload)
            headers["Content-Type"] = "application/json"

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                request = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                body_text = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Kemo {path} failed ({exc.code}): {_error_message(body_text)}") from exc
            except (urllib.error.URLError, OSError) as exc:
                last_err = exc
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"Kemo {path} connection failed: {exc}") from exc
        raise RuntimeError("unreachable")

    # ── Image / Audio / Video / Embedding / Rerank ──

    def generate_image(self, prompt: str, **kwargs) -> list[dict]:
        if "image_generation" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持图像生成 (image_generation)")

        cfg = self.user_config.get("provider", {}) or {}
        model = _configured(kwargs.get("model")) or _configured(cfg.get("image_generation_model"))
        if not model:
            raise ValueError("image_generation_model 未配置")

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": int(kwargs.get("n", 1)),
            "size": kwargs.get("size", "1024x1024"),
            "response_format": kwargs.get("response_format", "url"),
        }
        for key in ("quality", "style", "negative_prompt", "seed"):
            if kwargs.get(key) is not None:
                payload[key] = kwargs[key]

        response = self._json_request("POST", "images/generations", payload)
        results: list[dict] = []
        for item in response.get("data", []):
            if isinstance(item, dict):
                results.append({
                    "url": item.get("url"),
                    "b64_json": item.get("b64_json"),
                    "revised_prompt": item.get("revised_prompt") or item.get("prompt") or prompt,
                    "finish_reason": item.get("finish_reason"),
                    "seed": item.get("seed"),
                })
        return results

    def edit_image(self, image_path: str, prompt: str, **kwargs) -> list[dict]:
        if "image_edit" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持图像编辑 (image_edit)")

        image_file = Path(image_path)
        if not image_file.is_file():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        model = (
            _configured((self.user_config.get("provider", {}) or {}).get("image_edit_model"))
            or DEFAULT_IMAGE_EDIT_MODEL
        )
        response_format = kwargs.get("response_format", "url")
        size = kwargs.get("size")
        filename = image_file.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        image_bytes = image_file.read_bytes()

        fields = {
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
        }
        if size:
            fields["size"] = size

        body, multipart_type = _multipart_body(
            fields=fields,
            files=[
                ("image", filename, image_bytes, content_type),
                ("image_file", filename, image_bytes, content_type),
            ],
        )

        url = f"{self.base_url.rstrip('/')}/images/edits"
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.kemo_api_key}",
                "Content-Type": multipart_type,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kemo image edit failed ({exc.code}): {_error_message(body_text)}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Kemo image edit connection failed: {exc}") from exc

        results: list[dict] = []
        for item in payload.get("data", []):
            if not isinstance(item, dict):
                continue
            results.append({
                "url": item.get("url"),
                "b64_json": item.get("b64_json"),
                "revised_prompt": item.get("revised_prompt") or item.get("prompt") or prompt,
                "finish_reason": item.get("finish_reason"),
                "seed": item.get("seed"),
            })
        return results

    def generate_speech(self, text: str, **kwargs) -> str:
        """TTS — 直接 POST {base_url}/v1/audio/speech。"""
        if "speech_generation" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持语音生成 (speech_generation)")

        cfg = self.user_config.get("provider", {}) or {}
        model = _configured(kwargs.get("model")) or _configured(cfg.get("speech_generation_model"))
        if not model:
            raise ValueError("speech_generation_model 未配置")

        voice = kwargs.get("voice", "cixingnansheng")
        fmt = kwargs.get("format") or kwargs.get("response_format") or "mp3"
        speed = kwargs.get("speed", 1.0)
        output_dir = kwargs.get("output_dir", "")
        if not output_dir:
            raise ValueError("output_dir 不能为空")
        os.makedirs(output_dir, exist_ok=True)
        filename = kwargs.get("filename", f"speech_{uuid.uuid4().hex[:8]}.{fmt}")
        filepath = os.path.join(output_dir, filename)

        payload: dict[str, Any] = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": fmt,
            "speed": speed,
        }
        for key in ("instruction", "volume", "sample_rate"):
            if kwargs.get(key) is not None:
                payload[key] = kwargs[key]

        url = f"{self.base_url.rstrip('/')}/audio/speech"
        request = urllib.request.Request(
            url,
            data=_json_bytes(payload),
            headers={
                "Authorization": f"Bearer {self.kemo_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kemo TTS failed ({exc.code}): {_error_message(body_text)}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Kemo TTS connection failed: {exc}") from exc

        with open(filepath, "wb") as f:
            f.write(content)
        return filepath

    def transcribe_audio(self, file_path: str, **kwargs) -> str:
        """ASR — Kemo 网关优先，StepFun 原生 SSE ASR 降级。

        优先 Kemo 网关，网关返回 404/501 时用同一套凭据再试标准接口。
        """
        if "audio_transcription" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持语音识别 (audio_transcription)")

        audio_file = Path(file_path)
        if not audio_file.is_file():
            raise FileNotFoundError(f"音频文件不存在: {file_path}")

        cfg = self.user_config.get("provider", {}) or {}
        model = _configured(kwargs.get("model")) or _configured(cfg.get("audio_transcription_model"))
        if not model:
            raise ValueError("audio_transcription_model 未配置")

        # ── 第 1 步：Kemo 网关 ──
        try:
            return self._transcribe_audio_kemo(audio_file, model, **kwargs)
        except urllib.error.HTTPError as exc:
            if exc.code not in (404, 501):
                body_text = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Kemo ASR failed ({exc.code}): {_error_message(body_text)}"
                ) from exc
            kemo_err = f"Kemo ASR ({exc.code}): {_error_message(exc.read().decode('utf-8', errors='replace'))}"
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Kemo ASR connection failed: {exc}") from exc
        except RuntimeError as exc:
            # 404/501 也可能被 _transcribe_audio_kemo 以 RuntimeError 抛出
            msg = str(exc)
            if "404" not in msg and "501" not in msg:
                raise
            kemo_err = msg

        # ── 第 2 步：标准 ASR 接口降级 ──
        stepfun_err = None
        try:
            return self._transcribe_audio_fallback(audio_file, model, **kwargs)
        except Exception as exc:
            stepfun_err = str(exc)

        raise RuntimeError(
            f"ASR 全部失败: {kemo_err}; "
            f"StepFun fallback {'也' if stepfun_err else '未配置或跳过'}"
            + (f" ({stepfun_err})" if stepfun_err else "")
        )

    def _transcribe_audio_kemo(self, audio_file: Path, model: str, **kwargs) -> str:
        """通过 Kemo 网关 multipart 上传音频进行 ASR。"""
        language = kwargs.get("language", "zh")
        prompt = kwargs.get("prompt", "")
        content_type = mimetypes.guess_type(audio_file.name)[0] or "application/octet-stream"
        audio_bytes = audio_file.read_bytes()

        fields: dict[str, str] = {"model": model, "language": language}
        if prompt:
            fields["prompt"] = prompt

        body, multipart_type = _multipart_body(
            fields=fields,
            files=[("file", audio_file.name, audio_bytes, content_type)],
        )

        url = f"{self.base_url.rstrip('/')}/audio/transcriptions"
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.kemo_api_key}",
                "Content-Type": multipart_type,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return (payload.get("text") or "").strip()

    def _transcribe_audio_fallback(self, audio_file: Path, model: str, **kwargs) -> str:
        """标准 ASR 降级 — 复用同一套 api_key + base_url 再试一次。

        走 OpenAI 兼容的 /v1/audio/transcriptions multipart 接口。
        小米模型就是因为支持标准接口才成功语音识别的。
        """
        language = kwargs.get("language", "zh")
        prompt = kwargs.get("prompt", "")
        content_type = mimetypes.guess_type(audio_file.name)[0] or "application/octet-stream"
        audio_bytes = audio_file.read_bytes()

        fields: dict[str, str] = {"model": model, "language": language}
        if prompt:
            fields["prompt"] = prompt

        body, multipart_type = _multipart_body(
            fields=fields,
            files=[("file", audio_file.name, audio_bytes, content_type)],
        )

        url = f"{self.base_url.rstrip('/')}/audio/transcriptions"
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.kemo_api_key}",
                "Content-Type": multipart_type,
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return (payload.get("text") or "").strip()

    def speech_to_speech(self, audio_path: str, **kwargs) -> str:
        if "speech_to_speech" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持语音生语音 (speech_to_speech)")

        audio_file = Path(audio_path)
        if not audio_file.is_file():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        cfg = self.user_config.get("provider", {}) or {}
        model = _configured(kwargs.get("model")) or _configured(cfg.get("speech_to_speech_model"))
        if not model:
            raise ValueError("speech_to_speech_model 未配置")

        fmt = kwargs.get("format") or kwargs.get("response_format") or "mp3"
        output_dir = kwargs.get("output_dir", "")
        if not output_dir:
            raise ValueError("output_dir 不能为空")
        os.makedirs(output_dir, exist_ok=True)
        filename = kwargs.get("filename", f"speech_to_speech_{uuid.uuid4().hex[:8]}.{fmt}")
        filepath = os.path.join(output_dir, filename)

        content_type = mimetypes.guess_type(audio_file.name)[0] or "application/octet-stream"
        fields: dict[str, str] = {"model": model, "response_format": fmt}
        for key in ("prompt", "instruction", "voice", "speed"):
            if kwargs.get(key) is not None:
                fields[key] = str(kwargs[key])

        audio_bytes = audio_file.read_bytes()
        body, multipart_type = _multipart_body(
            fields=fields,
            files=[
                ("file", audio_file.name, audio_bytes, content_type),
                ("audio", audio_file.name, audio_bytes, content_type),
            ],
        )
        url = f"{self.base_url.rstrip('/')}/audio/speech-to-speech"
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.kemo_api_key}",
                "Content-Type": multipart_type,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kemo speech-to-speech failed ({exc.code}): {_error_message(body_text)}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Kemo speech-to-speech connection failed: {exc}") from exc

        with open(filepath, "wb") as f:
            f.write(content)
        return filepath

    def generate_video(self, prompt: str = "", **kwargs) -> dict:
        if "video_generation" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持视频生成 (video_generation)")

        cfg = self.user_config.get("provider", {}) or {}
        model = _configured(kwargs.get("model")) or _configured(cfg.get("video_generation_model"))
        if not model:
            raise ValueError("video_generation_model 未配置")

        payload: dict[str, Any] = {"model": model}
        if prompt:
            payload["prompt"] = prompt
        for key in ("image", "video", "duration", "size", "seed", "negative_prompt"):
            if kwargs.get(key):
                payload[key] = kwargs[key]
        return self._json_request("POST", "videos/generations", payload)

    def get_video(self, job_id: str, **kwargs) -> dict:
        if "video_generation" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持视频生成 (video_generation)")
        return self._json_request("GET", f"videos/{job_id}")

    def download_video(self, job_id: str, output_dir: str, **kwargs) -> str:
        if "video_generation" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持视频生成 (video_generation)")
        if not output_dir:
            raise ValueError("output_dir 不能为空")
        os.makedirs(output_dir, exist_ok=True)

        filename = kwargs.get("filename") or f"video_{job_id}.mp4"
        filepath = os.path.join(output_dir, filename)
        request = urllib.request.Request(
            self._endpoint(f"videos/{job_id}/content"),
            headers={"Authorization": f"Bearer {self.kemo_api_key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                raw = response.read()
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kemo video content failed ({exc.code}): {_error_message(body_text)}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Kemo video content connection failed: {exc}") from exc

        if "application/json" in content_type:
            payload = json.loads(raw.decode("utf-8"))
            url = payload.get("url") or payload.get("content_url") or payload.get("video_url")
            if url:
                urllib.request.urlretrieve(url, filepath)
                return filepath
            data = payload.get("b64_json") or payload.get("base64") or payload.get("video")
            if isinstance(data, str):
                if data.startswith("data:"):
                    data = data.split(",", 1)[1]
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(data))
                return filepath
            with open(os.path.splitext(filepath)[0] + ".json", "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return os.path.splitext(filepath)[0] + ".json"

        with open(filepath, "wb") as f:
            f.write(raw)
        return filepath