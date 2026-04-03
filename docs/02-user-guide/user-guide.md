# 用户指南总览

这份总览的目标很简单：让第一次接触这个项目的人，先建立正确的心智模型，再去读对自己有用的那一页。

## 1. 先记住项目是什么

`sinan-captcha` 不是网站服务，也不是单个安装包。它是一个“生成训练数据 + 训练模型”的本地工程。

项目当前只做两个专项：

- `group1`
  - 图形点选
- `group2`
  - 滑块缺口定位

对外只保留两个正式 CLI：

- `sinan-generator`
  - Go 生成器
  - 负责生成器工作区、素材导入、样本生成、批次 QA、YOLO 数据集导出
- `sinan`
  - Python CLI
  - 负责训练目录初始化、训练环境检查、训练数据工程、训练、评估、发布

## 2. 先区分 3 个目录概念

第一次上手最容易混淆的不是命令，而是目录。

### 2.1 生成器安装目录

这里通常放：

- `sinan-generator.exe`

推荐路径：

- `D:\sinan-captcha-generator`

说明：

- 普通用户不需要手工维护 `configs/*.yaml`
- 生成器内置预设会在首次运行时自动写入工作区 `presets/`

### 2.2 生成器工作区

这里才是真正保存运行时素材和任务记录的地方：

- `workspace.json`
- `presets/`
- `materials/`
- `cache/`
- `jobs/`
- `logs/`

推荐路径：

- `D:\sinan-captcha-generator\workspace`

如果你不显式传 `--workspace`，Windows 默认会落到：

- `%LOCALAPPDATA%\SinanGenerator`

### 2.3 训练目录

这里保存训练机运行环境和训练产物：

- `pyproject.toml`
- `.python-version`
- `.venv/`
- `datasets/`
- `runs/`
- `reports/`

推荐路径：

- `D:\sinan-captcha-work`

## 3. 常用占位符是什么意思

为了避免每一页都重复写很长路径，公开文档里有时会用这些占位符：

- `<generator-root>`
  - 生成器安装目录
  - 例如：`D:\sinan-captcha-generator`
- `<generator-workspace>`
  - 生成器工作区
  - 例如：`D:\sinan-captcha-generator\workspace`
- `<train-root>`
  - 训练目录
  - 例如：`D:\sinan-captcha-work`
- `<version>`
  - 你的数据版本名
  - 例如：`firstpass`、`v1`

## 4. 什么时候该用哪个 CLI

下面这个判断最重要：

- 你在处理素材、生成样本、做批次 QA，用 `sinan-generator`
- 你在处理训练目录、数据集、训练、评估，用 `sinan`

最常见的主链路是：

1. `uvx --from sinan-captcha sinan env setup-train`
2. `sinan-generator workspace init --workspace <generator-workspace>`
3. `sinan-generator materials import|fetch --workspace <generator-workspace>`
4. `sinan-generator make-dataset --workspace <generator-workspace>`
5. `uv run sinan train group1` 或 `uv run sinan train group2`
6. `uv run sinan evaluate`

## 5. 你应该从哪一页开始

### 5.1 我已经有 YOLO 数据集，只想最快开训

从这里开始：

- [Windows 快速开始](./windows-quickstart.md)

### 5.2 我要完整理解 Windows 安装和训练步骤

从这里开始：

- [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)

### 5.3 我要自己生成训练数据

从这里开始：

- [使用交付物与正式 CLI](./use-build-artifacts.md)
- [用生成器准备训练数据](./prepare-training-data-with-generator.md)

这里已经补齐：

- 素材包结构要求
- 如何补齐或增加素材
- 一次默认生成多少条
- 如何多次生成不同版本数据集
- 第一次生成好的数据后能否继续重复训练

### 5.4 我已经训练完，要做验证和验收

从这里开始：

- [训练完成后的模型使用与测试](./use-and-test-trained-models.md)

这里已经补齐：

- 第一次训练完成后先看什么
- `predict` / `val` / `evaluate` 各自适合看什么
- 同一份训练数据能否重复用于多轮训练

## 6. 这份总览刻意不做什么

- 不解释内部设计过程
- 不讲项目阶段推进
- 不混入维护者入口
- 不承载内部演进记录
