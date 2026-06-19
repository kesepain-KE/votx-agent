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

KEMO_DEFAULT_BASE_URL = "http://127.0.0.1:8741/v1"
KEMO_CHAT_MODELS = [
    "stepfun-step-3.7-flash",
    "stepfun-step-3.5-flash-2603",
    "stepfun-step-3.5-flash",
    "stepfun-step-router-v1",
    "deepseek-deepseek-v4-flash",
    "deepseek-deepseek-v4-pro",
]

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

def ensure_user_skeleton(user_dir: Path):
    """创建或补齐完整的用户目录结构。"""
    # history 子目录
    for sub in ["chat", "log", "archive", "file"]:
        (user_dir / "history" / sub).mkdir(parents=True, exist_ok=True)

    # download（给用户的产出文件）
    (user_dir / "download").mkdir(parents=True, exist_ok=True)

    # avatar（用户头像）
    (user_dir / "avatar").mkdir(parents=True, exist_ok=True)

    # 知识库（用户独立）
    (user_dir / "knowledge").mkdir(parents=True, exist_ok=True)

    # 任务计划存储
    (user_dir / "task-plan").mkdir(parents=True, exist_ok=True)

    # 定时任务存储
    (user_dir / "tasks").mkdir(parents=True, exist_ok=True)

    # improve 三层记忆体系（permanent + temporary）
    for sub in ["memory", "self-improving", "ontology"]:
        for tier in ["permanent", "temporary"]:
            (user_dir / "improve" / sub / tier).mkdir(parents=True, exist_ok=True)

    # self-improving 模板文件（不存在时创建）
    si_perm = user_dir / "improve" / "self-improving" / "permanent"
    _write_if_missing(si_perm / "memory.md", MEMORY_MD)
    _write_if_missing(si_perm / "corrections.md", CORRECTIONS_MD)


def _ensure_dirs(user_dir: Path):
    """兼容旧调用名。"""
    ensure_user_skeleton(user_dir)


def _write_if_missing(path: Path, content: str):
    """文件不存在时写入"""
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _read_config(user_dir: Path) -> dict:
    """执行 read_config 内部辅助逻辑。"""
    cfg_path = user_dir / "config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def _write_config(user_dir: Path, config: dict):
    """执行 write_config 内部辅助逻辑。"""
    cfg_path = user_dir / "config.json"
    cfg_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_soul(user_dir: Path) -> str:
    """执行 read_soul 内部辅助逻辑。"""
    soul_path = user_dir / "self_soul.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")
    return ""


def _write_soul(user_dir: Path, content: str):
    """执行 write_soul 内部辅助逻辑。"""
    (user_dir / "self_soul.md").write_text(content, encoding="utf-8")


def list_users() -> list[str]:
    """返回已配置用户列表"""
    if not USERS_DIR.is_dir():
        return []
    result = []
    for d in USERS_DIR.iterdir():
        if d.is_dir() and (d / "config.json").exists():
            ensure_user_skeleton(d)
            result.append(d.name)
    return sorted(result)


# ── 交互式输入 ──────────────────────────────────

def _dedupe_models(models: list[str]) -> list[str]:
    """模型名去重，保持原始顺序。"""
    seen = set()
    result = []
    for model in models:
        name = str(model).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def _pick_model_from_list(models: list[str], default: str = "") -> str:
    """从厂商模型列表中选择模型，并允许手动输入。"""
    models = _dedupe_models(models)
    if default and default not in models:
        models.append(default)

    if not models:
        return input("  输入模型名: ").strip()

    print("\n  可用模型:")
    for i, name in enumerate(models, 1):
        marker = " (当前)" if name == default else ""
        print(f"  {i}. {name}{marker}")
    custom_idx = len(models) + 1
    print(f"  {custom_idx}. 手动输入模型名")

    default_idx = str(models.index(default) + 1) if default in models else "1"
    choice = input(f"  选择 [{default_idx}]: ").strip() or default_idx
    if choice == str(custom_idx):
        return input("  输入模型名: ").strip() or (default or models[0])
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            return models[idx]
    except ValueError:
        pass
    return default or models[0]


def _prompt_existing_key(current_key: str, empty_hint: str) -> str:
    """编辑时处理 API Key：回车保持，'-' 清除。"""
    if current_key:
        print(f"  当前 Key: {current_key[:16]}...")
        choice = input("  修改? (留空保持 / 输入新 Key / '-' 清除): ").strip()
        if choice == "-":
            return ""
        if choice:
            return choice
        return current_key
    return input(empty_hint).strip()


def _configure_kemo_provider(current: dict | None = None) -> dict:
    """配置本地 Kemo LLM Adapter。"""
    current = current or {}
    print("\n  Kemo LLM Adapter 本地网关。")
    cur_base_url = (
        current.get("base_url", "").strip()
        or os.environ.get("KEMO_BASE_URL", "").strip()
        or KEMO_DEFAULT_BASE_URL
    )
    base_url = input(f"  Base URL [{cur_base_url}]: ").strip() or cur_base_url
    api_key = _prompt_existing_key(
        current.get("api_key", "").strip(),
        "  API Key (留空使用 KEMO_API_KEY): ",
    )
    model = _pick_model_from_list(KEMO_CHAT_MODELS, current.get("model", "").strip() or KEMO_CHAT_MODELS[0])

    return {
        "type": "kemo",
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "vision_model": model,
        "audio_transcription_model": current.get("audio_transcription_model") or "stepfun-stepaudio-2.5-asr",
        "image_generation_model": current.get("image_generation_model", ""),
        "image_edit_model": current.get("image_edit_model") or "stepfun-step-image-edit-2",
        "speech_generation_model": current.get("speech_generation_model") or "stepfun-stepaudio-2.5-tts",
        "speech_to_speech_model": current.get("speech_to_speech_model", ""),
        "video_generation_model": current.get("video_generation_model", ""),
        "embedding_model": current.get("embedding_model", ""),
        "rerank_model": current.get("rerank_model", ""),
    }


def _pick_provider_config(current: dict | None = None, allow_keep: bool = False) -> dict | None:
    """选择并配置 provider。仅支持 Kemo LLM Adapter 本地网关。"""
    current = current or {}
    default_model = current.get("model", "")

    print("\n  Provider: Kemo LLM Adapter — 本地多模态网关")
    print(f"  当前模型: {default_model or '(未设置)'}")

    if allow_keep:
        choice = input("  修改配置? (回车保持 / y=重新配置): ").strip().lower()
        if not choice:
            return None
    else:
        input("  按回车继续配置...")

    return _configure_kemo_provider(current)


def _edit_api_key_only(config: dict, cfg: dict):
    """保留旧的单独 API Key 编辑能力。"""
    print("\n  API Key:")
    cur_key = cfg.get("api_key", "")
    if cur_key:
        new_key = _prompt_existing_key(cur_key, "  Key: ")
        config["provider"]["api_key"] = new_key
        if new_key and new_key != cur_key:
            new_url = input("  Base URL (回车不变): ").strip()
            if new_url:
                config["provider"]["base_url"] = new_url
        elif not new_key:
            config["provider"]["base_url"] = ""
    else:
        choice = input("  设置自定义 Key (留空保持 .env): ").strip()
        if choice:
            config["provider"]["api_key"] = choice
            new_url = input("  Base URL (回车默认): ").strip()
            if new_url:
                config["provider"]["base_url"] = new_url


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
    ensure_user_skeleton(user_dir)

    display_name = input(f"  角色名称 (回车='{name}'): ").strip() or name
    provider_config = _pick_provider_config()

    think_choice = input("  启用思考模式? (y/N): ").strip().lower()
    think = think_choice in ("y", "yes")

    stream_choice = input("  启用流式输出? (Y/n): ").strip().lower()
    stream = stream_choice not in ("n", "no")

    # config.json
    config = {
        "provider": {
            "think": think,
            "stream": stream,
            "timeout": 120,
            "vision_model": "",
            "audio_transcription_model": "",
            "image_generation_model": "",
            "image_edit_model": "",
            "speech_generation_model": "",
            "speech_to_speech_model": "",
            "video_generation_model": "",
            "embedding_model": "",
            "rerank_model": "",
            "capabilities_override": None,
            **provider_config,
        },
        "history": {
            "data": f"{name}_chat_data.json",
            "log": f"{name}_chat_log.json",
        },
        "tool": {"tool_timeout": 120, "enabled": {}, "deny": []},
        "task_plan": {"accept_task": True},
    }
    _write_config(user_dir, config)

    # self_soul.md — 默认使用通用模板
    _write_soul(user_dir, DEFAULT_SOUL)

    provider = config["provider"]
    tag = f"模型={provider.get('model')}" + (f" Key=自定义" if provider.get("api_key") else " Key=.env")
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
    ensure_user_skeleton(user_dir)

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
    provider_update = _pick_provider_config(cfg, allow_keep=True)
    if provider_update:
        config.setdefault("provider", {}).update(provider_update)
    else:
        _edit_api_key_only(config, cfg)

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

    provider_cfg = config.setdefault("provider", {})
    provider_cfg.setdefault("vision_model", "")
    provider_cfg.setdefault("audio_transcription_model", "")
    provider_cfg.setdefault("image_generation_model", "")
    provider_cfg.setdefault("image_edit_model", "")
    provider_cfg.setdefault("speech_generation_model", "")
    provider_cfg.setdefault("speech_to_speech_model", "")
    provider_cfg.setdefault("video_generation_model", "")
    provider_cfg.setdefault("embedding_model", "")
    provider_cfg.setdefault("rerank_model", "")
    provider_cfg.setdefault("capabilities_override", None)

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
    """执行命令行入口流程。"""
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
