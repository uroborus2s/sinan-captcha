# 搭建训练环境并完成模型训练

- 文档状态：草稿
- 当前阶段：IMPLEMENTATION
- 目标读者：零基础训练操作者、项目维护者
- 负责人：Codex
- 最近重构：2026-04-02
- 关联需求：`REQ-001`、`REQ-002`、`REQ-003`、`REQ-005`、`REQ-006`、`REQ-007`、`REQ-008`

## 0. 先把 5 个概念分清

这是当前项目最容易混淆的部分。现在统一按下面 5 层理解：

- 基础模型：训练起点权重，例如 `yolo26n.pt`
- 项目仓库：保存源码、脚本、配置、文档和构建产物定义的地方
- 训练工作目录：训练机上的运行现场，保存数据、日志、权重和报告
- 内部生成器：负责导出图片和真值标签的工具，不等于对外验证码服务
- 训练链路：把 JSONL 主事实源转换、训练、评估和回灌的流程

关系是这样的：

1. 内部生成器导出 `query/`、`scene/`、`labels.jsonl`、`manifest.json`
2. 训练链路读取 JSONL 主事实源
3. 转换脚本生成 YOLO 训练目录和 `dataset.yaml`
4. YOLO 微调基础模型，产出专项模型
5. 评估和失败样本回灌决定下一轮数据和模型版本

结论：

- 训练工作目录不是仓库
- 仓库也不是训练结果目录
- 仓库负责“工具和契约”
- 工作目录负责“数据和运行结果”

## 1. 这份手册为什么要重构

旧版本手册已经和当前设计、目录边界、以及仓库骨架有 4 个主要偏差：

1. 旧版本默认先部署 `go-captcha-service`，但新设计已经改成“优先自有生成逻辑或内部离线生成器，不要求先起完整服务”。
2. 旧版本把训练步骤和仓库结构混在一起，没有讲清“项目仓库”和“训练工作目录”的分工。
3. 旧版本引用了尚未落地或已改名的脚本名称，例如 `build_group1_yolo.py`、`build_group2_yolo.py`。
4. 旧版本默认读者可以直接使用完整自动标注、评估和后处理入口，但当前仓库里这些能力仍有一部分处于脚手架状态。

因此，本手册现在的目标不是重复设计文档，而是：

- 告诉你当前仓库已经能直接用哪些产出物
- 告诉你哪些步骤仍需按 checklist 或外部工具补齐
- 给出一条与现有仓库骨架一致的最小闭环路径

## 2. 当前仓库已经落地到什么程度

先不要假设仓库已经“一键全自动”。截至 2026-04-02，当前状态如下：

| 能力 | 当前状态 | 你怎么用 |
|---|---|---|
| Go 第一专项生成器 CLI | 已有骨架，可编译、可导出批次 | 编译 `sinan-click-generator.exe`，导出 `query/`、`scene/`、`labels.jsonl` |
| JSONL 读取与基础校验 | 已实现 | 用 `core.dataset.cli` 做快速读盘校验 |
| JSONL 转 YOLO | 已实现 | 用 `scripts/convert/build_yolo_dataset.py` 生成 `yolo/` 和 `dataset.yaml` |
| 第一专项训练命令组织 | 已实现 | 用 `core.train.group1.cli` 或 `scripts/train/train_group1.ps1` 生成标准训练命令 |
| 第二专项训练命令组织 | 已实现 | 用 `core.train.group2.cli` 或 `scripts/train/train_group2.ps1` 生成标准训练命令 |
| 环境自检脚本 | 已有最小版本 | 用 `scripts/ops/check-env.ps1` 做基础 GPU 可见性检查 |
| 第二专项自动标注 | 仅脚手架 | 当前仍需按 checklist 和外部工具执行 |
| 统一评估入口 | 仅脚手架 | 当前仍以 YOLO 原生结果和人工汇总为主 |
| 推理后处理 | 仅接口骨架 | 第一专项顺序映射、第二专项中心点后处理尚未实装 |

这意味着：

- 现在可以真实跑通的是：环境准备、第一专项样本导出、JSONL 校验、YOLO 转换、训练命令生成
- 现在还不能假装已经完整跑通的是：自动标注、统一评估、推理后处理全自动化

## 3. 新设计下的主线结论

当前版本固定这 6 条规则：

1. 不默认先部署完整验证码服务。
2. 先把“仓库”和“训练工作目录”分开。
3. Go 生成器和 Python 训练链路通过文件契约对接。
4. 标签主事实源始终是 JSONL，不是 YOLO 文本标签。
5. 第一专项和第二专项分开建数据、分开训练、分开验收。
6. 自动标注优先，但当前仓库尚未把自动标注完整做完，所以要明确哪些步骤还是人工或外部工具承担。

如果你只记一个结论，就记这个：

`先准备训练机和工作目录，再把仓库产物部署进去，最后按 JSONL -> YOLO -> 训练 的顺序跑闭环。`

## 4. 先决定你走哪条生成路线

不要一上来就默认 `go-captcha-service`。

### 路线 A：你已经有自有验证码生成逻辑

这是第一优先级。

做法：

1. 在自有生成逻辑上补“导出图片 + 导出标签”能力
2. 直接输出到训练工作目录
3. 跳过完整验证码服务部署

适用条件：

- 你能改生成代码
- 你能直接拿到真值标签

### 路线 B：你没有现成生成逻辑，但能接受内部离线生成器

这是当前仓库最贴近的路线。

做法：

1. 编译 Go 生成器二进制
2. 准备素材目录
3. 导出批次到工作目录

适用条件：

- 你能准备背景图、图标图和类别表
- 你接受先跑离线生成，不追求先上线业务服务

### 路线 C：你只有公开验证码服务接口

这不是推荐主线。

原因：

- 公开接口通常只能稳定拿到图片
- 训练需要的是真值标签，不只是图片
- 第一专项还需要目标顺序和干扰项框

只有当你短期内完全拿不到生成端源码时，才把它当临时过渡方案；即便如此，也仍要尽快补“内部导出模式”。

## 5. 先把目录边界搭好

当前版本建议把仓库和工作目录拆成两个根目录：

```text
D:\
  sinan-captcha-repo\
  sinan-captcha-work\
```

推荐分工如下：

### 5.1 项目仓库

```text
D:\sinan-captcha-repo\
  docs\
  generator\
  core\
  scripts\
  tests\
  configs\
  materials\
  dist\
```

职责：

- 保存源码、脚本、设计文档和构建产物定义
- 负责编译 Go 生成器
- 负责运行 Python 训练链路脚本

### 5.2 训练工作目录

```text
D:\sinan-captcha-work\
  datasets\
    group1\
      v1\
        raw\
        interim\
        reviewed\
        yolo\
        reports\
    group2\
      v1\
        raw\
        interim\
        reviewed\
        yolo\
        reports\
  runs\
  reports\
  tools\
    generator\
  materials\
  models\
```

职责：

- 保存运行期样本、训练结果、报告和二进制
- 不作为仓库事实源
- 不要求提交到 Git

### 5.3 关于 `configs/workspace.example.yaml`

仓库里有一份工作区示例配置：

- `configs/workspace.example.yaml`

它表达的是当前推荐边界：

- `repo_root` 指向仓库
- `work_root` 指向训练工作目录

注意：

- 这份配置当前还是“约定示例”
- 现有脚本还没有统一自动读取它
- 现阶段请继续在命令里显式传绝对路径

## 6. 第一步：先把训练机环境搭起来

环境搭建先按下面顺序完成。你至少要达到这些状态，才进入后续步骤：

- `nvidia-smi` 正常
- `python -c "import torch; print(torch.cuda.is_available())"` 输出 `True`
- `uv` 和 Python 3.11 已装好
- 已准备独立工作目录

推荐顺序：

1. 安装并确认 NVIDIA 驱动
2. 安装 `uv`
3. 安装 Python 3.11
4. 创建虚拟环境
5. 安装 PyTorch GPU 版
6. 安装 `ultralytics`、`opencv-python` 等训练依赖
7. 运行环境检查脚本

如果你只是不确定 CUDA 版本怎么看，再补读：

- [如何确认 Windows 电脑上的 CUDA 版本](./how-to-check-cuda-version.md)

仓库里还提供了一个最小环境检查脚本：

```powershell
Set-Location D:\sinan-captcha-repo
.\scripts\ops\check-env.ps1
```

这一步只检查：

- 驱动是否可见
- Python 是否能看到 CUDA

它不替代完整环境 checklist。

## 7. 第二步：把仓库产物部署到训练机

### 7.1 准备仓库

建议把仓库放到单独目录，例如：

```powershell
Set-Location D:\
git clone <你的仓库地址> sinan-captcha-repo
Set-Location D:\sinan-captcha-repo
```

### 7.2 编译 Go 生成器

当前仓库第一专项生成器需要你手工编译：

```powershell
Set-Location D:\sinan-captcha-repo\generator
go build -o ..\dist\generator\windows-amd64\sinan-click-generator.exe .\cmd\sinan-click-generator
```

编译成功后，复制到工作目录：

```powershell
New-Item -ItemType Directory -Force D:\sinan-captcha-work\tools\generator | Out-Null
Copy-Item D:\sinan-captcha-repo\dist\generator\windows-amd64\sinan-click-generator.exe D:\sinan-captcha-work\tools\generator\
```

### 7.3 准备素材

当前生成器运行时依赖素材目录。你需要准备：

- 背景图
- 图标图
- 类别表

推荐把运行时素材放在工作目录：

```text
D:\sinan-captcha-work\materials\
```

原因：

- 它们属于训练运行资产
- 不应和仓库源码强耦合

如果你只是本地开发，也可以暂时从仓库里的 `materials/` 占位目录起步，但正式训练时应使用独立素材包。

### 7.4 Python 侧当前怎么运行

当前仓库还没有把训练依赖完整写进 `pyproject.toml`。

所以现阶段要分两层理解：

- 仓库代码通过 `uv run python ...` 调用
- PyTorch、Ultralytics、OpenCV 等训练依赖仍按环境 checklist 手工安装

不要误以为只做 `uv sync` 就已经具备完整训练依赖。

## 8. 第三步：导出第一批样本

### 8.1 第一专项当前可直接用仓库骨架导出

先准备：

- 生成器二进制
- 生成器配置文件
- 素材目录

然后从仓库根目录执行：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\export\export_group1_batch.py `
  --binary D:\sinan-captcha-work\tools\generator\sinan-click-generator.exe `
  --config D:\sinan-captcha-repo\generator\configs\default.yaml `
  --materials-root D:\sinan-captcha-work\materials `
  --output-root D:\sinan-captcha-work\datasets\group1\v1\raw
```

当前第一专项生成器会在 `output-root` 下再创建一个批次目录，例如：

```text
D:\sinan-captcha-work\datasets\group1\v1\raw\batch_0001\
  query\
  scene\
  labels.jsonl
  manifest.json
```

### 8.2 第二专项当前不应假装已经有同等仓内导出脚本

截至当前版本：

- 仓库里还没有第二专项对等的生成器导出入口
- 第二专项样本导出仍应来自你的自有生成逻辑、内部离线脚本或外部受控工具

但无论你用哪种方式，最终都要满足统一目录和字段要求。最少要保证：

- 顶层字段有 `sample_id`、`query_image`、`scene_image`、`label_source`、`source_batch`
- 第一专项有 `targets[]` 和 `distractors[]`
- 第二专项有 `target`

另外要特别注意当前仓库实现约束：

- 转换器现在要求每个目标对象都带 `class_id`
- 第一专项的 `targets[]`、`distractors[]` 都要带 `class_id`
- 第二专项的 `target` 也要带 `class_id`

如果你的外部导出当前只有 `class` 没有 `class_id`，请先补齐类别映射，再进入转换步骤。

### 8.3 `go-captcha-service` 现在是什么角色

现在只把它当可选底座，不再当默认前置。

适合用它的场景：

- 你没有自有生成逻辑
- 你需要一个可快速起步的内部底座
- 你愿意继续在源码层补导出逻辑

不适合把它当成什么：

- 不适合当“训练只要调公开接口就行”的捷径
- 不适合替代内部生成器或导出模式本身

## 9. 第四步：先确认 JSONL 主事实源是对的

正式进入训练前，先确认样本批次至少能被仓库正确读取。

从仓库根目录执行：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python -m core.dataset.cli --path D:\sinan-captcha-work\datasets\group1\v1\raw\batch_0001\labels.jsonl
```

这个 CLI 当前做的是“快速读盘和行数确认”。

更严格的 schema 校验会在转换阶段触发。所以这一步的意义是：

- 先确认文件存在
- 先确认 JSONL 至少能被正常读入

正式训练前你仍然要经过：

- 字段抽检
- 批次 QA
- `gold` / `auto` / `reviewed` 状态确认

如果你是从仓外工具导样本到当前仓库链路，还要额外确认：

- 对象里已经包含 `class_id`
- `bbox` 是 `[x1, y1, x2, y2]`
- `center` 是 `[cx, cy]`

## 10. 第五步：把通过检查的批次转成 YOLO 训练集

正式训练不要直接拿 `raw` 批次开跑。推荐顺序是：

1. 样本先进入 `raw`
2. 抽检或修正后进入 `reviewed`
3. 再从 `reviewed` 转换成 `yolo`

第一专项示例：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\convert\build_yolo_dataset.py `
  --task group1 `
  --version v1 `
  --source-dir D:\sinan-captcha-work\datasets\group1\v1\reviewed\batch_0001 `
  --output-dir D:\sinan-captcha-work\datasets\group1\v1\yolo
```

第二专项示例：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\convert\build_yolo_dataset.py `
  --task group2 `
  --version v1 `
  --source-dir D:\sinan-captcha-work\datasets\group2\v1\reviewed\batch_0001 `
  --output-dir D:\sinan-captcha-work\datasets\group2\v1\yolo
```

转换成功后，你应得到：

```text
D:\sinan-captcha-work\datasets\group1\v1\yolo\
  images\
    train\
    val\
    test\
  labels\
    train\
    val\
    test\
  dataset.yaml
```

注意：

- `dataset.yaml` 的 `path` 会被写成绝对路径
- 训练命令实际消费的是这个 `dataset.yaml`

## 11. 第六步：开始训练

### 11.1 当前最稳的方式是直接跑 YOLO 命令

第二专项示例：

```powershell
uv run yolo detect train data=D:\sinan-captcha-work\datasets\group2\v1\yolo\dataset.yaml model=yolo26n.pt imgsz=640 epochs=100 batch=16 device=0 project=D:\sinan-captcha-work\runs\group2 name=v1
```

第一专项示例：

```powershell
uv run yolo detect train data=D:\sinan-captcha-work\datasets\group1\v1\yolo\dataset.yaml model=yolo26n.pt imgsz=640 epochs=120 batch=16 device=0 project=D:\sinan-captcha-work\runs\group1 name=v1
```

### 11.2 仓库里的训练脚本当前是什么角色

仓库已经有：

- `scripts/train/train_group1.ps1`
- `scripts/train/train_group2.ps1`
- `core.train.group1.cli`
- `core.train.group2.cli`

但当前行为要特别注意：

- 它们现在负责“生成标准训练命令”
- 不是直接替你执行整场训练

也就是说，现阶段它们更像“命令模板固定器”，不是“一键训练器”。

如果你想看标准命令，可以这样调用：

```powershell
Set-Location D:\sinan-captcha-repo
.\scripts\train\train_group2.ps1 `
  -DatasetYaml D:\sinan-captcha-work\datasets\group2\v1\yolo\dataset.yaml `
  -ProjectDir D:\sinan-captcha-work\runs\group2 `
  -Name v1 `
  -Model yolo26n.pt
```

输出结果会是标准的 `uv run yolo detect train ...` 命令字符串。

## 12. 第七步：自动标注、评估、后处理当前怎么处理

### 12.1 自动标注

设计上已经明确：

- 第二专项先走规则法预标注
- 第一专项优先 `gold`，退路是“种子集 + 暖启动模型”

但当前仓库状态是：

- `scripts/autolabel/run_autolabel.py` 仍是脚手架
- `core.autolabel` 仍是占位接口

所以现在的实际做法是：

1. 第二专项先用规则法做预标注，至少能产出 `bbox` 和 `center`
2. 第一专项优先使用 `gold` 标签；如果拿不到，就先做 300-500 张种子集
3. 用外部标注工具复核和修正
4. 等仓库内自动标注模块落地后，再切回统一入口

### 12.2 评估

设计上要求统一评估和失败样本回灌，但当前仓库状态是：

- `scripts/evaluate/evaluate_model.py` 仍是脚手架
- `core.evaluate` 仍未实装

所以当前先这样做：

1. 读取 YOLO 自带训练输出
2. 收集 `best.pt`、指标曲线和日志
3. 手工整理失败样本清单到工作目录 `reports/`

### 12.3 后处理

设计上还需要：

- 第一专项顺序映射成点击点
- 第二专项把目标框换算成中心点

当前仓库状态是：

- `core.inference` 仅保留接口骨架

所以训练成功不等于完整业务输出已经自动化完成。现阶段请把它理解为：

- 模型训练链路优先落地
- 推理后处理仍在后续实现范围内

## 13. 一轮最小闭环完成后，你应该拿到什么

如果你按当前版本跑完一轮最小闭环，至少应拿到这些东西：

1. 一套已通过环境检查的 Windows + NVIDIA 训练机
2. 一个独立的训练工作目录
3. 一批可追溯的 JSONL 样本批次
4. 一套 `yolo/` 训练目录和 `dataset.yaml`
5. 一次可启动、可落盘、可得到 `best.pt` 的训练结果
6. 一份失败样本和问题分类记录

如果你拿不到第 3 到第 6 项，不要急着调 epoch 或换模型，先回头查：

- 样本导出是不是缺字段
- `reviewed` 数据是不是没有真的形成
- `dataset.yaml` 指向是不是错了
- 训练目录是不是还混在仓库目录里

## 14. 当前最容易踩的 8 个坑

1. 还按旧手册默认先起 `go-captcha-service`，结果把注意力放错到服务部署而不是标签导出。
2. 把项目仓库当成训练工作目录用，导致 `datasets/`、`runs/`、`reports/` 混进 Git 工作区。
3. 误以为 `uv sync` 已经装好了完整训练依赖。
4. 误以为 `scripts/train/*.ps1` 会直接执行训练，实际上它们当前主要负责打印标准命令。
5. 第一专项直接拿 `raw` 样本训练，没有先经过 `reviewed`。
6. 继续引用旧脚本名 `build_group1_yolo.py`、`build_group2_yolo.py`，而不是当前的 `build_yolo_dataset.py`。
7. 以为自动标注、评估、后处理已经在仓库里完整实现。
8. 第二专项还没稳定，第一专项数据还没固化，就急着追求统一接口或更复杂模型。

## 15. 你下一步该读什么

如果你还没理解交付物怎么用，先回去读：

1. [使用项目编译结果](./use-build-artifacts.md)

如果你只是卡在 CUDA 版本判断，补读：

2. [如何确认 Windows 电脑上的 CUDA 版本](./how-to-check-cuda-version.md)

如果你是仓库维护者，而不是训练执行者，请改读开发者指南下的“维护者快速使用说明”。

## 16. 参考来源

- PyTorch Get Started: <https://pytorch.org/get-started/locally/>
- Ultralytics Docs: <https://docs.ultralytics.com/>
- Ultralytics Detect Datasets: <https://docs.ultralytics.com/datasets/detect/>
- `go-captcha`: <https://github.com/wenlng/go-captcha>
- `go-captcha-service`: <https://github.com/wenlng/go-captcha-service>
- `tianai-captcha`: <https://github.com/dromara/tianai-captcha>
