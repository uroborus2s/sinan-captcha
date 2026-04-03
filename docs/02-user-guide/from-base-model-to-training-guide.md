# Windows 训练机安装与模型训练完整指南

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：Windows 训练执行者
- 负责人：Codex
- 最近更新：2026-04-04

## 0. 这份文档解决什么问题

这是一份面向 Windows 训练机的完整操作文档。

它覆盖两类起点：

1. 你已经拿到了现成的 YOLO 数据集，准备直接训练
2. 你有独立生成器目录和素材，准备从样本生成开始

读完后你应能做到：

1. 在 Windows 上装好训练环境
2. 一条命令创建独立训练目录并自动安装运行环境
3. 区分生成器安装目录、生成器工作区和训练目录
4. 启动 `group1` 与 `group2` 的训练

如果你只想最快跑起来，不想先看完整手册，先读：

- [Windows 快速开始](./windows-quickstart.md)

如果你还没有训练数据，配合阅读：

- [用生成器准备训练数据](./prepare-training-data-with-generator.md)

如果你的训练机主要依赖交付包而不是源码仓库，补充阅读：

- [使用交付包在 Windows 训练机上安装](./windows-bundle-install.md)

## 1. 先准备这些文件

### 1.1 如果你准备直接从 PyPI 初始化训练目录

你只需要：

- `uv`
- 能从 PyPI 拉取 `sinan-captcha`

### 1.2 如果你要直接训练

还需要：

- `group1` 的 YOLO 数据集目录
- `group2` 的 YOLO 数据集目录

### 1.3 如果你要自己生成样本

还需要独立生成器目录里的这些文件：

- `sinan-generator.exe`
- 现成 `materials-pack/`
  或
- `materials-pack.zip`
  或
- 一个可访问的素材包下载地址

## 2. 开始前的最小检查单

开始前至少确认下面 6 件事：

1. 这台机器是 Windows
2. 有 NVIDIA 显卡
3. `nvidia-smi` 可用
4. 能访问互联网
5. 至少有一个专项的数据来源
6. 你知道自己走的是“直接训练”还是“本地生成再训练”

## 3. 固定训练机目录

建议固定为：

```text
D:\
  sinan-captcha-generator\
  sinan-captcha-work\
```

推荐结构：

```text
D:\sinan-captcha-generator\
  sinan-generator.exe
  workspace\
    workspace.json
    presets\
    materials\
    cache\
    jobs\
    logs\

D:\sinan-captcha-work\
  pyproject.toml
  .python-version
  datasets\
  runs\
  reports\
```

说明：

- `sinan-captcha-generator` 是生成器安装目录
- `sinan-captcha-generator\workspace` 是建议显式指定的生成器工作区
- 如果你不传 `--workspace`，Windows 默认工作区会落到 `%LOCALAPPDATA%\SinanGenerator`
- 如果你的电脑没有 `D:` 盘，把本页所有 `D:\` 统一替换成你自己的实际盘符

## 4. 安装驱动并确认显卡可用

先完成：

1. 安装 NVIDIA 稳定驱动
2. 重启电脑
3. 打开 PowerShell 执行：

```powershell
nvidia-smi
```

通过标准：

- 能看到显卡型号
- 能看到驱动版本
- 能看到显存
- 能看到 `CUDA Version`

如果你不确定 CUDA 版本怎么确认，补读：

- [如何确认 Windows 电脑上的 CUDA 版本](./how-to-check-cuda-version.md)

## 5. 安装 uv

```powershell
winget install --id=astral-sh.uv -e
uv --version
```

## 6. 一条命令创建训练目录

```powershell
Set-Location D:\
uvx --from sinan-captcha sinan env setup-train `
  --train-root D:\sinan-captcha-work `
  --generator-root D:\sinan-captcha-generator
```

这个命令会：

- 检测 `nvidia-smi`
- 读取 CUDA 版本
- 输出中文摘要
- 让你确认是否继续
- 自动创建：
  - `D:\sinan-captcha-work\pyproject.toml`
  - `D:\sinan-captcha-work\.python-version`
  - `D:\sinan-captcha-work\.venv`
  - `D:\sinan-captcha-work\datasets\`
  - `D:\sinan-captcha-work\runs\`
  - `D:\sinan-captcha-work\reports\`
- 自动执行 `uv sync`
- 不会替你创建生成器工作区；生成器工作区由 `sinan-generator workspace init` 管理

这一步不要求你先在本机克隆源码仓库。`uvx --from sinan-captcha ...` 会直接从 PyPI 拉取 CLI，再在训练目录里创建独立运行环境。

摘要输出形态大致如下：

![setup-train 输出示意](./assets/setup-train-terminal.svg)

通过标准：

- `D:\sinan-captcha-work` 已生成
- 训练目录里有 `pyproject.toml`、`.python-version` 和 `.venv`
- 命令结束后终端会打印“数据怎么放、后续怎么训练”的中文提示

## 7. 进入训练目录并自检

```powershell
Set-Location D:\sinan-captcha-work
uv run sinan --help
uv run sinan env check
uv run yolo checks
```

通过标准：

- `uv run sinan --help` 能显示子命令
- `uv run sinan env check` 能输出 JSON
- `uv run yolo checks` 没有关键错误

## 8. 选择你的起点

### 8.1 起点 A：你已经有 YOLO 数据集

把数据直接放到训练目录下，例如：

- `D:\sinan-captcha-work\datasets\group1\firstpass\yolo`
- `D:\sinan-captcha-work\datasets\group2\firstpass\yolo`

当前新版 `dataset.yaml` 使用相对路径，拷过去即可用；如果你手上的旧数据集仍然是绝对路径，建议让提供方重新导出，或者你自己重新执行一次 `sinan-generator make-dataset`。

下面训练命令里如果出现 `firstpass` 或 `v1`，都表示“你的实际数据版本名”。直接替换成你手里的版本目录即可。

如果你已经在训练目录里执行命令：

- `--project` 可以省略，默认会落到 `runs/group1` 或 `runs/group2`
- `--dataset-yaml` 也可以省略
  但这时应改用 `--dataset-version <版本目录名>`

### 8.2 起点 B：你要从样本生成开始

如果你要在本地先生成数据，再训练，不要继续硬读这一页中间的命令，直接跳到：

- [用生成器准备训练数据](./prepare-training-data-with-generator.md)

生成出 `dataset.yaml`、`images/`、`labels/` 之后，再回到本页第 9 节继续训练。

## 9. 先做冒烟训练

如果你走的是“自己生成再训练”路线，通常这里的 `dataset.yaml` 会落在：

- `D:\sinan-captcha-work\datasets\group1\v1\yolo\dataset.yaml`
- `D:\sinan-captcha-work\datasets\group2\v1\yolo\dataset.yaml`

如果你走的是“直接拿现成数据集训练”路线，则可能是：

- `D:\sinan-captcha-work\datasets\group1\firstpass\yolo\dataset.yaml`
- `D:\sinan-captcha-work\datasets\group2\firstpass\yolo\dataset.yaml`

### 9.1 `group1`

```powershell
uv run sinan train group1 `
  --dataset-version firstpass `
  --name smoke `
  --epochs 1 `
  --batch 8
```

### 9.2 `group2`

```powershell
uv run sinan train group2 `
  --dataset-version firstpass `
  --name smoke `
  --epochs 1 `
  --batch 8
```

冒烟目标不是训好模型，而是确认：

- 环境能跑
- 数据路径对
- `uv run yolo` 能正常启动

正常启动后的终端形态大致如下：

![smoke 训练输出示意](./assets/train-smoke-terminal.svg)

## 10. 启动正式训练

### 10.1 `group1`

```powershell
uv run sinan train group1 `
  --dataset-version firstpass `
  --name firstpass `
  --model yolo26n.pt `
  --epochs 120 `
  --batch 16 `
  --imgsz 640 `
  --device 0
```

### 10.2 `group2`

```powershell
uv run sinan train group2 `
  --dataset-version firstpass `
  --name firstpass `
  --model yolo26n.pt `
  --epochs 100 `
  --batch 16 `
  --imgsz 640 `
  --device 0
```

如果只想打印标准训练命令：

```powershell
uv run sinan train group1 --dataset-version firstpass --name firstpass --dry-run
```

## 11. 训练完成后你会得到什么

主要输出在：

```text
D:\sinan-captcha-work\runs\group1\firstpass\
D:\sinan-captcha-work\runs\group2\firstpass\
```

重点关注：

- `weights\best.pt`
- `weights\last.pt`
- `results.csv`
- `args.yaml`

## 12. 第一次训练完成后，先怎么看效果

先不要急着直接比较一大堆指标。第一次训练完成后，按下面顺序看最快：

1. `weights\best.pt` 是否存在
2. `results.csv` 是否已生成
3. 在验证集图片上跑一次 `predict`
4. 再跑一次 `val`

判断思路：

- `best.pt` 存在，说明训练流程至少完整跑过并保存了最佳权重
- `results.csv` 可用于和上一个实验版本做横向比较
- `predict` 适合做肉眼快速检查
- `val` 更适合做指标对比和回归检查

完整命令和验收方法继续读：

- [训练完成后的模型使用与测试](./use-and-test-trained-models.md)

## 13. 同一份训练数据能不能继续用于第二次训练

可以。

只要数据集目录没有被覆盖，你可以反复拿同一个 `dataset.yaml` 去跑：

- `smoke`
- 正式训练
- 不同 `--name` 的实验
- 不同超参数组合
- 不同预训练模型对比

建议做法：

- 把数据目录当成版本化输入，例如 `firstpass`、`firstpass_v2`
- 把训练输出放到不同的 `runs\<task>\<name>\`
- 不要一边训练一边重新生成同一个数据集目录

如果你觉得当前训练效果不够好，需要更多训练数据，不要直接覆盖旧数据集；回到：

- [用生成器准备训练数据](./prepare-training-data-with-generator.md)

然后新建一个新的数据版本目录继续生成。
## 14. 成功标准

在这一页里，最少达到下面 4 条，就说明训练链路已经健康：

1. `uvx --from sinan-captcha sinan env setup-train` 成功
2. `uv run sinan env check` 输出正常
3. 至少一个专项的冒烟训练成功启动
4. 正式训练目录下能产出 `weights\best.pt`

## 15. 常见问题

### 15.1 `uv run sinan env check` 显示 `torch_cuda_available=false`

结论：

- 你装成了 CPU 版 PyTorch
  或
- PyTorch CUDA 版本和驱动不匹配

### 15.2 `dataset.yaml` 找不到图片

结论：

- 你拿到的是旧版绝对路径数据集
- 让提供方重新导出一版相对路径数据集
  或
- 你自己重新执行一次 `sinan-generator make-dataset`

### 15.3 训练一启动就显存爆掉

结论：

- 先降 `batch`
- 再降 `imgsz`
- 先用 `yolo26n.pt`

### 15.4 `sinan-generator materials import|fetch|make-dataset` 失败

结论：

- 素材目录不完整
  或
- 图片损坏
  或
- `classes.yaml` 与图标目录不一致
  或
- 你把生成器安装目录和生成器工作区混成了一个概念，命令没有带上正确的 `--workspace`

## 16. 这份文档完成标志

满足下面 6 条，就说明 Windows 训练机链路已经跑通：

1. `nvidia-smi` 正常
2. `torch.cuda.is_available()` 为 `True`
3. `uv run sinan env check` 正常
4. 至少一个专项的冒烟训练成功
5. 正式训练产出 `best.pt`
6. 你知道下一步该去看模型验证文档

下一步继续读：

- [训练完成后的模型使用与测试](./use-and-test-trained-models.md)
