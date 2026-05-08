#!/usr/bin/env python3
"""votx-agent 用户管理 — 创建 / 编辑 / 查看用户

每个用户有独立的模型和 API Key。不填 Key 则走 .env 全局配置。

使用:
    python set_user.py                 交互式菜单
    python set_user.py add <name>      新建用户
    python set_user.py edit <name>     编辑用户
    python set_user.py list            列出所有用户
"""

import json
import os
import sys
from pathlib import Path

try:
    from paths import get_project_root
    ROOT = Path(get_project_root())
except Exception:
    ROOT = Path(__file__).parent
USERS_DIR = ROOT / "users"

MODELS = {
    "1": ("deepseek-v4-flash", "快速便宜，日常推荐"),
    "2": ("deepseek-v4-pro", "更强推理，复杂任务"),
    "3": ("deepseek-chat", "DeepSeek Chat"),
}

# ── 默认人设模板 ───────────────────────────────

DEFAULT_SOUL = """# 你的 AI 助手

你是用户专属的 AI 助手。帮助解决问题、回答疑问、完成任务。

## 要求
1. 回复简洁精炼
2. 积极回应用户的请求
3. 使用友好的语气
4. 不知道的事情直接说不知道，不编造

## 可用工具
你拥有文件读写、网络请求、命令执行、网络搜索等能力。根据需要使用。

## 行为准则
1. 不做危害用户系统的事
2. 保护用户隐私，不泄露敏感信息
3. 被纠正时立即改正，不辩解
4. 追求高效，能一步完成的不拆两步
"""

# ── 自改进模板 ────────────────────────────────

MEMORY_MD = """# Memory (HOT Tier)

## Preferences

## Patterns

## Rules

"""

CORRECTIONS_MD = """# Corrections Log

| Date | What I Got Wrong | Correct Answer | Status |
|------|-----------------|----------------|--------|
"""

# ── 工具函数 ────────────────────────────────────

def _ensure_dirs(user_dir: Path):
    """创建完整的用户目录结构"""
    # history 子目录
    for sub in ["chat", "log", "archive", "file"]:
        (user_dir / "history" / sub).mkdir(parents=True, exist_ok=True)

    # download
    (user_dir / "download").mkdir(parents=True, exist_ok=True)

    # 长期记忆
    (user_dir / "memory").mkdir(parents=True, exist_ok=True)

    # self-improving 目录 + 模板文件
    si = user_dir / "self-improving"
    for sub in ["projects", "domains", "archive"]:
        (si / sub).mkdir(parents=True, exist_ok=True)

    # 模板文件（不存在时才创建，避免覆盖）
    _write_if_missing(si / "memory.md", MEMORY_MD)
    _write_if_missing(si / "corrections.md", CORRECTIONS_MD)


def _write_if_missing(path: Path, content: str):
    """文件不存在时写入"""
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _read_config(user_dir: Path) -> dict:
    cfg_path = user_dir / "config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def _write_config(user_dir: Path, config: dict):
    cfg_path = user_dir / "config.json"
    cfg_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_soul(user_dir: Path) -> str:
    soul_path = user_dir / "self_soul.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")
    return ""


def _write_soul(user_dir: Path, content: str):
    (user_dir / "self_soul.md").write_text(content, encoding="utf-8")


def list_users() -> list[str]:
    """返回已配置用户列表"""
    if not USERS_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in USERS_DIR.iterdir()
        if d.is_dir() and (d / "config.json").exists()
    )


# ── 交互式输入 ──────────────────────────────────

def _pick_model(default: str = "") -> str:
    """选择模型"""
    print("\n  模型:")
    for k, (name, desc) in MODELS.items():
        marker = " (当前)" if name == default else ""
        print(f"  {k}. {name} — {desc}{marker}")
    print("  4. 自定义")
    choice = input(f"  选择 [{_model_to_key(default)}]: ").strip()
    if choice == "4":
        return input("  输入模型名: ").strip() or (default or "deepseek-v4-flash")
    for k, (name, _) in MODELS.items():
        if choice == k:
            return name
    if not choice and default:
        return default
    return MODELS["1"][0]


def _model_to_key(model: str) -> str:
    for k, (name, _) in MODELS.items():
        if name == model:
            return k
    return "1"


# ── 核心操作 ────────────────────────────────────

def add_user(name: str = "") -> str | None:
    """新建用户，返回用户名"""
    USERS_DIR.mkdir(parents=True, exist_ok=True)

    if not name:
        default = os.environ.get("USER", os.environ.get("USERNAME", "me"))
        name = input(f"  用户名 (回车='{default}'): ").strip() or default

    user_dir = USERS_DIR / name
    if user_dir.exists() and (user_dir / "config.json").exists():
        print(f"  用户 '{name}' 已存在，使用 edit 编辑")
        return None

    user_dir.mkdir(parents=True, exist_ok=True)
    _ensure_dirs(user_dir)

    display_name = input(f"  角色名称 (回车='{name}'): ").strip() or name
    model = _pick_model()

    print("\n  API Key (留空使用 .env 全局配置):")
    api_key = input("  Key: ").strip()

    base_url = ""
    if api_key:
        ask_url = input("  Base URL (回车默认 DeepSeek): ").strip()
        if ask_url:
            base_url = ask_url

    think_choice = input("  启用思考模式? (y/N): ").strip().lower()
    think = think_choice in ("y", "yes")

    stream_choice = input("  启用流式输出? (Y/n): ").strip().lower()
    stream = stream_choice not in ("n", "no")

    # config.json
    config = {
        "provider": {
            "model": model,
            "api_key": api_key,
            "think": think,
            "stream": stream,
            "timeout": 120,
            "base_url": base_url,
        },
        "history": {
            "data": f"{name}_chat_data.json",
            "log": f"{name}_chat_log.json",
        },
        "tool": {"tool_timeout": 120, "enabled": {}, "deny": []},
    }
    _write_config(user_dir, config)

    # self_soul.md — 默认使用通用模板
    _write_soul(user_dir, DEFAULT_SOUL)

    tag = f"模型={model}" + (f" Key=自定义" if api_key else " Key=.env")
    print(f"\n  用户 '{name}' 创建完成 ({tag})")
    print(f"  目录: {user_dir}")
    return name


def edit_user(name: str):
    """编辑已有用户"""
    user_dir = USERS_DIR / name
    if not user_dir.is_dir() or not (user_dir / "config.json").exists():
        print(f"  用户 '{name}' 不存在")
        return

    # 确保目录结构完整（补充可能缺失的目录）
    _ensure_dirs(user_dir)

    config = _read_config(user_dir)
    cfg = config.get("provider", {})

    print(f"\n  编辑用户: {name}")
    print(
        f"  当前配置: 模型={cfg.get('model')}  "
        f"think={cfg.get('think')}  stream={cfg.get('stream')}"
    )
    has_key = bool(cfg.get("api_key", "").strip())
    print(f"  API Key: {'自定义' if has_key else '.env 全局'}")

    print("\n  修改字段 (回车跳过):")
    model = _pick_model(cfg.get("model", ""))
    config.setdefault("provider", {})["model"] = model

    print("\n  API Key:")
    cur_key = cfg.get("api_key", "")
    if cur_key:
        print(f"  当前: {cur_key[:16]}...")
        choice = input("  修改? (留空保持 / 输入新 Key / '-' 清除): ").strip()
        if choice == "-":
            config["provider"]["api_key"] = ""
            config["provider"]["base_url"] = ""
        elif choice:
            config["provider"]["api_key"] = choice
            new_url = input("  Base URL (回车不变): ").strip()
            if new_url:
                config["provider"]["base_url"] = new_url
    else:
        choice = input("  设置自定义 Key (留空保持 .env): ").strip()
        if choice:
            config["provider"]["api_key"] = choice
            new_url = input("  Base URL (回车默认): ").strip()
            if new_url:
                config["provider"]["base_url"] = new_url

    think_cur = cfg.get("think", False)
    think_choice = input(f"  思考模式 [{'Y' if think_cur else 'N'}]: ").strip().lower()
    if think_choice in ("y", "yes"):
        config["provider"]["think"] = True
    elif think_choice in ("n", "no"):
        config["provider"]["think"] = False

    stream_cur = cfg.get("stream", True)
    stream_choice = input(
        f"  流式输出 [{'Y' if stream_cur else 'N'}]: "
    ).strip().lower()
    if stream_choice in ("y", "yes"):
        config["provider"]["stream"] = True
    elif stream_choice in ("n", "no"):
        config["provider"]["stream"] = False

    _write_config(user_dir, config)
    print(f"  用户 '{name}' 已更新")


# ── 菜单 ────────────────────────────────────────

def menu():
    """交互式菜单"""
    while True:
        users = list_users()
        print("\n" + "=" * 40)
        print("votx-agent 用户管理")
        print("=" * 40)
        if users:
            print("\n已有用户:")
            for u in users:
                cfg = _read_config(USERS_DIR / u).get("provider", {})
                key_src = "自定义Key" if cfg.get("api_key", "").strip() else ".env"
                print(f"  {u}  →  {cfg.get('model', '?')}  ({key_src})")
        else:
            print("\n(无用户)")

        print("\n操作:")
        print("  1. 新建用户")
        print("  2. 编辑用户")
        print("  3. 刷新")
        print("  4. 退出")
        choice = input("\n选择 [1]: ").strip() or "1"

        if choice == "1":
            add_user()
        elif choice == "2":
            if not users:
                print("  没有可编辑的用户")
                continue
            name = input(f"  用户名 ({'/'.join(users)}): ").strip()
            if name in users:
                edit_user(name)
            else:
                print(f"  用户 '{name}' 不存在")
        elif choice == "3":
            continue
        elif choice == "4":
            break


# ── 入口 ────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args:
        menu()
        return

    cmd = args[0].lower()
    if cmd == "list":
        users = list_users()
        if users:
            for u in users:
                cfg = _read_config(USERS_DIR / u).get("provider", {})
                key_src = "自定义Key" if cfg.get("api_key", "").strip() else ".env"
                print(f"  {u}  →  {cfg.get('model', '?')}  ({key_src})")
        else:
            print("(无用户)")
    elif cmd == "add":
        name = args[1] if len(args) > 1 else ""
        add_user(name)
    elif cmd == "edit":
        name = args[1] if len(args) > 1 else ""
        if not name:
            users = list_users()
            if not users:
                print("无用户可编辑")
                return
            name = input(f"用户名 ({'/'.join(users)}): ").strip()
        edit_user(name)
    else:
        print("用法: python set_user.py [add <name>|edit <name>|list]")


if __name__ == "__main__":
    main()
