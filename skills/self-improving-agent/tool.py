"""自主学习工具 — 记录学习/错误/功能请求到 .learnings/"""
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from run.tool import register_tool
from skills._common import err, truncate, safe_path


def _learnings_dir(base_dir: str = "") -> Path | None:
    """获取 .learnings/ 目录，默认在用户目录下"""
    if base_dir.strip():
        p = safe_path(base_dir.strip())
        if p is None:
            return None
        d = Path(p) / ".learnings"
    else:
        user_dir = os.environ.get("KESEPAIN_USER_DIR")
        if not user_dir:
            return None
        d = Path(user_dir) / ".learnings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _init_file(filepath: Path, header: str):
    """不存在则创建并写入头部"""
    if not filepath.exists():
        filepath.write_text(header, encoding="utf-8")


def _next_id(filepath: Path, prefix: str) -> str:
    """生成下一个 ID"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    pattern = re.compile(rf"^## \[{prefix}-{today}-(\d+)\]")
    max_n = 0
    if filepath.exists():
        try:
            for line in filepath.read_text(encoding="utf-8").splitlines():
                m = pattern.match(line)
                if m:
                    max_n = max(max_n, int(m.group(1)))
        except Exception:
            pass
    return f"{prefix}-{today}-{max_n + 1:03d}"


def log_learning(summary: str, category: str = "correction", details: str = "",
                 suggested_action: str = "", area: str = "backend",
                 priority: str = "medium", related_files: str = "",
                 tags: str = "", base_dir: str = "") -> str:
    """记录学习到 .learnings/LEARNINGS.md"""
    d = _learnings_dir(base_dir)
    if d is None:
        return err("无法确定 .learnings/ 目录")
    fp = d / "LEARNINGS.md"
    _init_file(fp, "# Learnings\n\n**Categories**: correction | insight | knowledge_gap | best_practice\n\n---\n")

    eid = _next_id(fp, "LRN")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    valid_cats = {"correction", "insight", "knowledge_gap", "best_practice"}
    if category not in valid_cats:
        category = "correction"

    entry = (
        f"## [{eid}] {category}\n\n"
        f"**Logged**: {now}\n"
        f"**Priority**: {priority}\n"
        f"**Status**: pending\n"
        f"**Area**: {area}\n\n"
        f"### Summary\n{summary}\n\n"
        f"### Details\n{details or summary}\n\n"
        f"### Suggested Action\n{suggested_action or '待定'}\n\n"
        f"### Metadata\n"
        f"- Source: conversation\n"
        f"- Related Files: {related_files or 'N/A'}\n"
        f"- Tags: {tags or 'general'}\n\n---\n"
    )
    fp.open("a", encoding="utf-8").write(entry)
    return f"OK: 已记录学习 {eid} → {fp}"


def log_error(command: str, error_message: str, context: str = "",
              area: str = "backend", reproducible: str = "unknown",
              related_files: str = "", base_dir: str = "") -> str:
    """记录错误到 .learnings/ERRORS.md"""
    d = _learnings_dir(base_dir)
    if d is None:
        return err("无法确定 .learnings/ 目录")
    fp = d / "ERRORS.md"
    _init_file(fp, "# Errors\n\nCommand failures and integration errors.\n\n---\n")

    eid = _next_id(fp, "ERR")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = (
        f"## [{eid}] {command}\n\n"
        f"**Logged**: {now}\n"
        f"**Priority**: high\n"
        f"**Status**: pending\n"
        f"**Area**: {area}\n\n"
        f"### Summary\n{command} 执行失败\n\n"
        f"### Error\n```\n{error_message[:2000]}\n```\n\n"
        f"### Context\n- Command: {command}\n{context or '- 无额外上下文'}\n\n"
        f"### Suggested Fix\n待分析\n\n"
        f"### Metadata\n"
        f"- Reproducible: {reproducible}\n"
        f"- Related Files: {related_files or 'N/A'}\n\n---\n"
    )
    fp.open("a", encoding="utf-8").write(entry)
    return f"OK: 已记录错误 {eid} → {fp}"


def log_feature_request(capability: str, user_context: str = "",
                        complexity: str = "medium", area: str = "backend",
                        priority: str = "medium", base_dir: str = "") -> str:
    """记录功能请求到 .learnings/FEATURE_REQUESTS.md"""
    d = _learnings_dir(base_dir)
    if d is None:
        return err("无法确定 .learnings/ 目录")
    fp = d / "FEATURE_REQUESTS.md"
    _init_file(fp, "# Feature Requests\n\nCapabilities requested by the user.\n\n---\n")

    eid = _next_id(fp, "FEAT")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = (
        f"## [{eid}] {capability}\n\n"
        f"**Logged**: {now}\n"
        f"**Priority**: {priority}\n"
        f"**Status**: pending\n"
        f"**Area**: {area}\n\n"
        f"### Requested Capability\n{capability}\n\n"
        f"### User Context\n{user_context or '未提供'}\n\n"
        f"### Complexity Estimate\n{complexity}\n\n"
        f"### Suggested Implementation\n待定\n\n"
        f"### Metadata\n- Frequency: first_time\n\n---\n"
    )
    fp.open("a", encoding="utf-8").write(entry)
    return f"OK: 已记录功能请求 {eid} → {fp}"


def read_learnings(file_name: str = "", filter_area: str = "",
                   filter_priority: str = "", base_dir: str = "") -> str:
    """读取 .learnings/ 中的记录，显示待处理条目和最近记录"""
    d = _learnings_dir(base_dir)
    if d is None:
        return err("无法确定 .learnings/ 目录")

    all_files = {
        "LEARNINGS.md": "学习",
        "ERRORS.md": "错误",
        "FEATURE_REQUESTS.md": "功能请求",
    }
    if file_name.strip():
        target = file_name.strip()
        if target not in all_files:
            return err(f"无效文件名: {target}，可选: {', '.join(all_files.keys())}")
        all_files = {target: all_files[target]}

    lines_out = []
    for fname, flabel in all_files.items():
        fp = d / fname
        if not fp.exists():
            lines_out.append(f"📄 {fname} — 尚未创建")
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            lines_out.append(f"📄 {fname} — 读取失败")
            continue

        entries = [e for e in content.split("\n---\n") if e.strip().startswith("## [")]
        pending = sum(1 for e in entries if "**Status**: pending" in e)
        lines_out.append(f"## {flabel} ({fname}) — {len(entries)} 条 / {pending} 待处理")

        for entry in entries[-3:]:
            title_m = re.search(r"^## \[([^\]]+)\]\s*(.+)", entry, re.MULTILINE)
            status_m = re.search(r"\*\*Status\*\*:\s*(\w+)", entry)
            priority_m = re.search(r"\*\*Priority\*\*:\s*(\w+)", entry)
            area_m = re.search(r"\*\*Area\*\*:\s*(\w+)", entry)

            fa = area_m.group(1) if area_m else ""
            fp_ = priority_m.group(1) if priority_m else ""
            if filter_area.strip() and fa != filter_area.strip():
                continue
            if filter_priority.strip() and fp_ != filter_priority.strip():
                continue

            if title_m:
                sid = title_m.group(1)
                stitle = title_m.group(2).strip()
                sstatus = status_m.group(1) if status_m else "?"
                lines_out.append(f"  [{sid}] {stitle} | {fp_} | {fa} | {sstatus}")

    return truncate("\n".join(lines_out)) if lines_out else "(无记录)"


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "log_learning",
            "description": (
                "将学习记录写入 .learnings/LEARNINGS.md。用于记录：用户纠正、新发现的洞察、"
                "知识空白、最佳实践。category 可选: correction/insight/knowledge_gap/best_practice"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "一句话描述学到的内容"},
                    "category": {"type": "string", "description": "分类: correction/insight/knowledge_gap/best_practice"},
                    "details": {"type": "string", "description": "完整上下文（可选，默认用 summary）"},
                    "suggested_action": {"type": "string", "description": "建议的改进措施"},
                    "area": {"type": "string", "description": "领域: frontend/backend/infra/tests/docs/config"},
                    "priority": {"type": "string", "description": "优先级: low/medium/high/critical"},
                    "related_files": {"type": "string", "description": "相关文件路径"},
                    "tags": {"type": "string", "description": "逗号分隔的标签"},
                    "base_dir": {"type": "string", "description": ".learnings/ 基础目录（可选，默认用户目录）"},
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_error",
            "description": "将错误记录写入 .learnings/ERRORS.md。用于记录命令失败、异常、超时等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "执行的命令/操作名称"},
                    "error_message": {"type": "string", "description": "错误输出或异常信息"},
                    "context": {"type": "string", "description": "额外上下文（环境、参数等）"},
                    "area": {"type": "string", "description": "领域: frontend/backend/infra/tests/docs/config"},
                    "reproducible": {"type": "string", "description": "是否可复现: yes/no/unknown"},
                    "related_files": {"type": "string", "description": "相关文件路径"},
                    "base_dir": {"type": "string", "description": ".learnings/ 基础目录（可选）"},
                },
                "required": ["command", "error_message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_feature_request",
            "description": "将用户的功能请求记录写入 .learnings/FEATURE_REQUESTS.md",
            "parameters": {
                "type": "object",
                "properties": {
                    "capability": {"type": "string", "description": "用户想要的功能/能力"},
                    "user_context": {"type": "string", "description": "用户为什么需要这个功能"},
                    "complexity": {"type": "string", "description": "复杂度估计: simple/medium/complex"},
                    "area": {"type": "string", "description": "领域: frontend/backend/infra/tests/docs/config"},
                    "priority": {"type": "string", "description": "优先级: low/medium/high/critical"},
                    "base_dir": {"type": "string", "description": ".learnings/ 基础目录（可选）"},
                },
                "required": ["capability"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_learnings",
            "description": (
                "读取 .learnings/ 中的学习记录。不指定 file_name 时显示所有文件的概要。"
                "可按 area 和 priority 筛选。默认显示最近 3 条记录。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "文件名: LEARNINGS.md / ERRORS.md / FEATURE_REQUESTS.md（可选）"},
                    "filter_area": {"type": "string", "description": "按领域筛选: frontend/backend/infra/tests/docs/config"},
                    "filter_priority": {"type": "string", "description": "按优先级筛选: low/medium/high/critical"},
                    "base_dir": {"type": "string", "description": ".learnings/ 基础目录（可选）"},
                },
                "required": [],
            },
        },
    },
]

HANDLERS = {
    "log_learning": log_learning,
    "log_error": log_error,
    "log_feature_request": log_feature_request,
    "read_learnings": read_learnings,
}


def register():
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
