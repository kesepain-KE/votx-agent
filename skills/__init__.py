"""skills 工具包 — 按 agentskills.io 标准自动发现并加载所有 Skill

agentskills.io 标准 (https://agentskills.io/specification):
    skill-name/
    ├── SKILL.md    ← 必需：YAML frontmatter(name+description) + Markdown 指引
    ├── scripts/    ← 可选：内部脚本
    ├── references/ ← 可选：参考文档
    └── assets/     ← 可选：模板/静态资源

本项目扩展：
    tool.py  — 可选：含 register()，注册 OpenAI function calling schema + handler
    有 tool.py → 工具可被 LLM 调用
    无 tool.py → 纯指令 Skill，SKILL.md 正文注入 system prompt

发现规则：
    1. 先扫描 plugins/ (内置技能，origin=builtin)
    2. 再扫描 skills/ (用户技能，origin=user)
    3. 同名冲突优先内置，除非用户技能 SKILL.md frontmatter 设 override: true
    _ 开头的目录/文件视为内部模块，不当作 Skill。
"""
import contextvars
import importlib.util
import re
import sys
from pathlib import Path


def _parse_skill_md(path: Path) -> dict:
    """解析 SKILL.md frontmatter，返回完整元数据 dict。"""
    text = path.read_text(encoding="utf-8")
    result: dict = {
        "name": path.parent.name,
        "description": "",
        "body": text.strip(),
        "version": "",
        "category": "",
        "enabled": True,
        "override": False,
    }
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2].strip()
            result["body"] = body

            # name
            m = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
            if m:
                result["name"] = m.group(1).strip()

            # description
            m = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
            if m:
                result["description"] = m.group(1).strip().strip('"')

            # version
            m = re.search(r"^version:\s*(.+)$", fm, re.MULTILINE)
            if m:
                result["version"] = m.group(1).strip().strip('"')

            # category
            m = re.search(r"^category:\s*(.+)$", fm, re.MULTILINE)
            if m:
                result["category"] = m.group(1).strip()

            # enabled
            m = re.search(r"^enabled:\s*(.+)$", fm, re.MULTILINE)
            if m:
                val = m.group(1).strip().lower()
                result["enabled"] = val not in ("false", "no", "0")

            # override
            m = re.search(r"^override:\s*(.+)$", fm, re.MULTILINE)
            if m:
                val = m.group(1).strip().lower()
                result["override"] = val in ("true", "yes", "1")

    return result


_last_skills_info: list[dict] = []

# 共享上下文：因 register_all() 用 importlib 加载 tool.py 可能产生独立模块实例，
# 需通过 skills 模块的 ContextVar 传递上下文，确保每个并发会话有独立的上下文副本。
_auto_improve_ctx: contextvars.ContextVar = contextvars.ContextVar("auto_improve_ctx", default=None)
_task_plan_ctx: contextvars.ContextVar = contextvars.ContextVar("task_plan_ctx", default=None)


def get_cached_skills_info() -> list[dict]:
    """返回上次 register_all() 缓存的技能摘要列表"""
    return list(_last_skills_info)


def _load_tool_module(tool_file: Path, rel: Path, base_dir: Path, force_reload: bool = False):
    """动态加载 tool.py 并调用 register()。"""
    mod_name = "skill_" + str(rel).replace("/", "_").replace("\\", "_").replace("-", "_").replace(".", "_") + "_tool"
    try:
        if force_reload and mod_name in sys.modules:
            del sys.modules[mod_name]
        spec = importlib.util.spec_from_file_location(mod_name, str(tool_file.resolve()))
        if spec is None or spec.loader is None:
            print(f"[Skill] 加载失败: {rel}/tool.py — spec 无效")
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "register"):
            mod.register()
    except Exception as e:
        print(f"[Skill] 加载失败: {rel}/tool.py — {e}")


def _scan_directory(scan_dir: Path, origin: str, registered_names: set, force_reload: bool = False) -> list[dict]:
    """扫描一个目录下所有 SKILL.md，注册 tool.py，返回 instruction_skills 列表。"""
    instruction_skills: list[dict] = []

    for skmd in sorted(scan_dir.glob("**/SKILL.md")):
        skill_dir = skmd.parent
        if skill_dir.name.startswith("_"):
            continue

        meta = _parse_skill_md(skmd)
        skill_name = meta["name"]
        skill_key = skill_name.lower()

        # 冲突检查（仅 user 技能需要检查）
        if origin == "user" and skill_key in registered_names and not meta["override"]:
            print(f"[Skill] 跳过 {skill_name}: plugins/ 已注册同名技能（设 override: true 可覆盖）")
            continue

        # enabled: false → 完全跳过
        if not meta["enabled"]:
            print(f"[Skill] 跳过 {skill_name}: enabled=false")
            continue

        # 加载 tool.py
        tool_file = skill_dir / "tool.py"
        if tool_file.is_file():
            rel = skill_dir.relative_to(scan_dir)
            _load_tool_module(tool_file, rel, scan_dir, force_reload)

        # 收集 SKILL.md 摘要
        body = meta.get("body", "")
        if body:
            has_tools = (skill_dir / "tool.py").exists()
            skill_type = "🔧 工具型" if has_tools else "📋 指令型"
            desc = meta.get("description", "")
            summary_line = f"- **{skill_name}** ({skill_type}): {desc}"

            instruction_skills.append({
                "name": skill_name,
                "description": desc,
                "summary": summary_line,
                "has_tools": has_tools,
                "body": body,
                "origin": origin,
                "version": meta.get("version", ""),
                "category": meta.get("category", ""),
            })

        registered_names.add(skill_key)

    return instruction_skills


def register_all(force_reload: bool = False, clear_registry: bool = True) -> list[dict]:
    """扫描 plugins/ + skills/ 下 SKILL.md → 加载 tool.py → 返回指令 Skill 列表

    Returns:
        list[dict]: [{"name", "description", "body", "origin", "summary", ...}, ...]
    """
    global _last_skills_info
    skills_dir = Path(__file__).parent
    project_root = skills_dir.parent
    plugins_dir = project_root / "plugins"

    if clear_registry:
        from run.tool import clear_tool_registry
        clear_tool_registry()

    # 把每个 skill/plugin 目录加入 sys.path（供 skill 内部 import scripts.xxx 等）
    for scan_dir in (plugins_dir, skills_dir):
        if not scan_dir.is_dir():
            continue
        for skmd in scan_dir.glob("**/SKILL.md"):
            skill_dir = skmd.parent
            if skill_dir.name.startswith("_"):
                continue
            d_str = str(skill_dir.resolve())
            if d_str not in sys.path:
                sys.path.insert(0, d_str)

    instruction_skills: list[dict] = []
    registered_names: set = set()

    # 1. 先扫 plugins/ (内置技能，优先级高)
    if plugins_dir.is_dir():
        instruction_skills.extend(
            _scan_directory(plugins_dir, "builtin", registered_names, force_reload)
        )

    # 2. 再扫 skills/ (用户技能)
    instruction_skills.extend(
        _scan_directory(skills_dir, "user", registered_names, force_reload)
    )

    _last_skills_info = instruction_skills
    return instruction_skills
