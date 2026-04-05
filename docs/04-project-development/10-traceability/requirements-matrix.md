# 需求追踪矩阵

本矩阵按 2026-04-05 最新业务澄清重构，正式把项目一级产品收口为“统一验证码求解包/库”，并把生成器、训练 CLI 和自主训练 CLI 追踪为支撑能力。

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
| REQ-003 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析顺序恢复与歧义风险 |
| REQ-003 | 落点 | docs/04-project-development/04-design/api-design.md | 有效 | 2026-04-05 | Codex | 已补齐 `group1` 统一响应与顺序结果设计 |
| REQ-004 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 最终交付为单一 bundle 和单一入口 |
| REQ-004 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已补齐 bundle、manifest 和交付包要求 |
| REQ-004 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析交付实体的重要性 |
| REQ-004 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-05 | Codex | 已把 bundle 管理与交付模块提升为正式交付面 |
| REQ-004 | 落点 | docs/02-user-guide/use-solver-bundle.md | 有效 | 2026-04-05 | Codex | 已补齐最终 solver 交付目录与统一合同的公开页 |
| REQ-004 | 落点 | docs/04-project-development/07-release-delivery/ | 有效 | 2026-04-05 | Codex | 发布与交付细节文档已收口为训练包与 solver 目标双轨说明 |
| REQ-005 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 项目分解中已保留 Go 生成器 |
| REQ-005 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写生成器为支撑能力 |
| REQ-005 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析 gold 样本和 preset 风险 |
| REQ-005 | 落点 | docs/02-user-guide/index.md | 有效 | 2026-04-05 | Codex | 公开入口已说明当前训练产线使用路径 |
| REQ-005 | 落点 | docs/04-project-development/04-design/graphic-click-generator-design.md | 有效 | 2026-04-05 | Codex | 现有生成器设计仍可作为详细设计事实源 |
| REQ-006 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 项目分解中已保留 Windows 训练 CLI |
| REQ-006 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写训练 CLI 为模型生产工具链 |
| REQ-006 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析训练目录与交付物边界 |
| REQ-006 | 落点 | docs/02-user-guide/user-guide.md | 有效 | 2026-04-05 | Codex | 公开用户入口已改写为“最终产品 + 当前训练主链路”双层口径 |
| REQ-006 | 落点 | docs/04-project-development/04-design/technical-selection.md | 有效 | 2026-04-05 | Codex | 当前技术选型仍然支撑训练主链路 |
| REQ-007 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 项目分解中已保留自主训练 CLI |
| REQ-007 | 来源 | docs/04-project-development/02-discovery/brainstorm-record.md | 有效 | 2026-04-05 | Codex | 已明确 agent 受限与控制器边界 |
| REQ-007 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写自主训练为生产效率能力 |
| REQ-007 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析 fallback 和恢复风险 |
| REQ-007 | 落点 | docs/04-project-development/04-design/autonomous-training-and-opencode-design.md | 有效 | 2026-04-05 | Codex | 现有详细设计仍可沿用，后续只需补 solver-first 上下文 |
| REQ-008 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 已明确需要完整生产线治理 |
| REQ-008 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写数据治理、验收和回灌 |
| REQ-008 | 落点 | docs/04-project-development/03-requirements/requirements-analysis.md | 有效 | 2026-04-05 | Codex | 已分析测试集冻结和回灌边界 |
| REQ-008 | 落点 | docs/04-project-development/04-design/module-boundaries.md | 有效 | 2026-04-05 | Codex | 已重写数据治理、评估与回灌模块边界 |
| REQ-009 | 来源 | docs/04-project-development/02-discovery/input.md | 有效 | 2026-04-05 | Codex | 已明确文档覆盖训练机、素材、生成器和自主训练 |
| REQ-009 | 落点 | docs/04-project-development/03-requirements/prd.md | 有效 | 2026-04-05 | Codex | 已重写部署与操作文档要求 |
| REQ-009 | 落点 | docs/02-user-guide/index.md | 有效 | 2026-04-05 | Codex | 用户入口已修正项目定位 |
| REQ-009 | 落点 | docs/02-user-guide/use-solver-bundle.md | 有效 | 2026-04-05 | Codex | 已补齐最终调用方视角的 solver 使用与部署说明 |
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
| REQ-010 | 落点 | docs/02-user-guide/use-solver-bundle.md | 有效 | 2026-04-05 | Codex | 已把最终 solver package/library + bundle 作为公开交付目标固定下来 |
| REQ-010 | 落点 | docs/03-developer-guide/solver-bundle-and-integration.md | 有效 | 2026-04-05 | Codex | 已补齐 solver bundle 集成缺口与后续修复优先级 |

## 更新记录

- 2026-04-01：创建早期需求追踪矩阵，主线仍偏向训练工程。
- 2026-04-04：补入自主训练与统一求解服务的追踪关系。
- 2026-04-05：按最新业务澄清重构追踪矩阵，正式把求解包/库提升为一级产品，维护人：Codex。
