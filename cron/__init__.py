"""cron — 后台定时调度系统

启动/停止入口:
    from cron import start_cron, stop_cron
    start_cron(root, core_config)
    ...
    stop_cron()
"""
import threading

_scheduler_thread = None
_stop_event = threading.Event()


def start_cron(root: str, core_config: dict, web_mode: bool = False):
    """启动后台调度线程（daemon，随主进程退出）"""
    global _scheduler_thread, _stop_event

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return

    _stop_event.clear()
    from cron.scheduler import _scheduler_loop
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(root, core_config, _stop_event, web_mode),
        daemon=True,
        name="cron-scheduler",
    )
    _scheduler_thread.start()
    print(f"[cron] 后台调度已启动 (web_mode={web_mode})")


def stop_cron():
    """停止后台调度线程"""
    global _scheduler_thread, _stop_event
    if _scheduler_thread is None:
        return
    _stop_event.set()
    _scheduler_thread.join(timeout=5)
    _scheduler_thread = None
    print("[cron] 后台调度已停止")
