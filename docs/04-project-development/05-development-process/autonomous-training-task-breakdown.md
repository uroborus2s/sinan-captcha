# 自主训练任务拆解

- 文档状态：草稿
- 当前阶段：DESIGN
- 目标读者：项目维护者、训练链路实现者、agent/skill 实现者
- 负责人：Codex
- 上游输入：
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/04-design/system-architecture.md`
  - `docs/04-project-development/04-design/module-boundaries.md`
- 下游交付：
  - `core/auto_train/` 实现顺序
  - `.opencode/commands/` 与 `.opencode/skills/` 实现顺序
  - 自主训练集成测试顺序
- 关联需求：`REQ-007`、`REQ-011`、`REQ-012`、`REQ-013`、`NFR-006`、`NFR-009`

## 1. 使用方式

这份文档是进入自主训练实现前的执行表，不是泛泛的路线建议。

执行原则：

1. 严格按 `TASK-AT-001` 到 `TASK-AT-015` 顺序推进。
2. 每个任务都要产出可检查物，不接受“先写点代码再说”。
3. 前一任务未通过验收，后一任务不得启动。
4. 如果发现需要修改 study 契约、goal 合同、agent JSON 契约、watchdog 或 group 指标，必须回到对应任务重开。

## 2. 总执行表

| 任务 ID | 任务名称 | 主执行角色 | 主要输入 | 主要输出 | 阶段关口 | 预计工时 |
|---|---|---|---|---|---|---|
| TASK-AT-001 | 冻结 study 契约 | 架构负责人 | 自主训练设计方案 | `study.json` / `trial.json` 字段表 | 契约冻结 | 0.5 天 |
| TASK-AT-002 | 冻结状态机与停止规则 | 架构负责人 | study 契约、需求文档 | 状态机图、停止规则表 | 状态机冻结 | 0.5 天 |
| TASK-AT-003 | 设计目录与恢复模型 | 训练链路负责人 | 契约、状态机 | study 目录蓝图、恢复规则 | 恢复边界冻结 | 0.5 天 |
| TASK-AT-004 | 设计 runner 适配层 | Python 实现者 | 现有 CLI、目录蓝图 | dataset/train/test/evaluate runner 契约 | 执行边界冻结 | 0.5 天 |
| TASK-AT-005 | 设计结果摘要层 | 评估实现者 | test/evaluate 产物 | `result_summary.json` 字段表 | 摘要冻结 | 0.5 天 |
| TASK-AT-006 | 设计 OpenCode commands | agent 集成者 | 摘要字段、状态机 | command 清单、命令输入输出 | command 冻结 | 0.5 天 |
| TASK-AT-007 | 设计 skills 与 JSON 决策契约 | agent 集成者 | command 清单、需求文档 | skills 清单、`decision.json` 契约 | skill/JSON 冻结 | 1 天 |
| TASK-AT-008 | 设计 group1/group2 策略 | 算法负责人 | 指标需求、评估设计 | 两组目标函数、停止与晋级规则 | 策略冻结 | 1 天 |
| TASK-AT-009 | 设计 Optuna 接入与 fallback | 优化负责人 | 策略规则、JSON 契约 | 搜索空间、pruning、fallback 规则 | 优化边界冻结 | 0.5 天 |
| TASK-AT-010 | 设计 GoalContract 与 StudyContract 编译层 | 架构负责人 | 业务目标、需求文档 | 目标编译合同、编译错误合同 | 目标合同冻结 | 0.5 天 |
| TASK-AT-011 | 设计 typed tool adapters 与 ObservationPacket | Python 实现者 | 现有 CLI、状态机、目标合同 | tool adapter 契约、观测包契约 | tool/observation 冻结 | 1 天 |
| TASK-AT-012 | 设计 Judge/Verifier/Reducer 多角色 verdict 链 | agent 集成者 | command/skill 契约、观测包 | 多角色 verdict 契约、冲突处理规则 | verdict 链冻结 | 1 天 |
| TASK-AT-013 | 设计 watchdog、dead-letter 与 replay 机制 | 架构负责人 | 状态机、verdict 链、NFR | watchdog 策略、死信规则、回放规则 | 无人值守守护冻结 | 0.5 天 |
| TASK-AT-014 | 设计 promotion gate 与 solver smoke gate | 发布负责人 | 评估设计、solver 资产导出合同 | gate 规则、promotion report 契约 | 晋级门冻结 | 0.5 天 |
| TASK-AT-015 | 实施前总验收 | 项目维护者 | 001-014 全部产物 | 准入结论、风险清单 | 允许进入实现 | 0.5 天 |

## 2.1 2026-04-09 商业试卷与 reviewed exam gate 增补任务

这一轮实现额外冻结以下执行顺序，避免“试卷整理”和“商业门改造”继续混在一起：

1. `TASK-AT-EXAM-001`：整理 `materials/group1` 与 `materials/result` 到 `materials/business_exams/<task>/reviewed-v1/import`
2. `TASK-AT-EXAM-002`：在 `X-AnyLabeling-GPU` 中完成 `group1/group2` 原生模型预标注
3. `TASK-AT-EXAM-003`：人工复核并导出 `reviewed/labels.jsonl`
4. `TASK-AT-EXAM-004`：冻结 reviewed 试卷池版本，不回灌训练集
5. `TASK-AT-EXAM-005`：把 `auto-train` 商业测试改成“从 reviewed 试卷池随机抽 50 题”
6. `TASK-AT-EXAM-006`：删除旧 `group2 overlay` 商业 gate，统一为 reviewed exam 门禁

本轮验收标准：

- `group1` 和 `group2` 都支持 `--business-eval-dir <reviewed_exam_dir>`
- 商业测试只接受 `labels.jsonl` 作为事实源
- 每轮稳定随机抽 `50` 题
- 只有抽样成功率达到门槛才允许 `commercial_gate_passed`

## 3. 执行角色定义

| 角色 | 责任 |
|---|---|
| 项目维护者 | 维护顺序、准入结论和文档一致性 |
| 架构负责人 | 维护 study 契约、状态机和边界 |
| 训练链路负责人 | 维护 runner、目录与恢复语义 |
| Python 实现者 | 后续把控制器与 runners 转成 Python 代码 |
| 评估实现者 | 维护摘要层、排行榜和 trial 证据字段 |
| agent 集成者 | 维护 `opencode` commands、skills 和 JSON 契约 |
| 算法负责人 | 维护 group1/group2 指标、停止规则与晋级标准 |
| 优化负责人 | 维护 `Optuna` 搜索空间、pruning 和 fallback |
| 发布负责人 | 维护 solver smoke gate、promotion gate 与晋级报告 |

## 4. TASK-AT-001 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 冻结 study 与 trial 状态文件，避免实现阶段边写边改 JSON 结构 |
| 主执行角色 | 架构负责人 |
| 协作角色 | 训练链路负责人、agent 集成者 |
| 前置条件 | 无 |
| 主要输入 | `autonomous-training-and-opencode-design.md` |
| 操作步骤 | 1. 固定 `study.json`、`best_trial.json`、`trial_history.jsonl`、`decisions.jsonl` 字段。<br>2. 固定 trial 目录中的 `input.json`、`dataset.json`、`train.json`、`test.json`、`evaluate.json`、`decision.json`。<br>3. 固定 `current_trial_id`、`best_trial_id`、`status` 和时间戳字段。 |
| 输出产物 | study/trial 字段表、示例 JSON |
| 验收标准 | 任何实现者仅看文档即可写出对应数据类与文件读写器 |
| 阻断条件 | 关键字段仍存在“实现时再定” |
| 失败处理 | 回到设计文档重定字段，不进入状态机设计 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-002 |

## 5. TASK-AT-002 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 冻结自主训练状态机与停止规则，避免控制器逻辑漂移 |
| 主执行角色 | 架构负责人 |
| 协作角色 | 项目维护者、算法负责人 |
| 前置条件 | TASK-AT-001 已通过 |
| 主要输入 | study 契约、`REQ-007`、`NFR-006` |
| 操作步骤 | 1. 固定 `PLAN/BUILD_DATASET/TRAIN/TEST/EVALUATE/SUMMARIZE/JUDGE/NEXT_ACTION/STOP` 状态。<br>2. 固定最大 trial、最大小时数、平台期、STOP 文件、致命失败等停止条件。<br>3. 固定恢复时从哪个状态继续。 |
| 输出产物 | 状态机图、停止规则表、恢复入口表 |
| 验收标准 | 项目维护者可以明确判断任一 study 当前停在哪个状态、为什么停 |
| 阻断条件 | 恢复点和停止条件定义不清 |
| 失败处理 | 回补状态迁移和停止条件，不进入目录设计 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-003 |

## 6. TASK-AT-003 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定 study 目录结构、排行榜和恢复语义 |
| 主执行角色 | 训练链路负责人 |
| 协作角色 | 架构负责人、评估实现者 |
| 前置条件 | TASK-AT-002 已通过 |
| 主要输入 | study 契约、状态机 |
| 操作步骤 | 1. 固定 `studies/group1/...` 与 `studies/group2/...` 目录结构。<br>2. 固定 `leaderboard.json` 和 `summary.md` 的存放位置。<br>3. 固定恢复时以哪些文件判定“已完成/需重跑”。 |
| 输出产物 | 目录蓝图、恢复规则说明 |
| 验收标准 | 任何成员只看目录蓝图即可判断文件职责与恢复入口 |
| 阻断条件 | group1/group2 目录仍可能互相覆盖 |
| 失败处理 | 回补目录与命名规则，不进入 runner 设计 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-004 |

## 7. TASK-AT-004 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定控制器与现有 CLI 的执行边界 |
| 主执行角色 | Python 实现者 |
| 协作角色 | 训练链路负责人 |
| 前置条件 | TASK-AT-003 已通过 |
| 主要输入 | 现有 `sinan-generator`、`sinan` CLI 行为 |
| 操作步骤 | 1. 固定 dataset/train/test/evaluate runner 的输入输出。<br>2. 明确 runner 只负责执行命令与采集结果，不负责 AI 判断。<br>3. 固定错误返回与重试边界。 |
| 输出产物 | runner 契约说明、错误处理表 |
| 验收标准 | 控制器实现者无需进入具体业务命令内部，也能完成编排 |
| 阻断条件 | runner 与控制器责任不清，或 runner 直接做业务判断 |
| 失败处理 | 回补边界文档，不进入摘要设计 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-005 |

## 8. TASK-AT-005 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定结果压缩层，避免 AI 直接读取长日志 |
| 主执行角色 | 评估实现者 |
| 协作角色 | agent 集成者、算法负责人 |
| 前置条件 | TASK-AT-004 已通过 |
| 主要输入 | `test.json`、`evaluate.json`、历史 trial 示例 |
| 操作步骤 | 1. 固定 `result_summary.json` 的字段范围。<br>2. 只保留判断所需的关键指标、弱类、失败模式、趋势。<br>3. 固定“最近 N 轮 + 最佳轮”摘要策略。 |
| 输出产物 | `result_summary.json` 字段表、摘要压缩规则 |
| 验收标准 | Judge 不看长日志也能完成下一步判断 |
| 阻断条件 | 摘要仍依赖终端长输出或整批图片 |
| 失败处理 | 回补摘要字段，不进入 command 设计 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-006 |

## 9. TASK-AT-006 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定 OpenCode commands 的数量、输入和输出 |
| 主执行角色 | agent 集成者 |
| 协作角色 | 架构负责人、评估实现者 |
| 前置条件 | TASK-AT-005 已通过 |
| 主要输入 | 摘要字段、OpenCode 接入设计 |
| 操作步骤 | 1. 固定 `result-read`、`judge-trial`、`plan-dataset`、`study-status` 四个 command。<br>2. 固定每个 command 的 message/file 输入约定。<br>3. 固定 headless 调用方式和输出 JSON 期望。 |
| 输出产物 | command 清单、front matter 约定、输入输出表 |
| 验收标准 | 控制器实现者可以稳定调用 OpenCode，而不是依赖临时 prompt |
| 阻断条件 | command 名、输入或输出语义不稳定 |
| 失败处理 | 回补 command 契约，不进入 skill 设计 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-007 |

## 10. TASK-AT-007 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定 skills 分工与决策 JSON 契约 |
| 主执行角色 | agent 集成者 |
| 协作角色 | 算法负责人、项目维护者 |
| 前置条件 | TASK-AT-006 已通过 |
| 主要输入 | command 清单、`REQ-012` |
| 操作步骤 | 1. 固定 `result-reader`、`training-judge`、`dataset-planner`、`study-archivist` 四个 skill。<br>2. 固定 `decision.json` 只能输出允许动作集。<br>3. 固定非法 JSON 的 fallback 行为。 |
| 输出产物 | skills 清单、JSON schema、fallback 规则 |
| 验收标准 | AI 决策可校验、可审计、可回退 |
| 阻断条件 | skill 职责混杂，或 JSON 动作集不封闭 |
| 失败处理 | 回补职责边界与 schema，不进入组策略设计 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-AT-008 |

## 11. TASK-AT-008 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定 group1/group2 的目标函数、停止规则和晋级标准 |
| 主执行角色 | 算法负责人 |
| 协作角色 | 评估实现者、项目维护者 |
| 前置条件 | TASK-AT-007 已通过 |
| 主要输入 | 指标需求、历史人工分析结论 |
| 操作步骤 | 1. 固定 group1 的主指标、副指标和弱类惩罚。<br>2. 固定 group2 的主指标、副指标和定位误差惩罚。<br>3. 固定两组各自的 plateau、promote、abandon 条件。 |
| 输出产物 | 两组策略表、停止与晋级规则 |
| 验收标准 | 同一组数据反复判断时，group1/group2 不会互相污染标准 |
| 阻断条件 | 仍试图用同一个总分评价两组模型 |
| 失败处理 | 回补策略表，不进入 Optuna 设计 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-AT-009 |

## 12. TASK-AT-009 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定 `Optuna` 接入和规则 fallback 边界 |
| 主执行角色 | 优化负责人 |
| 协作角色 | 算法负责人、Python 实现者 |
| 前置条件 | TASK-AT-008 已通过 |
| 主要输入 | 两组策略表、JSON 决策契约 |
| 操作步骤 | 1. 固定允许搜索的参数空间。<br>2. 固定 `Optuna` 只在 `RETUNE` 情况下介入。<br>3. 固定 pruning 与 no-improve 的交互规则。<br>4. 固定 AI 失败时的纯规则 fallback。 |
| 输出产物 | 搜索空间表、pruning 规则、fallback 规则 |
| 验收标准 | `Optuna` 不会越权决定业务动作，AI 失败也不会卡死 study |
| 阻断条件 | 搜索空间无限扩张，或 fallback 不存在 |
| 失败处理 | 回补优化边界，不进入总验收 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-010 |

## 13. TASK-AT-010 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 冻结一句业务目标到执行合同的编译层，避免无人值守训练依赖人工拼装 study 配置 |
| 主执行角色 | 架构负责人 |
| 协作角色 | 项目维护者、agent 集成者 |
| 前置条件 | TASK-AT-009 已通过 |
| 主要输入 | 需求文档、harness 设计、现有 study 契约 |
| 操作步骤 | 1. 固定 `GoalContract`、`StudyContract` 和编译错误对象字段。<br>2. 固定一句话目标到合同的必填映射。<br>3. 固定预算、允许动作和 gate 如何被编译到合同中。 |
| 输出产物 | 目标编译合同、错误合同、示例目标 |
| 验收标准 | 维护者只写业务目标也能得到可执行合同，而不是继续手工拼 study JSON |
| 阻断条件 | 目标文本和执行合同之间仍需要大量人工脑补 |
| 失败处理 | 回补目标字段与编译规则，不进入 tool adapter 设计 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-011 |

## 14. TASK-AT-011 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定 typed tool adapters 与 `ObservationPacket` / `TrialEvidencePack` 契约 |
| 主执行角色 | Python 实现者 |
| 协作角色 | 训练链路负责人、评估实现者 |
| 前置条件 | TASK-AT-010 已通过 |
| 主要输入 | 现有 CLI、状态机、目标合同 |
| 操作步骤 | 1. 把 `sinan-generator`、`train/test/evaluate/release` 收口成 stage tool adapters。<br>2. 固定每个 adapter 的输入、输出、错误和重试边界。<br>3. 固定供 agent 使用的 `ObservationPacket` 与 `TrialEvidencePack` 字段。 |
| 输出产物 | adapter 契约、观测包契约、错误处理表 |
| 验收标准 | agent 不看原始 shell 也能完成判断；控制器不向 agent 暴露裸 CLI |
| 阻断条件 | 模型仍需要依赖长日志或原始命令行文本才能判断 |
| 失败处理 | 回补 tool adapter 和观测包边界，不进入多角色 verdict 设计 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-AT-012 |

## 15. TASK-AT-012 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定 `Judge` / `Verifier` / `Reducer` 多角色 verdict 链 |
| 主执行角色 | agent 集成者 |
| 协作角色 | 架构负责人、项目维护者 |
| 前置条件 | TASK-AT-011 已通过 |
| 主要输入 | command/skill 契约、观测包契约 |
| 操作步骤 | 1. 固定 `JudgeVerdict`、`VerifierVerdict`、`DecisionEnvelope` schema。<br>2. 固定冲突 verdict 的 reducer 和 fallback 规则。<br>3. 固定 accepted output 必带的 `input_hash`、`reason_codes` 与 `evidence_refs`。 |
| 输出产物 | verdict schemas、冲突处理表、reducer 规则 |
| 验收标准 | 多 agent 只放大判断质量，不放大执行权限 |
| 阻断条件 | 角色职责仍混杂，或 verdict schema 不能封闭动作集 |
| 失败处理 | 回补 schema 与 reducer，不进入 watchdog 设计 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-AT-013 |

## 16. TASK-AT-013 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定真正无人值守所需的 watchdog、dead-letter 和 replay 机制 |
| 主执行角色 | 架构负责人 |
| 协作角色 | Python 实现者、项目维护者 |
| 前置条件 | TASK-AT-012 已通过 |
| 主要输入 | 状态机、verdict 链、NFR |
| 操作步骤 | 1. 固定阶段心跳、超时、schema 拒收率和 verdict 冲突率阈值。<br>2. 固定死信记录、暂停和停止规则。<br>3. 固定 replay / simulation 的最小输入集。 |
| 输出产物 | watchdog 策略、dead-letter 规则、replay 规则 |
| 验收标准 | 长流程卡死或反复失败时，系统能自行降级、暂停或停止 |
| 阻断条件 | 无人值守演练仍依赖人工看日志判断“是不是卡住了” |
| 失败处理 | 回补看门狗与死信规则，不进入晋级门设计 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-014 |

## 17. TASK-AT-014 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定 `PROMOTE_CANDIDATE` 的正式业务门和 solver smoke gate |
| 主执行角色 | 发布负责人 |
| 协作角色 | 算法负责人、评估实现者 |
| 前置条件 | TASK-AT-013 已通过 |
| 主要输入 | 评估设计、solver 资产导出合同 |
| 操作步骤 | 1. 固定候选晋级所需的主指标、副指标和稳定性条件。<br>2. 固定资产导出验证与 solver smoke gate。<br>3. 固定 `promotion_report` 与 `gate_report` 字段。 |
| 输出产物 | 晋级门规则、solver smoke gate 契约、晋级报告契约 |
| 验收标准 | 候选模型不能只靠训练分数晋级，必须过 solver gate |
| 阻断条件 | 晋级仍只看单一训练分数，或不验证交付面 |
| 失败处理 | 回补 gate 规则，不进入总验收 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-AT-015 |

## 18. TASK-AT-015 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 在进入编码前做总验收，确保自主训练实现不再依赖临时口头约定 |
| 主执行角色 | 项目维护者 |
| 协作角色 | 所有前序角色 |
| 前置条件 | TASK-AT-001 到 TASK-AT-014 全部通过 |
| 主要输入 | 全部设计与任务产物 |
| 操作步骤 | 1. 逐项检查 001-014 是否有明确产物。<br>2. 检查 study 契约、goal 合同、command/skill 契约、verdict 链、watchdog、group 策略和 gate 是否冻结。<br>3. 形成准入结论：允许进入实现或打回补文档。 |
| 输出产物 | 实施准入结论、剩余风险清单、补项清单 |
| 验收标准 | 实现者不再需要追问“目标怎么编译”“模型到底能主动做到哪里”“无人值守如何判定”“候选模型怎么才能晋级” |
| 阻断条件 | 任一关键前提仍未冻结 |
| 失败处理 | 指回具体任务重做，不允许越过总验收直接编码 |
| 预计工时 | 0.5 天 |
| 完成后进入 | 实现阶段 |

## 19. 每日推进建议

| 日期顺序 | 建议推进内容 | 结束标志 |
|---|---|---|
| 第 1 天上午 | TASK-AT-001 到 TASK-AT-003 | study 契约、状态机、目录恢复规则冻结 |
| 第 1 天下午 | TASK-AT-004 到 TASK-AT-006 | runner 与 OpenCode command 边界冻结 |
| 第 2 天上午 | TASK-AT-007 到 TASK-AT-008 | skills、JSON 契约与两组策略冻结 |
| 第 2 天下午 | TASK-AT-009 到 TASK-AT-011 | 优化边界、目标合同与观测包冻结 |
| 第 3 天上午 | TASK-AT-012 到 TASK-AT-014 | verdict 链、watchdog、晋级门冻结 |
| 第 3 天下午 | TASK-AT-015 | 形成实施准入结论 |

## 20. 不允许跳过的关口

下面 7 个关口不能跳：

1. study 契约冻结
2. 状态机与停止规则冻结
3. OpenCode command/skill 契约冻结
4. group1/group2 策略冻结
5. GoalContract / tool adapter / verdict 链冻结
6. watchdog 与 solver gate 冻结
7. 实施准入验收

## 21. 完成标志

当下面 4 条同时满足时，才算“自主训练任务拆解已经可执行”：

1. 15 个任务都有主执行角色。
2. 15 个任务都有明确输入、输出、验收和阻断条件。
3. 项目维护者可以据此安排执行顺序和检查完成情况。
4. 实现者可以不再追问“下一步先做什么”。
