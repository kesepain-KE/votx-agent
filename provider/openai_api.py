"""LLM Provider - OpenAI 兼容接口封装 (Chat Completions API)

支持 OpenAI 兼容 API (DeepSeek 等)，提供:
- 自动重试 (超时/连接错误，最多 2 次)
- 流式和非流式两种调用路径
- 多来源 API Key 加载 (用户配置 > DEEPSEEK_API_KEY > OPENAI_API_KEY)
- Token 用量统计 (含缓存命中)
- 思考模式 (reasoning_effort) 控制

实现 BaseProvider 接口，返回统一 ProviderResponse。
"""
import json
import os
import time as _time
from pathlib import Path
from typing import Any, Generator

# 修复 Windows SSL_CERT_FILE 指向不存在文件导致的 httpx 崩溃
# 某些 Python 发行版设置了无效的 SSL_CERT_FILE 环境变量，httpx 检测到后会崩溃
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError
from openai.types.chat import ChatCompletionMessage

from provider.base import BaseProvider
from provider.schema import ProviderResponse, ToolCall

# 加载 .env（不依赖 python-dotenv）
def _load_dotenv():
    """手动解析 .env 文件，写入 os.environ (不依赖 python-dotenv)"""
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

_OPENAI_VISION_KEYWORDS = [
    "gpt-5", "gpt-4.1", "gpt-4o", "gpt-4-vision", "gpt-4-turbo",
    "gemini", "gemma-3",
    "vision", "vl-", "-vl",
    "mimo", "minimax",
    "qwen-vl", "qwen2-vl", "qwen2.5-vl",
    "pixtral", "llama-3.2-vision", "llama-v",
]


def _supports_vision_model(model: str) -> bool:
    return any(kw in model.lower() for kw in _OPENAI_VISION_KEYWORDS)


# 非标准 TTS 模型的 voice 映射表
# key: 模型名关键词, value: {openai_voice: actual_voice_id}
_TTS_VOICE_MAP = {
    "kokoro": {
        "alloy": "af_bella",
        "echo": "am_adam",
        "fable": "bf_emma",
        "nova": "zf_xiaobei",
        "onyx": "am_michael",
        "shimmer": "af_sarah",
    },
}


def _resolve_tts_voice(model: str, openai_voice: str) -> str:
    """根据 TTS 模型，将 OpenAI 标准 voice 名映射为模型实际接受的 voice ID。
    未匹配时返回原 voice 值。
    """
    model_lower = model.lower()
    for keyword, mapping in _TTS_VOICE_MAP.items():
        if keyword in model_lower:
            return mapping.get(openai_voice, openai_voice)
    return openai_voice


class DeepSeekProvider(BaseProvider):
    """LLM Provider - 支持 OpenAI 兼容接口 (Chat Completions API)"""

    def __init__(self, user_config: dict, core_config: dict | None = None):
        """执行 init 内部辅助逻辑。"""
        core = core_config or {}
        cfg = user_config.get("provider", {})
        # API Key: config > DEEPSEEK_API_KEY > OPENAI_API_KEY
        api_key = (
            cfg.get("api_key", "").strip()
            or os.environ.get("DEEPSEEK_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        if not api_key:
            raise ValueError(
                "API Key 未设置。请通过以下方式之一提供:\n"
                "  1. 创建 .env 文件，写入 DEEPSEEK_API_KEY=sk-xxx\n"
                "  2. 设置环境变量: export DEEPSEEK_API_KEY=sk-xxx\n"
                "  3. 在 users/<name>/config.json 的 provider.api_key 中填写"
            )
        # base_url: config > DEEPSEEK_BASE_URL 环境变量 > DeepSeek 默认
        base_url = (
            cfg.get("base_url", "").strip()
            or os.environ.get("DEEPSEEK_BASE_URL", "")
            or "https://api.deepseek.com"
        )
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = cfg.get("model", "deepseek-v4-flash")
        self.base_url = base_url
        self.think = cfg.get("think", False)
        # stream: 用户配置 > 全局配置 > False
        self.stream = cfg.get("stream", core.get("output", {}).get("stream", False))
        self.timeout = cfg.get("timeout", 120)
        self.user_config = user_config
        self.vision_model = cfg.get("vision_model", "")
        self.last_usage: dict | None = None
        self.last_response: ProviderResponse | None = None

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
        import base64 as _b64, re as _re

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
            data = json.loads(content)
            fmt = data.get("format", "mp3")
            for k in ("audio", "data", "b64_json", "audio_data"):
                if k in data and isinstance(data[k], str):
                    return _b64.b64decode(data[k]), data.get("format", fmt)
        except (json.JSONDecodeError, Exception):
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
        if not content:
            return []
        content = content.strip()
        results: list[dict] = []
        # JSON: {"images": [...], "data": [...]}
        try:
            data = json.loads(content)
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
        except (json.JSONDecodeError, Exception):
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
                    segs = [{"start": s.start, "end": s.end, "text": s.text}
                            for s in transcription.segments]
                    return f"{text}\n\n--- 时间戳 ---\n{json.dumps(segs, ensure_ascii=False, indent=2)}"
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
            resolved_voice = _resolve_tts_voice(model, voice)
            response = self.client.audio.speech.create(
                model=model, voice=resolved_voice, input=text,
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
            f.write(json.dumps(debug_info, ensure_ascii=False, indent=2))
        raise RuntimeError(
            f"语音生成失败: 原生 TTS 端点不可用，chat 降级返回非音频数据，调试信息已保存至 {txt_path}"
        )

    def respond(
        self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None
    ) -> ProviderResponse:
        """发送消息，支持超时 + 重试。返回统一 ProviderResponse。

        重试策略:
        - APITimeoutError / APIConnectionError: 指数退避重试 (1s, 2s)
        - APIError (4xx/5xx): 直接抛出，不重试 (避免重复扣费)
        """
        effective_model = model or self.model
        kwargs: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "stream": self.stream,
            "timeout": self.timeout,
        }
        if self.think:
            kwargs["reasoning_effort"] = "high"
        else:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        if tools:
            kwargs["tools"] = tools

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except (APITimeoutError, APIConnectionError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e
            except APIError as e:
                raise RuntimeError(f"API 错误: {e}") from e

        if self.stream:
            msg, usage = self._collect_stream(response)
            self.last_usage = usage
        else:
            self.last_usage = _extract_usage(response)
            msg = response.choices[0].message
            reasoning = ""
            try:
                reasoning = getattr(msg, "reasoning_content", "") or ""
            except Exception:
                pass
            if not reasoning and hasattr(msg, "model_extra"):
                reasoning = msg.model_extra.get("reasoning_content", "") or ""
            if reasoning and not getattr(msg, "reasoning_content", None):
                msg.reasoning_content = reasoning  # type: ignore[attr-defined]

        result = _to_provider_response(msg)
        self.last_response = result
        return result

    def respond_stream(
        self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None
    ) -> Generator[dict, None, None]:
        """流式 LLM 调用 — 逐 chunk yield，完成后 self.last_response 可用。

        用法:
            for event in provider.respond_stream(messages, tools):
                if event["type"] == "thinking_chunk":  ...
                if event["type"] == "text_chunk":       ...
            response = provider.last_response  # ProviderResponse
            usage = provider.last_usage
        """
        effective_model = model or self.model
        kwargs: dict[str, Any] = {
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

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except (APITimeoutError, APIConnectionError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e
            except APIError as e:
                raise RuntimeError(f"API 错误: {e}") from e

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None

        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = _extract_usage(chunk)
                self.last_usage = usage
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
                        tool_calls_map[idx] = {
                            "id": tc.id or "",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.id:
                        tool_calls_map[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_map[idx]["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_map[idx]["function"]["arguments"] += tc.function.arguments

        if usage:
            self.last_usage = usage

        content = "".join(content_parts)
        tool_calls = None
        if tool_calls_map:
            from openai.types.chat.chat_completion_message_tool_call import (
                ChatCompletionMessageToolCall,
            )
            tool_calls = []
            for idx in sorted(tool_calls_map):
                tc = tool_calls_map[idx]
                tool_calls.append(ChatCompletionMessageToolCall(
                    id=tc["id"],
                    type="function",
                    function={
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                ))
        reasoning = "".join(reasoning_parts) if reasoning_parts else ""
        msg = ChatCompletionMessage(
            role="assistant", content=content or None, tool_calls=tool_calls
        )
        if reasoning:
            msg.reasoning_content = reasoning  # type: ignore[attr-defined]

        result = _to_provider_response(msg)
        self.last_response = result
        return result

    def _collect_stream(self, response) -> tuple[ChatCompletionMessage, dict | None]:
        """收集流式 chunk 拼接为完整 Message，同时提取 usage 和 reasoning"""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None
        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = _extract_usage(chunk)
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_parts.append(delta.reasoning_content)
            if delta.content:
                content_parts.append(delta.content)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {
                            "id": tc.id or "",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.id:
                        tool_calls_map[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_map[idx]["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_map[idx]["function"]["arguments"] += tc.function.arguments

        content = "".join(content_parts)
        tool_calls = None
        if tool_calls_map:
            from openai.types.chat.chat_completion_message_tool_call import (
                ChatCompletionMessageToolCall,
            )
            tool_calls = []
            for idx in sorted(tool_calls_map):
                tc = tool_calls_map[idx]
                tool_calls.append(ChatCompletionMessageToolCall(
                    id=tc["id"],
                    type="function",
                    function={
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                ))
        reasoning = "".join(reasoning_parts) if reasoning_parts else ""
        msg = ChatCompletionMessage(
            role="assistant", content=content or None, tool_calls=tool_calls
        )
        if reasoning:
            msg.reasoning_content = reasoning  # type: ignore[attr-defined]
        return msg, usage


def _to_provider_response(msg: ChatCompletionMessage) -> ProviderResponse:
    """将 ChatCompletionMessage 转为统一 ProviderResponse"""
    tool_calls = []
    if msg.tool_calls:
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))
    reasoning = ""
    try:
        reasoning = getattr(msg, "reasoning_content", "") or ""
    except Exception:
        pass
    if not reasoning and hasattr(msg, "model_extra"):
        reasoning = (msg.model_extra or {}).get("reasoning_content", "") or ""
    finish_reason = ""
    return ProviderResponse(
        text=msg.content or "",
        reasoning=reasoning,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
    )


def _extract_usage(response) -> dict | None:
    """从 API 响应提取 token 用量，含缓存命中信息"""
    try:
        u = response.usage
        if u is None:
            return None
        info = {
            "prompt_tokens": u.prompt_tokens or 0,
            "completion_tokens": u.completion_tokens or 0,
            "total_tokens": u.total_tokens or 0,
        }
        # prompt 缓存命中量（DeepSeek 的 prompt_tokens_details.cached_tokens）
        cached = 0
        if hasattr(u, "prompt_tokens_details") and u.prompt_tokens_details:
            cached = getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0
        info["cached_tokens"] = cached
        return info
    except Exception:
        return None