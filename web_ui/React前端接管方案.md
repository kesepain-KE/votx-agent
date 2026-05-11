# React 前端接管方案

> 写给外部贡献者，2026-05-11

## 边界规则

- React 前端放在项目根目录 `web-ui/` 下，不动现有 `web/` 任何文件
- 后端 Flask 不做任何改动，所有 API 保持不变
- React 前端通过 HTTP 调用后端 20 个现有 API
- 开发阶段 React dev server 独立运行，生产构建产物由 Flask 托管静态文件

## 现有 API 清单（不需要新增任何接口）

| 分组 | 端点 | 方法 | 用途 |
|------|------|------|------|
| 用户 | `/api/users` | GET | 获取用户列表 |
| 用户 | `/api/select-user` | POST | 选择用户进入 |
| 会话 | `/api/session` | GET | 获取当前会话状态 |
| 聊天 | `/api/chat` | POST | SSE 流式聊天 |
| 命令 | `/api/command` | POST | 执行 / 斜杠命令 |
| 断开 | `/api/disconnect` | POST | 断开连接 |
| 配置 | `/api/config` | GET/POST | 读取/保存用户配置 |
| 对话 | `/api/conversations` | GET/DELETE | 对话列表/批量删除 |
| 对话 | `/api/conversations/load` | POST | 加载归档对话 |
| 对话 | `/api/conversations/select` | POST | 选择对话预览 |
| 对话 | `/api/conversations/continue` | POST | 从归档继续 |
| 对话 | `/api/conversations/preview-state` | GET | 预览归档状态 |
| 对话 | `/api/conversations/<id>` | DELETE | 删除单个对话 |
| 对话 | `/api/conversations/<id>/rename` | POST | 重命名对话 |
| 文件 | `/api/upload` | POST | 上传文件 |
| 文件 | `/api/files` | GET/DELETE | 文件列表/批量删除 |
| 文件 | `/api/files/download/<name>` | GET | 下载文件 |
| 文件 | `/api/files/view/<name>` | GET | 预览文件 |
| 系统 | `/api/messages` | GET | 获取消息历史 |
| 系统 | `/api/system-prompt` | GET | 查看 system prompt |
| 系统 | `/api/export-markdown` | GET | 导出对话为 Markdown |
| 系统 | `/api/stats` | GET | 统计信息 |
| 系统 | `/api/tool-logs` | GET | 工具调用日志 |
| 系统 | `/api/reload` | POST | 重新加载配置 |

## 功能清单（必须还原现有功能）

### 聊天主界面
- SSE 流式接收消息
- 工具调用卡片（展开/收起）
- 消息历史滚动加载
- 斜杠命令输入和执行
- 输入框自动伸缩 + Shift+Enter 换行
- /clear /retry /summarize 命令支持

### 右侧面板（四栏）
- **概览栏**：当前用户、消息数、会话状态
- **调试栏**：思考/流式开关、模型/base-url/key 编辑、保存/应用/恢复按钮
- **日志栏**：工具调用日志列表
- **文件栏**：文件上传（拖拽）、文件列表、图片预览、引用 chip、批量删除

### 其他
- 用户选择界面（进入聊天前选用户）
- 对话管理（归档列表/预览/继续/删除/重命名）
- 暗色/亮色双主题
- 页面刷新自动恢复会话

## 交付标准

1. 包含 `web-ui/README.md` 写清怎么启动开发服务
2. 提供 `package.json`，`npm install && npm run dev` 能跑
3. 所有 20 个 API 都正常调用，不出现 404
4. 暗色/亮色主题切换正常
5. 在 Chrome 最新版无报错
