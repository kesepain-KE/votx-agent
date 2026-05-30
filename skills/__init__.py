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
    3. 同名冲突：用户技能设 override: true 可覆盖内置技能（提示词 + tool.py）
    4. 大小写不敏感、下划线/短横线等价
    _ 开头的目录/文件视为内部模块，不当作 Skill。
"""
import contextvars
import importlib.util
import json
import os
import re
import sys
import yaml
from pathlib import Path

# 核心保护名单 — 不可禁用/物理删除
CORE_LOCKED: set[str] = {
    "file", "shell", "time", "network",
    "task_plan", "auto_improve", "skill_creator",
    "task_time", "kb_retriever",
}


def _normalize_name(name: str) -> str:
    """标准化技能名：小写 + 短横线/下划线统一为下划线，用于冲突检测。"""
    return name.lower().replace("-", "_")


def _parse_skill_md(path: Path, origin: str = "") -> dict:
    """解析 SKILL.md frontmatter，返回完整元数据 dict。

    Args:
        path: SKILL.md 文件路径
        origin: 调用方传入的 origin（'builtin' 或 'user'），不从 frontmatter 读取
    """
    text = path.read_text(encoding="utf-8")
    result: dict = {
        "name": path.parent.name,
        "description": "",
        "body": text.strip(),
        "version": "",
        "category": "",
        "enabled": True,
        "override": False,
        "origin": origin,
    }
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1])
                if isinstance(fm, dict):
                    result["name"] = str(fm.get("name", result["name"])).strip()
                    result["description"] = str(fm.get("description", "")).strip()
                    result["version"] = str(fm.get("version", "")).strip()
                    result["category"] = str(fm.get("category", "")).strip()
                    enabled_val = fm.get("enabled", True)
                    if isinstance(enabled_val, bool):
                        result["enabled"] = enabled_val
                    elif isinstance(enabled_val, str):
                        result["enabled"] = enabled_val.lower() not in ("false", "no", "0")
                    override_val = fm.get("override", False)
                    if isinstance(override_val, bool):
                        result["override"] = override_val
                    elif isinstance(override_val, str):
                        result["override"] = override_val.lower() in ("true", "yes", "1")
            except yaml.YAMLError:
                pass  # 保留默认值
            result["body"] = parts[2].strip()
    return result


_last_skills_info: list[dict] = []

# 共享上下文：因 register_all() 用 importlib 加载 tool.py 可能产生独立模块实例，
# 需通过 skills 模块的 ContextVar 传递上下文，确保每个并发会话有独立的上下文副本。
_auto_improve_ctx: contextvars.ContextVar = contextvars.ContextVar("auto_improve_ctx", default=None)
_task_plan_ctx: contextvars.ContextVar = contextvars.ContextVar("task_plan_ctx", default=None)

# 记录每个技能已注册的工具名: "origin/skill_key" → [tool_names]（供 override 时精确清除）
_origin_tools: dict[str, list[str]] = {}

# tool_name → normalized_skill_key 反向映射（供 load_tool_schemas 按禁用技能过滤）
_tool_skill_map: dict[str, str] = {}


def get_cached_skills_info() -> list[dict]:
    """返回上次 register_all() 缓存的技能摘要列表（未按用户过滤）"""
    return list(_last_skills_info)


def load_disabled_skills(user_dir: str) -> set:
    """从用户 config.json 读取禁用的内置技能列表。

    CORE_LOCKED 中的技能即使出现在 disabled_builtin 中也会被忽略。
    """
    config_path = os.path.join(user_dir, "config.json")
    try:
        if os.path.isfile(config_path):
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
            skills_cfg = config.get("skills", {})
            raw = skills_cfg.get("disabled_builtin", [])
            if isinstance(raw, list):
                # 过滤掉核心保护技能
                return {_normalize_name(str(name)) for name in raw if _normalize_name(str(name)) not in CORE_LOCKED}
    except Exception:
        pass
    return set()


def get_filtered_skills_info(user_dir: str = "") -> list[dict]:
    """返回按当前用户 disabled_builtin 过滤后的技能摘要列表。

    Args:
        user_dir: 用户目录路径。空字符串时不进行用户级过滤。
    """
    all_skills = get_cached_skills_info()
    if not user_dir:
        return all_skills
    disabled = load_disabled_skills(user_dir)
    if not disabled:
        return all_skills
    return [
        s for s in all_skills
        if s.get("origin") != "builtin" or _normalize_name(s.get("name", "")) not in {
            _normalize_name(d) for d in disabled
        }
    ]


def unregister_skill_tools(skill_name: str, origin: str = "builtin"):
    """移除指定技能已注册的所有工具（供 override 使用）。

    使用复合 key "origin/skill_key" 精确匹配，只删除该技能的工具，
    不会影响其他技能（即使属于同一 origin）。
    """
    from run.tool import TOOL_REGISTRY
    composite_key = f"{origin}/{_normalize_name(skill_name)}"
    tool_names = _origin_tools.pop(composite_key, [])
    for tool_name in tool_names:
        TOOL_REGISTRY.pop(tool_name, None)
        _tool_skill_map.pop(tool_name, None)


def get_tool_skill_map() -> dict[str, str]:
    """返回 tool_name → skill_key 映射（供 load_tool_schemas 按禁用技能过滤）。"""
    return dict(_tool_skill_map)


def _load_tool_module(tool_file: Path, rel: Path, base_dir: Path, force_reload: bool = False) -> list[str]:
    """动态加载 tool.py 并调用 register()。返回注册的工具名列表。"""
    mod_name = "skill_" + str(rel).replace("/", "_").replace("\\", "_").replace("-", "_").replace(".", "_") + "_tool"
    try:
        if force_reload and mod_name in sys.modules:
            del sys.modules[mod_name]
        spec = importlib.util.spec_from_file_location(mod_name, str(tool_file.resolve()))
        if spec is None or spec.loader is None:
            print(f"[Skill] 加载失败: {rel}/tool.py — spec 无效")
            return []
        # 快照 TOOL_REGISTRY 现有 key 以追踪本技能注册的工具
        from run.tool import TOOL_REGISTRY
        before = set(TOOL_REGISTRY.keys())
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "register"):
            mod.register()
        after = set(TOOL_REGISTRY.keys())
        return list(after - before)
    except Exception as e:
        print(f"[Skill] 加载失败: {rel}/tool.py — {e}")
        return []


def _scan_directory(scan_dir: Path, origin: str, registered_names: set,
                    force_reload: bool = False, disabled_skills: set | None = None) -> list[dict]:
    """扫描一个目录下所有 SKILL.md，注册 tool.py，返回 instruction_skills 列表。

    Args:
        scan_dir: 要扫描的根目录
        origin: 'builtin' 或 'user'
        registered_names: 已注册的标准化名称集合
        force_reload: 是否强制重载模块
        disabled_skills: 被用户禁用的技能名集合（仅对 builtin 生效，CORE_LOCKED 免疫）
    """
    instruction_skills: list[dict] = []
    project_root = scan_dir.parent
    if disabled_skills is None:
        disabled_skills = set()

    for skmd in sorted(scan_dir.glob("**/SKILL.md")):
        skill_dir = skmd.parent
        if skill_dir.name.startswith("_"):
            continue

        meta = _parse_skill_md(skmd, origin=origin)
        skill_name = meta["name"]
        skill_key = _normalize_name(skill_name)

        # enabled: false → 完全跳过（适用于所有 origin）
        if not meta["enabled"]:
            print(f"[Skill] 跳过 {skill_name} ({origin}): enabled=false")
            continue

        # 用户禁用检查（仅对 builtin 生效，CORE_LOCKED 免疫）
        if origin == "builtin":
            if skill_key in {_normalize_name(d) for d in disabled_skills}:
                if skill_key not in CORE_LOCKED:
                    print(f"[Skill] 跳过 {skill_name} ({origin}): 用户已禁用")
                    continue

        # 冲突检查：用户技能 vs 已注册的内置技能
        if origin == "user" and skill_key in registered_names and not meta["override"]:
            print(f"[Skill] 跳过 {skill_name}: plugins/ 已注册同名技能（设 override: true 可覆盖）")
            continue

        # override: 用户覆盖内置技能时，先移除内置技能的工具
        if origin == "user" and skill_key in registered_names and meta["override"]:
            print(f"[Skill] {skill_name} 覆盖内置技能 (override=true)")
            unregister_skill_tools(skill_name, "builtin")

        # 加载 tool.py
        new_tools: list[str] = []
        tool_file = skill_dir / "tool.py"
        if tool_file.is_file():
            rel = skill_dir.relative_to(scan_dir)
            new_tools = _load_tool_module(tool_file, rel, scan_dir, force_reload)
        if new_tools:
            composite_key = f"{origin}/{skill_key}"
            _origin_tools.setdefault(composite_key, []).extend(new_tools)
            for t in new_tools:
                _tool_skill_map[t] = skill_key

        # 收集 SKILL.md 摘要
        body = meta.get("body", "")
        if body:
            has_tools = (skill_dir / "tool.py").exists()
            skill_type = "🔧 工具型" if has_tools else "📋 指令型"
            desc = meta.get("description", "")
            skill_path = skmd.relative_to(project_root).as_posix()
            summary_line = f"- **{skill_name}** ({skill_type}): {desc} — `{skill_path}`"
            # 覆盖标记
            if origin == "user" and meta.get("override"):
                summary_line += f" (已覆盖内置 `plugins/{skill_key}/SKILL.md`)"

            instruction_skills.append({
                "name": skill_name,
                "description": desc,
                "summary": summary_line,
                "has_tools": has_tools,
                "body": body,
                "origin": origin,
                "version": meta.get("version", ""),
                "category": meta.get("category", ""),
                "override": meta.get("override", False),
            })

        registered_names.add(skill_key)

    return instruction_skills


def register_all(force_reload: bool = False, clear_registry: bool = True) -> list[dict]:
    """扫描 plugins/ + skills/ 下 SKILL.md → 加载 tool.py → 返回指令 Skill 列表

    始终注册全部可用工具到 TOOL_REGISTRY（全局注册，不按用户过滤）。
    调用方如需按用户过滤，请使用 get_filtered_skills_info(user_dir)。

    Returns:
        list[dict]: [{"name", "description", "body", "origin", "summary", "override", ...}, ...]
    """
    global _last_skills_info, _origin_tools, _tool_skill_map
    skills_dir = Path(__file__).parent
    project_root = skills_dir.parent
    plugins_dir = project_root / "plugins"

    if clear_registry:
        from run.tool import clear_tool_registry
        clear_tool_registry()
        _origin_tools.clear()
        _tool_skill_map.clear()

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
