# Memory 生命周期执行原理

## 一、三层数据模型

| 类型 | 子目录 | 用途 |
|------|--------|------|
| `memory` | `users/<name>/improve/memory/` | 事实、偏好、长期上下文 |
| `self-improving` | `users/<name>/improve/self-improving/` | 行为纠正、回复策略 |
| `ontology` | `users/<name>/improve/ontology/` | 概念关系、知识图谱 |

每层都有两个层级：

| 层级 | 目录 | 权限 |
|------|------|------|
| 永久层 | `{sub}/` | 需要用户审阅后写入 |
| 临时层 | `{sub}/temporary/` | 自动写入，7 天过期清理 |

## 二、被动触发模式（默认）

### 触发时机
- cron 定时任务每小时执行一次

### 执行流程

```
cron 触发 → auto_improve_trigger()
  → 提取最近 N 条消息 → 构建分析 prompt
  → provider.respond(analyze_prompt) → 返回 JSON
  → 写入临时层（temporary/*.md）
```

### 权限限制
- 只读：永久层 + 临时层
- 只写：临时层
- 禁止：直接写永久层

## 三、主动审阅模式（用户触发）

```
用户: "整理记忆" → auto_improve_review()
  → 读取所有临时文件 + 当前对话
  → LLM 分析哪些值得保留
  → 有价值的写入永久层，无价值的标记 rejected
  → 写入 review_log.jsonl
```

## 四、清理机制

### 临时文件清理（run_forget）

- 执行者：cron 调度器，每 60 秒检查一次
- 保留天数：默认 7 天
- 判断依据：文件最后修改时间（mtime）

## 五、数据流总览

```
对话内容
  ▼ (被动触发)
临时层 ──(用户审阅)──→ 永久层
  │ (7天过期)             │ (长期有效)
  ▼                      ▼
自动清理              auto_improve_get() 按需读取
```
