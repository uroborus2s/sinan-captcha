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
- 能按 `max_hours`、`max_trials`、`max_new_datasets`、`max_no_improve_trials` 停止

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

启用后，控制器会在“训练指标已达标、当前候选被判为 `PROMOTE_BRANCH`”时额外执行一轮商业验收 gate：

1. 用当前 `group2` 模型预测缺口位置
2. 把 `tile` 贴回 `master`
3. 计算边界残差改善和拼缝质量，得到 `occlusion_score`
4. 从 `--business-eval-dir` 中稳定随机抽取最多 `100` 组样本进行本轮验收
5. 统计这 `100` 组样本的成功率
6. 只有当成功率达到 `98%` 且本轮验收样本数达到 `100` 时，study 才会真正停止

这里的“稳定随机抽样”指的是：

- 每个候选 `trial` 都会随机抽取一批样本
- 同一个 `trial` 重跑时，抽中的样本保持一致，便于复盘
- 新的 `trial` 会抽到不同的 100 组样本
- 当目录内总样本数少于 100 时，本轮会跑全部样本，但不会达到正式商业验收门

当前会额外落盘：

- `trials/<trial_id>/business_eval.json`
- `trials/<trial_id>/business_eval.md`
- `trials/<trial_id>/business_eval/<case_id>/overlay.png`
- `trials/<trial_id>/business_eval/<case_id>/diff.png`
- `commercial_report.md`

注意：

- 启用 business gate 后，`PROMOTE_BRANCH` 当前表示“训练指标达标的候选”，不再等同于“已经达到商用门”
- 当前商业验收默认门槛：
  - `business_eval_success_threshold = 0.98`
  - `business_eval_min_cases = 100`
  - `business_eval_sample_size = 100`
- 当 business gate 已启用但尚未通过时，控制器当前不会因为 `plateau` 或 `max_no_improve_trials` 提前停掉 study
- 真正的硬停止条件仍然是：
  - `max_trials`
  - `max_hours`
  - `max_new_datasets`
  - `STOP` 文件
  - 或手动中断

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

### 8.2 预算与停止参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--max-steps` | `1` | 本次命令最多执行多少个阶段胶囊，不是 trial 数。 |
| `--max-trials` | `20` | 整个 study 最多完成多少个 trial。 |
| `--max-hours` | `24` | 整个 study 的总小时预算。 |
| `--max-new-datasets` | 无 | 最多允许新建多少个新数据版本，不含最初的 `dataset-version`。 |
| `--max-no-improve-trials` | `4` | 连续多少个 trial 没有明显提升就停。 |

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
