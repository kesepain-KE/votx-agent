"""OpenAI Responses API Provider — 优先使用新 Responses API，自动回退 Completions API

Responses API 是 OpenAI 2025 年推出的统一 API:
- POST /v1/responses
- input 传对话内容，tools 用扁平格式
- 流式事件类型: response.output_text.delta / response.function_call_arguments.delta
- 与 Chat Completions API 的主要差异: input 格式、tool schema、output 结构

当接口不支持时自动回退到 Chat Completions API。
"""

import json
import os
import time as _time
from pathlib import Path
from typing import Any, Generator

# 修复 Windows SSL_CERT_FILE
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError

from provider.base import BaseProvider
from provider.schema import ProviderResponse, ToolCall

# 加载 .env
def _load_dotenv():
    """执行 load_dotenv 内部辅助逻辑。"""
    try:
        from paths import get_project_root
        root = Path(get_project_root())
    except Exception:
        root = Path(__file__).resolve().parent.parent
    for candidate in [
        root / ".env",
        Path.cwd() / ".env",
    ]:
        try:
            if candidate.is_file():
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_dotenv()

MAX_RETRIES = 2
RETRY_DELAY = 1.0

_RESPONSES_VISION_KEYWORDS = [
    "gpt-5", "gpt-4.1", "gpt-4o", "gpt-4-vision", "gpt-4-turbo",
    "gemini", "gemma-3",
    "vision", "vl-", "-vl",
    "mimo", "minimax",
    "qwen-vl", "qwen2-vl", "qwen2.5-vl",
    "pixtral", "llama-3.2-vision", "llama-v",
]


def _supports_vision_model(model: str) -> bool:
    return any(kw in model.lower() for kw in _RESPONSES_VISION_KEYWORDS)


class ResponsesProvider(BaseProvider):
    """OpenAI Responses API Provider — 自动回退到 Chat Completions"""

    def __init__(self, user_config: dict, core_config: dict | None = None):
        """执行 init 内部辅助逻辑。"""
        core = core_config or {}
        cfg = user_config.get("provider", {})

        api_key = (
            cfg.get("api_key", "").strip()
            or os.environ.get("DEEPSEEK_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        if not api_key:
            raise ValueError("API Key 未设置")

        base_url = (
            cfg.get("base_url", "").strip()
            or os.environ.get("DEEPSEEK_BASE_URL", "")
            or "https://api.deepseek.com"
        )

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = cfg.get("model", "deepseek-v4-flash")
        self.base_url = base_url
        self.think = cfg.get("think", False)
        self.stream = cfg.get("stream", core.get("output", {}).get("stream", True))
        self.timeout = cfg.get("timeout", 120)
        self.user_config = user_config
        self.vision_model = cfg.get("vision_model", "")
        self.last_usage: dict | None = None
        self.last_response: ProviderResponse | None = None

        # api 风格：仅两种选一，默认 chat
        api_style = cfg.get("api_style", "")
        if api_style == "responses":
            self._use_responses = True
        else:
            self._use_responses = False
        self._user_config = user_config
        self._responses_available = None  # None=未探测, True/False

    # ── BaseProvider 接口 ──

    def capabilities(self) -> set[str]:
        """返回 provider 支持的能力集合。四层判定标准：

        1. capabilities_override (不为 null) → 用户全权控制，直接返回
        2. api.openai.com → Vision + Audio/Image/Speech 全开（官方端点齐全）
        3. 专用模型字段非空 → 用户显式配置 = 信任声明，加对应能力
           - vision_model             → vision
           - audio_transcription_model → audio_transcription
           - image_generation_model   → image_generation
           - speech_generation_model  → speech_generation
        4. Vision 兜底: 聊天模型名命中多模态关键词也自动开启（走 chat 端点）
        """
        from provider.base import VALID_CAPABILITIES
        cfg = self.user_config.get("provider", {}) or {}
        override = cfg.get("capabilities_override")
        if override is not None:
            return {c for c in override if c in VALID_CAPABILITIES}
        caps = set()
        base = (self.base_url or "").lower()
        is_openai = not base or "api.openai.com" in base

        # Vision: 专用模型 > 关键词 > OpenAI 官方自动
        if cfg.get("vision_model") or _supports_vision_model(self.model) or is_openai:
            caps.add("vision")

        # Audio/Image/Speech: OpenAI 官方全开，其他厂商靠专用模型字段声明
        if is_openai:
            caps.update({"image_generation", "speech_generation", "audio_transcription"})
        else:
            if cfg.get("audio_transcription_model"):
                caps.add("audio_transcription")
            if cfg.get("image_generation_model"):
                caps.add("image_generation")
            if cfg.get("speech_generation_model"):
                caps.add("speech_generation")

        return caps

    # ── 多模态 chat 降级辅助 ──

    def _chat_completion(self, messages: list[dict], model: str, max_tokens: int = 4096):
        """Raw chat completion，绕过 respond() 避免工具递归。
        返回 ChatCompletionMessage 对象（含 content/audio/model_extra 等所有字段）。
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "timeout": self.timeout,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message

    @staticmethod
    def _extract_audio_from_message(msg, content: str) -> tuple:
        """多策略从 chat message 提取音频数据。返回 (bytes|None, format_str)。

        策略优先级:
        1. message.audio / message.audio_data 等直接字段
        2. message.model_extra 中的音频字段
        3. content 文本解析: JSON {audio/data/b64_json} → 裸 base64
        """
        import base64 as _b64, re as _re, json as _json

        # 策略 1: message 直接属性 (OpenAI GPT-4o audio 等)
        # 支持 dict 和 Pydantic 对象两种类型
        for attr in ("audio", "audio_data", "output_audio"):
            val = getattr(msg, attr, None)
            if val is None:
                continue
            # Pydantic 对象: val.data / val.id / val.transcript
            if hasattr(val, "data") and not isinstance(val, dict):
                data = getattr(val, "data", None)
                fmt = getattr(val, "format", "mp3")
                if data:
                    try:
                        return _b64.b64decode(data), fmt
                    except Exception:
                        pass
                # data 可能不是 base64 而是 bytes
                if isinstance(data, bytes):
                    fmt = getattr(val, "format", "mp3")
                    return data, fmt
            # dict: {"data": "...", "format": "mp3"}
            if isinstance(val, dict):
                data = val.get("data") or val.get("b64_json") or ""
                fmt = val.get("format", "mp3")
                if data:
                    try:
                        return _b64.b64decode(data), fmt
                    except Exception:
                        pass
            # raw string
            if isinstance(val, str) and len(val) > 100:
                try:
                    return _b64.b64decode(val), "mp3"
                except Exception:
                    pass

        # 策略 2: model_extra (Pydantic v2 额外字段)
        extra = getattr(msg, "model_extra", None) or {}
        if isinstance(extra, dict):
            for k in ("audio", "audio_data", "audio_output", "data", "output"):
                v = extra.get(k)
                if isinstance(v, dict):
                    data = v.get("data") or v.get("b64_json") or ""
                    fmt = v.get("format", "mp3")
                    if data:
                        try:
                            return _b64.b64decode(data), fmt
                        except Exception:
                            pass
                elif isinstance(v, str) and len(v) > 100:
                    try:
                        return _b64.b64decode(v), "mp3"
                    except Exception:
                        pass

        # 策略 3: content 文本解析
        if not content:
            return None, ""
        content = content.strip()
        try:
            data = _json.loads(content)
            fmt = data.get("format", "mp3")
            for k in ("audio", "data", "b64_json", "audio_data"):
                if k in data and isinstance(data[k], str):
                    return _b64.b64decode(data[k]), data.get("format", fmt)
        except (ValueError, Exception):
            pass
        if _re.match(r'^[A-Za-z0-9+/=\s]+$', content):
            try:
                return _b64.b64decode(_re.sub(r'\s+', '', content)), "mp3"
            except Exception:
                pass
        return None, ""

    @staticmethod
    def _parse_images_from_chat(content: str, prompt: str) -> list[dict]:
        """尝试从 chat 响应提取图像 URL/base64。"""
        import json as _json
        if not content:
            return []
        content = content.strip()
        results: list[dict] = []
        # JSON: {"images": [...], "data": [...]}
        try:
            data = _json.loads(content)
            items = data.get("images") or data.get("data") or [data]
            if isinstance(items, dict):
                items = [items]
            for item in items:
                results.append({
                    "url": item.get("url"),
                    "b64_json": item.get("b64_json"),
                    "revised_prompt": item.get("revised_prompt", prompt),
                })
            if results:
                return results
        except (ValueError, Exception):
            pass
        # URL in text
        for word in content.split():
            if word.startswith(("http://", "https://")) and any(
                ext in word.lower() for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")
            ):
                results.append({"url": word, "b64_json": None, "revised_prompt": prompt})
        return results

    def transcribe_audio(self, file_path: str, **kwargs) -> str:
        if "audio_transcription" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持语音识别 (audio_transcription)")
        model = (self.user_config.get("provider", {}) or {}).get("audio_transcription_model") or "whisper-1"
        language = kwargs.get("language", "")
        prompt = kwargs.get("prompt", "")
        timestamp_granularity = kwargs.get("timestamp_granularity", "segment")

        # 尝试原生 transcription 端点
        try:
            with open(file_path, "rb") as f:
                params = {"model": model, "file": f}
                if language:
                    params["language"] = language
                if prompt:
                    params["prompt"] = prompt
                if timestamp_granularity in ("word", "segment"):
                    params["timestamp_granularities"] = [timestamp_granularity]
                    params["response_format"] = "verbose_json"
                transcription = self.client.audio.transcriptions.create(**params)
            if hasattr(transcription, "text"):
                text = transcription.text
                if timestamp_granularity in ("word", "segment") and hasattr(transcription, "segments"):
                    import json as _json
                    segs = [{"start": s.start, "end": s.end, "text": s.text}
                            for s in transcription.segments]
                    return f"{text}\n\n--- 时间戳 ---\n{_json.dumps(segs, ensure_ascii=False, indent=2)}"
                return text
            return str(transcription)
        except Exception:
            pass  # 降级到 chat completions

        # 降级: chat completions (适配非标准 transcription 模型)
        import base64 as _b64
        with open(file_path, "rb") as f:
            audio_b64 = _b64.b64encode(f.read()).decode()
        msg = self._chat_completion(
            [{"role": "user", "content": [
                {"type": "text", "text": prompt or "Please transcribe the following audio."},
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
            ]}],
            model,
        )
        return (msg.content or "").strip()

    def generate_image(self, prompt: str, **kwargs) -> list[dict]:
        if "image_generation" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持图像生成 (image_generation)")
        model = (self.user_config.get("provider", {}) or {}).get("image_generation_model") or "dall-e-3"
        size = kwargs.get("size", "1024x1024")
        quality = kwargs.get("quality", "standard")
        n = kwargs.get("n", 1)

        # 尝试原生 images 端点
        try:
            response = self.client.images.generate(
                model=model, prompt=prompt, size=size, quality=quality, n=n,
            )
            results = []
            for img in response.data:
                results.append({
                    "url": getattr(img, "url", None),
                    "b64_json": getattr(img, "b64_json", None),
                    "revised_prompt": getattr(img, "revised_prompt", prompt),
                })
            return results
        except Exception:
            pass  # 降级到 chat completions

        # 降级: chat completions (适配非标准图像生成模型)
        msg = self._chat_completion(
            [{"role": "user", "content": prompt}], model
        )
        content = msg.content or ""
        results = self._parse_images_from_chat(content, prompt)
        if results:
            return results
        # 纯文本响应：将内容作为 revised_prompt 返回
        return [{"url": None, "b64_json": None, "revised_prompt": content.strip()}]

    def generate_speech(self, text: str, **kwargs) -> str:
        if "speech_generation" not in self.capabilities():
            raise NotImplementedError("当前 provider 不支持语音生成 (speech_generation)")
        import uuid
        model = (self.user_config.get("provider", {}) or {}).get("speech_generation_model") or "tts-1"
        voice = kwargs.get("voice", "alloy")
        fmt = kwargs.get("format", "mp3")
        speed = kwargs.get("speed", 1.0)
        output_dir = kwargs.get("output_dir", "")
        if not output_dir:
            raise ValueError("output_dir 不能为空")
        os.makedirs(output_dir, exist_ok=True)
        filename = kwargs.get("filename", f"speech_{uuid.uuid4().hex[:8]}.{fmt}")
        filepath = os.path.join(output_dir, filename)

        # 尝试原生 TTS 端点
        try:
            response = self.client.audio.speech.create(
                model=model, voice=voice, input=text,
                speed=speed, response_format=fmt,
            )
            response.stream_to_file(filepath)
            return filepath
        except Exception:
            pass  # 降级到 chat completions

        # 降级: chat completions (适配 MiMo/kokoro 等非标准 TTS 模型)
        msg = self._chat_completion(
            [{"role": "user", "content": text}], model
        )
        content = msg.content or ""
        audio_data, detected_fmt = self._extract_audio_from_message(msg, content)
        if audio_data:
            if detected_fmt and detected_fmt != fmt:
                filepath = filepath.replace(f".{fmt}", f".{detected_fmt}")
            with open(filepath, "wb") as f:
                f.write(audio_data)
            return filepath
        # 无法解析音频数据，保存完整 message 信息供排查
        import json as _json
        debug_info = {
            "content": content[:500],
            "content_len": len(content),
            "msg_type": type(msg).__name__,
        }
        # 抓取 msg.audio 的实际值和类型
        for attr in ("audio", "audio_data", "output_audio"):
            val = getattr(msg, attr, None)
            if val is not None:
                if hasattr(val, "data"):
                    debug_info[f"{attr}.type"] = type(val).__name__
                    debug_info[f"{attr}.id"] = getattr(val, "id", None)
                    debug_info[f"{attr}.data_head"] = str(getattr(val, "data", ""))[:200] if getattr(val, "data", None) else None
                    debug_info[f"{attr}.transcript"] = str(getattr(val, "transcript", ""))[:200] or None
                    debug_info[f"{attr}.format"] = getattr(val, "format", None)
                    debug_info[f"{attr}.attrs"] = [a for a in dir(val) if not a.startswith("_")]
                elif isinstance(val, dict):
                    debug_info[attr] = {k: str(v)[:200] for k, v in val.items()}
                else:
                    debug_info[attr] = str(val)[:500]
        try:
            extra = getattr(msg, "model_extra", None)
            if extra:
                debug_info["model_extra_keys"] = list(extra.keys()) if isinstance(extra, dict) else str(type(extra))
        except Exception:
            pass
        txt_path = filepath.replace(f".{fmt}", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(_json.dumps(debug_info, ensure_ascii=False, indent=2))
        raise RuntimeError(
            f"语音生成失败: 原生 TTS 端点不可用，chat 降级返回非音频数据，调试信息已保存至 {txt_path}"
        )

    def respond(
        self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None
    ) -> ProviderResponse:
        """处理 respond 相关逻辑。"""
        if self._use_responses and self._responses_available is not False:
            try:
                return self._respond_via_responses(messages, tools, model)
            except _ResponsesNotSupported:
                self._responses_available = False
                # 回退到 Chat Completions
        return self._respond_via_chat(messages, tools, model)

    def respond_stream(
        self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None
    ) -> Generator[dict, None, None]:
        """处理 respond_stream 相关逻辑。"""
        if self._use_responses and self._responses_available is not False:
            try:
                yield from self._respond_stream_via_responses(messages, tools, model)
                return
            except _ResponsesNotSupported:
                self._responses_available = False
        yield from self._respond_stream_via_chat(messages, tools, model)

    # ── Responses API 路径 ──

    def _respond_via_responses(
        self, messages: list[dict], tools: list[dict] | None, model: str | None = None
    ) -> ProviderResponse:
        """执行 respond_via_responses 内部辅助逻辑。"""
        instructions, inp = _to_responses_input(messages)
        effective_model = model or self.model
        resp_tools = _to_responses_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": effective_model,
            "input": inp,
            "stream": False,
            "timeout": self.timeout,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if resp_tools:
            kwargs["tools"] = resp_tools
        if self.think:
            kwargs["reasoning"] = {"effort": "high"}

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self.client.responses.create(**kwargs)
                break
            except APIError as e:
                if _is_not_supported(e):
                    raise _ResponsesNotSupported from e
                raise RuntimeError(f"Responses API 错误: {e}") from e
            except (APITimeoutError, APIConnectionError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e

        self.last_usage = _extract_responses_usage(resp)
        result = _from_responses_output(resp)
        self.last_response = result
        return result

    def _respond_stream_via_responses(
        self, messages: list[dict], tools: list[dict] | None, model: str | None = None
    ) -> Generator[dict, None, None]:
        """执行 respond_stream_via_responses 内部辅助逻辑。"""
        instructions, inp = _to_responses_input(messages)
        effective_model = model or self.model
        resp_tools = _to_responses_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": effective_model,
            "input": inp,
            "stream": True,
            "timeout": self.timeout,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if resp_tools:
            kwargs["tools"] = resp_tools
        if self.think:
            kwargs["reasoning"] = {"effort": "high"}

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                stream = self.client.responses.create(**kwargs)
                break
            except APIError as e:
                if _is_not_supported(e):
                    raise _ResponsesNotSupported from e
                raise RuntimeError(f"Responses API 错误: {e}") from e
            except (APITimeoutError, APIConnectionError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls_acc: dict[str, dict] = {}  # call_id → {name, arguments}
        usage = None

        for event in stream:
            etype = getattr(event, "type", "")

            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    text_parts.append(delta)
                    yield {"type": "text_chunk", "content": delta}

            elif etype == "response.reasoning_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    thinking_parts.append(delta)
                    yield {"type": "thinking_chunk", "content": delta}

            elif etype == "response.function_call_arguments.delta":
                delta = getattr(event, "delta", "") or ""
                call_id = getattr(event, "call_id", "")
                if call_id not in tool_calls_acc:
                    tool_calls_acc[call_id] = {"name": getattr(event, "name", ""), "arguments": ""}
                tool_calls_acc[call_id]["arguments"] += delta

            elif etype == "response.completed":
                resp = getattr(event, "response", None)
                if resp and hasattr(resp, "usage"):
                    self.last_usage = _extract_responses_usage(resp)

        self.last_response = ProviderResponse(
            text="".join(text_parts),
            reasoning="".join(thinking_parts),
            tool_calls=[
                ToolCall(id=cid, name=info["name"], input=_safe_json_parse(info["arguments"]))
                for cid, info in tool_calls_acc.items()
            ],
        )

    # ── Chat Completions 回退路径 ──

    def _respond_via_chat(
        self, messages: list[dict], tools: list[dict] | None, model: str | None = None
    ) -> ProviderResponse:
        """执行 respond_via_chat 内部辅助逻辑。"""
        from provider.openai_api import DeepSeekProvider
        # 传递用户的真实 provider 配置，避免丢失 api_key/base_url
        p = DeepSeekProvider(self._user_config, {})
        p.client = self.client
        p.model = self.model
        p.think = self.think
        p.stream = False
        p.timeout = self.timeout
        p.last_usage = None
        p.last_response = None
        return p.respond(messages, tools, model)

    def _respond_stream_via_chat(
        self, messages: list[dict], tools: list[dict] | None, model: str | None = None
    ) -> Generator[dict, None, None]:
        """执行 respond_stream_via_chat 内部辅助逻辑。"""
        effective_model = model or self.model
        from provider.openai_api import DeepSeekProvider
        # 传递用户的真实 provider 配置，避免丢失 api_key/base_url
        p = DeepSeekProvider(self._user_config, {})
        p.client = self.client
        p.model = self.model
        p.think = self.think
        p.stream = True
        p.timeout = self.timeout
        p.last_usage = None
        p.last_response = None

        # 调用 stream 方法
        kwargs = {
            "model": effective_model,
            "messages": messages,
            "stream": True,
            "timeout": self.timeout,
        }
        if self.think:
            kwargs["reasoning_effort"] = "high"
        else:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        if tools:
            kwargs["tools"] = tools

        response = p.client.chat.completions.create(**kwargs)
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None

        from provider.openai_api import _extract_usage
        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = _extract_usage(chunk)
                p.last_usage = usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_parts.append(delta.reasoning_content)
                yield {"type": "thinking_chunk", "content": delta.reasoning_content}
            if delta.content:
                content_parts.append(delta.content)
                yield {"type": "text_chunk", "content": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {"id": tc.id or "", "function": {"name": "", "arguments": ""}}
                    if tc.id:
                        tool_calls_map[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_map[idx]["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_map[idx]["function"]["arguments"] += tc.function.arguments

        if usage:
            p.last_usage = usage

        from openai.types.chat import ChatCompletionMessage
        from provider.openai_api import _to_provider_response
        content = "".join(content_parts)
        tool_calls = None
        if tool_calls_map:
            from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
            tool_calls = []
            for idx in sorted(tool_calls_map):
                tc = tool_calls_map[idx]
                tool_calls.append(ChatCompletionMessageToolCall(
                    id=tc["id"], type="function",
                    function={"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]},
                ))
        reasoning = "".join(reasoning_parts) if reasoning_parts else ""
        msg = ChatCompletionMessage(role="assistant", content=content or None, tool_calls=tool_calls)
        if reasoning:
            msg.reasoning_content = reasoning

        result = _to_provider_response(msg)
        p.last_response = result
        self.last_response = result
        self.last_usage = p.last_usage


# ── 格式转换 ──

def _to_responses_user_content(content: Any):
    """Convert internal user content, including OpenAI multimodal blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")

    parts: list[dict] = []
    for part in content:
        if not isinstance(part, dict):
            parts.append({"type": "input_text", "text": str(part)})
            continue

        ptype = part.get("type")
        if ptype == "text":
            parts.append({"type": "input_text", "text": str(part.get("text", ""))})
        elif ptype == "image_url":
            image_url = part.get("image_url", {})
            url = image_url.get("url", "") if isinstance(image_url, dict) else str(image_url or "")
            parts.append({"type": "input_image", "image_url": url})
        elif ptype in ("input_text", "input_image"):
            parts.append(part)
        else:
            parts.append({"type": "input_text", "text": json.dumps(part, ensure_ascii=False)})
    return parts


def _to_responses_input(messages: list[dict]) -> tuple[str, list[dict]]:
    """内部 dict 格式 → Responses API input + instructions"""
    instructions = ""
    items: list[dict] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            instructions += content + "\n"
            continue
        if role == "user":
            items.append({"role": "user", "content": _to_responses_user_content(content)})
        elif role == "assistant":
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    args = tc.get("function", {}).get("arguments", "{}")
                    items.append({
                        "type": "function_call",
                        "call_id": tc["id"],
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": args,
                    })
            elif content:
                items.append({"role": "assistant", "content": content})
        elif role == "tool":
            items.append({
                "type": "function_call_output",
                "call_id": msg.get("tool_call_id", ""),
                "output": str(content),
            })
    return instructions.strip(), items


def _to_responses_tools(tools: list[dict]) -> list[dict]:
    """Chat Completions tool schema → Responses API tool schema (扁平格式)"""
    result = []
    for t in tools:
        func = t.get("function", {})
        item = {
            "type": "function",
            "name": func.get("name", ""),
            "parameters": func.get("parameters", {"type": "object", "properties": {}}),
        }
        if "description" in func:
            item["description"] = func["description"]
        result.append(item)
    return result


def _from_responses_output(response) -> ProviderResponse:
    """Responses API 响应 → ProviderResponse"""
    text = ""
    reasoning = ""
    tool_calls: list[ToolCall] = []

    for item in getattr(response, "output", []):
        itype = getattr(item, "type", "")
        if itype == "message":
            for c in getattr(item, "content", []):
                if getattr(c, "type", "") == "output_text":
                    text += getattr(c, "text", "") or ""
        elif itype == "reasoning":
            for c in getattr(item, "content", []):
                if getattr(c, "type", "") == "reasoning_text":
                    reasoning += getattr(c, "text", "") or ""
        elif itype == "function_call":
            tool_calls.append(ToolCall(
                id=getattr(item, "call_id", ""),
                name=getattr(item, "name", ""),
                input=_safe_json_parse(getattr(item, "arguments", "{}")),
            ))

    return ProviderResponse(
        text=text,
        reasoning=reasoning,
        tool_calls=tool_calls,
    )


def _extract_responses_usage(response) -> dict | None:
    """从 Responses API 响应提取 token 用量"""
    try:
        u = response.usage
        if not u:
            return None
        return {
            "prompt_tokens": u.input_tokens or 0,
            "completion_tokens": u.output_tokens or 0,
            "total_tokens": u.total_tokens or 0,
            "cached_tokens": getattr(u, "input_tokens_details", {}).get("cached_tokens", 0) or 0,
        }
    except Exception:
        return None


# ── 辅助 ──

class _ResponsesNotSupported(Exception):
    """端点不支持 Responses API 时抛出"""
    pass


def _is_not_supported(error: APIError) -> bool:
    """判断是否是不支持 Responses API 的错误 (404/405)"""
    status = getattr(error, "status_code", 0) or getattr(error, "status", 0)
    if status in (404, 405):
        return True
    msg = str(error).lower()
    return any(kw in msg for kw in ["not found", "not supported", "unknown endpoint", "unrecognized"])


def _safe_json_parse(s: str) -> dict:
    """执行 safe_json_parse 内部辅助逻辑。"""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}
