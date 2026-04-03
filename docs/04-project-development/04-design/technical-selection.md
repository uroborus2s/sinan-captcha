# 技术选型与工程规则

- 项目名称：sinan-captcha
- 当前阶段：DESIGN
- 最近更新：2026-04-02
- 负责人：Codex

## 1. 设计目标

本阶段要固定的是“第一版如何稳妥落地”，不是追求最复杂的模型组合。设计目标有五个：

1. 让零基础用户在 Windows + NVIDIA 单机上可复现地跑通训练闭环。
2. 把两类验证码任务清晰拆开，不混成一个大杂烩模型。
3. 让样本获取和自动标注尽量依赖生成端真值，而不是大量人工标注。
4. 把生成器收口成“受控集成 + 可插拔 backend”，不让第三方库反向定义训练契约。
5. 让后续实现仍可在 Python 工程规范内维护，而不是变成一次性训练脚本。

## 2. 核心技术决策

### 2.1 训练框架

- 首选训练框架：Ultralytics YOLO
- 任务类型：目标检测
- 决策原因：
  - 官方文档明确面向自定义检测数据集和预训练权重微调场景。
  - CLI 和 Python 两种入口都成熟，适合零基础用户先从命令行跑通。
  - Windows + 单 GPU 的资料和社区经验更丰富。

### 2.2 基础模型策略

- 首版统一采用“预训练检测模型微调”，不从零训练。
- 第一专项基础权重：`yolo26n.pt`
- 第二专项基础权重：`yolo26n.pt`
- 资源允许且精度不足时，第二选择：`yolo26s.pt`
- 不采用“验证码专用底模”作为首版依赖。

设计判断：

- 当前没有一个公开、成熟、明显优于通用检测预训练权重的“图形验证码专项基础模型”被确认为首选。
- 对这个项目，标签质量和样本分布远比“寻找特殊基础模型”更重要。

### 2.3 第一专项模型路线

- 任务定义：多类别检测
- 输出：目标框 + 中心点 + 查询顺序映射后的点击点列表
- 首版不引入相似度匹配模型
- 只有当图标类别无法稳定维护时，才在后续变更中评估“检测 + 匹配”路线

### 2.4 第二专项模型路线

- 任务定义：滑块缺口定位
- 输出：缺口目标框 + 中心点 + 横向偏移量
- 规则法在首版中的角色：
  - 预标注
  - 可行性验证
  - 与模型结果对照
- 规则法不是正式交付物的唯一主线，正式模型仍为滑块缺口定位模型

## 3. 生成与数据策略

### 3.1 是否必须先部署完整验证码服务

- 不必须。
- 首版只需要一个“能稳定生成图片和标签的内部生成器”。
- 这个生成器可以是：
  - 现有业务验证码服务中的导出模式
  - 内部离线脚本
  - 内部 API

设计结论：

- 对训练来说，最关键的是“图片 + 真值标签”能直接输出。
- 不要求先部署面向真实业务流量的完整对外验证码平台。

### 3.2 生成端优先级

优先级固定如下：

1. 现有自有验证码生成逻辑上加导出功能
2. 内部自建离线生成器，并由控制层统一维护 JSONL 契约、真值校验和批次导出
3. 采用开源验证码生成项目作为内部 backend 候选，并通过适配层接入

设计结论：

- 生成器必须由自有控制层统一维护模式选择、批次元数据、真值校验和导出契约。
- backend 只负责提供验证码生成能力，不得直接定义训练标签主事实源。

### 3.3 开源生成底座选择

#### 首选：`go-captcha`

- 推荐仓库：<https://github.com/wenlng/go-captcha>
- 适用原因：
  - 同时支持 Click、Slide、Drag-Drop、Rotate 四类行为验证码
  - Click 模式支持 text 和 graphic 两种模式
  - Slide 模式可直接拿到主图、滑块图和验证数据
  - 可自定义背景、图形资源和图块资源
  - 还有单独的 `go-captcha-service` 供内部部署

设计判断：

- 这是目前最适合“滑块 + 图形点选”训练样本生成的开源 backend 候选。
- 它适合作为内部生成器的可插拔底座，而不是直接充当训练数据主事实源。

#### 备选：`tianai-captcha`

- 推荐仓库：<https://github.com/dromara/tianai-captcha>
- 适用原因：
  - Java / Spring Boot 集成友好
  - 明确支持滑块、旋转、滑动还原、文字点选
- 不足：
  - 对你当前最关心的“图形点选”支持表达没有 `go-captcha` 那么直接

设计判断：

- 如果团队强依赖 Java / Spring Boot，可作为备选。
- 如果主要目标是快速生成训练样本，不优先于 `go-captcha`。

## 4. Python 工程规则

本项目后续实现统一遵循 `python-uv-project` 规范。

### 4.1 环境管理

- Python 版本目标：3.12
- 统一使用 `uv`
- 统一使用 `pyproject.toml`
- 统一提交 `uv.lock`
- 不以 `requirements.txt` 作为主事实源

### 4.2 目录约定

默认实现目录：

```text
sinan-captcha/
  pyproject.toml
  uv.lock
  generator/
  core/
  tests/
  datasets/
  reports/
```

说明：

- `generator/` 放 Go 生成器工程和正式生成器 CLI
- `core/` 放 Python 训练与数据工程核心包
- `tests/` 放测试
- `datasets/` 是数据资产目录，不混入核心 Python 包

### 4.3 质量门槛

后续进入实现阶段前，默认要准备：

- `ruff`
- `mypy`

后续默认命令：

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy core tests
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

## 5. 数据与标注标准

### 5.1 标签主事实源

- 主事实源：JSONL
- 派生产物：YOLO 格式文本标签
- 禁止把 YOLO 文本标签作为唯一事实源

### 5.2 标签状态

- `gold`：生成器内部真值直出，且已通过一致性校验与重放校验
- `auto`：自动预标注生成
- `reviewed`：抽检或纠正后确认

### 5.3 `gold` 硬门禁

- `gold` 标签必须来自生成器内部几何真值，不允许渲染后反推
- 同一份真值必须同时驱动渲染和答案导出
- 每批样本必须支持按 `seed + backend + 素材版本 + 配置版本` 重放
- 任一一致性校验失败样本直接阻断，不写入 `raw`

### 5.4 测试集规则

- 测试集必须冻结
- 未抽检的 `auto` 标签禁止进入测试集
- 第一组测试集必须覆盖：
  - 多目标
  - 干扰项
  - 重复类别
- 第二组测试集必须覆盖：
  - 高亮目标
  - 弱对比目标
  - 复杂背景

## 6. 首版明确不做的事

- 不从零训练检测模型
- 不引入多模型检索系统作为第一专项首版主线
- 不要求先上线完整验证码平台
- 不直接抓第三方未授权验证码作为训练数据
- 不做分布式训练或多机训练

## 7. 后续需要触发变更评估的条件

- 第一组类别表无法稳定维护
- 第二组目标不再是单缺口滑块
- 生成端无法提供足够真值，且预标注质量长期低于门槛
- 单机显存无法支撑首版训练节奏
- 需要把内部生成器升级为真实对外服务

## 8. 参考来源

- PyTorch Get Started: <https://pytorch.org/get-started/locally/>
- Ultralytics Train: <https://docs.ultralytics.com/modes/train/>
- Ultralytics Detect Datasets: <https://docs.ultralytics.com/datasets/detect/>
- uv Getting Started: <https://docs.astral.sh/uv/getting-started/features/>
- go-captcha: <https://github.com/wenlng/go-captcha>
- tianai-captcha: <https://github.com/dromara/tianai-captcha>
