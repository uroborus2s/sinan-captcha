# Windows 训练机安装与模型训练完整指南

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：Windows 训练执行者
- 负责人：Codex
- 最近更新：2026-04-03

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

## 1. 先准备这些文件

### 1.1 如果你准备直接从 PyPI 初始化训练目录

你只需要：

- `uv`
- `sinan-captcha` 已发布到 PyPI

### 1.2 如果你要直接训练

还需要：

- `group1` 的 YOLO 数据集目录
- `group2` 的 YOLO 数据集目录

### 1.3 如果你要自己生成样本

还需要独立生成器目录里的这些文件：

- `sinan-generator.exe`
- `generator/configs/*.yaml`
- `materials-pack.toml`
- 现成 `materials-pack/` 或 `materials/`
  或
- `Pexels API Key`
  和
- `uv run sinan materials build` 所需的素材规格文件

## 2. 固定训练机目录

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
  configs\
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

## 3. 安装驱动并确认显卡可用

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

## 4. 安装 uv

```powershell
winget install --id=astral-sh.uv -e
uv --version
```

## 5. 一条命令创建训练目录

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

通过标准：

- `D:\sinan-captcha-work` 已生成
- 训练目录里有 `pyproject.toml`、`.python-version` 和 `.venv`
- 命令结束后终端会打印“数据怎么放、后续怎么训练”的中文提示

## 6. 进入训练目录并自检

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

## 7. 选择你的起点

### 7.1 起点 A：你已经有 YOLO 数据集

把数据直接放到训练目录下，例如：

- `D:\sinan-captcha-work\datasets\group1\firstpass\yolo`
- `D:\sinan-captcha-work\datasets\group2\firstpass\yolo`

当前新版 `dataset.yaml` 使用相对路径，拷过去即可用；如果你手上的旧数据集仍然是绝对路径，建议重新执行一次 `uv run sinan dataset build-yolo`。

下面训练命令里如果出现 `firstpass` 或 `v1`，都表示“你的实际数据版本名”。直接替换成你手里的版本目录即可。

### 7.2 起点 B：你要从样本生成开始

继续执行第 8 节。

## 8. 从独立生成器开始

### 8.1 准备素材

先初始化生成器工作区：

```powershell
sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
```

如果你已经拿到现成素材包，直接导入：

```powershell
sinan-generator.exe materials import --workspace D:\sinan-captcha-generator\workspace --from D:\materials-pack
```

如果你拿到的是压缩包或远程地址，也可以直接同步：

```powershell
sinan-generator.exe materials fetch --workspace D:\sinan-captcha-generator\workspace --source D:\materials-pack.zip
```

如果你手里没有现成素材包，只有 `materials-pack.toml` 和 `Pexels API Key`，先在训练目录里构建离线素材包：

```powershell
Set-Location D:\sinan-captcha-work
uv run sinan materials build `
  --spec D:\sinan-captcha-generator\materials-pack.toml `
  --output-root D:\sinan-captcha-generator\materials-pack `
  --cache-dir D:\sinan-captcha-generator\workspace\cache\materials
```

构建完成后，再导入：

```powershell
sinan-generator.exe materials import --workspace D:\sinan-captcha-generator\workspace --from D:\sinan-captcha-generator\materials-pack
```

### 8.2 直接生成 group1 数据集目录

```powershell
sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass\yolo
```

### 8.3 直接生成 group2 数据集目录

```powershell
sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group2 `
  --dataset-dir D:\sinan-captcha-work\datasets\group2\firstpass\yolo
```

### 8.4 生成器和训练 CLI 的交接面

- 生成器输出：`dataset.yaml`、`images/`、`labels/` 和 `.sinan/`
- 训练 CLI 输入：`--dataset-yaml <dataset-dir>\dataset.yaml`
- 训练 CLI 不读取生成器工作区，只读取数据集目录
- 训练 CLI 的环境和 `runs/` 目录仍由 `sinan env setup-train` 管理
- 生成器工作区建议固定成一个显式目录，而不是靠默认 `%LOCALAPPDATA%` 去猜

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
  --dataset-yaml D:\sinan-captcha-work\datasets\group1\firstpass\yolo\dataset.yaml `
  --project D:\sinan-captcha-work\runs\group1 `
  --name smoke `
  --epochs 1 `
  --batch 8
```

### 9.2 `group2`

```powershell
uv run sinan train group2 `
  --dataset-yaml D:\sinan-captcha-work\datasets\group2\firstpass\yolo\dataset.yaml `
  --project D:\sinan-captcha-work\runs\group2 `
  --name smoke `
  --epochs 1 `
  --batch 8
```

冒烟目标不是训好模型，而是确认：

- 环境能跑
- 数据路径对
- `uv run yolo` 能正常启动

## 10. 启动正式训练

### 10.1 `group1`

```powershell
uv run sinan train group1 `
  --dataset-yaml D:\sinan-captcha-work\datasets\group1\firstpass\yolo\dataset.yaml `
  --project D:\sinan-captcha-work\runs\group1 `
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
  --dataset-yaml D:\sinan-captcha-work\datasets\group2\firstpass\yolo\dataset.yaml `
  --project D:\sinan-captcha-work\runs\group2 `
  --name firstpass `
  --model yolo26n.pt `
  --epochs 100 `
  --batch 16 `
  --imgsz 640 `
  --device 0
```

如果只想打印标准训练命令：

```powershell
uv run sinan train group1 --dataset-yaml D:\sinan-captcha-work\datasets\group1\firstpass\yolo\dataset.yaml --project D:\sinan-captcha-work\runs\group1 --dry-run
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

## 12. 常见问题

### 12.1 `uv run sinan env check` 显示 `torch_cuda_available=false`

结论：

- 你装成了 CPU 版 PyTorch
  或
- PyTorch CUDA 版本和驱动不匹配

### 12.2 `dataset.yaml` 找不到图片

结论：

- 你拿到的是旧版绝对路径数据集
- 重新执行一次 `sinan-generator make-dataset`

### 12.3 训练一启动就显存爆掉

结论：

- 先降 `batch`
- 再降 `imgsz`
- 先用 `yolo26n.pt`

### 12.4 `sinan-generator materials import|fetch|make-dataset` 失败

结论：

- 素材目录不完整
  或
- 图片损坏
  或
- `classes.yaml` 与图标目录不一致
  或
- 你把生成器安装目录和生成器工作区混成了一个概念，命令没有带上正确的 `--workspace`

## 13. 这份文档完成标志

满足下面 6 条，就说明 Windows 训练机链路已经跑通：

1. `nvidia-smi` 正常
2. `torch.cuda.is_available()` 为 `True`
3. `uv run sinan env check` 正常
4. 至少一个专项的冒烟训练成功
5. 正式训练产出 `best.pt`
6. 你知道下一步该去看模型验证文档

下一步继续读：

- [训练完成后的模型使用与测试](./use-and-test-trained-models.md)
