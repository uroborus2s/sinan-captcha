# 接手与冷启动

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：第一次接手仓库、准备改代码或准备处理发版的维护者
- 最近更新：2026-04-11

## 这页解决什么问题

这页给新维护者一条最短上手路径：先读哪些事实、先装哪些工具、先跑哪些命令，怎样在第一个小时内确认自己已经具备维护能力。

## 第一步：先建立正确心智模型

先记住下面 5 件事，再开始跑命令：

1. 仓库主线不是公网 API，而是“模型生产仓库 + 独立 solver 包”的组合工程。
2. `sinan` 负责训练、评估、预测、`solve` 和自主训练；仓库级构建 / 发版 / 打包统一走根目录 `repo` CLI；`sinan-generator` 负责素材、样本和数据集生成；`sinanz` 是独立 solver 包。
3. 根 `uv workspace` 当前只纳入 `packages/sinan-captcha` 和 `packages/solver`；`packages/generator` 仍通过 Go 构建。
4. 当前仓库级正式命令由 `uv run repo ...` 驱动，`publish` 只上传 `sinan-captcha` 当前版本的 wheel 与 sdist。
5. `work_home/` 是默认本地运行根；不要把数据集、缓存、报告和构建脏数据直接塞回源码目录。

## 第二步：先读这些事实源

按这个顺序读，效率最高：

1. `AGENTS.md`
2. `docs/04-project-development/01-governance/project-charter.md`
3. `docs/04-project-development/02-discovery/input.md`
4. [开发者指南](./index.md)
5. [仓库结构与边界](./repository-structure-and-boundaries.md)
6. `README.md`

如果你这次要改发布、目录合同或 solver 交接，再补读：

1. `docs/04-project-development/04-design/technical-selection.md`
2. `docs/04-project-development/04-design/module-structure-and-delivery.md`
3. `docs/04-project-development/04-design/solver-asset-export-contract.md`

## 第二步补充：先知道命令从哪儿进代码

第一次排查命令或改 CLI 时，先看这些入口，效率最高：

| 你要排查什么 | 先看哪个文件 |
| --- | --- |
| `sinan` 根命令分发 | `packages/sinan-captcha/src/cli.py` |
| `repo build/publish/export/package` | `repo_cli.py`、`repo_release.py`、`repo_solver_export.py` |
| `sinan solve ...` | `packages/sinan-captcha/src/solve/cli.py` |
| 训练目录初始化 | `packages/sinan-captcha/src/ops/setup_train.py` |
| `sinan-generator` | `packages/generator/cmd/sinan-generator/main.go` |
| `sinanz` 公共 API | `packages/solver/src/sinanz.py` |

补充边界：

- `packages/sinan-captcha/src/solve/cli.py` 是训练仓库内的 bundle 调试入口。
- `packages/solver/src/` 才是独立 `sinanz` 包的公共边界。
- 如果你要改业务接入合同，先看 `packages/solver/src/`；如果你要改训练仓库里的调试、导出或 bundle 验证，再看 `packages/sinan-captcha/src/solve/`。

如果你只想先记一张最短表，记下面这个：

| 命令 / 目标 | 入口文件 | 最小验证 |
| --- | --- | --- |
| `sinan` 根命令 | `packages/sinan-captcha/src/cli.py` | `uv run python -m unittest discover -s tests/python -p 'test_root_cli.py'` |
| `repo ...` | `repo_cli.py` / `repo_release.py` | `./.venv/bin/python -m unittest discover -s tests/python -p 'test_repo_cli.py'` |
| `sinan solve ...` | `packages/sinan-captcha/src/solve/cli.py` | 相关 bundle / solve 回归 |
| `sinan-generator` | `packages/generator/cmd/sinan-generator/main.go` | 在 `packages/generator/` 下执行 `GOCACHE=/tmp/sinan-go-build-cache go test ./...` |
| `sinanz` | `packages/solver/src/sinanz.py` | `uv run pytest packages/solver/tests -q` |

## 第三步：准备本机工具

至少需要：

- `uv`
- Python 3.12
- 与 `packages/generator/go.mod` 对齐的 Go toolchain
- `git`

建议先确认：

```bash
uv --version
uv python list
go version
git --version
```

## 第四步：初始化仓库开发环境

在仓库根目录执行：

```bash
uv python install 3.12
uv sync
```

只有在你要跑训练、导出 solver 资产、验证 `ultralytics/onnx/optuna` 等重依赖时，再补：

```bash
uv sync --group train
```

补充说明：

- 默认源码环境是“轻量 CLI + 构建 + 文档维护”优先。
- 训练目录环境不是靠根仓库 `.venv` 代替的；如果要模拟真实训练机，请改用 `uv run sinan env setup-train --train-root <目录>`。

## 第五步：跑最小验证

### 根仓库 Python 回归

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

### Go 生成器回归

在 `packages/generator/` 目录执行：

```bash
GOCACHE=/tmp/sinan-go-build-cache go test ./...
```

### `sinanz` 回归

在仓库根目录执行：

```bash
uv run pytest packages/solver/tests -q
```

### 工作区健康检查

```bash
git diff --check
git status --short
```

## 第六步：确认你能完成最基本的构建

仓库级统一入口：

```bash
uv run repo paths
uv run repo build all
```

如果要交叉编译 Windows 版生成器：

```bash
uv run repo build generator --goos windows --goarch amd64
```

上传到 PyPI：

```bash
uv run repo publish-sinan
uv run repo publish-solver
```

这些命令的输出目录固定为：

- `packages/sinan-captcha/dist/`
- `packages/generator/dist/<goos>-<goarch>/`
- `packages/solver/dist/`

## 第一个小时结束前，你应该能回答的问题

如果下面 6 个问题都能答上来，就说明你已经完成冷启动：

1. 哪两个包是根 `uv workspace` 成员，哪个模块不是。
2. `sinan`、`sinan-generator`、`sinanz` 分别负责什么。
3. `work_home/`、`.opencode/`、`packages/solver/resources/` 分别属于什么边界。
4. 改完 Python 主线、Go 生成器、`sinanz` 后各自最少跑什么验证。
5. `repo build all`、`repo publish-sinan`、`repo publish-solver` 的边界分别是什么。
6. 当前真正会上传到 PyPI 的是哪个包，版本号从哪里读取，token 默认从哪些环境变量读取。

## 需要立即记住的边界

- 根目录 `.opencode/` 才是受 Git 管理的 OpenCode 资源源目录。
- `packages/solver/resources/` 不是普通缓存目录；执行 `stage-solver-assets` 后，这里会成为下一次 `sinanz` 打包的真实资源输入。
- 仓库级 CLI 在根目录 `repo_*.py`；`sinan` 运行时代码不应反向 import 这些仓库运维模块。
- `work_home/` 下的运行产物默认不进 Git；提交前一定看 `git status --short`。
