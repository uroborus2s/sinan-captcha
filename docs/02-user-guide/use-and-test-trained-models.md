# 训练完成后的模型使用与测试

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：训练执行者、交付使用者
- 负责人：Codex
- 最近更新：2026-04-04

## 0. 这份文档解决什么问题

这页回答四件事：

1. 训练完成后先看哪里
2. 怎么一条命令测试训练好的模型
3. 怎么看测试结果和效果
4. 怎么继续训练，把结果逐步推高

如果你还没开始训练，先回到：

- [Windows 快速开始](./windows-quickstart.md)
- [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)

## 1. 先找到训练结果

训练完成后，先确认这里已经有权重：

```text
D:\sinan-captcha-work\runs\group1\firstpass\weights\best.pt
D:\sinan-captcha-work\runs\group2\firstpass\weights\best.pt
```

如果没有 `best.pt`，先不要继续做模型测试。

同时建议确认训练目录里至少还有：

- `weights\last.pt`
- `results.csv`
- `args.yaml`

## 2. 第一次训练完成后，先看什么

如果你只是想先判断“这轮训练是不是基本有效”，按这个顺序看最快：

1. `weights\best.pt` 是否存在
2. `results.csv` 是否已生成
3. 先跑一次 `predict` 看检测框
4. 再跑一次 `val` 看指标

其中：

- `best.pt` 存在，说明训练流程至少完整跑过并保存了最佳权重
- `results.csv` 可用于横向比较不同实验
- `predict` 适合先做肉眼检查
- `val` 适合做版本比较和回归检查

## 3. 推荐的快速预测命令

如果你已经在训练目录里，例如：

```powershell
Set-Location D:\sinan-captcha-work
```

推荐直接用本项目封装好的命令，而不是手写很长的 `uv run yolo detect predict`：

### 3.1 `group1`

```powershell
uv run sinan predict group1 `
  --dataset-version firstpass `
  --train-name firstpass
```

### 3.2 `group2`

```powershell
uv run sinan predict group2 `
  --dataset-version firstpass `
  --train-name firstpass
```

这条命令会自动给底层预测入口补齐默认路径：

- `model` 默认指向 `runs\<task>\<train-name>\weights\best.pt`
- `group1` 的 `source` 默认指向 `datasets\<task>\<dataset-version>\yolo\images\val`
- `group2` 的 `source` 默认指向 `datasets\group2\<dataset-version>\splits\val.jsonl`
- `group2` 还会自动读取 `datasets\group2\<dataset-version>\dataset.json`
- `project` 默认指向 `reports\<task>`

如果你想先看它到底会执行什么原生命令，可以先加：

```powershell
uv run sinan predict group1 --dataset-version firstpass --train-name firstpass --dry-run
```

这一步只看三件事：

- 模型能加载
- 推理能跑完
- 输出图里能看到大致合理的框

## 4. 一条命令跑完整测试并生成中文报告

如果你不想分开跑 `predict` 和 `val`，直接用：

### 4.1 `group1`

```powershell
uv run sinan test group1 `
  --dataset-version firstpass `
  --train-name firstpass
```

### 4.2 `group2`

```powershell
uv run sinan test group2 `
  --dataset-version firstpass `
  --train-name firstpass
```

这条命令会顺序完成：

1. 检查 `best.pt` 和正式测试输入是否存在
2. 跑一次 `predict`
3. `group1` 跑一次 `val`；`group2` 跑一次 paired prediction 后再做 JSONL 对比评估
4. 直接在终端输出一份初学者可读的中文结论
5. 同时写出正式报告

默认输出位置：

```text
reports\group1\predict_firstpass\
reports\group1\val_firstpass\
reports\group1\test_firstpass\summary.md
reports\group1\test_firstpass\summary.json

reports\group2\predict_firstpass\
reports\group2\val_firstpass\
reports\group2\test_firstpass\summary.md
reports\group2\test_firstpass\summary.json
```

## 5. 怎么看测试结果和效果

推荐按这个顺序看：

1. 先看终端里的中文结论
2. 再打开 `summary.md`
3. 再打开 `predict_*` 目录里的图片做肉眼检查
4. `group1` 回看 `val_*` 目录里的 `results.csv`；`group2` 回看 `val_*` 目录里的 JSONL 评估摘要

### 5.1 中文报告里最重要的指标

- `group1`
  - 重点看 `Precision`、`Recall`、`mAP50`、`mAP50-95`
- `group2`
  - 重点看 `point_hit_rate`、`mean_center_error_px`、`mean_iou`、`mean_inference_ms`

### 5.2 初学者怎么先做粗判断

- `group1`
  - 继续沿用 `mAP50` 粗判断：`>= 0.85` 基本稳定，`0.70-0.85` 已有明显效果，`< 0.70` 先补数据质量。
- `group2`
  - `point_hit_rate >= 0.92` 且 `mean_iou >= 0.85`
    说明这轮双输入定位已经比较稳。
  - `point_hit_rate >= 0.80` 且 `mean_iou >= 0.70`
    说明已经有明显效果，优先补复杂背景和弱对比样本。
  - `point_hit_rate < 0.80`
    先查双输入样本契约、图案 mask 一致性和数据规模，不要只靠硬拉 `epochs`。

这只是入门级判断口径，不是最终业务验收线。

## 6. 什么时候还要继续跑 JSONL 对比评估

如果你的推理链路已经能输出与 `gold` 兼容的预测 `labels.jsonl`，继续用：

```powershell
uv run sinan evaluate `
  --task group1 `
  --gold-dir D:\sinan-captcha-work\datasets\group1\v1\reviewed\batch_0001 `
  --prediction-dir D:\sinan-captcha-work\reports\group1\pred_jsonl_v1 `
  --report-dir D:\sinan-captcha-work\reports\group1\eval_jsonl_v1
```

或：

```powershell
uv run sinan evaluate `
  --task group2 `
  --gold-dir D:\sinan-captcha-work\datasets\group2\v1\reviewed\batch_0001 `
  --prediction-dir D:\sinan-captcha-work\reports\group2\pred_jsonl_v1 `
  --report-dir D:\sinan-captcha-work\reports\group2\eval_jsonl_v1
```

它更适合做贴近任务契约的验收，例如：

- `group1` 的顺序命中率
- `group2` 的点位误差和 IoU

## 7. 如何调整参数，逐步把效果推高

初学者最容易犯的错，是一次改太多东西，最后不知道哪一个因素起作用了。

最稳的做法是：

1. 固定一版数据集和验证集
2. 每次只改一个因素
3. 每次都用新的训练名保存结果
4. 用 `uv run sinan test ...` 回归比较

推荐的调整顺序：

### 7.1 先解决“能不能稳定跑完”

- 显存不够：
  - 先把 `batch` 从 `16` 降到 `8`
  - 还不够再把 `imgsz` 从 `640` 降到 `512`
- 训练被意外打断：
  - 直接续跑，不要重头开始

示例：

```powershell
uv run sinan train group1 --name firstpass --resume
uv run sinan train group2 --name firstpass --resume
```

上面这两条会默认从当前训练版本的 `weights\last.pt` 继续跑。

### 7.2 再解决“模型是不是明显漏检”

如果报告里 `Recall` 明显低于 `Precision`，优先做这些事：

- 补更多目标样本
- 补复杂背景、边缘位置、遮挡和小目标样本
- 再小幅加 `epochs`

示例：

```powershell
uv run sinan train group1 `
  --dataset-version firstpass `
  --name firstpass_e160 `
  --epochs 160
```

### 7.3 再解决“模型是不是误检偏多”

如果 `Precision` 明显低于 `Recall`，优先做这些事：

- 清理错标和脏标
- 增加干扰项和负样本
- 不要第一反应就盲目加大模型

### 7.4 当基础已经稳定，再尝试更强模型

如果：

- 数据质量已经比较稳定
- `mAP50` 有提升但开始变慢
- 显存还有余量

可以试一轮更大的底模：

```powershell
uv run sinan train group1 `
  --dataset-version firstpass `
  --name firstpass_s `
  --model yolo26s.pt
```

## 8. 模型是梯次训练吗

可以把当前项目理解成“分阶段迭代训练”，但不是“无脑一直在同一个目录上叠加训练”。

### 8.1 第一次训练是不是从零开始

不是。

第一次正式训练默认就是在预训练权重基础上微调：

- `group1` 默认 `yolo26n.pt`
- `group2` 默认从内置的 paired-input 相关性定位器开始训练；如果指定 `--from-run`，则会从上一轮 `best.pt` 继续微调

也就是说，第一轮已经不是从零训练。

### 8.2 第二次训练一定要接着第一次的模型继续吗

不一定。

要分三种情况：

1. 只是训练中断了
   这种情况最适合 `--resume`，直接接着当前版本的 `last.pt` 继续跑。
2. 数据变多了，想在上一轮最佳结果基础上继续微调
   这种情况最适合 `--from-run`，用上一轮 `best.pt` 作为新一轮起点。
3. 只是想做一组对照实验
   这种情况可以继续用基础预训练模型，或换更大底模，不一定必须接上一轮。

### 8.3 在上一轮最佳模型基础上继续训练怎么做

示例：

```powershell
uv run sinan train group1 `
  --dataset-version firstpass_v2 `
  --name round2 `
  --from-run firstpass
```

```powershell
uv run sinan train group2 `
  --dataset-version firstpass_v2 `
  --name round2 `
  --from-run firstpass
```

这两条命令会默认把上一轮：

```text
runs\<task>\firstpass\weights\best.pt
```

当成新一轮训练的起始权重，但输出仍然会写到新的：

```text
runs\<task>\round2\
```

这样做的好处是：

- 旧结果不会被覆盖
- 你能看清第二轮到底有没有变好
- 数据版本和模型版本都能保留下来

## 9. 推荐验收顺序

如果你要交付一版模型，建议按这个顺序验收：

1. 先确认 `best.pt` 已生成
2. 跑 `uv run sinan test group1|group2 ...`
3. 打开 `summary.md`
4. 回看 `predict_*` 图片
5. 如果已有 JSONL 预测，再跑 `uv run sinan evaluate`
6. 决定下一步是补数据、调参数，还是继续推理侧集成

## 10. 这页完成标志

如果你已经做到下面 5 件事，就说明训练后验收链路已经跑通：

1. 找到 `best.pt`
2. 跑通一次 `uv run sinan predict ...`
3. 跑通一次 `uv run sinan test ...`
4. 看懂 `summary.md` 里的中文结论
5. 知道下一步该用 `--resume`、`--from-run`，还是该先回去补数据
