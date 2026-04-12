# 技术画像摘要

- 当前画像：图形验证码专项模型设计画像
- 预设：custom
- 技术栈：Python, PyTorch, Ultralytics YOLO（训练侧）, ONNX, ONNX Runtime, Rust, Windows, CUDA, X-AnyLabeling/CVAT
- 最近更新时间：2026-04-05 19:10:00

## 摘要

项目当前已完成需求阶段，设计阶段已固定如下结论：

- 一级产品目标是统一验证码求解包/库，而不是训练工程本身
- 最终交付由 `sinanz` 平台 wheel、内嵌 ONNX 资产和 Rust 原生扩展组成
- `group2` 当前已切到 `.onnx + native_bridge` 契约，训练仓库已支持导出 `slider_gap_locator.onnx`
- 第一专项使用预训练 YOLO 检测权重微调
- 第一专项采用 `query splitter + proposal detector + icon embedder + matcher`
- 第二专项做双输入滑块缺口定位，并以中心点作为正式主结果
- 生成端优先直接导出真值并执行硬门禁校验
- 生成器采用“受控集成 + 可插拔 backend”
- `go-captcha` 作为可选 backend adapter，而不是训练事实源
- 训练目录通过 `uvx --from sinan-captcha sinan env setup-train` 初始化为独立 uv 项目
- 生成器通过固定工作区管理预设、素材缓存和任务记录，并直接导出任务专属训练数据集目录
- 面向用户的目录模型已固定为“生成器安装目录 + 生成器工作区 + 训练目录”
- 自主训练以 Python 控制器 + OpenCode commands/skills + JSON/JSONL 工件为主
- 本地发布目标当前分两层：
  - 训练仓库的 Windows 交付包与导出资产交接
  - 独立 solver 项目的平台 wheel 发布

## 项目范围

- 统一验证码求解包/库
- 图形验证码两专项模型训练
- 内部生成器 / 样本导出
- 自动标注与抽检
- 训练评估与失败样本回灌
- 自主训练与 solver 资产导出

## 必装/必选模块

- `uv`
- `pyproject.toml`
- `uv.lock`
- `Ultralytics YOLO`（group1）
- `PyTorch` GPU 版
- `X-AnyLabeling` 或 `CVAT`
- `sinan-generator`

## 关键工程规则

- 统一使用 `uv` 管理 Python 版本、虚拟环境和依赖。
- Python 侧公开命令统一通过 `uvx --from sinan-captcha sinan`、`uv run sinan` 执行；`uv run yolo` 只作为 `group1` 底层运行时。
- Python 运行目标统一为 3.12，避免仓库配置、文档和训练机环境分叉。
- 训练 CLI 与生成器通过任务专属数据集目录交接：
  - `group1` 入口是 `dataset.json`
  - `group2` 入口是 `dataset.json`
- 生成器工作区与训练目录分离，`materials/` 只属于生成器工作区。
- 公开示例统一显式传入 `sinan-generator --workspace <generator-workspace>`，避免默认 `%LOCALAPPDATA%` 工作区造成读者误判。
- 使用 JSONL 作为标签主事实源；`group1` 的 `proposal-yolo/embedding/eval` 与 `group2` 的 paired split 清单都只是派生产物。
- 两专项模型独立训练和独立验收，不合并成单一万能模型。
- 任何实现都要遵守已固定的数据契约和模块边界。
- 任何 `gold` 样本都必须来自生成器内部真值，且通过一致性校验与重放校验。

## 强制技能

- `python-uv-project`

## 推荐初始化动作

- 补齐 `pyproject.toml`
- 建立 `generator/`、`core/`、`tests/` 结构
- 固定数据目录和标签 schema

## 参考资料

- `docs/04-project-development/04-design/technical-selection.md`
- `docs/04-project-development/04-design/module-boundaries.md`
- `docs/04-project-development/04-design/system-architecture.md`
- `docs/04-project-development/04-design/api-design.md`
