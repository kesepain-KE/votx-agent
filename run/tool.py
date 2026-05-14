"""工具执行 - 注册 / 权限 / 限流 / 日志"""
import json
import contextvars
import time as _time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, TYPE_CHECKING

from skills._common import err, log_tool_call, reset_current_user_dir, set_current_user_dir

if TYPE_CHECKING:
    from provider.schema import ProviderResponse

# 全局工具注册表  {name: (schema, handler)}
TOOL_REGISTRY: dict[str, Any] = {}


def register_tool(schema: dict, handler, meta: dict = None):
    """注册工具到全局表"""
    name = schema["function"]["name"]
    TOOL_REGISTRY[name] = (schema, handler, meta or {})


def load_tool_schemas() -> list[dict[str, Any]]:
    """返回排序后的 schema 列表"""
    items = sorted(TOOL_REGISTRY.values(), key=lambda x: x[0]["function"]["name"])
    return [s for s, *_ in items]  # 取第一个元素（schema），兼容二元组和三元组


def clear_tool_registry():
    """清空全局工具注册表（reload 前调用）"""
    TOOL_REGISTRY.clear()


def get_tool_registry_snapshot() -> dict[str, Any]:
    """返回当前注册表的浅拷贝"""
    return dict(TOOL_REGISTRY)


class ToolRunner:
    """工具执行器 — 权限校验 / 限流 / 日志"""

    def __init__(self, core_config: dict[str, Any], user_config: dict[str, Any] = None, user_dir: str | None = None):
        """执行 init 内部辅助逻辑。"""
        tool_cfg = core_config.get("tool", {})
        self.max_total = tool_cfg.get("tool_max_per_type", 80)     # 单轮总上限
        self.max_per_tool = tool_cfg.get("tool_max_per_tool", 80)  # 单工具上限
        self.call_count = 0
        self.per_tool_count: dict[str, int] = {}
        self.user_dir = user_dir

        # 工具执行超时，优先级：user_config.tool.tool_timeout > core_config.tool.tool_timeout > provider.timeout > 120s
        user_tool_cfg = (user_config or {}).get("tool", {})
        provider_cfg = (user_config or {}).get("provider", {})
        self.tool_timeout = (
            user_tool_cfg.get("tool_timeout")
            or tool_cfg.get("tool_timeout")
            or provider_cfg.get("timeout")
            or 120
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
        """执行 count 内部辅助逻辑。"""
        self.call_count += 1
        self.per_tool_count[name] = self.per_tool_count.get(name, 0) + 1

    # ---- 工具调用 ----

    def has_tool_calls(self, response: Any) -> bool:
        """检查响应是否包含工具调用（适配 ProviderResponse 和旧 SDK 对象）"""
        if hasattr(response, "has_tool_calls"):
            return response.has_tool_calls
        return hasattr(response, "tool_calls") and bool(response.tool_calls)

    def execute(self, response: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """执行所有 tool_calls，返回 (tool result 消息列表, 调用详情列表)"""
        results: list[dict[str, Any]] = []
        details: list[dict[str, Any]] = []
        ctx_token = set_current_user_dir(self.user_dir)
        try:
            for tc in response.tool_calls:
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
                    details.append({"name": name, "args": {}, "elapsed": 0, "success": False})
                    log_tool_call(name, {}, limit_err, False, 0, user_dir=self.user_dir)
                    continue

                # 执行（带全局超时）
                t0 = _time.perf_counter()
                try:
                    if name in TOOL_REGISTRY:
                        entry = TOOL_REGISTRY[name]
                        handler = entry[1]  # handler 始终是第二个元素
                        call_context = contextvars.copy_context()
                        executor = ThreadPoolExecutor(max_workers=1)
                        try:
                            future = executor.submit(call_context.run, handler, **args)
                            try:
                                result = future.result(timeout=self.tool_timeout)
                                output = str(result)
                                success = not output.startswith("ERROR:")
                            except FutureTimeoutError:
                                future.cancel()
                                output = err(f"工具 {name} 执行超时 ({self.tool_timeout}s)")
                                success = False
                                executor.shutdown(wait=False, cancel_futures=True)
                                executor = None
                        finally:
                            if executor is not None:
                                executor.shutdown(wait=True, cancel_futures=True)
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
                results.append(_tool_msg(tc_id, output))
                details.append({"name": name, "args": args, "elapsed": elapsed, "success": success})
                log_tool_call(name, args, output, success, elapsed, user_dir=self.user_dir)
        finally:
            reset_current_user_dir(ctx_token)

        return results, details

    def reset_count(self):
        """处理 reset_count 相关逻辑。"""
        self.call_count = 0
        self.per_tool_count.clear()


def _tool_msg(tool_call_id: str, content: str) -> dict:
    """执行 tool_msg 内部辅助逻辑。"""
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}
