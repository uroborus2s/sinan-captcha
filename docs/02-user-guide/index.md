# 用户指南概览

本目录面向真实 Windows 训练机使用者，只回答一件事：怎样把 `sinan-captcha` 用起来。

如果你是第一次上手，先按你的起点选入口：

- 已经有现成训练数据集，只想尽快开训：
  - [Windows 快速开始](./windows-quickstart.md)
- 还没有训练数据，想先生成训练数据：
  - [用生成器准备训练数据](./prepare-training-data-with-generator.md)
- 想看完整 Windows 安装和训练过程：
  - [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)
- 训练完成后想看效果和验收：
  - [训练完成后的模型使用与测试](./use-and-test-trained-models.md)
- 卡在 CUDA 版本或 GPU 环境确认：
  - [如何确认 Windows 电脑上的 CUDA 版本](./how-to-check-cuda-version.md)

## 最短心智模型

项目当前对外只保留两个 CLI：

- `sinan-generator`
  - 负责素材导入/抓取、样本生成、批次 QA、导出任务专属训练数据集
- `sinan`
  - 负责训练目录初始化、训练环境自检、训练、评估

两者通过一个稳定交接面配合：

- `group1`：YOLO 数据集目录
- `group1/dataset.yaml`
- `group1/images/`
- `group1/labels/`
- `group2`：paired dataset 目录
- `group2/dataset.json`
- `group2/master/`
- `group2/tile/`
- `group2/splits/`
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
4. 用 `sinan-generator make-dataset --workspace <generator-workspace>` 直接产出可交给训练 CLI 的任务专属数据集目录
5. 用 `uv run sinan train group1` 或 `uv run sinan train group2` 启动训练
6. 用 `uv run sinan evaluate` 做 JSONL 对比评估

默认样本规模：

- `smoke`：20 条
- `firstpass`：200 条
- `hard`：200 条，使用更强的阴影、背景模糊和边缘软化

如果你对同一个 `dataset-dir` 重跑 `make-dataset` 并加 `--force`，会覆盖原目录；如果要保留旧数据，请换一个新的版本目录。

## 补充入口

- [使用指南总览](./user-guide.md)
- [使用交付物与正式 CLI](./use-build-artifacts.md)
- [使用交付包在 Windows 训练机上安装](./windows-bundle-install.md)

## 本目录不包含什么

- 内部设计文档
- 项目阶段文档
- AI 协作规则
- 维护者过程说明

如果你要的是维护仓库、推进实现或查看内部设计，请转到开发者指南和项目开发文档。
