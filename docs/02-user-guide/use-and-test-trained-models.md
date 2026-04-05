# 训练者角色：训练后结果验收

这页解决的是：

- 模型训练完以后，训练者应该先看什么、怎么验收。

## 1. 先看训练产物是否完整

### `group1`

至少检查：

- `runs/group1/<train-name>/scene-detector/weights/best.pt`
- `runs/group1/<train-name>/query-parser/weights/best.pt`

### `group2`

至少检查：

- `runs/group2/<train-name>/weights/best.pt`
- `runs/group2/<train-name>/summary.json`

## 2. 再看测试结果

推荐直接执行：

```powershell
uv run sinan test group1 --dataset-version firstpass --train-name firstpass
uv run sinan test group2 --dataset-version firstpass --train-name firstpass
```

重点关注：

- `group1`
  - 单点命中率
  - 全序列命中率
  - 平均中心点误差
- `group2`
  - `point_hit_rate`
  - `mean_center_error_px`
  - `mean_iou`

## 3. 什么时候继续人工评估

如果你要对 JSONL 结果做更明确的验收，再跑：

```powershell
uv run sinan evaluate --task group1 --gold-dir <gold-dir> --prediction-dir <pred-dir> --report-dir <report-dir>
uv run sinan evaluate --task group2 --gold-dir <gold-dir> --prediction-dir <pred-dir> --report-dir <report-dir>
```

## 4. 什么时候可以进入业务接入准备

只有在下面 3 件事都满足后，才建议进入业务接入准备：

1. 模型测试结果已达标。
2. 训练结果已稳定。
3. 已准备后续导出和打包计划。

如果你是业务接入方，继续读：

- [使用者角色：安装与使用最终求解包](./use-solver-bundle.md)
- [使用者角色：在自己的应用中接入并做业务测试](./application-integration.md)
