"""In-process external message router lifecycle."""
from __future__ import annotations

from message.runtime import MessageRuntime

_runtime: MessageRuntime | None = None


def start_message_router(root: str, core_config: dict):
    """Start the message router thread if message config enables it."""
    global _runtime
    if _runtime is not None and _runtime.is_alive():
        return

    runtime = MessageRuntime(root, core_config)
    if not runtime.enabled:
        return

    _runtime = runtime
    runtime.start()


def stop_message_router():
    """Stop the message router thread."""
    global _runtime
    if _runtime is None:
        return
    _runtime.stop()
    _runtime = None
