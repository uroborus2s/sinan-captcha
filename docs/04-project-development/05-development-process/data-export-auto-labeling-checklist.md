# 样本导出与自动标注 Checklist

- 文档状态：草稿
- 当前阶段：DESIGN
- 目标读者：零基础训练操作者、项目维护者、生成服务维护者
- 负责人：Codex
- 关联需求：`REQ-002`、`REQ-003`、`REQ-004`、`REQ-007`

## 1. 总原则

这一阶段最重要的规则只有三条：

1. 优先从生成端直接导出标签。
2. 生成器直出 `gold` 必须 100% 来源于内部真值并通过校验。
3. 自动标注优先，人工只做种子集、抽检和纠错。

如果一开始就走“人工逐张标框”，基本会把项目拖死。

## 2. 先确认你有没有生成端入口

先逐条确认：

- [ ] 你能接触验证码生成服务、渲染脚本或日志
- [ ] 你知道第一组和第二组样本分别从哪里来
- [ ] 你能区分第一组与第二组
- [ ] 你能把导出的图片和标签存到固定目录

如果上面有任意一条做不到：

- 不要直接开始几千张人工标注
- 先只做少量种子集

## 3. 商业试卷目录先建好

当前仓库已经固定原始素材位置：

- 点选原始图：`materials/group1/<sample_id>/icon.jpg`、`materials/group1/<sample_id>/bg.jpg`
- 滑块原始图：`materials/result/<sample_id>/bg.jpg`、`materials/result/<sample_id>/gap.jpg`

推荐把“商业试卷”单独沉淀到：

```text
materials/
  business_exams/
    group1/
      reviewed-v1/
        import/
          query/
          scene/
        reviewed/
          query/
          scene/
          labels.jsonl
        manifest.json
    group2/
      reviewed-v1/
        import/
          master/
          tile/
        reviewed/
          master/
          tile/
          labels.jsonl
        manifest.json
```

准备命令：

```bash
uv run sinan exam prepare --task group1 --materials-root materials --output-dir materials/business_exams/group1/reviewed-v1
uv run sinan exam prepare --task group2 --materials-root materials --output-dir materials/business_exams/group2/reviewed-v1
```

检查项：

- [ ] `group1` 试卷工作目录里已生成 `import/query` 和 `import/scene`
- [ ] `group2` 试卷工作目录里已生成 `import/master` 和 `import/tile`
- [ ] `group2/import/tile` 已把 `gap.jpg` 转成紧边界透明 `png`
- [ ] 每个样本都保留稳定 `sample_id`
- [ ] 试卷目录与正式训练集目录分开，不能回灌训练集

## 4. 第一组导出 Checklist

第一组目标是“多图标顺序点击”。

每条样本必须尽量导出这些字段：

- [ ] `sample_id`
- [ ] `captcha_type`
- [ ] `query_image`
- [ ] `scene_image`
- [ ] `targets`
- [ ] `targets[].order`
- [ ] `targets[].class`
- [ ] `targets[].bbox`
- [ ] `targets[].center`
- [ ] `distractors`
- [ ] `label_source`
- [ ] `source_batch`

通过标准：

- [ ] 一条样本里能完整表示“要按什么顺序点击哪些目标”
- [ ] 干扰项没有丢

## 5. 第二组导出 Checklist

第二组目标是“滑块缺口定位”。

每条样本至少导出：

- [ ] `sample_id`
- [ ] `captcha_type`
- [ ] `master_image`
- [ ] `tile_image`
- [ ] `target_gap.bbox`
- [ ] `target_gap.center`
- [ ] `tile_bbox`
- [ ] `offset_x`
- [ ] `offset_y`
- [ ] `label_source`
- [ ] `source_batch`

通过标准：

- [ ] 一条样本里能明确缺口位置和滑块偏移量
- [ ] `master_image` 的缺口和 `tile_image` 来自同一个图案 mask
- [ ] `offset_x/y` 能由 `target_gap` 与 `tile_bbox` 一致推回

## 6. 样本来源合规 Checklist

所有正式训练样本都必须满足：

- [ ] 来自自有系统
- [ ] 或来自已授权环境
- [ ] 样本有来源批次记录
- [ ] 来源不明样本没有混入正式训练集

禁止：

- [ ] 直接抓第三方未授权验证码做正式训练

## 7. 数据切分 Checklist

正式切分前检查：

- [ ] 训练集、验证集、测试集互相独立
- [ ] 同一批背景模板或同一会话样本没有同时落到多个集合
- [ ] 测试集单独冻结

建议首版数量：

- [ ] 第一组：训练 5000，对验证 1000，对测试 1000
- [ ] 第二组：训练 3000，对验证 500，对测试 500

如果还没收够：

- [ ] 允许先做更小规模冒烟集
- [ ] 但正式验收前要补到目标规模

## 8. 第二组预标注 + 人工复核 Checklist

第二组目标是做出“商业试卷答案”，不是替换最终 solver。

执行原则：

- [ ] `X-AnyLabeling` 只负责预标注和人工复核
- [ ] 最终训练和最终求解仍继续使用项目现有 `group2` solver
- [ ] 如需给 `X-AnyLabeling` 喂原生模型，使用辅助单图缺口检测模型，仅服务于标注

辅助预标模型数据准备命令：

```bash
uv run sinan exam build-group2-prelabel-yolo \
  --source-dir materials/business_exams/group2/reviewed-v1/reviewed \
  --output-dir materials/business_exams/group2/prelabel-yolo
```

在 `X-AnyLabeling-GPU` 中的操作步骤：

1. 打开 `materials/business_exams/group2/reviewed-v1/import/master`
2. 加载原生目标检测模型，对 `master/bg` 图做批量预标注
3. 标签名固定为 `slider_gap`
4. 每张图只保留一个缺口框
5. `tile/gap` 图只作为对照参考，不在其上标框
6. 人工逐张复核 `bbox`
7. 把复核后的 `json + 图片` 放到 `reviewed/master` 和 `reviewed/tile`

导出 reviewed 试卷答案命令：

```bash
uv run sinan exam export-reviewed --task group2 --exam-root materials/business_exams/group2/reviewed-v1
```

通过标准：

- [ ] 每张 `master` 图只有一个 `slider_gap`
- [ ] `reviewed/labels.jsonl` 已生成
- [ ] `target_gap.bbox / center / offset_x / offset_y` 能稳定落盘

## 9. 第一组预标注 + 人工复核 Checklist

第一组要分别处理：

- `query/icon` 小图
- `scene/bg` 大图

在 `X-AnyLabeling-GPU` 中的操作步骤：

1. 打开 `materials/business_exams/group1/reviewed-v1/import/query`
2. 加载原生目标检测模型，对 `query/icon` 图批量预标注
3. `query` 标签只写类别名，例如 `icon_lock`
4. 打开 `materials/business_exams/group1/reviewed-v1/import/scene`
5. 对 `scene/bg` 图批量预标注
6. `scene` 标签必须写成 `NN|class`，例如 `01|icon_lock`
7. 同一张图里必须按点击顺序写 `01|`、`02|`、`03|`
8. 人工复核后，把 `json + 图片` 放到 `reviewed/query` 和 `reviewed/scene`

导出 reviewed 试卷答案命令：

```bash
uv run sinan exam export-reviewed --task group1 --exam-root materials/business_exams/group1/reviewed-v1
```

通过标准：

- [ ] `query` 标注导出后能自动按从左到右补 `order`
- [ ] `scene` 标注里顺序号和类别名一致
- [ ] `reviewed/labels.jsonl` 已生成
- [ ] `query_targets` 和 `scene_targets` 数量一致

## 10. 标签状态 Checklist

每条样本只允许以下三种状态：

- [ ] `gold`
- [ ] `auto`
- [ ] `reviewed`

流转规则：

- [ ] 生成端直出标签只有在真值一致性校验和重放校验通过后才可标记为 `gold`
- [ ] 规则法或暖启动模型产生的标签先标 `auto`
- [ ] 抽检/修正通过后改成 `reviewed`

禁止：

- [ ] 未抽检的 `auto` 直接进入测试集
- [ ] 真值校验失败的样本继续保留为 `gold`

## 10.1 商业试卷冻结规则

- [ ] 商业试卷统一标为 `reviewed`
- [ ] 商业试卷版本按 `reviewed-v1`、`reviewed-v2` 冻结
- [ ] 冻结后的试卷池不得回灌训练集
- [ ] 自动训练商业测试只从冻结版 `reviewed` 试卷池抽题

## 11. 抽检 Checklist

每一批自动标注都要抽检。

执行：

- [ ] 每批至少抽 200 张
- [ ] 检查漏框
- [ ] 检查错框
- [ ] 检查错类
- [ ] 检查第一组顺序字段
- [ ] 检查第二组中心点和偏移量

通过标准：

- [ ] 可用率 >= 97%

如果不通过：

- [ ] 不进入 `reviewed`
- [ ] 先修规则或修暖启动模型

## 12. 转换成训练集 Checklist

在进入训练前确认：

- [ ] `group1` 的 scene 图片已复制到 `proposal-yolo/images/train|val|test`
- [ ] `group1` 的 scene 图片已复制到 `proposal-yolo/images/train|val|test`
- [ ] `group1` 的 scene 标签已转换到 `proposal-yolo/labels/train|val|test`
- [ ] `group1` 的 query crop 已写入 `embedding/queries/train|val|test`
- [ ] `group1` 的 scene candidate crop 已写入 `embedding/candidates/train|val|test`
- [ ] `group1` 的 `embedding/pairs.jsonl` 与 `embedding/triplets.jsonl` 已生成
- [ ] `group1` 的 `eval/query|scene/train|val|test` 已生成
- [ ] `group1` 的 `eval/labels.jsonl` 已生成
- [ ] `group1` 的 `splits/train|val|test.jsonl` 已生成
- [ ] `group1` 的 `dataset.json` 已生成
- [ ] `group1 proposal-yolo` 单类别名固定为 `icon_object`
- [ ] `group2` 的 `master/train|val|test` 已生成
- [ ] `group2` 的 `tile/train|val|test` 已生成
- [ ] `group2` 的 `splits/train|val|test.jsonl` 已生成
- [ ] `group2` 的 `dataset.json` 已生成
- [ ] 第一组和第二组没有混在一起

## 13. 第一组特殊检查

第一组额外确认：

- [ ] 查询顺序字段没有丢
- [ ] 干扰项也有标签
- [ ] 类别表固定
- [ ] 同类重复目标场景有记录

## 14. 第二组特殊检查

第二组额外确认：

- [ ] `bbox` 存在
- [ ] `center` 存在
- [ ] `offset_x` 存在
- [ ] `dataset.json`、`master/`、`tile/`、`splits/` 能互相对上
- [ ] 缺口形状与 tile 外轮廓来自同一图案 mask
- [ ] 复杂背景样本也被覆盖
- [ ] 不同亮度条件下都有样本

## 15. 本阶段完成标志

以下项目全部勾上，才算“样本导出与自动标注阶段完成”：

- [ ] 两组目录结构正确
- [ ] 两组标签字段固定
- [ ] 来源合规
- [ ] 切分完成
- [ ] 第二组预标注可用
- [ ] 第一组有 `gold` 标签或有暖启动预标注能力
- [ ] 第二组 `gold` 样本已通过真值校验
- [ ] `reviewed` 数据集已形成
- [ ] `group1 yolo` 与 `group2 paired dataset` 都已生成
