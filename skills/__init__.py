"""skills 工具包 — 按标准骨架自动发现并注册所有 Skill

标准骨架 (agentskills.io / Claude Code Plugin):
    skill-name/
    ├── SKILL.md    ← 身份证：name + description + 使用指引
    ├── tool.py     ← 执行体：包含 register()，注册 tool_call schema + handler
    ├── scripts/    ← 可选：内部脚本
    ├── references/ ← 可选：参考文档
    └── assets/     ← 可选：模板/静态资源

发现规则：递归扫描 skills/ 下所有 SKILL.md，加载同目录的 tool.py。
_ 开头的目录/文件视为内部模块，不当作 Skill。
"""
import importlib.util
from pathlib import Path


def register_all():
    """扫描 SKILL.md → 加载 tool.py → 调用 register()"""
    import sys
    skills_dir = Path(__file__).parent

    # 把每个 skill 目录加入 sys.path（供 skill 内部 import scripts.xxx 等）
    for skmd in sorted(skills_dir.glob("**/SKILL.md")):
        skill_dir = skmd.parent
        if skill_dir.name.startswith("_"):
            continue
        d_str = str(skill_dir.resolve())
        if d_str not in sys.path:
            sys.path.insert(0, d_str)

    # 加载 tool.py 并注册
    for skmd in sorted(skills_dir.glob("**/SKILL.md")):
        skill_dir = skmd.parent
        if skill_dir.name.startswith("_"):
            continue

        tool_file = skill_dir / "tool.py"
        if not tool_file.is_file():
            continue

        rel = skill_dir.relative_to(skills_dir)
        mod_name = "skills." + str(rel).replace("/", "_").replace("\\", "_").replace("-", "_") + "_tool"

        try:
            spec = importlib.util.spec_from_file_location(mod_name, str(tool_file.resolve()))
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"[Skill] 加载失败: {rel}/tool.py — {e}")
            continue

        if hasattr(mod, "register"):
            try:
                mod.register()
            except Exception as e:
                print(f"[Skill] 注册失败: {rel}/tool.py — {e}")
