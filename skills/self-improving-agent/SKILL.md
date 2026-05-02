---
name: self-improving-agent
description: "Captures learnings, errors, and corrections to enable continuous improvement. Use when: (1) A command or operation fails unexpectedly, (2) User corrects Claude, (3) User requests a capability that doesn't exist, (4) An external API or tool fails, (5) Claude realizes its knowledge is outdated or incorrect, (6) A better approach is discovered for a recurring task. Also review learnings before major tasks."
---

# Self-Improvement Skill

Log learnings and errors to markdown files for continuous improvement.

## First-Use Initialisation

Ensure `.learnings/` directory and files exist:

```bash
mkdir -p .learnings
[ -f .learnings/LEARNINGS.md ] || printf "# Learnings\n\n---\n" > .learnings/LEARNINGS.md
[ -f .learnings/ERRORS.md ] || printf "# Errors\n\n---\n" > .learnings/ERRORS.md
[ -f .learnings/FEATURE_REQUESTS.md ] || printf "# Feature Requests\n\n---\n" > .learnings/FEATURE_REQUESTS.md
```

Never overwrite existing files. Do not log secrets, tokens, or full source files.

## Quick Reference

| Situation | Action |
|-----------|--------|
| Command/operation fails | Log to `ERRORS.md` |
| User corrects you | Log to `LEARNINGS.md` as `correction` |
| User requests missing feature | Log to `FEATURE_REQUESTS.md` |
| API/external tool fails | Log to `ERRORS.md` with integration details |
| Knowledge was outdated | Log to `LEARNINGS.md` as `knowledge_gap` |
| Found better approach | Log to `LEARNINGS.md` as `best_practice` |
| Broadly applicable learning | Promote to `CLAUDE.md` / `AGENTS.md` |
| Tool gotchas | Promote to `TOOLS.md` |
| Behavioral patterns | Promote to `SOUL.md` |

## Workflow

When errors or corrections occur:
1. Log to the appropriate file in `.learnings/`
2. Review and promote broadly applicable learnings to project memory files

## Logging Format

See `references/logging-templates.md` for full format specs including:
- Learning Entry (LEARNINGS.md)
- Error Entry (ERRORS.md)
- Feature Request Entry (FEATURE_REQUESTS.md)
- ID Generation (TYPE-YYYYMMDD-XXX)
- Resolving and status updates

## Promotion

When a learning is broadly applicable, promote it to permanent project memory:

| Target | What Belongs There |
|--------|-------------------|
| `CLAUDE.md` | Project facts, conventions, gotchas |
| `AGENTS.md` | Workflows, tool usage, automation rules |
| `.github/copilot-instructions.md` | Copilot context |
| `SOUL.md` | Behavioral patterns |
| `TOOLS.md` | Tool gotchas |

## Platform Integration

See reference docs:
- `references/openclaw-integration.md` — OpenClaw workspace setup and inter-session communication
- `references/hooks-setup.md` — Auto-detection hooks for Claude Code and Codex
