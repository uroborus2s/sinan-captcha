# 需求追踪矩阵

本矩阵按 2026-04-12 最新需求增量更新：项目一级产品仍是“统一验证码求解包/库”，`group1` 正式路线已切到实例匹配求解，且已新增 solver 多输入、背景素材扩充，以及 `prelabel-vlm` 逐样本恢复要求。

## 追踪关系

| 源项 | 关系 | 目标项 | 状态 | 更新时间 | 负责人 | 备注 |
|---|---|---|---|---|---|---|
| REQ-001 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 最终产物为统一求解包/库 |
| REQ-001 | 来源 | docs/04-project-development/02-discovery/brainstorm-record.md | 有效 | 2026-04-05 | Codex | 已明确采用 solver-first 单仓方案 |
| REQ-001 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写统一入口与统一合同要求 |
| REQ-001 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析项目主次纠偏意义 |
| REQ-001 | 落点 | README.md | 有效 | 2026-04-05 | Codex | 公开入口改为先说明最终求解包目标 |
| REQ-001 | 落点 | docs/04-project-development/04-design/system-architecture.md | 有效 | 2026-04-05 | Codex | 已按 solver-first 重写架构主线 |
| REQ-002 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 已明确 `group2` 输出中心点 |
| REQ-002 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写 `group2` 业务语义 |
| REQ-002 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析中心点语义和风险 |
| REQ-002 | 落点 | docs/04-project-development/04-design/api-design.md | 有效 | 2026-04-05 | Codex | 已把 `group2` 中心点设为主结果，并把偏移字段降为辅助结果 |
| REQ-003 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 已明确 `group1` 输出有序中心点序列 |
| REQ-003 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写 `group1` 业务语义 |
| REQ-003 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-11 | Codex | 已分析 query 切分、候选召回、向量混淆与分配风险 |
| REQ-003 | 落点 | docs/04-project-development/04-design/group1-instance-matching-refactor.md | 有效 | 2026-04-13 | Codex | 已冻结 `query detector + scene proposal detector + icon embedder + matcher` 工程化主线 |
| REQ-003 | 落点 | docs/04-project-development/04-design/api-design.md | 有效 | 2026-04-05 | Codex | 已补齐 `group1` 统一响应与顺序结果设计 |
| REQ-003 | 落点 | docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md | 有效 | 2026-04-11 | Codex | 已新增 `group1` 实例匹配重构任务拆解 |
| REQ-004 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 最终交付为单一 bundle 和单一入口 |
| REQ-004 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已补齐 bundle、manifest 和交付包要求 |
| REQ-004 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析交付实体的重要性 |
| REQ-004 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-05 | Codex | 已把 bundle 管理与交付模块提升为正式交付面 |
| REQ-004 | 落点 | docs/02-user-guide/solver-package-usage-guide.md | 有效 | 2026-04-11 | Codex | 已收口为仅保留最新 solver 使用入口的公开页 |
| REQ-004 | 落点 | docs/04-project-development/07-release-delivery/ | 有效 | 2026-04-05 | Codex | 发布与交付细节文档已收口为训练包与 solver 目标双轨说明 |
| REQ-005 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 项目分解中已保留 Go 生成器 |
| REQ-005 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-11 | Codex | 已把 `group1` 素材主键切到 `asset_id/template_id/variant_id` |
| REQ-005 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-11 | Codex | 已分析素材主键稳定性与实例数据契约风险 |
| REQ-005 | 落点 | docs/02-user-guide/index.md | 有效 | 2026-04-05 | Codex | 公开入口已说明当前训练产线使用路径 |
| REQ-005 | 落点 | docs/04-project-development/04-design/graphic-click-generator-design.md | 有效 | 2026-04-05 | Codex | 现有生成器设计保留控制层原则 |
| REQ-005 | 落点 | docs/04-project-development/04-design/group1-instance-matching-refactor.md | 有效 | 2026-04-11 | Codex | 已定义 `proposal-yolo/embedding/eval` 导出结构 |
| REQ-006 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 项目分解中已保留 Windows 训练 CLI |
| REQ-006 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-11 | Codex | 已把 `group1` 训练主线切到 proposal + embedder + matcher 校准 |
| REQ-006 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-11 | Codex | 已分析整链路训练与评估口径变更 |
| REQ-006 | 落点 | docs/02-user-guide/complete-training-operations-guide.md | 有效 | 2026-04-11 | Codex | 已收口为单一训练主链路入口并移除历史流程页 |
| REQ-006 | 落点 | docs/04-project-development/04-design/technical-selection.md | 有效 | 2026-04-11 | Codex | 已把 `group1` 训练框架改为 proposal + embedder 路线 |
| REQ-006 | 落点 | docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md | 有效 | 2026-04-11 | Codex | 已拆出 proposal/embedder/matcher 分阶段任务 |
| REQ-007 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 项目分解中已保留自主训练 CLI |
| REQ-007 | 来源 | docs/04-project-development/02-discovery/brainstorm-record.md | 有效 | 2026-04-05 | Codex | 已明确 agent 受限与控制器边界 |
| REQ-007 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写自主训练为生产效率能力 |
| REQ-007 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析 fallback 和恢复风险 |
| REQ-007 | 落点 | docs/04-project-development/04-design/autonomous-training-and-opencode-design.md | 有效 | 2026-04-05 | Codex | 现有详细设计仍可沿用，后续只需补 solver-first 上下文 |
| REQ-007 | 落点 | docs/04-project-development/04-design/group1-instance-matching-refactor.md | 有效 | 2026-04-11 | Codex | 已定义 `group1` 新自动学习阶段与失败归因 |
| REQ-008 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 已明确需要完整生产线治理 |
| REQ-008 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-11 | Codex | 已把 `group1` 商业试卷和失败归因切到新口径 |
| REQ-008 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-11 | Codex | 已分析 `group1` 新评估与回灌边界 |
| REQ-008 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-11 | Codex | 已重写 `group1` 数据转换与训练模块职责 |
| REQ-008 | 落点 | docs/04-project-development/04-design/group1-instance-matching-refactor.md | 有效 | 2026-04-11 | Codex | 已定义 reviewed、预标注和 business gate 新合同 |
| REQ-009 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 已明确文档覆盖训练机、素材、生成器和自主训练 |
| REQ-009 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写部署与操作文档要求 |
| REQ-009 | 落点 | docs/02-user-guide/index.md | 有效 | 2026-04-05 | Codex | 用户入口已修正项目定位 |
| REQ-009 | 落点 | docs/02-user-guide/solver-package-usage-guide.md | 有效 | 2026-04-11 | Codex | 已补齐最终调用方视角的 solver 使用与部署说明 |
| REQ-009 | 落点 | docs/03-developer-guide/index.md | 有效 | 2026-04-05 | Codex | 维护者入口已说明 solver-first 主次关系 |
| REQ-009 | 落点 | docs/03-developer-guide/solver-bundle-and-integration.md | 有效 | 2026-04-05 | Codex | 已补齐维护者视角的 solver 集成边界说明 |
| REQ-009 | 落点 | docs/04-project-development/08-operations-maintenance/deployment-guide.md | 有效 | 2026-04-05 | Codex | 已补齐训练机与目标 solver 使用机器的部署边界 |
| REQ-009 | 落点 | docs/04-project-development/08-operations-maintenance/operations-runbook.md | 有效 | 2026-04-05 | Codex | 已补齐运行维护主线与当前实现差距 |
| REQ-010 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 最终交付要求包含打包为方便调用的库 |
| REQ-010 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写版本化发布与交付管理要求 |
| REQ-010 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析版本映射和回滚必要性 |
| REQ-010 | 落点 | docs/04-project-development/07-release-delivery/release-notes.md | 有效 | 2026-04-05 | Codex | 已定义当前稳定发布层与目标 solver 交付层 |
| REQ-010 | 落点 | docs/04-project-development/07-release-delivery/delivery-package.md | 有效 | 2026-04-05 | Codex | 已明确训练交付包与目标 solver 交付包边界 |
| REQ-010 | 落点 | docs/04-project-development/07-release-delivery/release-checklist.md | 有效 | 2026-04-05 | Codex | 已补齐发布门槛与当前 bundle 差距检查 |
| REQ-010 | 落点 | docs/02-user-guide/solver-package-usage-guide.md | 有效 | 2026-04-11 | Codex | 已把最终 solver package/library + bundle 作为公开交付目标固定下来 |
| REQ-010 | 落点 | docs/03-developer-guide/solver-bundle-and-integration.md | 有效 | 2026-04-05 | Codex | 已补齐 solver bundle 集成缺口与后续修复优先级 |
| REQ-011 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 已明确自主训练需以业务目标驱动 |
| REQ-011 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已定义一句业务目标到合同的编译要求 |
| REQ-011 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析目标编译的价值与风险 |
| REQ-011 | 落点 | docs/04-project-development/04-design/autonomous-training-and-opencode-design.md | 有效 | 2026-04-05 | Codex | 已定义 GoalContract / StudyContract 设计边界 |
| REQ-012 | 来源 | docs/04-project-development/02-discovery/brainstorm-record.md | 有效 | 2026-04-05 | Codex | 已明确 agent 只能在受限 harness 中输出 verdict |
| REQ-012 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已定义严格 schema I/O 和多 agent 分工 |
| REQ-012 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析多 agent 冲突与 reducer 风险 |
| REQ-012 | 落点 | docs/04-project-development/04-design/autonomous-training-and-opencode-design.md | 有效 | 2026-04-05 | Codex | 已定义 Judge / Verifier / Reducer 角色边界 |
| REQ-013 | 来源 | docs/04-project-development/02-discovery/brainstorm-record.md | 有效 | 2026-04-05 | Codex | 已明确自动验收和晋级门属于正式主线 |
| REQ-013 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已定义 watchdog、自动验收和 promotion gate |
| REQ-013 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-11 | Codex | 已补充 `group1` 不能继续沿旧闭集指标晋级的风险说明 |
| REQ-013 | 落点 | docs/04-project-development/04-design/group1-instance-matching-refactor.md | 有效 | 2026-04-11 | Codex | 已定义 `group1` 新离线门与商业成功门 |
| REQ-014 | 来源 | docs/04-project-development/02-discovery/brainstorm-record.md | 有效 | 2026-04-11 | Codex | 已明确新方案 cutover 后必须删除旧正式主线 |
| REQ-014 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-11 | Codex | 已新增旧方案清理需求 |
| REQ-014 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-11 | Codex | 已分析双轨污染风险 |
| REQ-014 | 落点 | docs/04-project-development/04-design/group1-instance-matching-refactor.md | 有效 | 2026-04-11 | Codex | 已定义 cutover 与删除清单原则 |
| REQ-014 | 落点 | docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md | 有效 | 2026-04-11 | Codex | 已新增 `TASK-G1-REF-012` 旧方案清理任务 |
| REQ-015 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-11 | Codex | 已新增 solver 多输入与全格式兼容业务约束 |
| REQ-015 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-11 | Codex | 已定义 Path/bytes/base64/URL 统一输入合同与验收标准 |
| REQ-015 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-11 | Codex | 已分析输入适配、URL 安全与一致性风险 |
| REQ-015 | 落点 | docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md | 有效 | 2026-04-11 | Codex | 已新增 `TASK-SOLVER-MIG-013/014/015` 实施任务 |
| REQ-015 | 落点 | docs/02-user-guide/solver-package-usage-guide.md | 有效 | 2026-04-11 | Codex | 已同步当前限制与目标输入口径说明 |
| REQ-015 | 落点 | docs/02-user-guide/solver-package-function-reference.md | 有效 | 2026-04-11 | Codex | 已同步输入类型定义与实施状态说明 |
| REQ-016 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-12 | Codex | 已明确需要扩充背景素材且样本来源必须来自授权环境 |
| REQ-016 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-12 | Codex | 已定义背景素材扩充、质量门与正式 backgrounds 合并要求 |
| REQ-016 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-12 | Codex | 已分析原图直送 VLM 策略、质量门和合并风险 |
| REQ-016 | 落点 | docs/04-project-development/04-design/background-material-expansion-design.md | 有效 | 2026-04-12 | Codex | 已冻结不依赖自动修补的正式设计策略 |
| REQ-016 | 落点 | docs/04-project-development/05-development-process/background-material-expansion-task-breakdown.md | 有效 | 2026-04-12 | Codex | 已拆出 `TASK-MAT-BG-001` 到 `TASK-MAT-BG-006` |
| REQ-017 | 来源 | .factory/workitems/changes/CR-001-group1-vlm-prelabel-resume-and-process-artifacts.md | 有效 | 2026-04-12 | Codex | 用户已确认 `prelabel-vlm` 需要逐样本恢复与过程目录 |
| REQ-017 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-12 | Codex | 已定义 `prelabel-vlm` 过程工件、断点续传和聚合重建要求 |
| REQ-017 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-12 | Codex | 已分析整批重跑、弱恢复语义和审计成本风险 |
| REQ-017 | 落点 | docs/04-project-development/04-design/group1-instance-matching-refactor.md | 有效 | 2026-04-12 | Codex | 已冻结 `process/` 目录、逐样本状态和恢复规则 |
| REQ-017 | 落点 | docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md | 有效 | 2026-04-12 | Codex | 已新增 `TASK-G1-REF-013` 承接实现 |

## 更新记录

- 2026-04-01：创建早期需求追踪矩阵，主线仍偏向训练工程。
- 2026-04-04：补入自主训练与统一求解服务的追踪关系。
- 2026-04-05：按最新业务澄清重构追踪矩阵，正式把求解包/库提升为一级产品，维护人：Codex。
- 2026-04-11：按 `group1` 实例匹配重构决策更新追踪关系，并补入 `REQ-011` 到 `REQ-014`，维护人：Codex。
- 2026-04-11：新增 `REQ-015`（多输入与全格式兼容）追踪关系，并补入 solver 输入适配任务，维护人：Codex。
- 2026-04-12：新增 `REQ-016`（背景素材扩充、质量门与正式 backgrounds 合并）追踪关系，维护人：Codex。
- 2026-04-12：新增 `CR-001` 与 `REQ-017`（`group1 prelabel-vlm` 逐样本恢复与过程工件目录）追踪关系，维护人：Codex。
