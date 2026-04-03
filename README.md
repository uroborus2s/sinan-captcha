# sinan-captcha

`sinan-captcha` 是一个本地训练工程，用来生成和训练两类行为验证码模型：

- `group1`：图形点选
- `group2`：滑块缺口定位

项目对外只保留两个正式入口：

- `sinan-generator`
  - Go CLI
  - 负责固定工作区、素材导入/同步、原始样本生成、批次 QA、YOLO 数据集导出
- `sinan`
  - Python CLI
  - 负责训练目录初始化、素材包构建、JSONL 校验、YOLO 转换、自动标注、评估、训练、发布交付

运行时目录建议始终分开：

- 生成器安装目录：保存 `sinan-generator(.exe)` 和生成器配置
- 生成器工作区：保存 `workspace.json`、`presets/`、`materials/`、`cache/`、`jobs/`、`logs/`
- 训练目录：保存 `pyproject.toml`、`.venv/`、`datasets/`、`runs/`、`reports/`

## 仓库结构

下面是源码仓库结构，不是 Windows 训练机的推荐运行目录。训练机目录请看用户指南。

```text
sinan-captcha/
  generator/   # Go 生成器工程
  core/        # Python 训练与数据工程 CLI
  configs/     # 配置文件
  materials/   # 背景图、图标和素材 manifest
  datasets/    # 原始样本、reviewed 数据和 YOLO 数据集
  reports/     # QA 与评估输出
  docs/        # 正式文档
```

## 正式工作流

1. 用 `uvx --from sinan-captcha sinan env setup-train` 创建独立训练目录
2. 用 `sinan-generator workspace init --workspace <generator-workspace>` 初始化生成器固定工作区
3. 用 `sinan-generator materials import|fetch --workspace <generator-workspace>` 准备素材
4. 用 `sinan-generator make-dataset --workspace <generator-workspace>` 直接产出可交给训练 CLI 的 YOLO 数据集目录
5. 用 `uv run sinan train group1` 或 `uv run sinan train group2` 启动训练
6. 用 `uv run sinan evaluate` 做 JSONL 对比评估

## 典型命令

```bash
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work
uv run sinan release build --project-dir .
sinan-generator workspace init --workspace D:\sinan-captcha-generator\workspace
sinan-generator materials import --workspace D:\sinan-captcha-generator\workspace --from D:\materials-pack
sinan-generator make-dataset --workspace D:\sinan-captcha-generator\workspace --task group1 --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass\yolo
uv run sinan train group1 --dataset-yaml D:\sinan-captcha-work\datasets\group1\firstpass\yolo\dataset.yaml --project D:\sinan-captcha-work\runs\group1
```

## 文档入口

- [用户指南总览](docs/02-user-guide/user-guide.md)
- [使用交付物与正式 CLI](docs/02-user-guide/use-build-artifacts.md)
- [Windows 训练机安装与模型训练完整指南](docs/02-user-guide/from-base-model-to-training-guide.md)
- [训练完成后的模型使用与测试](docs/02-user-guide/use-and-test-trained-models.md)

## 当前事实

- 生成器模式：`group1 -> click/native`、`group2 -> slide/native`
- 训练标签：`gold` 真值必须通过一致性校验、重放校验和负样本校验
- 生成器交付给训练 CLI 的正式接口：YOLO 数据集目录 + `dataset.yaml`
- 如果生成器命令不显式传 `--workspace`，Windows 默认工作区会落在 `%LOCALAPPDATA%\\SinanGenerator`

这个项目不是 HTTP 服务，也不是单一可执行程序。它是一个围绕本地 CLI、训练数据和模型训练流程组织的工程。
