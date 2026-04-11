# `group1` 实例匹配重构任务拆解

- 文档状态：实施中
- 当前阶段：IMPLEMENTATION
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

### `TASK-G1-REF-007`

- 当前 2026-04-11 已完成第一训练切片：
  - `core.train.group1.embedder.IconEmbedder` 已提供仓库内 PyTorch 度量学习编码器
  - `Group1TripletDataset` 已能消费 generator 输出的 `embedding/triplets.jsonl`
  - `uv run sinan train group1 --component icon-embedder ...` 已能训练并写出：
    - `runs/group1/<name>/icon-embedder/weights/best.pt`
    - `runs/group1/<name>/icon-embedder/weights/last.pt`
    - `runs/group1/<name>/icon-embedder/summary.json`
  - 训练 summary 已包含：
    - `embedding_recall_at_1`
    - `embedding_recall_at_3`
  - 当前 2026-04-11 已完成推理衔接切片：
    - `load_icon_embedder_runtime(...)` 已能加载 `icon-embedder/weights/*.pt`
    - `IconEmbedderRuntime.embed_crop(...)` 已能对 query/scene bbox crop 生成归一化 embedding
    - `map_group1_instances(...)` 已支持注入训练后的 embedding provider
- 当前仍待补齐：
  - 用真实大批量数据校准 recall 阈值
  - solver ONNX/runtime 导出

### `TASK-G1-REF-005`

- `query` 人工标注不再要求类名
- `scene` 人工标注不再要求 `NN|class`
- `reviewed/labels.jsonl` 能恢复 query 顺序和 scene 答案位置
- 当前 2026-04-11 已完成 reviewed 合同切换切片：
  - `group1 reviewed query` 现统一写 `query_item`
  - `group1 reviewed scene` 现统一写两位顺序号 `NN`
  - `exam export-reviewed --task group1` 已改为正式输出：
    - `query_items[{order,bbox,center}]`
    - `scene_targets[{order,bbox,center}]`
  - 导出器仍兼容读取旧人工答案：
    - `query=<class>`
    - `scene=NN|class`
  - legacy 类别信息已降级为可选 `class_guess`，不再是 reviewed 正式主键

### `TASK-G1-REF-009`

- 当前 2026-04-11 已完成第一轮预标注 cutover：
  - `train group1 prelabel` 生成的 `query/*.json` 已统一写 `query_item`
  - `train group1 prelabel` 生成的 `scene/*.json` 已统一写 `NN`
  - 预标注输出会把旧类别提示沉淀到 `shape.flags.class_guess`
  - `train group1 prelabel-query-dir` 也已切到同一合同
  - `train group1 prelabel` CLI 已支持实例匹配数据集透传 `icon-embedder`
  - `train group1 prelabel-vlm` 已支持：
    - 直接扫描同名 `query + scene|scence` 图片对
    - 调用本地 Ollama 多模态模型生成 reviewed 稀疏预标注
    - 把结果落成 `reviewed/query|scene/*.json`
    - 把中间产物写入 `.sinan/prelabel/group1/vlm/{source,labels,trace,summary}`
- 当前仍待补齐：
  - 面向人工审核的全量文档收口
  - 旧 reviewed 目录的批量迁移脚本（如需要）

### `TASK-G1-REF-008`

- 统一输出仍保持现有业务合同
- 对歧义样本必须显式拒判
- 当前 2026-04-11 已完成第一实现切片：
  - `core.inference.service.map_group1_instances()` 已具备 crop 相似度 + 全局 assignment + 歧义判定
  - `group1 predict` 与统一 `solve` 已接到实例匹配器
  - 实例匹配预测输出已优先写 `asset_id/template_id/variant_id`
  - 当前 2026-04-11 已完成第二实现切片：
    - `uv run sinan predict group1` 默认解析 `runs/group1/<train-name>/icon-embedder/weights/best.pt`
    - `uv run sinan test group1` 可把 `icon-embedder` 权重透传到整链路预测
    - 统一 solver bundle 会复制并声明 `models/group1/icon-embedder/model.pt`
    - `UnifiedSolverService` 会从 bundle 加载 `icon-embedder` 并交给 matcher
- 当前 2026-04-11 已完成第三实现切片：
  - `uv run sinan release export-solver-assets` 已能同时导出：
    - `click_proposal_detector.onnx`
    - `click_query_parser.onnx`
    - `click_icon_embedder.onnx`
    - `slider_gap_locator.onnx`
  - `solver/src/sinanz_group1_runtime.py` 已提供：
    - query parser / proposal detector ONNX Runtime 调用
    - icon embedder ONNX Runtime 调用
    - embedding 全局 assignment 与歧义拒判
  - `sinanz.sn_match_targets(...)` / `CaptchaSolver.sn_match_targets(...)` 已不再是占位接口
  - 当前 `TASK-G1-REF-008` 已收口到首版正式 E2E

### `TASK-G1-REF-011`

- 当前 2026-04-11 已完成第一运行时编排切片：
  - 内部 PT solver bundle 已纳入 `icon_embedder`
  - bundle `matcher/config.json` 已写出：
    - `strategy`
    - `embedding_model`
    - `similarity_threshold`
    - `ambiguity_margin`
  - 当前 `core.solve.service` 已能在 Python/PyTorch 过渡运行时消费该权重
- 当前 2026-04-11 已完成第二运行时编排切片：
  - `core.release.solver_export` 已补齐 `group1 + group2` 统一 ONNX 资产导出
  - `metadata/click_matcher.json` 已切到真实 matcher 配置，不再写占位状态
  - `solver/pyproject.toml` 已改为通配打包 `resources/models/*.onnx*` 与 `resources/metadata/*.json`
  - `sinanz_group1_service` 已能解析：
    - 内嵌 `resources/models/*.onnx`
    - 或显式传入的 `asset_root`
  - 当前首版正式 solver 交付口径已固定为：
    - 纯 Python wheel
    - `onnxruntime`
    - staged ONNX assets
- 当前 `TASK-G1-REF-011` 已按现阶段目标收口；Rust/native 不再作为本任务验收前置

### `TASK-G1-REF-010`

- `group1` 自动训练必须能区分：
  - `query_split_error`
  - `proposal_miss`
  - `embedding_confusion`
  - `assignment_error`
  - `ambiguity_reject`
- 当前 2026-04-11 已完成自动训练主链路修复切片：
  - `auto-train train` 已把 `icon-embedder` checkpoint 纳入 `TrainRecord.params`
  - `auto-train test` 已按实例匹配数据集自动透传 `icon-embedder`
  - `business_eval` 已把 `icon-embedder` 纳入正式 model-test 请求
  - `group1` 判卷已改为：
    - gold 有完整 identity 时按 identity 判
    - gold 只有 legacy `class/class_id` 时按 class 判
    - reviewed 稀疏答案时按 `order + center` 判
- 当前仍待补齐：
  - 面向 controller/judge 的细粒度失败归因落盘
  - 旧 `query_split_error` 等诊断口径与新 matcher 失败模式的统一映射

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
