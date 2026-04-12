# 发布说明

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：项目维护者、发布负责人、交付负责人
- 负责人：Codex
- 最近更新：2026-04-05

## 1. 本页解决什么问题

这页说明当前项目的正式发布模型是什么，以及“当前已经稳定可发的内容”和“设计上已经确认、但代码仍待接通的交付内容”分别是什么。

## 2. 当前发布模型

当前项目的发布模型分成两层：

### 2.1 当前稳定可发层

- Python wheel / sdist
- Go 生成器二进制
- 面向训练机的 Windows 交付包

这一层已经有正式命令和稳定使用路径：

- `uv run sinan release build`
- `uv run sinan release publish`
- `uv run sinan release package-windows`

### 2.2 目标正式交付层

- solver package/library
- solver bundle
- 面向调用方的统一交付包

这一层已经完成需求和设计收口，也已经有 `core/solve` 代码骨架，但还没有完全接入根 CLI 和现有 `package-windows` 发布主线。

## 3. 当前稳定发布物

### 3.1 Python 包

- `dist/*.whl`
- `dist/*.tar.gz`

用途：

- 训练机初始化
- 训练 / 测试 / 评估
- 自主训练
- 维护者发布流程

### 3.2 Go 生成器二进制

典型产物：

- `generator/dist/generator/windows-amd64/sinan-generator.exe`
- `generator/dist/generator/darwin-arm64/sinan-generator`

用途：

- 工作区初始化
- 素材导入 / 获取
- 受控样本生成
- 训练数据集导出

### 3.3 Windows 训练交付包

典型目录：

- `dist/windows-bundle-<version>/`

当前稳定内容：

- `python/`
- `generator/`
- 可选 `datasets/`
- 可选 `materials/`
- `README-交付包说明.txt`

## 4. 目标 solver 交付物

目标 solver 交付应包含：

- solver package/library
- solver bundle
- bundle manifest
- 版本映射与交付说明

目标 bundle 至少包含：

- `manifest.json`
- `models/group1/scene-detector/...`
- `models/group1/icon-embedder/...`
- `models/group1/matcher/...`
- `models/group2/locator/...`

## 5. 当前实现状态

截至 2026-04-05，发布层已经接通 solver 第一阶段主线：

1. 根 `sinan` CLI 已正式注册 `solve`
2. `release package-windows` 已支持把 solver bundle 纳入交付包
3. 面向最终调用方的 bundle 安装与调用页已形成独立公开页面

这些事实意味着：

- 当前可以稳定发训练机交付包
- 当前也可以稳定发“Python wheel + solver bundle”的交付目录
- 当前不应把 solver 模型宣传成“已经完全内嵌进单个 PyPI wheel”

## 6. 当前发布策略

### 6.1 训练发布

当前可以正式执行：

1. 构建 Python 包
2. 构建 Go 生成器二进制
3. 组装训练机 Windows 交付包
4. 更新训练相关公开文档

### 6.2 solver 发布

当前应视为“设计已冻结、代码骨架已存在、发布链路未完全接通”的状态。

在代码未收口前：

- 不应把 solver bundle 当作标准外发产物
- 不应在公开安装文档里假设 `package-windows` 已经包含 bundle

## 7. 版本说明原则

- Python 包版本、训练数据版本、训练运行名和 bundle 版本必须可追溯
- 比较新旧版本时，必须同时引用：
  - 数据集版本
  - 模型运行名
  - 评估报告
  - 交付包版本
- 回滚必须指向完整交付版本，而不是零散模型文件

## 8. 本页完成标志

当维护者读完这页后，应能明确：

1. 当前哪些东西已经可以正式发布
2. solver bundle 当前属于什么状态
3. 发布文档和公开交付文档应该如何避免夸大发布能力
