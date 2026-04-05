# 本地开发与验证工作流

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：会在本仓库内改代码、改文档、跑验证的维护者
- 负责人：Codex
- 最近更新：2026-04-05

## 0. 这页解决什么问题

这页说明维护者在本地改动时，应该按什么顺序工作，才能避免出现：

- 只改代码，不改文档
- 只改文档，不改 `.factory`
- 改完 Python，没跑 Go 回归
- 改完生成器交接面，却没检查用户文档

## 1. 先判断你改的是哪一类变更

### 1.1 文档类

例如：

- 用户指南重构
- 开发者指南补齐
- 目录和导航调整

### 1.2 Python CLI 类

例如：

- `sinan` 子命令
- 训练目录初始化
- 训练命令
- 发布命令

### 1.3 Go 生成器类

例如：

- 工作区
- 素材导入/同步
- 数据集导出
- 生成侧 QA

### 1.4 跨边界类

例如：

- `group1 dataset.json / group2 dataset.json` 契约变化
- 生成器交付目录变化
- 发布交付目录变化
- solver bundle 合同变化
- 训练目录结构变化

跨边界类一定要同时更新：

- 代码
- 文档
- `.factory`

## 2. 本地开发前置

至少准备好：

- `uv`
- Python 3.12
- Go 1.22+

推荐先做：

```bash
uv python install 3.12
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

Go 回归单独在生成器目录执行：

```bash
cd generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
```

## 3. 一条标准维护者工作流

### 3.1 先看事实源

进入较大改动前，至少先读：

1. `AGENTS.md`
2. `.factory/project.json`
3. `.factory/memory/current-state.md`
4. `.factory/memory/change-summary.md`

### 3.2 再决定你改动影响哪一层

最少判断这三件事：

1. 是否改了对外 CLI
2. 是否改了目录结构
3. 是否改了交接契约

### 3.3 动手改

改动时保持一个原则：

- 用户感知变化先同步 `docs/02-user-guide/`
- 维护流程变化同步 `docs/03-developer-guide/`
- 事实变化同步 `.factory/memory/`

### 3.4 改完立即做最小验证

#### 只改文档

至少执行：

```bash
git diff --check
```

#### 改 Python

至少执行：

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
git diff --check
```

#### 改 Go

至少执行：

```bash
cd generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
```

然后回仓库根再做：

```bash
git diff --check
```

#### 改跨边界契约

至少执行：

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
cd generator && GOCACHE=/tmp/sinan-go-build-cache go test ./...
git diff --check
```

## 4. 用户可见改动必须同步哪里

### 4.1 改用户命令

同步更新：

- `README.md`
- `docs/index.md`
- `docs/02-user-guide/`
- 必要时 `docs/01-getting-started/index.md`

### 4.2 改维护者工作流

同步更新：

- `docs/index.md`
- `docs/03-developer-guide/`
- `.factory/memory/current-state.md`
- `.factory/memory/change-summary.md`

### 4.3 改内部策略或设计边界

同步更新：

- `docs/04-project-development/`
- `.factory/memory/current-state.md`

### 4.4 改 solver / bundle 集成面

同步更新：

- `docs/02-user-guide/use-solver-bundle.md`
- `docs/03-developer-guide/solver-bundle-and-integration.md`
- `docs/04-project-development/04-design/`
- `docs/04-project-development/07-release-delivery/`
- `.factory/memory/current-state.md`

## 5. 常用命令清单

### 5.1 Python 测试

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

### 5.2 Go 测试

```bash
cd generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
```

### 5.3 Python 分发构建

```bash
uv run sinan release build --project-dir .
```

### 5.4 生成 Windows 交付包

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe generator/dist/generator/windows-amd64/sinan-generator.exe \
  --output-dir dist/windows-bundle-0.1.13
```

### 5.5 在训练目录中做默认路径 dry-run

如果当前目录已经是训练目录：

```bash
uv run sinan train group1 --dataset-version firstpass --name smoke --dry-run
```

## 6. 什么时候不要提交

出现下面任一情况，先不要提交：

- `git status` 里混入了运行时产物
- 文档与实现口径不一致
- `.factory` 没同步
- 只改了用户指南，没改对应的开发者说明
- 改了训练或生成命令，但没做最小验证

## 7. 这页完成标志

如果你已经能按这套顺序完成一次“修改 -> 验证 -> 同步文档 -> 净化仓库”的闭环，就说明这页已经足够支撑本地维护。
