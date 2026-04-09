# 开发者快速上手

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：第一次接手本仓库，或准备开始发版的维护者
- 最近更新：2026-04-09

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

- `solver/`

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
cd solver
uv run pytest
cd ..
```

### 4.4 补丁和文档完整性检查

```bash
git diff --check
git status --short
```

## 5. 各模块最快编译命令

### 5.0 根目录统一编译

```bash
uv run sinan release build-all --project-dir .
```

如果要同时产出 Windows 版生成器：

```bash
uv run sinan release build-all --project-dir . --goos windows --goarch amd64
```

输出目录：

- `dist/`
- `generator/dist/<goos>-<goarch>/`
- `solver/dist/`

当前会先清理对应输出目录，再写入新的编译结果。

### 5.1 编译根仓库 Python 包

```bash
uv run sinan release build --project-dir .
```

构建结果：

- `dist/sinan_captcha-<version>-py3-none-any.whl`
- `dist/sinan_captcha-<version>.tar.gz`

### 5.2 编译 Go 生成器

当前目标：

```bash
uv run sinan release build-generator --project-dir .
```

Windows amd64：

```bash
uv run sinan release build-generator --project-dir . --goos windows --goarch amd64
```

### 5.3 编译独立 solver 包

```bash
uv run sinan release build-solver --project-dir .
```

构建结果：

- `solver/dist/*.whl`
- `solver/dist/*.tar.gz`

## 6. 最快发一版根仓库 Python 包

如果版本号已经更新到根目录 `pyproject.toml`，最短路径是：

```bash
uv run sinan release build-all --project-dir . --goos windows --goarch amd64
uv run sinan release publish --project-dir . --token-env UV_PUBLISH_TOKEN
```

如果你们把 token 放在别的环境变量里：

```bash
uv run sinan release publish --project-dir . --token-env PYPI_TOKEN
```

## 7. 最快组装 Windows 训练交付包

前提：

- 根仓库 wheel 已生成
- `generator/dist/windows-amd64/sinan-generator.exe` 已生成

命令：

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe generator/dist/windows-amd64/sinan-generator.exe \
  --output-dir dist/windows-bundle-<version>
```

如果还要带 solver bundle、数据集或素材：

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe generator/dist/windows-amd64/sinan-generator.exe \
  --bundle-dir bundles/solver/current \
  --datasets-dir datasets \
  --materials-dir materials \
  --output-dir dist/windows-bundle-<version>
```

## 8. 接手成功的最低标准

做到下面这些，才算真正能维护：

1. 知道根仓库 Python 包、Go 生成器、`solver` 分别怎么编译
2. 跑过根仓库 Python、Go、`solver` 三类最小回归
3. 知道根仓库主发布链路是 `sinan-captcha`，不是 `sinanz`
4. 知道 Windows 交付包依赖 wheel + `sinan-generator.exe`
5. 改完文档或流程后会同步 `.factory`
