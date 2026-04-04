# sinan-captcha

`sinan-captcha` 是一个本地 CLI 工程，用来生成和训练两类行为验证码模型：

- `group1`：图形点选
- `group2`：滑块缺口定位

如果你是第一次上手，先按你的起点选入口：

- 已经有 YOLO 数据集，只想尽快开训：
  - [Windows 快速开始](docs/02-user-guide/windows-quickstart.md)
- 还没有训练数据，想先生成训练数据：
  - [用生成器准备训练数据](docs/02-user-guide/prepare-training-data-with-generator.md)
- 想看完整 Windows 安装和训练过程：
  - [Windows 训练机安装与模型训练完整指南](docs/02-user-guide/from-base-model-to-training-guide.md)
- 训练完成后想看效果和验收：
  - [训练完成后的模型使用与测试](docs/02-user-guide/use-and-test-trained-models.md)

## 最短心智模型

项目对外只保留两个正式入口：

- `sinan-generator`
  - 负责素材导入/抓取、样本生成、批次 QA、YOLO 数据集导出
- `sinan`
  - 负责训练目录初始化、训练环境检查、训练、评估

两者通过一个稳定交接面配合：

- YOLO 数据集目录
- `dataset.yaml`
- `images/`
- `labels/`
- `.sinan/`

运行时目录建议始终分开：

- 生成器安装目录：保存 `sinan-generator(.exe)`
- 生成器工作区：保存 `workspace.json`、`presets/`、`materials/`、`cache/`、`jobs/`、`logs/`
- 训练目录：保存 `pyproject.toml`、`.venv/`、`datasets/`、`runs/`、`reports/`

普通用户不需要手工拷贝 `configs/*.yaml`。生成器预设会在首次运行时自动写入工作区 `presets/`。

如果你在 Windows PowerShell 里从当前目录执行生成器，命令要写成：

```powershell
.\sinan-generator.exe ...
```

## 最短流程

1. 用 `uvx --from sinan-captcha sinan env setup-train` 创建独立训练目录
2. 用 `sinan-generator workspace init --workspace <generator-workspace>` 初始化生成器固定工作区
3. 用 `sinan-generator materials import|fetch --workspace <generator-workspace>` 准备素材
4. 用 `sinan-generator make-dataset --workspace <generator-workspace>` 直接产出可交给训练 CLI 的 YOLO 数据集目录
5. 用 `uv run sinan train group1` 或 `uv run sinan train group2` 启动训练
6. 用 `uv run sinan test group1|group2` 做一键预测 + 验证，并生成中文报告
7. 如果已有 JSONL 预测结果，再用 `uv run sinan evaluate` 做任务契约级评估

## 典型命令

```powershell
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work
Set-Location D:\sinan-captcha-generator
.\sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
.\sinan-generator.exe materials import --workspace D:\sinan-captcha-generator\workspace --from D:\materials-pack
.\sinan-generator.exe make-dataset --workspace D:\sinan-captcha-generator\workspace --task group1 --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass\yolo
Set-Location D:\sinan-captcha-work
uv run sinan train group1 --dataset-version firstpass --name firstpass
uv run sinan test group1 --dataset-version firstpass --train-name firstpass
```

默认样本规模：

- `smoke`：20 条
- `firstpass`：200 条

如果你对同一个 `dataset-dir` 重跑 `make-dataset` 并加 `--force`，会覆盖原目录；如果要保留旧数据，请换一个新的版本目录。

继续训练的两个正式入口：

- 训练中断后继续当前版本：
  - `uv run sinan train group1 --name firstpass --resume`
- 在上一轮最佳模型基础上开新一轮：
  - `uv run sinan train group1 --dataset-version firstpass_v2 --name round2 --from-run firstpass`

## 文档入口

- [用户指南总览](docs/02-user-guide/user-guide.md)
- [使用交付物与正式 CLI](docs/02-user-guide/use-build-artifacts.md)
- [用生成器准备训练数据](docs/02-user-guide/prepare-training-data-with-generator.md)
- [Windows 训练机安装与模型训练完整指南](docs/02-user-guide/from-base-model-to-training-guide.md)
- [训练完成后的模型使用与测试](docs/02-user-guide/use-and-test-trained-models.md)

## 开发者入口

- [开发者指南概览](docs/03-developer-guide/index.md)

下面是源码仓库结构，不是 Windows 训练机的推荐运行目录。训练机目录请看用户指南。

```text
sinan-captcha/
  generator/   # Go 生成器工程
  core/        # Python 训练与数据工程 CLI
  configs/     # 配置与素材规格
  materials/   # 本地素材目录或构建产物
  datasets/    # 原始样本、reviewed 数据和 YOLO 数据集
  reports/     # QA 与评估输出
  docs/        # 正式文档
```

## 当前事实

- 生成器模式：`group1 -> click/native`、`group2 -> slide/native`
- 训练标签：`gold` 真值必须通过一致性校验、重放校验和负样本校验
- 生成器交付给训练 CLI 的正式接口：YOLO 数据集目录 + `dataset.yaml`
- 如果生成器命令不显式传 `--workspace`，Windows 默认工作区会落在 `%LOCALAPPDATA%\\SinanGenerator`

这个项目不是 HTTP 服务，也不是单一可执行程序。它是一个围绕本地 CLI、训练数据和模型训练流程组织的工程。
