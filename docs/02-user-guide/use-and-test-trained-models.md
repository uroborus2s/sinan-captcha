# 训练完成后的模型使用与测试

- 文档状态：草稿
- 当前阶段：IMPLEMENTATION
- 目标读者：训练执行者、交付使用者
- 负责人：Codex
- 最近新增：2026-04-02
- 关联需求：`REQ-002`、`REQ-005`、`REQ-006`、`REQ-007`、`REQ-008`

## 0. 读完后你应能做到

- 找到训练输出的权重文件
- 对训练好的模型做一次快速试跑
- 区分“冒烟测试”“验证集评估”“JSONL 对比评估”
- 看懂评估报告产物
- 明确当前仓库已经支持什么，还没有替你补齐什么

## 1. 先找到模型产物

训练完成后，先确认运行目录下已经有权重文件：

```text
D:\sinan-captcha-work\runs\group1\v1\weights\best.pt
D:\sinan-captcha-work\runs\group2\v1\weights\best.pt
```

如果这里没有 `best.pt`，先不要进入后面的“使用”和“测试”步骤。

## 2. 先做一次快速使用

当前仓库最稳的模型使用方式，是先走 YOLO 原生 `predict` 做冒烟验证。

第一专项示例：

```powershell
uv run yolo detect predict model=D:\sinan-captcha-work\runs\group1\v1\weights\best.pt source=D:\sinan-captcha-work\datasets\group1\v1\reviewed\batch_0001\scene conf=0.25 project=D:\sinan-captcha-work\reports\group1 name=predict_smoke
```

第二专项示例：

```powershell
uv run yolo detect predict model=D:\sinan-captcha-work\runs\group2\v1\weights\best.pt source=D:\sinan-captcha-work\datasets\group2\v1\reviewed\batch_0001\scene conf=0.25 project=D:\sinan-captcha-work\reports\group2 name=predict_smoke
```

这一步的目标很简单：

- 模型能正常加载
- 推理命令能跑完
- 输出图片里能看到检测框

## 3. 训练好的模型怎么被业务使用

当前仓库还没有把“YOLO 原生结果 -> 业务侧最终结构化输出”做成一条完整公共 CLI，所以先按下面理解：

### 3.1 第二专项

- 你可以直接从检测框计算中心点
- 常用点击点就是 `bbox` 的中心
- 如果你的业务只需要“单个目标位置”，第二专项更容易先落地

### 3.2 第一专项

- 第一专项不是只拿到框就结束
- 你还需要把检测结果映射成目标顺序
- 当前仓库还没有提供完整的一步式后处理 CLI

所以第一专项当前更现实的做法是：

1. 先确认模型能稳定检测出目标框
2. 再在你的推理脚本里把结果整理成有顺序的结构化输出
3. 最后再接到业务点击链路

## 4. 训练好的模型怎么测试

不要把“我能跑出一个 `best.pt`”当成测试完成。当前建议固定成三层测试。

### 4.1 第一层：冒烟测试

就是上一节的 `predict`。

适用目标：

- 快速确认模型文件没坏
- 快速确认推理环境没坏
- 快速看几张图是否明显跑偏

### 4.2 第二层：验证集评估

用 YOLO 原生 `val` 对 `dataset.yaml` 做评估。

第一专项示例：

```powershell
uv run yolo detect val data=D:\sinan-captcha-work\datasets\group1\v1\yolo\dataset.yaml model=D:\sinan-captcha-work\runs\group1\v1\weights\best.pt device=0 project=D:\sinan-captcha-work\reports\group1 name=val_v1
```

第二专项示例：

```powershell
uv run yolo detect val data=D:\sinan-captcha-work\datasets\group2\v1\yolo\dataset.yaml model=D:\sinan-captcha-work\runs\group2\v1\weights\best.pt device=0 project=D:\sinan-captcha-work\reports\group2 name=val_v1
```

这一步适合看：

- YOLO 原生验证指标
- 同一版模型的横向比较
- 训练参数变化后是否变好还是变坏

### 4.3 第三层：JSONL 对比评估

如果你的推理脚本已经能把预测结果导出成和真值兼容的 `labels.jsonl`，可以直接使用仓库里的评估脚本。

第二专项示例：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\evaluate\evaluate_model.py `
  --task group2 `
  --gold-dir D:\sinan-captcha-work\datasets\group2\v1\reviewed\batch_0001 `
  --prediction-dir D:\sinan-captcha-work\reports\group2\pred_jsonl_v1 `
  --report-dir D:\sinan-captcha-work\reports\group2\eval_jsonl_v1
```

第一专项示例：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\evaluate\evaluate_model.py `
  --task group1 `
  --gold-dir D:\sinan-captcha-work\datasets\group1\v1\reviewed\batch_0001 `
  --prediction-dir D:\sinan-captcha-work\reports\group1\pred_jsonl_v1 `
  --report-dir D:\sinan-captcha-work\reports\group1\eval_jsonl_v1
```

`gold-dir` 和 `prediction-dir` 都必须包含 `labels.jsonl`。

最小理解方式如下：

- 第二专项预测结果里要有 `sample_id` 和 `target`
- `target` 里至少要有 `class_id`、`bbox`、`center`
- 第一专项预测结果里要有按顺序排列的 `targets[]`
- 如果你记录了 `inference_ms`，第二专项评估会一并统计平均推理耗时

## 5. 怎么看评估结果

JSONL 对比评估会产出这三类文件：

```text
D:\sinan-captcha-work\reports\<task>\eval_jsonl_v1\
  summary.json
  summary.md
  failures.jsonl
```

你重点看这几项：

### 5.1 第一专项

- `single_target_hit_rate`
- `full_sequence_hit_rate`
- `mean_center_error_px`
- `order_error_rate`

### 5.2 第二专项

- `point_hit_rate`
- `mean_center_error_px`
- `mean_iou`
- `mean_inference_ms`

`failures.jsonl` 用来回看失败样本，决定下一轮该补：

- 数据
- 标注
- 推理后处理
- 还是训练参数

## 6. 当前边界要说清楚

当前仓库已经有：

- 离线自动标注/标签整理入口
- JSONL 对比评估脚本
- 训练命令生成入口

当前仓库还没有替你完全做完：

- 第二专项对等的仓内样本导出器
- 从 YOLO 原生预测结果自动转成业务最终输出的一步式 CLI
- 第一专项完整的顺序后处理公共入口

## 7. 推荐验收顺序

如果你是第一次交付一版模型，按这个顺序最稳：

1. 先做 10 到 20 张图的 `predict` 冒烟测试
2. 再跑一次 `yolo detect val`
3. 如果你已经有预测 JSONL，再跑 `evaluate_model.py`
4. 打开 `failures.jsonl` 反查失败样本
5. 把问题回灌到 `reviewed` 数据集或后处理逻辑
