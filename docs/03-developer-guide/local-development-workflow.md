# 模块编译与本地验证

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：会在本仓库内改代码、改文档、改发布流程的开发者
- 最近更新：2026-04-06

## 0. 这页解决什么问题

这页回答的是：

- 每个模块平时应该怎么开发、怎么编译、怎么验证
- 跨模块改动时，最少要补哪些检查

## 1. 开发前先判断你改了哪一层

### 1.1 根仓库 Python CLI

典型改动：

- `sinan` 子命令
- 训练、评估、自主训练
- 发布打包逻辑

主要目录：

- `core/`
- `tests/python/`
- `pyproject.toml`

### 1.2 Go 生成器

典型改动：

- 工作区
- 素材导入/拉取
- 数据集导出
- 生成侧 QA

主要目录：

- `generator/`

### 1.3 独立 solver 包

典型改动：

- `sinanz` 公共 API
- 包资源
- Rust 原生桥接

主要目录：

- `solver_package/src/`
- `solver_package/native/`
- `solver_package/tests/`

### 1.4 跨模块契约

典型改动：

- `dataset.json` 结构
- 训练目录或交付目录结构
- solver 资产导出合同
- 发布和打包入口

这类改动一定要同步：

- 代码
- `docs/03-developer-guide/`
- 对应用户指南
- `.factory/memory/`

## 2. 根仓库 Python 模块工作流

### 2.1 常用命令

跑测试：

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

构建包：

```bash
uv run sinan release build --project-dir .
```

安装烟测：

```bash
uvx --from ./dist/sinan_captcha-<version>-py3-none-any.whl sinan --help
```

### 2.2 什么时候至少跑这一层

- 改了 `core/`
- 改了 `pyproject.toml`
- 改了 `.opencode/` 资源
- 改了发布命令

## 3. Go 生成器模块工作流

### 3.1 常用命令

跑测试：

```bash
cd generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
cd ..
```

本机构建：

```bash
cd generator
go build ./cmd/sinan-generator
cd ..
```

目标平台构建：

```bash
cd generator
mkdir -p dist/generator/windows-amd64
GOOS=windows GOARCH=amd64 go build -o dist/generator/windows-amd64/sinan-generator.exe ./cmd/sinan-generator
cd ..
```

### 3.2 什么时候至少跑这一层

- 改了 `generator/cmd/`
- 改了 `generator/internal/`
- 改了生成器 CLI 参数
- 改了工作区、素材或数据集导出逻辑

## 4. 独立 solver 包模块工作流

### 4.1 常用命令

跑测试：

```bash
cd solver_package
uv run pytest
cd ..
```

构建包：

```bash
cd solver_package
uv build
cd ..
```

### 4.2 什么时候至少跑这一层

- 改了 `solver_package/src/`
- 改了 `solver_package/native/`
- 改了 solver 资产加载方式
- 改了独立 API 或资源目录结构

## 5. 跨模块改动的最低验证矩阵

| 改动类型 | 最少验证 |
| --- | --- |
| 只改开发者文档 | `git diff --check` |
| 只改根仓库 Python | `uv run python -m unittest discover -s tests/python -p 'test_*.py'` |
| 只改 Go 生成器 | `cd generator && GOCACHE=/tmp/sinan-go-build-cache go test ./...` |
| 只改 `solver_package` | `cd solver_package && uv run pytest` |
| 改发布链路 | 根仓库 Python 测试 + `uv run sinan release build --project-dir .` |
| 改交付包结构 | 根仓库 Python 测试 + 生成器构建 + `package-windows` 烟测 |
| 改数据/资产交接合同 | 根仓库 Python 测试 + Go 测试 + `solver_package` 测试 |

## 6. 改完后必须同步哪些文档

### 6.1 改对外命令或安装流程

同步：

- `README.md`
- `docs/02-user-guide/`
- `docs/03-developer-guide/`

### 6.2 改维护者工作流

同步：

- `docs/03-developer-guide/`
- `.factory/memory/current-state.md`
- `.factory/memory/change-summary.md`

### 6.3 改设计边界或正式合同

同步：

- `docs/04-project-development/`
- `.factory/memory/current-state.md`

## 7. 提交前最后检查

至少执行：

```bash
git diff --check
git status --short
```

不要提交这些内容：

- `.venv/`
- `dist/` 构建产物
- `generator/dist/` 二进制
- `solver_package/dist/` 构建产物
- `runs/`
- `reports/`
- 本地缓存

## 8. 一条推荐的本地维护闭环

1. 先判定改动属于哪个模块。
2. 只跑与该模块匹配的最小回归。
3. 如果改动越过模块边界，升级成跨模块验证。
4. 同步用户指南、开发者指南和 `.factory`。
5. 最后做 `git diff --check` 和 `git status --short`。
