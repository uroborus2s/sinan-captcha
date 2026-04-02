# 变更摘要

- 2026-04-02：重构 `docs/02-user-guide/from-base-model-to-training-guide.md`，将手册主线改为“仓库产物 + 训练工作目录 + 当前实现状态”，移除把 `go-captcha-service` 作为默认前置的旧叙述。
- 2026-04-02：同步更新 `docs/02-user-guide/user-guide.md` 和 `/.factory/memory/current-state.md`，明确新手阅读入口与当前仓库事实边界。
- 2026-04-02：重构用户指南信息架构，新增 `docs/02-user-guide/use-build-artifacts.md`，将 `docs/02-user-guide/user-guide.md` 改为公开总览页，并把维护者说明迁移到 `docs/03-developer-guide/maintainer-quickstart.md`。
- 2026-04-02：更新 `docs/index.md` 导航，移除用户指南中的私有页面混入，确保公开路径只围绕“使用编译结果”和“训练环境 + 模型训练”两类目标展开。
