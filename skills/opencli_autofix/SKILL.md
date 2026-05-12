---
name: opencli_autofix
description: OpenCLI 适配器自动修复技能。当 opencli 命令因网站 DOM/API/响应格式变化而失败时，自动诊断、修复 adapter 并重试。触发词：opencli 报错、adapter 坏了、修复 opencli、autofix。
type: instruction
---

# OpenCLI AutoFix

当 `opencli` 命令因网站变化而失败时，自动诊断、修复 adapter、验证、并提交上游 issue。

## 安全边界

**修复前检查硬停止条件：**

- `AUTH_REQUIRED` (exit 77) — **停。** 不修改代码。提示用户登录。
- `BROWSER_CONNECT` (exit 69) — **停。** 提示用户 `opencli doctor`。
- CAPTCHA / 限流 — **停。** 不是 adapter 问题。

**范围约束：** 只修改 trace `summary.md` 中的 `adapterSourcePath`。不碰 `src/`、`extension/`、`tests/` 等。

**重试预算：** 最多 3 轮修复。3 轮后停止并报告。

## 流程

### Step 1: 收集 Trace

```bash
opencli <site> <command> [args...] --trace retain-on-failure 2>trace-error.yaml
```

读取 `summary.md` 的 front matter（含 `adapterSourcePath`, `errorCode`, `errorMessage`）。

### Step 2: 分析失败

| Error Code | 可能原因 | 修复策略 |
|-----------|---------|---------|
| SELECTOR | DOM 重构，class/id 改名 | 探索当前 DOM → 找新选择器 |
| EMPTY_RESULT | API 响应格式变化 | 检查 network → 找新响应路径 |
| API_ERROR | Endpoint URL 变了 | 通过 network intercept 发现新 API |
| TIMEOUT | 页面加载方式变了 | 添加/更新 wait 条件 |
| PAGE_CHANGED | 大改版 | 可能需要完整重写 adapter |

### Step 3: 探索当前网站

用 `opencli browser` 而非损坏的 adapter：

```bash
# DOM 变了
opencli browser open <url> && opencli browser state

# API 变了
opencli browser open <url> && opencli browser state
opencli browser click <N> && opencli browser network
opencli browser network --detail <key>
```

### Step 4: 修补 Adapter

最小修改原则：
- 只改坏的部分，不重构
- 保持 columns 和输出格式兼容
- 优先 API 而非 DOM 抓取
- 只用 `@jackwener/opencli/*` 导入
- 改完立即测试

### Step 5: 验证

```bash
opencli <site> <command> [args...]
```

失败 → 回 Step 1。最多 3 轮。

### Step 6: 提交上游 Issue

修复通过后，准备并提交 GitHub issue 到 `jackwener/OpenCLI`：

```bash
gh issue create --repo jackwener/OpenCLI \
  --title "[autofix] <site>/<command>: <error_code>" \
  --body "..."
```

**不提交的情况：** AUTH_REQUIRED、BROWSER_CONNECT、CAPTCHA、3 轮耗尽仍未修复。
