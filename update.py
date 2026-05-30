#!/usr/bin/env python3
"""Linux/Docker updater for votx-agent.

The updater compares the local version.json with the version.json on GitHub
main, clones the latest source into a temporary directory, backs up the current
application, syncs framework files, preserves user data, and then refreshes the
runtime environment.

This script intentionally does not support Windows.
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
from pathlib import Path
from typing import Iterable


APP_NAME = "votx-agent"
DEFAULT_REPO_URL = "https://github.com/kesepain-KE/votx-agent.git"
DEFAULT_BRANCH = "main"
VERSION_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/kesepain-KE/votx-agent/{branch}/version.json"
)
BACKUP_KEEP = 2

ROOT = Path(__file__).resolve().parent

MAIN_EXCLUDES = [
    ".git/",
    ".venv/",
    ".backups/",
    "users/",
    "skills/",
    ".env",
    ".session_secret",
    "message-runtime/",
    "message/config.local.json",
    "message/config.json",
    "message/identity/identity_map.json",
    "message/push_queue/",
    "tmp/",
    "knowledge/",
    "config/",
]

BACKUP_EXCLUDES = [
    ".git/",
    ".venv/",
    ".backups/",
    "users/",
    "skills/",
    "tmp/",
    "message/push_queue/",
]


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
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd))
    if dry_run and not capture:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=True,
    )


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def require_commands(names: Iterable[str]) -> None:
    missing = [name for name in names if not command_exists(name)]
    if missing:
        raise UpdateError("Missing required command(s): " + ", ".join(missing))


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
        raise UpdateError(f"{path} is not a JSON object")
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
        raise UpdateError(f"Remote JSON is not an object: {url}")
    return data


def parse_version(value: str) -> tuple[int, ...]:
    text = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.\d+)*", text):
        raise UpdateError(f"Invalid version: {value!r}")
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
        mark = " (default)" if key == default else ""
        print(f"  {key}) {label}{mark}")
    while True:
        answer = input("> ").strip().lower()
        if not answer:
            return default
        if answer in choices:
            return answer
        print("Please choose one of: " + ", ".join(choices))


def tree_digest(path: Path) -> str:
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


def rsync_args(
    source: Path,
    target: Path,
    *,
    delete: bool = False,
    excludes: Iterable[str] = (),
    dry_run: bool = False,
) -> list[str]:
    cmd = ["rsync", "-a"]
    if delete:
        cmd.append("--delete")
    if dry_run:
        cmd.append("--dry-run")
    for pattern in excludes:
        cmd.extend(["--exclude", pattern])
    cmd.extend([str(source) + "/", str(target) + "/"])
    return cmd


def make_backup(dry_run: bool) -> Path | None:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = ROOT / ".backups" / f"update-{timestamp}"
    if dry_run:
        print(f"[dry-run] Would create backup: {backup_dir}")
        return None

    backup_dir.mkdir(parents=True, exist_ok=False)
    run(rsync_args(ROOT, backup_dir, excludes=BACKUP_EXCLUDES), cwd=ROOT)
    prune_backups()
    print(green(f"Backup created: {backup_dir}"))
    return backup_dir


def prune_backups() -> None:
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
        print(yellow(f"Removed old backup: {old}"))


def clone_latest(repo_url: str, branch: str, work_dir: Path) -> Path:
    target = work_dir / "source"
    run(["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(target)])
    return target


def sync_main_source(source: Path, *, dry_run: bool) -> None:
    print(green("Syncing framework files..."))
    run(
        rsync_args(source, ROOT, delete=True, excludes=MAIN_EXCLUDES, dry_run=dry_run),
        cwd=ROOT,
    )


def handle_config(source: Path, *, assume_yes: bool, dry_run: bool) -> None:
    new_config = source / "config"
    local_config = ROOT / "config"
    if not new_config.exists():
        return

    if not local_config.exists():
        print(green("Installing new config/ directory"))
        run(rsync_args(new_config, local_config, delete=True, dry_run=dry_run), cwd=ROOT)
        return

    if not paths_differ(new_config, local_config):
        print("config/ unchanged")
        return

    choice = ask_choice(
        "config/ differs from the latest version. What should the updater do?",
        {
            "o": "overwrite config/ with latest version",
            "k": "keep local config/",
        },
        default="o",
        assume_yes=assume_yes,
    )
    if choice == "o":
        run(rsync_args(new_config, local_config, delete=True, dry_run=dry_run), cwd=ROOT)
        print(green("config/ updated"))
    else:
        print(yellow("Skipped config/"))


def handle_knowledge(source: Path, *, assume_yes: bool, dry_run: bool) -> None:
    new_knowledge = source / "knowledge"
    local_knowledge = ROOT / "knowledge"
    if not new_knowledge.exists():
        return

    choice = ask_choice(
        "How should knowledge/ be updated?",
        {
            "1": "merge latest files into knowledge/ and keep local extra files",
            "2": "skip knowledge/",
            "3": "replace knowledge/ entirely with latest version",
        },
        default="1",
        assume_yes=assume_yes,
    )
    if choice == "1":
        local_knowledge.mkdir(parents=True, exist_ok=True)
        run(rsync_args(new_knowledge, local_knowledge, dry_run=dry_run), cwd=ROOT)
        print(green("knowledge/ merged"))
    elif choice == "2":
        print(yellow("Skipped knowledge/"))
    else:
        if dry_run:
            print(f"[dry-run] Would replace {local_knowledge}")
        else:
            if local_knowledge.exists():
                shutil.rmtree(local_knowledge)
            local_knowledge.mkdir(parents=True, exist_ok=True)
        run(rsync_args(new_knowledge, local_knowledge, dry_run=dry_run), cwd=ROOT)
        print(green("knowledge/ replaced"))


def handle_message_runtime(source: Path, *, assume_yes: bool, dry_run: bool) -> None:
    template = source / "message" / "config.example.json"
    runtime_dir = ROOT / "message-runtime"
    if not template.exists() or not runtime_dir.exists():
        return

    runtime_example = runtime_dir / "config.example.json"
    if runtime_example.exists() and not paths_differ(template, runtime_example):
        print("message-runtime/config.example.json unchanged")
        return

    choice = ask_choice(
        "message-runtime template differs from the latest version. Choose an action.",
        {
            "k": "keep message-runtime unchanged",
            "e": "update message-runtime/config.example.json only",
            "r": "backup and replace message-runtime/config.json with latest template",
        },
        default="k",
        assume_yes=assume_yes,
    )
    if choice == "k":
        print(yellow("Skipped message-runtime/"))
        return

    if choice == "e":
        if dry_run:
            print(f"[dry-run] Would copy {template} -> {runtime_example}")
        else:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template, runtime_example)
        print(green("message-runtime/config.example.json updated"))
        return

    runtime_config = runtime_dir / "config.json"
    backup_path = runtime_dir / f"config.json.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    if dry_run:
        print(f"[dry-run] Would backup {runtime_config} -> {backup_path}")
        print(f"[dry-run] Would copy {template} -> {runtime_config}")
    else:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        if runtime_config.exists():
            shutil.copy2(runtime_config, backup_path)
        shutil.copy2(template, runtime_config)
    print(green("message-runtime/config.json replaced"))


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
            if ask_yes_no("Use Docker post-update commands?", default=False, assume_yes=False):
                return "docker"
    return "native"


def post_update(mode: str, *, dry_run: bool, skip_post_update: bool) -> None:
    if skip_post_update:
        print(yellow("Skipped post-update commands"))
        return

    if mode == "docker":
        compose = find_compose_command()
        if not compose:
            raise UpdateError("Docker Compose is required for Docker mode")
        run(compose + ["build"], dry_run=dry_run)
        run(compose + ["up", "-d"], dry_run=dry_run)
        print(green("Docker service rebuilt and restarted"))
        return

    run(["bash", "install.sh", "--skip-user"], dry_run=dry_run)
    print(green("Native Linux environment refreshed"))


def load_versions(remote_url: str) -> tuple[str, str]:
    local_path = ROOT / "version.json"
    if not local_path.is_file():
        raise UpdateError(f"Local version file not found: {local_path}")

    local = read_json(local_path)
    remote = fetch_json(remote_url)

    local_version = str(local.get("version", "")).strip()
    remote_version = str(remote.get("version", "")).strip()
    if not local_version or not remote_version:
        raise UpdateError("Both local and remote version.json must contain a version field")
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
    print(f"Local version : {local_version}")
    print(f"Remote version: {remote_version}")

    if cmp_result == 0:
        if force:
            print(yellow("Versions match; forcing reinstall from main."))
            return True
        return ask_yes_no("Versions match. Reinstall from main anyway?", default=False, assume_yes=assume_yes)

    if cmp_result < 0:
        print(green(f"Update available: {local_version} -> {remote_version}"))
        return ask_yes_no("Proceed with update?", default=True, assume_yes=assume_yes)

    print(yellow(f"Local version is newer than remote: {local_version} > {remote_version}"))
    print(yellow("This may downgrade or replace a development build."))
    return ask_yes_no("Proceed anyway?", default=False, assume_yes=assume_yes)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update votx-agent on Linux/Docker.")
    parser.add_argument("--check", action="store_true", help="Only check local and remote versions.")
    parser.add_argument("--force", action="store_true", help="Allow reinstall when versions match.")
    parser.add_argument("--yes", "-y", action="store_true", help="Use default choices and confirm prompts.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned sync actions without modifying files.")
    parser.add_argument("--skip-post-update", action="store_true", help="Do not run install.sh or docker compose commands.")
    parser.add_argument("--docker", action="store_true", help="Run Docker post-update commands.")
    parser.add_argument("--native", action="store_true", help="Run native Linux post-update commands.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repository URL.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Git branch to clone.")
    parser.add_argument("--remote-version-url", default="", help="Override remote version.json URL.")
    args = parser.parse_args(argv)
    if args.docker and args.native:
        parser.error("--docker and --native cannot be used together")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if platform.system().lower() != "linux":
        print(red("update.py only supports Linux/Docker hosts. Windows is not supported."))
        return 1

    try:
        remote_url = args.remote_version_url or VERSION_URL_TEMPLATE.format(branch=args.branch)
        local_version, remote_version = load_versions(remote_url)

        if args.check:
            cmp_result = compare_versions(local_version, remote_version)
            if cmp_result == 0:
                print(green(f"Up to date: {local_version}"))
            elif cmp_result < 0:
                print(yellow(f"Update available: {local_version} -> {remote_version}"))
            else:
                print(yellow(f"Local version is newer: {local_version} > {remote_version}"))
            return 0

        if not should_update(
            local_version,
            remote_version,
            force=args.force,
            assume_yes=args.yes,
        ):
            print(yellow("Update cancelled"))
            return 0

        require_commands(["git", "rsync"])

        mode = detect_mode(args)
        print(f"Post-update mode: {mode}")

        with tempfile.TemporaryDirectory(prefix="votx-agent-update-") as tmp:
            source = clone_latest(args.repo_url, args.branch, Path(tmp))
            make_backup(args.dry_run)
            sync_main_source(source, dry_run=args.dry_run)
            handle_config(source, assume_yes=args.yes, dry_run=args.dry_run)
            handle_knowledge(source, assume_yes=args.yes, dry_run=args.dry_run)
            handle_message_runtime(source, assume_yes=args.yes, dry_run=args.dry_run)

        post_update(mode, dry_run=args.dry_run, skip_post_update=args.skip_post_update)
        print(green("Update complete"))
        return 0
    except subprocess.CalledProcessError as exc:
        print(red(f"Command failed: {' '.join(exc.cmd)}"), file=sys.stderr)
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
        print(yellow("Update interrupted"))
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
