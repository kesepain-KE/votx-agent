# -*- coding: utf-8 -*-
"""Ontology 知识图谱工具 — 实体/关系 CRUD + 校验"""
import json
import sys
from pathlib import Path

from run.tool import register_tool
from skills._common import err, truncate

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 默认存储路径（项目级共享）
DEFAULT_GRAPH = str(_PROJECT_ROOT / "memory" / "ontology" / "graph.jsonl")
DEFAULT_SCHEMA = str(_PROJECT_ROOT / "memory" / "ontology" / "schema.yaml")

# 导入 ontology 核心逻辑
sys.path.insert(0, str(_PROJECT_ROOT / "skills" / "ontology" / "scripts"))
try:
    from ontology import (
        create_entity, get_entity, query_entities, list_entities,
        update_entity, delete_entity, create_relation, get_related,
        validate_graph, append_schema,
    )
except ImportError:
    # 兼容直接引用
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ontology",
        str(_PROJECT_ROOT / "skills" / "ontology" / "scripts" / "ontology.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    create_entity = mod.create_entity
    get_entity = mod.get_entity
    query_entities = mod.query_entities
    list_entities = mod.list_entities
    update_entity = mod.update_entity
    delete_entity = mod.delete_entity
    create_relation = mod.create_relation
    get_related = mod.get_related
    validate_graph = mod.validate_graph
    append_schema = mod.append_schema


def _ensure_dir(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


# ---- 工具函数 ----

def _ontology_create(type_name: str, properties: str, graph_path: str = "", entity_id: str = "") -> str:
    """Create an ontology entity"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    _ensure_dir(gp)
    try:
        props = json.loads(properties) if isinstance(properties, str) else properties
    except json.JSONDecodeError as e:
        return err(f"properties 不是合法 JSON: {e}")
    eid = entity_id.strip() or None
    try:
        entity = create_entity(type_name, props, gp, eid)
        return f"Created: {json.dumps(entity, ensure_ascii=False, indent=2)}"
    except Exception as e:
        return err(f"创建实体失败: {e}")


def _ontology_query(type_name: str, where: str = "", graph_path: str = "") -> str:
    """Query entities by type and optional filter"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    try:
        w = json.loads(where) if where.strip() else {}
    except json.JSONDecodeError as e:
        return err(f"where 不是合法 JSON: {e}")
    try:
        results = query_entities(type_name, w, gp)
        if not results:
            return f"No {type_name} entities found matching the filter."
        return truncate(json.dumps(results, ensure_ascii=False, indent=2), 8000)
    except Exception as e:
        return err(f"查询失败: {e}")


def _ontology_get(entity_id: str, graph_path: str = "") -> str:
    """Get an entity by ID"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    try:
        entity = get_entity(entity_id, gp)
        if entity:
            return json.dumps(entity, ensure_ascii=False, indent=2)
        return f"Entity '{entity_id}' not found."
    except Exception as e:
        return err(f"获取实体失败: {e}")


def _ontology_list(type_name: str, graph_path: str = "") -> str:
    """List all entities of a type"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    try:
        results = list_entities(type_name, gp)
        if not results:
            return f"No {type_name} entities found."
        return truncate(json.dumps(results, ensure_ascii=False, indent=2), 8000)
    except Exception as e:
        return err(f"列举失败: {e}")


def _ontology_update(entity_id: str, properties: str, graph_path: str = "") -> str:
    """Update an entity's properties"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    try:
        props = json.loads(properties) if isinstance(properties, str) else properties
    except json.JSONDecodeError as e:
        return err(f"properties 不是合法 JSON: {e}")
    try:
        entity = update_entity(entity_id, props, gp)
        if entity:
            return f"Updated: {json.dumps(entity, ensure_ascii=False, indent=2)}"
        return f"Entity '{entity_id}' not found."
    except Exception as e:
        return err(f"更新失败: {e}")


def _ontology_delete(entity_id: str, graph_path: str = "") -> str:
    """Delete an entity"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    try:
        if delete_entity(entity_id, gp):
            return f"Entity '{entity_id}' deleted."
        return f"Entity '{entity_id}' not found."
    except Exception as e:
        return err(f"删除失败: {e}")


def _ontology_relate(from_id: str, rel_type: str, to_id: str, properties: str = "", graph_path: str = "") -> str:
    """Create a relation between two entities"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    try:
        props = json.loads(properties) if properties.strip() else {}
    except json.JSONDecodeError as e:
        return err(f"properties 不是合法 JSON: {e}")
    try:
        rel = create_relation(from_id, rel_type, to_id, props, gp)
        return f"Relation created: {json.dumps(rel, ensure_ascii=False)}"
    except Exception as e:
        return err(f"创建关系失败: {e}")


def _ontology_related(entity_id: str, rel_type: str = "", graph_path: str = "", direction: str = "outgoing") -> str:
    """Get related entities"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    if direction not in ("outgoing", "incoming"):
        return err('direction 必须是 "outgoing" 或 "incoming"')
    try:
        results = get_related(entity_id, rel_type or None, gp, direction)
        if not results:
            return f"No related entities found for '{entity_id}'."
        return truncate(json.dumps(results, ensure_ascii=False, indent=2), 8000)
    except Exception as e:
        return err(f"获取关联实体失败: {e}")


def _ontology_validate(graph_path: str = "", schema_path: str = "") -> str:
    """Validate the graph against schema"""
    gp = graph_path.strip() or DEFAULT_GRAPH
    sp = schema_path.strip() or DEFAULT_SCHEMA
    try:
        errors = validate_graph(gp, sp)
        if not errors:
            return "Graph is valid. No constraint violations found."
        return truncate("\n".join(f"  - {e}" for e in errors), 4000)
    except Exception as e:
        return err(f"校验失败: {e}")


# ---- Schema ----

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "ontology_create",
            "description": "创建知识图谱实体。type_name 为类型（Person/Project/Task/Event 等），properties 为 JSON 属性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type_name": {"type": "string", "description": "实体类型，如 Person, Project, Task, Event, Document 等"},
                    "properties": {"type": "string", "description": "JSON 格式的属性，如 {\"name\":\"Alice\",\"email\":\"alice@example.com\"}"},
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选，默认 memory/ontology/graph.jsonl）"},
                    "entity_id": {"type": "string", "description": "实体 ID（可选，留空自动生成）"},
                },
                "required": ["type_name", "properties"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontology_query",
            "description": "查询指定类型的实体，支持可选的过滤条件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type_name": {"type": "string", "description": "实体类型"},
                    "where": {"type": "string", "description": "JSON 过滤条件，如 {\"status\":\"active\"}（可选）"},
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选）"},
                },
                "required": ["type_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontology_get",
            "description": "通过 ID 获取单个实体详情。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 ID"},
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选）"},
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontology_list",
            "description": "列出指定类型的所有实体。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type_name": {"type": "string", "description": "实体类型"},
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选）"},
                },
                "required": ["type_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontology_update",
            "description": "更新实体的属性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 ID"},
                    "properties": {"type": "string", "description": "JSON 格式的要更新的属性"},
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选）"},
                },
                "required": ["entity_id", "properties"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontology_delete",
            "description": "删除实体（追加墓碑标记，不物理擦除历史记录）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 ID"},
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选）"},
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontology_relate",
            "description": "在两个实体之间创建关系。",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_id": {"type": "string", "description": "源实体 ID"},
                    "rel_type": {"type": "string", "description": "关系类型，如 has_owner, has_task, blocks 等"},
                    "to_id": {"type": "string", "description": "目标实体 ID"},
                    "properties": {"type": "string", "description": "JSON 格式的关系属性（可选）"},
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选）"},
                },
                "required": ["from_id", "rel_type", "to_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontology_related",
            "description": "获取与某个实体关联的其他实体。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 ID"},
                    "rel_type": {"type": "string", "description": "关系类型过滤（可选）"},
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选）"},
                    "direction": {"type": "string", "description": "方向: outgoing（发出）或 incoming（指向），默认 outgoing"},
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ontology_validate",
            "description": "校验整个图谱是否满足 schema 约束。",
            "parameters": {
                "type": "object",
                "properties": {
                    "graph_path": {"type": "string", "description": "图谱 JSONL 路径（可选）"},
                    "schema_path": {"type": "string", "description": "schema YAML 路径（可选）"},
                },
            },
        },
    },
]


# ---- handlers ----

HANDLERS = {
    "ontology_create": _ontology_create,
    "ontology_query": _ontology_query,
    "ontology_get": _ontology_get,
    "ontology_list": _ontology_list,
    "ontology_update": _ontology_update,
    "ontology_delete": _ontology_delete,
    "ontology_relate": _ontology_relate,
    "ontology_related": _ontology_related,
    "ontology_validate": _ontology_validate,
}


def register():
    for schema in SCHEMAS:
        name = schema["function"]["name"]
        register_tool(schema, HANDLERS[name])
