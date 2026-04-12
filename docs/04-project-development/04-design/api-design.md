# 接口与入口基线

- 项目名称：sinan-captcha
- 当前阶段：IMPLEMENTATION（设计基线维护）

## 设计结论

V1 不先实现公网 HTTP API。新的正式交付目标也不再是“训练仓库里的 `solve` 子命令 + 外置 bundle”。

首版需要固定两层合同：

1. 独立 solver 项目合同：
   - `sinanz` PyPI 包
   - 业务函数入口
   - 默认内嵌 ONNX 推理资产加载
   - 纯 Python `onnxruntime` 运行时
2. 生产面合同：
   - 生成器导出
   - 训练
   - 评估
   - 自主训练
   - `PT -> ONNX` 推理资产导出
   - solver 项目发布交接

设计重点不是“把一切都挂成 API”，而是先把：

- 调用方最终面对的 Python 函数合同
- 训练产线内部各入口的责任边界

同时固定下来。

## API-001 独立 solver Python API 合同

- 类型：独立 PyPI 库函数合同
- 调用方：最终业务使用者、维护者、后续 HTTP 映射层
- 包名：
  - 发布名：`sinanz`
  - 导入名：`sinanz`
- 设计原则：
  - 调用方默认只安装 wheel，不再准备 `request.json`
  - 调用方默认不传 `bundle_dir`
  - 调用方默认不关心权重路径
  - solver 默认从包内资源加载推理资产

### 业务函数

```python
ImageInput = str | Path | bytes | PIL.Image.Image | numpy.ndarray
BBox = tuple[int, int, int, int]

sn_match_slider(
    background_image: ImageInput,
    puzzle_piece_image: ImageInput,
    *,
    puzzle_piece_start_bbox: BBox | None = None,
    device: str = "auto",
    return_debug: bool = False,
) -> SliderGapCenterResult

sn_match_targets(
    query_icons_image: ImageInput,
    background_image: ImageInput,
    *,
    device: str = "auto",
    return_debug: bool = False,
) -> OrderedClickTargetsResult
```

### 可选面向对象封装

```python
class CaptchaSolver:
    def __init__(
        self,
        *,
        device: str = "auto",
        asset_root: str | Path | None = None,
    ) -> None: ...

    def sn_match_slider(...) -> SliderGapCenterResult: ...
    def sn_match_targets(...) -> OrderedClickTargetsResult: ...
```

说明：

- `asset_root` 只用于维护者调试、自定义模型或回归测试。
- 公开使用路径默认不需要 `asset_root`，会自动加载内嵌模型。
- 顶层函数可复用默认单例 `CaptchaSolver`，避免调用方先理解对象生命周期。
- `device` 当前由 Python `onnxruntime` runtime 直接做 provider 选择。

### `group2` 业务参数与结果

- 输入：
  - `background_image`
  - `puzzle_piece_image`
  - 可选 `puzzle_piece_start_bbox`
  - 可选 `device`
  - 可选 `return_debug`
- 输出：
  - `target_center`
  - `target_bbox`
  - 可选 `puzzle_piece_offset`
  - 可选 `debug`

推荐结果类型：

```python
@dataclass(slots=True)
class SliderGapCenterResult:
    target_center: tuple[int, int]
    target_bbox: tuple[int, int, int, int]
    puzzle_piece_offset: tuple[int, int] | None = None
    debug: SliderGapDebugInfo | None = None
```

### `group1` 业务参数与结果

- 输入：
  - `query_icons_image`
  - `background_image`
  - 可选 `device`
  - 可选 `return_debug`
- 输出：
  - `ordered_target_centers`
  - `ordered_targets`
  - `missing_query_orders`
  - `ambiguous_query_orders`
  - 可选 `debug`

推荐结果类型：

```python
@dataclass(slots=True)
class OrderedClickTarget:
    query_order: int
    center: tuple[int, int]
    class_id: int
    class_name: str
    score: float


@dataclass(slots=True)
class OrderedClickTargetsResult:
    ordered_target_centers: list[tuple[int, int]]
    ordered_targets: list[OrderedClickTarget]
    missing_query_orders: list[int]
    ambiguous_query_orders: list[int]
    debug: ClickCaptchaDebugInfo | None = None
```

### 示例

```python
from sinanz import (
    sn_match_slider,
    sn_match_targets,
)

slider_result = sn_match_slider(
    background_image="master.png",
    puzzle_piece_image="tile.png",
)

click_result = sn_match_targets(
    query_icons_image="query.png",
    background_image="scene.png",
)
```

### 异常合同

独立 solver 包不再以结构化错误对象作为主合同，而是采用 Python 异常：

- `SolverInputError`
  - 输入图片无法解析、尺寸不合法、参数冲突
- `SolverAssetError`
  - 内嵌模型缺失、版本不兼容、模型元数据非法
- `SolverRuntimeError`
  - 模型加载失败、推理运行失败、结果后处理失败

设计约束：

- 顶层业务函数成功时只返回结果对象，不混入错误包装层。
- 调用方看到函数名就应知道业务含义，不需要理解 `group1` / `group2` 内部编排。
- 训练仓库内现有 `packages/sinan-captcha/src/solve` CLI 只保留迁移期调试价值，不再视为最终用户主入口。

## API-002 推理资产导出合同

- 类型：训练仓库 CLI 入口 + 目录合同
- 调用方：项目维护者、发布流程、独立 solver 项目构建流程
- 输入：
  - `group1` 训练运行名
  - `group2` 训练运行名
  - 输出目录
- 输出：
  - `manifest.json`
  - `models/click_proposal_detector.onnx`
  - `models/click_icon_embedder.onnx`
  - `models/slider_gap_locator.onnx`
  - `metadata/click_proposal_detector.json`
  - `metadata/click_icon_embedder.json`
  - `metadata/slider_gap_locator.json`
  - `metadata/click_matcher.json`
  - `metadata/class_names.json`
  - `metadata/export_report.json`

### 设计目标入口

```bash
uv run sinan release export-solver-assets \
  --project-dir . \
  --group1-proposal-checkpoint runs/group1/firstpass/proposal-detector/weights/best.pt \
  --group1-embedder-checkpoint runs/group1/firstpass/icon-embedder/weights/best.pt \
  --group1-run firstpass \
  --group2-checkpoint runs/group2/firstpass/weights/best.pt \
  --group2-run firstpass \
  --output-dir dist/solver-assets/20260405 \
  --asset-version 20260405
```

说明：

- 当前命令已统一承载 `group1 + group2` 导出。
- 若缺少 `group1` 两个 checkpoint，命令仍可只导出 `group2`，但 `click_matcher.json` 与 `class_names.json` 会保持占位状态。

### 导出目录基线

```text
dist/
  solver-assets/
    20260405/
      manifest.json
      models/
        click_proposal_detector.onnx
        click_icon_embedder.onnx
        slider_gap_locator.onnx
      metadata/
        click_proposal_detector.json
        click_icon_embedder.json
        slider_gap_locator.json
        click_matcher.json
        class_names.json
        export_report.json
```

说明：

- 这是训练仓库与独立 solver 项目之间的内部交接物，不是最终调用方安装目录。
- 导出物必须是推理专用 ONNX 资产，不得继续携带训练态 `optimizer_state`、绝对路径和运行目录引用。
- 独立 solver 项目构建时，会把这批资产复制到 wheel 资源目录中，由纯 Python `onnxruntime` 运行时加载。
- 字段级合同、命名规则和 provider 顺序以 [solver-asset-export-contract.md](/Users/uroborus/AiProject/sinan-captcha/docs/04-project-development/04-design/solver-asset-export-contract.md) 和 [solver_asset_contract.py](/Users/uroborus/AiProject/sinan-captcha/packages/sinan-captcha/src/release/solver_asset_contract.py) 为准。

## API-003 独立 solver 构建产物合同

- 类型：独立 solver 项目发布合同
- 调用方：维护者、发布链路、最终业务使用者
- 最终对外产物：
  - 纯 Python PyPI wheel
  - 包含 Python API
  - 包含内嵌 ONNX 模型与 metadata
- 最终用户不再接触：
  - 外置 `bundle_dir`
  - 模型路径
  - 训练运行目录

### 设计基线

```text
sinanz-0.1.0-py3-none-any.whl
  resources/
    models/
      click_proposal_detector.onnx
      click_icon_embedder.onnx
      slider_gap_locator.onnx
    metadata/
      click_matcher.json
      class_names.json
```

说明：

- 当前正式交付是纯 Python `py3-none-any` wheel。
- Python 层负责参数规范化、图片输入解码、ONNX Runtime 会话建立和后处理桥接。

## API-004 生成器数据导出合同

- 类型：CLI 入口
- 调用方：训练机操作者、项目维护者、自主训练控制器
- 输入：
  - `task`
  - `workspace`
  - `dataset_dir`
  - 可选 preset / 覆盖参数
- 输出：
  - `group1`：pipeline dataset 目录
  - `group2`：paired dataset 目录
  - QA 结果与批次元数据

### 正式命令形态

```bash
sinan-generator make-dataset --workspace D:\sinan-captcha-generator\workspace --task group1 --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass
```

## API-005 训练入口合同

- 类型：CLI 入口
- 调用方：训练机操作者、自主训练控制器
- 输入：
  - `group1` / `group2`
  - `dataset.json`
  - 初始化权重或检查点
  - 训练超参数
- 输出：
  - 模型权重
  - 训练摘要
  - 日志与运行目录

### 正式命令形态

```bash
uv run sinan train group1 --dataset-version firstpass --name firstpass
uv run sinan train group2 --dataset-version firstpass --name firstpass
```

## API-005 测试与评估入口合同

- 类型：CLI 入口
- 调用方：训练机操作者、自主训练控制器
- 输入：
  - 任务类型
  - 数据集版本
  - 训练运行名
  - 或显式 gold / prediction / report 目录
- 输出：
  - 中文测试报告
  - JSONL 评估报告
  - 失败样本清单

### 正式命令形态

```bash
uv run sinan test group1 --dataset-version firstpass --train-name firstpass
uv run sinan evaluate --task group1 --gold-dir <gold-dir> --prediction-dir <pred-dir> --report-dir <report-dir>
```

## API-006 自主训练入口合同

- 类型：CLI 入口
- 调用方：项目维护者、训练机操作者
- 输入：
  - `task`
  - `goal_text` 或 `goal_file`
  - `study_name`
  - `train_root`
  - `generator_workspace`
  - 预算和停止规则
  - `allowed_actions`
  - `watchdog_policy`
- 输出：
  - `goal.json`
  - `study.json`
  - `trial_history.jsonl`
  - 各 trial 工件
  - `decision.json`
  - `result_summary.json`
  - `promotion_report.json`

### 正式命令形态

```bash
uv run sinan auto-train compile-goal group2 --goal-text "在 12 小时内把 group2 验证集 P95 中心点误差压到 4px 以内，并导出可供 sinanz 调用的候选资产"
uv run sinan auto-train run group1 --study-name study_001 --train-root D:\sinan-captcha-work --generator-workspace D:\sinan-generator\workspace
```

说明：

- `compile-goal` 负责把一句自然语言目标编译成 `GoalContract` / `StudyContract`，冻结指标、预算、gate 和允许动作集。
- `run` 负责消费已冻结合同并推进 stage capsules，不直接接受 agent 原始 shell 命令。
- agent 侧所有 verdict 都必须通过 schema 校验，并带 `input_hash` 与 `evidence_refs`。

## API-007 发布与交付打包合同

- 类型：CLI 入口
- 调用方：项目维护者、发布流程
- 输入：
  - `project_dir`
  - `generator_exe`
  - 输出目录
- 输出：
  - Python wheel / sdist
  - Windows 训练交付包
  - solver 资产导出目录
  - 交付说明

### 设计目标入口

```bash
uv run sinan release build --project-dir .
uv run sinan release package-windows --project-dir . --generator-exe dist/generator/windows-amd64/sinan-generator.exe --output-dir release/windows/v1
uv run sinan release export-solver-assets --project-dir . --group1-proposal-checkpoint runs/group1/firstpass/proposal-detector/weights/best.pt --group1-embedder-checkpoint runs/group1/firstpass/icon-embedder/weights/best.pt --group1-run firstpass --group2-checkpoint runs/group2/firstpass/weights/best.pt --group2-run firstpass --output-dir dist/solver-assets/20260405 --asset-version 20260405
```

说明：

- `package-windows` 继续服务训练机与维护者交付，不再冒充最终 solver 产品发布物。
- 最终给业务调用方的发布物应由独立 solver 项目构建并上传到 PyPI。
- 训练仓库负责产出推理资产，独立 solver 项目负责嵌入资产、构建 wheel 和发布。
- 当前导出命令已支持 `group1 + group2` 全量资产；只有在缺失 `group1` checkpoint 时，相关 metadata 才会保留占位状态。
