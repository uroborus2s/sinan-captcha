# 维护者快速使用说明

- 项目名称：sinan-captcha
- 当前阶段：IMPLEMENTATION
- 当前目标：初始化 Go 生成器与 Python `core/` 核心包骨架，并保持文档、代码和忽略规则一致

## 新协作者先读什么

1. `AGENTS.md` / `GEMINI.md`
2. `.factory/project.json`
3. `.factory/memory/agent-session.md`
4. `.factory/memory/current-state.md`
5. [从基础模型到训练的实操手册](./from-base-model-to-training-guide.md)
6. [零基础落地实施方案](../04-project-development/05-development-process/implementation-plan.md)
7. [Windows 训练环境 Checklist](../04-project-development/05-development-process/windows-environment-checklist.md)
8. [如何确认 Windows 电脑上的 CUDA 版本](./how-to-check-cuda-version.md)
9. [样本导出与自动标注 Checklist](../04-project-development/05-development-process/data-export-auto-labeling-checklist.md)
10. [图形点选生成器任务拆解](../04-project-development/05-development-process/generator-task-breakdown.md)
11. 本目录下的运维手册和追踪矩阵

## 后续怎么和 AI 协作

- 修缺陷时说：`新增一个 BUG，先分析影响，再同步代码、测试、文档和 AI 记忆。`
- 加需求时说：`新增一个 CR，先补需求和设计，再进入实现。`
- 不确定下一步时说：`先生成 agent session 和 state doctor，再告诉我最合适的下一步。`

## 维护边界

- 以当前真实实现状态为准，不把项目当成新项目重做。
- 缺陷走 `BUG-*`，需求走 `CR-*`，治理补齐走 `TASK-*`。
- 当前最重要的正式执行文档是“从基础模型到训练的实操手册”，不要只从 PRD 的需求条目里拼接执行步骤。
- 如果你是第一次真开工，先读“从基础模型到训练的实操手册”，再读 checklist。
