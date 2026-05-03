"""
AgentMemory tool.py — 将 AgentMemory 包装成本项目可调用的工具
"""
import sys
import os
import json
from pathlib import Path

# 确保能导入 src/memory.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.memory import AgentMemory

from run.tool import register_tool
from skills._common import err, truncate

# 单例记忆实例
_mem = None

def _get_memory():
    """获取单例 AgentMemory 实例。

    存储路径: users/<name>/agent_memory.db (由 VOTX_USER_DIR 确定)
    注意: 本项目覆写了 AgentMemory 的默认路径 (~/.agent-memory/memory.db)，
          改用用户目录下的 agent_memory.db，实现用户级隔离。
    """
    global _mem
    if _mem is None:
        user_dir = os.environ.get("VOTX_USER_DIR", "")
        if user_dir:
            db_dir = Path(user_dir)
        else:
            # 回退：从 skills 位置推算
            db_dir = Path(__file__).resolve().parent.parent.parent / "users" / "default"
        db_dir.mkdir(parents=True, exist_ok=True)
        _mem = AgentMemory(db_path=str(db_dir / "agent_memory.db"))
    return _mem

def mem_remember(content: str, tags: str = "", confidence: float = 1.0, expires_in_days: int = None) -> str:
    """记住一条事实
    
    Args:
        content: 要记住的事实内容
        tags: 逗号分隔的标签
        confidence: 置信度 0-1
        expires_in_days: 自动过期天数，为空不过期
    """
    try:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        mem = _get_memory()
        fact_id = mem.remember(content, tags=tag_list, confidence=confidence, expires_in_days=expires_in_days)
        return f"OK: 已记住 (id={fact_id})"
    except Exception as e:
        return err(f"记忆失败: {e}")

def mem_recall(query: str, limit: int = 5, tags: str = "", min_confidence: float = 0) -> str:
    """搜索回忆事实
    
    Args:
        query: 搜索关键词
        limit: 最多返回条数
        tags: 逗号分隔的标签筛选
        min_confidence: 最低置信度
    """
    try:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        mem = _get_memory()
        facts = mem.recall(query, limit=limit, tags=tag_list or None, min_confidence=min_confidence)
        if not facts:
            return "没有找到相关记忆"
        lines = []
        for i, f in enumerate(facts, 1):
            lines.append(f"{i}. [{', '.join(f.tags)}] {f.content} (置信度: {f.confidence})")
        return truncate("\n".join(lines))
    except Exception as e:
        return err(f"搜索失败: {e}")

def mem_learn(action: str, context: str, outcome: str, insight: str) -> str:
    """从经验中学习
    
    Args:
        action: 做了什么
        context: 场景/主题
        outcome: 结果: positive/negative/neutral
        insight: 学到的教训
    """
    try:
        mem = _get_memory()
        lesson_id = mem.learn(action, context, outcome, insight)
        return f"OK: 已记录教训 (id={lesson_id})"
    except Exception as e:
        return err(f"学习记录失败: {e}")

def mem_get_lessons(context: str = "", outcome: str = "", limit: int = 5) -> str:
    """获取经验教训
    
    Args:
        context: 按场景筛选
        outcome: 按结果筛选: positive/negative/neutral
        limit: 最多返回条数
    """
    try:
        mem = _get_memory()
        ctx = context if context else None
        out = outcome if outcome else None
        lessons = mem.get_lessons(context=ctx, outcome=out, limit=limit)
        if not lessons:
            return "没有找到相关教训"
        lines = []
        for i, l in enumerate(lessons, 1):
            emoji = "✅" if l.outcome == "positive" else "❌" if l.outcome == "negative" else "➖"
            lines.append(f"{i}. {emoji} [{l.context}] {l.action}")
            lines.append(f"   教训: {l.insight}")
        return truncate("\n".join(lines))
    except Exception as e:
        return err(f"获取教训失败: {e}")

def mem_track_entity(name: str, entity_type: str = "person", attributes: str = "{}") -> str:
    """追踪一个实体（人/项目等）
    
    Args:
        name: 实体名称
        entity_type: 实体类型: person/project/company/tool
        attributes: JSON 格式的属性字典
    """
    try:
        attr_dict = json.loads(attributes) if isinstance(attributes, str) else attributes
        mem = _get_memory()
        entity_id = mem.track_entity(name, entity_type, attr_dict)
        return f"OK: 已追踪实体「{name}」(id={entity_id})"
    except Exception as e:
        return err(f"追踪实体失败: {e}")

def mem_get_entity(name: str, entity_type: str = "person") -> str:
    """获取实体信息
    
    Args:
        name: 实体名称
        entity_type: 实体类型
    """
    try:
        mem = _get_memory()
        entity = mem.get_entity(name, entity_type)
        if entity:
            attrs = json.dumps(entity.attributes, ensure_ascii=False)
            return f"实体: {entity.name} ({entity.entity_type})\n属性: {attrs}\n首次记录: {entity.first_seen}"
        return f"未找到实体: {name}"
    except Exception as e:
        return err(f"查询实体失败: {e}")

def mem_stats() -> str:
    """查看记忆统计"""
    try:
        mem = _get_memory()
        stats = mem.stats()
        return f"📊 记忆统计:\n- 活跃事实: {stats.get('active_facts', 0)}\n- 已替换事实: {stats.get('superseded_facts', 0)}\n- 教训: {stats.get('lessons', 0)}\n- 实体: {stats.get('entities', 0)}"
    except Exception as e:
        return err(f"获取统计失败: {e}")

def register():
    """向 ToolRunner 注册所有记忆工具"""
    schemas = [
        {
            "type": "function",
            "function": {
                "name": "mem_remember",
                "description": "记住一条事实信息，跨会话持久化存储。当用户告诉你个人信息、偏好、重要事项时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "要记住的事实内容"},
                        "tags": {"type": "string", "description": "逗号分隔的标签，如 偏好,沟通"},
                        "confidence": {"type": "number", "description": "置信度 0-1"},
                        "expires_in_days": {"type": "integer", "description": "自动过期天数，不填不过期"}
                    },
                    "required": ["content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mem_recall",
                "description": "搜索回忆已记住的事实。当需要回忆关于某事的之前记住的信息时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "limit": {"type": "integer", "description": "最多返回条数，默认 5"},
                        "tags": {"type": "string", "description": "逗号分隔的标签筛选"},
                        "min_confidence": {"type": "number", "description": "最低置信度"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mem_learn",
                "description": "记录经验教训（成功/失败）。当从操作中学到了什么时使用，避免重复犯错。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "做了什么操作"},
                        "context": {"type": "string", "description": "场景或主题"},
                        "outcome": {"type": "string", "enum": ["positive", "negative", "neutral"], "description": "结果"},
                        "insight": {"type": "string", "description": "学到的教训"}
                    },
                    "required": ["action", "context", "outcome", "insight"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mem_get_lessons",
                "description": "获取已记录的经验教训。按场景或结果筛选。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "context": {"type": "string", "description": "按场景筛选（可选）"},
                        "outcome": {"type": "string", "enum": ["positive", "negative", "neutral"], "description": "按结果筛选（可选）"},
                        "limit": {"type": "integer", "description": "最多返回条数，默认 5"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mem_track_entity",
                "description": "追踪一个人、项目或实体及其属性。当用户介绍自己、团队、项目时使用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "实体名称"},
                        "entity_type": {"type": "string", "enum": ["person", "project", "company", "tool"], "description": "实体类型"},
                        "attributes": {"type": "string", "description": "JSON 格式的属性字典，如 {\"角色\":\"老板\",\"时区\":\"EST\"}"}
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mem_get_entity",
                "description": "查询已追踪实体的信息。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "实体名称"},
                        "entity_type": {"type": "string", "description": "实体类型"}
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "mem_stats",
                "description": "查看记忆系统的统计信息（事实数、教训数、实体数）。",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]
    
    handlers = {
        "mem_remember": mem_remember,
        "mem_recall": mem_recall,
        "mem_learn": mem_learn,
        "mem_get_lessons": mem_get_lessons,
        "mem_track_entity": mem_track_entity,
        "mem_get_entity": mem_get_entity,
        "mem_stats": mem_stats,
    }
    
    for schema in schemas:
        name = schema["function"]["name"]
        register_tool(schema, handlers[name])
