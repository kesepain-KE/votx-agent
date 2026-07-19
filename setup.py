
def build_frontend() -> bool:
    """构建前端 web/dist/ (Node.js 构建产物)"""
    dist_dir = ROOT / "web" / "dist"
    if dist_dir.is_dir() and any(dist_dir.iterdir()):
        print("  web/dist/         [已构建]")
        return True

    print("  web/dist/ 不存在，需要构建前端...")

    # 检查 Node.js
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        subprocess.run(["npm", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  Node.js/npm 未安装，跳过自动构建")
        print("  手动构建: cd web && npm install && npm run build")
        return False

    web_dir = ROOT / "web"
    print("  npm install...")
    try:
        subprocess.run(
            ["npm", "install"],
            cwd=str(web_dir),
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("  npm install       [FAIL]")
        print(f"  手动执行: cd {web_dir} && npm install && npm run build")
        return False

    print("  npm run build...")
    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(web_dir),
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("  npm run build     [FAIL]")
        print(f"  手动执行: cd {web_dir} && npm run build")
        return False

    if dist_dir.is_dir() and any(dist_dir.iterdir()):
        print("  前端构建          [OK]")
        return True
    else:
        print("  前端构建          [FAIL] — 构建后 dist 仍为空")
        return False
"""votx-agent 环境安装 — 全新安装 / 迁移后一键就绪

使用:
    python setup.py          安装依赖 + 配置 .env
    python setup.py --skip-env  跳过 .env 配置（仅安装依赖+验证）
    python setup.py --check     仅检查环境，不改动任何文件
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def check_python() -> bool:
    """Python >= 3.10"""
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 10)
    tag = "OK" if ok else f"FAIL (需要 3.10+)"
    print(f"  Python {major}.{minor}  [{tag}]")
    return ok


def check_git() -> bool:
    """git 可用"""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print("  git               [OK]")
        return True
    except Exception:
        print("  git               [MISSING]")
        return True  # 不阻断


def check_deps() -> bool:
    """检查核心依赖是否已安装"""
    deps = {
        "yt_dlp": "yt-dlp",
        "tavily": "tavily-python",
        "yaml": "pyyaml",
        "PIL": "pillow",
        "pdf2image": "pdf2image",
        "flask": "flask",
        "websockets": "websockets",
    }
    missing = []
    for mod, pkg in deps.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"  缺失依赖: {', '.join(missing)}")
        return False
    print(f"  核心依赖 ({len(deps)})    [OK]")
    return True


def install_deps() -> bool:
    """安装 requirements.txt"""
    req = ROOT / "requirements.txt"
    if not req.exists():
        print("  requirements.txt 不存在，跳过")
        return True

    print("  安装依赖...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(req), "--quiet"],
            check=True,
        )
        print("  依赖安装          [OK]")
        return True
    except subprocess.CalledProcessError:
        print("  依赖安装          [FAIL]")
        print(f"  手动执行: pip install -r {req}")
        return False


def setup_env() -> bool:
    """创建或更新 .env"""
    env_file = ROOT / ".env"
    env_example = ROOT / ".env.example"

    # 已有有效 .env
    if env_file.exists() and env_file.stat().st_size > 0:
        content = env_file.read_text(encoding="utf-8")
        if "VOTX_API_KEY=" in content and "sk-votx-your-key-here" not in content:
            print("  .env              [已配置]")
            return True

    print("  .env 未配置或包含占位符，需要填写 VOTX API Key")
    print("  获取: 查看 llm-adapter-votx 的 config/api_keys.json")

    if env_example.exists():
        template = env_example.read_text(encoding="utf-8")
    else:
        template = (
            "# votx-agent 环境变量\n"
            "VOTX_API_KEY=sk-votx-your-key-here\n"
            "# VOTX_BASE_URL=http://127.0.0.1:8741/v1\n"
            "# TAVILY_API_KEY=your-tavily-key\n"
            "# HTTP_TIMEOUT=15\n"
        )

    try:
        api_key = input("  VOTX API Key (回车跳过): ").strip()
    except (EOFError, KeyboardInterrupt):
        api_key = ""

    content = template.replace("sk-votx-your-key-here", api_key) if api_key else template
    env_file.write_text(content, encoding="utf-8")
    print(f"  .env              [{'已创建' if api_key else '已跳过'}]")
    return True


def verify_imports() -> bool:
    """验证关键模块可导入"""
    sys.path.insert(0, str(ROOT))
    modules = [
        "provider.votx_adapter",
        "run.chat",
        "run.tool",
        "run.engine",
        "skills",
        "cron",
        "agents",
        "web",
        "message",
        "message.attachments",
        "message.routes.onebot",
        "message.routes.telegram",
    ]
    failed = []
    for mod in modules:
        try:
            import importlib
            importlib.import_module(mod)
        except Exception as e:
            failed.append(f"  {mod}: {e}")

    if failed:
        print("  模块导入失败:")
        for f in failed:
            print(f)
        return False
    print(f"  模块导入 ({len(modules)})     [OK]")
    return True


def check_users() -> bool:
    """扫描已有用户"""
    users_dir = ROOT / "users"
    if not users_dir.is_dir():
        print("  users/ 目录不存在，运行 set_user.py 创建")
        return False

    users = [
        d.name for d in users_dir.iterdir()
        if d.is_dir() and (d / "config.json").exists()
    ]
    if users:
        print(f"  已有用户: {', '.join(users)}")
        return True
    else:
        print("  无已配置用户，运行 set_user.py 创建")
        return False


def main():
    """执行命令行入口流程。"""
    check_only = "--check" in sys.argv
    skip_env = "--skip-env" in sys.argv

    print("votx-agent 环境安装\n")

    if check_only:
        print("[仅检查模式]\n")

    # 1. 环境检查
    print("[1] 环境检查")
    py_ok = check_python()
    check_git()
    if not py_ok:
        sys.exit(1)
    deps_ok = check_deps()
    if check_only and not deps_ok:
        sys.exit(1)

    # 2. 依赖安装
    if not check_only:
        print("\n[2] 依赖安装")
        if not deps_ok:
            if not install_deps():
                sys.exit(1)
        else:
            print("  (已安装，跳过)")

    # 3. .env 配置
    if not check_only and not skip_env:
        print("\n[3] API Key 配置")
        setup_env()

    # 4. 验证
    print("\n[4] 验证")
    if not verify_imports():
        sys.exit(1)

    # 5. 前端构建（web/dist/ — 构建产物，不跟踪在 Git 中）
    if not check_only:
        print("\n[5] 前端构建")
        if not build_frontend():
            sys.exit(1)

    # 6. 用户状态
    print("\n[6] 用户状态")
    has_users = check_users()

    print()
    if has_users:
        print("环境就绪。启动:")
        print("  python start.py          # CLI")
        print("  python start_web.py      # Web UI")
    else:
        print("下一步:")
        print("  python set_user.py       # 创建用户")
        print("  python start.py          # CLI")
        print("  python start_web.py      # Web UI")
    print()


if __name__ == "__main__":
    main()
