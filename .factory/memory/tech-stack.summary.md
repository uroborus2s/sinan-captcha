# 技术画像摘要

- 当前画像：图形验证码专项模型设计画像
- 预设：custom
- 技术栈：Python, Ultralytics YOLO, Windows, CUDA, X-AnyLabeling/CVAT
- 最近更新时间：2026-04-01 17:30:00

## 摘要

项目当前已完成需求阶段，设计阶段已固定如下结论：

- 使用预训练 YOLO 检测权重微调
- 第一专项做多类别检测
- 第二专项做单类别检测
- 生成端优先直接导出真值
- 首选 `go-captcha` 作为开源内部生成底座

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

## 关键工程规则

- 统一使用 `uv` 管理 Python 版本、虚拟环境和依赖。
- 使用 JSONL 作为标签主事实源，YOLO 标签作为派生产物。
- 两专项模型独立训练和独立验收，不合并成单一万能模型。
- 任何实现都要遵守已固定的数据契约和模块边界。

## 强制技能

- `python-uv-project`

## 推荐初始化动作

- 补齐 `pyproject.toml`
- 建立 `src/`、`tests/`、`scripts/` 结构
- 固定数据目录和标签 schema

## 参考资料

- `docs/04-project-development/04-design/technical-selection.md`
- `docs/04-project-development/04-design/module-boundaries.md`
- `docs/04-project-development/04-design/system-architecture.md`
- `docs/04-project-development/04-design/api-design.md`
