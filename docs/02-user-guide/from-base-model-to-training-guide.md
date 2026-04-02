# 搭建训练环境并完成模型训练

- 文档状态：草稿
- 当前阶段：IMPLEMENTATION
- 目标读者：零基础训练执行者
- 负责人：Codex
- 最近重构：2026-04-02
- 关联需求：`REQ-001`、`REQ-002`、`REQ-003`、`REQ-005`、`REQ-006`、`REQ-007`、`REQ-008`

## 0. 读完后你应能做到

- 在 Windows + NVIDIA 电脑上把训练环境搭起来
- 分清项目仓库和训练工作目录
- 按 `raw -> reviewed -> yolo -> train` 跑通主链路
- 知道训练结果在哪里
- 知道训练完成后下一步该怎么使用和测试模型

## 1. 先固定目录边界

推荐固定成两个根目录：

```text
D:\
  sinan-captcha-repo\
  sinan-captcha-work\
```

职责只分两类：

- `sinan-captcha-repo`：保存源码、脚本、文档和构建产物定义
- `sinan-captcha-work`：保存样本、模型、报告、运行素材和生成器二进制

推荐工作目录结构：

```text
D:\sinan-captcha-work\
  datasets\
    group1\
      v1\
        raw\
        interim\
        reviewed\
        yolo\
    group2\
      v1\
        raw\
        interim\
        reviewed\
        yolo\
  runs\
  reports\
  tools\
    generator\
  materials\
  models\
```

## 2. 先把训练机环境搭好

进入数据和训练前，至少先确认下面 4 条：

1. `nvidia-smi` 正常
2. `python -c "import torch; print(torch.cuda.is_available())"` 输出 `True`
3. `uv` 和 Python 3.11 已可用
4. 已手工安装 PyTorch GPU 版、`ultralytics`、`opencv-python` 等训练依赖

从仓库根目录可以先跑最小自检：

```powershell
Set-Location D:\sinan-captcha-repo
.\scripts\ops\check-env.ps1
```

如果你只是不确定 CUDA 版本怎么看，补读：

- [如何确认 Windows 电脑上的 CUDA 版本](./how-to-check-cuda-version.md)

当前要特别注意：

- `uv sync` 还不能替代完整训练环境安装
- 训练依赖仍按环境 checklist 手工安装更稳

## 3. 准备样本

当前主线只记这一条：

`raw -> reviewed -> yolo -> train`

如果你还没有一套本地素材包，可以先用仓库脚本批量构建一份离线 `materials/`：

```powershell
Set-Location D:\sinan-captcha-repo
$env:PEXELS_API_KEY = "<你的 Pexels API Key>"
uv run python .\scripts\materials\build_offline_pack.py `
  --spec .\configs\materials-pack.example.toml `
  --output-root D:\sinan-captcha-work\materials `
  --cache-dir D:\sinan-captcha-work\tools\material-cache
```

这一步会：

- 批量下载背景图
- 批量提取图标 PNG
- 自动生成 `classes.yaml`

### 3.1 第一专项：用仓库产物导出样本

先把生成器二进制放到：

```text
D:\sinan-captcha-work\tools\generator\
```

再执行导出：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\export\export_group1_batch.py `
  --binary D:\sinan-captcha-work\tools\generator\sinan-click-generator.exe `
  --config D:\sinan-captcha-repo\generator\configs\default.yaml `
  --materials-root D:\sinan-captcha-work\materials `
  --output-root D:\sinan-captcha-work\datasets\group1\v1\raw
```

导出后会得到一个批次目录，例如：

```text
D:\sinan-captcha-work\datasets\group1\v1\raw\batch_0001\
  query\
  scene\
  labels.jsonl
  manifest.json
```

### 3.2 第二专项：当前没有对等仓内导出器

第二专项样本目前仍来自你的自有生成逻辑、内部离线脚本或受控外部工具。

无论你从哪里导出，进入本仓库训练链路前都要满足这几条：

- 批次目录里有 `labels.jsonl`
- 目标对象包含 `class_id`
- `bbox` 使用 `[x1, y1, x2, y2]`
- `center` 使用 `[cx, cy]`

### 3.3 需要离线预处理时怎么做

当前仓库已经有离线自动标注/标签整理入口，但它不是“训练后自动回标”的完整闭环。

常见入口如下：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\autolabel\run_autolabel.py `
  --task group1 `
  --mode seed-review `
  --input-dir D:\sinan-captcha-work\datasets\group1\v1\raw\batch_0001 `
  --output-dir D:\sinan-captcha-work\datasets\group1\v1\reviewed\batch_0001
```

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\autolabel\run_autolabel.py `
  --task group2 `
  --mode rule-auto `
  --input-dir D:\sinan-captcha-work\datasets\group2\v1\raw\batch_0001 `
  --output-dir D:\sinan-captcha-work\datasets\group2\v1\interim\batch_0001
```

当前建议理解成：

- 第一专项的 `seed-review` 更接近“把已确认样本整理进 reviewed”，不是模型推理回标
- 第二专项的 `rule-auto` 更接近“规则法预标注”，不是完整自动验收
- `reviewed` 是进入训练前的最终样本源
- `interim` 适合放规则法或伪自动结果
- 正式训练前仍要抽检关键字段和失败样本

## 4. 校验并转换成 YOLO 训练集

先确认 JSONL 至少能被仓库读到：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python -m core.dataset.cli --path D:\sinan-captcha-work\datasets\group1\v1\raw\batch_0001\labels.jsonl
```

然后把 `reviewed` 批次转换成 YOLO 目录。

第一专项：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\convert\build_yolo_dataset.py `
  --task group1 `
  --version v1 `
  --source-dir D:\sinan-captcha-work\datasets\group1\v1\reviewed\batch_0001 `
  --output-dir D:\sinan-captcha-work\datasets\group1\v1\yolo
```

第二专项：

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\convert\build_yolo_dataset.py `
  --task group2 `
  --version v1 `
  --source-dir D:\sinan-captcha-work\datasets\group2\v1\reviewed\batch_0001 `
  --output-dir D:\sinan-captcha-work\datasets\group2\v1\yolo
```

转换完成后，你至少应看到：

```text
D:\sinan-captcha-work\datasets\group1\v1\yolo\
  images\
  labels\
  dataset.yaml
```

## 5. 开始训练

当前最稳的方式仍然是直接执行 YOLO 原生命令。

第一专项示例：

```powershell
uv run yolo detect train data=D:\sinan-captcha-work\datasets\group1\v1\yolo\dataset.yaml model=yolo26n.pt imgsz=640 epochs=120 batch=16 device=0 project=D:\sinan-captcha-work\runs\group1 name=v1
```

第二专项示例：

```powershell
uv run yolo detect train data=D:\sinan-captcha-work\datasets\group2\v1\yolo\dataset.yaml model=yolo26n.pt imgsz=640 epochs=100 batch=16 device=0 project=D:\sinan-captcha-work\runs\group2 name=v1
```

如果你只想先生成标准命令，再手工执行，也可以用仓库脚本：

```powershell
Set-Location D:\sinan-captcha-repo
.\scripts\train\train_group1.ps1 `
  -DatasetYaml D:\sinan-captcha-work\datasets\group1\v1\yolo\dataset.yaml `
  -ProjectDir D:\sinan-captcha-work\runs\group1 `
  -Name v1 `
  -Model yolo26n.pt
```

当前训练脚本的定位是：

- 帮你固定标准参数
- 输出标准训练命令
- 不负责代替你执行整场训练

## 6. 训练完成后你应该拿到什么

训练完成后，最重要的产物是权重文件：

```text
D:\sinan-captcha-work\runs\group1\v1\weights\best.pt
D:\sinan-captcha-work\runs\group2\v1\weights\best.pt
```

到这里，这一页的目标就完成了：

- 训练环境已经搭好
- 数据已经能转成 YOLO
- 训练命令已经能执行
- 模型权重已经产出

## 7. 下一步读哪一页

训练结束后，不要继续回头翻设计文档，直接读：

- [训练完成后的模型使用与测试](./use-and-test-trained-models.md)

那一页只回答两件事：

1. 训练好的模型怎么用
2. 训练好的模型怎么测
