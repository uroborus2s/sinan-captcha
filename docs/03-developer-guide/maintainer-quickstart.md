# 开发者快速上手

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：第一次接手本仓库，或准备开始发版的维护者
- 最近更新：2026-04-06

## 0. 这页解决什么问题

这页只做一件事：

- 让开发者在 30 分钟内看懂仓库、跑通最小验证、知道各模块怎么编译

## 1. 先读哪些事实源

第一次进入仓库，按这个顺序看：

1. `AGENTS.md`
2. `.factory/project.json`
3. `.factory/memory/current-state.md`
4. `.factory/memory/change-summary.md`
5. `docs/index.md`
6. [开发者指南概览](./index.md)
7. [仓库结构与边界](./repository-structure-and-boundaries.md)

目的很简单：

- 先知道项目当前处于什么阶段
- 再知道哪些发布链路已经稳定，哪些仍在迁移
- 最后再开始跑命令

## 2. 本机最少工具要求

至少准备：

- `uv`
- Python 3.12
- Go 1.22+
- `git`

建议先确认：

```bash
uv --version
uv python list
go version
git --version
```

## 3. 仓库里最重要的 3 个模块

### 3.1 根仓库 Python 模块

目录：

- `core/`
- `tests/python/`
- `pyproject.toml`

职责：

- 提供 `sinan` CLI
- 管训练、测试、评估、发布打包、自主训练

### 3.2 Go 生成器模块

目录：

- `generator/`

职责：

- 提供 `sinan-generator`
- 管工作区、素材导入、数据集生成

### 3.3 独立 solver 包模块

目录：

- `solver_package/`

职责：

- 演进中的独立 `sinanz` 包
- 提供未来面向业务方的独立求解库主线

当前状态：

- 可本地构建和测试
- 不是根仓库主发布链路

## 4. 第一次进仓库先跑什么

### 4.1 根仓库 Python 最小回归

```bash
uv python install 3.12
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

### 4.2 Go 生成器最小回归

```bash
cd generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
cd ..
```

### 4.3 独立 solver 包最小回归

```bash
cd solver_package
uv run pytest
cd ..
```

### 4.4 补丁和文档完整性检查

```bash
git diff --check
git status --short
```

## 5. 各模块最快编译命令

### 5.1 编译根仓库 Python 包

```bash
uv run sinan release build --project-dir .
```

构建结果：

- `dist/sinan_captcha-<version>-py3-none-any.whl`
- `dist/sinan_captcha-<version>.tar.gz`

### 5.2 编译 Go 生成器

macOS arm64：

```bash
cd generator
mkdir -p dist/generator/darwin-arm64
GOOS=darwin GOARCH=arm64 go build -o dist/generator/darwin-arm64/sinan-generator ./cmd/sinan-generator
cd ..
```

Windows amd64：

```bash
cd generator
mkdir -p dist/generator/windows-amd64
GOOS=windows GOARCH=amd64 go build -o dist/generator/windows-amd64/sinan-generator.exe ./cmd/sinan-generator
cd ..
```

### 5.3 编译独立 solver 包

```bash
cd solver_package
uv build
cd ..
```

构建结果：

- `solver_package/dist/*.whl`
- `solver_package/dist/*.tar.gz`

## 6. 最快发一版根仓库 Python 包

如果版本号已经更新到 `core/_version.py`，最短路径是：

```bash
uv run sinan release build --project-dir .
uv run sinan release publish --project-dir . --token-env UV_PUBLISH_TOKEN
```

如果你们把 token 放在别的环境变量里：

```bash
uv run sinan release publish --project-dir . --token-env PYPI_TOKEN
```

## 7. 最快组装 Windows 训练交付包

前提：

- 根仓库 wheel 已生成
- `generator/dist/generator/windows-amd64/sinan-generator.exe` 已生成

命令：

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe generator/dist/generator/windows-amd64/sinan-generator.exe \
  --output-dir dist/windows-bundle-<version>
```

如果还要带 solver bundle、数据集或素材：

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe generator/dist/generator/windows-amd64/sinan-generator.exe \
  --bundle-dir bundles/solver/current \
  --datasets-dir datasets \
  --materials-dir materials \
  --output-dir dist/windows-bundle-<version>
```

## 8. 接手成功的最低标准

做到下面这些，才算真正能维护：

1. 知道根仓库 Python 包、Go 生成器、`solver_package` 分别怎么编译
2. 跑过根仓库 Python、Go、`solver_package` 三类最小回归
3. 知道根仓库主发布链路是 `sinan-captcha`，不是 `sinanz`
4. 知道 Windows 交付包依赖 wheel + `sinan-generator.exe`
5. 改完文档或流程后会同步 `.factory`
