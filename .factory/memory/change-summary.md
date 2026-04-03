# 变更摘要

## 2026-04-03 文档读者视角收口与仓库忽略规则修正

- 已按读者视角重审公开文档，并收口到统一目录心智模型：
  - 生成器安装目录
  - 生成器工作区
  - 训练目录
- 已修正文档中容易混淆的点：
  - 不再把 `sinan-captcha-generator` 直接描述成工作区本身
  - 显式说明 Windows 默认工作区仍落在 `%LOCALAPPDATA%\\SinanGenerator`
  - 公开命令示例统一补上 `sinan-generator --workspace <generator-workspace>`
- 已同步更新：
  - `README.md`
  - `configs/workspace.example.yaml`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/how-to-check-cuda-version.md`
  - `docs/04-project-development/07-release-delivery/index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/tech-stack.summary.md`
- 已修正忽略规则，避免下列运行时产物继续进入 Git：
  - `materials/manifests/backgrounds.csv`
  - `materials/manifests/icons.csv`
  - `materials/quarantine/`

## 2026-04-03 生成器产品化与训练 CLI 交接面收口

- 已新增生成器产品化规范文档：
  - `docs/04-project-development/04-design/generator-productization.md`
- 已把生成器与训练 CLI 的正式交界面收口为：
  - 生成器输出 `dataset.yaml`、`images/`、`labels/` 与 `.sinan/`
  - 训练 CLI 只消费 `--dataset-yaml <dataset-dir>/dataset.yaml`
- 已重写 Go 侧生成器入口：
  - `workspace init|show`
  - `materials import|fetch`
  - `make-dataset`
- 已新增固定工作区能力：
  - 首次启动自动创建默认工作区
  - 默认工作区展开 `presets/`、`materials/`、`cache/`、`jobs/`、`logs/`
  - 不再支持 EXE 同级便携模式
- 已新增素材产品层：
  - 可把本地素材目录导入工作区
  - 可把 zip 包或远程地址同步到 `materials/official/`
  - 工作区会维护当前激活素材集
- 已新增 Go 侧数据集导出层：
  - 生成器内部直接把 raw batch 导出成 YOLO 数据集目录
  - `dataset.yaml` 已与训练 CLI 对齐为相对路径 `path: .`
  - `.sinan/raw/`、`manifest.json`、`job.json` 保留审计线索，但不参与训练 CLI 输入
- 已更新公开文档与设计文档，移除旧的公开口径：
  - `README.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/04-project-development/04-design/graphic-click-generator-design.md`
  - `docs/04-project-development/04-design/api-design.md`
- 已新增/通过 Go 回归：
  - `generator/internal/workspace/workspace_test.go`
  - `generator/internal/materialset/store_test.go`
  - `generator/internal/app/make_dataset_test.go`
- 已完成命令级冒烟：
  - `go run ./cmd/sinan-generator workspace init --workspace /tmp/sinan-generator-smoke-workspace`
  - `go run ./cmd/sinan-generator make-dataset --task group1 --preset smoke --workspace /tmp/sinan-generator-smoke-workspace --materials-source /Users/uroborus/AiProject/sinan-captcha/materials --dataset-dir /tmp/sinan-generator-smoke-dataset`
- 回归验证通过：
  - `GOCACHE=/tmp/sinan-go-build go test ./...`

## 2026-04-03 本地发布与训练目录初始化

- 已新增训练扩展依赖：`sinan-captcha[train]`
- `torch` 继续不直接打进主包，而是由训练目录运行时 `pyproject.toml` 根据检测到的 CUDA 后端安装
- 已新增 `core/ops/setup_train.py`，提供：
  - `uvx --from sinan-captcha sinan env setup-train`
  - 自动检测 `nvidia-smi` / CUDA 版本
  - 输出中文摘要并在确认后创建独立训练目录
  - 自动生成 `.python-version`、`pyproject.toml`、`README-训练机使用说明.txt`
  - 自动执行 `uv sync`
- 已明确分离两个运行目录：
  - 生成器目录：`sinan-generator.exe`、配置、`materials/`
  - 训练目录：运行时 `pyproject.toml`、`.venv`、`datasets/`、`runs/`、`reports/`
- 已新增本地发布 CLI：
  - `uv run sinan release build`
  - `uv run sinan release publish --token-env PYPI_TOKEN`
  - `uv run sinan release package-windows`
- 已新增 Windows 交付打包能力，可把 wheel、生成器二进制、配置和可选资产整理成独立交付包
- 已把训练前依赖缺失提示改成中文引导，明确提示先创建训练目录并执行 `uv sync`
- 已将 `dataset.yaml` 的 `path:` 改为相对路径 `.`
- 已新增 Python 单测覆盖：
  - 发布 CLI 分发
  - 本地发布服务
  - 训练目录初始化
  - 相对路径 `dataset.yaml`
- 回归验证通过：
  - `/Users/uroborus/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12 -m unittest discover -s tests/python -p 'test_*.py'`
  - `GOCACHE=/tmp/sinan-go-build-cache go test ./...`
  - `git diff --check`

## 2026-04-03 双 CLI 边界重构与仓库净化

- 已重新对齐项目正式边界：
  - Go 生成器统一为 `sinan-generator`
  - Python 训练与数据工程统一为 `sinan`
- 已为 Go 生成器补齐 `init-materials`，让素材目录骨架初始化也由 Go CLI 负责
- 已删除旧的 `scripts/*` 薄包装入口，避免继续出现“一个功能一个脚本”的散乱入口形态
- 已删除过时的 Python generator runner，生成器与训练链路改为通过文件契约对接
- 已清理 `.cache/`、`materials_stage*/`、空脚本目录与 `__pycache__`，减少仓库噪音
- 已同步更新设计文档与记忆层，正式文档不再把旧脚本目录和旧命令名当作当前事实
- 已新增根 CLI 分发测试与 Go 素材脚手架测试
- 已重新构建交付物，当前有效产物为：
  - `generator/dist/generator/darwin-arm64/sinan-generator`
  - `generator/dist/generator/windows-amd64/sinan-generator.exe`
  - `dist/sinan_captcha-0.1.0-py3-none-any.whl`
  - `dist/sinan_captcha-0.1.0.tar.gz`
- 已重写公开文档，当前对外页面统一采用双 CLI 口径：
  - README
  - `docs/01-getting-started/index.md`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/use-and-test-trained-models.md`
- 已同步更新 `docs/index.md` 中的公开导航标题，使导航和正文保持一致
- 已将 Python 版本目标统一收口到 3.12，并同步更新 `pyproject.toml`、用户文档、内部设计文档和 Windows 环境清单
- 已清理构建产生的 `sinan_captcha.egg-info` 元数据目录，保持工作区净化
- 已把 Python 侧执行口径统一为 `uv`：安装使用 `uv pip`，运行使用 `uv run sinan` / `uv run yolo`

## 2026-04-03 首版真实素材与 firstpass 数据集

- 已完成首版真实 `materials/` 包构建并回填主目录：
  - `materials/manifests/classes.yaml`
  - `materials/manifests/backgrounds.csv`
  - `materials/manifests/icons.csv`
  - `materials/icons/<class>/001.png`
- 当前素材规模为 20 类 canonical icon 和 715 张可用背景图
- 修复生成阶段暴露出的坏背景图问题：
  - `generator/internal/material/validate.go` 从“只数图片文件”升级为“逐张完整解码校验”
  - 新增 `generator/internal/material/validate_test.go`
  - 新增截断 JPEG、坏背景图、坏图标三类回归用例
- 已隔离 5 张损坏背景图到 `materials/quarantine/backgrounds/`，并同步修正 `backgrounds.csv`，避免目录与 manifest 不一致
- 已重新编译 mac 生成器二进制并完成 firstpass 数据链路实跑：
  - `datasets/group1/firstpass/raw/group1_fp_0001`
  - `datasets/group2/firstpass/raw/group2_fp_0001`
  - 两批各生成 200 条样本
- 两批原始样本 QA 均通过：
  - click：`query=200`、`scene=200`、`labels=200`
  - slide：`master=200`、`tile=200`、`labels=200`
- 已完成 YOLO 转换：
  - `datasets/group1/firstpass/yolo`
  - `datasets/group2/firstpass/yolo`
  - 两批均为 `train=160`、`val=20`、`test=20`
- 当前仍未进入正式训练，原因是本机 Python 环境缺少 `torch` 与 `ultralytics`

## 2026-04-03 PyPI/CLI 收口

- 已把 Python 训练与数据工程入口收口为统一总 CLI：`sinan`
- 当前子命令包括：
  - `uv run sinan env check`
  - `uv run sinan materials build`
  - `uv run sinan dataset validate`
  - `uv run sinan dataset build-yolo`
  - `uv run sinan autolabel`
  - `uv run sinan evaluate`
  - `uv run sinan train group1`
  - `uv run sinan train group2`
- 已把 Go 生成器正式入口收口为 `sinan-generator`
- `core/train/base.py` 的训练命令已改为通过 `uv run yolo` 启动，避免 Python 侧再出现绕开 `uv` 的直接执行入口
- `core/train/group1/cli.py` 与 `core/train/group2/cli.py` 现在默认会直接启动训练，并支持：
  - `--dry-run`
  - `--epochs`
  - `--batch`
  - `--imgsz`
  - `--device`
- 已新增 `core/convert/cli.py`、`core/autolabel/cli.py`、`core/evaluate/cli.py`、`core/ops/env.py`
- 已删除原 `scripts/convert/build_yolo_dataset.py`、`scripts/autolabel/run_autolabel.py`、`scripts/evaluate/evaluate_model.py` 等薄包装入口
- 已新增训练 CLI 单测并通过；Python 全量测试通过，共 28 个测试
- 已完成本地分发构建验证，`dist/` 下已产出：
  - `sinan_captcha-0.1.0.tar.gz`
  - `sinan_captcha-0.1.0-py3-none-any.whl`
- 当前仍未实际上传 PyPI；还需要 PyPI 发布凭据和最终包名确认

## 2026-04-03 Windows 训练机文档重构

- 已将 `docs/02-user-guide/from-base-model-to-training-guide.md` 重构为面向 Windows 训练机的完整操作文档
- 新文档主线已覆盖：
  - 从其他机器拷贝 wheel 与 YOLO 数据集
  - 修正 `dataset.yaml` 路径
  - 安装驱动、`uv`、Python 3.12、PyTorch GPU
  - 安装本地 wheel 与训练依赖
  - 执行 `uv run sinan env check`
  - 运行冒烟训练与正式训练
- 已同步更新：
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/04-project-development/05-development-process/windows-environment-checklist.md`
- 当前公开用户路径已不再要求读者先理解内部开发过程文档，就可以在 Windows 训练机上完成安装与训练

## 2026-04-02

- 统一 Go 生成器接口，`generate` 命令新增 `--mode` 与 `--backend`
- 新增 `click/native` 与 `slide/native` 两类原生 backend 路径
- 在 JSONL 与 `manifest.json` 中补齐 `mode`、`backend`、`truth_checks`、滑块字段和 `asset_dirs`
- 新增 `gold` 真值硬门禁代码：一致性校验、重放校验、负样本校验
- Python `core/` 侧同步适配新的 group2 字段：`master_image`、`tile_image`、`target_gap`、`tile_bbox`、`offset_x`、`offset_y`
- 当日曾新增过 `scripts/export/export_group2_batch.py` 作为过渡入口，后续已在 CLI 收口中移除
- 回归验证通过：
  - `GOCACHE=/tmp/sinan-go-build-cache go test ./...`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`

## 2026-04-02 批次 QA 强化

- 生成器 `qa` 已升级为批次逐条审计，不再只统计图片和标签数量
- QA 新增检查：
  - `truth_checks` 三项必须全部 `passed`
  - 样本 `mode/backend/source_batch` 必须与 manifest 一致
  - 资产路径必须落在对应 `asset_dirs` 下
  - 主图、查询图、滑块图尺寸必须与配置或几何真值一致
  - click/slide 样本结构会复用真值一致性与负样本校验逻辑
- 新增 Go 单测覆盖：
  - 合法 click 批次
  - 合法 slide 批次
  - 缺少 `truth_checks` 的坏批次应被拒绝

- 2026-04-02：重构 `docs/02-user-guide/from-base-model-to-training-guide.md`，将手册主线改为“仓库产物 + 训练工作目录 + 当前实现状态”，移除把 `go-captcha-service` 作为默认前置的旧叙述。
- 2026-04-02：同步更新 `docs/02-user-guide/user-guide.md` 和 `/.factory/memory/current-state.md`，明确新手阅读入口与当前仓库事实边界。
- 2026-04-02：重构用户指南信息架构，新增 `docs/02-user-guide/use-build-artifacts.md`，将 `docs/02-user-guide/user-guide.md` 改为公开总览页，并把维护者说明迁移到 `docs/03-developer-guide/maintainer-quickstart.md`。
- 2026-04-02：更新 `docs/index.md` 导航，移除用户指南中的私有页面混入，确保公开路径只围绕“使用编译结果”和“训练环境 + 模型训练”两类目标展开。
- 2026-04-02：继续压缩训练主手册，新增 `docs/02-user-guide/use-and-test-trained-models.md`，把“训练后模型如何使用与测试”从训练页拆出，并同步修正自动标注与 JSONL 评估的公开状态说明。
- 2026-04-02：新增离线素材包构建脚本与示例配置，支持批量下载背景图、提取官方图标、生成 `classes.yaml`，并同步补充到公开使用文档。
- 2026-04-02：将生成器相关需求、设计、过程文档统一收口为“受控集成 + 可插拔 backend”，消除“参考 go-captcha 思路”和“直接使用库能力”的混写。
- 2026-04-02：将第二专项正式收口为“滑块缺口定位”，并同步更新需求、架构、模块边界、执行清单与追踪矩阵。
- 2026-04-02：把“训练素材必须 100% 正确”落地为生成器 `gold` 硬门禁，新增一致性校验、重放校验和负样本校验要求。
