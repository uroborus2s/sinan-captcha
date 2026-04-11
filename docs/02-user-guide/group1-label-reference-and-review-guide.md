# 训练者角色：`group1` 标签对照与人工复核说明

这页专门解决 `group1` 人工审核时最容易混淆的 4 件事：

1. 当前预标注 run 到底应该以哪份素材/类表做辅助参考。
2. `query` / `scene` 的标签到底应该怎么写。
3. 缺失框、错框、错标签应该怎么人工修。
4. 模型没识别出来的图标，到底是人工补框，还是要回到生成器扩类重训。

## 1. 先记住一个总原则

`group1` 当前正式 reviewed 合同已经切到实例匹配路线。

- reviewed 人工标注不再把“类别名”当正式答案主键。
- 正式答案只要求保住：
  - `query` 的框
  - `scene` 的点击顺序
  - 两边的目标位置
- 如果你愿意保留旧类别判断，它现在只作为可选 `class_guess` 辅助信息，不再是正式导出字段。
- 如果素材体系需要扩类，也不要在标注现场临时热修 reviewed 合同，而应该回到生成器、素材和训练链路处理。

相关设计边界见：

- [技术选型：`group1` 正式技术路线](../04-project-development/04-design/technical-selection.md)
- [模块边界：`group1` 类别体系不稳定时的处理规则](../04-project-development/04-design/module-boundaries.md)

如果你现在要做的是“以素材类别为准补齐生成器素材”，而不是讨论某一轮训练数据启不启用，直接看：

- [训练者角色：`group1` 素材类别补齐清单](./group1-material-category-backlog.md)

## 2. 你审核时应以哪份参考素材为准

人工审核时，如果你想确认“这个图标大概像哪一类”，优先级按下面顺序看：

1. 当前 run 实际使用的数据集 `dataset.yaml`
2. 当前素材包的 `group1.classes.yaml`
3. 当前素材目录 `group1/icons/<class_name>/`

原因很简单：

- `dataset.yaml` 能告诉你当前 run 的旧类表背景。
- `group1.classes.yaml` 更适合查中文名和标准拼写。
- `group1/icons/<class_name>/` 目录最适合肉眼比对图标长相。
- 但这些都只用于辅助判断，不是 reviewed 正式标签合同。

当前仓库里，这 3 个参考点分别可以看：

- 当前 `firstpass` 数据集类表：[datasets/group1/firstpass/yolo/dataset.yaml](../../datasets/group1/firstpass/yolo/dataset.yaml)
- 当前素材包类清单：[materials/incoming/group1_icon_pack/manifests/group1.classes.yaml](../../materials/incoming/group1_icon_pack/manifests/group1.classes.yaml)
- 当前素材包图标目录：[materials/incoming/group1_icon_pack/group1/icons](../../materials/incoming/group1_icon_pack/group1/icons)

如果你的实际预训练 run 用的不是 `firstpass`，那就把下面文档里的“当前 `firstpass` 生效”理解成“请替换成你的实际 `dataset-version` 再看一遍 `dataset.yaml`”。

## 3. `firstpass` 当前生效的 20 个标签

下面这 20 个类，来自当前 `firstpass` 的 [dataset.yaml](../../datasets/group1/firstpass/yolo/dataset.yaml)：

| 标签名 | 中文名 |
| --- | --- |
| `icon_house` | 房子 |
| `icon_leaf` | 叶子 |
| `icon_ship` | 轮船 |
| `icon_plane` | 飞机 |
| `icon_car` | 汽车 |
| `icon_bicycle` | 自行车 |
| `icon_key` | 钥匙 |
| `icon_lock` | 锁 |
| `icon_camera` | 相机 |
| `icon_star` | 星星 |
| `icon_heart` | 心形 |
| `icon_paw` | 爪印 |
| `icon_tree` | 树 |
| `icon_flower` | 花朵 |
| `icon_gift` | 礼物 |
| `icon_music` | 音乐 |
| `icon_bell` | 铃铛 |
| `icon_umbrella` | 雨伞 |
| `icon_flag` | 旗帜 |
| `icon_globe` | 地球 |

如果你当前的预标模型就是用 `firstpass` 训练出来的，人工审核时优先从这 20 个里选。

## 4. 完整 `group1` 标签对照表

下面这张表来自当前素材包 [group1.classes.yaml](../../materials/incoming/group1_icon_pack/manifests/group1.classes.yaml)。

说明：

- `当前 firstpass 生效` = `是`
  - 表示它已经在当前 `firstpass` 数据集类表里，当前 `firstpass` 模型理论上有机会识别它。
- `当前 firstpass 生效` = `否`
  - 表示它只是素材包里存在，但不属于当前 `firstpass` 训练类表。
  - 如果你现在手里的模型是 `firstpass` 训出来的，就不要把这类标签当成“当前模型已支持”。

| 标签名 | 中文名 | 当前 `firstpass` 生效 |
| --- | --- | --- |
| `icon_smile` | 笑脸 | 否 |
| `icon_mail` | 信封 | 否 |
| `icon_check_circle` | 勾选圆章 | 否 |
| `icon_flag` | 旗帜 | 是 |
| `icon_briefcase` | 公文包 | 否 |
| `icon_remote_screen` | 遥控器与屏幕 | 否 |
| `icon_inbox` | 收件箱 | 否 |
| `icon_bell` | 铃铛 | 是 |
| `icon_heart` | 心形 | 是 |
| `icon_bolt` | 闪电 | 否 |
| `icon_train` | 列车 | 否 |
| `icon_shopping_cart` | 购物车 | 否 |
| `icon_yen_shield` | 日元盾牌 | 否 |
| `icon_letter_a_circle` | 圆形字母A | 否 |
| `icon_cloud_download` | 云下载 | 否 |
| `icon_anchor` | 锚 | 否 |
| `icon_lantern` | 灯笼 | 否 |
| `icon_knot` | 结饰 | 否 |
| `icon_star` | 星星 | 是 |
| `icon_seated_person` | 坐姿人物 | 否 |
| `icon_compass` | 指南针 | 否 |
| `icon_key` | 钥匙 | 是 |
| `icon_christmas_tree` | 松树 | 否 |
| `icon_climbing` | 攀岩人物 | 否 |
| `icon_headset` | 耳机 | 否 |
| `icon_speedboat` | 快艇 | 否 |
| `icon_luggage` | 行李箱 | 否 |
| `icon_flame` | 火焰 | 否 |
| `icon_microphone` | 麦克风 | 否 |
| `icon_shield_plus` | 十字盾牌 | 否 |
| `icon_hiking` | 徒步人物 | 否 |
| `icon_plane` | 飞机 | 是 |
| `icon_users` | 多人 | 否 |
| `icon_bicycle` | 自行车 | 是 |
| `icon_camera` | 相机 | 是 |
| `icon_car` | 汽车 | 是 |
| `icon_flower` | 花朵 | 是 |
| `icon_gift` | 礼物 | 是 |
| `icon_globe` | 地球 | 是 |
| `icon_house` | 房子 | 是 |
| `icon_leaf` | 叶子 | 是 |
| `icon_lock` | 锁 | 是 |
| `icon_music` | 音乐 | 是 |
| `icon_paw` | 爪印 | 是 |
| `icon_ship` | 轮船 | 是 |
| `icon_tree` | 树 | 是 |
| `icon_umbrella` | 雨伞 | 是 |

所有图标样例都按统一目录组织：

- `materials/incoming/group1_icon_pack/group1/icons/<class_name>/`

例如：

- [icon_plane 示例目录](../../materials/incoming/group1_icon_pack/group1/icons/icon_plane)
- [icon_flag 示例目录](../../materials/incoming/group1_icon_pack/group1/icons/icon_flag)
- [icon_yen_shield 示例目录](../../materials/incoming/group1_icon_pack/group1/icons/icon_yen_shield)

## 5. `query` 和 `scene` 的标签规则

### 5.1 `query`

`query` 统一写 `query_item`。

正确示例：

- `query_item`

错误示例：

- `icon_lock`
- `01|icon_lock`
- `1_icon_lock`
- `lock`

原因：

- `query` 的顺序会在导出 `reviewed/labels.jsonl` 时，按框中心从左到右自动补上。
- 如果你想保留模型给出的旧类别提示，只放在 `flags.class_guess`，不要再写进正式 label。

相关实现见：

- [导出 `query_items` 的顺序恢复逻辑](/Users/uroborus/AiProject/sinan-captcha/packages/sinan-captcha/src/exam/service.py)

### 5.2 `scene`

`scene` 必须写成两位顺序号 `NN`。

正确示例：

- `01`
- `02`
- `03`

规则：

- `01`、`02`、`03` 表示点击顺序。
- 同一张图里只标真正答案，不标干扰项。
- 如果你想保留旧类别提示，也只放在 `flags.class_guess`。

相关实现见：

- [导出 `scene_targets` 的顺序解析逻辑](/Users/uroborus/AiProject/sinan-captcha/packages/sinan-captcha/src/exam/service.py)

## 6. 人工审核时怎样确认标签是否正确

最稳的人工审核顺序是：

1. 先打开同 `sample_id` 的 `query` 图，数清楚查询图标有几个。
2. 看每个图标的实际外形，更像哪一个标准类。
3. 去上面的完整类表里找标准拼写。
4. 如果仍然犹豫，就打开对应 `group1/icons/<class_name>/` 目录看样例图。
5. 再回到 `scene` 图检查数量、类别和顺序是否一致。

每张 `query` 图至少检查：

- 每个查询图标都被框到
- 没有多框
- 没有漏框
- 标签统一写成 `query_item`

每张 `scene` 图至少检查：

- 只标真正答案
- 顺序号正确
- 框位置合理
- 如果保留了 `class_guess`，它只作为辅助信息，不影响正式导出

## 7. 模型没识别出来的图标怎么处理

这里一定要分成两种情况。

如果你当前阶段的目标已经变成“先补齐素材类别，再考虑下一轮训练”，那就把无法精确归类的图标统一登记到：

- [训练者角色：`group1` 素材类别补齐清单](./group1-material-category-backlog.md)

### 7.1 这是已有类别，只是模型漏了

特征：

- 这个图标能在上面的完整类表里找到。
- 它也属于你当前 run 使用的 `dataset.yaml` 类表，或者至少属于你已经冻结的业务类别体系。
- 只是这张图里模型没框出来，或者框错了。

处理方式：

1. 直接在 `reviewed/query` 或 `reviewed/scene` 里人工补框。
2. 直接改成正确标准标签。
3. 正常保存，继续审核。

这一步**不是**马上去改生成器。

原因：

- 这属于预标模型漏检或错检。
- 当前任务是先把 `reviewed` 试卷答案修对。
- `reviewed` 试卷本身不要直接回灌训练集。

相关硬规则见：

- [商业试卷统一标记为 `reviewed`，不要回灌训练集](./prepare-business-exam-with-x-anylabeling.md)

如果这类漏检反复出现，再单独开训练改进动作：

- 回看该类别的素材是否过少
- 回看该类别样式是否偏离现有素材
- 需要时补更多该类图标素材，再生成新数据版本并重训

### 7.2 这是真正的新类别，不在当前类表里

特征：

- 你在当前 run 的 `dataset.yaml` 里找不到它。
- 在当前素材包 `group1.classes.yaml` 里也找不到稳定对应项，或者现有标签都不准确。

处理方式：

1. 不要为了让当前审核先过，随手把它硬塞成某个旧类。
2. 也不要在当前冻结的 `reviewed-v1` 里临时热修业务合同。
3. 先把这个样本记为“新类别待处理”。
4. 回到生成器素材层做正式扩类：
   - 追加 `group1.templates.yaml` 中对应模板/变体定义
   - 追加 `group1/templates/<template_id>/...`
   - 重新生成数据集版本
   - 重新训练 `query-parser`、`proposal-detector` 和 `icon-embedder`
5. 如果业务试卷池已经冻结，建议新开 `reviewed-v2`，不要静默改旧版 `reviewed-v1`。

为什么要这么做：

- 当前 `group1` 是冻结模板库路线，模型没有“现场学会新模板”的能力。
- 模板体系不稳定时，项目要求发起设计变更，而不是在实现或标注现场临时热修。

相关边界见：

- [技术选型：`group1` 当前不走相似度匹配模型](../04-project-development/04-design/technical-selection.md)
- [模块边界：类别体系不稳定时发起设计变更](../04-project-development/04-design/module-boundaries.md#L220)

## 8. 一句话决策规则

- 能在当前类表里找到：人工补框，改成标准标签，不必立刻动生成器。
- 当前类表里根本没有：不要硬猜旧标签，回到生成器做扩类，并准备新的数据版本和新的 reviewed 版本。

## 9. 审核前的最短清单

开始人工审核前，先确认这 5 件事：

1. 你知道当前预标模型对应的 `dataset-version`。
2. 你已经打开对应数据集的 `dataset.yaml`。
3. 你手里有这页完整标签对照表。
4. 你只在 `reviewed/` 目录里修改，不改 `import/`。
5. 你分得清“已有类漏检”和“新类别扩类”是两条不同流程。
