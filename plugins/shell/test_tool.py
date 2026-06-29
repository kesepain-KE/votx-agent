import importlib.util
import sys
from itertools import count
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "plugins" / "shell" / "tool.py"


def load_shell_tool():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("plugins.shell.tool_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def shell_tool(tmp_path):
    mod = load_shell_tool()
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    mod.get_current_user_dir = lambda: str(user_dir)
    mod.check_sandbox = lambda p, allowed_roots=None: p
    mod.safe_path = lambda raw_path: Path(raw_path).resolve()
    mod.get_effective_tool_timeout = lambda default=120: 10
    mod._SESSION_CACHE.clear()
    return mod


def test_session_cd_and_cd_dash(shell_tool, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    nested = workspace / "nested"
    nested.mkdir()

    out1 = shell_tool.run_command(
        command=f'cd /d "{nested}" && pwd',
        working_dir=str(workspace),
        session_id="dev",
        reset_session=True,
    )
    assert out1 == str(nested)

    out2 = shell_tool.run_command(command="cd - && pwd", session_id="dev")
    assert out2 == str(workspace)


def test_session_export_with_spaces(shell_tool, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    shell_tool.run_command(
        command='export FOO="bar baz"',
        working_dir=str(workspace),
        session_id="dev",
        reset_session=True,
    )

    out = shell_tool.run_command(command="env", session_id="dev")
    assert "FOO=bar baz" in out


def test_or_and_semicolon_chain(shell_tool, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    out = shell_tool.run_command(
        command='python -c "import sys; sys.exit(1)" || python -c "print(42)"',
        working_dir=str(workspace),
    )
    assert "(exit=1)" in out
    assert "42" in out

    out2 = shell_tool.run_command(
        command='python -c "print(1)" ; python -c "print(2)"',
        working_dir=str(workspace),
    )
    assert out2.splitlines() == ["1", "2"]


def test_cd_segment_parser_and_empty_target(shell_tool, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    nested = workspace / "nested dir"
    nested.mkdir()
    user_dir = Path(shell_tool.get_current_user_dir())

    target, cd_only, err = shell_tool._parse_cd_segment(f'cd /d "{nested}"', str(workspace))
    assert err is None
    assert cd_only is False
    assert target == str(nested)

    home_target, err = shell_tool._resolve_cd_target("", str(workspace))
    assert err is None
    assert home_target == str(user_dir)

    empty_target, cd_only, err = shell_tool._parse_cd_segment("cd", str(workspace))
    assert empty_target is None
    assert cd_only is False
    assert err == "目录为空"


def test_session_store_prunes_oldest_and_keeps_active(shell_tool, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    user_dir = Path(shell_tool.get_current_user_dir())

    clock = count(1)
    shell_tool._utc_timestamp = lambda: float(next(clock))

    for idx in range(shell_tool._SESSION_MAX_COUNT):
        shell_tool._persist_session_state(
            str(user_dir),
            f"old-{idx:02d}",
            {"cwd": str(workspace), "env": {}, "history": []},
        )

    state = shell_tool._get_session_state(
        str(user_dir),
        "active",
        cwd_hint=str(workspace),
        reset_session=True,
    )
    assert state["cwd"] == str(workspace)

    session_path = user_dir / "history" / "shell_sessions.json"
    store = shell_tool.read_json_safe(session_path, default={})
    sessions = store["sessions"]

    assert len(sessions) == shell_tool._SESSION_MAX_COUNT
    assert "old-00" not in sessions
    assert "active" in sessions
    assert sessions["active"]["last_access"] > sessions["old-01"]["last_access"]
