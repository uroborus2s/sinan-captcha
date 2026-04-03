# 用户指南总览

这份总览只做一件事：帮你快速理解这个项目现在该怎么用。

## 1. 先理解项目是什么

`sinan-captcha` 不是网站服务，也不是单个安装包。它是一个本地训练工程，由两个 CLI 组成：

- `sinan-generator`
  - Go 生成器
  - 负责固定工作区、素材导入/同步、原始样本生成、批次 QA、YOLO 数据集导出
- `sinan`
  - Python CLI
  - 负责训练目录初始化、自动标注、评估、训练、发布交付

项目当前覆盖两个专项：

- `group1`：图形点选
- `group2`：滑块缺口定位

## 2. 什么时候该用哪个 CLI

下面这个判断最重要：

- 你在处理素材、生成样本、做批次 QA，用 `sinan-generator`
- 你在处理训练目录、数据集、训练、评估和发布，用 `sinan`

最常见的工作流是：

1. `uvx --from sinan-captcha sinan env setup-train`
2. `sinan-generator workspace init --workspace <generator-workspace>`
3. `sinan-generator materials import|fetch --workspace <generator-workspace>`
4. `sinan-generator make-dataset --workspace <generator-workspace>`
5. `uv run sinan train group1` 或 `uv run sinan train group2`
6. `uv run sinan evaluate`

## 3. 你属于哪类读者

### 3.1 交付使用者

你更关心：

- 交付物有哪些
- 生成器目录和训练目录怎么分开
- 生成器和 Python CLI 各自负责什么

从这里开始：

- [使用交付物与正式 CLI](./use-build-artifacts.md)

### 3.2 训练执行者

你更关心：

- Windows + NVIDIA 训练环境怎么搭
- 如何一条命令创建训练目录并自动装环境
- 怎么从数据走到训练结果

从这里开始：

- [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)

### 3.3 模型验证者

你更关心：

- `best.pt` 在哪里
- 怎么做 `predict`、`val` 和 JSONL 对比评估
- 当前项目已经提供了哪些验收入口

从这里开始：

- [训练完成后的模型使用与测试](./use-and-test-trained-models.md)

## 4. 推荐阅读顺序

如果你只想尽快用起来，按这个顺序读：

1. 先看本页，理解双 CLI 边界
2. 再看 [使用交付物与正式 CLI](./use-build-artifacts.md)
3. 如果要在 Windows 上训练，继续看 [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)
4. 训练完成后再看 [训练完成后的模型使用与测试](./use-and-test-trained-models.md)

## 5. 这份总览刻意不做什么

- 不解释内部设计过程
- 不讲项目阶段推进
- 不混入维护者入口
- 不承载内部演进记录
