# 背景素材扩充设计

- 当前阶段：IMPLEMENTATION（`REQ-016`）
- 关联需求：`REQ-005`、`REQ-008`、`REQ-016`、`NFR-004`
- 最近更新：2026-04-12
- 负责人：Codex

## 1. 设计目标

把现有 `uv run sinan materials collect-backgrounds` 从“生成搜索词并下载到 incoming”升级为可正式维护背景池的增量能力：

1. 保持主链路稳定，不把正确率未知的自动修补预处理强塞进主流程。
2. 允许参考图中带有验证码图标、缺口、滑块、文字等前景干扰，但由本地多模态模型直接在原图上忽略这些元素，只提取背景风格。
3. 把逐图分析结果、汇总搜索特征和下载任务状态都持久化，支持任务中断后自动恢复。
4. 为汇总阶段补齐 schema 漂移防护，避免模型返回字段结构变化时整批任务直接中断。
5. 为下载结果补齐最低质量门，阻止损坏图、小图和重复图进入正式背景池。
6. 在不破坏现有 `group1/group2` manifest 的前提下，把通过质量门的新背景图增量并入正式 `backgrounds/` 素材根。

## 2. 正式策略

### 2.1 风格分析策略

- 正式主线：原图直接送本地多模态模型。
- 约束提示词：
  - 只分析背景风格；
  - 忽略图标、缺口、滑块、文字、前景符号和点击目标；
  - 只输出风格摘要、英文搜索词和负面词。

设计判断：

- 当前没有证据表明通用遮罩/修补预处理能稳定优于多模态模型直接读原图。
- 若自动修补错误，会把背景纹理、光照和场景类型引向错误分布，风险高于“让 VLM 自己忽略前景”。
- 因此 V1 不把前景预处理放入正式主链路，只保留为后续可选实验方向。

### 2.2 断点续传策略

- `collect-backgrounds` 在 `output-root/reports/` 下固定写出 4 份状态文件：
  - `background-style-image-analysis.jsonl`：逐张参考图分析结果；
  - `background-style-summary.json`：基于逐图分析结果汇总出的最终搜索画像；
  - `background-style-download-state.json`：按搜索词拆分的下载任务流状态；
  - `background-style-drift-events.jsonl`：汇总阶段 schema 漂移、repair 与 fallback 事件。
- 逐图分析按图片粒度 checkpoint：
  - 每张图分析成功后立即写入 JSONL；
  - 下次重跑时，只要 `image_path + image_sha256 + analysis_key` 未变化，就直接复用，不再重跑该图片。
- 汇总阶段按整批参考图状态缓存：
  - 汇总输入由逐图分析结果组成；
  - 若参考图分析集合未变化，则直接复用上一次汇总结果。
- 下载阶段按 task 任务流缓存：
  - 每张参考图先生成 1 个 `reference_image` 保底任务；
  - 汇总搜索词再生成 `summary` 扩充任务；
  - 每个任务都有 `task_id / task_type / query / target_count / downloaded_count / rejected_count / next_page / completed / exhausted`；
  - 每次接受或拒绝候选图后立即刷盘；
  - 若搜索翻页前发生中断，下次从 `next_page` 继续，而不是从第 1 页重扫。

设计判断：

- 真正稳定的恢复语义必须建立在“任务状态显式持久化”上，不能依赖同目录重跑的偶然幂等。
- 逐图分析和下载任务是两类不同粒度的状态，不应混在一份报告里隐式推断。
- 若只保留汇总搜索词，参考图数量再多也可能只生成少量下载任务，无法满足“逐图保底扩充”目标。

### 2.3 汇总 schema 漂移防护

- 汇总阶段先按固定 JSON 合同校验顶层字段：
  - `style_summary_zh`
  - `style_summary_en`
  - `search_queries`
- 若响应不满足严格合同，但仍可被归一化解析：
  - 先记录 drift 事件；
  - 再向同一模型发起 1 次 repair 请求，要求只把已有信息改写成目标 schema；
  - repair 仍未恢复严格合同，则优先使用可归一化的模型结果继续任务。
- 若原始响应与 repair 响应都无法解析为可用汇总结果：
  - 自动退回本地汇总；
  - 继续生成下载任务，不以 schema 漂移中断整批流程。

设计判断：

- 模型输出结构漂移是运行时事实，不能仅靠 prompt 约束来赌“永不漂移”。
- repair 适合把“信息还在、字段错了”的响应拉回合同；本地 fallback 适合处理“内容已经不可恢复”的情况。
- drift 日志需要单独落盘，方便后续统计具体模型和提示词的漂移频次。

### 2.4 下载质量门

每张候选背景图下载后都要通过以下门槛：

1. 文件必须可被运行时图片解码器稳定打开。
2. 尺寸必须不低于命令参数配置的最小宽高阈值。
3. 必须未命中重复策略：
   - 同一轮下载集内重复；
   - `incoming/backgrounds/` 中已存在的重复；
   - 若启用正式合并，还要避免与目标正式素材根中的已有背景重复。

V1 去重策略：

- 默认走低风险重复抑制，不追求激进相似图清洗。
- 优先做确定性内容指纹；
- 需要近似去重时，允许额外启用基于小尺寸灰度哈希的汉明距离阈值。

### 2.5 正式素材根合并策略

- 新增可选 `merge-into` 目标根目录。
- 合并只处理：
  - `backgrounds/`
  - `manifests/materials.yaml`
  - `manifests/backgrounds.csv`
- 不改写：
  - `group1.templates.yaml`
  - `group1/icons/`
  - `group2.shapes.yaml`
  - `group2/shapes/`

设计判断：

- `collect-backgrounds` 产物应先落到 `incoming/`，再按显式参数增量并入正式素材根。
- 合并必须是幂等和增量的；重复背景应跳过而不是覆盖旧图。
- 正式索引需要保留来源和查询词，方便后续授权审计和质量回溯。

## 3. CLI 合同

保留现有主命令：

```bash
uv run sinan materials collect-backgrounds --source-dir <dir> --model <ollama-model>
```

新增或冻结的关键参数：

- `--min-width` / `--min-height`：下载质量门尺寸阈值
- `--max-hamming-distance`：近似去重阈值，默认保守
- `--merge-into <materials-root>`：将通过质量门的背景图增量并入正式素材根

## 4. 报告合同

背景扩充报告至少包含：

- 风格画像与原始模型输出
- 逐图分析 checkpoint 路径与复用计数
- 汇总结果路径
- schema 漂移日志路径与事件计数
- 下载任务状态路径、任务总数和已完成任务数
- 下载成功项
- 因损坏、尺寸不足、重复等原因被跳过的项
- 若启用正式合并：
  - 合并目标根
  - 新增写入数
  - 因目标根重复而跳过的项

## 5. 测试策略

- 单元测试：
  - 风格结果解析
  - 逐图分析 checkpoint 复用
  - 下载任务状态恢复
  - 下载后图片解码与尺寸校验
  - 重复检测
  - 正式素材根合并与 manifest 更新
- CLI 回归：
  - 根 CLI 命令分发
  - `dry-run` 不下载也不合并，但仍会写分析/汇总结果
- 非本轮范围：
  - 不做真实联网 E2E
  - 不做自动背景修补/inpaint 效果验收
