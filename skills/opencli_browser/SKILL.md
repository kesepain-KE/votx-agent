---
name: opencli-browser
description: 通过 opencli 驱动真实 Chrome 窗口的浏览器自动化技能。用于检查页面、填写表单、点击登录流程、提取数据。覆盖选择器优先的目标契约、复合表单字段、网络捕获等。触发词：opencli browser、浏览器自动化、网页操作、页面交互。
type: instruction
---

# opencli-browser

This skill is for driving a live browser via opencli. Use `opencli-adapter-author` if building a reusable adapter.

## Prerequisites

```bash
opencli doctor
```

## Mental model

1. **Selector-first.** Every interaction command takes a `<target>` — numeric ref from `state`/`find` or CSS selector.
2. **Every envelope reports `matches_n` and `match_level`.** `exact` > `stable` > `reidentified`.
3. **Compact output first, full payload on demand.**
4. **Structured errors:** branch on `error.code`, not message strings.

## Critical rules

1. Always `state` or `find` before acting. Never hard-code refs across sessions.
2. Prefer numeric ref over CSS once you have it.
3. Read `match_level` after every write.
4. Use `compound` field for form controls (date/select/file).
5. Verify writes: after `type`, run `get value`. Autocomplete can silently eat characters.
6. Re-`state` after page transitions.
7. Chain with `&&`.
8. `eval` is read-only.
9. Prefer `network` to screen-scraping for API data.

## Quick commands

| category | commands |
|----------|----------|
| Inspect | `state`, `find --css <sel>`, `frames`, `screenshot` |
| Get | `get title/url/text/value/attributes/html` |
| Interact | `click`, `type`, `fill`, `select`, `keys`, `scroll` |
| Wait | `wait selector/text/time` |
| Extract | `extract`, `eval`, `web read --url` |
| Network | `network`, `network --detail <key>`, `network --filter "field1,field2"` |
| Tabs | `tab list/new/select/close`, `back`, `close`, `bind`, `unbind` |

## Recipes

### Fill a login form

```bash
opencli browser open "https://example.com/login"
opencli browser state
opencli browser type 4 "me@example.com"
opencli browser type 5 "hunter2"
opencli browser get value 4  # verify
opencli browser click 6      # submit
opencli browser wait selector "[data-testid=account-menu]" --timeout 15000
opencli browser state
```

### Scrape via network instead of DOM

```bash
opencli browser open "https://news.ycombinator.com"
opencli browser network --filter "title,score"
opencli browser network --detail <key>
```

## Troubleshooting

| symptom | fix |
|---------|-----|
| `opencli doctor` red | Start Chrome with remote debugging, or install extension |
| `selector_not_found` | Page mutated. `wait selector "..."` then retry |
| `stale_ref` | Re-`state` |
| `type` value wrong | Verify with `get value`, add `keys Enter` |
| Giant `get html` | Use `--selector` + `--as json --depth 3 --children-max 20` |
