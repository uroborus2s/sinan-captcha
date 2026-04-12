# 训练者：训练器 CLI 全量参考（`sinan`）

本页按“逐命令可执行手册”整理 `uv run sinan ...` 的公开命令（源码基线：`2026-04-11`）。

每个命令都包含：

- 用途
- 适用场景
- 参数说明
- 最小示例
- 成功标志
- 常见误用

## 1. 调用方式

仓库或训练目录内执行：

```bash
uv run sinan <command> ...
```

## 2. 命令总览

```text
sinan
├── env check
├── env setup-train
├── materials build
├── materials audit-group1-query
├── materials collect-backgrounds
├── dataset validate
├── exam
│   ├── prepare
│   ├── export-reviewed
│   └── build-group2-prelabel-yolo
├── autolabel
├── train
│   ├── group1
│   │   ├── prelabel
│   │   ├── prelabel-query-dir
│   │   └── prelabel-vlm
│   └── group2
│       └── prelabel
├── predict
│   ├── group1
│   └── group2
├── test
│   ├── group1
│   └── group2
├── evaluate
├── auto-train
│   ├── run {group1|group2}
│   └── stage <stage> {group1|group2}
└── solve
    ├── build-bundle
    ├── validate-bundle
    └── run
```

| 命令                                | 主要用途                         | 典型使用场景           |
| --------------------------------- | ---------------------------- | ---------------- |
| `env check`                       | 训练机环境自检                      | 新机器首次验收          |
| `env setup-train`                 | 初始化训练目录与依赖                   | 训练机标准化初始化        |
| `materials build`                 | 构建离线素材包                      | 素材治理与归档          |
| `materials audit-group1-query`    | 审计 query 图并生成模板素材包           | `group1` 素材清洗/补齐 |
| `materials collect-backgrounds`   | 分析参考背景风格并下载相似背景图             | 背景素材扩充           |
| `dataset validate`                | 校验 JSONL 数据集合同               | 数据出库前门禁          |
| `exam prepare`                    | 准备 reviewed 试卷目录             | 人工标注前准备          |
| `exam export-reviewed`            | 导出 reviewed 为 `labels.jsonl` | 人工复核后回灌          |
| `exam build-group2-prelabel-yolo` | 为 group2 预标注构建 YOLO 集        | group2 标注前准备     |
| `autolabel`                       | 离线自动标注转换                     | 规则预标注与 seed 扩增   |
| `train group1`                    | 训练 group1 主模型链               | 点选任务训练           |
| `train group1 prelabel*`          | 生成 group1 预标注                | 人工审核前自动初标        |
| `train group2`                    | 训练 group2 主模型                | 拖拽任务训练           |
| `train group2 prelabel`           | 生成 group2 预标注                | group2 标注提效      |
| `predict group1/group2`           | 跑预测产物                        | 训练后快速出预测         |
| `test group1/group2`              | 跑标准测试流程                      | 出报告前模型验证         |
| `evaluate`                        | 比对 gold 与 prediction         | 指标计算与报告          |
| `auto-train run/stage`            | 自主训练控制器入口                    | 无人值守或阶段调试        |
| `solve *`                         | 本地 bundle 构建与试跑              | 训练产物交付验收         |

## 3. 环境命令

### 3.1 `env check`

#### 用途

输出训练机环境 JSON（`uv/torch/cuda/ultralytics/nvidia-smi`）。

#### 适用场景

- 安装依赖后确认 GPU 与训练栈是否可用。
- 报错排查时生成环境快照。

#### 语法

```bash
uv run sinan env check
```

#### 最小示例

```bash
uv run sinan env check
```

#### 成功标志

- 返回结构化 JSON。
- 包含关键字段（如 CUDA 可用性、torch 版本）。

#### 常见误用

- 在错误虚拟环境执行，导致误判“环境不可用”。

### 3.2 `env setup-train`

#### 用途

创建训练目录并安装训练依赖，形成标准训练运行环境。

#### 适用场景

- 新训练机首次初始化。
- 训练目录损坏后重建。

#### 语法

```bash
uv run sinan env setup-train \
  [--train-root <path>] \
  [--generator-root <path>] \
  [--package-spec <spec>] \
  [--torch-backend auto|cpu|cu118|cu126|cu128|cu130] \
  [--yes]
```

#### 参数说明

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--train-root` | `<cwd>/sinan-captcha-work` | 训练目录路径。 |
| `--generator-root` | 空 | 推荐生成器目录，仅用于输出提示。 |
| `--package-spec` | `sinan-captcha[train]==<runtime-version>` | 训练目录安装包规格。 |
| `--torch-backend` | `auto` | PyTorch index 选择策略。 |
| `--yes` | `false` | 跳过交互确认。 |

#### 最小示例

```bash
uv run sinan env setup-train --train-root D:\sinan-captcha-work --torch-backend cu128 --yes
```

#### 成功标志

- 训练目录结构创建成功。
- 依赖安装完成且可执行 `uv run sinan env check`。

#### 常见误用

- 不指定 `--train-root`，把训练目录创建在错误路径。
- CUDA 后端选错，导致 torch 与驱动不匹配。

## 4. 素材与数据命令

### 4.1 `materials build`

#### 用途

基于 TOML 规格构建本地离线素材包。

#### 适用场景

- 定期构建可复用素材集。
- 新增素材源后统一输出标准包。

#### 语法

```bash
uv run sinan materials build --spec <toml> --output-root <dir> [--cache-dir <dir>]
```

#### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--spec` | 是 | 无 | 素材构建规格文件。 |
| `--output-root` | 是 | 无 | 素材包输出目录。 |
| `--cache-dir` | 否 | `.cache/materials` | 下载与处理中间缓存目录。 |

#### 最小示例

```bash
uv run sinan materials build --spec configs/materials-pack.toml --output-root work_home/materials
```

#### 成功标志

- `output-root` 下生成可用素材包和索引。

#### 常见误用

- 规格文件路径错误或内容不完整，导致中途失败。

### 4.2 `materials audit-group1-query`

#### 用途

使用本地 Ollama 多模态模型分析 `group1` query 图，生成 `tpl_/var_` 结构素材包与审计报告。

#### 适用场景

- `group1` 图标素材治理。
- 失败图片重试与模板补齐。

#### 语法

```bash
uv run sinan materials audit-group1-query \
  --model <ollama-model> \
  [--query-dir <dir>] \
  [--output-root <dir>] \
  [--report-root <dir>] \
  [--output-jsonl <file>] \
  [--trace-jsonl <file>] \
  [--template-report-json <file>] \
  [--retry-from-report <file>] \
  [--cache-dir <dir>] \
  [--ollama-url <url>] \
  [--timeout-seconds <int>] \
  [--min-variants-per-template <int>] \
  [--limit <int>] \
  [--dry-run] \
  [--overwrite] \
  [--quiet] \
  [--yes]
```

#### 关键参数

| 参数 | 说明 |
| --- | --- |
| `--model` | 必填，本地 Ollama 多模态模型名（如 `gemma4:26b`）。 |
| `--timeout-seconds` | 默认 `600`，同时作用于逐图识别与最终模板汇总。 |
| `--retry-from-report` | 复用旧报告成功项，只重试失败图片。 |
| `--quiet` | 关闭执行进度日志。默认会输出逐图识别、模板汇总、候选图标下载与 SVG 光栅化进度。 |
| `--yes` | 非交互模式接受默认路径。 |

自动下载的候选图标大多来自 SVG 图标库。当前命令会优先尝试系统级 SVG 光栅化工具（如 `magick`、`rsvg-convert`、`inkscape`），若这些命令不存在，再回退到训练环境内置的 `svglib/reportlab` Python 光栅化链路。Windows 环境若是通过 `env setup-train` 创建的标准训练目录，更新到最新 `sinan-captcha[train]` 后通常不需要额外安装图形工具；若仍想提高成功率，仍可额外安装 ImageMagick、librsvg 或 Inkscape。

#### 最小示例

```bash
uv run sinan materials audit-group1-query --model gemma4:26b --overwrite --yes
```

#### 成功标志

- 输出审计 JSONL/trace 文件。
- 终端持续输出 `[group1-query-audit]` 进度日志；若停在候选图标阶段，可根据最近一条 `library`、`slug`、`url` 或 SVG 光栅化命令判断当前处理点。
- 模板素材目录成功生成。
- 若大模型返回的图标数量与本地切图数量不一致，当前会记录 warning 并继续以大模型结果落地；本地切图只作为参考和日志告警。
- 若本地切图完全没有切出候选图标，当前也只记录 warning，并继续直接采用大模型返回的 `icons` 结果，不再因此中断整张图片。

#### 常见误用

- 模型名写错或 Ollama 未启动。
- `--retry-from-report` 指向非同批次报告，导致重试结果混乱。

### 4.3 `materials collect-backgrounds`

#### 用途

使用本地 Ollama 多模态模型直接分析参考文件夹中的原始背景图片风格，忽略图标、缺口、滑块、文字和点击目标等前景信息，再用生成的英文搜索词从 Pexels 下载风格类似的背景图。

当前正式主线不强依赖自动前景修补或 inpaint。若参考图里带有验证码干扰元素，命令会直接把原图送给多模态模型，并通过提示词要求模型只关注背景风格。
同一 `--output-root` 下重跑时，命令会自动复用已完成的逐图分析结果和已保存的下载任务状态。
当前下载策略不是“只按汇总搜索词找图”，而是“每张参考图至少 1 个保底下载任务，再叠加汇总扩充任务”。

#### 适用场景

- 已有一小批真实业务背景，需要扩充相似背景素材。
- 背景上混有验证码前景元素，但只想学习背景场景、色彩和纹理风格。

#### 语法

```bash
uv run sinan materials collect-backgrounds \
  --source-dir <reference-background-dir> \
  --model <ollama-model> \
  [--output-root <dir>] \
  [--ollama-url <url>] \
  [--timeout-seconds <int>] \
  [--sample-limit <int>] \
  [--max-queries <int>] \
  [--per-query <int>] \
  [--limit <int>] \
  [--orientation landscape|portrait|square] \
  [--min-width <int>] \
  [--min-height <int>] \
  [--max-hamming-distance <int>] \
  [--merge-into <materials-root>] \
  [--api-key-env PEXELS_API_KEY] \
  [--dry-run] \
  [--quiet]
```

#### 关键参数

| 参数 | 说明 |
| --- | --- |
| `--source-dir` | 必填，参考背景图片目录。 |
| `--model` | 必填，本地 Ollama 多模态模型名。 |
| `--output-root` | 默认 `work_home/materials/incoming`。下载图片写到 `output-root/backgrounds/`。 |
| `--sample-limit` | 默认不限制。只在你显式传入时才限制参考图分析数量。 |
| `--max-queries` | 默认 `5`，大模型输出的英文搜索词上限。 |
| `--per-query` | 默认 `8`，每个搜索词最多下载的图片数。 |
| `--limit` | 全局下载上限。 |
| `--min-width` | 默认 `256`。下载图片的最小宽度；小于阈值会被跳过。 |
| `--min-height` | 默认 `128`。下载图片的最小高度；小于阈值会被跳过。 |
| `--max-hamming-distance` | 默认 `0`。重复抑制阈值；`0` 只做保守重复检测。 |
| `--merge-into` | 可选。把通过质量门的新背景图增量并入指定正式素材根的 `backgrounds/` 与 `manifests/backgrounds.csv`。 |
| `--api-key-env` | 默认 `PEXELS_API_KEY`，用于读取 Pexels API key。 |
| `--dry-run` | 只分析风格和输出搜索词，不访问 Pexels、不下载图片。 |

#### 断点续传与状态文件

- `output-root/reports/background-style-image-analysis.jsonl`：逐张参考图的分析结果。已成功分析的图片下次会按 `image_path + image_sha256` 复用。
- `output-root/reports/background-style-summary.json`：根据逐图分析结果汇总出来的最终背景风格画像和搜索词。
- `output-root/reports/background-style-download-state.json`：下载任务状态，记录 `reference_image` 保底任务和 `summary` 扩充任务的来源、目标数量、已下载数量、已拒绝数量和下一页游标。
- 若命令在下载阶段中断，只要重用同一 `--output-root` 重跑，就会从上次保存的任务状态继续，而不是从第一页重新开始。

#### 最小示例

```bash
$env:PEXELS_API_KEY = "<your-pexels-api-key>"
uv run sinan materials collect-backgrounds \
  --source-dir work_home/materials/validation/backgrounds \
  --model qwen2.5vl:7b \
  --limit 30
```

#### 成功标志

- `output-root/backgrounds/` 下生成下载的背景图。
- `output-root/manifests/materials.yaml` 会补齐素材根 schema 标记。
- `output-root/manifests/backgrounds.csv` 记录来源、搜索词、作者和文件名。
- 若未设置更小的全局 `--limit`，系统会优先保证每张参考图至少下载 1 张通过质量门的背景图。
- `output-root/reports/background-style-image-analysis.jsonl` 记录逐图分析 checkpoint。
- `output-root/reports/background-style-summary.json` 记录汇总后的背景风格画像和搜索词。
- `output-root/reports/background-style-download-state.json` 记录下载任务流状态。
- `output-root/reports/background-style-collection.json` 记录复用计数、下载任务统计、下载成功项、跳过原因和正式合并结果。
- 若指定 `--merge-into`，目标素材根的 `backgrounds/` 与 `manifests/backgrounds.csv` 会增量更新，且不会改写已有 `group1/group2` manifest。

### 4.4 `dataset validate`

#### 用途

验证 `labels.jsonl` 等 JSONL 数据集文件是否符合当前合同。

#### 适用场景

- 导出后、训练前做门禁校验。
- 回灌 reviewed 数据前做结构确认。

#### 语法

```bash
uv run sinan dataset validate --path <jsonl>
```

#### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--path` | 是 | 无 | 待验证 JSONL 文件路径。 |

#### 最小示例

```bash
uv run sinan dataset validate --path work_home/datasets/group1/v1/eval/labels.jsonl
```

#### 成功标志

- 返回码 `0`，且无合同错误。

#### 常见误用

- 校验了错误版本的数据文件，误以为当前数据集可训练。

## 5. 试卷命令（`exam`）

### 5.1 `exam prepare`

#### 用途

把原始素材复制到稳定 reviewed 目录，供人工标注或复核。

#### 适用场景

- 新一轮业务试卷准备。
- X-AnyLabeling 人工审核前。

#### 语法

```bash
uv run sinan exam prepare --task group1|group2 [--materials-root <dir>] --output-dir <dir>
```

#### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--task` | 是 | 无 | 任务类型：`group1` 或 `group2`。 |
| `--materials-root` | 否 | 程序默认 materials 目录 | 原始素材根目录。 |
| `--output-dir` | 是 | 无 | reviewed 输出目录。 |

#### 最小示例

```bash
uv run sinan exam prepare --task group1 --materials-root work_home/materials --output-dir work_home/materials/business_exams/group1/reviewed-v1
```

#### 成功标志

- 命令返回 JSON，`status=ok`。
- `output-dir` 下存在可复核目录结构（`import/`、`manifest` 等）。

#### 常见误用

- 把生成器工作区路径当 `--materials-root` 传入，导致找不到业务试卷素材。
- `--task` 与素材目录内容不匹配（例如 `group1` 命令读到 `result/` 结构）。

### 5.2 `exam export-reviewed`

#### 用途

把人工 reviewed 标注导出为训练/评估可消费的 `labels.jsonl`。

#### 适用场景

- 人工复核完成后回灌数据前。

#### 语法

```bash
uv run sinan exam export-reviewed --task group1|group2 --exam-root <dir>
```

#### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--task` | 是 | 无 | 任务类型。 |
| `--exam-root` | 是 | 无 | reviewed 试卷根目录。 |

#### 最小示例

```bash
uv run sinan exam export-reviewed --task group1 --exam-root work_home/materials/business_exams/group1/reviewed-v1
```

#### 成功标志

- 命令返回 JSON，包含导出数量统计。
- `exam-root` 内生成或更新 `labels.jsonl`（按任务合同输出）。

#### 常见误用

- 在“未完成人工复核”的目录直接导出，导致标签质量不可控。
- `--exam-root` 指到 prepare 产物但没有标注结果，导出为空。

### 5.3 `exam build-group2-prelabel-yolo`

#### 用途

从 group2 试卷源目录构建单图 YOLO 预标注数据集。

#### 适用场景

- 准备 group2 的检测式预标注流程。

#### 语法

```bash
uv run sinan exam build-group2-prelabel-yolo --source-dir <dir> --output-dir <dir>
```

#### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--source-dir` | 是 | 无 | 输入试卷源目录。 |
| `--output-dir` | 是 | 无 | 输出 YOLO 数据集目录。 |

#### 最小示例

```bash
uv run sinan exam build-group2-prelabel-yolo --source-dir work_home/materials/business_exams/group2/reviewed-v1 --output-dir work_home/materials/business_exams/group2/prelabel-yolo-v1
```

#### 成功标志

- 命令返回 JSON，包含样本统计。
- `output-dir` 下生成可直接用于检测预标注的 YOLO 目录结构。

#### 常见误用

- `source-dir` 传入 group1 数据，导致字段不兼容。
- 输出目录复用旧版本但未隔离，覆盖后难以追溯。

## 6. 自动标注命令（`autolabel`）

### 用途

执行离线自动标注转换流程。

### 适用场景

- 需要快速生成可人工复核的初始标签。
- 需要基于规则做轻量扰动生成。

### 语法

```bash
uv run sinan autolabel \
  --task group1|group2 \
  --mode <mode> \
  --input-dir <dir> \
  --output-dir <dir> \
  [--limit <int>] \
  [--jitter-pixels <int>]
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--task` | 是 | 无 | `group1` 或 `group2`。 |
| `--mode` | 是 | 无 | 标注模式（见下表）。 |
| `--input-dir` | 是 | 无 | 输入目录，需包含 `labels.jsonl` 与图片。 |
| `--output-dir` | 是 | 无 | 输出目录。 |
| `--limit` | 否 | 空 | 限制处理样本数。 |
| `--jitter-pixels` | 否 | `4` | bbox 抖动强度。 |

模式说明（当前实现）：

| task | 可用 mode | 含义 |
| --- | --- | --- |
| `group1` | `seed-review` | 保留人工语义，标记为 reviewed。 |
| `group1` | `warmup-auto` | 对目标与干扰项做规则扰动，标记为 auto。 |
| `group2` | `rule-auto` | 对目标框做规则扰动，标记为 auto。 |

### 最小示例

```bash
uv run sinan autolabel --task group1 --mode warmup-auto --input-dir work_home/materials/business_exams/group1/reviewed-v1 --output-dir work_home/materials/business_exams/group1/autolabel-v1 --limit 200
```

### 成功标志

- 命令返回 JSON，包含输入/输出统计。
- `output-dir` 下生成可人工复核的标注文件与配套资源。

### 常见误用

- `task` 与 `mode` 组合不合法（例如 `group2 + seed-review`）。
- 输入目录缺 `labels.jsonl` 或图片资源不完整。

## 7. 训练命令（`train group1`）

### 7.1 主训练命令

#### 用途

训练 `group1` 组件链（`proposal-detector/icon-embedder`）。

#### 适用场景

- 从零训练新版本。
- 从历史 run 续训或迁移训练。

#### 语法

```bash
uv run sinan train group1 \
  [--dataset-config <path>] \
  [--dataset-version <name>] \
  [--project <dir>] \
  [--name <run-name>] \
  [--component all|proposal-detector|icon-embedder] \
  [--model <model>] \
  [--proposal-model <path-or-name>] \
  [--embedder-model <path>] \
  [--from-run <run-name>] \
  [--resume] \
  [--epochs <int>] \
  [--batch <int>] \
  [--imgsz <int>] \
  [--device <device>] \
  [--dry-run]
```

#### 关键参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--dataset-version` | `v1` | 训练数据版本。 |
| `--name` | `v1` | 本次训练 run 名。 |
| `--component` | `all` | 训练范围。 |
| `--imgsz` | `640` | 输入尺寸。 |
| `--device` | `0` | 训练设备。 |
| `--model` | `yolo26n.pt`（回退） | 共享基础模型。 |
| `--resume` | `false` | 从同名 run 的 last 权重续训。 |
| `--from-run` | 空 | 从历史 run best 权重迁移训练。 |

约束：

- `--resume` 与 `--from-run` 不能同时传。
- 传 `--from-run` 时不要再传 `--model/--proposal-model/--embedder-model`。

#### 最小示例

```bash
uv run sinan train group1 --dataset-version v1 --name firstpass --component all --epochs 100 --device 0
```

#### 成功标志

- `runs/group1/<name>/.../weights/` 下生成权重。
- 训练 summary 正常输出。

### 7.2 `train group1 prelabel`

#### 用途

对 reviewed 试卷做 group1 全链路预标注。

#### 适用场景

- 已有训练权重，想把 reviewed 试卷先自动出一版标注。
- 人工标注资源紧张时先生成可复核初稿。

#### 语法

```bash
uv run sinan train group1 prelabel \
  --exam-root <dir> \
  [--dataset-config <path>] \
  [--dataset-version <name>] \
  [--project <dir>] \
  [--train-name <run-name>] \
  [--proposal-model <path>] \
  [--embedder-model <path>] \
  [--name <predict-run-name>] \
  [--conf <float>] \
  [--imgsz <int>] \
  [--device <device>] \
  [--limit <int>] \
  [--overwrite] \
  [--dry-run]
```

#### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--exam-root` | 是 | 无 | reviewed 试卷目录。 |
| `--dataset-config` | 否 | 由 `dataset-version` 推导 | 数据集配置路径。 |
| `--dataset-version` | 否 | `v1` | 数据集版本。 |
| `--project` | 否 | `<exam-root>/.sinan/prelabel/group1/predict` | 预测输出目录。 |
| `--train-name` | 否 | `v1` | 权重来源 run 名。 |
| `--proposal-model` | 否 | 从 `train-name` 推导 | proposal 模型覆盖。 |
| `--embedder-model` | 否 | 视配置自动推导 | embedder 模型覆盖。 |
| `--name` | 否 | `prelabel` | 预测 run 名。 |
| `--conf` | 否 | `0.25` | 预测阈值。 |
| `--imgsz` | 否 | `640` | 预测输入尺寸。 |
| `--device` | 否 | `0` | 推理设备。 |
| `--limit` | 否 | 空 | 限制样本数。 |
| `--overwrite` | 否 | `false` | 覆盖已有输出。 |
| `--dry-run` | 否 | `false` | 仅打印执行计划。 |

#### 最小示例

```bash
uv run sinan train group1 prelabel --exam-root work_home/materials/business_exams/group1/reviewed-v1 --dataset-version firstpass --train-name firstpass --limit 200
```

#### 成功标志

- 命令输出 JSON 结果，包含成功样本统计。
- 目标目录生成可在 X-AnyLabeling 继续复核的产物。

#### 常见误用

- `--train-name` 指向不存在 run，导致无法自动定位模型。
- 未传 `--overwrite` 重跑同一目录，结果看似“无新增”。

### 7.3 `train group1 prelabel-query-dir`

#### 用途

仅针对 query 图目录做预标注（不需要 query-scene 成对输入）。

#### 适用场景

- 只需要维护 query 图标语义，不涉及背景图匹配。
- 快速构建 query 标注初稿供人工修订。
- 希望直接使用内置规则式 query splitter，而不是依赖单独模型。

#### 语法

```bash
uv run sinan train group1 prelabel-query-dir \
  --input-dir <dir> \
  [--project <dir>] \
  [--name <predict-run-name>] \
  [--limit <int>] \
  [--overwrite] \
  [--dry-run]
```

#### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--input-dir` | 是 | 无 | query 图片目录。 |
| `--project` | 否 | `<input-dir>/.sinan/prelabel/group1/query` | 输出目录。 |
| `--name` | 否 | `prelabel-query` | 预测 run 名。 |
| `--limit` | 否 | 空 | 限制样本数。 |
| `--overwrite` | 否 | `false` | 覆盖已有结果。 |
| `--dry-run` | 否 | `false` | 仅输出执行计划。 |

#### 最小示例

```bash
uv run sinan train group1 prelabel-query-dir --input-dir work_home/query_pool --limit 300
```

#### 成功标志

- 生成 query 目录对应的预标注结果文件。
- 命令输出统计与执行摘要。

#### 常见误用

- 把 mixed 目录传给 `--input-dir`（含非 query 图），导致规则切分结果噪声高。
- 未先人工抽检规则切分结果，就直接大批量导入审核流程。

### 7.4 `train group1 prelabel-vlm`

#### 用途

用本地 Ollama 多模态模型直接预标注 query/scene 图片对。

#### 适用场景

- 尚无可用训练权重时做冷启动预标。
- 想快速比较“模型预标”和“规则预标”质量。

#### 语法

```bash
uv run sinan train group1 prelabel-vlm \
  --pair-root <dir> \
  --model <ollama-model> \
  [--project <dir>] \
  [--ollama-url <url>] \
  [--timeout-seconds <int>] \
  [--limit <int>] \
  [--overwrite] \
  [--dry-run]
```

#### 参数说明

| 参数                  | 必填  | 默认值                                      | 说明                 |
| ------------------- | --- | ---------------------------------------- | ------------------ |
| `--pair-root`       | 是   | 无                                        | query/scene 成对目录根。 |
| `--model`           | 是   | 无                                        | Ollama 多模态模型名。     |
| `--project`         | 否   | `<pair-root>/.sinan/prelabel/group1/vlm` | 统一输出目录，包含 `reviewed/`、`labels.jsonl`、`trace.jsonl`、`summary.json`。 |
| `--ollama-url`      | 否   | `http://127.0.0.1:11434`                 | Ollama 服务地址。       |
| `--timeout-seconds` | 否   | `300`                                    | 单请求超时时间。           |
| `--limit`           | 否   | 空                                        | 限制样本数。             |
| `--overwrite`       | 否   | `false`                                  | 覆盖已有结果。            |
| `--dry-run`         | 否   | `false`                                  | 仅打印计划。             |

#### 最小示例

```bash
uv run sinan train group1 prelabel-vlm --pair-root work_home/group1_pairs --model qwen2.5vl:7b --limit 50
```

#### 成功标志

- 命令输出 JSON，包含处理数量与写入路径。
- `--project` 目录下生成 `reviewed/query/*.json`、`reviewed/scene/*.json`、`labels.jsonl`、`trace.jsonl` 和 `summary.json`。

#### 常见误用

- `--model` 填写本机不存在模型，调用失败。
- `--pair-root` 目录命名不规范，query/scene 无法配对。

## 8. 训练命令（`train group2`）

### 8.1 主训练命令

#### 用途

训练 `group2` paired 输入模型。

#### 适用场景

- 训练拖拽任务主模型。
- 从历史 run 快速迁移或续训。

#### 语法

```bash
uv run sinan train group2 \
  [--dataset-config <path>] \
  [--dataset-version <name>] \
  [--project <dir>] \
  [--name <run-name>] \
  [--model <path-or-name>] \
  [--from-run <run-name>] \
  [--resume] \
  [--epochs <int>] \
  [--batch <int>] \
  [--imgsz <int>] \
  [--device <device>] \
  [--dry-run]
```

#### 参数说明

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--dataset-version` | `v1` | 训练数据版本。 |
| `--name` | `v1` | 本次 run 名。 |
| `--project` | `<repo>/work_home/runs/group2` | 训练输出目录。 |
| `--model` | `paired_cnn_v1`（回退） | 初始化模型或权重。 |
| `--from-run` | 空 | 从历史 run best 权重迁移。 |
| `--resume` | `false` | 从同名 run last 权重续训。 |
| `--epochs` | 空 | 覆盖轮次。 |
| `--batch` | 空 | 覆盖 batch。 |
| `--imgsz` | `192` | 输入尺寸。 |
| `--device` | `0` | 训练设备。 |
| `--dry-run` | `false` | 仅打印命令。 |

约束：

- `--resume` 与 `--from-run` 不能同时传。
- 传 `--from-run` 时不要再传 `--model`。

#### 最小示例

```bash
uv run sinan train group2 --dataset-version firstpass --name firstpass --epochs 120 --device 0
```

#### 成功标志

- `runs/group2/<name>/weights/` 下生成模型权重。
- 训练日志正常结束并输出指标。

#### 常见误用

- `imgsz` 改成非预期尺寸但未同步评估口径，导致对比失真。
- `--resume` 续训时忘记确认同名 run 内容，造成误续训。

### 8.2 `train group2 prelabel`

#### 用途

对 group2 reviewed 试卷执行预标注。

#### 适用场景

- group2 人工标注前先批量生成初稿。

#### 语法

```bash
uv run sinan train group2 prelabel \
  --exam-root <dir> \
  [--dataset-config <path>] \
  [--dataset-version <name>] \
  [--project <dir>] \
  [--train-name <run-name>] \
  [--model <path>] \
  [--name <predict-run-name>] \
  [--imgsz <int>] \
  [--device <device>] \
  [--limit <int>] \
  [--overwrite] \
  [--dry-run]
```

#### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--exam-root` | 是 | 无 | reviewed 试卷目录。 |
| `--dataset-config` | 否 | 由 `dataset-version` 推导 | 数据集配置路径。 |
| `--dataset-version` | 否 | `v1` | 数据集版本。 |
| `--project` | 否 | `<exam-root>/.sinan/prelabel/group2/predict` | 输出目录。 |
| `--train-name` | 否 | `v1` | 模型来源 run。 |
| `--model` | 否 | 从 `train-name` 推导 | 显式模型路径。 |
| `--name` | 否 | `prelabel` | 预测 run 名。 |
| `--imgsz` | 否 | `192` | 输入尺寸。 |
| `--device` | 否 | `0` | 推理设备。 |
| `--limit` | 否 | 空 | 限制样本数。 |
| `--overwrite` | 否 | `false` | 覆盖已有结果。 |
| `--dry-run` | 否 | `false` | 仅打印执行计划。 |

#### 最小示例

```bash
uv run sinan train group2 prelabel --exam-root work_home/materials/business_exams/group2/reviewed-v1 --train-name firstpass --limit 200
```

#### 成功标志

- 输出 JSON 汇总，包含已处理样本数。
- 输出目录中生成可继续复核的预标注文件。

#### 常见误用

- `--train-name` 对应权重不存在，无法自动定位模型。
- 输入目录与 `dataset-config` 版本不一致，导致字段兼容问题。

## 9. 预测命令（`predict`）

### 9.1 `predict group1`

#### 用途

在 `group1` 数据源上运行预测并输出预测结果目录。

#### 适用场景

- 训练完成后快速抽检模型效果。
- 作为 `test group1` 之前的单步排查入口。

#### 语法

```bash
uv run sinan predict group1 \
  [--dataset-config <path>] \
  [--proposal-model <path>] \
  [--query-model <path>] \
  [--embedder-model <path>] \
  [--train-name <run-name>] \
  [--source <jsonl>] \
  [--dataset-version <name>] \
  [--project <dir>] \
  [--name <predict-run-name>] \
  [--conf <float>] \
  [--device <device>] \
  [--imgsz <int>] \
  [--dry-run]
```

#### 参数说明

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--dataset-config` | 由 `dataset-version` 推导 | 数据集配置路径。 |
| `--proposal-model` | 从 `train-name` 推导 | proposal 模型路径。 |
| `--query-model` | 从 `train-name` 推导 | query 模型路径。 |
| `--embedder-model` | 从 `train-name` 推导 | embedder 模型路径。 |
| `--train-name` | `v1` | 权重来源 run。 |
| `--source` | 由 `dataset-version` 推导 | 预测输入 JSONL。 |
| `--dataset-version` | `v1` | 数据集版本。 |
| `--project` | `<repo>/work_home/reports/group1` | 预测输出根目录。 |
| `--name` | `predict_<train-name>` | 预测任务名。 |
| `--conf` | `0.25` | 预测阈值。 |
| `--device` | `0` | 推理设备。 |
| `--imgsz` | `640` | 输入尺寸。 |
| `--dry-run` | `false` | 仅打印底层命令。 |

#### 最小示例

```bash
uv run sinan predict group1 --dataset-version firstpass --train-name firstpass --name predict_firstpass
```

#### 成功标志

- 预测目录生成 `labels.jsonl` 等输出文件。
- 命令返回码为 `0`。

#### 常见误用

- 只替换 `--train-name` 没替换 `--dataset-version`，导致验证集来源错位。
- 手动传了旧模型路径覆盖默认推导，结果与 run 名不一致。

### 9.2 `predict group2`

#### 用途

在 `group2` 数据源上运行预测并输出预测结果目录。

#### 适用场景

- 快速验证 group2 模型在当前验证集的定位表现。
- 为后续 `evaluate` 准备 prediction 目录。

#### 语法

```bash
uv run sinan predict group2 \
  [--dataset-config <path>] \
  [--model <path>] \
  [--train-name <run-name>] \
  [--source <jsonl>] \
  [--dataset-version <name>] \
  [--project <dir>] \
  [--name <predict-run-name>] \
  [--conf <float>] \
  [--device <device>] \
  [--imgsz <int>] \
  [--dry-run]
```

#### 参数说明

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--dataset-config` | 由 `dataset-version` 推导 | 数据集配置路径。 |
| `--model` | 从 `train-name` 推导 | 模型路径。 |
| `--train-name` | `v1` | 权重来源 run。 |
| `--source` | 由 `dataset-version` 推导 | 预测输入 JSONL。 |
| `--dataset-version` | `v1` | 数据集版本。 |
| `--project` | `<repo>/work_home/reports/group2` | 预测输出根目录。 |
| `--name` | `predict_<train-name>` | 预测任务名。 |
| `--conf` | `0.25` | 保留参数（group2 兼容位）。 |
| `--device` | `0` | 推理设备。 |
| `--imgsz` | `192` | 输入尺寸。 |
| `--dry-run` | `false` | 仅打印底层命令。 |

#### 最小示例

```bash
uv run sinan predict group2 --dataset-version firstpass --train-name firstpass --name predict_firstpass
```

#### 成功标志

- 输出目录生成 prediction JSONL。
- 命令返回码 `0`。

#### 常见误用

- `--imgsz` 与训练尺寸偏差过大，导致定位指标漂移。
- `--model` 指向错误文件（例如非 group2 权重）。

## 10. 测试命令（`test`）

### 10.1 `test group1`

#### 用途

执行 `group1` 标准测试流程并输出测试报告。

#### 适用场景

- 训练后做一次“可交付前”完整验证。
- 对比两个 run 的业务表现差异。

#### 语法

```bash
uv run sinan test group1 \
  [--dataset-config <path>] \
  [--dataset-version <name>] \
  [--proposal-model <path>] \
  [--query-model <path>] \
  [--embedder-model <path>] \
  [--train-name <run-name>] \
  [--source <jsonl>] \
  [--project <dir>] \
  [--predict-name <name>] \
  [--val-name <name>] \
  [--report-dir <dir>] \
  [--conf <float>] \
  [--device <device>] \
  [--imgsz <int>] \
  [--dry-run]
```

#### 参数说明

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--dataset-config` | 由 `dataset-version` 推导 | 数据集配置路径。 |
| `--dataset-version` | `v1` | 数据集版本。 |
| `--proposal-model` | 从 `train-name` 推导 | proposal 模型路径。 |
| `--query-model` | 从 `train-name` 推导 | query 模型路径。 |
| `--embedder-model` | 从 `train-name` 推导 | embedder 模型路径。 |
| `--train-name` | `v1` | 待测 run 名。 |
| `--source` | 由 `dataset-version` 推导 | 测试输入 JSONL。 |
| `--project` | `<repo>/work_home/reports/group1` | 预测/评估基目录。 |
| `--predict-name` | `predict_<train-name>` | 预测阶段任务名。 |
| `--val-name` | `val_<train-name>` | 评估阶段任务名。 |
| `--report-dir` | `<project>/test_<train-name>` | 中文报告输出目录。 |
| `--conf` | `0.25` | 预测阈值。 |
| `--device` | `0` | 推理设备。 |
| `--imgsz` | `640` | 输入尺寸。 |
| `--dry-run` | `false` | 仅打印 predict/evaluate 命令。 |

#### 最小示例

```bash
uv run sinan test group1 --dataset-version firstpass --train-name firstpass --report-dir work_home/reports/group1/test_firstpass
```

#### 成功标志

- `report-dir` 内生成测试报告。
- 终端输出可读中文总结。

#### 常见误用

- 手工传了 `--predict-name` 但 `--report-dir` 仍沿用旧目录，覆盖历史报告。
- 只看总分，不检查 `missing/ambiguous` 等业务关键字段。

### 10.2 `test group2`

#### 用途

执行 `group2` 标准测试流程并输出测试报告。

#### 适用场景

- 训练回归验证与版本准入门禁。
- 评估不同训练策略在定位指标上的差异。

#### 语法

```bash
uv run sinan test group2 \
  [--dataset-config <path>] \
  [--dataset-version <name>] \
  [--model <path>] \
  [--train-name <run-name>] \
  [--source <jsonl>] \
  [--project <dir>] \
  [--predict-name <name>] \
  [--val-name <name>] \
  [--report-dir <dir>] \
  [--conf <float>] \
  [--device <device>] \
  [--imgsz <int>] \
  [--dry-run]
```

#### 参数说明

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--dataset-config` | 由 `dataset-version` 推导 | 数据集配置路径。 |
| `--dataset-version` | `v1` | 数据集版本。 |
| `--model` | 从 `train-name` 推导 | 待测模型路径。 |
| `--train-name` | `v1` | 待测 run 名。 |
| `--source` | 由 `dataset-version` 推导 | 测试输入 JSONL。 |
| `--project` | `<repo>/work_home/reports/group2` | 预测/评估基目录。 |
| `--predict-name` | `predict_<train-name>` | 预测阶段任务名。 |
| `--val-name` | `val_<train-name>` | 评估阶段任务名。 |
| `--report-dir` | `<project>/test_<train-name>` | 中文报告输出目录。 |
| `--conf` | `0.25` | 保留参数（group2 兼容位）。 |
| `--device` | `0` | 推理设备。 |
| `--imgsz` | `640` | 默认测试尺寸。 |
| `--dry-run` | `false` | 仅打印底层命令。 |

#### 最小示例

```bash
uv run sinan test group2 --dataset-version firstpass --train-name firstpass --report-dir work_home/reports/group2/test_firstpass
```

#### 成功标志

- 输出目录生成评估报告与摘要。
- 命令退出码为 `0`。

#### 常见误用

- 用 train 产物目录当 `report-dir`，把训练文件和测试文件混在一起。
- 没有固定 `--source`，导致跨批次数据比较失真。

## 11. 评估命令（`evaluate`）

### 用途

对比 gold 与 prediction 目录，计算任务指标并写报告。

### 适用场景

- 测试后统一计算指标。
- 回归对比不同 run 的性能变化。

### 语法

```bash
uv run sinan evaluate \
  --task group1|group2 \
  --gold-dir <dir> \
  --prediction-dir <dir> \
  --report-dir <dir> \
  [--point-tolerance-px <int>] \
  [--iou-threshold <float>]
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--task` | 是 | 无 | 任务类型。 |
| `--gold-dir` | 是 | 无 | 金标准目录。 |
| `--prediction-dir` | 是 | 无 | 预测结果目录。 |
| `--report-dir` | 是 | 无 | 评估报告输出目录。 |
| `--point-tolerance-px` | 否 | `12` | 点位容差。 |
| `--iou-threshold` | 否 | `0.5` | IoU 阈值。 |

### 最小示例

```bash
uv run sinan evaluate --task group1 --gold-dir work_home/eval/gold --prediction-dir work_home/eval/pred --report-dir work_home/eval/report
```

### 成功标志

- 输出目录写入评估 JSON/摘要。
- 命令返回码为 `0`。

### 常见误用

- `gold` 与 `prediction` 不同批次，导致结果无参考价值。
- group1 仍沿用 group2 的容差参数，指标解释偏差。

## 12. 自动训练命令（`auto-train`）

### 12.1 `auto-train run`

#### 用途

创建或恢复一个 study，并连续执行多个 stage。

#### 适用场景

- 需要无人值守跑完整闭环。
- 需要在约束预算内自动迭代训练方案。

#### 语法

```bash
uv run sinan auto-train run {group1|group2} --study-name <name> --train-root <dir> --generator-workspace <dir> [options]
```

#### 成功标志

- 输出包含 `final_stage`、`study_status`。
- 对应 `studies/<task>/<study-name>/` 下生成完整 trial 记录。

#### 常见误用

- `--max-trials` 太小但目标阈值过高，导致自动流程过早停止。
- 在不同目录反复执行同名 study，状态链断裂。

### 12.2 `auto-train stage`

#### 用途

只执行单个 stage，用于调试和问题定位。

#### 适用场景

- 某阶段持续失败，需要单步重放。
- 调整策略后只验证特定 stage 逻辑。

#### 语法

```bash
uv run sinan auto-train stage <stage> {group1|group2} --study-name <name> --train-root <dir> --generator-workspace <dir> [options]
```

#### 成功标志

- 终端输出 `stage -> next_stage [trial_id]`。
- 对应 stage 记录写入 study 目录。

#### 常见误用

- 复跑 `stage` 时更换 `study-name`，导致状态与上次执行无法衔接。

### 12.3 `stage` 可选值

`<stage>` 可传：

- `plan`
- `build-dataset`
- `train`
- `test`
- `evaluate`
- `summarize`
- `judge`
- `next-action`
- `stop`

### 12.4 `run/stage` 共享参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--study-name` | 无 | study 名（必填）。 |
| `--studies-root` | `studies` | study 存储根目录。 |
| `--train-root` | 无 | 训练目录（必填）。 |
| `--generator-workspace` | 无 | 生成器工作区（必填）。 |
| `--generator-executable` | `sinan-generator(.exe)` | 生成器可执行命令。 |
| `--mode` | `full_auto` | `full_auto` / `review_auto`。 |
| `--judge-provider` | `rules` | judge provider。 |
| `--judge-model` | `policy-v1` | judge model 名。 |
| `--opencode-attach-url` | 空 | OpenCode attach URL。 |
| `--opencode-binary` | `opencode` | OpenCode 可执行命令。 |
| `--opencode-timeout-seconds` | `300.0` | OpenCode 调用超时。 |
| `--max-trials` | `20` | 最大 trial 数。 |
| `--max-hours` | `24.0` | 最大运行小时数。 |
| `--max-new-datasets` | 空 | 最多新建数据集次数。 |
| `--max-no-improve-trials` | `4` | 连续无提升 trial 限制。 |
| `--dataset-version` | `v1` | 训练数据版本。 |
| `--train-name` | 空 | 显式训练名。 |
| `--train-mode` | `fresh` | `fresh` / `resume` / `from_run`。 |
| `--base-run` | 空 | `from_run` 源 run。 |
| `--model` | 空 | 显式模型。 |
| `--epochs` | 空 | 覆盖训练轮次。 |
| `--batch` | 空 | 覆盖 batch。 |
| `--imgsz` | 空 | 覆盖输入尺寸。 |
| `--device` | `0` | 训练/推理设备。 |
| `--gold-dir` | 空 | 评估金标准目录。 |
| `--prediction-dir` | 空 | 预测结果目录。 |
| `--point-tolerance-px` | `5` | 自动训练评估点容差。 |
| `--iou-threshold` | `0.5` | 自动训练评估 IoU 阈值。 |
| `--business-eval-dir` | 空 | 商业评估样本目录。 |
| `--business-eval-success-threshold` | `0.90` | 商业评估通过阈值。 |
| `--business-eval-min-cases` | `50` | 商业评估最小样本数。 |
| `--business-eval-sample-size` | `50` | 单次商业抽样数。 |
| `--goal-only-stop` | `false` | 只在达到目标或命中停止条件时停机。 |

`run` 独有参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--max-steps` | 空 | 单次运行最大阶段步数；空值由 `goal_only_stop` 推导。 |

### 12.5 最小示例

```bash
uv run sinan auto-train run group1 --study-name study_001 --train-root D:\sinan-captcha-work --generator-workspace D:\sinan-generator\workspace --max-trials 5
```

## 13. Solver 命令（`solve`）

### 用途

训练产物交付前的本地 solver 验收入口。

### 适用场景

- 构建可迁移 bundle。
- 发布前校验 bundle 结构。
- 用请求 JSON 做本地 smoke 验证。

### 子命令

- `solve build-bundle`
- `solve validate-bundle`
- `solve run`

### 最小示例

```bash
uv run sinan solve build-bundle --bundle-dir work_home/bundles/solver/current --group1-run firstpass --group2-run firstpass --force
uv run sinan solve validate-bundle --bundle-dir work_home/bundles/solver/current
uv run sinan solve run --bundle-dir work_home/bundles/solver/current --request work_home/requests/group2_req.json --output work_home/requests/group2_resp.json
```

### 详细参考

这部分有完整请求/响应合同、参数表和错误码，请读：
[训练者：Solver Bundle CLI 参考](./solver-bundle-cli-reference.md)

## 14. 常见误用总览

- 只看语法不看场景，导致把“预标注命令”当“正式训练命令”使用。
- `--dataset-version`、`--train-name` 混用，结果目录与预期不一致。
- `--resume` 与 `--from-run` 同时传，触发参数冲突。
- `auto-train stage` 调试时忘记传同一 `study-name`，导致状态不连续。
