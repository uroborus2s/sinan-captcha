# 使用项目编译结果

- 项目名称：sinan-captcha
- 当前阶段：IMPLEMENTATION
- 目标读者：交付使用者、训练执行者
- 目标：在不理解全部仓库实现细节的前提下，正确使用项目的构建产物

## 0. 这页解决什么问题

如果你已经拿到了项目的构建结果，或者准备把仓库里的可执行产物部署到训练机，这页就是你的起点。

读完后你应能清楚理解：

1. 当前项目会产出哪些可使用的东西
2. 这些产物应该放到哪里
3. 这些产物分别能做什么，不能做什么

## 1. 先认清“编译结果”有哪些

当前项目不是单一程序包，而是多交付物结构。

你会接触到的主要产物有：

### 1.1 Go 生成器二进制

典型形态：

- `sinan-click-generator.exe`

它负责：

- 校验素材
- 生成第一专项样本批次
- 输出 `query/`、`scene/`、`labels.jsonl`、`manifest.json`

它不负责：

- 第二专项完整导出
- 自动标注
- 模型训练
- 评估报告

### 1.2 Python 训练链路脚本

典型入口：

- `scripts/convert/build_yolo_dataset.py`
- `scripts/train/train_group1.ps1`
- `scripts/train/train_group2.ps1`
- `scripts/ops/check-env.ps1`

它们负责：

- 数据转换
- 训练命令组织
- 最小环境检查

当前要特别注意：

- 训练脚本现在主要负责生成标准命令
- 它们不是完整的一键训练器

### 1.3 配置和素材

你还需要：

- 生成器配置
- 背景图、图标图、类别表

它们属于运行资产，不应和训练结果混在一起，也不应默认混进仓库源码管理。

## 2. 产物应该放在哪里

推荐固定成下面两层：

```text
D:\
  sinan-captcha-repo\
  sinan-captcha-work\
```

分工如下：

### 2.1 仓库目录

用于保存：

- 源码
- 文档
- 脚本
- 构建产物定义

### 2.2 工作目录

用于保存：

- 生成器二进制
- 运行素材
- 样本数据
- 训练输出
- 报告

推荐结构：

```text
D:\sinan-captcha-work\
  datasets\
  runs\
  reports\
  tools\
    generator\
  materials\
```

## 3. 最小部署步骤

### 3.1 准备训练机环境

先完成：

- Windows + NVIDIA 驱动可用
- Python 3.11 可用
- `uv` 可用
- PyTorch / Ultralytics / OpenCV 已装好

如果你还没完成这一层，不要急着看后面的产物使用。直接转到：

- [搭建训练环境并完成模型训练](./from-base-model-to-training-guide.md)

### 3.2 放置 Go 生成器

把生成器二进制放到：

```text
D:\sinan-captcha-work\tools\generator\
```

例如：

```powershell
New-Item -ItemType Directory -Force D:\sinan-captcha-work\tools\generator | Out-Null
Copy-Item D:\sinan-captcha-repo\dist\generator\windows-amd64\sinan-click-generator.exe D:\sinan-captcha-work\tools\generator\
```

### 3.3 放置素材

把背景图、图标图、类别表放到：

```text
D:\sinan-captcha-work\materials\
```

### 3.4 保持仓库脚本可调用

当前版本最稳的方式仍然是：

1. 仓库保留在 `D:\sinan-captcha-repo`
2. 从仓库根目录执行 Python 脚本
3. 用绝对路径指向 `D:\sinan-captcha-work`

这样做的好处是：

- 不会把工作目录误当成仓库
- 不依赖脚本自动推断路径
- 出错时更容易定位到底是“仓库脚本问题”还是“工作目录数据问题”

## 4. 你可以用这些产物完成什么

### 4.1 使用生成器导出第一专项样本

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\export\export_group1_batch.py `
  --binary D:\sinan-captcha-work\tools\generator\sinan-click-generator.exe `
  --config D:\sinan-captcha-repo\generator\configs\default.yaml `
  --materials-root D:\sinan-captcha-work\materials `
  --output-root D:\sinan-captcha-work\datasets\group1\v1\raw
```

### 4.2 把 JSONL 批次转成 YOLO 训练集

```powershell
Set-Location D:\sinan-captcha-repo
uv run python .\scripts\convert\build_yolo_dataset.py `
  --task group1 `
  --version v1 `
  --source-dir D:\sinan-captcha-work\datasets\group1\v1\reviewed\batch_0001 `
  --output-dir D:\sinan-captcha-work\datasets\group1\v1\yolo
```

### 4.3 生成标准训练命令

```powershell
Set-Location D:\sinan-captcha-repo
.\scripts\train\train_group1.ps1 `
  -DatasetYaml D:\sinan-captcha-work\datasets\group1\v1\yolo\dataset.yaml `
  -ProjectDir D:\sinan-captcha-work\runs\group1 `
  -Name v1 `
  -Model yolo26n.pt
```

## 5. 当前编译结果还不能替你做什么

为了避免误解，这里明确列出当前限制：

1. 第二专项还没有同等仓内导出入口。
2. 自动标注仍不是完整可用状态。
3. 统一评估入口仍是脚手架。
4. 推理后处理还没有落成。
5. `pyproject.toml` 还没有把完整训练依赖写满，所以不要把“仓库能运行”误认为“训练环境已经完备”。

## 6. 什么时候算你已经会“使用项目编译结果”

满足下面 4 条，就算这一路已经跑通：

1. 你能说清每个产物属于仓库还是工作目录。
2. 你能把生成器二进制和素材放到正确位置。
3. 你能从仓库根目录调用脚本并指向工作目录。
4. 你能用这些产物完成一次“导出样本 -> 转换数据 -> 生成训练命令”的链路。

## 7. 下一步去哪里

如果你下一步要真正把训练环境搭起来并拿到模型结果，请继续：

- [搭建训练环境并完成模型训练](./from-base-model-to-training-guide.md)
