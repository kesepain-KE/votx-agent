# Memory 生命周期执行原理

## 一、三层数据模型

| 类型 | 子目录 | 用途 | 示例 |
|------|--------|------|------|
| `memory` | `users/<name>/improve/memory/` | 事实、偏好、长期上下文 | "用户偏好 Python 3.12" |
| `self-improving` | `users/<name>/improve/self-improving/` | 行为纠正、回复策略 | "不要使用字符 # 和 *" |
| `ontology` | `users/<name>/improve/ontology/` | 概念关系、知识图谱 | "Plana → 是 → AI 助手" |

每层都有两个层级：

| 层级 | 目录 | 权限 | 说明 |
|------|------|------|------|
| 永久层 | `{sub}/` | 需要用户审阅后写入 | 长期有效 |
| 临时层 | `{sub}/temporary/` | 自动写入 | 7 天过期清理 |

## 二、被动触发模式（默认）

### 触发时机
- 每次 `run_chat_turn()` 结束后
- 由 cron 定时任务每小时执行一次

### 执行流程

```
对话结束 / cron 触发
  │
  ▼
auto_improve_trigger(provider, chat, user_name)
  │
  ▼
提取最近 N 条消息 → 构建分析 prompt
  │
  ▼
provider.respond(analyze_prompt)
  │  返回 JSON:
  │  {
  │    "memory": [{"key": "xxx", "content": "..."}],
  │    "self_improving": [{"key": "yyy", "content": "..."}],
  │    "ontology": [{"key": "zzz", "content": "..."}]
  │  }
  │
  ▼
写入临时层（temporary/*.md）
  │  每个条目一个文件
  │  文件名 = key + .md
  │  内容 = Markdown 格式
  │
  ▼
设置过期时间（mtime = 当前时间，7 天后清理）
```

### 权限限制
- 只读：永久层 + 临时层
- 只写：临时层
- 禁止：直接写永久层

## 三、主动审阅模式（用户触发）

### 触发方式
用户说 "review" / "审阅" / "整理记忆" → 主代理调用 `auto_improve_review()`

### 执行流程

```
用户: "整理记忆"
  │
  ▼
auto_improve_review()
  │
  ▼
1. 读取所有临时层文件（temporary/*.md）
2. 读取当前对话上下文
3. 读取已有永久层文件
  │
  ▼
构建审阅 prompt → provider.respond()
  │  返回:
  │  {
  │    "absorbed": [{"key": "xxx", "target": "memory", "action": "create|update"}],
  │    "rejected": [{"key": "yyy", "reason": "已过期"}]
  │  }
  │
  ▼
写入永久层（被吸收的条目）
  │  写入 memory/xxx.md 或 self-improving/yyy.md
  │
  ▼
写入 review_log.jsonl（审阅记录）
  │
  ▼
返回审阅结果给用户
```

### 权限
- 读取：临时层 + 永久层
- 写入：永久层 + review_log
- 禁止：直接修改临时层（由审阅结果决定）

## 四、清理机制

### 临时文件清理（run_forget）

```python
# run/forget.py
def run_forget(user_dir, retention_days=7):
    """清理超过保留天数的临时文件"""
    for sub in ["memory", "self-improving", "ontology"]:
        temp_dir = os.path.join(user_dir, "improve", sub, "temporary")
        for f in os.listdir(temp_dir):
            path = os.path.join(temp_dir, f)
            mtime = os.path.getmtime(path)
            age_days = (time.time() - mtime) / 86400
            if age_days > retention_days:
                os.remove(path)
```

- 执行者：cron 调度器，每 60 秒检查一次
- 保留天数：默认 7 天（`retention_days` 参数）
- 判断依据：文件最后修改时间（mtime）

### 已审阅清理

```python
auto_improve_cleanup_reviewed()
```
- 清理已被审阅吸收的临时文件
- 通过 `review_log.jsonl` 判断哪些文件已被吸收

## 五、注入到 System Prompt

临时记忆在 `build_system_prompt()` 中自动注入：

```
[SYSTEM-INTERNAL:临时记忆]
## 事实与偏好
- python_preferences.md: 用户偏好 Python 3.12，喜欢简洁风格

## 行为规则
- no_hash_in_reply.md: 不要在回复中使用 # 字符

## 概念关系
- plana_identity.md: Plana 是 AI 助手，来自蔚蓝档案

这些是系统自动提取的临时观察。可被 auto_improve_review 吸收为永久记忆。
```

永久记忆不注入 system prompt，而是通过 `auto_improve_get()` 工具按需读取。

## 六、数据流总览

```
对话内容
  │
  ▼ (被动触发)
临时层 ──(用户审阅)──→ 永久层
  │                      │
  │ (7天过期)             │ (长期有效)
  ▼                      ▼
自动清理              auto_improve_get() 按需读取
```

## 七、关键配置

| 配置项 | 位置 | 默认值 | 说明 |
|--------|------|--------|------|
| `retention_days` | 工具参数 | 7 | 临时文件保留天数 |
| cron 间隔 | cron/scheduler.py | 3600s | 被动触发间隔 |
| 清理检查间隔 | cron/scheduler.py | 60s | run_forget 检查间隔 |
