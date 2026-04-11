# 训练者：生成器 CLI 全量参考（`sinan-generator`）

本页覆盖 `sinan-generator` 当前所有正式命令（源码基线：2026-04-11）。

## 1. 调用方式

Windows 可执行文件：

```powershell
.\sinan-generator.exe <command> ...
```

源码目录调试（Go）：

```bash
go run ./cmd/sinan-generator <command> ...
```

## 2. 命令树

```text
sinan-generator
├── workspace init
├── workspace show
├── materials import
├── materials fetch
└── make-dataset
```

## 3. `workspace init`

用途：创建或刷新固定工作区目录结构。

语法：

```powershell
sinan-generator workspace init [--workspace <path>]
```

参数：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |

示例：

```powershell
.\sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
```

## 4. `workspace show`

用途：打印当前工作区 metadata 与 layout。

语法：

```powershell
sinan-generator workspace show [--workspace <path>]
```

参数：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |

## 5. `materials import`

用途：将本地目录素材包导入工作区。

语法：

```powershell
sinan-generator materials import --from <dir> [--workspace <path>] [--name <name>] [--task group1|group2]
```

参数：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--from` | 是 | 无 | 本地素材包目录。 |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |
| `--name` | 否 | 目录名 | 导入后的素材集名。 |
| `--task` | 否 | 空 | 单任务素材包时用 `group1` 或 `group2` 做任务校验。 |

示例：

```powershell
.\sinan-generator.exe materials import `
  --workspace D:\sinan-captcha-generator\workspace `
  --from D:\materials-pack-v3 `
  --name official-v3
```

## 6. `materials fetch`

用途：从 zip / URL 拉取素材包并导入工作区。

语法：

```powershell
sinan-generator materials fetch --source <source> [--workspace <path>] [--name <name>] [--task group1|group2]
```

参数：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--source` | 是 | 无 | `http(s)` URL、`file://` URL，或本地 zip 路径。 |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |
| `--name` | 否 | 来源文件名 | 导入后的素材集名。 |
| `--task` | 否 | 空 | 单任务素材包校验范围。 |

示例：

```powershell
.\sinan-generator.exe materials fetch `
  --workspace D:\sinan-captcha-generator\workspace `
  --source https://example.com/materials-pack.zip `
  --name official-pack-v1
```

## 7. `make-dataset`

用途：生成可训练数据集目录（`group1` 或 `group2`）。

语法：

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

参数：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--task` | 否 | `group1` | 数据任务类型。 |
| `--preset` | 否 | `firstpass` | 预设强度。 |
| `--dataset-dir` | 强烈建议是 | 空 | 目标数据集目录。生产环境请显式传入。 |
| `--workspace` | 否 | 工作区默认路径 | 覆盖工作区根目录。 |
| `--materials` | 否 | 空 | 固定素材选择器，格式 `official/name` 或 `local/name`。 |
| `--materials-source` | 否 | 空 | 临时素材来源（目录、zip、URL）。 |
| `--runtime-seed` | 否 | `0` | 指定后可重放同一轮生成。 |
| `--override-file` | 否 | 空 | JSON 覆盖文件（`sample_count/sampling/effects`）。 |
| `--force` | 否 | `false` | 覆盖输出目录已有文件。 |

内置预设样本数：

- `firstpass=200`
- `hard=200`
- `smoke=20`

示例：

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group2 `
  --preset hard `
  --dataset-dir D:\sinan-captcha-work\datasets\group2\hard-v1 `
  --materials official/official-pack-v1 `
  --force
```

## 8. 典型执行顺序

```text
workspace init -> materials import/fetch -> make-dataset(group1/group2)
```

如果你要继续看训练器 `sinan` 的所有命令，请读：
[训练者：训练器 CLI 全量参考](./trainer-cli-reference.md)
