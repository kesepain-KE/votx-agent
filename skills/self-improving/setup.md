# Setup — Self-Improving Agent (votx-agent 适配版)

## 首次启动（自动）

Skill 安装后，首次激活时自动完成以下操作：

### 1. 创建记忆目录结构

```python
# Agent 自动执行
users/<name>/self-improving/
├── memory.md          # HOT 层
├── corrections.md     # 纠正日志
├── projects/          # 项目模式
├── domains/           # 领域模式
└── archive/           # 归档
```

### 2. 初始化核心文件

`memory.md` 初始内容：
```markdown
# Memory (HOT Tier)

## Preferences

## Patterns

## Rules
```

`corrections.md` 初始内容：
```markdown
# Corrections Log

| Date | What I Got Wrong | Correct Answer | Status |
|------|-----------------|----------------|--------|
```

无需手动操作，Agent 会在首次激活时自动完成。

## 验证

用 "记忆统计" 确认设置完成：

```
📊 Self-Improving Memory

HOT (always loaded):
   memory.md: 0 entries

WARM (load on demand):
   projects/: 0 files
   domains/: 0 files

COLD (archived):
   archive/: 0 files
```
