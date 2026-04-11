# `group1` 实例匹配重构任务拆解

- 文档状态：草稿
- 当前阶段：DESIGN
- 最近更新：2026-04-11
- 负责人：Codex
- 上游输入：
  - `docs/04-project-development/04-design/group1-instance-matching-refactor.md`
  - `docs/04-project-development/03-requirements/prd.md`
- 关联需求：`REQ-003`、`REQ-005`、`REQ-006`、`REQ-008`、`REQ-014`、`NFR-010`

## 1. 总原则

1. 先冻结需求和设计，再改代码。
2. 先改数据契约和生成器，再改训练与推理。
3. cutover 后必须删除旧正式方案，不保留长期双轨。
4. 每个任务都要产出可审计结果，不接受“边写边想”。

## 2. 任务总表

| 任务 ID | 任务名称 | 主要输出 | 阶段关口 |
| --- | --- | --- | --- |
| `TASK-G1-REF-001` | 冻结新需求与设计基线 | 需求、设计、矩阵同步完成 | 文档冻结 |
| `TASK-G1-REF-002` | 冻结新 `group1` 数据契约 | `dataset.json` 字段表、样例、校验规则 | 契约冻结 |
| `TASK-G1-REF-003` | 重构素材库主键与 manifest | `asset_id/template_id/variant_id` 规则 | 素材主键冻结 |
| `TASK-G1-REF-004` | 重构生成器 `group1` 导出链 | `proposal-yolo/embedding/eval` 数据产物 | 生成链冻结 |
| `TASK-G1-REF-005` | 重构商业试卷与 reviewed 导出 | 新试卷标注规则与导出器 | 试卷合同冻结 |
| `TASK-G1-REF-006` | 实现 `proposal detector` | 训练、预测、评估入口 | proposal 可用 |
| `TASK-G1-REF-007` | 实现 `icon embedder` | metric learning 训练与检索验证 | embedder 可用 |
| `TASK-G1-REF-008` | 实现 `matcher` 与整链路推理 | 相似度分配、歧义判定、统一输出 | E2E 可用 |
| `TASK-G1-REF-009` | 重构预标注与人工审核工具 | query/scene 新预标注合同 | 预标主线冻结 |
| `TASK-G1-REF-010` | 重构 `auto-train` 指标、阶段和 gate | 新阶段、失败归因、晋级门 | auto-train 冻结 |
| `TASK-G1-REF-011` | 重构 solver 导出与运行时编排 | 新 ONNX 资产和 runtime 配置 | solver 可交付 |
| `TASK-G1-REF-012` | 删除旧方案代码并完成 cutover | 旧 CLI/测试/文档/资产清单删除 | 主线切换完成 |

## 3. 分阶段执行

### 阶段 A：文档与契约冻结

包含任务：

- `TASK-G1-REF-001`
- `TASK-G1-REF-002`
- `TASK-G1-REF-003`

完成标准：

- 正式需求、设计、矩阵、任务文档全部同步
- 新 `group1` 字段和素材主键规则不再变动

### 阶段 B：生成器与试卷体系重构

包含任务：

- `TASK-G1-REF-004`
- `TASK-G1-REF-005`

完成标准：

- 生成器可稳定导出 `proposal-yolo/embedding/eval`
- 商业试卷可按“顺序 + 框”完成标注与导出

### 阶段 C：模型链与推理链重构

包含任务：

- `TASK-G1-REF-006`
- `TASK-G1-REF-007`
- `TASK-G1-REF-008`
- `TASK-G1-REF-011`

完成标准：

- proposal detector、embedder、matcher 整链路可跑
- solver 产物可导出并可被统一运行时加载

### 阶段 D：自动学习与工具链切换

包含任务：

- `TASK-G1-REF-009`
- `TASK-G1-REF-010`

完成标准：

- 预标注、人审、auto-train 全部切到新口径

### 阶段 E：旧方案清理与 cutover

包含任务：

- `TASK-G1-REF-012`

完成标准：

- 仓库中不再存在旧 `group1` 正式主线

## 4. 关键验收项

### `TASK-G1-REF-004`

- 必须能导出：
  - `proposal-yolo/`
  - `embedding/`
  - `eval/labels.jsonl`
- 必须能从 `asset_id` 追溯回素材来源

### `TASK-G1-REF-006`

- 第一阶段已要求：
  - Python `group1 dataset loader` 能读取 `sinan.group1.instance_matching.v1`
  - `train group1` 至少能消费 `proposal-yolo/dataset.yaml`
  - 当 `dataset.json` 未提供 `query_parser` 数据集时，训练入口必须显式拒绝该组件，而不是静默读旧目录
- 第二阶段再进入：
  - `proposal detector` 真实训练指标
  - embedder / matcher 主线接管最终位置挑选

### `TASK-G1-REF-005`

- `query` 人工标注不再要求类名
- `scene` 人工标注不再要求 `NN|class`
- `reviewed/labels.jsonl` 能恢复 query 顺序和 scene 答案位置

### `TASK-G1-REF-008`

- 统一输出仍保持现有业务合同
- 对歧义样本必须显式拒判

### `TASK-G1-REF-010`

- `group1` 自动训练必须能区分：
  - `query_split_error`
  - `proposal_miss`
  - `embedding_confusion`
  - `assignment_error`
  - `ambiguity_reject`

### `TASK-G1-REF-012`

- 必须删除：
  - 旧正式 CLI
  - 旧正式用户文档
  - 旧正式设计基线引用
  - 旧正式测试主线
- 必须产出：
  - 删除清单
  - cutover 验证记录
  - 回归测试结果
