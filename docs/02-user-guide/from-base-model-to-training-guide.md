# 训练者角色：使用训练器完成训练、测试与评估

这页只讲训练者怎么用 `sinan` 完成手动训练。

## 1. 审核结论

当前手动训练主线已经可用，适合作为训练机正式入口：

- `env setup-train`
- `train group1`
- `train group2`
- `predict group1|group2`
- `test group1|group2`
- `evaluate`

## 2. 开始前你必须有

- 训练目录，例如 `D:\sinan-captcha-work`
- 至少一个可用数据集版本
- 已通过 `uv run sinan env check`

## 3. 手动训练

进入训练目录：

```powershell
Set-Location D:\sinan-captcha-work
```

### 3.1 训练 `group1`

```powershell
uv run sinan train group1 `
  --dataset-version firstpass `
  --name firstpass
```

这条命令会基于生成器导出的同一份 `group1 pipeline dataset`，顺序训练：

- `query-parser`
- `scene-detector`

如果你要显式拆开训练，也可以直接指定组件：

```powershell
uv run sinan train group1 `
  --dataset-version firstpass `
  --name g1_query `
  --component query-parser

uv run sinan train group1 `
  --dataset-version firstpass `
  --name g1_scene `
  --component scene-detector
```

### 3.2 训练 `group2`

```powershell
uv run sinan train group2 `
  --dataset-version firstpass `
  --name firstpass
```

这里有一个关键边界：

- `group2` 的 fresh 训练默认不是加载 `yolo26n.pt`
- `group2` 默认会使用内置架构名 `paired_cnn_v1`
- 这表示按 `PairedGapLocator` 架构从头开始训练第一版模型

## 4. 续训方式

### 4.1 从当前训练继续

```powershell
uv run sinan train group1 --name firstpass --resume
uv run sinan train group2 --name firstpass --resume
```

### 4.2 从上一轮最佳结果继续开新轮

```powershell
uv run sinan train group1 --dataset-version firstpass_v2 --name round2 --from-run firstpass
uv run sinan train group2 --dataset-version firstpass_v2 --name round2 --from-run firstpass
```

### 4.3 `group2` 三种模式怎么选

- `fresh`
  - 场景：第一次训 `group2`，或者你想完全重新开一轮
  - 命令：

```powershell
uv run sinan train group2 `
  --dataset-version firstpass `
  --name firstpass
```

  - 实际含义：默认使用 `paired_cnn_v1`，从头训练

- `resume`
  - 场景：同一个 run 中断后继续
  - 命令：

```powershell
uv run sinan train group2 `
  --name firstpass `
  --resume
```

  - 实际含义：自动续接 `runs/group2/firstpass/weights/last.pt`

- `from_run`
  - 场景：上一轮已经有较好的 `best.pt`，想开新 run 继续优化
  - 命令：

```powershell
uv run sinan train group2 `
  --dataset-version firstpass_v2 `
  --name round2 `
  --from-run firstpass
```

  - 实际含义：自动把 `runs/group2/firstpass/weights/best.pt` 作为起点

不要把 `group1` 用的 `yolo26n.pt` 传给 `group2`。`group2` 只接受：

- 架构名 `paired_cnn_v1`
- 或者 `group2` 自己训练产出的 checkpoint `.pt`

## 5. 预测、测试与评估

### 5.1 预测

```powershell
uv run sinan predict group1 --dataset-version firstpass --train-name firstpass
uv run sinan predict group2 --dataset-version firstpass --train-name firstpass
```

### 5.2 一键测试

```powershell
uv run sinan test group1 --dataset-version firstpass --train-name firstpass
uv run sinan test group2 --dataset-version firstpass --train-name firstpass
```

这里要特别记住：

- `group1` 的 `test` 不是只看两个子模型各自的检测结果
- 它验证的是最终位置挑选链路：
  - `query-parser` 先恢复 query 顺序
  - `scene-detector` 再给出 scene 候选目标
  - `matcher` 最后输出按顺序排列的点击点

### 5.3 JSONL 评估

```powershell
uv run sinan evaluate `
  --task group1 `
  --gold-dir D:\sinan-captcha-work\reports\group1\test_firstpass\_gold `
  --prediction-dir D:\sinan-captcha-work\reports\group1\predict_firstpass `
  --report-dir D:\sinan-captcha-work\reports\group1\eval_firstpass
```

## 6. 训练完成后看什么

### `group1`

重点看：

- `runs\group1\<train-name>\scene-detector\weights\best.pt`
- `runs\group1\<train-name>\query-parser\weights\best.pt`

### `group2`

重点看：

- `runs\group2\<train-name>\weights\best.pt`
- `runs\group2\<train-name>\summary.json`

## 7. 下一步

如果你要做训练结果验收，继续读：

- [训练者角色：训练后结果验收](./use-and-test-trained-models.md)

如果你要尝试自动化训练，继续读：

- [训练者角色：使用自动化训练](./auto-train-on-training-machine.md)
