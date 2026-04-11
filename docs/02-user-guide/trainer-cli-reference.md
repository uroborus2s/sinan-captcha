# 训练者：训练器 CLI 全量参考（`sinan`）

本页覆盖 `uv run sinan ...` 当前公开命令（源码基线：2026-04-11）。

## 1. 调用方式

仓库或训练目录内执行：

```bash
uv run sinan <command> ...
```

## 2. 命令树

```text
sinan
├── env check
├── env setup-train
├── materials build
├── materials audit-group1-query
├── dataset validate
├── exam
│   ├── prepare
│   ├── export-reviewed
│   └── build-group2-prelabel-yolo
├── autolabel
├── auto-train
│   ├── run {group1|group2}
│   └── stage <stage> {group1|group2}
├── evaluate
├── predict
│   ├── group1
│   └── group2
├── test
│   ├── group1
│   └── group2
├── train group1
│   ├── prelabel
│   ├── prelabel-query-dir
│   └── prelabel-vlm
├── train group2
│   └── prelabel
└── solve
    ├── build-bundle
    ├── validate-bundle
    └── run
```

## 3. 环境与初始化命令

### 3.1 `env check`

语法：

```bash
uv run sinan env check
```

用途：输出训练机环境 JSON（`uv/torch/cuda/ultralytics/nvidia-smi`）。

### 3.2 `env setup-train`

语法：

```bash
uv run sinan env setup-train \
  [--train-root <path>] \
  [--generator-root <path>] \
  [--package-spec <spec>] \
  [--torch-backend auto|cpu|cu118|cu126|cu128|cu130] \
  [--yes]
```

参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--train-root` | `<cwd>/sinan-captcha-work` | 训练目录路径。 |
| `--generator-root` | 空 | 推荐生成器目录，仅用于输出提示信息。 |
| `--package-spec` | `sinan-captcha[train]==<runtime-version>` | 训练目录安装包规格。 |
| `--torch-backend` | `auto` | PyTorch index 选择策略。 |
| `--yes` | `false` | 跳过交互确认。 |

## 4. 素材与数据命令

### 4.1 `materials build`

语法：

```bash
uv run sinan materials build --spec <toml> --output-root <dir> [--cache-dir <dir>]
```

参数：

| 参数 | 必填 | 默认值 |
| --- | --- | --- |
| `--spec` | 是 | 无 |
| `--output-root` | 是 | 无 |
| `--cache-dir` | 否 | `.cache/materials` |

### 4.2 `materials audit-group1-query`

语法：

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

关键参数说明：

| 参数 | 说明 |
| --- | --- |
| `--model` | 必填，本地 Ollama 多模态模型名（如 `gemma4:26b`）。 |
| `--timeout-seconds` | Ollama 单次请求超时，默认 `600`。该值同时作用于逐图识别和最终 template 汇总。 |
| `--retry-from-report` | 复用旧报告成功项，只重试失败图片。 |
| `--quiet` | 关闭逐图日志。 |
| `--yes` | 非交互环境接受默认路径。 |

### 4.3 `dataset validate`

语法：

```bash
uv run sinan dataset validate --path <jsonl>
```

## 5. 试卷处理命令（`exam`）

### 5.1 `exam prepare`

```bash
uv run sinan exam prepare --task group1|group2 [--materials-root <dir>] --output-dir <dir>
```

### 5.2 `exam export-reviewed`

```bash
uv run sinan exam export-reviewed --task group1|group2 --exam-root <dir>
```

### 5.3 `exam build-group2-prelabel-yolo`

```bash
uv run sinan exam build-group2-prelabel-yolo --source-dir <dir> --output-dir <dir>
```

## 6. 自动标注命令（`autolabel`）

语法：

```bash
uv run sinan autolabel \
  --task group1|group2 \
  --mode <mode> \
  --input-dir <dir> \
  --output-dir <dir> \
  [--limit <int>] \
  [--jitter-pixels <int>]
```

参数默认值：

- `--jitter-pixels`: `4`

## 7. 训练命令（`train group1`）

### 7.1 主训练命令

语法：

```bash
uv run sinan train group1 \
  [--dataset-config <path>] \
  [--dataset-version <name>] \
  [--project <dir>] \
  [--name <run-name>] \
  [--component all|proposal-detector|query-parser|icon-embedder] \
  [--model <model>] \
  [--proposal-model <path-or-name>] \
  [--query-model <path-or-name>] \
  [--embedder-model <path>] \
  [--from-run <run-name>] \
  [--resume] \
  [--epochs <int>] \
  [--batch <int>] \
  [--imgsz <int>] \
  [--device <device>] \
  [--dry-run]
```

默认值（关键）：

- `--dataset-version v1`
- `--name v1`
- `--component all`
- `--imgsz 640`
- `--device 0`
- `--model` 默认回退到 `yolo26n.pt`

约束：

- `--resume` 与 `--from-run` 不能同时传。
- 传 `--from-run` 时不要再同时传 `--model/--proposal-model/--query-model/--embedder-model`。

### 7.2 `train group1 prelabel`

```bash
uv run sinan train group1 prelabel \
  --exam-root <dir> \
  [--dataset-config <path>] \
  [--dataset-version <name>] \
  [--project <dir>] \
  [--train-name <run-name>] \
  [--proposal-model <path>] \
  [--query-model <path>] \
  [--embedder-model <path>] \
  [--name <predict-run-name>] \
  [--conf <float>] \
  [--imgsz <int>] \
  [--device <device>] \
  [--limit <int>] \
  [--overwrite] \
  [--dry-run]
```

### 7.3 `train group1 prelabel-query-dir`

```bash
uv run sinan train group1 prelabel-query-dir \
  --input-dir <dir> \
  [--project <dir>] \
  [--train-name <run-name>] \
  [--query-model <path>] \
  [--name <predict-run-name>] \
  [--conf <float>] \
  [--imgsz <int>] \
  [--device <device>] \
  [--limit <int>] \
  [--overwrite] \
  [--dry-run]
```

### 7.4 `train group1 prelabel-vlm`

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

默认值：

- `--ollama-url`: `http://127.0.0.1:11434`
- `--timeout-seconds`: `300`

## 8. 训练命令（`train group2`）

### 8.1 主训练命令

语法：

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

默认值（关键）：

- `--dataset-version v1`
- `--name v1`
- `--imgsz 192`
- `--device 0`
- `--model` 默认回退到 `paired_cnn_v1`

约束：

- `--resume` 与 `--from-run` 不能同时传。
- 传 `--from-run` 时不要再传 `--model`。

### 8.2 `train group2 prelabel`

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

## 9. 预测命令（`predict`）

### 9.1 `predict group1`

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

默认值：

- `--dataset-version v1`
- `--train-name v1`
- `--conf 0.25`
- `--imgsz 640`
- `--device 0`

### 9.2 `predict group2`

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

默认值：

- `--imgsz 192`
- 其余默认值同 `group1`（按任务路径展开）

## 10. 测试命令（`test`）

### 10.1 `test group1`

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

### 10.2 `test group2`

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

## 11. 评估命令（`evaluate`）

语法：

```bash
uv run sinan evaluate \
  --task group1|group2 \
  --gold-dir <dir> \
  --prediction-dir <dir> \
  --report-dir <dir> \
  [--point-tolerance-px <int>] \
  [--iou-threshold <float>]
```

默认值：

- `--point-tolerance-px 12`
- `--iou-threshold 0.5`

## 12. 自动训练命令（`auto-train`）

### 12.1 `auto-train run`

语法：

```bash
uv run sinan auto-train run {group1|group2} --study-name <name> --train-root <dir> --generator-workspace <dir> [options]
```

### 12.2 `auto-train stage`

语法：

```bash
uv run sinan auto-train stage <stage> {group1|group2} --study-name <name> --train-root <dir> --generator-workspace <dir> [options]
```

`<stage>` 可传：`plan|build-dataset|train|test|evaluate|summarize|judge|next-action|stop`（大小写与别名由控制器归一化）。

### 12.3 `run/stage` 共享参数

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
| `--goal-only-stop` | `false` | 只在达到目标或明确停止条件时停机。 |

`run` 独有参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--max-steps` | 空 | 单次运行最大阶段步数；空值会由 `goal_only_stop` 推导。 |

## 13. Solver 命令（`solve`）

`solve` 子命令包括：

- `build-bundle`
- `validate-bundle`
- `run`

由于该部分有独立的请求/响应合同说明，请阅读：
[训练者：Solver Bundle CLI 参考](./solver-bundle-cli-reference.md)
