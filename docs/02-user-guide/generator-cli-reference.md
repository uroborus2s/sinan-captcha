# 训练者：生成器 CLI 全量参考（`sinan-generator`）

本页覆盖 `sinan-generator` 当前正式命令，并对每个命令补齐：

- 用途
- 适用场景
- 参数说明
- 最小示例
- 成功标志
- 常见误用

源码基线：`2026-04-11`。

## 1. 调用方式

Windows 可执行文件：

```powershell
.\sinan-generator.exe <command> ...
```

源码目录调试（Go）：

```bash
go run ./cmd/sinan-generator <command> ...
```

## 2. 命令总览

```text
sinan-generator
├── workspace init
├── workspace show
├── materials import
├── materials fetch
└── make-dataset
```

| 命令 | 主要用途 | 典型使用场景 |
| --- | --- | --- |
| `workspace init` | 初始化生成器工作区目录 | 新机器首次搭建生成器环境 |
| `workspace show` | 检查当前工作区与元数据 | 生成前自检、排查路径配置 |
| `materials import` | 导入本地素材包 | 你已经有离线素材目录 |
| `materials fetch` | 拉取并导入 zip/URL 素材 | 素材包在共享链接或制品仓库 |
| `make-dataset` | 产出 `group1/group2` 训练数据集 | 训练前正式生成数据集版本 |

## 3. `workspace init`

### 3.1 用途

创建或刷新固定工作区目录结构。

### 3.2 适用场景

- 新训练机第一次使用生成器。
- 工作区目录被误删或结构损坏后重建。

### 3.3 语法

```powershell
sinan-generator workspace init [--workspace <path>]
```

### 3.4 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |

### 3.5 最小示例

```powershell
.\sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
```

### 3.6 成功标志

- 命令正常退出（返回码 `0`）。
- 指定工作区下出现预期目录结构。

### 3.7 常见误用

- 在错误盘符初始化，后续素材和数据都写到错误路径。
- 误以为会自动导入素材；该命令只建目录，不导入任何素材。

## 4. `workspace show`

### 4.1 用途

打印当前工作区元数据与目录布局。

### 4.2 适用场景

- 生成前核对当前使用的是哪个工作区。
- 交接时确认同事的 workspace 配置是否一致。

### 4.3 语法

```powershell
sinan-generator workspace show [--workspace <path>]
```

### 4.4 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |

### 4.5 最小示例

```powershell
.\sinan-generator.exe workspace show --workspace D:\sinan-captcha-generator\workspace
```

### 4.6 成功标志

- 输出包含当前 workspace 的实际路径和目录布局信息。

### 4.7 常见误用

- 忽略 `show` 结果，直接开始生成，最终把数据写到非预期目录。

## 5. `materials import`

### 5.1 用途

把本地素材目录导入到生成器工作区。

### 5.2 适用场景

- 你拿到的是离线素材目录（非 zip、非 URL）。
- 需要把素材纳入生成器的标准管理视图。

### 5.3 语法

```powershell
sinan-generator materials import --from <dir> [--workspace <path>] [--name <name>] [--task group1|group2]
```

### 5.4 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--from` | 是 | 无 | 本地素材包目录。 |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |
| `--name` | 否 | 目录名 | 导入后的素材集名。 |
| `--task` | 否 | 空 | 单任务素材包时用 `group1` 或 `group2` 做任务校验。 |

### 5.5 最小示例

```powershell
.\sinan-generator.exe materials import `
  --workspace D:\sinan-captcha-generator\workspace `
  --from D:\materials-pack-v3 `
  --name official-v3
```

### 5.6 成功标志

- 输出包含导入结果摘要。
- `workspace` 下可见导入后的素材集。

### 5.7 常见误用

- 把 `--from` 指到 zip 文件；`import` 只接受目录，zip 请用 `materials fetch`。
- 不传 `--task` 就拿单任务素材包做双任务生成，导致后续数据缺素材。

## 6. `materials fetch`

### 6.1 用途

从 zip / URL 拉取素材包并导入工作区。

### 6.2 适用场景

- 素材包托管在 HTTP 链接、`file://` 链接或本地 zip。
- 需要把远端发布素材快速纳入本地工作区。

### 6.3 语法

```powershell
sinan-generator materials fetch --source <source> [--workspace <path>] [--name <name>] [--task group1|group2]
```

### 6.4 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--source` | 是 | 无 | `http(s)` URL、`file://` URL，或本地 zip 路径。 |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |
| `--name` | 否 | 来源文件名 | 导入后的素材集名。 |
| `--task` | 否 | 空 | 单任务素材包校验范围。 |

### 6.5 最小示例

```powershell
.\sinan-generator.exe materials fetch `
  --workspace D:\sinan-captcha-generator\workspace `
  --source https://example.com/materials-pack.zip `
  --name official-pack-v1
```

### 6.6 成功标志

- 下载与导入都成功完成。
- 输出中出现导入素材集名称与路径。

### 6.7 常见误用

- URL 需要认证却未配置，导致拉取失败。
- 以为 `fetch` 会自动开始生成数据；它只负责“拉取+导入”。

## 7. `make-dataset`

### 7.1 用途

按 preset 和素材配置生成可训练数据集目录（`group1` 或 `group2`）。

### 7.2 适用场景

- 训练前生产正式数据集版本。
- 做 smoke/hard 分层实验并对比训练效果。

### 7.3 语法

```powershell
sinan-generator make-dataset `
  [--task group1|group2] `
  [--preset firstpass|hard|smoke] `
  [--dataset-dir <dir>] `
  [--workspace <path>] `
  [--materials <official/name|local/name>] `
  [--materials-source <dir|zip|url>] `
  [--runtime-seed <int>] `
  [--override-file <json>] `
  [--force]
```

### 7.4 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--task` | 否 | `group1` | 数据任务类型。 |
| `--preset` | 否 | `firstpass` | 预设强度。 |
| `--dataset-dir` | 强烈建议是 | 空 | 目标数据集目录；生产环境建议显式指定。 |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |
| `--materials` | 否 | 空 | 固定素材选择器，格式 `official/name` 或 `local/name`。 |
| `--materials-source` | 否 | 空 | 临时素材来源（目录、zip、URL）。 |
| `--runtime-seed` | 否 | `0` | 指定后可重放同一轮生成。 |
| `--override-file` | 否 | 空 | JSON 覆盖文件（如 `sample_count/sampling/effects`）。 |
| `--force` | 否 | `false` | 覆盖输出目录已有文件。 |

内置预设样本数：

- `firstpass=200`
- `hard=200`
- `smoke=20`

### 7.5 最小示例

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group2 `
  --preset hard `
  --dataset-dir D:\sinan-captcha-work\datasets\group2\hard-v1 `
  --materials official/official-pack-v1 `
  --force
```

### 7.6 成功标志

- `dataset-dir` 下生成完整数据集目录与清单文件。
- 命令退出码为 `0`，且无素材缺失错误。

### 7.7 常见误用

- 不传 `--dataset-dir`，结果数据输出到非预期默认路径。
- 同时混用 `--materials` 与错误的 `--materials-source`，导致素材来源不一致。
- 忽略 `--runtime-seed`，回归对比时无法复现同批样本。

## 8. 推荐执行顺序

```text
workspace init -> workspace show -> materials import/fetch -> make-dataset
```

如果你要继续看训练器 `sinan` 命令，请读：
[训练者：训练器 CLI 全量参考](./trainer-cli-reference.md)
