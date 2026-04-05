# 自主训练实施准入结论

- 文档状态：有效
- 当前阶段：IMPLEMENTATION
- 目标读者：项目维护者、Python 实现者、agent 集成者、优化负责人
- 负责人：Codex
- 上游输入：
  - `docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/03-requirements/prd.md`
- 下游交付：
  - 自主训练控制器整合实现
  - `auto-train` CLI 入口实现
  - `opencode`/`Optuna` 运行时集成
- 关联需求：`REQ-009`、`NFR-006`

## 1. 准入结论

结论：**允许进入自主训练控制器的整合实现阶段**。

本结论的含义是：

- `TASK-AT-001` 到 `TASK-AT-009` 的前置边界已经冻结，不再依赖口头约定。
- 后续实现者可以开始编排 `study` 控制循环、`auto-train` CLI、真实 `opencode` 调用和 `Optuna` driver。
- 仍未完成的内容属于“下一阶段实现范围”，不是本轮准入阻断项。

本结论**不等于**：

- 自主训练功能已经端到端可用。
- 已经完成真实训练机上的长时间稳定性验证。
- 已经通过 Windows + NVIDIA + `opencode` + `Optuna` 的全链路集成验收。

### 1.1 实施进展回写（2026-04-05）

准入结论通过后，仓库已经继续落地了第一版控制器骨架：

- 新增 `core/auto_train/controller.py`
- 新增 `core/auto_train/cli.py`
- 根 CLI 已新增 `uv run sinan auto-train ...` 入口
- 当前已支持 `run` 与 `stage` 两种执行形态
- 当前阶段胶囊已经能串起 `PLAN -> BUILD_DATASET -> TRAIN -> TEST -> EVALUATE -> SUMMARIZE -> JUDGE -> NEXT_ACTION`

这次实现的边界是：

- 已经有正式控制循环骨架和 study/trial 工件接力
- `SUMMARIZE` 已支持真实 `opencode run --command result-read ...` 调用
- `JUDGE` 已支持真实 `opencode run --command judge-trial ...` 调用
- `REGENERATE_DATA` 分流已支持真实 `opencode run --command plan-dataset ...` 调用
- `dataset_plan.json` 当前已不再只是账本工件：
  - 下一轮 `input.json` 会写入 `dataset_preset`
  - 下一轮 trial 会物化 `generator_override.json`
  - `BUILD_DATASET` 会通过 `sinan-generator make-dataset --preset ... --override-file ...` 真正消费这些数据控制参数
- study 级归档摘要已支持真实 `opencode run --command study-status ...` 调用
- `RETUNE` 已支持真实 `Optuna` runtime：
  - 当前 trial 会先注册到 `optuna.sqlite3`
  - 下一轮 trial 会写入真实建议参数和最小运行时元数据
- `JUDGE` 在运行失败、超时或非法 JSON 时会稳定回退到 rules fallback
- `SUMMARIZE` / `plan-dataset` / `study-status` 在运行失败、超时或非法 JSON 时会稳定回退到本地确定性实现
- `RETUNE` 在 `Optuna` 缺失或 runtime 失败时会稳定回退到 deterministic fallback 参数

## 2. 验收范围

本次准入只检查两类内容：

1. 自主训练前置边界是否已经冻结。
2. 当前实现与文档是否足以支撑后续整合编码，而无需再次追问核心契约。

不在本次准入范围内的内容：

- `auto-train` 主控制器整合实现
- Windows GPU 训练机上的长试验稳定性

## 3. 逐项核对

| 任务 | 结论 | 已冻结的关键产物 |
|---|---|---|
| `TASK-AT-001` | 通过 | `study.json`、`input.json`、`dataset.json`、`train.json`、`test.json`、`evaluate.json`、`decision.json`、`trial_history.jsonl`、`decisions.jsonl` 契约已固化到 `core/auto_train/contracts.py` 与 `core/auto_train/storage.py` |
| `TASK-AT-002` | 通过 | 状态机、停止规则和恢复入口已固化到 `core/auto_train/state_machine.py` 与 `core/auto_train/stop_rules.py` |
| `TASK-AT-003` | 通过 | study/trial 目录蓝图、leaderboard、best trial 与恢复顺序已固化到 `core/auto_train/layout.py` 与 `core/auto_train/recovery.py` |
| `TASK-AT-004` | 通过 | dataset/train/test/evaluate runner 边界与错误封装已固化到 `core/auto_train/runners/` |
| `TASK-AT-005` | 通过 | `result_summary.json` 字段与压缩规则已固化到 `core/auto_train/summary.py` |
| `TASK-AT-006` | 通过 | `opencode` command 清单、输入输出与 headless 调用方式已固化到 `.opencode/commands/` 和 `core/auto_train/opencode_commands.py` |
| `TASK-AT-007` | 通过 | skills 分工、`decision.json` schema 与非法 JSON fallback 已固化到 `.opencode/skills/`、`core/auto_train/opencode_skills.py`、`core/auto_train/decision_protocol.py` |
| `TASK-AT-008` | 通过 | `group1/group2` 指标、晋级/放弃/数据重建标准已固化到 `core/auto_train/policies.py` |
| `TASK-AT-009` | 通过 | `Optuna` 搜索空间、pruning、no-improve 与纯规则 fallback 边界已固化到 `core/auto_train/optimize.py` |

## 4. 当前已满足的准入标准

下面这些问题，后续实现者现在不需要再追问：

- `study` 和 `trial` 工件长什么样。
- 当前 trial 应从哪个阶段恢复。
- `result_summary.json` 应该包含哪些指标与摘要。
- `opencode` 到底有哪些 command、哪些 skill、输出什么 JSON。
- `decision.json` 允许哪些动作，非法 JSON 如何回退。
- `group1` 和 `group2` 各自按什么标准判断好坏。
- `Optuna` 什么时候能介入、允许改哪些参数、什么时候必须停。

这意味着 `TASK-AT-010` 的核心验收标准已经满足：  
实现者可以开始写整合代码，而不会因为核心前提漂移被迫“边写边发明契约”。

## 5. 当前证据

代码与目录证据：

- `core/auto_train/`
- `.opencode/commands/`
- `.opencode/skills/`
- `tests/python/test_auto_train_*.py`

当前回归证据：

- 最近一次全量 Python 回归命令：
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
- 最近一次结果：
  - `119` 个 Python 测试通过

这些回归覆盖了：

- contracts / storage
- state machine / stop rules
- layout / recovery
- runners
- summary
- opencode commands
- opencode skills
- decision fallback
- group policies
- optimize boundary

## 6. 剩余风险

下面这些是**开放风险**，但当前不构成准入阻断：

### 6.1 真实运行时已进一步整合，但未全部闭环

当前已经有正式的 `uv run sinan auto-train ...` 入口，也已经把 contracts、runners、summary、judge、optimize 串成第一版控制循环骨架，并把 `result-read`、`judge-trial`、`plan-dataset`、`study-status` 接到了真实 `opencode` runtime，同时把 `RETUNE` 接到了真实 `Optuna` runtime。

影响：

- 当前已经能证明 `PLAN -> NEXT_ACTION` 的骨架可运行。
- 也还不能证明真实训练机上的长流程稳定性。

### 6.2 `opencode` 运行时未做端到端联调

当前 `.opencode/commands` 与 `.opencode/skills` 已冻结，并且已经完成 `result-read`、`judge-trial`、`plan-dataset`、`study-status` 的真实 `opencode serve` / `opencode run --attach ...` 适配接入。

影响：

- `result-read`、`judge-trial`、`plan-dataset`、`study-status` 的调用链和 fallback 边界已进入代码与测试。

### 6.3 `Optuna` 已接 runtime，但未完成实机验证

当前已冻结搜索空间与 pruning/fallback 规则，并且已经：

- 把 `optuna` 加入训练依赖
- 建立 `optuna.sqlite3` study 存储
- 接入实际 ask/tell + completed-trial import 运行时

影响：

- 当前能保证“怎么接不会越权”。
- 还不能证明“在真实训练预算下的搜索效果、恢复稳定性和性能开销”。

### 6.4 缺少真实训练机长流程演练

当前回归以本地 Python 测试为主，还没有在 Windows + NVIDIA 训练机上做：

- 中断恢复演练
- 多轮 no-improve 停止演练
- `opencode` judge 失败时的长流程回退演练

影响：

- 规则正确性已具备较强信心。
- 但长时间运行稳定性仍需实机验证。

## 7. 补项清单

这些属于后续实现任务，不是本轮阻断项：

1. 做 Windows GPU 训练机上的恢复、停止和 fallback 演练。
2. 增加至少一条从 `PLAN` 到 `STOP` 的整合测试路径。
3. 复核真实训练预算下的 `Optuna` 搜索效果与性能开销。

## 8. 下一阶段实施边界

允许进入的下一阶段工作：

- Windows + NVIDIA 训练机整合演练
- `auto-train` 长流程恢复/停止/fallback 验证
- end-to-end study 演练
- `Optuna` 搜索效果与性能复核

不允许越过的边界：

- 不得重新定义 `study`/`trial` JSON 结构
- 不得新增第 5 个 `opencode` command 或第 5 个 skill 来绕开当前分工
- 不得让 `Optuna` 越权决定 `PROMOTE_BRANCH` / `REGENERATE_DATA` / `ABANDON_BRANCH`
- 不得让 `opencode` 直接接管训练 shell

## 9. 最终判定

最终判定：**通过 `TASK-AT-010`，允许进入自主训练整合实现阶段。**

建议下一步直接进入：

1. Windows + NVIDIA 训练机上的端到端回归与恢复演练
2. `opencode` + `Optuna` 联合长流程演练
3. `PLAN -> STOP` 的整合测试路径
4. `Optuna` 搜索效果与性能复核
