# 开发者指南概览

本目录面向会直接维护源码仓库的开发者。目标不是解释业务背景，而是让维护者尽快回答 3 个问题：

1. 仓库里有哪些模块，分别怎么编译。
2. 改动后最少要跑哪些验证。
3. 怎样把 Python 包、Go 生成器和 Windows 交付包稳定打出来并上传。

## 1. 先记住当前发布边界

- 当前主发布包是根仓库 Python 包 `sinan-captcha`。
- 当前正式 CLI 是：
  - `sinan`
  - `sinan-generator`
- 当前稳定交付链路是：
  - 根仓库 wheel + sdist
  - `generator/` 下的 `sinan-generator` 二进制
  - 基于两者组装的 Windows 训练交付包
- `solver_package/` 是独立 solver 包主线的迁移工程，当前可以本地编译和验证，但还不是根仓库主发布入口。

## 2. 本目录推荐阅读顺序

按这个顺序读，最快能上手：

1. [开发者快速上手](./maintainer-quickstart.md)
2. [仓库结构与边界](./repository-structure-and-boundaries.md)
3. [模块编译与本地验证](./local-development-workflow.md)
4. [打包与上传发布](./release-and-delivery-workflow.md)
5. [独立 solver 包迁移与集成边界](./solver-bundle-and-integration.md)

## 3. 如果你只想完成一件事

- 第一次接手仓库：
  - 看 [开发者快速上手](./maintainer-quickstart.md)
- 想知道某个目录能不能改、该不该提交：
  - 看 [仓库结构与边界](./repository-structure-and-boundaries.md)
- 想在本地编译某个模块：
  - 看 [模块编译与本地验证](./local-development-workflow.md)
- 想发新版本到 PyPI，或组装 Windows 交付包：
  - 看 [打包与上传发布](./release-and-delivery-workflow.md)
- 想继续推进独立 `sinanz` 包：
  - 看 [独立 solver 包迁移与集成边界](./solver-bundle-and-integration.md)

## 4. 模块速览

| 模块 | 目录 | 主要语言 | 当前职责 | 常用构建命令 |
| --- | --- | --- | --- | --- |
| 训练 CLI | `.` | Python | `sinan`、训练、评估、自动训练、发布打包 | `uv run sinan release build --project-dir .` |
| 生成器 | `generator/` | Go | `sinan-generator`、工作区、素材、数据集生成 | `go build -o dist/generator/<platform>/sinan-generator ./cmd/sinan-generator` |
| 独立 solver 包 | `solver_package/` | Python + Rust | `sinanz` 迁移主线、公共 API、原生桥接骨架 | `cd solver_package && uv build` |

## 5. 本目录的维护原则

- 开发者指南优先回答“怎么做”，不要重复长篇需求背景。
- 所有命令都以当前仓库真实入口为准，不写概念性伪命令。
- 发布流程只写已经存在且可执行的链路；目标态能力单独标注“当前不是主发布入口”。
- 一旦开发工作流、编译命令或发布路径变化，必须同步：
  - `docs/03-developer-guide/`
  - `README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
