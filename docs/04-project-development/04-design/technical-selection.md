# 技术选型与工程规则

- 项目名称：sinan-captcha
- 当前阶段：IMPLEMENTATION（设计基线维护）
- 最近更新：2026-04-05
- 负责人：Codex

## 1. 设计目标

本阶段的技术选型不再围绕“怎么搭一个训练工程”展开，而是围绕“怎么稳定交付统一验证码求解包/库”展开。设计目标固定为：

1. 最终交付 1 个本地可调用的统一求解 wheel，内嵌模型与 Rust 扩展；外置 bundle 只保留为训练仓库到 solver 项目之间的内部交接资产。
2. 让 Windows + NVIDIA 单机继续承担样本生成、训练、测试、评估和自主训练闭环。
3. 让 `group1` 与 `group2` 保持独立训练与独立验收，但对外统一到单一求解合同。
4. 让生成器继续拥有 `gold` 真值定义权，不让 backend 或训练框架反向定义训练事实。
5. 让自主训练维持“确定性控制器 + 受限 agent”边界，不依赖长上下文记忆。
6. 让设计文档明确区分：
   - 最终目标交付
   - 当前已存在实现
   - 后续仍需补齐的正式发布主线

## 2. 核心技术决策

### 2.1 一级产品与交付形态

- 一级产品：
  - 本地统一验证码求解包/库
  - 平台相关 wheel
  - 单一业务语义和函数调用合同
- 二级支撑能力：
  - Go 生成器 CLI
  - Python 训练 / 测试 / 评估 / 发布 CLI
  - Python 自主训练 CLI
- V1 不先做公网 HTTP 平台。
- V1 优先固化本地 `PyPI wheel + Rust native extension + embedded ONNX assets` 的交付模型。

设计判断：

- 当前仓库最完整的实现仍在模型生产线，但技术选型必须先对齐最终 solver 交付面，否则 release、部署和用户文档会继续漂移。

### 2.2 训练框架

- `group1` 训练框架：
  - Ultralytics YOLO
  - 分别训练 `scene detector` 与 `query parser`
- `group2` 训练框架：
  - 仓库内 PyTorch 自定义 paired-input runner

设计判断：

- `group1` 的真实业务是 `query_image + scene_image -> ordered_clicks`，首版拆成 `scene detector + query parser + matcher` 最稳。
- `group2` 的真实业务是 `master_image + tile_image -> target_center`，继续伪装成单图 detect 只会让合同和实现都失真。

### 2.2.1 推理运行时路线

- 训练侧保留：
  - PyTorch
  - Ultralytics YOLO
- solver 侧迁移为：
  - ONNX
  - ONNX Runtime
  - Rust 原生扩展

设计判断：

- 训练期继续保留现有 PyTorch / Ultralytics 栈，避免过早重写训练主线。
- 最终调用方不应承担 PyTorch 级运行时复杂度，solver 侧应收口到更轻的 ONNX Runtime。
- Rust 原生扩展是 solver 侧的长期运行时边界，不再把 Python 当作最终重计算层。

### 2.3 `group1` 正式技术路线

- 子模型 1：`scene detector`
- 子模型 2：`query parser`
- 非模型组件：`matcher`
- 正式业务输出：按查询顺序排列的中心点序列
- 调试或解释字段：检测框、候选框、匹配状态、歧义状态

设计判断：

- 首版不引入额外相似度匹配模型。
- 只有当类别体系无法稳定维护、重复类别场景无法靠规则消歧时，才重新评估“检测 + 匹配模型”路线。

### 2.4 `group2` 正式技术路线

- 输入：`master_image + tile_image`
- 正式业务输出：背景图坐标系中的目标中心点
- 辅助输出：目标框、偏移量、调试信息
- `tile_start_bbox`：
  - 只服务于偏移量等辅助字段
  - 不应继续成为“能否返回中心点主结果”的强依赖

设计判断：

- 当前实现已支持把 `tile_start_bbox` 作为可选输入。
- 设计基线以中心点为主结果，偏移量退到辅助结果层。

### 2.5 生成器与 backend 策略

- 生成器控制层：Go
- backend 形态：
  - 自有 native backend
  - 可选 `go-captcha` adapter backend
- 生成器职责：
  - 工作区与 preset 管理
  - 素材索引与校验
  - 真值生成与重放
  - 批次 QA
  - 直接导出任务专属训练数据集目录

设计判断：

- backend 只能提供生成能力，不得成为训练标签的主事实源。
- 视觉难度增强第一版只允许 truth-preserving 的像素级扰动，不允许改变几何语义。

### 2.6 自主训练控制器与 agent 运行时

- 控制器：仓库内 Python 控制器
- agent 运行时：`opencode`
- study/trial 主持久化：
  - study 目录
  - JSON / JSONL 工件
- 优化器：
  - `Optuna` 作为可插拔搜索器
  - 未接 driver 或未满足前置条件时回退到规则模式
- 结构化校验：
  - 当前基线为标准库 dataclass + 显式校验
  - `pydantic` 不是当前必须前置

设计判断：

- 本项目当前最稳定的持久化主线是文件账本，而不是数据库。
- 若后续为 `Optuna` 或统计分析引入额外本地存储，只能建立在文件账本已经完整可信的前提上。

### 2.7 统一求解与发布策略

- 统一求解实现语言：
  - Python API 外壳
  - Rust 原生扩展运行时
- 正式运行目标：
  - package/library 直接调用
  - `pip install sinanz`
- 内部交接资产规则：
  - ONNX 模型与 metadata 自描述
  - 不允许直接引用 `runs/` 的绝对路径
- 最终 wheel 目标内容：
  - Python 包
  - Rust native extension
  - embedded ONNX assets
- Windows 训练交付包目标内容：
  - Go 生成器可执行文件
  - 训练仓库 wheel
  - 内部导出资产说明
  - 使用说明

设计判断：

- 当前 `core/solve` 已经存在，说明统一求解主线不应再被视为“未来想法”。
- 当前 `sinanz` 仍处于 Python/PyTorch 迁移过渡期；正式对外交付仍需补齐 ONNX 导出、Rust bridge 和平台 wheel 发布链路。

## 3. 生成与数据策略

### 3.1 是否必须先部署完整验证码服务

- 不必须。
- 首版只需要稳定生成图片和真值的内部生成器。
- 生成器可以来自：
  - 自有业务生成逻辑的导出模式
  - 内部离线脚本
  - 内部 API

### 3.2 标签主事实源

- 主事实源：JSONL
- 派生产物：
  - `group1`：`dataset.json`、`scene-yolo/`、`query-yolo/`、`splits/`
  - `group2`：`dataset.json`、`master/`、`tile/`、`splits/`
- 禁止把任何派生产物当作唯一事实源。

### 3.3 标签状态

- `gold`：生成器内部真值直出且通过校验
- `auto`：自动预标注生成
- `reviewed`：抽检或修正后确认

### 3.4 `gold` 硬门禁

- `gold` 必须来自生成器内部几何真值。
- 同一份真值必须同时驱动渲染和标签导出。
- 每批样本必须支持按 `seed + backend + 素材版本 + 配置版本` 重放。
- 任一一致性校验失败样本直接阻断，不写入正式数据集。

## 4. Python 与 CLI 工程规则

### 4.1 环境管理

- Python 版本目标：3.12
- 统一使用 `uv`
- 统一使用 `pyproject.toml`
- 统一提交 `uv.lock`
- 不把 `requirements.txt` 当主事实源

### 4.2 正式入口边界

- Go 侧正式入口：`sinan-generator`
- Python 侧正式入口：`sinan`
- solver 侧正式能力归属：
  - 当前迁移参考实现在 `core/solve`
  - 正式公开入口应在 `solver/src/sinanz/`
  - 正式运行时扩展应在 `solver/native/sinanz_ext/`
- 不再允许 `scripts/*` 成为正式对外入口。

### 4.3 默认质量门槛

默认验证命令：

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy core tests
uv run python -m unittest discover -s tests/python -p 'test_*.py'
```

Go 验证：

```bash
go test ./...
```

自主训练新增验证重点：

- study 状态恢复
- JSON 决策解析与 fallback
- `group1/group2` 双 study 隔离
- 停止规则与 resume 行为
- `plan-dataset` / `judge-trial` / `result-read` / `study-status` 运行时接入

## 5. 推理资产与部署规则

- 内部导出资产必须可整体复制，不依赖训练目录绝对路径。
- 导出资产校验必须在打包 wheel 前完成。
- 最终用户交付优先是平台相关 wheel，而不是外置 bundle。
- wheel 内必须同时包含：
  - `sinanz` Python API
  - Rust 原生扩展
  - `resources/models/*.onnx`
  - `resources/metadata/*.json`
- 调用方不应直接读取 `runs/`、`datasets/`、`studies/` 或模型文件路径。

## 6. 当前实现对齐状态

### 已存在的稳定实现

- Go 生成器工作区、素材、QA 与数据导出主线
- Python 训练、测试、评估与发布主线
- 自主训练控制器骨架与 `opencode` JUDGE/PLAN/READ/STATUS + `Optuna` RETUNE 运行时接入
- `core/solve` 的合同和统一求解骨架

### 仍待继续补齐的正式主线

- `PT -> ONNX` 推理资产导出
- Rust 扩展与 ONNX Runtime bridge
- 平台相关 wheel 构建与安装冒烟
- 旧 bundle 交付口径向内部交接资产降级

## 7. 首版明确不做的事

- 不先做公网 HTTP 服务、多租户鉴权和在线扩缩容
- 不把 AI agent 放开为不受约束的命令执行者
- 不把 `group1` 与 `group2` 强行合并成一个万能模型
- 不直接抓第三方未授权验证码作为训练数据
- 不在正式文档里把尚未接入发布主线的功能写成“已经交付”

## 8. 参考来源

- PyTorch Get Started: <https://pytorch.org/get-started/locally/>
- Ultralytics Train: <https://docs.ultralytics.com/modes/train/>
- Ultralytics Detect Datasets: <https://docs.ultralytics.com/datasets/detect/>
- ONNX Runtime Docs: <https://onnxruntime.ai/docs/>
- Rust Cargo Book: <https://doc.rust-lang.org/cargo/>
- uv Getting Started: <https://docs.astral.sh/uv/getting-started/features/>
- go-captcha: <https://github.com/wenlng/go-captcha>
- OpenCode Intro: <https://opencode.ai/docs/>
- OpenCode Commands: <https://opencode.ai/docs/commands/>
- OpenCode Skills: <https://opencode.ai/docs/skills/>
- Optuna Installation: <https://optuna.readthedocs.io/en/stable/installation.html>
