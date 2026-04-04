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
4. 哪些文件必须拷到训练机，哪些文件其实不需要
5. 生成器最终应该把什么交给训练 CLI

## 1. 当前正式交付物

### 1.1 Go 生成器

典型交付物：

- `sinan-generator.exe`

它负责：

- 初始化固定工作区
- 导入或同步素材包
- 生成 `group1/group2` 原始批次
- 对生成批次做 QA
- 直接导出任务专属训练数据集目录

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
- `uv run sinan train group1`
- `uv run sinan train group2`
- `uv run sinan evaluate`

其中：

- 普通训练执行者的主链路不需要 `materials build`
- 训练数据目录应直接由 `sinan-generator make-dataset` 生成
- `group1` 训练 CLI 的正式输入是现成数据集目录里的 `dataset.yaml`
- `group2` 训练 CLI 的正式输入是现成数据集目录里的 `dataset.json`

发布命令也已经收口到 `sinan release ...`，但那是维护者入口，不是训练执行者的主路径。

如果训练机上当前还是旧版 `0.1.1`，推荐直接用新版 `setup-train` 原地升级训练目录，而不是手工改训练目录里的依赖：

```powershell
uvx --from "sinan-captcha==0.1.3" sinan env setup-train `
  --train-root D:\sinan-captcha-work `
  --generator-root D:\sinan-captcha-generator `
  --yes
```

这会升级训练环境，但不会删除已有 `datasets\`、`runs\`、`reports\`。

### 1.3 运行资产

除了二进制和 Python 包，还会涉及这些运行资产：

- `materials/`
- `datasets/`
- `reports/`

但要注意：

- 普通用户不需要手工拷贝 `configs/*.yaml`
- 生成器内置预设会在首次运行时自动写入工作区 `presets/`
- 生成器当前内置 `smoke`、`firstpass`、`hard` 三个 preset；其中 `hard` 仍是 200 条样本，但会增加更强的阴影、背景模糊和边缘软化
- 生成器工作区只属于 `sinan-generator`
- 训练 CLI 最小只需要训练环境和正式训练数据集目录
- 如果训练机只负责训练，不在本地生成样本，就不需要生成器工作区

## 2. 3 种最常见的交付场景

| 场景 | 你手里要有的东西 | 不需要带什么 |
| --- | --- | --- |
| 只训练 | 训练目录初始化命令、正式训练数据集目录 | `materials/`、生成器工作区 |
| 本地生成再训练 | `sinan-generator.exe`、素材包目录/zip/下载地址、训练目录 | 源码仓库完整目录 |
| 交付给另一台训练机 | wheel 或 PyPI 包、生成器可执行文件、可选素材包、可选数据集 | `core/`、`generator/` 源码 |

## 3. 为什么要分成两个目录

当前推荐固定成两个目录：

```text
D:\
  sinan-captcha-generator\
  sinan-captcha-work\
```

职责如下：

- `sinan-captcha-generator`
  - 保存 `sinan-generator.exe`
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

## 4. 推荐目录结构

### 4.1 生成器安装目录与工作区

```text
D:\sinan-captcha-generator\
  sinan-generator.exe
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

普通用户不需要把 `configs/*.yaml` 复制到安装目录。`workspace init` 会自动在工作区写出 `presets/`。如果高级用户要覆盖默认视觉难度参数，也只允许改工作区里的固定命名 preset，不支持 `exe` 同级配置覆盖。

### 4.2 训练目录

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

## 5. 正式 CLI 边界

### 5.1 `sinan-generator`

你应该用它做这些事：

```powershell
sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
sinan-generator.exe materials import --workspace D:\sinan-captcha-generator\workspace --from D:\materials-pack
sinan-generator.exe make-dataset --workspace D:\sinan-captcha-generator\workspace --task group1 --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass\yolo
```

### 5.2 `sinan`

你应该用它做这些事：

```powershell
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work --generator-root D:\sinan-captcha-generator
uv run sinan train group1 --dataset-version firstpass --name firstpass
uv run sinan evaluate --task group1 --gold-dir D:\sinan-captcha-work\datasets\group1\reviewed\batch_0001 --prediction-dir D:\sinan-captcha-work\reports\group1\pred_jsonl_v1 --report-dir D:\sinan-captcha-work\reports\group1\eval_jsonl_v1
uv run sinan release build --project-dir <源码仓库目录>
```

其中最后这条 `release build` 是发布者/维护者命令，不是训练执行者的必经步骤。

## 6. 训练机到底要拷什么

### 6.1 如果这台机器只负责训练

最小只要：

- `uv`
- PyPI 上的 `sinan-captcha`
  或
- wheel 文件
- 至少一个正式训练数据集目录

不需要：

- `materials/`
- 生成器工作区
- 源码仓库

### 6.2 如果这台机器要本地生成再训练

至少再补上：

- `sinan-generator.exe`
- 一个明确约定的生成器工作区路径
  - 运行时会自动创建
  或
- 一个素材包目录
  或
- 一个素材包 zip
  或
- 一个可访问的素材包下载地址

### 6.3 如果你要给别人做交付包

建议交付：

- Python wheel
- `sinan-generator.exe`
- `README-交付包说明.txt`
- 可选的 `materials-pack/`
- 可选的 `materials-pack.zip`
- 可选的 `datasets/`

如果你准备按交付包方式在训练机上安装，再继续读：

- [使用交付包在 Windows 训练机上安装](./windows-bundle-install.md)

## 7. 三种典型使用方式

### 7.1 只训练

你只需要：

1. 创建训练目录
2. 把训练数据集拷到 `D:\sinan-captcha-work\datasets\...`
3. 执行训练命令

这种方式不需要 `materials/`，也不需要在训练机上运行生成器。

### 7.2 先生成，再训练

你需要：

1. 初始化生成器工作区
2. 让生成器直接输出一个完整训练数据集目录
3. 把这个数据集目录交给训练 CLI
4. 在训练目录里训练

### 7.3 交付给另一台 Windows 训练机

你需要准备：

- Python 包发布源或 wheel
- `sinan-generator.exe`
- 可选的 `materials-pack/`
- 可选的 `materials-pack.zip`
- 可选的 `datasets/`

然后让训练机先执行：

```powershell
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work --generator-root D:\sinan-captcha-generator
```

## 8. 一个最常见的主链路

### 8.1 在训练机创建训练目录

```powershell
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work --generator-root D:\sinan-captcha-generator
```

### 8.2 在生成器工作区准备素材

```powershell
sinan-generator.exe materials import --workspace D:\sinan-captcha-generator\workspace --from D:\materials-pack
```

### 8.3 直接生成训练数据集目录

```powershell
sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass\yolo
```

或：

```powershell
sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group2 `
  --dataset-dir D:\sinan-captcha-work\datasets\group2\firstpass
```

### 8.4 把数据集目录交给训练 CLI

```powershell
uv run sinan train group1 `
  --dataset-version firstpass `
  --name firstpass
```

### 8.5 交接边界

- `group1` 生成器交付：`dataset.yaml` + `images/` + `labels/` + `.sinan/`
- `group1` 训练 CLI 输入：
  - 显式模式：`--dataset-yaml <dataset-dir>\dataset.yaml`
  - 默认模式：在训练目录里使用 `--dataset-version <版本目录名>`
- `group2` 生成器交付：`dataset.json` + `master/` + `tile/` + `splits/` + `.sinan/`
- `group2` 训练 CLI 输入：
  - 显式模式：`--dataset-config <dataset-dir>\dataset.json`
  - 默认模式：在训练目录里使用 `--dataset-version <版本目录名>`
- 训练 CLI 不读取生成器工作区
- 生成器不负责训练环境和 `runs/`

## 9. 当前公开边界

当前文档只承认下面这套正式使用方式：

- 训练目录通过 `uvx --from sinan-captcha sinan env setup-train` 初始化
- 训练数据生成走 `sinan-generator make-dataset --workspace <generator-workspace>`
- 训练 CLI 和生成器只通过数据集目录交接
- 数据工程和训练走 `uv run sinan`
- `group1` 的底层训练/验证继续走 `uv run yolo`
- `group2` 的训练/验证走 paired runner 与 `uv run sinan evaluate`

不要把脚本目录当成公开入口，也不要把这个项目理解成线上验证码服务。

## 10. 这页完成标志

如果你已经能做到下面 5 件事，就说明你已经掌握了交付物的使用方式：

1. 能区分 `sinan-generator` 和 `sinan` 的职责
2. 能区分生成器安装目录、生成器工作区和训练目录
3. 知道 `materials/` 只属于生成器目录
4. 能把样本直接生成到训练目录的 `datasets/`
5. 能把生成器产出的任务专属训练数据集目录直接交给训练 CLI 并启动训练

下一步继续读：

- 如果你要最快开训，读 [Windows 快速开始](./windows-quickstart.md)
- 如果你要完整操作手册，读 [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)
- 如果你要自己生成数据，读 [用生成器准备训练数据](./prepare-training-data-with-generator.md)
