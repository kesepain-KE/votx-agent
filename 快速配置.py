#!/usr/bin/env python3
"""kesepain-Agent 快速配置 — 克隆后一键完成环境设置

自动完成：依赖安装 → API Key 配置 → 用户创建 → 验证
首次运行后只需 `python start.py` 即可日常使用。
"""

import os
import subprocess
import sys
import json
from pathlib import Path


def banner():
    print("""
  ╔══════════════════════════════════════╗
  ║     kesepain-Agent 快速配置工具      ║
  ║     多用户 AI Agent 框架一键就绪     ║
  ╚══════════════════════════════════════╝
""")
    print("克隆后首次运行，我来帮你把一切都配置好～\n")


def check_python() -> bool:
    """检查 Python 版本 >= 3.10"""
    major, minor = sys.version_info[:2]
    print(f"[1/6] Python 版本: {major}.{minor}")
    if (major, minor) < (3, 10):
        print(f"  错误: 需要 Python 3.10+，当前 {major}.{minor}")
        return False
    print("  OK\n")
    return True


def setup_env() -> bool:
    """创建 .env 文件，引导填写 API Key"""
    print("[2/6] 设置 API Key")

    root = Path(__file__).parent
    env_file = root / ".env"
    env_example = root / ".env.example"

    # 已有 .env 且不为空 → 跳过
    if env_file.exists() and env_file.stat().st_size > 0:
        content = env_file.read_text(encoding="utf-8")
        if "sk-your-key-here" not in content and "DEEPSEEK_API_KEY=" in content:
            print(f"  .env 已存在且已配置，跳过\n")
            return True
        print("  .env 已存在但未填写有效 Key，重新配置...")

    # 从模板读取
    if env_example.exists():
        template = env_example.read_text(encoding="utf-8")
    else:
        template = "# kesepain-Agent 环境变量\nDEEPSEEK_API_KEY=sk-your-key-here\n# DEEPSEEK_BASE_URL=https://api.deepseek.com\n# UAPI_API_KEY=your-uapi-key\n# TAVILY_API_KEY=your-tavily-key\n# HTTP_TIMEOUT=15\n"

    print("  获取 DeepSeek API Key: https://platform.deepseek.com/api_keys")
    api_key = input("  DeepSeek API Key (留空跳过): ").strip()

    if api_key:
        content = template.replace("sk-your-key-here", api_key)
    else:
        content = template
        print("  已跳过，之后可编辑 .env 手动填写")

    env_file.write_text(content, encoding="utf-8")
    print("  OK — .env 已创建\n")
    return True


def install_deps() -> bool:
    """安装 Python 依赖"""
    print("[3/6] 安装依赖")

    root = Path(__file__).parent
    req_file = root / "requirements.txt"
    if not req_file.exists():
        print("  错误: 找不到 requirements.txt")
        return False

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"],
            check=True,
        )
        print("  OK — 依赖安装完成\n")
        return True
    except subprocess.CalledProcessError:
        print("  错误: pip install 失败，请检查网络后手动运行:")
        print(f"  pip install -r {req_file}")
        return False


def create_user() -> bool:
    """交互式创建用户"""
    print("[4/6] 创建用户")

    root = Path(__file__).parent
    users_dir = root / "users"
    users_dir.mkdir(parents=True, exist_ok=True)

    # 选择用户名
    default_name = os.environ.get("USER", os.environ.get("USERNAME", "me"))
    name = input(f"  用户名 (回车默认 '{default_name}'): ").strip()
    if not name:
        name = default_name

    # 检查是否已存在
    user_dir = users_dir / name
    if user_dir.exists():
        print(f"  用户 '{name}' 已存在，跳过创建\n")
        return True

    user_dir.mkdir(parents=True, exist_ok=True)

    # 模型选择
    print("\n  选择默认模型 (回车=1):")
    print("  1. deepseek-v4-flash  — 快速便宜，日常推荐")
    print("  2. deepseek-v4-pro    — 更强推理，复杂任务")
    print("  3. 自定义")
    model_choice = input("  模型 [1]: ").strip()

    model_map = {
        "1": "deepseek-v4-flash",
        "2": "deepseek-v4-pro",
        "": "deepseek-v4-flash",
    }
    if model_choice == "3":
        model = input("  输入模型名: ").strip() or "deepseek-v4-flash"
    else:
        model = model_map.get(model_choice, "deepseek-v4-flash")

    # 角色名称
    display_name = input(f"  角色名称 (回车默认 '{name}'): ").strip() or name

    # 创建 config.json
    config = {
        "provider": {
            "model": model,
            "api_key": "",
            "think": False,
            "stream": False,
            "timeout": 120,
        },
        "history": {
            "data": f"{name}_chat_data.json",
            "log": f"{name}_chat_log.json",
        },
        "tool": {
            "enabled": {},
            "deny": [],
        },
    }
    with open(user_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 创建 self_soul.md
    soul = f"""# {display_name} 的角色定义

你是 {display_name} 的 AI 助手。帮助解决问题、回答疑问、完成任务。

## 要求
1. 回复简洁精炼
2. 积极回应用户的请求
3. 使用友好的语气

## 可用工具
你拥有文件读写、网络请求、命令执行、网络搜索等能力。根据需要使用。
"""
    with open(user_dir / "self_soul.md", "w", encoding="utf-8") as f:
        f.write(soul)

    # 创建历史目录
    for sub in ["chat", "log", "archive", "file"]:
        (user_dir / "history" / sub).mkdir(parents=True, exist_ok=True)

    print(f"\n  OK — 用户 '{name}' 已创建 (模型: {model})\n")
    return True


def verify() -> bool:
    """验证关键模块能正常导入"""
    print("[5/6] 验证项目")

    root = Path(__file__).parent
    sys.path.insert(0, str(root))

    errors = []
    for mod_name in ["provider.openai_api", "run.chat", "run.tool", "skills"]:
        try:
            import importlib
            importlib.import_module(mod_name)
        except Exception as e:
            errors.append(f"  {mod_name}: {e}")

    if errors:
        print("  以下模块导入失败:")
        for e in errors:
            print(e)
        print("  请检查依赖是否安装完整\n")
        return False

    # 检查 API Key
    env_file = root / ".env"
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        if "DEEPSEEK_API_KEY=sk-" in content and "sk-your-key-here" not in content:
            print("  OK — 所有模块可用，API Key 已配置\n")
            return True

    print("  OK — 模块可用 (API Key 未配置，启动前请编辑 .env)\n")
    return True


def finish():
    print("[6/6] 配置完成！\n")
    print("  启动方式:")
    print(f"    python start.py")
    print()
    print("  斜杠命令:")
    print("    /exit   退出      /clear  清除历史")
    print("    /history 状态      /archive 归档")
    print("    /help   帮助")


def main():
    banner()

    steps = [check_python, setup_env, install_deps, create_user, verify, finish]
    for step in steps:
        try:
            if not step():
                print(f"\n配置中断于: {step.__doc__}")
                print("修复后重新运行即可。")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\n\n已取消。可重新运行继续配置。")
            sys.exit(0)


if __name__ == "__main__":
    main()
