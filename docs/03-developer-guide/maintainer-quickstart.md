# 维护者快速使用说明

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：第一次接手本仓库的维护者
- 负责人：Codex
- 最近更新：2026-04-04

## 0. 这页解决什么问题

这页只解决一件事：

- 一个新维护者进入仓库后，前 30 分钟应该按什么顺序理解项目并跑通最小验证

## 1. 先读什么

先按这个顺序读：

1. `AGENTS.md`
2. `.factory/project.json`
3. `.factory/memory/current-state.md`
4. `.factory/memory/change-summary.md`
5. `docs/index.md`
6. [用户指南总览](../02-user-guide/user-guide.md)
7. [仓库结构与边界](./repository-structure-and-boundaries.md)
8. [本地开发与验证工作流](./local-development-workflow.md)

这样做的目的很直接：

- 先知道当前项目是什么
- 再知道文档导航和访问边界
- 再知道仓库边界
- 最后再跑命令

## 2. 先确认本地工具

至少确认这些工具存在：

- `uv`
- Python 3.12
- Go 1.22+
- `git`

建议先跑：

```bash
uv --version
go version
git --version
```

## 3. 第一次进入仓库先跑什么

### 3.1 Python 侧最小回归

```bash
uv python install 3.12
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

### 3.2 Go 侧最小回归

```bash
cd generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
```

### 3.3 文档与补丁完整性检查

回到仓库根后执行：

```bash
git diff --check
git status --short
```

## 4. 接手后要先建立的心智模型

先记住 4 句就够：

1. 这个项目只有两个正式 CLI：`sinan-generator` 和 `sinan`
2. 生成器工作区不等于生成器安装目录
3. 训练目录不等于源码仓库
4. 生成器和训练 CLI 只通过 `group1 YOLO / group2 paired` 数据集目录交接

## 5. 常见维护任务怎么分

### 5.1 改用户操作路径

例如：

- 新增训练命令参数
- 调整安装方式
- 调整交付目录结构

这类改动要同步：

- `docs/02-user-guide/`
- `README.md`
- `.factory/memory/current-state.md`

### 5.2 改维护工作流

例如：

- 新增发布步骤
- 修改本地验证顺序
- 修改 Git 边界

这类改动要同步：

- `docs/03-developer-guide/`
- `.factory/memory/change-summary.md`

### 5.3 改设计和内部策略

这类改动要同步：

- `docs/04-project-development/`
- `.factory/memory/current-state.md`

## 6. 和 AI 协作时的最小要求

- 修缺陷时，不只报现象，要同步说明影响面
- 加需求时，不只改代码，要先改需求和设计
- 改目录或命令时，不只改实现，要同步公开文档
- 做完后，不只说“完成”，要说明跑了哪些验证

## 7. 什么时候说明你还没真正接手成功

出现下面任一情况，说明还不能算接手完成：

- 你还说不清 3 个运行目录的区别
- 你不知道哪个命令属于 `sinan-generator`，哪个属于 `sinan`
- 你没跑过任何 Python 或 Go 回归
- 你改了文档却没同步 `.factory`

## 8. 这页完成标志

如果你已经做到下面 5 件事，就说明你已经能开始维护这套工程：

1. 跑过 Python 最小回归
2. 跑过 Go 最小回归
3. 看过当前事实源和变更摘要
4. 能区分源码仓库、生成器工作区和训练目录
5. 知道下一个问题应该去用户指南、开发者指南还是内部设计文档里找
