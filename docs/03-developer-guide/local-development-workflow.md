# 日常开发与验证

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：在本仓库中改代码、改合同、改构建链路的开发者
- 最近更新：2026-04-11

## 这页解决什么问题

这页回答三个问题：

1. 日常开发该从哪个入口启动。
2. 按改动范围最少要跑哪些验证。
3. 哪些改动必须同步文档和 `.factory` 记忆层。

## 先选你在改哪一层

### Python 主线：`packages/sinan-captcha`

典型改动：

- `sinan` 子命令
- 训练、预测、评估
- `auto_train` 控制器
- 训练仓库内的 bundle 调试与 `solve` 入口

### Go 生成器：`packages/generator`

典型改动：

- 工作区和 preset
- 素材校验
- 样本渲染
- 数据集导出
- 生成器 CLI 参数

### 独立 solver：`packages/solver`

典型改动：

- `sinanz` 公共 API
- ONNX Runtime 运行时
- `resources/` 里的嵌入式资产

### 跨模块合同

典型改动：

- `dataset.json` 结构
- `work_home/` 路径约定
- solver 资产导出合同
- Windows 交付包结构
- build / publish / stage 命令行为

这类改动不能只改代码，必须同步文档和 `.factory/memory/`。

## 开发环境常用入口

### 基础源码环境

```bash
uv sync
```

适合：

- 改 CLI
- 改文档
- 改构建逻辑
- 跑轻量 Python 回归

### 含训练栈的源码环境

```bash
uv sync --group train
```

适合：

- 跑训练相关测试
- 导出 solver 资产
- 处理 `onnx` / `ultralytics` / `optuna` 相关改动

### 独立训练目录

如果你要复现真实训练机，而不是只在源码仓库里开发：

```bash
uv run sinan env setup-train --train-root <训练目录>
```

这会生成独立训练目录、安装 `sinan-captcha[train] + torch/torchvision/torchaudio`，并复制 `.opencode/` 资源。

## 根目录开发命令

### 查看当前 monorepo 路径

```bash
uv run repo paths
```

### 构建一个或全部模块

```bash
uv run repo build sinan-captcha
uv run repo build generator
uv run repo build solver
uv run repo build all
```

如果要交叉编译 Windows 版生成器：

```bash
uv run repo build generator --goos windows --goarch amd64
```

说明：

- `repo` 是当前唯一正式仓库级 CLI。
- `sinan` 不再承载仓库级构建 / 发布 / 打包命令。

## 最小验证矩阵

| 改动范围 | 最少验证 |
| --- | --- |
| 只改 `docs/03-developer-guide/` 或 `.factory/memory/` | `git diff --check` |
| 只改 `packages/sinan-captcha/src/` | `uv run python -m unittest discover -s tests/python -p 'test_*.py'` |
| 只改 `packages/generator/` | 在 `packages/generator/` 下执行 `GOCACHE=/tmp/sinan-go-build-cache go test ./...` |
| 只改 `packages/solver/` | `uv run pytest packages/solver/tests -q` |
| 改 `scripts/repo_tools/repo_cli.py`、`scripts/repo_tools/repo_release.py`、打包逻辑 | Python 回归 + `uv run repo build all` |
| 改 solver 资产导出 / staging / `sinanz` 资源路径 | Python 回归 + solver 测试 + 相关构建 |
| 改 `dataset.json`、训练目录结构、跨模块合同 | Python 回归 + Go 测试 + solver 测试 |

## Python 主线的常用工作流

### 跑整套 Python 回归

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

### 只看 CLI 是否还能分发命令

```bash
uv run python -m unittest discover -s tests/python -p 'test_root_cli.py'
```

### 构建 `sinan-captcha`

```bash
uv run repo build sinan-captcha
```

构建行为要点：

- 直接调用 `setuptools` build backend
- 构建前清空 `packages/sinan-captcha/dist/`
- 根目录 `.opencode/` 会被临时 stage 到包内资源目录
- 构建结束后会自动清理临时 `.opencode` 目录、`build/` 和 `*.egg-info`

## Go 生成器的常用工作流

### 跑 Go 测试

在 `packages/generator/` 目录执行：

```bash
GOCACHE=/tmp/sinan-go-build-cache go test ./...
```

### 从根目录构建生成器

```bash
uv run repo build generator
```

当前输出目录：

- `packages/generator/dist/<goos>-<goarch>/`

当前规则：

- 构建前会清空对应目标目录
- `GOCACHE` 默认收口到 `work_home/.cache/go/`
- 若请求 Windows 目标，输出文件名会自动切到 `sinan-generator.exe`

## `sinanz` 的常用工作流

### 跑 `sinanz` 测试

```bash
uv run pytest packages/solver/tests -q
```

### 构建 `sinanz`

```bash
uv run repo build solver
```

如果你刚执行过 solver 资产 staging，建议立即重新构建一次，确认资源和 wheel 能对齐。

## 正式发布入口

如果你要验证“当前仓库级发布链路是否还能用”，直接跑正式入口：

```bash
uv run repo build all
```

可选 Windows 版生成器：

```bash
uv run repo build all --goos windows --goarch amd64
```

## 改完后必须同步什么

### 改了目录结构、命令入口、构建路径

同步：

- `README.md`
- `docs/03-developer-guide/`
- `.factory/memory/current-state.md`
- `.factory/memory/change-summary.md`

### 改了用户也会感知到的安装 / 训练 / 交付路径

同步：

- `docs/02-user-guide/`
- `docs/03-developer-guide/`
- 必要时 `docs/index.md`

### 改了设计基线或正式合同

同步：

- `docs/04-project-development/04-design/`
- `docs/04-project-development/05-development-process/`
- `.factory/memory/current-state.md`

## 提交前最后检查

```bash
git diff --check
git status --short
```

特别注意两类误提交：

- `work_home/`、缓存目录、构建产物
- 构建后遗留的 `build/`、`*.egg-info`、`__pycache__`
