# 需求追踪矩阵

把当前需求阶段的 REQ 与输入、分析和后续设计落点关联起来，保证后续设计和实现不会偏离“零基础可执行的两专项模型训练方案”。

## 追踪关系

| 源项 | 关系 | 目标项 | 状态 | 更新时间 | 负责人 | 备注 |
|---|---|---|---|---|---|---|
| REQ-001 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-01 | Codex | 环境搭建是首要问题 |
| REQ-001 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-01 | Codex | Windows 训练环境要求 |
| REQ-001 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-01 | Codex | 给出 Windows 训练环境实际操作步骤 |
| REQ-001 | 落点 | docs/04-project-development/05-development-process/windows-environment-checklist.md | 有效 | 2026-04-01 | Codex | 给出逐项可勾选环境清单 |
| REQ-001 | 落点 | docs/04-project-development/04-design/technical-selection.md | 有效 | 2026-04-01 | Codex | 已定义预训练权重、Python/uv 与环境规则 |
| REQ-001 | 落点 | docs/04-project-development/04-design/system-architecture.md | 有效 | 2026-04-01 | Codex | 已定义离线训练系统架构 |
| REQ-001 | 落点 | docs/02-user-guide/how-to-check-cuda-version.md | 有效 | 2026-04-01 | Codex | 已补充 Windows 上 CUDA 版本的识别方法 |
| REQ-001 | 落点 | docs/04-project-development/04-design/module-structure-and-delivery.md | 有效 | 2026-04-02 | Codex | 已明确本地训练机上的模块语言、构建和部署形态 |
| REQ-002 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-01 | Codex | 样本获取与合规导出 |
| REQ-002 | 来源 | graphical_captcha_training_guide.md | 有效 | 2026-04-01 | Codex | 明确从生成端导出坐标 |
| REQ-002 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-01 | Codex | 样本导出契约 |
| REQ-002 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-01 | Codex | 给出样本导出与字段落地方法 |
| REQ-002 | 落点 | docs/04-project-development/05-development-process/data-export-auto-labeling-checklist.md | 有效 | 2026-04-01 | Codex | 给出样本导出和切分清单 |
| REQ-002 | 落点 | docs/04-project-development/04-design/technical-selection.md | 有效 | 2026-04-01 | Codex | 已定义内部生成器优先和开源底座选择 |
| REQ-002 | 落点 | docs/04-project-development/04-design/api-design.md | 有效 | 2026-04-01 | Codex | 已定义数据导出入口合同 |
| REQ-002 | 落点 | docs/04-project-development/04-design/graphic-click-generator-design.md | 有效 | 2026-04-02 | Codex | 已收口为受控集成的多模式生成器，并定义双模式导出和真值门禁 |
| REQ-003 | 来源 | docs/04-project-development/02-discovery/brainstorm-record.md | 有效 | 2026-04-01 | Codex | 自动标注优先是核心决策 |
| REQ-003 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-01 | Codex | 预标注 + 抽检流程 |
| REQ-003 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-01 | Codex | 给出自动标注优先级与具体执行法 |
| REQ-003 | 落点 | docs/04-project-development/05-development-process/data-export-auto-labeling-checklist.md | 有效 | 2026-04-01 | Codex | 给出自动标注、抽检和状态流转清单 |
| REQ-003 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-01 | Codex | 已定义自动标注流水线模块 |
| REQ-003 | 落点 | docs/04-project-development/04-design/api-design.md | 有效 | 2026-04-01 | Codex | 已定义自动标注入口合同 |
| REQ-004 | 来源 | docs/04-project-development/02-discovery/current-state-analysis.md | 有效 | 2026-04-01 | Codex | 当前缺少数据治理 |
| REQ-004 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-01 | Codex | 数据目录、schema、版本 |
| REQ-004 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-01 | Codex | 给出数据集目录和版本规则 |
| REQ-004 | 落点 | docs/04-project-development/05-development-process/data-export-auto-labeling-checklist.md | 有效 | 2026-04-01 | Codex | 给出目录、切分和转换检查项 |
| REQ-004 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-01 | Codex | 已定义数据契约与版本管理模块 |
| REQ-004 | 落点 | docs/04-project-development/04-design/graphic-click-generator-design.md | 有效 | 2026-04-02 | Codex | 已定义多模式生成器目录、配置、JSONL 主事实源和校验门禁 |
| REQ-004 | 落点 | docs/04-project-development/04-design/module-structure-and-delivery.md | 有效 | 2026-04-02 | Codex | 已明确仓库目录、代码模块和运行资产目录划分 |
| REQ-005 | 来源 | graphical_captcha_training_guide.md | 有效 | 2026-04-01 | Codex | 第一专项为多类别检测 |
| REQ-005 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-01 | Codex | 第一专项模型要求 |
| REQ-005 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-01 | Codex | 给出第一专项训练顺序和命令模板 |
| REQ-005 | 落点 | docs/04-project-development/04-design/technical-selection.md | 有效 | 2026-04-01 | Codex | 已定义预训练微调和首版权重选择 |
| REQ-005 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-01 | Codex | 已定义第一专项训练模块 |
| REQ-005 | 落点 | docs/04-project-development/04-design/api-design.md | 有效 | 2026-04-01 | Codex | 已定义第一专项训练入口 |
| REQ-005 | 落点 | docs/04-project-development/04-design/graphic-click-generator-design.md | 有效 | 2026-04-02 | Codex | 已固定第一专项图形点选样本的生成规则和标签契约 |
| REQ-006 | 来源 | graphical_captcha_training_guide.md | 有效 | 2026-04-02 | Codex | 第二专项现收口为滑块缺口定位 |
| REQ-006 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-02 | Codex | 第二专项滑块定位模型要求 |
| REQ-006 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-02 | Codex | 给出第二专项滑块预标注和训练顺序 |
| REQ-006 | 落点 | docs/04-project-development/04-design/technical-selection.md | 有效 | 2026-04-02 | Codex | 已定义规则法角色和滑块定位主线 |
| REQ-006 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-02 | Codex | 已定义第二专项滑块定位训练模块 |
| REQ-006 | 落点 | docs/04-project-development/04-design/api-design.md | 有效 | 2026-04-02 | Codex | 已定义第二专项训练入口 |
| REQ-007 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-01 | Codex | 用户明确要求小白可执行步骤 |
| REQ-007 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-01 | Codex | 零基础操作手册要求 |
| REQ-007 | 落点 | docs/02-user-guide/from-base-model-to-training-guide.md | 有效 | 2026-04-01 | Codex | 已形成从基础模型到训练闭环的逐步实操手册 |
| REQ-007 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-01 | Codex | 已形成单独的小白执行文档 |
| REQ-007 | 落点 | docs/04-project-development/05-development-process/windows-environment-checklist.md | 有效 | 2026-04-01 | Codex | 小白环境搭建清单 |
| REQ-007 | 落点 | docs/04-project-development/05-development-process/data-export-auto-labeling-checklist.md | 有效 | 2026-04-01 | Codex | 小白样本与标注执行清单 |
| REQ-007 | 落点 | docs/04-project-development/04-design/graphic-click-generator-design.md | 有效 | 2026-04-02 | Codex | 已形成多模式生成器的完整设计方案，便于后续按步骤实现 |
| REQ-007 | 落点 | docs/04-project-development/05-development-process/generator-task-breakdown.md | 有效 | 2026-04-02 | Codex | 已把编号任务表收口到多模式生成器与 gold 门禁 |
| REQ-007 | 落点 | docs/04-project-development/04-design/module-structure-and-delivery.md | 有效 | 2026-04-02 | Codex | 已形成模块、目录、语言和交付形态的一体化说明 |
| REQ-008 | 来源 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-01 | Codex | 训练工程化与回灌 |
| REQ-008 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-01 | Codex | 验收与版本化要求 |
| REQ-008 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-01 | Codex | 给出验收、归档和回灌动作 |
| REQ-008 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-01 | Codex | 已定义评估与报告模块 |
| REQ-008 | 落点 | docs/04-project-development/04-design/system-architecture.md | 有效 | 2026-04-01 | Codex | 已定义失败样本回灌链路 |
| REQ-008 | 落点 | docs/04-project-development/04-design/module-structure-and-delivery.md | 有效 | 2026-04-02 | Codex | 已明确模块交付物与部署边界，便于后续维护和归档 |
| REQ-009 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-04 | Codex | 用户追加“V1 先接入 opencode”的自主训练要求 |
| REQ-009 | 来源 | docs/04-project-development/02-discovery/brainstorm-record.md | 有效 | 2026-04-04 | Codex | 已收口为“Python 控制器 + opencode + skills + study 账本” |
| REQ-009 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-04 | Codex | 已定义自主训练控制器与 opencode 接入需求 |
| REQ-009 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-04 | Codex | 已分析 study、skill、group 隔离和 fallback 风险 |
| REQ-009 | 落点 | docs/04-project-development/04-design/technical-selection.md | 有效 | 2026-04-04 | Codex | 已定义 opencode、Optuna 和状态存储技术选型 |
| REQ-009 | 落点 | docs/04-project-development/04-design/system-architecture.md | 有效 | 2026-04-04 | Codex | 已补充自主训练控制平面 |
| REQ-009 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-04 | Codex | 已补充控制器、agent 接入层和优化策略模块 |
| REQ-009 | 落点 | docs/04-project-development/04-design/autonomous-training-and-opencode-design.md | 有效 | 2026-04-04 | Codex | 已形成自主训练与 OpenCode 接入详细设计 |
| REQ-009 | 落点 | docs/04-project-development/05-development-process/implementation-plan.md | 有效 | 2026-04-04 | Codex | 已补充第二阶段自主训练实施主线 |
| REQ-009 | 落点 | docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md | 有效 | 2026-04-04 | Codex | 已形成自主训练任务拆解与顺序 |

## 更新记录

- 2026-04-01：重建需求阶段追踪矩阵，维护人：Codex。
- 2026-04-01：补充“零基础落地实施方案”作为 REQ-001 至 REQ-008 的执行落点，维护人：Codex。
- 2026-04-01：补充两个配套 checklist，维护人：Codex。
- 2026-04-01：补充第一专项图形点选样本生成器完整方案，维护人：Codex。
- 2026-04-01：补充 CUDA 版本识别说明和图形点选生成器任务拆解，维护人：Codex。
- 2026-04-02：补充模块结构与构建交付设计，维护人：Codex。
- 2026-04-02：将生成器设计统一收口为“受控集成 + 可插拔 backend”，并把第二专项改为滑块缺口定位，维护人：Codex。
- 2026-04-04：新增 `REQ-009`，把“自主训练控制器 + OpenCode 先行接入”落到需求、设计和任务拆解文档，维护人：Codex。
