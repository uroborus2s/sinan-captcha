# 训练者：完整训练操作指南

这份指南面向“从零开始到可交付”的训练者，覆盖：

- 训练环境初始化
- 生成器工作区与素材准备
- `group1` / `group2` 数据生成、训练、预测、测试、评估
- reviewed 试卷预标注
- 自动训练 `auto-train`
- 本地 solver bundle 组装与调用验证

## 1. 先确认你的目标

你至少要明确下面 3 件事：

1. 这次训练的任务范围：`group1`、`group2`，还是两者都做。
2. 输出目标是“训练验证”还是“交付 bundle”。
3. 训练目录与生成器目录是否固定在 Windows 盘符路径。

推荐目录约定：

```text
D:\
  sinan-captcha-work\         # 训练目录（datasets/runs/reports/studies）
  sinan-captcha-generator\    # 生成器目录（sinan-generator.exe）
    workspace\                # 生成器工作区（materials/presets/jobs/logs）
```

## 2. 初始化训练目录

在训练机执行：

```powershell
uvx --from sinan-captcha sinan env setup-train `
  --train-root D:\sinan-captcha-work `
  --generator-root D:\sinan-captcha-generator `
  --torch-backend auto `
  --yes
```

说明：

- `env setup-train` 会创建训练目录、写入 `.python-version` 和 `pyproject.toml`、执行 `uv sync`。
- 会自动铺入 `.opencode/commands` 与 `.opencode/skills`，供 `auto-train --judge-provider opencode` 使用。
- `--torch-backend auto` 会按 `nvidia-smi` 的 CUDA 版本自动选择 `cpu/cu118/cu126/cu128/cu130`。

然后执行环境自检：

```powershell
Set-Location D:\sinan-captcha-work
uv run sinan env check
```

通过标准（至少）：

- `torch_installed=true`
- 如果是 GPU 训练，建议 `torch_cuda_available=true`

## 3. 初始化生成器工作区并导入素材

先初始化工作区：

```powershell
Set-Location D:\sinan-captcha-generator
.\sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
```

导入本地素材包：

```powershell
.\sinan-generator.exe materials import `
  --workspace D:\sinan-captcha-generator\workspace `
  --from D:\materials-pack-v3
```

或从 zip / URL 拉取：

```powershell
.\sinan-generator.exe materials fetch `
  --workspace D:\sinan-captcha-generator\workspace `
  --source https://example.com/materials-pack.zip `
  --name official-pack-v1
```

如果素材包只包含单任务内容（例如只含 `group1`），导入时显式传 `--task group1` 或 `--task group2`。

### 3.1 为 `exam prepare` 预置训练目录素材

`sinan exam prepare` 默认读取训练目录下的 `materials/`，不是生成器工作区。

在进入第 7 节前，请确保训练目录至少包含：

```text
D:\sinan-captcha-work\materials\
  group1\   # group1 审卷原始素材（case/icon.jpg + bg.jpg）
  result\   # group2 审卷原始素材（case/bg.jpg + gap.jpg）
```

如果你前面把原始素材放在其他目录（例如素材归档目录、共享盘、历史数据盘），请先同步到训练目录再继续。例如：

```powershell
New-Item -ItemType Directory -Force D:\sinan-captcha-work\materials | Out-Null
Copy-Item <你的原始素材目录>\group1 D:\sinan-captcha-work\materials\group1 -Recurse -Force
Copy-Item <你的原始素材目录>\result D:\sinan-captcha-work\materials\result -Recurse -Force
```

`sinan exam prepare` 只读取训练目录 `materials/`，不会读取生成器工作区。

## 4. 生成训练数据

### 4.1 生成 `group1` 数据集

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --preset firstpass `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass `
  --force
```

### 4.2 生成 `group2` 数据集

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group2 `
  --preset firstpass `
  --dataset-dir D:\sinan-captcha-work\datasets\group2\firstpass `
  --force
```

### 4.3 你应该看到的关键产物

- `datasets/group1/<version>/dataset.json`
- `datasets/group2/<version>/dataset.json`
- `splits/val.jsonl`（预测/测试默认输入）

## 5. 手动训练主线

以下命令在训练目录执行：

```powershell
Set-Location D:\sinan-captcha-work
```

### 5.1 训练 `group1`

整链路（默认组件 `all`）：

```powershell
uv run sinan train group1 --dataset-version firstpass --name firstpass
```

分组件训练：

```powershell
uv run sinan train group1 --dataset-version firstpass --name g1_proposal --component proposal-detector
uv run sinan train group1 --dataset-version firstpass --name g1_embed --component icon-embedder
```

关键事实：

- `group1` 的 proposal detector 默认基模型是 `yolo26n.pt`。
- `embedder` 由 `--embedder-model` 单独指定，未指定时走组件默认策略。

### 5.2 训练 `group2`

```powershell
uv run sinan train group2 --dataset-version firstpass --name firstpass
```

关键事实：

- `group2` 默认模型是 `paired_cnn_v1`，不是 YOLO。
- 默认输入尺寸 `imgsz=192`。

### 5.3 续训与迁移训练

在同一 run 续训：

```powershell
uv run sinan train group1 --name firstpass --resume
uv run sinan train group2 --name firstpass --resume
```

从上一轮最佳权重开新 run：

```powershell
uv run sinan train group1 --dataset-version firstpass_v2 --name round2 --from-run firstpass
uv run sinan train group2 --dataset-version firstpass_v2 --name round2 --from-run firstpass
```

## 6. 预测、测试与评估

### 6.1 预测

```powershell
uv run sinan predict group1 --dataset-version firstpass --train-name firstpass
uv run sinan predict group2 --dataset-version firstpass --train-name firstpass
```

### 6.2 一键测试（predict + evaluate）

```powershell
uv run sinan test group1 --dataset-version firstpass --train-name firstpass
uv run sinan test group2 --dataset-version firstpass --train-name firstpass
```

### 6.3 仅评估 JSONL

```powershell
uv run sinan evaluate `
  --task group1 `
  --gold-dir D:\sinan-captcha-work\reports\group1\test_firstpass\_gold `
  --prediction-dir D:\sinan-captcha-work\reports\group1\predict_firstpass `
  --report-dir D:\sinan-captcha-work\reports\group1\eval_firstpass
```

`group2` 同理，把 `--task` 和目录切到 `group2`。

## 7. reviewed 试卷与预标注

### 7.1 准备试卷目录并导出 reviewed 标注

```powershell
uv run sinan exam prepare --task group1 --materials-root D:\sinan-captcha-work\materials --output-dir D:\sinan-captcha-work\materials\business_exams\group1\reviewed-v1
uv run sinan exam export-reviewed --task group1 --exam-root D:\sinan-captcha-work\materials\business_exams\group1\reviewed-v1
```

`group2` 同理，`--materials-root` 仍指向训练目录 `materials/`。

### 7.2 用已训练模型预标注 reviewed 试卷

```powershell
uv run sinan train group1 prelabel --exam-root D:\sinan-captcha-work\materials\business_exams\group1\reviewed-v1 --dataset-version firstpass --train-name firstpass
uv run sinan train group2 prelabel --exam-root D:\sinan-captcha-work\materials\business_exams\group2\reviewed-v1 --dataset-version firstpass --train-name firstpass
```

### 7.3 `group1` 查询图目录预标注

```powershell
uv run sinan train group1 prelabel-query-dir --input-dir D:\query-dir
```

关键事实：

- 当前这条命令使用内置规则式 query splitter，不依赖单独检测模型。

### 7.4 `group1` 本地 VLM 预标注

```powershell
uv run sinan train group1 prelabel-vlm `
  --pair-root D:\vlm-pairs `
  --model qwen2.5vl:7b `
  --ollama-url http://127.0.0.1:11434
```

## 8. 自动训练（`auto-train`）

建议顺序：先 `rules`，后 `opencode`。

### 8.1 `rules` 路线

```powershell
uv run sinan auto-train run group1 `
  --study-name study_group1_firstpass `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --judge-provider rules `
  --max-steps 8 `
  --max-hours 2 `
  --max-new-datasets 1
```

### 8.2 `opencode` 路线

先在训练目录启动：

```powershell
opencode serve --port 4096
```

再运行：

```powershell
uv run sinan auto-train run group1 `
  --study-name study_group1_llm `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --judge-provider opencode `
  --judge-model gemma4 `
  --opencode-attach-url http://127.0.0.1:4096 `
  --max-steps 8
```

## 9. 组装并验证本地 solver bundle

用已训练 run 构建 bundle：

```powershell
uv run sinan solve build-bundle `
  --bundle-dir D:\sinan-captcha-work\bundles\solver\current `
  --group1-run firstpass `
  --group2-run firstpass `
  --train-root D:\sinan-captcha-work `
  --force
```

校验 bundle：

```powershell
uv run sinan solve validate-bundle --bundle-dir D:\sinan-captcha-work\bundles\solver\current
```

运行单次请求：

```powershell
uv run sinan solve run `
  --bundle-dir D:\sinan-captcha-work\bundles\solver\current `
  --request D:\sinan-captcha-work\requests\group2_req.json `
  --output D:\sinan-captcha-work\requests\group2_resp.json
```

`solve run` 请求/响应合同见：
[训练者：Solver Bundle CLI 参考](./solver-bundle-cli-reference.md)

## 10. 完成判定（建议作为交付前 gate）

- `env check` 通过（训练环境可用）。
- 至少 1 轮 `group1` + `group2` 手动训练成功。
- `test group1` / `test group2` 均生成报告并达成业务阈值。
- 若要交付本地 bundle：`solve build-bundle` + `solve validate-bundle` + `solve run` 三步通过。
- 所有关键命令和参数沉淀到你的运行脚本或作业记录中，避免人工记忆执行。
