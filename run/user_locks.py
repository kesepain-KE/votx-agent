"""Per-user locks shared by Web UI, cron, and message routers."""
import threading

_guard = threading.RLock()
_locks: dict[str, threading.RLock] = {}


def get_user_lock(user_name: str) -> threading.RLock:
    """Return a stable reentrant lock for one internal user."""
    key = (user_name or "").strip()
    if not key:
        key = "__default__"
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock
