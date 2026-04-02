# 项目索引

- 项目名称：sinan-captcha
- 当前模式：cli_direct
- 当前阶段：DESIGN
- 项目负责人：Codex
- 技术栈：Python, Ultralytics YOLO, Windows, CUDA, X-AnyLabeling/CVAT, Go generator control plane
- 当前技术画像：图形验证码专项模型设计画像
- 设计交付物数：4
- 当前阶段主要角色：项目协调者、方案架构师、文档与记忆管理员

## 项目创意摘要

司南：面向行为验证码训练两个专项模型。第一专项为多类别检测模型，用于图形点选验证码；第二专项为滑块缺口定位模型，用于滑块验证码。当前设计结论是：生成器采用受控集成 + 可插拔 backend，优先从自有生成端或内部生成器直接导出并校验 `gold` 标签，不要求先上线完整验证码平台。

## 项目概况

- 任务数：0
- 变更数：0
- 缺陷数：0
- 活跃 PR 数：0
- 已合并 PR 数：0
- AI 入口：`/.factory/memory/current-state.md`、`/.factory/memory/agent-session.md`、`docs/04-project-development/04-design/technical-selection.md`
