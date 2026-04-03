# 技术画像摘要

- 当前画像：图形验证码专项模型设计画像
- 预设：custom
- 技术栈：Python, Ultralytics YOLO, Windows, CUDA, X-AnyLabeling/CVAT
- 最近更新时间：2026-04-03 22:30:00

## 摘要

项目当前已完成需求阶段，设计阶段已固定如下结论：

- 使用预训练 YOLO 检测权重微调
- 第一专项做多类别检测
- 第二专项做滑块缺口定位
- 生成端优先直接导出真值并执行硬门禁校验
- 生成器采用“受控集成 + 可插拔 backend”
- `go-captcha` 作为可选 backend adapter，而不是训练事实源
- 训练目录通过 `uvx --from sinan-captcha sinan env setup-train` 初始化为独立 uv 项目
- 生成器通过固定工作区管理预设、素材缓存和任务记录，并直接导出 YOLO 数据集目录
- 面向用户的目录模型已固定为“生成器安装目录 + 生成器工作区 + 训练目录”
- 本地发布通过 `uv run sinan release build/publish/package-windows` 收口

## 项目范围

- 图形验证码两专项模型训练
- 内部生成器 / 样本导出
- 自动标注与抽检
- 训练评估与失败样本回灌

## 必装/必选模块

- `uv`
- `pyproject.toml`
- `uv.lock`
- `Ultralytics YOLO`
- `PyTorch` GPU 版
- `X-AnyLabeling` 或 `CVAT`
- `sinan-generator`

## 关键工程规则

- 统一使用 `uv` 管理 Python 版本、虚拟环境和依赖。
- Python 侧公开命令统一通过 `uvx --from sinan-captcha sinan`、`uv run sinan`、`uv run yolo` 执行。
- Python 运行目标统一为 3.12，避免仓库配置、文档和训练机环境分叉。
- 训练 CLI 与生成器只通过 YOLO 数据集目录交接，正式入口是 `dataset.yaml`。
- 生成器工作区与训练目录分离，`materials/` 只属于生成器工作区。
- 公开示例统一显式传入 `sinan-generator --workspace <generator-workspace>`，避免默认 `%LOCALAPPDATA%` 工作区造成读者误判。
- 使用 JSONL 作为标签主事实源，YOLO 标签作为派生产物。
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
