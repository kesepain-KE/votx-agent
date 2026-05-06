"""统一数据结构 — Provider 层与 engine/tool/chat 层之间的接口约定"""

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """统一工具调用 — 所有 Provider adapter 的输出格式"""
    id: str
    name: str
    input: dict  # 已解析的 JSON 参数字典


@dataclass
class ProviderResponse:
    """统一 LLM 响应 — 所有 Provider 的 respond() 返回此类型"""
    text: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict | None = None
    finish_reason: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0
