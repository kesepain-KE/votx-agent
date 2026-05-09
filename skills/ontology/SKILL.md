---
name: ontology
description: 结构化知识图谱，跨会话记住实体和关系。用户说"记住/保存XX信息"、"XX和YY什么关系"、"谁负责XX"、"列出所有XX"、"关联XX和YY"、"更新/删除XX"时使用。支持 Person/Project/Task/Event/Document 等类型。
---

# Ontology — 结构化知识图谱

有类型约束的知识图谱，用于结构化记忆。把信息存成「实体」和「关系」，支持校验。

## 核心概念

```
Entity: { id, type, properties, relations, created, updated }
Relation: { from_id, relation_type, to_id, properties }
```

所有修改在提交前都会校验类型约束。

## 什么时候用

| 触发词 | 动作 |
|--------|------|
| "记住/保存某人/项目/任务…" | `ontology_create` |
| "关于 XX 我知道什么" | `ontology_query` / `ontology_get` |
| "把 X 和 Y 关联起来" | `ontology_relate` |
| "显示项目 Z 的所有任务" | `ontology_related` |
| "什么依赖 X？" | `ontology_related` (方向: incoming) |
| "列出所有任务" | `ontology_list` |
| "更新/删除 XX" | `ontology_update` / `ontology_delete` |
| "校验数据" | `ontology_validate` |

## 核心类型

- **人/组织**: Person, Organization
- **工作**: Project, Task, Goal
- **时间/地点**: Event, Location
- **信息**: Document, Message, Thread, Note
- **资源**: Account, Device, Credential（只存引用，不存密钥）
- **元**: Action, Policy

完整类型定义见 `references/schema.md`

## 工具列表

| 工具名 | 功能 |
|--------|------|
| `ontology_create` | 创建实体 |
| `ontology_query` | 按类型+条件查询实体 |
| `ontology_get` | 按 ID 获取实体 |
| `ontology_list` | 列出某类型所有实体 |
| `ontology_update` | 更新实体属性 |
| `ontology_delete` | 删除实体（追加墓碑） |
| `ontology_relate` | 创建实体间关系 |
| `ontology_related` | 获取关联实体 |
| `ontology_validate` | 校验图谱约束 |

## 存储

默认路径：`memory/ontology/graph.jsonl`（项目级共享）
存储格式：JSONL（追加模式，不覆盖历史）

## 使用示例

- 记住一个人: `ontology_create(type_name="Person", properties='{"name":"Alice","role":"设计师"}')`
- 查询任务: `ontology_query(type_name="Task", where='{"status":"open"}')`
- 关联项目和任务: `ontology_relate(from_id="proj_001", rel_type="has_task", to_id="task_001")`
- 谁负责什么: `ontology_related(entity_id="p_001", rel_type="has_owner", direction="incoming")`
