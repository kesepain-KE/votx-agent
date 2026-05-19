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

发现规则：递归扫描 skills/ 下所有 SKILL.md。
_ 开头的目录/文件视为内部模块，不当作 Skill。
"""
import contextvars
import importlib.util
import re
from pathlib import Path


def _parse_skill_md(path: Path) -> tuple[str, str]:
    """解析 SKILL.md 返回 (name, body)。body 不含 YAML frontmatter。"""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2].strip()
            m = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
            name = m.group(1).strip() if m else path.parent.name
            return name, body
    return path.parent.name, text.strip()


_last_skills_info: list[dict] = []

# 共享上下文：因 register_all() 用 importlib 加载 tool.py 可能产生独立模块实例，
# 需通过 skills 模块的 ContextVar 传递上下文，确保每个并发会话有独立的上下文副本。
_auto_improve_ctx: contextvars.ContextVar = contextvars.ContextVar("auto_improve_ctx", default=None)
_task_plan_ctx: contextvars.ContextVar = contextvars.ContextVar("task_plan_ctx", default=None)


def get_cached_skills_info() -> list[dict]:
    """返回上次 register_all() 缓存的技能摘要列表"""
    return list(_last_skills_info)


def register_all(force_reload: bool = False, clear_registry: bool = True) -> list[dict]:
    """扫描 SKILL.md → 加载 tool.py（如有）→ 返回指令 Skill 列表

    Returns:
        list[dict]: [{"name": str, "description": str, "body": str}, ...]
        其中 body 是 SKILL.md 正文（不含 frontmatter），供 main.py 注入 system prompt。
    """
    global _last_skills_info
    import sys
    skills_dir = Path(__file__).parent

    if clear_registry:
        from run.tool import clear_tool_registry
        clear_tool_registry()

    # 把每个 skill 目录加入 sys.path（供 skill 内部 import scripts.xxx 等）
    for skmd in sorted(skills_dir.glob("**/SKILL.md")):
        skill_dir = skmd.parent
        if skill_dir.name.startswith("_"):
            continue
        d_str = str(skill_dir.resolve())
        if d_str not in sys.path:
            sys.path.insert(0, d_str)

    instruction_skills: list[dict] = []

    # 加载 tool.py 并注册，同时收集指令
    for skmd in sorted(skills_dir.glob("**/SKILL.md")):
        skill_dir = skmd.parent
        if skill_dir.name.startswith("_"):
            continue

        rel = skill_dir.relative_to(skills_dir)
        skill_name, body = _parse_skill_md(skmd)

        tool_file = skill_dir / "tool.py"
        if tool_file.is_file():
            # 有 tool.py → 注册工具
            mod_name = "skills." + str(rel).replace("/", "_").replace("\\", "_").replace("-", "_") + "_tool"
            try:
                if force_reload:
                    # 清理旧的模块缓存，避免 Python 模块缓存导致旧代码未刷新
                    if mod_name in sys.modules:
                        del sys.modules[mod_name]
                spec = importlib.util.spec_from_file_location(mod_name, str(tool_file.resolve()))
                if spec is None or spec.loader is None:
                    print(f"[Skill] 加载失败: {rel}/tool.py — spec 无效")
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "register"):
                    mod.register()
            except Exception as e:
                print(f"[Skill] 加载失败: {rel}/tool.py — {e}")
                continue

        # 收集 SKILL.md 摘要（不注入完整正文，遵循 agentskills.io 渐进披露）
        if body:
            text = skmd.read_text(encoding="utf-8")
            desc = ""
            if text.startswith("---\n"):
                parts = text.split("---\n", 2)
                if len(parts) >= 3:
                    m = re.search(r"^description:\s*(.+)$", parts[1], re.MULTILINE)
                    if m:
                        desc = m.group(1).strip().strip('"')

            # 判断 Skill 类型
            has_tools = (skill_dir / "tool.py").exists()
            skill_type = "🔧 工具型" if has_tools else "📋 指令型"

            # 紧凑摘要：1-2 行，仅 name + description + 类型
            summary_line = f"- **{skill_name}** ({skill_type}): {desc}"

            instruction_skills.append({
                "name": skill_name,
                "description": desc,
                "summary": summary_line,
                "has_tools": has_tools,
                "body": body,  # 保留完整正文供 on-demand 读取
            })

    _last_skills_info = instruction_skills
    return instruction_skills
