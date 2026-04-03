# 使用交付物与正式 CLI

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：交付使用者、训练执行者
- 负责人：Codex

## 0. 这页解决什么问题

这页说明当前项目有哪些正式交付物，以及它们应该如何被使用。

读完后你应能明确：

1. 现在项目实际交付什么
2. `sinan-generator` 和 `sinan` 的职责边界
3. 为什么生成器安装目录、生成器工作区和训练目录要分开
4. 生成器最终应该把什么交给训练 CLI

## 1. 当前正式交付物

### 1.1 Go 生成器

典型交付物：

- `sinan-generator.exe`

它负责：

- 初始化固定工作区
- 导入或同步素材包
- 生成 `group1/group2` 原始批次
- 对生成批次做 QA
- 直接导出 YOLO 数据集目录

它不负责：

- 自动标注
- 模型训练
- 模型评估
- 训练环境初始化

### 1.2 Python CLI

当前 Python 侧正式入口是 `sinan`。

对训练机使用者来说，优先路径是：

- 直接从 PyPI 使用 `uvx --from sinan-captcha sinan ...`
- 或安装现成 wheel 后再用 `uv run sinan ...`

常用命令包括：

- `uv run sinan env check`
- `uvx --from sinan-captcha sinan env setup-train`
- `uv run sinan materials build`
- `uv run sinan dataset validate`
- `uv run sinan dataset build-yolo`
- `uv run sinan autolabel`
- `uv run sinan evaluate`
- `uv run sinan train group1`
- `uv run sinan train group2`

发布命令也已经收口到 `sinan release ...`，但那是维护者入口，不是训练执行者的主路径。

### 1.3 运行资产

除了二进制和 Python 包，还会涉及这些运行资产：

- `generator/configs/*.yaml`
- `materials/`
- `datasets/`
- `reports/`

但要注意：

- 生成器工作区只属于 `sinan-generator`
- 训练 CLI 最小只需要训练环境和 `dataset.yaml`
- 如果训练机只负责训练，不在本地生成样本，就不需要生成器工作区

## 2. 为什么要分成两个目录

当前推荐固定成两个目录：

```text
D:\
  sinan-captcha-generator\
  sinan-captcha-work\
```

职责如下：

- `sinan-captcha-generator`
  - 保存 `sinan-generator.exe`
  - 保存生成器配置
  - 可选保存一个显式工作区目录，例如 `workspace\`
- `sinan-captcha-work`
  - 保存训练目录自己的 `pyproject.toml`
  - 保存训练目录自己的 `.venv`
  - 保存 `datasets/`、`runs/`、`reports/`
  - 负责训练、评估和训练输出

还要再区分一个概念：

- 生成器工作区
  - 真正保存 `workspace.json`、`presets/`、`materials/`、`cache/`、`jobs/`、`logs/`
  - 如果你不传 `--workspace`，Windows 默认会落到 `%LOCALAPPDATA%\SinanGenerator`
  - 如果你希望目录更可控，建议显式固定成 `D:\sinan-captcha-generator\workspace`

这样分开的原因很直接：

- 训练目录不必背生成器素材
- 生成器目录不必背训练环境
- 训练机既可以“只训练”，也可以“本地生成再训练”
- 出问题时更容易判断是生成端还是训练端

## 3. 推荐目录结构

### 3.1 生成器安装目录与工作区

```text
D:\sinan-captcha-generator\
  sinan-generator.exe
  configs\
  workspace\
    workspace.json
    presets\
    materials\
    cache\
    jobs\
    logs\
```

如果你不想显式指定 `--workspace`，默认工作区会落在：

```text
%LOCALAPPDATA%\SinanGenerator\
```

### 3.2 训练目录

```text
D:\sinan-captcha-work\
  pyproject.toml
  .python-version
  .venv\
  datasets\
    group1\
    group2\
  runs\
    group1\
    group2\
  reports\
    group1\
    group2\
  README-训练机使用说明.txt
```

## 4. 正式 CLI 边界

### 4.1 `sinan-generator`

你应该用它做这些事：

```powershell
sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
sinan-generator.exe materials import --workspace D:\sinan-captcha-generator\workspace --from D:\materials-pack
sinan-generator.exe make-dataset --workspace D:\sinan-captcha-generator\workspace --task group1 --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass\yolo
```

### 4.2 `sinan`

你应该用它做这些事：

```powershell
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work --generator-root D:\sinan-captcha-generator
uv run sinan train group1 --dataset-yaml D:\sinan-captcha-work\datasets\group1\firstpass\yolo\dataset.yaml --project D:\sinan-captcha-work\runs\group1
uv run sinan evaluate --task group1 --gold-dir D:\sinan-captcha-work\datasets\group1\reviewed\batch_0001 --prediction-dir D:\sinan-captcha-work\reports\group1\pred_jsonl_v1 --report-dir D:\sinan-captcha-work\reports\group1\eval_jsonl_v1
uv run sinan release build --project-dir <源码仓库目录>
```

其中最后这条 `release build` 是发布者/维护者命令，不是训练执行者的必经步骤。

## 5. 三种典型使用方式

### 5.1 只训练

你只需要：

1. 创建训练目录
2. 把 YOLO 数据集拷到 `D:\sinan-captcha-work\datasets\...`
3. 执行训练命令

这种方式不需要 `materials/`，也不需要在训练机上运行生成器。

### 5.2 先生成，再训练

你需要：

1. 初始化生成器工作区
2. 让生成器直接输出一个完整 YOLO 数据集目录
3. 把这个数据集目录交给训练 CLI
4. 在训练目录里训练

### 5.3 交付给另一台 Windows 训练机

你需要准备：

- Python 包发布源或 wheel
- `sinan-generator.exe`
- 生成器配置
- `materials-pack.toml`
- 可选的 `materials/`
- 可选的 `datasets/`

然后让训练机先执行：

```powershell
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work --generator-root D:\sinan-captcha-generator
```

## 6. 一个最常见的主链路

### 6.1 在训练机创建训练目录

```powershell
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work --generator-root D:\sinan-captcha-generator
```

### 6.2 在生成器工作区准备素材

```powershell
sinan-generator.exe materials import --workspace D:\sinan-captcha-generator\workspace --from D:\materials-pack
```

### 6.3 直接生成 YOLO 数据集目录

```powershell
sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass\yolo
```

### 6.4 把数据集目录交给训练 CLI

```powershell
uv run sinan train group1 `
  --dataset-yaml D:\sinan-captcha-work\datasets\group1\firstpass\yolo\dataset.yaml `
  --project D:\sinan-captcha-work\runs\group1 `
  --name firstpass
```

### 6.5 交接边界

- 生成器交付：`dataset.yaml` + `images/` + `labels/` + `.sinan/`
- 训练 CLI 输入：`--dataset-yaml <dataset-dir>\dataset.yaml`
- 训练 CLI 不读取生成器工作区
- 生成器不负责训练环境和 `runs/`

## 7. 当前公开边界

当前文档只承认下面这套正式使用方式：

- 训练目录通过 `uvx --from sinan-captcha sinan env setup-train` 初始化
- 训练数据生成走 `sinan-generator make-dataset --workspace <generator-workspace>`
- 训练 CLI 和生成器只通过数据集目录交接
- 数据工程和训练走 `uv run sinan`
- 权重验证和模型验收继续走 `uv run yolo` 与 `uv run sinan evaluate`

不要把脚本目录当成公开入口，也不要把这个项目理解成线上验证码服务。

## 8. 这页完成标志

如果你已经能做到下面 5 件事，就说明你已经掌握了交付物的使用方式：

1. 能区分 `sinan-generator` 和 `sinan` 的职责
2. 能区分生成器安装目录、生成器工作区和训练目录
3. 知道 `materials/` 只属于生成器目录
4. 能把样本直接生成到训练目录的 `datasets/`
5. 能把生成器产出的 YOLO 数据集目录直接交给训练 CLI 并启动训练

下一步继续读：

- [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)
