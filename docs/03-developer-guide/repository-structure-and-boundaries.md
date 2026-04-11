# 仓库结构与边界

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：维护仓库、排查路径问题、调整构建和交付边界的开发者
- 最近更新：2026-04-11

## 这页解决什么问题

这页只回答一个问题：当前仓库里哪些是源码，哪些是默认运行目录，哪些是发布产物，哪些是中间 staging 目录。

如果边界没分清，最容易发生 4 类问题：

1. 把 `work_home/` 下的运行结果误提交进 Git。
2. 把 `packages/solver/resources/` 当成普通缓存，导致 `sinanz` 打包资源失真。
3. 把 `packages/generator` 错当成 `uv workspace` 成员，最后构建命令和依赖方式都写错。
4. 把 `scripts/` 里的辅助脚本写成正式运行时依赖。

## 顶层结构速览

当前仓库最关键的目录是：

```text
sinan-captcha/
  packages/
    sinan-captcha/
    generator/
    solver/
  docs/
  scripts/
  tests/
  work_home/
  .opencode/
  .factory/
  pyproject.toml
  uv.lock
```

## 源码边界

### `packages/sinan-captcha/`

这是 Python 主线工程，负责：

- `sinan` CLI
- 训练、预测、评估、发布
- 自主训练控制器
- 训练仓库内的本地 solver bundle 调试入口

关键事实：

- 当前源码是 `src/` 直出布局，不再使用 `core/` 前缀。
- 顶层功能包包括 `auto_train`、`train`、`solve`、`release`、`materials`、`predict` 等。
- 根目录 `tests/python/` 是这条主线的主要测试面。

### `packages/generator/`

这是独立 Go 模块，负责：

- `sinan-generator`
- 工作区管理
- 素材导入 / 拉取
- 训练数据集导出
- 生成侧 QA

关键事实：

- 它不属于根 `uv workspace`。
- 构建由 Go toolchain 完成，根目录只是额外提供了统一包装入口。
- `configs/`、`cmd/`、`internal/` 都属于源码。

### `packages/solver/`

这是独立 `sinanz` 包，负责：

- 对外公开的 solver API
- `onnxruntime` 纯 Python 运行时
- 嵌入式 `resources/` 资产

关键事实：

- 这是 `uv workspace` 成员。
- `src/` 保存公共 API 和运行时代码。
- `resources/` 是包资源的一部分，不是普通缓存目录。
- `sinanz` 的独立包边界在这里；训练仓库里另有 `packages/sinan-captcha/src/solve/` 作为参考实现和 bundle 调试路径，不要混成同一层。

### `scripts/`

这里只放开发期辅助脚本，例如：

- 素材整理和聚类
- 爬取 / 浏览器驱动采样
- 特定回归和分析脚本
- 少量一次性开发辅助脚本

硬边界：

- `scripts/` 不是正式 CLI / SDK 入口。
- 运行时代码不应 import 这里的脚本。

### 仓库级 CLI 模块

当前仓库级正式入口在根目录：

- `repo_cli.py`
- `repo_release.py`
- `repo_solver_export.py`
- `repo_solver_asset_contract.py`

硬边界：

- 这些模块负责 monorepo 的构建、发版、资产导出和交付。
- `packages/sinan-captcha/src/cli.py` 只负责 `sinan` 训练仓库功能，不再承载仓库级发布命令。

## 运行目录边界

### `work_home/`

这是仓库默认的本地运行根目录，`common.paths` 也会把它当成默认工作根。

这里通常出现：

- `work_home/materials/`
- `work_home/datasets/`
- `work_home/reports/`
- `work_home/.cache/`

这些内容属于本地运行产物，不是正式源码事实源。

### 训练目录

真实训练机不必直接使用仓库根目录，而应通过下面命令创建独立训练目录：

```bash
uv run sinan env setup-train --train-root <训练目录>
```

这个目录通常包含：

- `datasets/`
- `runs/`
- `reports/`
- `.opencode/`

它是运行目录，不是源码目录。

### 生成器安装目录与工作区

生成器交付后通常拆成两层：

- 安装目录：
  放 `sinan-generator` 可执行文件
- 工作区：
  放 `workspace.json`、素材包、缓存、日志、任务状态

不要把生成器工作区混进源码仓库，也不要让训练 CLI 直接读取生成器工作区内部状态。

## 构建与 staging 边界

### `packages/*/dist/`

这些是构建产物目录：

- `packages/sinan-captcha/dist/`
- `packages/generator/dist/`
- `packages/solver/dist/`

特点：

- 每次构建前会被清理。
- 它们是输出，不是源码。
- 一般不应把构建文件长期提交进 Git。

### `packages/solver/resources/`

这是最容易误判的目录。

它既不是普通临时目录，也不是训练产线原始输出目录。它的角色是：

- `sinanz` 打包时的真实资源输入
- `stage-solver-assets` 的目标目录
- 下一次 `packages/solver/dist/` 构建时会被一起打入 wheel 的资产区

因此这里的改动要分两类看：

- `README.md`、占位结构、资源契约说明：
  属于源码
- `stage-solver-assets` 写入的 `manifest.json`、`metadata/*.json`、`models/*`：
  属于有意的发布前 staging 变更，应结合当前资产版本审阅，而不是当成随机缓存直接忽略

### `.opencode/`

根目录 `.opencode/` 是唯一受 Git 管理的资源源目录。

两个派生位置都不应当被当作主事实源：

- `packages/sinan-captcha/src/auto_train/resources/opencode/`
  只在构建 wheel / sdist 时临时 stage
- `<训练目录>/.opencode/`
  只在 `env setup-train` 时复制给训练机使用

## Git 边界

默认需要认真维护的目录：

- `packages/`
- `docs/`
- `scripts/`
- `tests/`
- `.factory/`
- `.opencode/`
- 根目录 `pyproject.toml`
- 根目录 `uv.lock`

默认需要警惕的运行 / 构建目录：

- `.venv/`
- `work_home/`
- `packages/*/dist/`
- `packages/*/build/`
- `*.egg-info`
- `__pycache__/`
- `.pytest_cache`
- `.ruff_cache`
- `.mypy_cache`

提交前至少做两件事：

```bash
git status --short
git diff --check
```

## 文档边界

- `docs/02-user-guide/`
  面向训练机使用者和业务接入者
- `docs/03-developer-guide/`
  面向维护源码仓库的人
- `docs/04-project-development/`
  面向内部设计、需求、计划和追踪

不要把“如何维护仓库”和“如何使用交付包”写在同一页，也不要把内部设计决策塞回开发者快速手册。
