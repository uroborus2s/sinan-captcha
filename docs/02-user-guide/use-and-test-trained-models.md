# 训练完成后的模型使用与测试

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：训练执行者、交付使用者
- 负责人：Codex

## 0. 这份文档解决什么问题

这页只回答训练完成后的两件事：

1. 模型怎么做快速使用验证
2. 模型怎么做训练后验收

## 1. 先找到权重文件

训练完成后，先确认这里已经有权重：

```text
D:\sinan-captcha-work\runs\group1\firstpass\weights\best.pt
D:\sinan-captcha-work\runs\group2\firstpass\weights\best.pt
```

如果没有 `best.pt`，先不要继续做模型使用和测试。

## 2. 先做一次快速预测

最稳的方式是先用 YOLO 原生命令做 `predict`。

### 2.1 `group1`

```powershell
uv run yolo detect predict `
  model=D:\sinan-captcha-work\runs\group1\firstpass\weights\best.pt `
  source=D:\sinan-captcha-work\datasets\group1\firstpass\yolo\images\val `
  conf=0.25 `
  project=D:\sinan-captcha-work\reports\group1 `
  name=predict_firstpass
```

### 2.2 `group2`

```powershell
uv run yolo detect predict `
  model=D:\sinan-captcha-work\runs\group2\firstpass\weights\best.pt `
  source=D:\sinan-captcha-work\datasets\group2\firstpass\yolo\images\val `
  conf=0.25 `
  project=D:\sinan-captcha-work\reports\group2 `
  name=predict_firstpass
```

这一步只看三件事：

- 模型能加载
- 推理能跑完
- 输出图里能看到合理检测框

## 3. 再做验证集评估

### 3.1 `group1`

```powershell
uv run yolo detect val `
  data=D:\sinan-captcha-work\datasets\group1\firstpass\yolo\dataset.yaml `
  model=D:\sinan-captcha-work\runs\group1\firstpass\weights\best.pt `
  device=0 `
  project=D:\sinan-captcha-work\reports\group1 `
  name=val_firstpass
```

### 3.2 `group2`

```powershell
uv run yolo detect val `
  data=D:\sinan-captcha-work\datasets\group2\firstpass\yolo\dataset.yaml `
  model=D:\sinan-captcha-work\runs\group2\firstpass\weights\best.pt `
  device=0 `
  project=D:\sinan-captcha-work\reports\group2 `
  name=val_firstpass
```

这一步适合做：

- 同一专项不同训练版本的横向比较
- 超参数调整前后的回归检查
- 快速筛查是不是明显退化

## 4. 做 JSONL 对比评估

如果你的推理链路已经能输出与 `gold` 兼容的预测 `labels.jsonl`，继续用 `uv run sinan evaluate` 做更贴近任务契约的评估。

### 4.1 `group1`

```powershell
uv run sinan evaluate `
  --task group1 `
  --gold-dir D:\sinan-captcha-work\datasets\group1\v1\reviewed\batch_0001 `
  --prediction-dir D:\sinan-captcha-work\reports\group1\pred_jsonl_v1 `
  --report-dir D:\sinan-captcha-work\reports\group1\eval_jsonl_v1
```

### 4.2 `group2`

```powershell
uv run sinan evaluate `
  --task group2 `
  --gold-dir D:\sinan-captcha-work\datasets\group2\v1\reviewed\batch_0001 `
  --prediction-dir D:\sinan-captcha-work\reports\group2\pred_jsonl_v1 `
  --report-dir D:\sinan-captcha-work\reports\group2\eval_jsonl_v1
```

`gold-dir` 和 `prediction-dir` 都必须包含 `labels.jsonl`。

## 5. 怎么看评估输出

`uv run sinan evaluate` 会产出：

```text
summary.json
summary.md
failures.jsonl
```

### 5.1 `group1` 重点看什么

- `single_target_hit_rate`
- `full_sequence_hit_rate`
- `mean_center_error_px`
- `order_error_rate`

### 5.2 `group2` 重点看什么

- `point_hit_rate`
- `mean_center_error_px`
- `mean_iou`
- `mean_inference_ms`

### 5.3 `failures.jsonl` 用来做什么

它用来反查失败样本，判断下一轮该补的是：

- 数据
- 训练参数
- 自动标注
- 推理后处理

## 6. 训练好的模型如何进入业务

当前项目已经提供：

- 训练入口
- 原生 `predict` 与 `val` 路线
- JSONL 对比评估入口

当前项目还没有提供：

- 面向业务的公共推理 CLI
- 一步式“YOLO 结果 -> 业务最终输出”转换器

这意味着：

- `group2` 通常更容易先落地，因为只需要一个目标位置
- `group1` 还需要你自己的顺序整理和结果映射逻辑

## 7. 推荐验收顺序

如果你要交付一版模型，建议按这个顺序验收：

1. 先跑 `predict`
2. 再跑 `uv run yolo detect val`
3. 如果已有预测 JSONL，再跑 `uv run sinan evaluate`
4. 打开 `failures.jsonl` 回看错误样本
5. 决定是否回到数据、训练或推理侧继续迭代

## 8. 这页完成标志

如果你已经做到下面 5 件事，就说明训练后验收链路已经跑通：

1. 找到 `best.pt`
2. 跑通一次 `predict`
3. 跑通一次 `val`
4. 跑通一次 `uv run sinan evaluate`
5. 能根据失败样本决定下一步该改哪里
