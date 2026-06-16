# knowledge/ 目录结构

VOTX Agent 全局知识库，存放所有用户共享的参考资料和系统说明。更新程序会对 `knowledge/` 做特殊处理：默认合并更新内置知识文件，保留用户额外新增文件。

## 文件列表

### 系统部署与配置

| 文件 | 说明 |
|------|------|
| `data_structure.md` | 全局知识库索引（本文件） |
| `deployment.md` | 部署、环境变量与更新说明，覆盖 Windows/Linux/Docker、外部访问/局域网访问、`.env`、`update.py`、`message-runtime/`、`knowledge/` 更新策略 |
| `message-config.md` | 外部消息路由配置说明，覆盖 OneBot/NapCat、Telegram、群聊控制、账号绑定、附件接收、主动推送 |
| `users-config.md` | 用户配置文件说明，覆盖目录结构、默认输出/上传目录、用户头像、`config.json` 完整字段（含 `provider.timeout`/`api_style`/`vision_model`/`max_tokens`/`thinking`）、工具超时、技能禁用、用户知识库索引维护 |

### 架构原理（内部机制分析）

| 文件 | 说明 |
|------|------|
| `01-system-prompt拼接架构.md` | System Prompt 七层拼接顺序、注入规则、两种可见性分类、缓存机制、前端渲染分离 |
| `02-对话历史保留与压缩原理.md` | ChatManager 消息模型、20 轮保留策略、LLM 摘要压缩、JSONL 日志存储、外部消息历史共享 |
| `03-工具调用原理.md` | 工具型/指令型 Skill 注册、ToolRunner 执行流程、run_chat_turn 循环、上下文绑定、内置工具清单 |
| `04-memory生命周期执行原理.md` | 三层数据模型（memory/self-improving/ontology）、永久层与临时层、被动触发与主动审阅、清理机制 |
| `05-临时记忆生命周期执行原理.md` | 临时记忆创建、system prompt 注入格式、mtime 过期判断、cron 清理、临时→永久转化流程 |
| `06-定时任务执行位置.md` | CLI/Web 两种执行模式、cron 调度循环、子进程 vs 进程内执行、并发安全、任务结果推送 |
| `07-消息路由编号原理.md` | 四层编号体系、身份映射查找优先级、OneBot/Telegram 路由流程、推送队列状态机、Source 闭环 |
| `08-任务计划实际执行原理.md` | 无专用引擎设计、子代理生成计划、Web/外部审批、system prompt 注入驱动执行、状态机与缓存失效 |
| `09-智能体工作规范.md` | Skill 优先于 shell、默认路径规则、`tmp`/`download`/`history/file` 用途边界、知识库索引维护、插件收口状态 |

## 使用建议

- 用户询问外部消息路由、QQ/NapCat、Telegram、附件接收时，优先阅读 `message-config.md`。
- 用户询问模型配置、API Key、用户目录、技能开关、多模态能力、头像配置时，优先阅读 `users-config.md`。
- 用户询问部署、Docker、环境变量、局域网访问、外部访问、版本更新时，优先阅读 `deployment.md`。
- 用户询问智能体产物保存位置、临时文件、上传文件、Skill 与 shell 的使用边界、知识库索引维护时，优先阅读 `09-智能体工作规范.md`。
- 用户询问内部架构、执行原理、数据流时，阅读对应的 `01~08` 系列文件。
- 用户个人资料、聊天记录和私有知识不应写入这里，应放在 `users/<用户名>/` 下。

## 规则

- 检索时同时搜索两层，用户级结果优先。
- 默认写入用户级，只有用户明确说"写入全局"时才写入全局知识库。
- 全局知识库发生新增、修改、删除、重命名、移动后，必须更新本索引。
