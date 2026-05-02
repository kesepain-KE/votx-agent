# Hook Setup (Auto-Detection)

## activator.sh

Place in `.learnings/` to auto-initialise the directory if missing:

```bash
#!/bin/bash
# .learnings/activator.sh — Run once per session to ensure .learnings/ exists
LEARNINGS_DIR="$(dirname "$0")"
mkdir -p "$LEARNINGS_DIR"
for f in LEARNINGS.md ERRORS.md FEATURE_REQUESTS.md; do
    [ -f "$LEARNINGS_DIR/$f" ] || touch "$LEARNINGS_DIR/$f"
done
```

## error-detector.sh

A hook script that watches for common error patterns in command output and auto-logs to ERRORS.md:

```bash
#!/bin/bash
# .learnings/error-detector.sh — Scan for error patterns and log
# Intended to be called after each command in interactive sessions
LOG_FILE=".learnings/ERRORS.md"
LAST_EXIT=$?
LAST_CMD=$(history | tail -1 | sed 's/^ *[0-9]* *//')

if [ $LAST_EXIT -ne 0 ]; then
    echo "## [ERR-$(date +%Y%m%d)-$(openssl rand -hex 3)] $(echo $LAST_CMD | cut -d' ' -f1)" >> "$LOG_FILE"
    echo "**Logged**: $(date -Iseconds)" >> "$LOG_FILE"
    echo "**Priority**: medium" >> "$LOG_FILE"
    echo "**Status**: pending" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    echo "Command exited with code $LAST_EXIT: \`$LAST_CMD\`" >> "$LOG_FILE"
    echo "---" >> "$LOG_FILE"
fi
```

## Claude Code Hook Config

```json
{
  "hooks": {
    "preToolExecution": ".learnings/activator.sh",
    "postToolExecution": ".learnings/error-detector.sh"
  }
}
```

## Codex Hook Config

Codex supports pre/post command hooks via `~/.codex/config.json`:

```json
{
  "hooks": {
    "onCommand": [".learnings/activator.sh"],
    "onError": [".learnings/error-detector.sh"]
  }
}
```
