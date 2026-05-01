# 模块 API

## main.py

```python
MAX_TOOL_ROUNDS = 20  # 单轮对话最大工具往返次数

# System prompt 组装:
#   self_soul.md → config/soul.md → AGENT.md

def _dispatch(cmd) -> bool | None
    # True=退出, False=已处理跳过LLM, None=不是命令交给LLM
    # /exit /quit /q  → True
    # /clear /history /archive /help → False
```

## provider/openai_api.py

```python
class DeepSeekProvider:
    def __init__(self, user_config: dict)
        # 配置: provider.api_key / model / think / stream / timeout
        # api_key 为空时抛出 ValueError（含设置指引）
        # 自动加载 .env 文件（项目根 + CWD，不覆盖已有环境变量）

    last_usage: dict | None  # 最近一次 API 调用的 token 用量
        # {"prompt_tokens": N, "completion_tokens": N,
        #  "total_tokens": N, "cached_tokens": N}

    def chat(messages, tools=None) -> ChatCompletionMessage
        # think=True  → reasoning_effort="high"
        # think=False → thinking: disabled
        # stream=True → 收集 chunk 拼接为完整 Message + usage
        # 超时/连接错误自动重试 2 次（间隔递增）
```

## run/chat.py

```python
class ChatManager:
    # --- 消息管理 ---
    set_system_prompt(prompt)          # 设置角色人设
    build_messages() -> list[dict]     # system + self.messages

    add_user_message(content)          # {"role":"user",...}
    add_assistant_message(content)     # {"role":"assistant",...}
    add_tool_call_message(tool_calls)  # SDK对象→dict 后追加
    add_tool_results(results)          # [{"role":"tool",...}]

    # --- 持久化 ---
    load_history()                     # JSON → self.messages（损坏自动修复）
    save_history()                     # self.messages → JSON（不含system）
    save_log(full_messages)            # 完整消息链（含system+AGENT.md）→ JSON

    # --- 历史管理命令 ---
    clear_history() -> str             # 先归档再清空，删除历史文件
    archive_now() -> str               # 手动归档当前全部历史（不清空）
    history_stats() -> str             # 返回状态摘要（消息数/文件大小/归档数/开关状态）

    # --- 内部 ---
    _trim_if_needed()                  # 裁剪 + 触发归档
    _archive(old_messages)             # 归档到 history/archive/
```

### 消息存储格式（OpenAI 标准）

```json
[
  {"role": "system", "content": "角色人设...\n\nAGENT.md..."},
  {"role": "user", "content": "你好"},
  {"role": "assistant", "content": null,
   "tool_calls": [{"id":"call_xxx","type":"function",
    "function":{"name":"download_video","arguments":"{...}"}}]},
  {"role": "tool", "tool_call_id": "call_xxx", "content": "OK: ..."}
]
```

## run/tool.py

```python
# 全局注册表
TOOL_REGISTRY: dict[str, (schema, handler)]
register_tool(schema, handler)       # 注册
load_tool_schemas() -> list[dict]    # 排序返回

class ToolRunner:
    def __init__(self, core_config, user_config=None)
        # 配置: tool_max(100) / tool_max_per_type(50) / enabled / deny

    reset_count()                      # 每轮重置
    has_tool_calls(message) -> bool

    def execute(message) -> list[dict]
        # 流程: 权限检查 → 限流检查 → 解析参数 → handler → 日志
        # 全异常捕获，统一 ERROR: 格式
```

## skills/_common/__init__.py

```python
err(msg) -> str                    # → "ERROR: {msg}"
truncate(text, max=8000) -> str    # 超长截断+标注
safe_path(raw) -> Path | None      # 路径沙箱（仅用户目录+项目根）
log_tool_call(name, args, result, success, elapsed)  # JSON Lines（过滤敏感参数）
```
