# 维护者快速使用说明

- 项目名称：sinan-captcha
- 当前阶段：IMPLEMENTATION
- 当前目标：维护 Go 生成器与 Python `core/` 骨架，并保持文档、代码和记忆层一致

## 新维护者先读什么

1. `AGENTS.md` / `GEMINI.md`
2. `.factory/project.json`
3. `.factory/memory/agent-session.md`
4. `.factory/memory/current-state.md`
5. [使用指南总览](../02-user-guide/user-guide.md)
6. [使用交付物与正式 CLI](../02-user-guide/use-build-artifacts.md)
7. [Windows 训练机安装与模型训练完整指南](../02-user-guide/from-base-model-to-training-guide.md)

## 后续怎么和 AI 协作

- 修缺陷时说：`新增一个 BUG，先分析影响，再同步代码、测试、文档和 AI 记忆。`
- 加需求时说：`新增一个 CR，先补需求和设计，再进入实现。`
- 不确定下一步时说：`先生成 agent session 和 state doctor，再告诉我最合适的下一步。`

## 维护边界

- 以当前真实实现状态为准，不把项目当成新项目重做。
- 缺陷走 `BUG-*`，需求走 `CR-*`，治理补齐走 `TASK-*`。
- 用户指南只负责“怎么使用项目”，不要再把维护者阅读顺序塞回用户指南。
- 内部维护时优先同步代码、文档、测试和 AI 记忆，不要只改其中一层。
- Python 侧安装、运行、测试和构建统一使用 `uv` 命令，不再在维护文档里混用 `python -m` 和 `pip`。
