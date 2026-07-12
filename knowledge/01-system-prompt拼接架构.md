# System Prompt 拼接架构

更新时间：2026-07-12

## 拼接顺序

`run.engine.build_system_prompt(root, user_dir)` 按当前源码依次拼接：

1. `users/<name>/self_soul.md`
2. `config/soul.md`（存在、非空且不是注释占位时）
3. 根目录 `AGENTS.md`
4. 当前用户未禁用的 Skill 摘要
5. 用户知识库 `users/<name>/knowledge/data_structure.md`
6. 全局知识库 `knowledge/data_structure.md`
7. auto_improve 永久层和临时层内容
8. `SESSION-STATE.md`（存在时）
9. 当前活跃任务计划

注意：用户人格当前先加入，随后才加入全局基座与 AGENTS。文档应描述实际顺序，不能沿用旧 旧基座人格路径 路径；当前文件名是 `config/soul.md`。

## Skill 注入

`register_all()` 注册插件工具。`get_filtered_skills_info(user_dir)` 根据用户 `skills.disabled_builtin` 过滤 Skill 摘要，并分成：

- 工具型 Skill：存在 `tool.py`，可 function call。
- 指令型 Skill：只有 `SKILL.md`，向模型提供工作流程。

完整 `SKILL.md` 不会全部塞入摘要；需要时由智能体读取对应文件。

## 知识库注入

只注入两层 `data_structure.md` 索引，不自动注入所有正文：

- 用户级：优先检索、默认写入。
- 全局级：兜底检索、共享资料。

因此知识文件发生增删改移后，索引必须同步，否则智能体可能找不到资料。

## 缓存

`run/prompt_cache.py` 根据以下来源的 mtime 计算缓存 key：

- `self_soul.md`
- `config/soul.md`
- `AGENTS.md`
- `plugins/`、`skills/` 中的 `SKILL.md`、`tool.py`、`_meta.json`
- 用户 `config.json`
- auto_improve 临时/永久目录
- `SESSION-STATE.md`
- 用户任务计划目录

任一来源变更后，下次构建会重建 prompt；部分流程也会主动调用 `invalidate_prompt_cache()`。

## 前端渲染分离

System Prompt 只影响模型上下文。前端正文、工具调用卡片和 artifacts 的展示由 Web 端独立处理，详见 `10-回复渲染与工具产物展示.md`。
