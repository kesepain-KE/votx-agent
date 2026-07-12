"""工具执行 - 注册 / 权限 / 限流 / 日志"""
import json
import contextvars
import queue as _queue
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, TYPE_CHECKING

from plugins._common import err, log_tool_call, reset_current_user_dir, set_current_user_dir
from skills._common import (
    reset_current_user_dir as sc_reset_current_user_dir,
    set_current_user_dir as sc_set_current_user_dir,
)

if TYPE_CHECKING:
    from provider.schema import ProviderResponse

# 全局工具注册表  {name: (schema, handler)}
TOOL_REGISTRY: dict[str, Any] = {}


class ToolExecutionCancelled(RuntimeError):
    """Raised when the current tool run is cancelled by the user."""


# ---- 工具中间事件流式推送 ----

# tool_call_id -> Queue，用于工具在子线程中推送中间事件
_tool_event_queues: dict[str, _queue.Queue] = {}

# 当前正在执行的 tool_call_id（ContextVar，供工具 handler 读取自己的 ID）
current_tool_call_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_tool_call_id", default=""
)


def register_tool_event_queue(tool_call_id: str) -> _queue.Queue:
    """为指定 tool_call 注册事件队列，返回队列引用"""
    q = _queue.Queue()
    _tool_event_queues[tool_call_id] = q
    return q


def get_tool_event_queue(tool_call_id: str) -> _queue.Queue | None:
    """获取指定 tool_call 的事件队列（供工具 handler 使用）"""
    return _tool_event_queues.get(tool_call_id)


def unregister_tool_event_queue(tool_call_id: str):
    """工具执行完毕后清理队列"""
    _tool_event_queues.pop(tool_call_id, None)


def register_tool(schema: dict, handler, meta: dict = None):
    """注册工具到全局表"""
    name = schema["function"]["name"]
    TOOL_REGISTRY[name] = (schema, handler, meta or {})


def _normalize_skill_key(name: str) -> str:
    return str(name).lower().replace("-", "_")


def _positive_int(value) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def load_tool_schemas(disabled_skills: set | None = None) -> list[dict[str, Any]]:
    """返回排序后的 schema 列表，可选按 disabled_skills 过滤工具。

    Args:
        disabled_skills: 被禁用的技能名集合（标准化后的 skill_key），
                         为 None 时不过滤（向后兼容）。
    """
    items = sorted(TOOL_REGISTRY.values(), key=lambda x: x[0]["function"]["name"])
    schemas = [s for s, *_ in items]  # 取第一个元素（schema），兼容二元组和三元组
    if disabled_skills:
        from skills import get_tool_skill_map
        tsm = get_tool_skill_map()
        disabled_keys = {_normalize_skill_key(d) for d in disabled_skills}
        schemas = [s for s in schemas
                   if tsm.get(s["function"]["name"], "") not in disabled_keys]
    return schemas


def clear_tool_registry():
    """清空全局工具注册表（reload 前调用）"""
    TOOL_REGISTRY.clear()


def get_tool_registry_snapshot() -> dict[str, Any]:
    """返回当前注册表的浅拷贝"""
    return dict(TOOL_REGISTRY)


class ToolRunner:
    """工具执行器 — 权限校验 / 限流 / 日志"""

    def __init__(self, core_config: dict[str, Any], user_config: dict[str, Any] = None, user_dir: str | None = None, disabled_skills: set | None = None):
        """执行 init 内部辅助逻辑。"""
        tool_cfg = core_config.get("tool", {})
        self.max_total = tool_cfg.get("tool_max_per_type", 0)     # 0 = 不限制
        self.max_per_tool = tool_cfg.get("tool_max_per_tool", 0)  # 0 = 不限制
        self.call_count = 0
        self.per_tool_count: dict[str, int] = {}
        self.user_dir = user_dir
        self._disabled_skills = {_normalize_skill_key(d) for d in (disabled_skills or set())}

        # 工具执行超时，优先级：user_config.tool.tool_timeout > core_config.tool.tool_timeout > 工具运行器默认值
        user_tool_cfg = (user_config or {}).get("tool", {})
        self.tool_timeout = (
            _positive_int(user_tool_cfg.get("tool_timeout"))
            or _positive_int(tool_cfg.get("tool_timeout"))
            or 300
        )

        # 权限：从用户配置读取（deny 优先）
        ucfg = (user_config or {}).get("tool", {})
        core_enabled = tool_cfg.get("enabled", {})
        user_enabled = ucfg.get("enabled", {})
        user_deny = ucfg.get("deny", [])
        self._enabled = {**core_enabled, **user_enabled}
        self._deny = set(user_deny)

    # ---- 限流 ----

    def _check_limit(self, name: str) -> str | None:
        """返回错误字符串或 None。仅保留配置级权限检查，移除硬编码限流。"""
        if name in self._deny:
            return err(f"工具 {name} 已被管理员禁用")
        enabled = self._enabled.get(name)
        if enabled is False:
            return err(f"工具 {name} 未启用（配置关闭）")
        # 检查技能级禁用（双重保险：即使 schema 没过滤掉，执行层也拦截）
        if self._disabled_skills:
            from skills import get_tool_skill_map
            tsm = get_tool_skill_map()
            skill_key = tsm.get(name, "")
            if skill_key and skill_key in self._disabled_skills:
                return err(f"工具 {name} 所属技能已被用户禁用")
        return None

    def _count(self, name: str):
        """执行 count 内部辅助逻辑。"""
        self.call_count += 1
        self.per_tool_count[name] = self.per_tool_count.get(name, 0) + 1

    # ---- 工具调用 ----

    def has_tool_calls(self, response: Any) -> bool:
        """检查响应是否包含工具调用（适配 ProviderResponse 和旧 SDK 对象）"""
        if hasattr(response, "has_tool_calls"):
            return response.has_tool_calls
        return hasattr(response, "tool_calls") and bool(response.tool_calls)

    def execute(self, response: Any, cancel_event: threading.Event | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """执行所有 tool_calls，返回 (tool result 消息列表, 调用详情列表, 中间事件列表)"""
        results: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        all_intermediate_events: list[dict[str, Any]] = []
        ctx_token = set_current_user_dir(self.user_dir)
        sc_ctx_token = sc_set_current_user_dir(self.user_dir)
        try:
            for tc in response.tool_calls:
                if cancel_event and cancel_event.is_set():
                    raise ToolExecutionCancelled("tool run cancelled")
                # 适配 ProviderResponse.ToolCall (统一格式) 和旧 SDK 对象
                if hasattr(tc, "name"):
                    name = tc.name
                    args = tc.input
                    tc_id = tc.id
                else:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    tc_id = tc.id

                # 限流 / 权限
                limit_err = self._check_limit(name)
                if limit_err:
                    results.append(_tool_msg(tc_id, limit_err))
                    log_id = log_tool_call(name, {}, limit_err, False, 0, user_dir=self.user_dir, tool_call_id=tc_id)
                    details.append({"name": name, "args": {}, "elapsed": 0, "success": False, "log_id": log_id, "tool_call_id": tc_id})
                    continue

                # ── 中间事件流：注册队列 + 注入 tool_call_id 到 handler 上下文 ──
                event_q = register_tool_event_queue(tc_id) if tc_id else None
                tc_token = current_tool_call_id.set(tc_id) if tc_id else None
                intermediate_events: list[dict[str, Any]] = []

                try:
                    # 执行（带全局超时）
                    t0 = _time.perf_counter()
                    try:
                        if name in TOOL_REGISTRY:
                            entry = TOOL_REGISTRY[name]
                            handler = entry[1]  # handler 始终是第二个元素
                            meta = entry[2] if len(entry) > 2 else {}
                            timeout = None if meta.get("skip_tool_timeout") else self.tool_timeout
                            call_context = contextvars.copy_context()
                            executor = ThreadPoolExecutor(max_workers=1)
                            try:
                                future = executor.submit(call_context.run, handler, **args)
                                deadline = None if timeout is None else _time.perf_counter() + timeout
                                cancelled = False
                                while True:
                                    if cancel_event and cancel_event.is_set():
                                        cancelled = True
                                        future.cancel()
                                        output = err(f"停止 {name} 执行（用户取消）")
                                        success = False
                                        break

                                    if deadline is not None:
                                        remaining = deadline - _time.perf_counter()
                                        if remaining <= 0:
                                            future.cancel()
                                            output = err(f"工具 {name} 执行超时 ({self.tool_timeout}s)")
                                            success = False
                                            break
                                        wait_for = min(0.2, remaining)
                                    else:
                                        wait_for = 0.2

                                    try:
                                        result = future.result(timeout=wait_for)
                                        output = str(result)
                                        success = not output.startswith("ERROR:")
                                        break
                                    except FutureTimeoutError:
                                        # ── 收集中间事件 ──
                                        if event_q:
                                            while not event_q.empty():
                                                try:
                                                    intermediate_events.append(event_q.get_nowait())
                                                except _queue.Empty:
                                                    break
                                        continue

                                if cancelled:
                                    raise ToolExecutionCancelled("tool run cancelled")
                            finally:
                                if executor is not None:
                                    executor.shutdown(wait=False, cancel_futures=True)
                                    executor = None
                        else:
                            output = err(f"工具 {name} 未注册")
                            success = False
                    except ToolExecutionCancelled:
                        raise
                    except TypeError as e:
                        output = err(f"参数错误: {e}")
                        success = False
                    except Exception as e:
                        output = err(f"执行异常: {e}")
                        success = False
                    elapsed = _time.perf_counter() - t0
                finally:
                    # ── 中间事件流清理 ──
                    if tc_token is not None:
                        current_tool_call_id.reset(tc_token)
                    if event_q is not None:
                        unregister_tool_event_queue(tc_id)
                        for ev in intermediate_events:
                            ev.setdefault("tool_call_id", tc_id)
                        all_intermediate_events.extend(intermediate_events)

                self._count(name)
                results.append(_tool_msg(tc_id, output))
                log_id = log_tool_call(name, args, output, success, elapsed, user_dir=self.user_dir, tool_call_id=tc_id)
                details.append({"name": name, "args": args, "elapsed": elapsed, "success": success, "log_id": log_id, "tool_call_id": tc_id})
        finally:
            reset_current_user_dir(ctx_token)
            sc_reset_current_user_dir(sc_ctx_token)

        return results, details, all_intermediate_events

    def reset_count(self):
        """处理 reset_count 相关逻辑。"""
        self.call_count = 0
        self.per_tool_count.clear()


def _tool_msg(tool_call_id: str, content: str) -> dict:
    """执行 tool_msg 内部辅助逻辑。"""
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}
