"""工具执行 - 注册 / 权限 / 限流 / 日志"""
import json
import time as _time
from typing import Any

from skills._common import err, log_tool_call

# 全局工具注册表  {name: (schema, handler)}
TOOL_REGISTRY: dict[str, Any] = {}


def register_tool(schema: dict, handler):
    """注册工具到全局表"""
    TOOL_REGISTRY[schema["function"]["name"]] = (schema, handler)


def load_tool_schemas() -> list[dict[str, Any]]:
    """返回排序后的 schema 列表"""
    items = sorted(TOOL_REGISTRY.values(), key=lambda x: x[0]["function"]["name"])
    return [s for s, _ in items]


class ToolRunner:
    """工具执行器 — 权限校验 / 限流 / 日志"""

    def __init__(self, core_config: dict[str, Any], user_config: dict[str, Any] = None):
        tool_cfg = core_config.get("tool", {})
        self.max_total = tool_cfg.get("tool_max", 50)          # 单轮总上限
        self.max_per_tool = tool_cfg.get("tool_max_per_type", 10)  # 单工具上限
        self.call_count = 0
        self.per_tool_count: dict[str, int] = {}

        # 权限：从用户配置读取（deny 优先）
        ucfg = (user_config or {}).get("tool", {})
        core_enabled = tool_cfg.get("enabled", {})
        user_enabled = ucfg.get("enabled", {})
        user_deny = ucfg.get("deny", [])
        self._enabled = {**core_enabled, **user_enabled}
        self._deny = set(user_deny)

    # ---- 限流 ----

    def _check_limit(self, name: str) -> str | None:
        """返回错误字符串或 None"""
        if name in self._deny:
            return err(f"工具 {name} 已被管理员禁用")
        enabled = self._enabled.get(name)
        if enabled is False:
            return err(f"工具 {name} 未启用（配置关闭）")
        if self.call_count >= self.max_total:
            return err(f"全局调用上限已达 ({self.max_total})")
        pc = self.per_tool_count.get(name, 0)
        if pc >= self.max_per_tool:
            return err(f"工具 {name} 单轮调用上限已达 ({self.max_per_tool})")
        return None

    def _count(self, name: str):
        self.call_count += 1
        self.per_tool_count[name] = self.per_tool_count.get(name, 0) + 1

    # ---- 工具调用 ----

    def has_tool_calls(self, message: Any) -> bool:
        return hasattr(message, "tool_calls") and bool(message.tool_calls)

    def execute(self, message: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """执行所有 tool_calls，返回 (tool result 消息列表, 调用详情列表)"""
        results: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        for tc in message.tool_calls:
            name = tc.function.name

            # 限流 / 权限
            limit_err = self._check_limit(name)
            if limit_err:
                results.append(_tool_msg(tc.id, limit_err))
                details.append({"name": name, "args": {}, "elapsed": 0, "success": False})
                log_tool_call(name, {}, limit_err, False, 0)
                continue

            # 解析参数
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            # 执行
            t0 = _time.perf_counter()
            try:
                if name in TOOL_REGISTRY:
                    _, handler = TOOL_REGISTRY[name]
                    output = str(handler(**args))
                    success = not output.startswith("ERROR:")
                else:
                    output = err(f"工具 {name} 未注册")
                    success = False
            except TypeError as e:
                output = err(f"参数错误: {e}")
                success = False
            except Exception as e:
                output = err(f"执行异常: {e}")
                success = False
            elapsed = _time.perf_counter() - t0

            self._count(name)
            results.append(_tool_msg(tc.id, output))
            details.append({"name": name, "args": args, "elapsed": elapsed, "success": success})
            log_tool_call(name, args, output, success, elapsed)

        return results, details

    def reset_count(self):
        self.call_count = 0
        self.per_tool_count.clear()


def _tool_msg(tool_call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}
