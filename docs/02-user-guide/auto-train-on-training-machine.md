# 训练者角色：使用自动化训练

这页只讲怎样在训练机上把 `uv run sinan auto-train ...` 搭起来并真正跑起来。

## 1. 先选一种运行路线

当前有两条路线：

| 路线 | 是否需要大模型 | 是否需要 `opencode` | 当前推荐程度 | 适用场景 |
| --- | --- | --- | --- | --- |
| `rules` 路线 | 不需要 | 不需要 | 推荐先用 | 第一次在训练机上跑 `auto-train` |
| `opencode` 路线 | 需要一个可供 OpenCode 调用的模型后端 | 需要 | 第二步再用 | 你已经跑通 `rules`，想让控制器自动生成摘要、判定和数据计划 |

最重要的判断：

- 如果你现在只是想在训练机上开始自动训练，先走 `rules`。
- 如果你想让控制器自动和大模型交互，再切到 `opencode`。

## 2. `auto-train run` 会做什么

一条命令会串起下面这条流水线：

- `PLAN`
- `BUILD_DATASET`
- `TRAIN`
- `TEST`
- `EVALUATE`
- `SUMMARIZE`
- `JUDGE`
- `NEXT_ACTION`

也就是说，控制器会创建或恢复一个 study，把生成器、训练、测试、评估和下一轮决策接到一起。

当前已经具备的闭环：

- 能把 `dataset_plan` 传给生成器 `--preset / --override-file`
- 能在 `TEST` 后自动接上 `EVALUATE`
- 当前当控制器决定“新建一版样本”时，自动生成的数据集目录会固定命名为 `<study-name>_<trial-id>`：
  - 例如 `study_group1_firstpass_trial_0002`
  - 不再继续叠加 `_r0002_r0003...` 这类越来越长的目录名
- 当前在启用 `business_eval` 时，默认会切到“目标驱动停止”：
  - 结束条件是商业测试通过
  - 或人工 `STOP` 文件
  - 或进程/机器意外中断后用同一个 `study-name` 恢复继续

当前还没有完成的边界：

- 还没有完成 Windows + NVIDIA 训练机上的长流程稳定性验收
- 还不能宣称为“长期无人值守正式入口”

## 3. 开始前你必须已经有

- 已创建训练目录
- 已创建生成器工作区
- 已准备素材
- 至少跑通过一次手动训练、测试和评估主线

这里的“已准备素材”有一个新边界：

- 如果你的生成器工作区里激活的是完整素材包，`group1` / `group2` study 都可以直接复用
- 如果你只准备了 `group1` 或只准备了 `group2` 的单任务素材包，也可以启动自动训练
- 但单任务素材包第一次导入工作区时，要通过 `sinan-generator materials import --task <task>`、`materials fetch --task <task>`，或让 `make-dataset --materials-source` 按当前 task 自动导入

推荐先完成：

1. [训练者角色：训练机安装](./windows-bundle-install.md)
2. [训练者角色：使用生成器准备训练数据](./prepare-training-data-with-generator.md)
3. [训练者角色：使用训练器完成训练、测试与评估](./from-base-model-to-training-guide.md)

## 4. 训练机目录建议

推荐至少固定下面 3 个目录：

```text
D:\
  sinan-captcha-work\
  sinan-captcha-generator\
    workspace\
```

其中：

- `sinan-captcha-work`
  - 训练目录
  - 存放 `.opencode/`、`datasets/`、`runs/`、`reports/`、`studies/`
- `sinan-captcha-generator\workspace`
  - 生成器工作区
  - 存放素材、preset、cache

## 5. `rules` 路线怎么搭

这是当前最稳的训练机启动方式。

### 5.1 你需要什么

- `uv`
- 训练目录已经通过 `uvx --from sinan-captcha sinan env setup-train ...` 初始化
- `sinan-generator` 可执行
- 生成器工作区已初始化并已有素材
- 如果你未来要切到 `opencode`，训练目录中已经自动包含 `.opencode/commands` 和 `.opencode/skills`
- 如果当前工作区只激活了单任务素材包，study 的 `task` 必须和素材包任务一致

如果训练机上 `sinan-generator.exe` 不在 `PATH`，现在建议显式传：

- `--generator-executable C:\你的目录\sinan-generator.exe`

### 5.2 最小启动命令

#### `group1`

```powershell
Set-Location D:\sinan-captcha-work

uv run sinan auto-train run group1 `
  --study-name study_group1_firstpass `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --generator-executable D:\sinan-captcha-generator\sinan-generator.exe `
  --dataset-version firstpass `
  --judge-provider rules `
  --max-steps 8 `
  --max-hours 2 `
  --max-new-datasets 1
```

#### `group2`

```powershell
Set-Location D:\sinan-captcha-work

uv run sinan auto-train run group2 `
  --study-name study_group2_firstpass `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --generator-executable D:\sinan-captcha-generator\sinan-generator.exe `
  --dataset-version firstpass `
  --judge-provider rules `
  --max-steps 8 `
  --max-hours 2 `
  --max-new-datasets 1
```

第一次建议保守一点：

- `--judge-provider rules`
- `--max-steps 8`
- `--max-hours 2`
- `--max-new-datasets 1`

### 5.3 如何让 `group2` 朝“满足业务要求”自动收敛

当前版本里，`auto-train` 对 `group2` 的默认晋级门是：

- `point_hit_rate >= 0.93`
- `mean_iou >= 0.85`
- `mean_center_error_px <= 8.0`

也就是说，当前系统里的“满足业务要求”默认等价于上面这组阈值。

如果你只是第一次在训练机上跑通 `group2` 自动训练，先用：

```powershell
uv run sinan auto-train run group2 `
  --study-name study_group2_rules `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --generator-executable D:\sinan-captcha-generator\sinan-generator.exe `
  --dataset-version firstpass `
  --judge-provider rules `
  --max-steps 20 `
  --max-trials 20 `
  --max-hours 12 `
  --max-no-improve-trials 4 `
  --max-new-datasets 2
```

这条命令的推荐含义是：

- 先用 `fresh` 起步，默认模型会自动使用 `paired_cnn_v1`
- 如果判定结果要求继续调参，控制器会在后续 trial 自动切到 `from_run` 或 `resume`
- 如果失败模式显示数据契约有问题，控制器会触发 `REGENERATE_DATA`
- 当指标达到当前晋级门，或预算耗尽、连续无提升达到上限时，study 会停止

如果你已经跑通 `rules`，并且要让 OpenCode 参与摘要、判定和数据规划，再切到：

```powershell
uv run sinan auto-train run group2 `
  --study-name study_group2_llm `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --generator-executable D:\sinan-captcha-generator\sinan-generator.exe `
  --dataset-version firstpass `
  --judge-provider opencode `
  --judge-model gemma4 `
  --opencode-attach-url http://127.0.0.1:4096 `
  --max-steps 20 `
  --max-trials 20 `
  --max-hours 12 `
  --max-no-improve-trials 4 `
  --max-new-datasets 2
```

如果你的真实业务阈值不是上面这组默认值，就不要直接开跑。先把 `group2` 的策略门改成你的业务门，再启动 study：

- `core/auto_train/policies.py`

## 6. `opencode` 路线怎么搭

这条路线会让控制器自动和大模型交互，但前提是你先把 `rules` 路线跑通。

### 6.1 你额外需要什么

- 训练机上有 `opencode` 命令
- 有一个可供 OpenCode 使用的模型后端
- 训练目录已经通过 `env setup-train` 自动铺好 `.opencode/commands/` 和 `.opencode/skills/`

这里要分清楚：

- 如果 OpenCode 连远端模型服务，训练机不一定要本地安装大模型
- 如果 OpenCode 连本地模型服务，训练机就要本地准备模型后端

### 6.2 `skills` 怎么安装到训练机

当前项目里的 skills 不是单独的 pip 包。

它们当前会随着训练目录初始化一起落到本地文件：

- `D:\sinan-captcha-work\.opencode\commands\`
- `D:\sinan-captcha-work\.opencode\skills\`

因此当前不需要“单独安装 skill”。

确认下面两个目录存在即可：

- `D:\sinan-captcha-work\.opencode\commands`
- `D:\sinan-captcha-work\.opencode\skills`

然后直接从训练目录启动 `opencode serve`。

### 6.3 推荐部署方式

在训练机上：

```text
D:\
  sinan-captcha-work\
    .opencode\
    studies\
    datasets\
    runs\
    reports\
  sinan-captcha-generator\
    workspace\
```

然后：

1. 在 `D:\sinan-captcha-work` 里启动 OpenCode 服务
2. 在 `D:\sinan-captcha-work` 里启动 `auto-train`

### 6.4 启动 OpenCode 服务

在训练目录里：

```powershell
Set-Location D:\sinan-captcha-work
opencode serve --port 4096
```

### 6.5 启动 `auto-train`

```powershell
Set-Location D:\sinan-captcha-work

uv run sinan auto-train run group1 `
  --study-name study_group1_llm `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --generator-executable D:\sinan-captcha-generator\sinan-generator.exe `
  --dataset-version firstpass `
  --judge-provider opencode `
  --judge-model gemma4 `
  --opencode-attach-url http://127.0.0.1:4096 `
  --opencode-timeout-seconds 300 `
  --max-steps 8 `
  --max-hours 2 `
  --max-new-datasets 1
```

### 6.6 `opencode` 连通性自检与排错

如果你怀疑问题不是训练器本身，而是 OpenCode 或大模型后端没有连通，先不要直接重跑 `auto-train`，先在训练目录里做下面几步。

先确认命令本身存在：

```powershell
Set-Location D:\sinan-captcha-work
Get-Command opencode
```

如果这里报“找不到命令”，先解决 OpenCode 安装或 `PATH` 问题。

再确认训练目录已经铺好本地 commands 和 skills：

```powershell
Set-Location D:\sinan-captcha-work
Test-Path .opencode\commands\study-status.md
Test-Path .opencode\commands\judge-trial.md
Test-Path .opencode\skills\study-archivist\SKILL.md
Test-Path .opencode\skills\training-judge\SKILL.md
```

这 4 条都应该返回 `True`。

再用和当前控制器一致的调用方式做一次最小连通性测试。先不要再手写旧的 `--command` / `--file` 路线，当前控制器走的是 `message + inline files` 模式。

```powershell
Set-Location D:\sinan-captcha-work

opencode run `
  --attach http://127.0.0.1:4096 `
  --model gemma4 `
  --format json `
  --agent build `
  -- `
  'Return exactly this JSON object and nothing else: {"ok":true}'
```

如果这条命令最终能返回包含 `{"ok":true}` 的 JSON event，说明下面几层都已经通了：

- `opencode` 命令本身可执行
- `--attach` 能连上 `opencode serve --port 4096`
- `gemma4` 对应的模型后端可响应
- `--format json` 事件流可被正常输出到标准输出

如果最小连通性测试通过，再做一次和控制器完全一致的真实重放。不要自己改写 prompt，直接重放 trace 里记录下来的最终 message：

```powershell
Set-Location D:\sinan-captcha-work

$trace = Get-Content .\studies\group1\study_group1_llm\trials\trial_0001\opencode\0003_plan-dataset.json -Raw | ConvertFrom-Json

opencode run `
  --attach http://127.0.0.1:4096 `
  --model gemma4 `
  --format json `
  --agent build `
  -- `
  $trace.command[-1]
```

如果你当前 study 名、trial id 或 trace 文件名不一样，把上面路径换成你自己的目录。

判断标准：

- 能返回合法 JSON event，并且 `text` part 里包含最终对象：
  - 说明 OpenCode 和模型后端大概率已经连通，后续问题更可能在 `auto-train` 传参、文件路径或工件状态上
- 返回连接错误、超时或空输出：
  - 优先排查 `opencode serve` 是否还在运行、`--attach` 地址是否正确、模型后端是否可用
- stdout 以 `step_finish(reason="tool-calls")` 结束，且没有最终 JSON：
  - 说明这次 headless 调用停在了工具回合，没有真正产出最终对象
  - 优先升级到 `sinan-captcha==0.1.20` 或更高版本，再重新执行 `env setup-train`
  - 新版本会把 skill 指南直接内联到 prompt，不再要求 headless command 先调用 `skill` 工具
- stdout 只有 `step_start` 之类的起始 event，没有最终 JSON：
  - 说明这次 attach 调用返回了不完整事件流
  - 优先升级到 `sinan-captcha==0.1.20` 或更高版本，再重新执行 `env setup-train`
  - 新版本会把这类返回识别成 `opencode_incomplete_event_stream`，并在本机 attach 场景下自动做一次本地直连重试
- 返回 “File not found”：
  - 优先排查 trace 里引用的 study 目录、trial 目录和训练根目录是否一致

当前版本的控制器在 `--attach` 成功退出但 `stdout` 为空时，会自动再走一次不带 `--attach` 的本地直连重试，避免这类空输出直接让整轮 `auto-train` 退回本地 fallback。

当前版本的控制器还会把 `step_finish(reason="tool-calls")` 这种“只完成工具调用、没有最终 JSON”的事件流识别成 `opencode_incomplete_tool_calls`，不再把它记成普通成功返回。

如果你已经启用最新版本的 `auto-train`，控制器也会把每次发给 OpenCode 的内容和 OpenCode 返回的原始内容写到：

- `studies\<task>\<study-name>\opencode.log`
- `studies\<task>\<study-name>\trials\<trial_id>\opencode\*.json`

这两处是定位 “到底是没连上，还是连上了但判断不符合预期” 的第一现场。

## 7. 启动后控制器和大模型会怎么交互

只有在 `--judge-provider opencode` 时才会发生这部分交互。

当前控制器会调用 4 个 project-local command：

- `result-read`
  - 读取 `test.json` / `evaluate.json`
  - 输出 `result_summary.json`
- `judge-trial`
  - 读取当前 trial 摘要
  - 输出 `decision.json`
- `plan-dataset`
  - 读取当前失败模式和弱类
  - 输出 `dataset_plan.json`
- `study-status`
  - 读取 `study.json` / `leaderboard.json`
  - 输出 `study_status.json`

这意味着启动后：

- 控制器会自动和 OpenCode 交互
- OpenCode 会基于这些工件返回结构化 JSON
- 控制器再继续推进下一阶段
- 控制器会把“发给 OpenCode 的内容”和“OpenCode 返回的原始内容”同时打印到终端并写入日志

你最终能看到的“分析报告/判断结果”主要是：

- `trials/<trial_id>/result_summary.json`
- `trials/<trial_id>/decision.json`
- `trials/<trial_id>/dataset_plan.json`
- `study_status.json`
- `summary.md`

其中：

- `result_summary.json` 是 trial 级压缩分析
- `decision.json` 是下一步动作判断
- `dataset_plan.json` 是下一轮数据策略
- `summary.md` 是 study 级摘要，第一眼先看这里

## 7.1 把真实样本 business gate 接到最终停止条件

如果你希望 `group2` 不是“达到训练指标就停”，而是“必须通过真实样本遮挡验证才停”，可以额外传入：

```powershell
uv run sinan auto-train run group2 `
  --study-name study_group2_llm `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-generator\workspace `
  --business-eval-dir D:\sinan-captcha-work\business_eval\group2 `
  --business-eval-success-threshold 0.98 `
  --business-eval-min-cases 100 `
  --business-eval-sample-size 100 `
  --business-eval-occlusion-threshold 0.78
```

推荐目录：

- 建议直接放在训练根目录下：
  - `D:\sinan-captcha-work\business_eval\group2`
- 这样做的好处是：
  - 训练数据 `datasets/`、训练产物 `runs/`、商业验收样本 `business_eval/` 在同一个训练根目录里，便于迁移和复盘
  - 启动命令不需要再额外记一条独立磁盘路径

`--business-eval-dir` 的目录约定：

- 可以直接放一组样本：
  - `master.png`
  - `tile.png`
  - 或 `bg.jpg`
  - 或 `gap.jpg`
- 也可以放多组子目录：
  - `case_0001/master.png`
  - `case_0001/tile.png`
  - `case_0002/master.png`
  - `case_0002/tile.png`
  - 或者像你的真实样本一样：
  - `20260407190052_2/bg.jpg`
  - `20260407190052_2/gap.jpg`
  - `20260407190323_4/bg.jpg`
  - `20260407190323_4/gap.jpg`

当前兼容的文件名别名：

- 背景图：`master.*`、`bg.*`、`background.*`
- 缺口块：`tile.*`、`gap.*`、`piece.*`、`puzzle_piece.*`

关于 `gap.jpg` / `tile.jpg`：

- 当前商业验收不再强依赖透明 PNG 的 alpha 通道。
- 如果 `gap/tile` 本身已经带透明边缘，运行时会直接使用原始 alpha。
- 如果 `gap/tile` 是像你的真实样本那样的 `jpg` 小图，运行时会根据图块四周的背景颜色自动提取轮廓掩码，再用于：
  - `group2` 推理输入
  - 商业验收贴回评分
- 这意味着 `bg.jpg + gap.jpg` 现在可以直接参与商业验收，不需要先手工改成透明 PNG。

启用后，控制器会在“训练指标已达标、当前候选被判为 `PROMOTE_BRANCH`”时额外执行一轮商业验收 gate：

1. 用当前 `group2` 模型预测缺口位置
2. 把 `tile` 贴回 `master`
3. 在模型输出位置附近做一圈局部搜索，尝试把缺口块在附近轻微挪动
4. 比较当前 overlay 与附近候选 overlay，判断当前结果是否已经接近附近最干净的贴合位置
5. 从 `--business-eval-dir` 中稳定随机抽取最多 `100` 组样本进行本轮验收
6. 统计这 `100` 组样本的成功率
7. 只有当成功率达到 `98%` 且本轮验收样本数达到 `100` 时，study 才会真正停止

这里还有一个重要变化：

- 只要配置了 `--business-eval-dir`，当前 study 默认就会进入“目标驱动停止”模式
- 这意味着：
  - 默认不再因为 `max_trials / max_hours / max_new_datasets / max_no_improve_trials / plateau` 自动停止
  - 进程会持续跑，直到：
    - 商业测试通过
    - 你手工放置 `STOP` 文件
    - 或进程/机器被意外中断
- 意外中断后，用同一个 `--study-name` 重启命令即可恢复

当前 `group2` 商业验收的主判标准已经从“背景图里反推参考槽位”调整为“轮廓重合率主判 + overlay 痕迹辅判 + 局部 10px 容差”。

- 旧规则的问题是：它需要在背景图里猜一个“参考缺口位置”，本质上仍是启发式假设。
- 真实业务图里更接近人眼判断的方式是：
  - 图块轮廓有没有真正压到背景缺口轮廓上
  - overlay 后是否还露出明显缺口边缘
  - 是否出现双轮廓/重影
  - 是否有明显越界边缘
- 因此当前商业测试会直接分析当前 `overlay`，并把“轮廓是否重合”作为主判：
  - `contour_overlap_ratio`：图块轮廓与背景缺口轮廓的重合率，越高越好
  - `exposed_gap_edge_ratio`：overlay 后仍露出的缺口边缘比例，越低越好
  - `double_contour_ratio`：overlay 后出现双轮廓/重影的比例，越低越好
  - `tile_residue_ratio`：overlay 中是否还能看到大面积图块痕迹，越低越好
  - `overflow_edge_score`：是否有明显越界边缘，越低越好
  - `clean_score(occlusion_score)`：当前位置整体贴合得有多干净，越高越好
- 同时程序会在模型输出位置附近做一圈局部搜索：
  - `best_local_bbox`
  - `best_local_offset_px`
  - `best_local_clean_score`
- 当前单样本通过条件变成：
  - 模型输出位置与邻域内最干净位置的边框偏差 `<= 10px`
  - 当前模型输出位置的 `contour_overlap_ratio >= 0.55`
  - 当前模型输出位置的 `double_contour_ratio <= 0.45`
  - 当前模型输出位置的 `overflow_edge_score <= 0.40`
  - 当前模型输出位置的 `clean_score >= effective_clean_threshold`
    - `effective_clean_threshold = max(0.72, --business-eval-occlusion-threshold - 0.06)`
  - `exposed_gap_edge_ratio` 与 `tile_residue_ratio` 当前继续保留在日志里做辅诊断，但不再单独作为硬门
- `boundary_before / boundary_after / fill_score / seam_score` 当前仍会保留为兼容旧日志的辅诊断字段：
  - `fill_score` 现等价于 `contour_overlap_ratio`
  - `seam_score` 现表示边缘干净程度
  - `boundary_before / boundary_after` 现用于辅助表达露边和越界诊断

这里的“稳定随机抽样”指的是：

- 每个候选 `trial` 都会随机抽取一批样本
- 同一个 `trial` 重跑时，抽中的样本保持一致，便于复盘
- 新的 `trial` 会抽到不同的 100 组样本
- 当目录内总样本数少于 100 时，本轮会跑全部样本，但不会达到正式商业验收门

当前会额外落盘：

- `trials/<trial_id>/business_eval.json`
- `trials/<trial_id>/business_eval.md`
- `trials/<trial_id>/business_eval.log`
- `trials/<trial_id>/business_eval/<case_id>/overlay.png`
- `trials/<trial_id>/business_eval/<case_id>/diff.png`
- `commercial_report.md`

其中：

- `business_eval.json` 是结构化明细，适合机器读取
- `business_eval.md` 是中文摘要
- `business_eval.log` 是逐 case 文本日志，当前会先写“字段说明 / 数据来源”，再记录：
  - `predicted_bbox / predicted_center / inference_ms`
    - 这些字段直接来自 `group2` 求解模块的推理输出
  - `best_local_bbox / best_local_offset_px / best_local_clean_score`
    - 这些字段来自局部邻域搜索，用来表示“当前位置附近最干净的贴合位置”以及模型输出与它的偏差
  - `contour_overlap_ratio / exposed_gap_edge_ratio / double_contour_ratio`
    - 这些字段直接描述当前 overlay 中图块轮廓是否和背景缺口轮廓重合、是否露边、是否出现双轮廓
  - `tile_residue_ratio / double_edge_score / overflow_edge_score`
    - 这些字段描述当前 overlay 中是否还存在明显图块残留、双边缘和越界边缘
  - `result_cn / final_score / required_score / failed_checks_cn`
    - 这些字段直接给出逐样本中文结论、最终得分、要求得分以及未通过项
  - `clean_score`
    - 这些字段由商业测试评分模块计算
    - 表示当前模型输出位置的整体贴合干净程度，越高越好
    - 当前它是参考分，不再是唯一决定单样本 PASS/FAIL 的硬门
  - `success_rate / commercial_ready`
    - 这些字段表示整批真实样本的通过率和是否达到最终商用门
- `commercial_report.md` 是最终人类可读报告，当前固定包含：
  - 最终结论
  - 流程状态
  - 训练过程结论
  - 晋级结论
  - 商业测试结论
  - 商业测试字段说明
- `summary.md` / `study_status.json` 当前也会额外写出：
  - `final_reason`
  - `final_detail`
  - 用来区分“流程正常停止”和“商业测试通过”
- `business_eval.log` 的逐 case 行当前会记录：
  - `predicted_bbox`
  - `predicted_center`
  - `best_local_bbox`
  - `best_local_offset_px`
  - `best_local_clean_score`
  - `contour_overlap_ratio`
  - `exposed_gap_edge_ratio`
  - `double_contour_ratio`
  - `result_cn`
  - `final_score`
  - `required_score`
  - `failed_checks_cn`
  - `inference_ms`
  - `clean_score`
  - `tile_residue_ratio`
  - `double_edge_score`
  - `overflow_edge_score`
  - `PASS/FAIL`

当前 `leaderboard.json` / `best_trial.json` 也已经不再只按离线 `primary_score` 排序。

- 旧规则的问题是：如果很多 trial 的 `point_hit_rate` 都是 `1.0`，最早的简单样本轮次会一直排第一。
- 当前排行榜会综合考虑：
  - `offline_score`：离线指标组合分，来自 `point_hit_rate + mean_iou + mean_center_error_px`
  - `difficulty_score`：当前数据版本的策略难度系数，不是从图片像素里算出来的，而是来自 `dataset_preset + 数据重生深度`
    - `smoke = 0.85`
    - `firstpass = 1.00`
    - `hard = 1.12`
    - 每增加一层重生版本深度，再额外加 `0.02`，最多加到 `0.08`
  - `business_success_rate`：当前真实业务样本通过率
  - `commercial_ready`：当前是否已经达到最终商业门
- 这 4 项会汇总成 `ranking_score`，`leaderboard.json` 与 `best_trial.json` 当前都按这个综合分选“最佳 trial”。
- 当前具体公式是：
  - `center_quality = clamp(1 - mean_center_error_px / 12, 0..1)`
  - `offline_score = 0.50 * point_hit_rate + 0.30 * mean_iou + 0.20 * center_quality`
  - `difficulty_score = preset_weight + min(regenerate_depth * 0.02, 0.08)`
  - `business_component = business_success_rate * 0.75 + (commercial_ready ? 0.25 : 0.0)`
  - `ranking_score = offline_score * difficulty_score + business_component * 0.35`
- 你可以直接在 `studies/<task>/<study-name>/leaderboard.json` 里看每个 trial 的：
  - `offline_score`
  - `difficulty_score`
  - `business_success_rate`
  - `commercial_ready`
  - `ranking_score`
- 因此：
  - 离线同分时，不会再默认让 `trial_0001` 永远排第一
  - 更难的数据版本、真实业务通过率更高的 trial，会被更优先地视为当前最佳候选
  - 下一轮 `from_run` 默认会优先继承这个综合最佳 trial
  - 当前还会自动清理模型目录，只保留综合评分最优的前 3 个 run，其他 trial 的模型目录会被删除

注意：

- 启用 business gate 后，`PROMOTE_BRANCH` 当前表示“训练指标达标的候选”，不再等同于“已经达到商用门”
- 当前 business gate 不是“每固定 N 轮就跑一次”，而是“某个 `trial` 先被判成候选晋级时才跑一次”
- 当前 `group2 + business gate` 已改为“商用目标优先”的搜索闭环：
  - 如果本轮已经通过 business gate，study 才真正 `STOP`
  - 如果本轮还没有进入候选晋级区间，下一轮默认也会进入 `REGENERATE_DATA`
  - 如果本轮进入候选晋级区间但 business gate 未通过，下一轮同样会进入 `REGENERATE_DATA`
  - 也就是说，只要还没达到最终商用门，下一轮默认就是：
    - 新数据版本
    - 基于当前最佳 run 继续训练
- `group2` 的离线晋级阈值和商业测试阈值当前不是同一个指标体系：
  - 离线晋级看 `point_hit_rate / mean_iou / mean_center_error_px`
  - 最终停止看真实样本 `business_success_rate`
  - 但控制器当前已把离线晋级和调参动作都收口为“服务于最终 business gate”
- 当前商业验收默认门槛：
  - `business_eval_success_threshold = 0.98`
  - `business_eval_min_cases = 100`
  - `business_eval_sample_size = 100`
- 当 business gate 已启用时，当前默认不会因为：
  - `max_trials`
  - `max_hours`
  - `max_new_datasets`
  - `max_no_improve_trials`
  - `plateau`
  提前停掉 study
- 目标驱动模式下，真正会结束 study 的条件是：
  - 商业测试通过
  - `STOP` 文件
  - 或进程/机器中断后等待你恢复
- 如果终端输出 `final_stage=STOP`，不要直接理解成“商业测试通过”
  - 还需要继续看 `study_status`、`commercial_ready`、`final_reason`
- 当前 CLI 退出码语义：
  - `0`：本次流程正常结束，且最终业务目标达成，或者本次只是中途返回
  - `2`：本次流程被 stop rule 停止，但最终没有达到商用门

如果你要排查 “OpenCode 到底看了什么、怎么判断的、怎么生成数据计划的”，再额外看：

- `opencode.log`
- `trials/<trial_id>/opencode/*.json`
- `opencode/*.json`

其中：

- `opencode.log` 是 study 级串行文本日志，适合直接在终端或编辑器里追
- `trials/<trial_id>/opencode/*.json` 是 trial 级结构化 trace，重点看 `judge-trial`、`result-read`、`plan-dataset`
- `opencode/*.json` 是 study 级结构化 trace，重点看 `study-status`
- 每份 trace 都会包含：
  - 实际调用的 OpenCode command 名称
  - 命令模板 `.opencode/commands/*.md` 的文本
  - 对应 skill `.opencode/skills/*/SKILL.md` 的文本
  - 附带给 OpenCode 的文件路径和文件内容预览
  - 原始 `stdout`
  - 原始 `stderr`
  - 是否成功和错误信息

## 8. 必填参数和常用参数

### 8.1 必填参数

| 参数 | 说明 |
| --- | --- |
| `group1` / `group2` | 位置参数，指定专项。 |
| `--study-name` | study 名称。目录会落在 `studies/<task>/<study-name>/`。 |
| `--train-root` | 训练目录根，例如 `D:\sinan-captcha-work`。 |
| `--generator-executable` | 可选但在 Windows 上强烈建议显式传。填 `sinan-generator.exe` 的完整路径，避免找不到生成器命令。 |
| `--generator-workspace` | 生成器工作区目录。 |

### 8.2 运行批次与停止参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--max-steps` | `business_eval 开启时为 0，否则为 1` | `0` 表示本次命令持续运行直到真正 `STOP`；正整数表示本次命令最多执行多少个阶段胶囊，不是 trial 数。 |
| `--goal-only-stop` | 关 | 显式开启“只按目标停止”。当前只要配置了 `--business-eval-dir`，即使不写这个参数也会自动开启。 |
| `--max-trials` | `20` | 整个 study 最多完成多少个 trial。启用目标驱动停止时，这个上限只会被记录，不再自动触发 stop rule。 |
| `--max-hours` | `24` | 整个 study 的总小时预算。启用目标驱动停止时，这个上限只会被记录，不再自动触发 stop rule。 |
| `--max-new-datasets` | 无 | 最多允许新建多少个新数据版本，不含最初的 `dataset-version`。启用目标驱动停止时，这个上限只会被记录，不再自动触发 stop rule。 |
| `--max-no-improve-trials` | `4` | 连续多少个 trial 没有明显提升就停。启用目标驱动停止时，这个上限只会被记录，不再自动触发 stop rule。 |

### 8.3 判定与 OpenCode 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--judge-provider` | `rules` | 判定器。常用值是 `rules` 或 `opencode`。 |
| `--judge-model` | `policy-v1` | `rules` 路线下它更像策略名；`opencode` 路线下它会传给 OpenCode 的 `--model`。 |
| `--opencode-attach-url` | 无 | `judge-provider=opencode` 时，连接已有 OpenCode 服务。 |
| `--opencode-binary` | `opencode` | `judge-provider=opencode` 时使用的本地命令。 |
| `--opencode-timeout-seconds` | `300` | 单次 OpenCode 调用超时。本地 `ollama/*` 大模型建议至少 `300`，慢机型可调到 `600`。 |

### 8.4 训练与评估参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--dataset-version` | `v1` | 第一轮 trial 使用的数据版本。 |
| `--train-name` | 当前 `trial_id` | 第一轮训练运行名。 |
| `--train-mode` | `fresh` | `fresh`、`resume`、`from_run`。 |
| `--base-run` | 无 | `from_run` 时的来源 run。 |
| `--model` | 无 | 显式覆盖训练模型。 |
| `--epochs` | 无 | 显式覆盖训练轮数。 |
| `--batch` | 无 | 显式覆盖 batch size。 |
| `--imgsz` | `group1=640`、`group2=192` | 显式覆盖训练尺寸。 |
| `--device` | `0` | 训练设备。 |
| `--gold-dir` | 无 | 如果你要用自定义 gold 标签目录评估，就显式传入。 |
| `--prediction-dir` | 无 | 如果你要用自定义预测目录评估，就显式传入。 |

## 9. 恢复、暂停和单步调试

### 9.1 恢复已有 study

用同一个 `--study-name`、`--train-root` 和 `--generator-workspace` 重新执行原命令即可。控制器会根据已有工件推断下一阶段。

当前支持恢复的场景：

- 你主动按下 `Ctrl+C`
- 训练机重启
- 终端或 Python 进程意外退出
- `opencode` / 训练器 / 生成器等外部进程临时失败后，你修好环境再重新执行

恢复时不需要手工指定“从哪一轮开始”。控制器会读取：

- `study.json`
- 当前 `trial_xxxx` 目录已有工件
- `STOP` 文件是否存在

然后自动推断从：

- `PLAN`
- `BUILD_DATASET`
- `TRAIN`
- `TEST`
- `EVALUATE`
- `SUMMARIZE`
- `JUDGE`
- `NEXT_ACTION`

中的哪一层继续。

### 9.2 请求停止

如果你想让 study 在下一次停止检查时停下来，在 study 根目录放一个 `STOP` 文件：

```text
studies\
  group1\
    study_group1_firstpass\
      STOP
```

### 9.3 只跑一个阶段

```powershell
uv run sinan auto-train stage BUILD_DATASET group1 `
  --study-name study_group1_firstpass `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace
```

## 10. Study 目录里会看到什么

你至少会看到：

- `study.json`
- `leaderboard.json`
- `summary.md`
- `trials/trial_0001/...`

常见文件含义：

| 文件 | 作用 |
| --- | --- |
| `study.json` | study 级元数据、预算和当前 trial 指针。 |
| `leaderboard.json` | 当前 study 的试验排行榜。 |
| `summary.md` | study 级中文摘要，第一眼先看这里。 |
| `opencode.log` | 按时间顺序记录每次发送给 OpenCode 的输入和返回内容。 |
| `trials/trial_0001/input.json` | 这一轮 trial 的输入参数。 |
| `trials/trial_0001/dataset_plan.json` | 如果控制器决定重生数据，这里会记录新数据计划。 |
| `trials/trial_0001/generator_override.json` | 真正传给生成器的覆盖 JSON。 |
| `trials/trial_0001/train.json` | 训练命令与训练结果摘要。 |
| `trials/trial_0001/test.json` | 测试命令与测试结果摘要。 |
| `trials/trial_0001/evaluate.json` | 评估结果摘要。 |
| `trials/trial_0001/result_summary.json` | 给判定器消费的压缩摘要。 |
| `trials/trial_0001/decision.json` | 这一轮的决策结果。 |
| `trials/trial_0001/opencode/*.json` | `result-read` / `judge-trial` / `plan-dataset` 的原始 trace。 |
| `trials/trial_0001/opencode/*.stdout.txt` | 每次 OpenCode 调用的原始标准输出，不经过 JSON 二次包装，优先用于排查模型到底返回了什么。 |
| `trials/trial_0001/opencode/*.stderr.txt` | 每次 OpenCode 调用的原始标准错误。 |
| `opencode/*.json` | `study-status` 这类 study 级 OpenCode trace。 |

## 11. 推荐的观察顺序

每轮至少看这 4 个位置：

1. `studies/<task>/<study-name>/summary.md`
2. `studies/<task>/<study-name>/leaderboard.json`
3. `studies/<task>/<study-name>/trials/<trial_id>/input.json`
4. `studies/<task>/<study-name>/trials/<trial_id>/decision.json`

如果控制器开始重生数据，再额外看：

- `dataset_plan.json`
- `generator_override.json`

如果你在确认大模型到底是怎么判断的，再额外看：

- `opencode.log`
- `trials/<trial_id>/opencode/0001_judge-trial.json`
- `trials/<trial_id>/opencode/0001_judge-trial.stdout.txt`
- `trials/<trial_id>/opencode/0001_plan-dataset.json`
- `trials/<trial_id>/opencode/0001_plan-dataset.stdout.txt`

排查优先级建议：

- 先看 `*.stdout.txt`，这是模型原始返回，最接近真实现场
- 再看 `opencode.log`，这里会串行记录 `trace_file`、`raw_stdout_file`、`raw_stderr_file` 和同一次调用的上下文
- 最后再看 `*.json` trace，用来对照命令参数、附带文件和运行时判定分支

## 12. 当前最重要的现实边界

- `rules` 路线现在已经适合训练机开始受控自动训练
- `opencode` 路线需要额外准备 `opencode` 和可用的大模型后端
- 当前 `.opencode/commands + .opencode/skills` 会在 `env setup-train` 时自动落到训练目录
- 当前还没有完成 Windows + NVIDIA 训练机上的长流程验收，因此不要直接长时间无人看守运行

## 13. 下一步

如果你想先手工确认训练结果，再决定是否继续自动化，回到：

- [训练者角色：使用训练器完成训练、测试与评估](./from-base-model-to-training-guide.md)
