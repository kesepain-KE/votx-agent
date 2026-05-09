"""测试 run/chat.py 的 tool_calls 链完整性保护。

覆盖场景:
  - _repair_tool_chain: 缺 tool 消息切除 / 部分结果切除 / ID 不匹配切除 / 正常链保留
  - _close_tool_chain: 末尾未闭合 tool_calls 自动补 ERROR
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# 确保能导入 run.chat
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from run.chat import ChatManager


def _make_chat() -> ChatManager:
    """创建一个最小 ChatManager 实例用于测试。"""
    core_config = {"history": {"history_max": 100, "zip_history": False}}
    user_config = {}
    with tempfile.TemporaryDirectory() as td:
        return ChatManager(td, core_config, user_config)


def _tool_call(id_: str, name: str, args: str = "{}"):
    """构建一个 tool_call dict"""
    return {
        "id": id_,
        "type": "function",
        "function": {"name": name, "arguments": args},
    }


def _tool_result(id_: str, content: str = "OK"):
    """构建一个 tool result dict"""
    return {"role": "tool", "tool_call_id": id_, "content": content}


def _assistant_with_tool_calls(*tcs):
    """构建含 tool_calls 的 assistant 消息"""
    return {"role": "assistant", "content": None, "tool_calls": list(tcs)}


# ── _repair_tool_chain ──────────────────────────────────────────

def test_normal_chain_preserved():
    """正常 tool_calls → tool results 链不应被修改"""
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        _assistant_with_tool_calls(_tool_call("c1", "get_time")),
        _tool_result("c1", "OK: 12:00"),
        {"role": "assistant", "content": "现在是12点"},
        {"role": "user", "content": "thanks"},
    ]
    original = list(chat.messages)
    chat._repair_tool_chain()
    assert len(chat.messages) == len(original), (
        f"正常链不应被修改: 原 {len(original)} → 现 {len(chat.messages)}"
    )


def test_missing_tool_removes_from_assistant():
    """tool_calls 后完全没有 tool 消息 → 切除该 assistant 及之后"""
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "好的"},
        _assistant_with_tool_calls(_tool_call("c1", "get_time")),
        # 缺少 tool result — 链断了
    ]
    chat._repair_tool_chain()
    assert len(chat.messages) == 2, f"应切除断链 assistant，剩 2 条，实际 {len(chat.messages)}"
    assert chat.messages[-1]["role"] == "assistant"
    assert chat.messages[-1]["content"] == "好的"


def test_partial_tool_results_removes_from_assistant():
    """2 个 tool_calls 但只有 1 个 tool result → 切除"""
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        _assistant_with_tool_calls(
            _tool_call("c1", "get_time"),
            _tool_call("c2", "read_file"),
        ),
        _tool_result("c1", "OK"),  # 只有 1 个，c2 缺失
    ]
    chat._repair_tool_chain()
    assert len(chat.messages) == 1, f"应切到 user，剩 1 条，实际 {len(chat.messages)}"
    assert chat.messages[0]["role"] == "user"


def test_tool_call_id_mismatch_removes():
    """tool result 的 ID 与 tool_call 不匹配 → 切除"""
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        _assistant_with_tool_calls(_tool_call("c1", "get_time")),
        _tool_result("c2", "OK"),  # ID 不匹配
    ]
    chat._repair_tool_chain()
    assert len(chat.messages) == 1, f"ID 不匹配应切除，剩 1 条，实际 {len(chat.messages)}"


def test_tool_before_assistant_removes():
    """tool 消息出现在其匹配 assistant(tool_calls) 之前 → 从 tool 处切除

    这种乱序常见于 _trim_if_needed 大量裁剪后，剩余消息以 tool 开头。
    修复前 _repair_tool_chain 只检查 ID 是否存在于 valid_ids，
    不检查 tool 是否在 assistant 之后，导致乱序放过，API 返回 400。
    """
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        _tool_result("c1", "OK"),  # 在匹配的 assistant 之前！
        _assistant_with_tool_calls(_tool_call("c1", "get_time")),
    ]
    chat._repair_tool_chain()
    # tool(c1) 在 assistant(tc=[c1]) 之前 → 从 tool 处切除，只剩 user
    assert len(chat.messages) == 1, (
        f"tool 出现在 assistant 之前应切除，剩 1 条(user)，实际 {len(chat.messages)}"
    )
    assert chat.messages[0]["role"] == "user"


def test_multi_tool_normal_chain_preserved():
    """多个 tool_calls 全部匹配 → 保留"""
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        _assistant_with_tool_calls(
            _tool_call("c1", "get_time"),
            _tool_call("c2", "read_file"),
            _tool_call("c3", "mem_recall"),
        ),
        _tool_result("c1", "12:00"),
        _tool_result("c2", "content"),
        _tool_result("c3", "memory"),
        {"role": "assistant", "content": "done"},
    ]
    original_len = len(chat.messages)
    chat._repair_tool_chain()
    assert len(chat.messages) == original_len, f"多 tool 正常链不应被修改"


# ── _close_tool_chain ───────────────────────────────────────────

def test_close_chain_on_unclosed_tool_calls():
    """末尾是未闭合 assistant(tool_calls) → 补 ERROR tool 消息"""
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        _assistant_with_tool_calls(
            _tool_call("c1", "get_time"),
            _tool_call("c2", "read_file"),
        ),
    ]
    chat._close_tool_chain()
    # 应该追加了 2 条 tool 消息
    assert len(chat.messages) == 4, f"应补 2 条 ERROR tool，共 4 条，实际 {len(chat.messages)}"
    assert chat.messages[2]["role"] == "tool"
    assert chat.messages[2]["tool_call_id"] == "c1"
    assert "ERROR" in chat.messages[2]["content"]
    assert chat.messages[3]["role"] == "tool"
    assert chat.messages[3]["tool_call_id"] == "c2"


def test_close_chain_no_op_on_normal_end():
    """末尾是普通 assistant 消息 → 不修改"""
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    original = list(chat.messages)
    chat._close_tool_chain()
    assert chat.messages == original, "正常结尾不应被修改"


def test_close_chain_no_op_on_completed_tool_round():
    """tool_calls 后已有 tool 结果 → 不修改"""
    chat = _make_chat()
    chat.messages = [
        {"role": "user", "content": "hi"},
        _assistant_with_tool_calls(_tool_call("c1", "get_time")),
        _tool_result("c1", "12:00"),
    ]
    original = list(chat.messages)
    chat._close_tool_chain()
    assert chat.messages == original, "已完成链不应被修改"


def test_close_chain_no_op_on_empty():
    """空消息列表 → 不报错"""
    chat = _make_chat()
    chat._close_tool_chain()
    assert chat.messages == []


# ── 集成: 完整 save/load 周期 ────────────────────────────────────

def test_save_load_roundtrip_with_unclosed_chain():
    """save → load 后，未闭合链被修复，消息可正常构建"""
    with tempfile.TemporaryDirectory() as td:
        core_config = {"history": {"history_max": 100, "zip_history": False}}
        user_config = {}
        chat = ChatManager(td, core_config, user_config)
        chat.set_system_prompt("test system")

        # 模拟 Ctrl+C 中断后的状态：2 个 tool_calls 未闭合
        chat.messages = [
            {"role": "user", "content": "hi"},
            _assistant_with_tool_calls(
                _tool_call("c1", "get_time"),
                _tool_call("c2", "read_file"),
            ),
        ]

        # save — _close_tool_chain 自动闭合，补 2 条 ERROR tool
        chat.save_history()

        # load — _repair_tool_chain 不应再切除（因为已闭合）
        chat2 = ChatManager(td, core_config, user_config)
        chat2.load_history()

        # 消息: user + assistant(tool_calls) + tool(c1) + tool(c2) = 4
        assert len(chat2.messages) == 4, f"闭合后应有 4 条消息，实际 {len(chat2.messages)}"
        assert chat2.messages[2]["role"] == "tool"
        assert chat2.messages[3]["role"] == "tool"
        assert "ERROR" in chat2.messages[2]["content"]
        assert "ERROR" in chat2.messages[3]["content"]


def test_save_load_roundtrip_normal():
    """正常对话 save → load 往返不变"""
    with tempfile.TemporaryDirectory() as td:
        core_config = {"history": {"history_max": 100, "zip_history": False}}
        user_config = {}
        chat = ChatManager(td, core_config, user_config)

        chat.messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "what time"},
            _assistant_with_tool_calls(_tool_call("c1", "get_time")),
            _tool_result("c1", "12:00"),
            {"role": "assistant", "content": "现在是12点"},
        ]

        chat.save_history()

        chat2 = ChatManager(td, core_config, user_config)
        chat2.load_history()
        assert len(chat2.messages) == len(chat.messages)
        for i, (a, b) in enumerate(zip(chat.messages, chat2.messages)):
            assert a == b, f"消息 {i} 不匹配"
