#!/usr/bin/env python3
"""votx-agent 全平台更新脚本

比对本地 version.json 与 GitHub main 分支上的 version.json，
将最新源码克隆到临时目录，备份当前应用，同步框架文件，保留用户数据，
然后刷新运行环境。

全平台通用（Linux / macOS / Windows），不依赖 rsync。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Iterable


APP_NAME = "votx-agent"
DEFAULT_REPO_URL = "https://github.com/kesepain-KE/votx-agent.git"
DEFAULT_BRANCH = "main"
VERSION_URL_TEMPLATE = (
    f"https://raw.githubusercontent.com/kesepain-KE/votx-agent/{{branch}}/version.json"
)
BACKUP_KEEP = 2

ROOT = Path(__file__).resolve().parent

# ── 排除规则 ─────────────────────────────────────────────────────
# 规则:
#   name/  → 路径「任意层」出现该名字的目录都会被排除（及其子文件）
#   name   → 根目录下精确匹配该名字的文件/目录才被排除
#   path/to/name → 相对该路径才被排除（暂不支持，以防混淆用全路径匹配）
MAIN_EXCLUDES = [
    # 版本控制
    ".git/",
    # 虚拟环境
    ".venv/",
    "build_env/",
    # 用户数据
    "users/",
    "skills/",
    # 构建产物
    "build/",
    "dist/",
    "web/node_modules/",
    "web/dist/",
    # 缓存
    "__pycache__/",
    "tmp/",
    # 备份
    ".backups/",
    # 运行时配置（用户专属，不覆盖）
    ".env",
    ".session_secret",
    "message/config.json",
    "message/config.local.json",
    "message/identity/identity_map.json",
    "message/push_queue/",
    # 交互式处理（走单独逻辑）
    "config/",
    "knowledge/",
    # 本地副本
    "使用手册-AI/",
]

BACKUP_EXCLUDES = [
    ".git/",
    ".venv/",
    "build_env/",
    ".backups/",
    "users/",
    "skills/",
    "build/",
    "dist/",
    "web/node_modules/",
    "web/dist/",
    "tmp/",
    "__pycache__/",
    "message/push_queue/",
]


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════


class UpdateError(RuntimeError):
    pass


def green(text: str) -> str:
    return f"\033[0;32m{text}\033[0m"


def yellow(text: str) -> str:
    return f"\033[1;33m{text}\033[0m"


def red(text: str) -> str:
    return f"\033[0;31m{text}\033[0m"


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    dry_run: bool = False,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd))
    if dry_run and not capture:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    kwargs: dict = {"text": True}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    return subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        check=True,
        **kwargs,
    )


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def require_commands(names: Iterable[str]) -> None:
    missing = [name for name in names if not command_exists(name)]
    if missing:
        raise UpdateError(f"缺少必需命令: {', '.join(missing)}")


def find_compose_command() -> list[str] | None:
    if command_exists("docker"):
        try:
            run(["docker", "compose", "version"], capture=True)
            return ["docker", "compose"]
        except Exception:
            pass
    if command_exists("docker-compose"):
        try:
            run(["docker-compose", "--version"], capture=True)
            return ["docker-compose"]
        except Exception:
            pass
    return None


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise UpdateError(f"{path} 不是 JSON 对象")
    return data


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "votx-agent-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise UpdateError(f"远程 JSON 不是对象: {url}")
    return data


def parse_version(value: str) -> tuple[int, ...]:
    text = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)*", text):
        raise UpdateError(f"无效版本号: {value!r}")
    return tuple(int(part) for part in text.split("."))


def compare_versions(left: str, right: str) -> int:
    a = parse_version(left)
    b = parse_version(right)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def ask_yes_no(prompt: str, *, default: bool, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not is_interactive():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    answer = input(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def ask_choice(
    prompt: str,
    choices: dict[str, str],
    *,
    default: str,
    assume_yes: bool,
) -> str:
    if assume_yes or not is_interactive():
        return default
    print(prompt)
    for key, label in choices.items():
        mark = " (默认)" if key == default else ""
        print(f"  {key}) {label}{mark}")
    while True:
        answer = input("> ").strip().lower()
        if not answer:
            return default
        if answer in choices:
            return answer
        print("请选择: " + ", ".join(choices))


def tree_digest(path: Path) -> str:
    """计算目录/文件的 SHA256 摘要，用于判断是否有实质性差异。"""
    if not path.exists():
        return ""
    if path.is_file():
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    h = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = item.relative_to(path).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(item.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def paths_differ(left: Path, right: Path) -> bool:
    return tree_digest(left) != tree_digest(right)


# ═══════════════════════════════════════════════════════════════════
# 纯 Python 目录同步（替代 rsync）
# ═══════════════════════════════════════════════════════════════════


def _parse_excludes(excludes: Iterable[str]) -> tuple[set[str], set[str]]:
    """解析排除规则为 (目录模式, 文件模式)。

    规则:
      "dir/"       → 路径任意层出现该目录名即排除
      ".env"       → 根目录下精确匹配该名称
      "path/file"  → 相对路径精确匹配
    """
    dir_patterns: set[str] = set()
    file_patterns: set[str] = set()
    for pattern in excludes:
        p = pattern.replace("\\", "/")
        if p.endswith("/"):
            dir_patterns.add(p.rstrip("/"))
        else:
            file_patterns.add(p)
    return dir_patterns, file_patterns


def _is_excluded(
    rel: str,
    dir_patterns: set[str],
    file_patterns: set[str],
) -> bool:
    """判断 rel（Unix 风格相对路径）是否被排除。"""
    rel = rel.replace("\\", "/")
    # 根文件名/目录名精确匹配
    if rel in file_patterns:
        return True
    # 任意层目录名匹配
    parts = rel.split("/")
    for pattern in dir_patterns:
        if pattern in parts:
            return True
    return False


def _walk_sync(
    source: Path,
    target: Path,
    *,
    dir_patterns: set[str],
    file_patterns: set[str],
    dry_run: bool,
) -> None:
    """正向同步: source 下的文件复制到 target。"""
    for root, dirs, files in os.walk(str(source)):
        root_path = Path(root)
        rel = root_path.relative_to(source).as_posix()
        if rel == ".":
            rel = ""

        # 被排除的目录 → 不进入
        if rel and _is_excluded(rel, dir_patterns, file_patterns):
            dirs.clear()
            continue

        target_dir = target / rel if rel else target
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            rel_file = f"{rel}/{f}" if rel else f
            if _is_excluded(rel_file, dir_patterns, file_patterns):
                continue
            src_file = root_path / f
            dst_file = target_dir / f
            if dry_run:
                print(f"[dry-run]  复制  {_short(src_file)}")
            else:
                shutil.copy2(src_file, dst_file, follow_symlinks=False)


def _walk_delete(
    source: Path,
    target: Path,
    *,
    dir_patterns: set[str],
    file_patterns: set[str],
    dry_run: bool,
) -> None:
    """反向删除: 删除 target 中 source 没有的文件/目录（排除项不动）。"""
    for root, dirs, files in os.walk(str(target), topdown=False):
        root_path = Path(root)
        rel = root_path.relative_to(target).as_posix()
        if rel == ".":
            rel = ""

        if rel and _is_excluded(rel, dir_patterns, file_patterns):
            continue

        # 删文件
        for f in files:
            rel_file = f"{rel}/{f}" if rel else f
            if _is_excluded(rel_file, dir_patterns, file_patterns):
                continue
            src_file = source / rel_file
            if not src_file.exists():
                if dry_run:
                    print(f"[dry-run]  删除  {_short(root_path / f)}")
                else:
                    (root_path / f).unlink()

        # 删空目录（排除项不动）
        if rel and not _is_excluded(rel, dir_patterns, file_patterns):
            src_dir = source / rel
            if not src_dir.exists():
                try:
                    if dry_run:
                        print(f"[dry-run]  删除目录  {_short(root_path)}")
                    else:
                        root_path.rmdir()
                except OSError:
                    pass  # 非空或占用，跳过


def _short(path: Path) -> str:
    """输出简短相对路径（从 ROOT 开始算）。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sync_directory(
    source: Path,
    target: Path,
    *,
    delete: bool = False,
    excludes: Iterable[str] = (),
    dry_run: bool = False,
) -> None:
    """纯 Python 目录同步。

    行为等价于 rsync -a [--delete] [--exclude=...] source/ target/

    参数:
        source:  源目录
        target:  目标目录
        delete:  是否删除 target 中 source 没有的文件/目录
        excludes: 排除规则列表（支持 name/ 目录模式）
        dry_run:  仅打印不执行
    """
    dir_patterns, file_patterns = _parse_excludes(excludes)

    if not source.is_dir():
        raise UpdateError(f"源目录不存在: {source}")

    if delete:
        print(f"  同步 {_short(source)} -> {_short(target)} (含删除)")
    else:
        print(f"  同步 {_short(source)} -> {_short(target)}")

    target.mkdir(parents=True, exist_ok=True)
    _walk_sync(source, target, dir_patterns=dir_patterns, file_patterns=file_patterns, dry_run=dry_run)
    if delete:
        _walk_delete(source, target, dir_patterns=dir_patterns, file_patterns=file_patterns, dry_run=dry_run)


# ═══════════════════════════════════════════════════════════════════
# 核心流程
# ═══════════════════════════════════════════════════════════════════


def make_backup(dry_run: bool) -> Path | None:
    """创建当前项目完整备份（跳过 BACKUP_EXCLUDES 中的内容）。"""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = ROOT / ".backups" / f"update-{timestamp}"
    if dry_run:
        print(f"[dry-run] 将创建备份: {backup_dir}")
        return None

    backup_dir.mkdir(parents=True, exist_ok=False)
    sync_directory(ROOT, backup_dir, delete=False, excludes=BACKUP_EXCLUDES)
    prune_backups()
    print(green(f"备份已创建: {backup_dir}"))
    return backup_dir


def prune_backups() -> None:
    """保留最近 BACKUP_KEEP 个备份，删除更旧的。"""
    backups_root = ROOT / ".backups"
    if not backups_root.is_dir():
        return
    backups = sorted(
        [p for p in backups_root.iterdir() if p.is_dir() and p.name.startswith("update-")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[BACKUP_KEEP:]:
        shutil.rmtree(old, ignore_errors=True)
        print(yellow(f"已移除旧备份: {old}"))


def clone_latest(repo_url: str, branch: str, work_dir: Path) -> Path:
    """浅克隆指定分支到临时目录。"""
    target = work_dir / "source"
    run(["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(target)])
    return target


def sync_main_source(source: Path, *, dry_run: bool) -> None:
    """同步框架代码，跳过 MAIN_EXCLUDES 中的内容。"""
    print(green("正在同步框架文件..."))
    sync_directory(source, ROOT, delete=True, excludes=MAIN_EXCLUDES, dry_run=dry_run)


def handle_config(source: Path, *, assume_yes: bool, dry_run: bool) -> None:
    """交互式处理 config/ 目录：保持或覆盖。"""
    new_config = source / "config"
    local_config = ROOT / "config"
    if not new_config.exists():
        return

    if not local_config.exists():
        print(green("正在安装 config/ 目录"))
        sync_directory(new_config, local_config, delete=True, dry_run=dry_run)
        return

    if not paths_differ(new_config, local_config):
        print("config/ 无变化")
        return

    choice = ask_choice(
        "config/ 与最新版本不同，请选择处理方式:",
        {
            "o": "用最新版本覆盖 config/",
            "k": "保留本地 config/",
        },
        default="o",
        assume_yes=assume_yes,
    )
    if choice == "o":
        sync_directory(new_config, local_config, delete=True, dry_run=dry_run)
        print(green("config/ 已更新"))
    else:
        print(yellow("跳过 config/"))


def handle_knowledge(source: Path, *, assume_yes: bool, dry_run: bool) -> None:
    """交互式处理知识库：合并、跳过或完全替换。"""
    new_knowledge = source / "knowledge"
    local_knowledge = ROOT / "knowledge"
    if not new_knowledge.exists():
        return

    choice = ask_choice(
        "请选择 knowledge/ 的更新方式:",
        {
            "1": "合并最新文件，保留本地额外文件",
            "2": "跳过 knowledge/",
            "3": "完全替换为最新版本",
        },
        default="1",
        assume_yes=assume_yes,
    )
    if choice == "1":
        local_knowledge.mkdir(parents=True, exist_ok=True)
        sync_directory(new_knowledge, local_knowledge, dry_run=dry_run)
        print(green("knowledge/ 已合并"))
    elif choice == "2":
        print(yellow("跳过 knowledge/"))
    else:
        if dry_run:
            print(f"[dry-run] 将替换 {local_knowledge}")
        else:
            if local_knowledge.exists():
                shutil.rmtree(local_knowledge)
            local_knowledge.mkdir(parents=True, exist_ok=True)
        sync_directory(new_knowledge, local_knowledge, dry_run=dry_run)
        print(green("knowledge/ 已替换"))


def migrate_user_skeletons(*, dry_run: bool) -> None:
    """补齐已有用户目录骨架，不覆盖用户已有文件。"""
    users_dir = ROOT / "users"
    if not users_dir.is_dir():
        return
    candidates = [
        path for path in sorted(users_dir.iterdir())
        if path.is_dir() and (path / "config.json").is_file()
    ]
    if not candidates:
        return
    if dry_run:
        print(f"[dry-run] 将补齐 {len(candidates)} 个用户的目录骨架")
        return
    try:
        sys.path.insert(0, str(ROOT))
        from set_user import ensure_user_skeleton  # type: ignore[import-untyped]

        for user_dir in candidates:
            ensure_user_skeleton(user_dir)
        print(green(f"用户目录骨架已补齐: {len(candidates)} 个用户"))
    except Exception as exc:
        print(yellow(f"用户目录补齐跳过: {exc}"))


def detect_mode(args: argparse.Namespace) -> str:
    if args.docker:
        return "docker"
    if args.native:
        return "native"

    compose = find_compose_command()
    if compose:
        try:
            result = run(compose + ["ps", "-q"], capture=True)
            if result.stdout.strip():
                return "docker"
        except Exception:
            pass
        if is_interactive():
            if ask_yes_no("使用 Docker 后更新命令？", default=False, assume_yes=False):
                return "docker"
    return "native"


def post_update(mode: str, *, dry_run: bool, skip_post_update: bool) -> None:
    """更新后刷新环境。

    - Docker: rebuild + restart
    - Native: python setup.py --skip-env
    """
    if skip_post_update:
        print(yellow("跳过后更新命令"))
        return

    if mode == "docker":
        compose = find_compose_command()
        if not compose:
            raise UpdateError("Docker 模式需要 Docker Compose")
        run(compose + ["build"], dry_run=dry_run)
        run(compose + ["up", "-d"], dry_run=dry_run)
        print(green("Docker 服务已重建并重启"))
        return

    # Native: 使用 setup.py 安装/验证依赖
    print(green("正在刷新本地环境..."))
    run([sys.executable, str(ROOT / "setup.py"), "--skip-env"], dry_run=dry_run)
    print(green("本地环境已刷新"))


# ═══════════════════════════════════════════════════════════════════
# 版本比对与入口
# ═══════════════════════════════════════════════════════════════════


def load_versions(remote_url: str) -> tuple[str, str]:
    """读取本地与远程 version.json，返回 (local_version, remote_version)。"""
    local_path = ROOT / "version.json"
    if not local_path.is_file():
        raise UpdateError(f"未找到本地版本文件: {local_path}")

    local = read_json(local_path)
    remote = fetch_json(remote_url)

    local_version = str(local.get("version", "")).strip()
    remote_version = str(remote.get("version", "")).strip()
    if not local_version or not remote_version:
        raise UpdateError("本地和远程 version.json 都必须包含 version 字段")
    parse_version(local_version)
    parse_version(remote_version)
    return local_version, remote_version


def should_update(
    local_version: str,
    remote_version: str,
    *,
    force: bool,
    assume_yes: bool,
) -> bool:
    cmp_result = compare_versions(local_version, remote_version)
    print(f"本地版本  : {local_version}")
    print(f"远程版本  : {remote_version}")

    if cmp_result == 0:
        if force:
            print(yellow("版本相同，强制重新安装 main 分支。"))
            return True
        return ask_yes_no("版本相同，仍要从 main 重新安装？", default=False, assume_yes=assume_yes)

    if cmp_result < 0:
        print(green(f"发现更新: {local_version} -> {remote_version}"))
        return ask_yes_no("是否继续更新？", default=True, assume_yes=assume_yes)

    print(yellow(f"本地版本更新于远程: {local_version} > {remote_version}"))
    print(yellow("这可能导致降级或覆盖开发构建。"))
    return ask_yes_no("是否继续？", default=False, assume_yes=assume_yes)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="更新 votx-agent（全平台）")
    parser.add_argument("--check", action="store_true", help="仅检查本地和远程版本")
    parser.add_argument("--force", action="store_true", help="版本相同时强制重新安装")
    parser.add_argument("--yes", "-y", action="store_true", help="使用默认选项确认所有提示")
    parser.add_argument("--dry-run", action="store_true", help="仅展示计划的操作，不实际修改")
    parser.add_argument(
        "--skip-post-update",
        action="store_true",
        help="跳过安装依赖/重建 Docker 等后处理",
    )
    parser.add_argument("--docker", action="store_true", help="使用 Docker 后更新命令")
    parser.add_argument("--native", action="store_true", help="使用原生后更新命令")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git 仓库 URL")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Git 分支")
    parser.add_argument(
        "--remote-version-url",
        default="",
        help="远程 version.json URL 覆盖",
    )
    args = parser.parse_args(argv)
    if args.docker and args.native:
        parser.error("--docker 和 --native 不能同时使用")
    return args


def _print_platform_warning() -> None:
    """Windows 下提示需要 git，但赋予用户选择权。"""
    system = platform.system().lower()
    if system == "windows":
        if not command_exists("git"):
            print(yellow("⚠ Windows 上未检测到 git 命令"))
            print(yellow("  请安装 Git for Windows: https://git-scm.com/download/win"))
            print(yellow("  安装后请重启终端再试。"))
            raise SystemExit(1)
        print(yellow("ℹ Windows 模式 — 确保 git 命令可从当前终端访问。"))
    elif system == "darwin":
        print(green("ℹ macOS 模式"))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        # ── 平台检查 ──────────────────────────────────────────────
        # 不再阻止非 Linux 平台，但 Windows 需要 git
        _print_platform_warning()

        # ── 版本比对 ──────────────────────────────────────────────
        remote_url = args.remote_version_url or VERSION_URL_TEMPLATE.format(
            branch=args.branch
        )
        local_version, remote_version = load_versions(remote_url)

        if args.check:
            cmp_result = compare_versions(local_version, remote_version)
            if cmp_result == 0:
                print(green(f"已是最新: {local_version}"))
            elif cmp_result < 0:
                print(yellow(f"发现更新: {local_version} -> {remote_version}"))
            else:
                print(yellow(f"本地版本更新于远程: {local_version} > {remote_version}"))
            return 0

        if not should_update(
            local_version, remote_version, force=args.force, assume_yes=args.yes
        ):
            print(yellow("更新已取消"))
            return 0

        # ── 环境检查 ──────────────────────────────────────────────
        # 需要 git 来克隆远程仓库；不再需要 rsync
        require_commands(["git"])

        mode = detect_mode(args)
        print(f"后更新模式: {mode}")

        # ── 执行更新 ──────────────────────────────────────────────
        with tempfile.TemporaryDirectory(prefix="votx-agent-update-") as tmp:
            source = clone_latest(args.repo_url, args.branch, Path(tmp))
            make_backup(args.dry_run)
            sync_main_source(source, dry_run=args.dry_run)
            handle_config(source, assume_yes=args.yes, dry_run=args.dry_run)
            handle_knowledge(source, assume_yes=args.yes, dry_run=args.dry_run)
            migrate_user_skeletons(dry_run=args.dry_run)

        # ── 后处理 ────────────────────────────────────────────────
        post_update(
            mode, dry_run=args.dry_run, skip_post_update=args.skip_post_update
        )

        print(green("更新完成"))
        return 0

    except subprocess.CalledProcessError as exc:
        print(red(f"命令失败: {' '.join(exc.cmd)}"), file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return 1
    except UpdateError as exc:
        print(red(str(exc)), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        print(yellow("更新已中断"))
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
