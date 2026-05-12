"""临时记忆遗忘 + 定期 auto_improve 触发"""
import os
import time as _time
from pathlib import Path


def run_forget(user_dir: str, forget_time: int):
    """清理 improve/*/temporary/ 中过期的 .md 文件。

    Args:
        user_dir: 用户目录路径
        forget_time: 过期秒数（默认 604800 = 7 天）
    """
    improve_dir = os.path.join(user_dir, "improve")
    if not os.path.isdir(improve_dir):
        return

    now = _time.time()
    for sub in ("memory", "self-improving", "ontology"):
        temp_dir = os.path.join(improve_dir, sub, "temporary")
        if not os.path.isdir(temp_dir):
            continue
        for fn in os.listdir(temp_dir):
            if not fn.endswith(".md"):
                continue
            fp = os.path.join(temp_dir, fn)
            try:
                if now - os.path.getmtime(fp) > forget_time:
                    os.remove(fp)
                    print(f"[corn:forget] 已删除过期文件: {fp}")
            except OSError:
                pass


def run_auto_improve_trigger(root: str, user_dir: str, core_config: dict):
    """检查上次 auto_improve 时间，满足间隔则触发一次被动提取。

    上次运行时间记录在 user_dir/improve/.last_auto_improve 纯文本文件中。
    """
    auto_improve_time = core_config.get("improve", {}).get("auto_improve_time", 3600)
    timestamp_file = os.path.join(user_dir, "improve", ".last_auto_improve")

    now = _time.time()

    # 检查间隔
    if os.path.exists(timestamp_file):
        try:
            with open(timestamp_file, encoding="utf-8") as f:
                last = float(f.read().strip())
            if now - last < auto_improve_time:
                return
        except (ValueError, IOError):
            pass

    # 按需创建 provider 并执行
    try:
        from provider.factory import create_provider
        from agents.auto_improve.agent import run_auto_improve

        user_config_path = os.path.join(user_dir, "config.json")
        core_config_path = os.path.join(root, "config", "config_core.json")

        import json
        with open(core_config_path, encoding="utf-8") as f:
            cc = json.load(f)
        if os.path.exists(user_config_path):
            with open(user_config_path, encoding="utf-8") as f:
                uc = json.load(f)
        else:
            uc = {}

        provider = create_provider(uc, cc)

        # 读取最近消息
        from run.chat import ChatManager
        chat = ChatManager(user_dir, cc, uc)
        chat.set_provider(provider)
        try:
            chat.load_history()
        except Exception:
            pass

        messages = chat.messages
        if messages:
            result = run_auto_improve(provider, messages, user_dir)
            if result.get("summary"):
                print(f"[corn:auto_improve] {result['summary']}")

        # 记录时间戳
        os.makedirs(os.path.dirname(timestamp_file), exist_ok=True)
        with open(timestamp_file, "w", encoding="utf-8") as f:
            f.write(str(now))

    except Exception as e:
        print(f"[corn:auto_improve] 触发失败: {e}")
