# OpenClaw Integration

## Installation

This skill is part of OpenClaw's built-in tool suite. When installed via OpenClaw, the `.learnings/` directory is auto-initialised at the workspace root.

## Workspace Structure

```
.learnings/
├── LEARNINGS.md              # Corrections, insights, knowledge gaps
├── ERRORS.md                 # Command failures and integration errors
└── FEATURE_REQUESTS.md       # Capabilities requested by the user
```

## Promotion Targets

| Target | What Belongs There |
|--------|-------------------|
| `CLAUDE.md` | Project facts, conventions, gotchas for all Claude interactions |
| `AGENTS.md` | Agent-specific workflows, tool usage patterns, automation rules |
| `.github/copilot-instructions.md` | Project context for GitHub Copilot |
| `SOUL.md` | Behavioral patterns and identity |
| `TOOLS.md` | Tool gotchas and usage notes |

## Inter-session Communication

OpenClaw's `plans/` and `decisions/` directories complement `.learnings/`:

- `plans/` — Active plans and in-progress work
- `decisions/` — Architectural decisions (ADR-style)
