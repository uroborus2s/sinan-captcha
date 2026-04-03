# 生成器产品化与工作区规范

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：生成器实现者、交付使用者、训练执行者
- 负责人：Codex
- 关联模块：`MOD-001`

## 1. 目标

本规范只约束生成器产品化后的使用方式，不涉及训练 CLI。

生成器对普通用户的目标只有一个：

- 安装或复制 `sinan-generator.exe` 后，用户只需选择任务类型和数据集目录，就能生成可直接交给训练 CLI 的 YOLO 数据集目录。

## 2. 分发与运行

### 2.1 单 EXE 规则

- 生成器对外分发形态可以是单个 `sinan-generator.exe`
- 单 EXE 不等于所有运行时数据都放进 EXE
- EXE 只承载程序逻辑、内置预设和最小默认配置

### 2.2 不支持便携模式

- 不支持“EXE 同级目录即工作区”的便携模式
- 不支持通过在 EXE 同目录创建标记文件切换工作区
- EXE 升级或替换不得影响工作区中的素材、日志和历史任务

## 3. 首次启动行为

### 3.1 默认工作区

- Windows 首选工作区根目录：`%LOCALAPPDATA%\SinanGenerator`
- 若 `LOCALAPPDATA` 不存在，则回退到系统用户配置目录下的 `SinanGenerator`

### 3.2 首启自动初始化

无论用户是双击 EXE，还是在终端执行命令，首次启动都必须先执行以下动作：

1. 解析默认工作区路径
2. 若工作区不存在，则自动创建
3. 创建固定目录骨架
4. 写入工作区元数据文件
5. 把内置预设展开到工作区可读位置
6. 向用户打印当前工作区位置

### 3.3 首启不得要求用户手工建目录

- 不要求用户先手动创建 `materials/`、`logs/` 或 `jobs/`
- 不要求用户先手工复制默认配置文件

## 4. 工作区目录契约

工作区固定目录结构如下：

```text
%LOCALAPPDATA%\SinanGenerator\
  workspace.json
  presets\
    smoke.yaml
    group1.firstpass.yaml
    group2.firstpass.yaml
  materials\
    official\
    local\
    manifests\
    quarantine\
  cache\
    downloads\
  jobs\
  logs\
```

目录职责如下：

- `workspace.json`
  - 工作区元数据
  - 记录 schema 版本、创建时间、默认素材来源和最近一次使用的素材版本
- `presets/`
  - 从 EXE 内置资源展开出的只读默认预设副本
- `materials/official/`
  - 自动下载或同步得到的官方素材版本目录
- `materials/local/`
  - 用户自行导入的本地素材包
- `materials/manifests/`
  - 工作区级素材清单与索引
- `materials/quarantine/`
  - 校验失败、损坏或不完整素材
- `cache/downloads/`
  - 下载缓存
- `jobs/`
  - 每次生成任务的元数据与结果摘要
- `logs/`
  - 运行日志

## 5. 数据集目录契约

数据集目录不等于工作区，也不等于训练 CLI 的环境目录。

数据集目录由用户在运行时指定，生成器最终产物必须直接落到数据集目录：

```text
<dataset-dir>\
  dataset.yaml
  images\
    train\
    val\
    test\
  labels\
    train\
    val\
    test\
  .sinan\
    raw\
    manifest.json
    job.json
```

约束如下：

- `dataset.yaml` 是生成器交给训练 CLI 的唯一主入口
- `dataset.yaml` 内部不再写 `path:` 字段，`train/val/test` 直接相对 `dataset.yaml` 所在目录组织
- `.sinan/raw/` 保留生成器原始批次与审计线索
- 数据集目录不得依赖 EXE 所在目录
- 训练环境、`.venv`、`pyproject.toml` 和 `runs/` 不属于生成器职责

## 6. 面向用户的命令边界

普通用户只面向下列生成器能力：

- 自动初始化工作区
- 同步或导入素材
- 按预设直接生成训练目录

普通用户主入口收口为一步命令：

```text
sinan-generator make-dataset --workspace <generator-workspace> --task <group1|group2> --dataset-dir <path>
```

执行该命令时，生成器内部必须自动完成：

1. 工作区检查
2. 预设解析
3. 素材存在性检查
4. 原始样本生成
5. 批次 QA
6. 训练目录导出

## 7. 素材来源规则

- 素材优先从工作区读取，不从 EXE 同目录读取
- 本地无素材时，允许按工作区配置自动从网络同步官方素材包
- 网络同步得到的新素材必须以版本目录形式落在 `materials/official/`
- 更新素材不得覆盖旧版本目录

## 8. 配置内置与外置边界

### 8.1 内置到 EXE 的内容

- 默认预设
- 默认目录骨架
- 工作区 schema 版本
- 默认素材同步配置模板

### 8.2 外置到工作区的内容

- `workspace.json`
- 已展开预设副本
- 用户选择的训练目录
- 素材版本索引
- 任务记录与日志

## 9. 非目标

- 不支持便携模式
- 不要求训练 CLI 参与训练数据生成
- 不把素材大文件整体打进 EXE
