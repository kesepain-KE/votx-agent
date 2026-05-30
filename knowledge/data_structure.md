# knowledge/ 目录结构

VOTX Agent 全局知识库，存放所有用户共享的参考资料和系统说明。更新程序会对 `knowledge/` 做特殊处理：默认合并更新内置知识文件，保留用户额外新增文件。

## 文件列表

| 文件 | 说明 |
|------|------|
| `data_structure.md` | 全局知识库索引（本文件） |
| `deployment.md` | 部署、环境变量与更新说明，覆盖 Windows/Linux/Docker、`.env`、`update.py`、`message-runtime/`、`knowledge/` 更新策略 |
| `message-config.md` | 外部消息路由配置说明，覆盖 OneBot/NapCat、Telegram、群聊控制、账号绑定、附件接收、主动推送 |
| `users-config.md` | 用户配置文件说明，覆盖 `users/<name>/config.json`、模型 provider、多模态能力、技能禁用、`self_soul.md`、用户知识库 |

## 使用建议

- 用户询问外部消息路由、QQ/NapCat、Telegram、附件接收时，优先阅读 `message-config.md`。
- 用户询问模型配置、API Key、用户目录、技能开关、多模态能力时，优先阅读 `users-config.md`。
- 用户询问部署、Docker、环境变量、版本更新时，优先阅读 `deployment.md`。
- 用户个人资料、聊天记录和私有知识不应写入这里，应放在 `users/<用户名>/` 下。
