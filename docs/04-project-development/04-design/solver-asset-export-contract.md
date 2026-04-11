# Solver 资产导出合同

- 文档状态：生效
- 当前阶段：IMPLEMENTATION（`TASK-G1-REF-011`）
- 目标读者：训练链路负责人、Python 实现者、发布维护者
- 负责人：Codex

## 1. 设计结论

`TASK-SOLVER-MIG-006` 的目标是先冻结训练仓库导出给 `sinanz` 的稳定资产面；当前 `TASK-G1-REF-011` 已把 `group1 + group2` 的首版正式导出链路接上。

本轮冻结后，训练仓库与独立 solver 项目之间的内部交接资产统一为：

- `manifest.json`
- `models/*.onnx`
- `metadata/*.json`

调用方需要记住的结论只有三条：

1. 最终用户安装的是 `sinanz` wheel，不直接接触这批导出资产。
2. `sinanz` 包和调试脚本后续都只能消费这份合同，不能继续回头读训练目录。
3. 当前仓库已实现 `group1 + group2` 的统一 `export-solver-assets`，并可继续通过 `stage-solver-assets` 内嵌到 `sinanz` wheel。

## 2. 固定文件命名

### 2.1 ONNX 模型文件名

| 模型 ID | 任务 | 组件 | 固定文件名 | 固定相对路径 |
|---|---|---|---|---|
| `click_proposal_detector` | `group1` | `proposal_detector` | `click_proposal_detector.onnx` | `models/click_proposal_detector.onnx` |
| `click_query_parser` | `group1` | `query_parser` | `click_query_parser.onnx` | `models/click_query_parser.onnx` |
| `click_icon_embedder` | `group1` | `icon_embedder` | `click_icon_embedder.onnx` | `models/click_icon_embedder.onnx` |
| `slider_gap_locator` | `group2` | `locator` | `slider_gap_locator.onnx` | `models/slider_gap_locator.onnx` |

### 2.2 Metadata 文件名

| 文件用途 | 固定文件名 | 固定相对路径 |
|---|---|---|
| `click_proposal_detector` 元数据 | `click_proposal_detector.json` | `metadata/click_proposal_detector.json` |
| `click_query_parser` 元数据 | `click_query_parser.json` | `metadata/click_query_parser.json` |
| `click_icon_embedder` 元数据 | `click_icon_embedder.json` | `metadata/click_icon_embedder.json` |
| `slider_gap_locator` 元数据 | `slider_gap_locator.json` | `metadata/slider_gap_locator.json` |
| `group1` matcher 配置 | `click_matcher.json` | `metadata/click_matcher.json` |
| 类别表 | `class_names.json` | `metadata/class_names.json` |
| 导出报告 | `export_report.json` | `metadata/export_report.json` |

## 3. 顶层目录基线

```text
dist/
  solver-assets/
    20260405/
      manifest.json
      models/
        click_proposal_detector.onnx
        click_query_parser.onnx
        click_icon_embedder.onnx
        slider_gap_locator.onnx
      metadata/
        click_proposal_detector.json
        click_query_parser.json
        click_icon_embedder.json
        slider_gap_locator.json
        click_matcher.json
        class_names.json
        export_report.json
```

目录规则：

- 所有路径都必须是导出目录内部的相对路径。
- 不允许绝对路径。
- 不允许 `..` 跳目录。
- 不允许把 `runs/`、`datasets/`、`studies/` 直接拷入导出目录。

## 4. `manifest.json` 合同

### 4.1 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `asset_format` | `string` | 固定为 `sinan.solver.assets.v1` |
| `asset_version` | `string` | 导出资产版本，推荐与发布版本或日期版本对齐 |
| `exported_at` | `string` | UTC ISO8601 时间戳 |
| `runtime.target` | `string` | 固定为 `python-onnxruntime` |
| `runtime.python_package` | `string` | 固定为 `sinanz` |
| `runtime.preferred_execution_providers` | `array[string]` | 当前默认顺序：`CUDAExecutionProvider`、`CPUExecutionProvider` |
| `models` | `object` | 稳定模型 ID 的清单；当前首版正式要求包含 `click_proposal_detector`、`click_query_parser`、`click_icon_embedder`、`slider_gap_locator` |
| `metadata_files` | `object` | 非模型类 metadata 的相对路径清单 |

### 4.2 `models.<model_id>` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `task` | `string` | `group1` 或 `group2` |
| `component` | `string` | `proposal_detector` / `query_parser` / `icon_embedder` / `locator` |
| `format` | `string` | 固定为 `onnx` |
| `opset` | `integer` | 该模型导出的 ONNX opset 版本 |
| `path` | `string` | 模型相对路径 |
| `metadata` | `string` | 模型 metadata 相对路径 |
| `input.names` | `array[string]` | ONNX 输入 tensor 名称 |
| `input.image_size` | `array[int]` | `[width, height]` |
| `input.layout` | `string` | 固定为 `NCHW` |
| `input.pixel_format` | `string` | 固定为 `RGB` |
| `input.dtype` | `string` | 固定为 `float32` |
| `input.normalization` | `string` | 固定为 `zero_to_one` |
| `output.names` | `array[string]` | ONNX 输出 tensor 名称 |
| `output.postprocess` | `string` | 后处理协议名 |
| `preferred_execution_providers` | `array[string]` | 模型级 provider 偏好，默认与 `runtime` 一致 |

### 4.3 `metadata_files` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `click_matcher` | `string` | `group1` matcher 配置路径 |
| `class_names` | `string` | 类别表路径 |
| `export_report` | `string` | 导出报告路径 |

## 5. 模型 metadata 合同

每个 `metadata/<model_id>.json` 至少包含下面字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `model_id` | `string` | 与 manifest 中的模型 ID 一致 |
| `task` | `string` | `group1` 或 `group2` |
| `component` | `string` | 组件名 |
| `runtime_target` | `string` | 固定为 `python-onnxruntime` |
| `format` | `string` | 固定为 `onnx` |
| `opset` | `integer` | ONNX opset |
| `input` | `object` | 与 manifest 中 `input` 同结构 |
| `output` | `object` | 与 manifest 中 `output` 同结构 |
| `preferred_execution_providers` | `array[string]` | 模型级 provider 顺序 |

设计约束：

- 模型 metadata 必须足够让 `sinanz` 运行时和调试脚本独立理解输入输出约束。
- 模型 metadata 不得包含训练机绝对路径。
- 模型 metadata 不得依赖外部环境变量才能解释。

## 6. `export_report.json` 合同

`export_report.json` 服务于维护者排障和发布追踪，不服务于最终调用方。

### 6.1 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `asset_format` | `string` | 固定为 `sinan.solver.assets.v1` |
| `asset_version` | `string` | 与 manifest 一致 |
| `group1_run` | `string` | `group1` 导出所用训练运行名 |
| `group2_run` | `string` | `group2` 导出所用训练运行名 |
| `exported_at` | `string` | UTC ISO8601 时间戳 |
| `runtime_target` | `string` | 固定为 `python-onnxruntime` |
| `exported_models` | `array[object]` | 每个导出模型的来源与完整性记录 |

### 6.2 `exported_models[]` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `model_id` | `string` | 稳定模型 ID |
| `source_checkpoint` | `string` | 来源 checkpoint 路径，必须是相对逻辑路径，不得是绝对路径 |
| `exported_model_path` | `string` | 导出模型相对路径 |
| `exported_metadata_path` | `string` | 导出 metadata 相对路径 |
| `sha256` | `string` | 导出模型文件的完整性摘要 |

## 7. Provider 与后处理命名规则

- provider 顺序当前固定为：
  - `CUDAExecutionProvider`
  - `CPUExecutionProvider`
- `group1` 当前默认后处理协议：
  - `yolo_detect_v1`
  - `normalized_embedding_v1`
- `group2` 当前默认后处理协议：
  - `paired_gap_bbox_v1`

这些值不是训练框架内部实现细节，而是 `sinanz` 运行时和调试脚本之间的稳定约定。

## 8. 当前仓库中的代码事实源

本轮合同冻结后，仓库内的代码事实源是：

- [solver_asset_contract.py](/Users/uroborus/AiProject/sinan-captcha/core/release/solver_asset_contract.py)
- [test_solver_asset_contract.py](/Users/uroborus/AiProject/sinan-captcha/tests/python/test_solver_asset_contract.py)

如果未来实现修改了文件名、字段名或 provider 顺序，必须先更新这两处，再更新导出实现。

## 9. 当前仍未完成的实现

这份合同已经冻结，且 `group1 + group2` 的首条实现已经接入：

- 已实现命令：`uv run sinan release export-solver-assets --group1-proposal-checkpoint ... --group1-query-checkpoint ... --group1-embedder-checkpoint ... --group1-run ... --group2-checkpoint ... --group2-run ... --output-dir ... --asset-version ...`
- 已实现 `group1 + group2` 的 `PT -> ONNX` 导出与 `manifest.json / metadata / export_report.json` 落盘
- 已实现 `click_matcher.json` 的真实 matcher 配置落盘
- `sinanz` wheel 当前按纯 Python 包路线消费这些资产，运行时为 `onnxruntime`
- 如导出时未传完整 `group1` checkpoint，`click_matcher.json` 与 `class_names.json` 会退回占位状态
