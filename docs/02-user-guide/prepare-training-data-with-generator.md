# 训练者角色：使用生成器准备训练数据

这页只讲训练者怎么用 `sinan-generator` 把素材整理成可训练的数据集目录。

## 1. 先分清 3 个目录

- 生成器安装目录：
  - 例如 `D:\sinan-captcha-generator`
  - 放 `sinan-generator.exe`
- 生成器工作区：
  - 例如 `D:\sinan-captcha-generator\workspace`
  - 放 `presets/`、`materials/`、`jobs/`、`logs/`
- 训练目录：
  - 例如 `D:\sinan-captcha-work`
  - 放 `datasets/`、训练结果和报告

这三者不要混用。`make-dataset` 的输出应该落到训练目录下的 `datasets/`。

## 2. 你要准备什么

至少要有：

- `sinan-generator.exe`
- 一个固定工作区目录
- 一个素材包目录、素材 zip，或一个可访问的素材包 URL
- 一个训练目录，例如 `D:\sinan-captcha-work`

推荐工作区：

```text
D:\sinan-captcha-generator\workspace
```

## 3. 素材包应该长什么样

一个最小可用的素材包目录结构如下：

```text
D:\materials-pack\
  backgrounds\
    bg_001.png
    bg_002.jpg
  group1\
    icons\
      icon_house\
        001.png
        002.png
      icon_leaf\
        001.png
  group2\
    shapes\
      shape_badge\
        001.png
      shape_shield\
        001.png
  manifests\
    materials.yaml
    group1.classes.yaml
    group2.shapes.yaml
```

各目录含义：

- `backgrounds/`
  - 背景图素材。
  - 支持 `.png`、`.jpg`、`.jpeg`。
- `group1/icons/<class_name>/`
  - 点选任务专用图标池。
  - 每个子目录代表 1 个点选类别。
  - 目录名必须和 `group1.classes.yaml` 中的 `name` 一致。
  - 最好使用透明背景 PNG。
- `group2/shapes/<shape_name>/`
  - 滑块缺口任务专用形状池。
  - 每个子目录代表 1 种缺口形状模板。
  - 目录名必须和 `group2.shapes.yaml` 中的 `name` 一致。
  - 这些图形只用于雕刻缺口 mask，不会成为 `group2` 的训练类别。
  - 边缘越干净，生成出来的缺口越稳定。
- `manifests/materials.yaml`
  - 素材包 schema 元信息。
- `manifests/group1.classes.yaml`
  - 点选类别清单。
  - 决定有哪些 `group1/icons/<class_name>/` 目录必须存在。
- `manifests/group2.shapes.yaml`
  - 缺口形状清单。
  - 决定有哪些 `group2/shapes/<shape_name>/` 目录必须存在。

`materials.yaml` 示例：

```yaml
schema_version: 2
```

`group1.classes.yaml` 示例：

```yaml
classes:
  - id: 0
    name: icon_house
    zh_name: 房子
  - id: 1
    name: icon_leaf
    zh_name: 叶子
```

`group2.shapes.yaml` 示例：

```yaml
shapes:
  - id: 0
    name: shape_badge
    zh_name: 徽章缺口
  - id: 1
    name: shape_shield
    zh_name: 盾牌缺口
```

字段说明：

- `id`
  - 素材条目 ID。
  - `group1` 会写进点选标签；`group2` 主要用于素材管理和审查。
- `name`
  - 条目英文名，同时也是对应目录名。
- `zh_name`
  - 中文名，方便人工阅读和审查。

不要再把点选图标和缺口形状放在同一个目录里。当前生成器会严格按 `group1/icons/` 和 `group2/shapes/` 两个池子分别读取。

## 3.1 旧素材包怎么迁移

如果你手上还是旧布局，至少要做下面 4 个调整：

- 把旧的点选图标目录迁到 `group1/icons/<class_name>/`
- 把旧的缺口形状目录迁到 `group2/shapes/<shape_name>/`
- 把旧的点选类别清单改名成 `manifests/group1.classes.yaml`
- 新增 `manifests/group2.shapes.yaml`，把缺口形状清单单独维护

最常见的迁移映射：

```text
旧结构                          新结构
icons/icon_house/         ->    group1/icons/icon_house/
icons/icon_leaf/          ->    group1/icons/icon_leaf/
shapes/shape_badge/       ->    group2/shapes/shape_badge/
classes.yaml              ->    manifests/group1.classes.yaml
```

如果你已经把 `group1` 和 `group2` 素材拆成两个独立包，也可以继续用，但要注意下面这条规则：

- `materials import` / `materials fetch` 默认按“全量素材包”校验
- 如果 zip 或目录里只有 `group1` 或只有 `group2`，导入时要显式传 `--task group1` 或 `--task group2`
- `make-dataset` 和 `auto-train` 在建数阶段已经支持按任务校验，不会再要求另一个任务的目录同时存在

## 4. 初始化工作区

```powershell
Set-Location D:\sinan-captcha-generator
.\sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
```

如果你想看当前工作区布局和激活中的素材集：

```powershell
.\sinan-generator.exe workspace show --workspace D:\sinan-captcha-generator\workspace
```

## 5. 导入素材、下载素材、自动拉取素材

### 5.1 从本地目录导入素材

适合你已经把素材整理成目录的情况：

```powershell
.\sinan-generator.exe materials import `
  --workspace D:\sinan-captcha-generator\workspace `
  --from D:\materials-pack
```

可选参数：

| 参数 | 说明 |
| --- | --- |
| `--workspace` | 工作区目录。 |
| `--from` | 本地素材包目录，目录内部必须包含 `backgrounds/`、`group1/icons/`、`group2/shapes/`、`manifests/materials.yaml`、`manifests/group1.classes.yaml`、`manifests/group2.shapes.yaml`。 |
| `--name` | 可选素材集名称；不传时默认使用目录名。 |
| `--task` | 可选。只有当素材包只包含 `group1` 或只包含 `group2` 时才传；可选值是 `group1` 或 `group2`。 |

导入后，素材会复制到工作区的 `materials/local/<name>/`，并自动设为当前激活素材集。

### 5.2 从 zip 包或 URL 下载素材

适合素材由维护者打成 zip 或放到 HTTP 地址的情况：

```powershell
.\sinan-generator.exe materials fetch `
  --workspace D:\sinan-captcha-generator\workspace `
  --source D:\materials-pack.zip `
  --name official-pack-v1
```

或：

```powershell
.\sinan-generator.exe materials fetch `
  --workspace D:\sinan-captcha-generator\workspace `
  --source https://example.com/materials-pack.zip `
  --name official-pack-v1
```

可选参数：

| 参数 | 说明 |
| --- | --- |
| `--workspace` | 工作区目录。 |
| `--source` | 本地 zip 路径、`file://` URL，或 `http(s)://` URL。 |
| `--name` | 可选素材集名称；不传时默认使用 zip 文件名或 URL 文件名。 |
| `--task` | 可选。只有当 zip 里只包含 `group1` 或只包含 `group2` 时才传；可选值是 `group1` 或 `group2`。 |

下载后，素材会解压到工作区的 `materials/official/<name>/`，并自动设为当前激活素材集。

例如，只导入 `group1` 点选素材包：

```powershell
.\sinan-generator.exe materials import `
  --workspace D:\sinan-captcha-generator\workspace `
  --from D:\materials-pack-group1 `
  --task group1
```

例如，只下载 `group2` 缺口形状 zip：

```powershell
.\sinan-generator.exe materials fetch `
  --workspace D:\sinan-captcha-generator\workspace `
  --source D:\materials-pack-group2.zip `
  --task group2 `
  --name group2-pack-v1
```

### 5.3 把中转目录增量并入现有素材集

如果你手上不是完整素材包，而是一批零散的新背景图、点选图标和透明缺口图，可以先放到一个中转目录，再用 `materials merge` 直接并进已有素材集根目录。

中转目录结构：

```text
D:\incoming-materials\
  backgrounds\
    bg_001.jpg
    bg_002.png
  group1\
    house.png
    star.png
  group2\
    ticket-gap.png
    star-gap.png
```

规则说明：

- `backgrounds/`
  - 每个文件都会追加到现有背景池。
- `group1/`
  - 当前按“1 张图 = 1 个新类别”处理。
  - 类别名默认取文件名去扩展名后的结果，例如 `star.png -> star`。
  - 如果现有素材集里已经有同名类别，会自动补成 `star_002`、`star_003`。
- `group2/`
  - 每个透明缺口图都会追加成 1 个新 shape。
  - shape 名默认取文件名去扩展名后的结果。
  - 合并时会自动：
    - 按 alpha 裁掉四周透明边；
    - 补成方形透明画布；
    - 写入 `group2/shapes/<shape_name>/001.png`。
  - 这一步是为了避免细长透明 gap 直接缩放后形状被压扁。

命令示例：

```powershell
.\sinan-generator.exe materials merge `
  --into D:\materials-pack `
  --from D:\incoming-materials
```

合并后会自动：

- 补齐 `manifests/materials.yaml`
- 追加 `manifests/group1.classes.yaml`
- 追加 `manifests/group2.shapes.yaml`
- 运行当前素材校验

### 5.4 生成数据时自动拉取素材

如果当前工作区还没有激活素材集，可以在 `make-dataset` 里直接传 `--materials-source`：

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --materials-source https://example.com/materials-pack.zip `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass
```

注意：

- `--materials-source` 只在当前工作区还没有激活素材集时才会参与拉取。
- 如果你想显式切换到某个已导入素材集，优先用 `--materials local/<name>` 或 `--materials official/<name>`。
- 如果 `--materials-source` 指向的是单任务素材包，`make-dataset` 会按当前 `--task` 自动做 task-scoped 校验。

## 6. 生成训练数据

### 6.1 生成 `group1`

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass
```

### 6.2 生成 `group2`

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group2 `
  --dataset-dir D:\sinan-captcha-work\datasets\group2\firstpass
```

## 7. `make-dataset` 的参数都是什么意思

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--workspace` | 否 | 工作区目录。不传时会落到默认工作区，例如 Windows 下的 `%LOCALAPPDATA%\SinanGenerator`。公开示例推荐总是显式传。 |
| `--task` | 否 | 数据集任务类型，`group1` 或 `group2`，默认 `group1`。 |
| `--preset` | 否 | 预设名，`smoke`、`firstpass`、`hard`。默认 `firstpass`。 |
| `--dataset-dir` | 是 | 生成后的数据集目录。目录不存在时会创建。 |
| `--materials` | 否 | 显式选择一个已经导入到工作区的素材集，格式是 `official/<name>` 或 `local/<name>`。 |
| `--materials-source` | 否 | 当前工作区没有激活素材集时，用这个参数自动从本地目录、zip、`file://` URL 或 `http(s)://` URL 获取素材。 |
| `--override-file` | 否 | JSON 覆盖文件，用来临时改样本数量、采样范围和视觉扰动。 |
| `--force` | 否 | 如果你要覆盖已有的 `dataset-dir`，必须显式加这个参数。 |

## 8. 什么时候用 `preset`，什么时候用 `override-file`

### 8.1 用 `preset`

当前内置：

- `smoke`
- `firstpass`
- `hard`

内置预设的实际文件名在工作区里是：

- `presets/smoke.yaml`
- `presets/group1.firstpass.yaml`
- `presets/group2.firstpass.yaml`
- `presets/group1.hard.yaml`
- `presets/group2.hard.yaml`

默认规模和难度：

| 预设 | 内置样本数 | 适合场景 |
| --- | --- | --- |
| `smoke` | 20 | 验证命令、目录和训练链路是否能跑通。 |
| `firstpass` | 200 | 第一轮正式训练数据。 |
| `hard` | 200 | 样本量与 `firstpass` 接近，但会加更强的阴影、模糊和遮挡。 |

例如：

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group1 `
  --preset hard `
  --dataset-dir D:\sinan-captcha-work\datasets\group1\hard_v1
```

### 8.2 用 `override-file`

如果你要临时覆盖样本规模或难度，又不想改工作区里的 preset 文件，用 `--override-file`。

示例：

```powershell
.\sinan-generator.exe make-dataset `
  --workspace D:\sinan-captcha-generator\workspace `
  --task group2 `
  --preset hard `
  --override-file D:\study\trial_0002\generator_override.json `
  --dataset-dir D:\sinan-captcha-work\datasets\group2\v2
```

一个最小 JSON 示例：

```json
{
  "project": {
    "sample_count": 320
  },
  "sampling": {
    "target_count_min": 3,
    "target_count_max": 5,
    "distractor_count_min": 5,
    "distractor_count_max": 8
  },
  "effects": {
    "common": {
      "scene_veil_strength": 1.45,
      "background_blur_radius_min": 1,
      "background_blur_radius_max": 2
    },
    "click": {
      "icon_shadow_alpha_min": 0.28,
      "icon_shadow_alpha_max": 0.36,
      "icon_shadow_offset_x_min": 2,
      "icon_shadow_offset_x_max": 3,
      "icon_shadow_offset_y_min": 3,
      "icon_shadow_offset_y_max": 4,
      "icon_edge_blur_radius_min": 1,
      "icon_edge_blur_radius_max": 2
    }
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `project.sample_count` | 这次要生成多少条样本。 |
| `sampling.target_count_min/max` | `group1` 每张场景图最少/最多放多少个目标图标。 |
| `sampling.distractor_count_min/max` | `group1` 每张场景图最少/最多放多少个干扰图标。 |
| `effects.common.scene_veil_strength` | 场景遮罩强度，值越大越容易遮挡背景细节。 |
| `effects.common.background_blur_radius_min/max` | 背景模糊半径的随机范围。 |
| `effects.click.icon_shadow_alpha_min/max` | `group1` 图标阴影透明度范围。 |
| `effects.click.icon_shadow_offset_x/y_min/max` | `group1` 图标阴影偏移范围。 |
| `effects.click.icon_edge_blur_radius_min/max` | `group1` 图标边缘模糊范围。 |
| `effects.slide.gap_shadow_alpha_min/max` | `group2` 缺口阴影透明度范围。 |
| `effects.slide.gap_shadow_offset_x/y_min/max` | `group2` 缺口阴影偏移范围。 |
| `effects.slide.tile_edge_blur_radius_min/max` | `group2` 拼图块边缘模糊范围。 |

说明：

- 所有 `*_min` / `*_max` 字段表示随机采样区间，不是固定值。
- `sampling.*` 主要影响 `group1`。
- `effects.click.*` 只影响 `group1`。
- `effects.slide.*` 只影响 `group2`。
- 覆盖文件只接受已知字段，写错字段名会直接报错。
- 传了 `--override-file` 后，最终生效配置会额外写到 `<dataset-dir>\.sinan\effective-config.yaml`，方便你复盘。

## 9. 生成完成后检查什么

### `group1`

至少应有：

- `dataset.json`
- `scene-yolo/`
- `query-yolo/`
- `splits/`
- `.sinan/raw/`
- `.sinan/manifest.json`
- `.sinan/job.json`

### `group2`

至少应有：

- `dataset.json`
- `master/`
- `tile/`
- `splits/`
- `.sinan/raw/`
- `.sinan/manifest.json`
- `.sinan/job.json`

如果你重跑同一个目录，需要显式加 `--force`；否则应该改用新的版本目录，例如 `firstpass_v2`、`hard_r0002`。

## 10. 下一步

数据准备完后，继续读：

- [训练者角色：使用训练器完成训练、测试与评估](./from-base-model-to-training-guide.md)

如果你准备让控制器自己调数据和开训，继续读：

- [训练者角色：使用自动化训练](./auto-train-on-training-machine.md)
