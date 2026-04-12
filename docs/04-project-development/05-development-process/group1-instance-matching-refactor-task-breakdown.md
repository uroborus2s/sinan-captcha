# `group1` 实例匹配重构任务拆解

- 文档状态：实施中
- 当前阶段：IMPLEMENTATION
- 最近更新：2026-04-13
- 负责人：Codex
- 上游输入：
  - `docs/04-project-development/04-design/group1-instance-matching-refactor.md`
  - `docs/04-project-development/03-requirements/prd.md`
- 关联需求：`REQ-003`、`REQ-005`、`REQ-006`、`REQ-008`、`REQ-014`、`REQ-017`、`NFR-010`

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
| `TASK-G1-REF-004` | 重构生成器 `group1` 导出链 | `query-yolo/proposal-yolo/embedding/eval` 数据产物 | 生成链冻结 |
| `TASK-G1-REF-005` | 重构商业试卷与 reviewed 导出 | 新试卷标注规则与导出器 | 试卷合同冻结 |
| `TASK-G1-REF-014` | 实现 `query detector` | `query-yolo` 导出、训练、预测、评估入口 | query 可用 |
| `TASK-G1-REF-006` | 实现 `scene proposal detector` | 训练、预测、评估入口 | scene proposal 可用 |
| `TASK-G1-REF-007` | 实现 `icon embedder` | metric learning 训练与检索验证 | embedder 可用 |
| `TASK-G1-REF-008` | 实现 `matcher` 与整链路推理 | 相似度分配、歧义判定、统一输出 | E2E 可用 |
| `TASK-G1-REF-009` | 重构预标注与人工审核工具 | query/scene 新预标注合同 | 预标主线冻结 |
| `TASK-G1-REF-010` | 重构 `auto-train` 指标、阶段和 gate | 新阶段、失败归因、晋级门 | auto-train 冻结 |
| `TASK-G1-REF-011` | 重构 solver 导出与运行时编排 | 新 ONNX 资产和 runtime 配置 | solver 可交付 |
| `TASK-G1-REF-012` | 删除旧方案代码并完成 cutover | 旧 CLI/测试/文档/资产清单删除 | 主线切换完成 |
| `TASK-G1-REF-013` | 为 `prelabel-vlm` 增加过程目录与断点续传 | 逐样本状态目录、恢复语义、聚合重建规则 | VLM 预标注恢复冻结 |
| `TASK-G1-REF-015` | 固化 `group1` 严格串行工程化工作流 | smoke/v1/gate/回退/商业门禁方案 | 工作流冻结 |

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

- 生成器可稳定导出 `query-yolo/proposal-yolo/embedding/eval`
- 商业试卷可按“顺序 + 框”完成标注与导出

### 阶段 C：模型链与推理链重构

包含任务：

 - `TASK-G1-REF-014`
- `TASK-G1-REF-006`
- `TASK-G1-REF-007`
- `TASK-G1-REF-008`
- `TASK-G1-REF-011`

完成标准：

- query detector、proposal detector、embedder、matcher 整链路可跑
- solver 产物可导出并可被统一运行时加载

### 阶段 D：自动学习与工具链切换

包含任务：

- `TASK-G1-REF-009`
- `TASK-G1-REF-010`
- `TASK-G1-REF-013`
 - `TASK-G1-REF-015`

完成标准：

- 预标注、人审、auto-train 全部切到新口径
- `prelabel-vlm` 具备逐样本恢复和按文件名审计能力

### 阶段 E：旧方案清理与 cutover

包含任务：

- `TASK-G1-REF-012`

完成标准：

- 仓库中不再存在旧 `group1` 正式主线

## 4. 关键验收项

### `TASK-G1-REF-004`

- 必须能导出：
  - `query-yolo/`
  - `proposal-yolo/`
  - `embedding/`
  - `eval/labels.jsonl`
- 必须能从 `asset_id` 追溯回素材来源

### `TASK-G1-REF-014`

- 当前 2026-04-13 已完成第一切片：
  - generator 已写出 `query-yolo/images|labels/{train,val,test}` 与 `query-yolo/dataset.yaml`
  - `dataset.json` 已新增 `query_detector` 组件合同，指向 `query-yolo/dataset.yaml`
  - Python `group1 dataset loader` 已能读取 `query_detector` 字段
  - `train group1` 已新增 `query-detector` 组件：
    - CLI 已支持 `--component query-detector`
    - dry-run / from-run / resume 已能显式带出 `--query-model`
    - runner 已能消费 `query-yolo/dataset.yaml` 并写出 `query-detector/weights/*.pt`
    - 训练完成后已会在 `val` 上自动产出：
      - `query_item_recall`
      - `query_exact_count_rate`
      - `query_strict_hit_rate`
      - `query-detector/failcases.jsonl`
      - `query-detector gate`
  - 已通过：
    - `go test ./internal/app -count=1`
    - `uv run pytest tests/python/test_training_jobs.py -q`
    - `uv run pytest tests/python/test_auto_train_runners.py -q`
    - `uv run pytest tests/python/test_group1_embedder.py -q`
- 剩余待补齐：
  - `query detector` 推理接线
  - `auto-train` 对 query gate 的正式阶段消费
  - `query detector` 对外预测入口（替换规则 splitter 前的独立链路）
- 第一阶段验收要求：
  - 能消费 `query-yolo/dataset.yaml`
  - 能输出 `best.pt / last.pt / summary.json / failcases.jsonl`
  - 必须报告 query 侧“稳定输出正好 3 个目标”的业务指标

### `TASK-G1-REF-006`

- 第一阶段已要求：
  - Python `group1 dataset loader` 能读取 `sinan.group1.instance_matching.v1`
  - `train group1` 至少能消费 `proposal-yolo/dataset.yaml`
  - 训练入口必须明确区分 `query-detector`、`proposal-detector` 与 `icon-embedder`，不得静默回退到旧 query 检测链路
- 第二阶段再进入：
  - `scene proposal detector` 真实训练指标
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

### `TASK-G1-REF-013`

- `train group1 prelabel-vlm` 必须新增正式过程目录：
  - `process/index.json`
  - `process/samples/<sample_id>/status.json`
  - `process/samples/<sample_id>/request.json`
  - `process/samples/<sample_id>/response.json`
  - `process/samples/<sample_id>/normalized.json`
  - `process/samples/<sample_id>/error.json`
- 同一 `--project` 目录重跑时，必须按逐样本状态恢复：
  - `completed + normalized.json 完整` 的样本直接复用
  - `failed/running/partial` 只重跑该样本
- `reviewed/*.json`、`labels.jsonl`、`trace.jsonl`、`summary.json` 必须可由逐样本工件重建
- 当前 2026-04-12 已完成需求与设计冻结：
  - 已新增 `CR-001`
  - 已新增 `REQ-017`
  - 已冻结 `process/` 目录为正式恢复入口
- 当前仍待补齐：
  - CLI 参数与默认行为收口
  - 逐样本状态机实现
  - 同目录恢复回归测试
  - 聚合文件重建测试

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
    - `click_icon_embedder.onnx`
    - `slider_gap_locator.onnx`
  - `solver/src/sinanz_group1_runtime.py` 已提供：
    - 内置 query splitter / proposal detector 运行时调用
    - icon embedder ONNX Runtime 调用
    - embedding 全局 assignment 与歧义拒判
  - `sinanz.sn_match_targets(...)` / `CaptchaSolver.sn_match_targets(...)` 已不再是占位接口
  - 当前 `TASK-G1-REF-008` 已收口到首版正式 E2E
- 当前 2026-04-12 已完成主链路 query cutover：
  - `uv run sinan predict group1`
  - `uv run sinan test group1`
  - `UnifiedSolverService`
  - `auto-train test / business_eval`
  默认已改为 `query splitter + proposal detector + icon embedder + matcher`
  - 主链路默认不再解析独立 query 检测模型权重
  - 旧 query 检测组件已从正式训练/预标注边界删除

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
- 当前 2026-04-12 已完成 solver 资产收口：
  - `export-solver-assets` 主线已移除独立 query 检测模型导出物
  - `metadata/click_matcher.json` 已改为声明 `query_splitter_strategy = rule_based_v1`
  - 独立 `sinanz` 包已内置规则式 query splitter，不再要求独立 query 检测模型

### `TASK-G1-REF-010`

- `group1` 自动训练必须能区分：
  - `query_error`
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
  - `query detector`、`scene detector`、`embedder`、`matcher` 的阶段 gate 编排

### `TASK-G1-REF-015`

- 必须冻结首版严格串行工作流：
  - `dataset_smoke`
  - `dataset_v1`
  - `TRAIN_QUERY`
  - `QUERY_GATE`
  - `TRAIN_SCENE`
  - `SCENE_GATE`
  - `TRAIN_EMBEDDER_BASE`
  - `BUILD_EMBEDDER_HARDSET`
  - `TRAIN_EMBEDDER_HARD`
  - `CALIBRATE_MATCHER`
  - `OFFLINE_EVAL`
  - `BUSINESS_EVAL`
  - `EXPORT`
- 必须冻结每个阶段允许的状态：
  - `PASS`
  - `CONTINUE_TRAIN`
  - `REBUILD_DATASET`
  - `FIX_EXPORTER`
  - `BACK_TO_QUERY`
  - `BACK_TO_SCENE`
  - `BACK_TO_EMBEDDER`
  - `TUNE_MATCHER`
- 必须明确：
  - `dataset_smoke = 200`
  - `dataset_v1` 为第一版正式训练集，建议从 `10000` 条起步
  - 第一轮工程化流程不以三模型并行训练为默认前提

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
- 当前 2026-04-12 已完成第一批正式删除/收口：
  - 已从默认 CLI、默认 bundle、默认 solver 资产导出和 auto-train 主链路移除旧 query 检测依赖
  - 已删除主线对独立 query 检测 ONNX 资产的正式交付要求
  - 已补齐主仓库与 `sinanz` 包的 cutover 回归测试
- 当前 2026-04-12 已完成第二批正式删除/收口：
  - 已删除旧独立 query 检测训练入口
  - `train group1 prelabel-query-dir` 已改为纯规则式 splitter 预标注
  - `train group1 prelabel` 只保留 proposal detector + icon embedder 主线能力
