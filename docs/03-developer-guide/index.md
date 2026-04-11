# 开发者指南

本目录面向直接维护 `sinan-captcha` 源码仓库的人，不面向只使用训练机交付包或最终 solver 的使用者。目标只有一个：让维护者能基于当前仓库事实，快速判断应该去哪里改、改完跑什么、怎样构建和交付。

## 当前仓库的 4 个稳定事实

1. 仓库现在是 monorepo，但根 `uv workspace` 只纳入两个 Python 包：
   - `packages/sinan-captcha`
   - `packages/solver`
2. `packages/generator` 不是 `uv workspace` 成员，而是独立 Go 模块；构建要走 Go toolchain，仓库级统一入口是根目录 `repo` CLI。
3. `work_home/` 是默认本地运行根目录，素材、数据集、报告、缓存都应该落在这里，而不是散落在源码树。
4. 根目录 `.opencode/` 是唯一受 Git 管理的 OpenCode 资源事实源；包内 `src/auto_train/resources/opencode/` 只允许在构建或训练目录初始化时临时生成。

## 推荐阅读顺序

1. [接手与冷启动](./maintainer-quickstart.md)
2. [仓库结构与边界](./repository-structure-and-boundaries.md)
3. [日常开发与验证](./local-development-workflow.md)
4. [构建、发版与交付](./release-and-delivery-workflow.md)
5. [`sinanz` 集成与资产 staging](./solver-bundle-and-integration.md)

## 按任务找页面

- 第一次接手仓库：
  [接手与冷启动](./maintainer-quickstart.md)
- 想确认某个目录属于源码、生成物还是交付物：
  [仓库结构与边界](./repository-structure-and-boundaries.md)
- 想知道改完当前模块最少跑哪些验证：
  [日常开发与验证](./local-development-workflow.md)
- 想打包、导出 solver 资产、发布 PyPI 或组装 Windows 交付包：
  [构建、发版与交付](./release-and-delivery-workflow.md)
- 想推进独立 solver 包或核对 `sinan solve` / `sinanz` 的边界：
  [`sinanz` 集成与资产 staging](./solver-bundle-and-integration.md)

## 这套指南默认覆盖的对象

- `packages/sinan-captcha`
  Python 训练、评估、发布与自主训练 CLI，正式命令是 `sinan`
- `packages/generator`
  Go 生成器工程，正式命令是 `sinan-generator`
- `packages/solver`
  独立 `sinanz` 求解包与嵌入式 ONNX 资源
- `scripts/repo_tools/repo_cli.py` / `scripts/repo_tools/repo_release.py` / `scripts/repo_tools/repo_solver_export.py`
  仓库级构建、发版、资产导出和交付入口，不属于 `sinan` 运行时能力

## 维护原则

- 只写当前仓库真实存在的入口、目录和命令，不保留旧 `core/` 路径和历史布局残影。
- 对开发者最重要的是“当前怎么做”，不是重复需求背景；背景与正式设计请回到 `docs/04-project-development/`。
- 一旦工作流、目录边界、发布路径或 solver 资产合同变化，至少同步：
  - `docs/03-developer-guide/`
  - `docs/index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
