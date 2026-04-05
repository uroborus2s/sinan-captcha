# 项目索引

- 项目名称：sinan-captcha
- 当前模式：cli_direct
- 当前阶段：IMPLEMENTATION
- 项目负责人：Codex
- 技术栈：Python, PyTorch, Ultralytics YOLO, ONNX, ONNX Runtime, Rust, Windows, CUDA, X-AnyLabeling/CVAT, Go generator control plane
- 当前技术画像：图形验证码专项模型设计画像
- 设计交付物数：9
- 当前阶段主要角色：项目协调者、需求分析师、文档与记忆管理员

## 项目创意摘要

司南：交付一个本地可调用的验证码求解能力，覆盖图形点选与滑块缺口两类业务语义。当前仓库负责 Go 生成器、Windows 训练 CLI、自主训练 CLI 和推理资产导出；最终业务交付目标已经冻结为独立 PyPI solver 包 `sinanz`，以平台相关 wheel、内嵌 ONNX 资产和 Rust 原生扩展向调用方提供函数级入口。

## 项目概况

- 任务数：0
- 变更数：0
- 缺陷数：0
- 活跃 PR 数：0
- 已合并 PR 数：0
- AI 入口：`/.factory/memory/current-state.md`、`/.factory/memory/agent-session.md`、`docs/04-project-development/03-requirements/prd.md`
