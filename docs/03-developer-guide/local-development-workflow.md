# 模块编译与本地验证

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：会在本仓库内改代码、改文档、改发布流程的开发者
- 最近更新：2026-04-11

## 0. 这页解决什么问题

这页回答的是：

- 每个模块平时应该怎么开发、怎么编译、怎么验证
- 跨模块改动时，最少要补哪些检查

## 1. 开发前先判断你改了哪一层

### 1.1 `packages/sinan-captcha`

典型改动：

- `sinan` 子命令
- 训练、评估、自主训练
- 发布打包逻辑

主要目录：

- `packages/sinan-captcha/core/`
- `tests/python/`
- `packages/sinan-captcha/pyproject.toml`

### 1.2 `packages/generator`

典型改动：

- 工作区
- 素材导入/拉取
- 数据集导出
- 生成侧 QA

主要目录：

- `packages/generator/`

### 1.3 `packages/solver`

典型改动：

- `sinanz` 公共 API
- 包资源
- Rust 原生桥接

主要目录：

- `packages/solver/src/`
- `packages/solver/resources/`
- `packages/solver/tests/`

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

### 1.5 根目录统一编译入口

如果你这次同时改了训练 CLI、生成器或 solver 的发布边界，优先直接在仓库根目录执行：

```bash
uv run python scripts/repo.py build all
```

如果要顺手产出 Windows 版生成器：

```bash
uv run python scripts/repo.py build generator --goos windows --goarch amd64
```

正式发布链路仍然是：

```bash
uv run sinan release build-all --project-dir .
```

如果要顺手产出 Windows 版生成器：

```bash
uv run sinan release build-all --project-dir . --goos windows --goarch amd64
```

输出目录固定为：

- `packages/sinan-captcha/dist/`
- `packages/generator/dist/<goos>-<goarch>/`
- `packages/solver/dist/`

当前行为：

- 编译前会先清理对应输出目录
- `.gitignore` 会保留
- 生成器构建后会校验目标二进制是否真的生成

## 2. 根仓库 Python 模块工作流

### 2.1 常用命令

跑测试：

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

构建包：

```bash
uv run python scripts/repo.py build sinan-captcha
```

安装烟测：

```bash
uvx --from ./packages/sinan-captcha/dist/sinan_captcha-<version>-py3-none-any.whl sinan --help
```

### 2.2 什么时候至少跑这一层

- 改了 `packages/sinan-captcha/core/`
- 改了 `packages/sinan-captcha/pyproject.toml`
- 改了 `.opencode/` 资源
- 改了发布命令

## 3. Go 生成器模块工作流

### 3.1 常用命令

跑测试：

```bash
cd packages/generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
cd ..
```

从根目录构建当前 Go 目标：

```bash
uv run python scripts/repo.py build generator
```

输出进入：

- `packages/generator/dist/<goos>-<goarch>/`

当前会先清空该目标目录，再写入新的二进制。

目标平台构建：

```bash
uv run python scripts/repo.py build generator --goos windows --goarch amd64
```

### 3.2 什么时候至少跑这一层

- 改了 `packages/generator/cmd/`
- 改了 `packages/generator/internal/`
- 改了生成器 CLI 参数
- 改了工作区、素材或数据集导出逻辑

## 4. 独立 solver 包模块工作流

### 4.1 常用命令

跑测试：

```bash
cd packages/solver
uv run pytest
cd ..
```

构建包：

```bash
uv run python scripts/repo.py build solver
```

### 4.2 什么时候至少跑这一层

- 改了 `packages/solver/src/`
- 改了 `packages/solver/resources/`
- 改了 solver 资产加载方式
- 改了独立 API 或资源目录结构

## 5. 跨模块改动的最低验证矩阵

| 改动类型 | 最少验证 |
| --- | --- |
| 只改开发者文档 | `git diff --check` |
| 只改根仓库 Python | `uv run python -m unittest discover -s tests/python -p 'test_*.py'` |
| 只改 Go 生成器 | `cd packages/generator && GOCACHE=/tmp/sinan-go-build-cache go test ./...` |
| 只改 `solver` | `cd packages/solver && uv run pytest` |
| 改发布链路 | 根仓库 Python 测试 + `uv run sinan release build --project-dir .` |
| 改交付包结构 | 根仓库 Python 测试 + 生成器构建 + `package-windows` 烟测 |
| 改数据/资产交接合同 | 根仓库 Python 测试 + Go 测试 + `solver` 测试 |

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
- `packages/generator/dist/` 二进制
- `packages/solver/dist/` 构建产物
- `runs/`
- `work_home/reports/`
- 本地缓存

## 8. 一条推荐的本地维护闭环

1. 先判定改动属于哪个模块。
2. 只跑与该模块匹配的最小回归。
3. 如果改动越过模块边界，升级成跨模块验证。
4. 同步用户指南、开发者指南和 `.factory`。
5. 最后做 `git diff --check` 和 `git status --short`。
