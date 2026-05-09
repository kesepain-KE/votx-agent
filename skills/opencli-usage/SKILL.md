---
name: opencli-usage
description: OpenCLI 顶层使用指南。当 Agent 需要了解 opencli 能做什么、如何发现适配器、通用标志和输出格式时使用。触发词：opencli 能做什么、opencli 命令怎么用、opencli list。
type: instruction
---

# opencli-usage

OpenCLI turns any website, Electron desktop app, or external CLI into a uniform `opencli <site> <command>` surface that agents can drive without screen-scraping.

## The three pillars

- **Adapter commands** — `opencli <site> <command> [...]`. Built-in adapters live in `clis/`, user adapters in `~/.opencli/clis/`.
- **Browser driving** — `opencli browser *` subcommands for ad-hoc interaction and scraping.
- **External CLI passthrough** — `opencli gh`, `opencli docker`, `opencli vercel`, etc.

## Install

```bash
npm install -g @jackwener/opencli          # requires Node >= 21
opencli doctor                              # verify browser bridge
```

## Discover commands

```bash
opencli list                    # table, grouped by site
opencli list -f json            # machine-readable
opencli <site> --help           # site commands + flags
opencli <site> <command> --help # positional args and flags
```

## Universal flags

| flag | effect |
|------|--------|
| `-f, --format <fmt>` | `table` / `json` / `yaml` / `plain` / `md` / `csv` |
| `-v, --verbose` | Debug logs + stack traces |

## Strategy tags

| Strategy | Needs browser? |
|----------|---------------|
| `PUBLIC` | No — pure HTTP |
| `COOKIE` / `HEADER` | Chrome logged in + OpenCLI extension |
| `INTERCEPT` | Same as COOKIE + automation window |
| `UI` | Same as COOKIE, full DOM interaction |
| `LOCAL` | No browser, local/dev endpoint |

## Where to go next

| Task | Load |
|------|------|
| Drive a live browser | `opencli-browser` |
| Write a new adapter | `opencli-adapter-author` |
| Fix a broken adapter | `opencli-autofix` |
| Smart search routing | `smart-search` |
