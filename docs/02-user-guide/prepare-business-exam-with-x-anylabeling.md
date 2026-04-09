# 训练者角色：用 X-AnyLabeling 制作商业测试试卷答案

这页解决的是 3 件事：

1. 你手里的原始图片怎么整理成可标注目录。
2. 你在训练机上怎么实际操作 `X-AnyLabeling-GPU`。
3. 你标完以后怎么人工复核，并导出成 `labels.jsonl` 试卷答案。

这条线的目标只有一个：

- 做出 `reviewed` 商业试卷池，供训练完成后随机抽题测试。

它**不会**改变项目现在的最终 solver 方案。

- `X-AnyLabeling` 只用于预标注和人工复核。
- 最终训练结果验收时，仍然调用项目现有 `group1` / `group2` solver。

## 1. 先确认你当前的原始图片位置

当前仓库已经固定原始图片目录：

### `group1` 点选题

- `materials/group1/<sample_id>/icon.jpg`
- `materials/group1/<sample_id>/bg.jpg`

含义：

- `icon.jpg`：题目上方的小查询图
- `bg.jpg`：真正需要点击的大背景图

### `group2` 滑块题

- `materials/result/<sample_id>/bg.jpg`
- `materials/result/<sample_id>/gap.jpg`

含义：

- `bg.jpg`：带缺口的背景图
- `gap.jpg`：滑块小图

如果你的原始图已经在这两个目录里，就不要手工改名、不要手工搬目录，直接用下面的命令整理。

## 2. 第一步：把原始图片整理成试卷工作目录

在项目根目录执行：

```bash
uv run sinan exam prepare --task group1 --materials-root materials --output-dir materials/business_exams/group1/reviewed-v1
uv run sinan exam prepare --task group2 --materials-root materials --output-dir materials/business_exams/group2/reviewed-v1
```

执行后会得到：

### `group1`

```text
materials/business_exams/group1/reviewed-v1/
  import/
    query/
    scene/
  manifest.json
```

### `group2`

```text
materials/business_exams/group2/reviewed-v1/
  import/
    master/
    tile/
  manifest.json
```

这些目录的含义是：

- `group1/import/query`
  - 存放从 `icon.jpg` 整理出来的查询图
- `group1/import/scene`
  - 存放从 `bg.jpg` 整理出来的场景图
- `group2/import/master`
  - 存放滑块背景图
- `group2/import/tile`
  - 存放滑块小图，只用来参考

`manifest.json` 里会记录每个样本原来来自哪里，后面出问题时可以回查。

## 3. 第二步：在训练机上启动 X-AnyLabeling

如果你以前没用过，先记住这几个最基本动作：

1. 打开一个图片目录。
2. 加载一个原生检测模型做预标注。
3. 逐张检查框和标签。
4. 保存当前图片标注。

你这次不要一口气混着做，按下面顺序分 3 次操作：

1. `group1 query`
2. `group1 scene`
3. `group2 master`

## 4. `group1 query` 的详细操作

目标：

- 给每张 `icon.jpg` 里的查询小图标打框。

目录：

- `materials/business_exams/group1/reviewed-v1/import/query`

操作步骤：

1. 打开 `X-AnyLabeling-GPU`。
2. 选择“打开目录”。
3. 选中：
   - `materials/business_exams/group1/reviewed-v1/import/query`
4. 如果你已经准备好了可用于预标注的原生检测模型，就在软件里加载这个模型。
5. 对当前目录执行预标注。
6. 打开第一张图。
7. 检查图里每个小图标是否都被框到了。
8. 如果漏框，就新建一个矩形框。
9. 如果框位置不准，就拖动框边修正。
10. 如果标签错了，就修改标签名。
11. 保存当前图片标注。
12. 继续下一张。

### `group1 query` 的标签规则

这里非常重要：

- `query` 里的标签**只写类别名**
- 不写顺序

正确示例：

- `icon_lock`
- `icon_star`
- `icon_car`

错误示例：

- `01|icon_lock`
- `1_icon_lock`
- `target_1`

### `group1 query` 复核标准

每张图至少检查：

- 每个查询图标都被框到
- 没有多框
- 没有漏框
- 标签类别正确

## 5. `group1 scene` 的详细操作

目标：

- 给每张 `bg.jpg` 里的真实点击目标打框，并写清点击顺序。

目录：

- `materials/business_exams/group1/reviewed-v1/import/scene`

操作步骤：

1. 在 `X-AnyLabeling-GPU` 里打开目录：
   - `materials/business_exams/group1/reviewed-v1/import/scene`
2. 加载预标注模型。
3. 执行当前目录的预标注。
4. 打开第一张图。
5. 找到题目里真正需要点击的目标。
6. 检查这些目标是否都被框到。
7. 删除干扰项上的错误框。
8. 修正框位置。
9. 修改标签为“顺序 + 类别名”。
10. 保存。
11. 继续下一张。

### `group1 scene` 的标签规则

这里的标签必须写成：

- `NN|class`

正确示例：

- `01|icon_lock`
- `02|icon_star`
- `03|icon_car`

规则是：

- `01`、`02`、`03` 表示点击顺序
- 后面的 `class` 必须和 `query` 里对应的类别一致
- 同一张图里只能标真正答案，不标干扰项

### `group1 scene` 复核标准

每张图至少检查：

- 只标真正答案
- 顺序号正确
- 类别名正确
- 框位置合理

最稳的复核方式是：

1. 左边打开同 `sample_id` 的 `query`
2. 右边打开同 `sample_id` 的 `scene`
3. 先数 `query` 里有几个目标
4. 再看 `scene` 里是不是也有对应数量的 `01|...`、`02|...`
5. 检查类别和顺序是否一致

## 6. `group2 master` 的详细操作

目标：

- 给每张滑块背景图上的缺口打一个框。

目录：

- `materials/business_exams/group2/reviewed-v1/import/master`

参考图目录：

- `materials/business_exams/group2/reviewed-v1/import/tile`

操作步骤：

1. 在 `X-AnyLabeling-GPU` 里打开目录：
   - `materials/business_exams/group2/reviewed-v1/import/master`
2. 加载原生检测模型。
3. 执行预标注。
4. 打开第一张图。
5. 找到真正的缺口位置。
6. 如果软件给了多个框，只保留真正缺口那个。
7. 如果框偏了，就拖动修正。
8. 标签统一改成：
   - `slider_gap`
9. 保存。
10. 继续下一张。

### `group2` 的标签规则

每张图必须满足：

- 只能有 1 个框
- 标签只能是 `slider_gap`

如果你不确定哪个位置是缺口，就同时打开对应的 `tile/gap` 小图，用形状对比。

### `group2` 复核标准

每张图至少检查：

- 只有 1 个框
- 标签是 `slider_gap`
- 框到的是缺口，不是别的高亮区域
- 框大小和缺口边界基本一致

## 7. 第三步：把标注结果整理到 `reviewed` 目录

标完以后，不要直接从 `import` 目录导出结果，要把“图片 + json”整理到 `reviewed` 目录。

### `group1`

把下面两类文件分别放好：

- `materials/business_exams/group1/reviewed-v1/reviewed/query`
  - 查询图图片
  - 查询图对应的 `json`
- `materials/business_exams/group1/reviewed-v1/reviewed/scene`
  - 场景图图片
  - 场景图对应的 `json`

### `group2`

把下面两类文件分别放好：

- `materials/business_exams/group2/reviewed-v1/reviewed/master`
  - 背景图图片
  - 背景图对应的 `json`
- `materials/business_exams/group2/reviewed-v1/reviewed/tile`
  - 小图图片

注意：

- `group2/tile` 目录里通常只放图片，不放标注框
- 真正答案框在 `reviewed/master/*.json`

## 8. 第四步：导出成正式试卷答案

整理好 `reviewed` 目录后，在项目根目录执行：

```bash
uv run sinan exam export-reviewed --task group1 --exam-root materials/business_exams/group1/reviewed-v1
uv run sinan exam export-reviewed --task group2 --exam-root materials/business_exams/group2/reviewed-v1
```

导出后会生成：

### `group1`

- `materials/business_exams/group1/reviewed-v1/reviewed/labels.jsonl`

### `group2`

- `materials/business_exams/group2/reviewed-v1/reviewed/labels.jsonl`

这两份 `labels.jsonl` 就是后面自动训练商业测试要用的“试卷标准答案”。

## 9. 第五步：自动训练怎么使用这套试卷

训练完成后，要让自动训练从 reviewed 试卷池随机抽 30 题测试。

### `group1`

```bash
uv run sinan auto-train run group1 \
  --study-name study_group1_exam \
  --train-root D:\sinan-captcha-work \
  --generator-workspace D:\sinan-generator\workspace \
  --business-eval-dir D:\sinan-captcha-work\materials\business_exams\group1\reviewed-v1\reviewed
```

### `group2`

```bash
uv run sinan auto-train run group2 \
  --study-name study_group2_exam \
  --train-root D:\sinan-captcha-work \
  --generator-workspace D:\sinan-generator\workspace \
  --business-eval-dir D:\sinan-captcha-work\materials\business_exams\group2\reviewed-v1\reviewed
```

当前商业测试逻辑是：

- 从试卷池稳定随机抽 `30` 题
- 用项目现有 solver 跑预测
- `group1` 按整题序列判卷
- `group2` 按中心点误差和 `IoU` 判卷
- 成功率达到门槛才算通过

## 10. 最后再记 4 条硬规则

1. 商业试卷统一标记为 `reviewed`，不要回灌训练集。
2. `group1 query` 只写类别名，不写顺序。
3. `group1 scene` 必须写 `NN|class`。
4. `group2` 每张图只允许一个 `slider_gap`。

## 11. 推荐阅读顺序

如果你第一次做这条线，按下面顺序读：

1. [训练者角色：使用生成器准备训练数据](./prepare-training-data-with-generator.md)
2. [训练者角色：用 X-AnyLabeling 制作商业测试试卷答案](./prepare-business-exam-with-x-anylabeling.md)
3. [训练者角色：使用自动化训练](./auto-train-on-training-machine.md)
4. [训练者角色：训练后结果验收](./use-and-test-trained-models.md)
