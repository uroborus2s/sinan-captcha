# 部署说明

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：项目维护者、训练机管理员、交付支持人员
- 最近更新：2026-04-05

## 1. 本页解决什么问题

这页说明当前项目应如何部署到两类机器：

- 训练机
- 目标 solver 使用机器

同时明确哪些部署路径已经稳定，哪些仍处于目标态。

## 2. 训练机部署

### 当前稳定目标

训练机需要能够：

- 初始化训练目录
- 运行训练、测试、评估
- 按需运行生成器
- 按需运行自主训练

### 训练机最小组件

- `uv`
- Python 3.12
- GPU 版 PyTorch
- `sinan-captcha` wheel 或 PyPI 包
- 训练数据集

如果训练机还要本地生成样本，再加上：

- `sinan-generator.exe`
- 生成器工作区
- `materials/` 或素材包

### 当前稳定部署路径

1. 训练目录初始化：
   - `uvx --from sinan-captcha sinan env setup-train --train-root <train-root>`
2. 训练目录内运行：
   - `uv run sinan train ...`
   - `uv run sinan test ...`
   - `uv run sinan evaluate ...`
   - `uv run sinan auto-train ...`
3. 如需本地生成数据：
   - `sinan-generator workspace init`
   - `sinan-generator materials import|fetch`
   - `sinan-generator make-dataset`

## 3. 训练机目录模型

### 生成器安装目录

- 保存 `sinan-generator.exe`

### 生成器工作区

- 保存 `workspace.json`
- 保存 `presets/`
- 保存 `materials/`
- 保存 `jobs/`
- 保存 `logs/`

### 训练目录

- 保存 `pyproject.toml`
- 保存 `.venv/`
- 保存 `datasets/`
- 保存 `runs/`
- 保存 `reports/`
- 保存 `studies/`

## 4. 目标 solver 部署

### 目标正式目标

目标 solver 使用机器只需要：

- Python 运行时或等价 package 运行环境
- solver package/library
- solver bundle
- 调用说明

它不应需要：

- 训练目录
- 生成器工作区
- `materials/`
- `datasets/`
- `studies/`

### 当前状态

截至 2026-04-05：

- solver bundle 目录设计和代码骨架已存在
- 统一求解合同已存在
- 正式发布链路仍未完全接通

因此当前部署结论是：

- 训练机部署：已稳定
- solver 独立部署：目标已固定，正式交付流程仍待补齐

## 5. 部署时的关键边界

- 训练机部署和 solver 部署不能混成一个目录模型
- bundle 不得依赖 `runs/` 的绝对路径
- 调用方机器不应直接消费训练资产
- 若交付目录包含 bundle，应以 `bundle/manifest.json` 作为 solver 模型事实源

## 6. 当前主要部署风险

- Windows 驱动、CUDA 和 PyTorch 兼容性
- 训练机完全离线时的依赖获取问题
- PyPI 包与 solver bundle 版本配对错误
- solver 运行环境缺少 `torch` / `ultralytics` / `Pillow`

## 7. 本页完成标志

当维护者读完这页后，应能明确：

1. 训练机需要部署什么
2. solver 目标机器最终需要部署什么
3. 当前哪些部署路径已经稳定，哪些还只是正式目标态
