---
name: opencli-adapter-author
description: OpenCLI 适配器编写技能 — 从零到通过 verify 的完整流程。用于为新站点编写 adapter 或给已有站点添加新命令。覆盖站点侦察、API 发现、字段解码、adapter 编写、验证全流程。触发词：写 adapter、新建 opencli 命令、opencli adapter、站点适配。
type: instruction
---

# opencli-adapter-author

为新站点编写 OpenCLI adapter 的完整工作流，目标：30 分钟内从零到 `opencli browser verify` 通过。

## 前置自测

1. 数据在浏览器里看得到吗？（否 → 先解决鉴权）
2. 数据是 HTTP/JSON/HTML 吗？（否 → 不在范围内）
3. 需要实时推送吗？（是 → 找 HTTP 接口，没有就放弃）

## 顶层流程

```
START
  ↓ opencli doctor 通？
  ↓ 读站点记忆 (~/.opencli/sites/<site>/)
  ↓ 站点侦察 (site-recon) → Pattern A/B/C/D/E
  ↓ API 发现: §1 network → §2 state → §3 bundle → §4 token → §5 intercept
  ↓ endpoint 验证 (fetch 确认 200 + 含目标数据)
  ↓ 字段解码 + 设计 columns
  ↓ opencli browser init <site>/<name>
  ↓ opencli browser verify <site>/<name>
  ↓ 回写 ~/.opencli/sites/
DONE
```

## Runbook (逐步勾选)

```
[ ] 1. opencli doctor — "Everything looks good"
[ ] 2. 读站点记忆：endpoints.json / notes.md
[ ] 3. 侦察：opencli browser analyze <url>
[ ] 4. API 发现按 Pattern 选 §
[ ] 5. 直接 fetch 验证 endpoint
[ ] 6. 鉴权策略：PUBLIC / COOKIE / HEADER / INTERCEPT
[ ] 7. 字段解码 (field-conventions / field-decode-playbook)
[ ] 8. 设计 columns (output-design)
[ ] 9. 写 adapter: opencli browser init → cp 邻居 → 改 name/URL/映射
[ ] 10. opencli browser verify → 通过后 --write-fixture
[ ] 11. 字段值 vs 网页肉眼比对
[ ] 12. 回写站点记忆
```

## 降级路径

| 卡在 | 现象 | 跳去 |
|------|------|-----|
| API 发现 | network 空 | §3 bundle 搜 baseURL |
| endpoint 验证 | 401/403 | §4 token 排查 |
| endpoint 验证 | 200 但是 HTML | 回 Step 3 换 Pattern |
| 字段解码 | 推不出 | 先输出 raw，adapter 跑起来再迭代 |
| verify 失败 | 某列永远是 null | 字段路径错了，回 Step 7 |

## 关键约定

- adapter 只引 `@jackwener/opencli/registry` + `@jackwener/opencli/errors`
- `columns` 数组和 `func` 返回对象 keys 完全对齐
- `browser:` field 决定 func 签名：`false → (args)`, `true → (page, args)`
- 已知失败按 typed errors 5-classification 抛对应错误
- 私人 adapter 用 `~/.opencli/clis/<site>/<name>.js`

## 卡住了

- 诊断：`opencli doctor` → `notes.md` → autofix
- 字段解码：field-decode-playbook 全三节 → 先输出 raw
- endpoint 找不到：api-discovery §5 intercept 兜底
