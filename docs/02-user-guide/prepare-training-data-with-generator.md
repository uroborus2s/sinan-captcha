# 用生成器准备训练数据

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：需要在本地生成训练数据的人
- 负责人：Codex
- 最近更新：2026-04-04

## 0. 这页解决什么问题

这页只解决一件事：

- 怎样用 `sinan-generator` 在 Windows 机器上准备素材，并直接生成可训练的 YOLO 数据集目录

最终目标是让你拿到这样的目录：

- `D:\sinan-captcha-work\datasets\group1\<version>\yolo`
- `D:\sinan-captcha-work\datasets\group2\<version>\yolo`

然后马上接：

- `uv run sinan train group1`
- `uv run sinan train group2`

## 1. 开始前先准备 3 个目录

推荐固定成：

```text
D:\
  sinan-captcha-generator\
  sinan-captcha-work\
```

它们分别表示：

- 生成器安装目录：
  - `D:\sinan-captcha-generator`
- 生成器工作区：
  - `D:\sinan-captcha-generator\workspace`
- 训练目录：
  - `D:\sinan-captcha-work`

如果训练目录还没有创建，先执行：

- [Windows 快速开始](./windows-quickstart.md)
  或
- [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)

如果你的电脑没有 `D:` 盘，把本页所有 `D:\` 统一替换成你自己的实际盘符。

## 2. 先把生成器放到安装目录

普通用户最少只需要：

- `sinan-generator.exe`

推荐目录结构：

```text
D:\sinan-captcha-generator\
  sinan-generator.exe
```

注意：

- 不需要手工拷贝 `configs/*.yaml`
- 预设配置已经内置到生成器里
- 首次运行时，生成器会自动把工作区需要的预设副本写到 `workspace\presets\`

如果你在 Windows PowerShell 里直接进入这个目录执行命令：

```powershell
Set-Location D:\sinan-captcha-generator
```

后续要写成：

```powershell
.\sinan-generator.exe ...
```

不要直接写 `sinan-generator.exe ...`，否则 PowerShell 默认不会从当前目录加载它。

## 3. 你可以从哪种素材来源开始

支持 3 条常见路线。

### 3.1 你已经拿到现成素材包目录

例如：

- `D:\materials-pack`

这是最简单的路线。

### 3.2 你拿到的是 zip 包或远程压缩包

例如：

- `D:\materials-pack.zip`
- `https://example.com/materials-pack.zip`

### 3.3 你没有现成素材包，但有可访问的下载地址

例如：

- `https://example.com/materials-pack.zip`

这时直接用 `materials fetch` 即可，不需要先手工解压。

### 3.4 一个可导入的素材包最少要长什么样

最少目录结构如下：

```text
materials-pack\
  backgrounds\
  icons\
    icon_house\
    icon_leaf\
    ...
  manifests\
    classes.yaml
```

说明：

- `backgrounds\` 里放背景图
- `icons\<class_name>\` 里放该类别的图标
- `manifests\classes.yaml` 负责声明类别名和类别 ID
- 当前实现会统一校验这套结构；即使你只生成 `group2`，当前也仍然要求素材包里有完整的 `classes.yaml` 和图标目录
- 如果你拿到的是源码仓库里的某个 `materials\` 目录，只有当它本身已经满足这套结构时，才能直接 `materials import`

## 4. 先初始化生成器工作区

```powershell
Set-Location D:\sinan-captcha-generator
.\sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
```

执行成功后，你应该看到工作区里出现：

- `workspace.json`
- `presets\`
- `materials\`
- `cache\`
- `jobs\`
- `logs\`

## 5. 选择素材准备方式

### 5.1 方式 A：导入现成素材目录

```powershell
.\sinan-generator.exe materials import `
  --workspace D:\sinan-captcha-generator\workspace `
  --from D:\materials-pack
```

### 5.2 方式 B：同步 zip 包或远程压缩包

```powershell
.\sinan-generator.exe materials fetch `
  --workspace D:\sinan-captcha-generator\workspace `
  --source D:\materials-pack.zip
```

如果是远程地址，把 `--source` 改成 URL 即可。

### 5.3 方式 C：直接抓取远程素材包

```powershell
.\sinan-generator.exe materials fetch `
  --workspace D:\sinan-captcha-generator\workspace `
  --source https://example.com/materials-pack.zip
```

如果你的训练机不能联网，就不要走这条路线，改成让交付方提供本地 `materials-pack/` 或 `materials-pack.zip`。

### 5.4 高级方式：从远程图片源构建素材包

这不是普通用户默认主链路，但当你手里没有现成素材包、又需要自己从远程图片源构建时，可以这样做。

先确认：

- 你在源码仓库目录里
- 已经安装好 Python 训练 CLI 运行环境
- 你有远程图片源的 API Key

当前仓库默认示例使用 Pexels，配置文件是：

- `configs/materials-pack.toml`

其中背景图 key 默认从环境变量读取：

- `PEXELS_API_KEY`

PowerShell 当前会话示例：

```powershell
$env:PEXELS_API_KEY = "你的PexelsKey"
```

如果要永久写到当前 Windows 用户环境变量：

```powershell
setx PEXELS_API_KEY "你的PexelsKey"
```

然后在源码仓库目录执行：

```powershell
Set-Location D:\sinan-captcha
uv run sinan materials build `
  --spec configs/materials-pack.toml `
  --output-root D:\materials-pack `
  --cache-dir D:\sinan-captcha-generator\workspace\cache\materials
```

构建完成后，再导入生成器工作区：

```powershell
Set-Location D:\sinan-captcha-generator
.\sinan-generator.exe materials import `
  --workspace D:\sinan-captcha-generator\workspace `
  --from D:\materials-pack
```

### 5.5 怎么检查素材够不够

当前生成器会先做结构校验，再决定能不能继续生成。

程序最低标准是：

- `manifests\classes.yaml` 存在且非空
- `backgrounds\` 里至少有 1 张可正常解码的图片
- `classes.yaml` 里每个类别对应的 `icons\<class_name>\` 目录至少有 1 张可正常解码的图片

你在 `materials import` 或 `materials fetch` 成功后，会看到一段 JSON，里面至少有：

- `class_count`
- `background_count`
- `icon_dir_count`

工程建议，不是程序硬门槛：

- 背景图尽量至少 `100` 张以上
- 每个类别图标尽量至少 `3-5` 张变体
- 如果只是验证流程，少量素材也能跑；如果准备做正式 firstpass 训练，素材越少，重复率越高

### 5.6 怎么补齐或增加素材

当前普通用户路径没有“在线增量补一张图”的命令。稳定做法是：

1. 准备一份新的 `materials-pack/`
2. 往 `backgrounds\` 增加背景图
3. 往 `icons\<class_name>\` 增加图标
4. 如果新增了类别，同时更新 `manifests\classes.yaml`
5. 重新执行一次 `materials import`

如果你想保留旧素材版本，不要覆盖原目录，建议新建一个新目录名，例如：

- `D:\materials-pack-20260404`

然后导入时显式命名：

```powershell
Set-Location D:\sinan-captcha-generator
.\sinan-generator.exe materials import `
  --workspace D:\sinan-captcha-generator\workspace `
  --from D:\materials-pack-20260404 `
  --name pack-20260404
```

## 6. 直接生成训练数据集

### 6.1 生成 `group1`

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass\yolo
```

### 6.2 生成 `group2`

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group2 `
  --dataset-dir D:\sinan-captcha-work\datasets\group2\firstpass\yolo
```

### 6.3 一次默认会生成多少条训练数据

当前公开生成器只有两个预设：

- `smoke`
  - 每次生成 `20` 条
- `firstpass`
  - 每次生成 `200` 条

如果你不显式传 `--preset`，默认就是：

- `firstpass`

所以这页里的默认命令，一次会生成：

- `200` 条样本

如果你只是想先跑通流程，显式加上：

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --preset smoke `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\smoke\yolo
```

这时会只生成：

- `20` 条样本

### 6.4 如果要生成更多训练数据，应该怎么做

当前普通用户 CLI 没有单独暴露 `--sample-count`。

所以“生成更多”有两种稳定做法：

1. 多跑几次，生成多个版本目录
2. 让维护者准备更大的 preset

普通用户最稳的做法是多跑几次，但每次都输出到不同目录，例如：

```powershell
Set-Location D:\sinan-captcha-generator
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass_v2\yolo
```

再来一次：

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass_v3\yolo
```

注意：

- 当前公开用户路径是一条命令产出一个完整数据集目录
- 如果你对同一个 `dataset-dir` 再跑一次，并带 `--force`，会覆盖原有生成内容，不会自动追加

### 6.5 第一次生成好的训练数据，后面还能不能继续用

可以。

只要下面这些文件还在：

- `dataset.yaml`
- `images\`
- `labels\`

同一份训练数据可以反复用于：

- `dry-run`
- 冒烟训练
- 正式训练
- 不同超参数训练
- 不同模型版本对比

建议做法：

- 生成好的数据集目录尽量视为只读版本
- 训练时改训练运行名，不要改数据目录
- 如果要生成新一轮数据，改数据版本目录名，而不是覆盖旧目录

## 7. 生成成功后应看到什么

每个数据集目录都至少应包含：

- `dataset.yaml`
- `images/`
- `labels/`
- `.sinan/`

其中：

- `dataset.yaml`
  - 是训练 CLI 的正式入口
- `images/`
  - 给 YOLO 训练直接读取
- `labels/`
  - 是 YOLO 标签
- `.sinan/`
  - 保留 raw、manifest、job 等审计线索

## 8. 下一步怎样开始训练

### 8.1 先做 `dry-run`

`group1`：

```powershell
Set-Location D:\sinan-captcha-work
uv run sinan train group1 `
  --dataset-version firstpass `
  --name firstpass `
  --dry-run
```

`group2`：

```powershell
Set-Location D:\sinan-captcha-work
uv run sinan train group2 `
  --dataset-version firstpass `
  --name firstpass `
  --dry-run
```

### 8.2 再做冒烟训练

`group1`：

```powershell
uv run sinan train group1 `
  --dataset-version firstpass `
  --name smoke `
  --epochs 1 `
  --batch 8
```

`group2`：

```powershell
uv run sinan train group2 `
  --dataset-version firstpass `
  --name smoke `
  --epochs 1 `
  --batch 8
```

### 8.3 第一次训练完成后，怎么看训练效果

先看最基本的 3 件事：

- 训练目录里有没有 `weights\best.pt`
- 训练目录里有没有 `results.csv`
- `uv run yolo detect predict` 能不能在验证集图片上跑出合理检测框

完整检查方式继续读：

- [训练完成后的模型使用与测试](./use-and-test-trained-models.md)

## 9. 最容易踩的坑

### 9.1 生成器安装目录和生成器工作区混了

表现：

- 命令能执行，但素材、任务记录、日志落在你意料之外的目录

处理：

- 所有生成器命令统一显式带上：
  - `--workspace D:\sinan-captcha-generator\workspace`

### 9.2 训练目录里没有 `dataset.yaml`

表现：

- `uv run sinan train ...` 一启动就报路径错误

处理：

- 回到 `make-dataset` 步骤，重新确认 `--dataset-dir`

### 9.3 素材包导入失败

常见原因：

- 素材目录结构不完整
- 图像损坏
- `classes.yaml` 和图标目录不一致

### 9.4 没有现成 `materials-pack/` 或 `materials-pack.zip`

处理：

- 当前普通用户链路不建议在训练机上从规格文件临时构建素材包
- 直接向交付方要 `materials-pack/`、`materials-pack.zip` 或可访问的下载地址
- 然后改走 `materials import` 或 `materials fetch`

## 10. 这页完成标志

如果你已经做到下面 5 件事，就说明“本地生成训练数据”这条链路跑通了：

1. 初始化了显式生成器工作区
2. 至少导入或抓取过一次素材包
3. 成功生成了 `group1` 或 `group2` 的 YOLO 数据集目录
4. 数据集目录里有 `dataset.yaml`
5. 训练 CLI 能对这个数据集执行 `dry-run`
