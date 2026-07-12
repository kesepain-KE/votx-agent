---
name: skill_creator
description: 创建或更新 VOTX Agent Skill 的指导技能。用于设计 SKILL.md、工具型或指令型 Skill、scripts/references/assets 资源、触发描述、渐进式披露结构，以及验证现有 Skill 是否适配框架。
---

# Skill Creator

设计、创建、更新和审查 VOTX Agent Skill。Skill 是包含 `SKILL.md` 及可选资源的独立能力包。

## 插件路径

`plugins/skill_creator/`

## Skill 类型

| 类型 | 结构 | 用途 |
|------|------|------|
| 工具型 | `SKILL.md` + `tool.py` | 注册可直接 function call 的工具 |
| 指令型 | `SKILL.md` | 注入领域流程、规范和知识导航 |

## 标准目录

```text
skill-name/
├── SKILL.md              # 必需
├── tool.py               # 工具型 Skill 可选/常用
├── scripts/              # 可重复执行的确定性脚本
├── references/           # 按需读取的详细文档
└── assets/               # 模板、图片、字体等输出资源
```

不要创建无必要的 README、安装指南、更新日志等重复文档。

## SKILL.md 最小格式

```markdown
---
name: skill_name
description: 说明能力、适用场景和触发条件。
---

# Skill 标题

核心流程与必要约束。
```

框架主要依赖 frontmatter 的 `name` 和 `description` 判断是否触发，因此描述必须包含“做什么”和“何时使用”。

## VOTX 推荐正文结构

根据复杂度选用以下章节，不要求机械堆满：

1. Skill 标题与目标
2. 插件相对路径
3. 注册工具及用途（工具型）
4. 参数、默认值和厂商差异
5. 结果格式与 artifact
6. 前置条件和配置
7. 标准工作流
8. 常见规范
9. 常见处理办法
10. 常见教训与限制
11. references/scripts/assets 导航

## 创建与更新流程

1. **理解使用场景**：收集会触发 Skill 的用户表达和具体任务。
2. **选择类型**：决定是工具型还是指令型，避免把纯流程硬做成工具。
3. **规划资源**：重复且确定的操作放 scripts；详细资料放 references；模板素材放 assets。
4. **读取现有实现**：更新已有 Skill 时，先读 `SKILL.md`、`tool.py` 和相邻插件风格。
5. **编写说明**：保持正文精炼，复杂细节通过 references 渐进披露。
6. **实现工具**：工具 schema 的 description 写清触发场景；参数说明与真实 handler 一致。
7. **验证**：Python 工具执行 `python -m py_compile <tool.py>`；检查 SKILL.md 路径、工具名和参数是否一致。
8. **迭代**：根据真实调用中的误触发、漏触发、参数错误继续调整。

## 工具型 Skill 注册规范

- 使用 `register_tool(schema, handler)` 注册。
- schema 中工具名必须与 handler 映射一致。
- `description` 写明能力和典型触发词，避免只写内部实现。
- `required` 只保留真正必需的参数。
- 厂商差异较大的参数（音色、格式、尺寸等）优先使用自由字符串并在 description 中给示例；框架内部协议值可保留 enum。
- 工具结果优先返回结构化 JSON；文件结果通过 artifact 暴露给前端。
- 异常返回 `ERROR:` 文本，不泄露堆栈和密钥。

## 渐进式披露

1. frontmatter 元数据始终在上下文中。
2. SKILL.md 正文仅在触发后加载。
3. references/scripts/assets 只在实际需要时读取或执行。

正文接近 500 行时应拆分。引用文件保持一层深度，并在 SKILL.md 中说明何时读取。

## 结果说明

本 Skill 是指令型技能，不注册工具。产出通常是：

- 新建或更新后的 Skill 目录；
- 标准化的 `SKILL.md`；
- 工具 schema/handler 设计说明；
- 验证结果与已知限制。

## 常见规范

- 能扩展现有 Skill 时不重复新建同类 Skill。
- 内置能力放 `plugins/`，用户扩展或实验能力放 `skills/`。
- Skill 名称清晰稳定，目录名建议使用小写下划线或短横线。
- references 中不要复制 SKILL.md 已有正文。

## 常见处理办法

- **工具不触发**：强化 frontmatter description 和 schema description 中的触发场景。
- **工具误触发**：明确边界、反例和优先级，例如“简单搜索不用深度研究”。
- **参数不兼容**：区分框架协议参数与厂商参数，减少不必要 enum。
- **正文过长**：把厂商表、API 文档和大量示例移入 references。
- **结果无法展示**：检查工具是否返回 `artifacts[]`。

## 常见教训

- frontmatter 描述是主要触发入口，把“何时使用”只写在正文里没有作用。
- SKILL.md 必须与实际 tool.py 保持一致，过期参数说明会直接误导调用。
- 不要为展示完整而堆砌常识；只保留模型执行任务时真正需要的信息。
- 新增脚本必须实际运行验证，不能只写不测。