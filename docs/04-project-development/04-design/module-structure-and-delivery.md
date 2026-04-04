# 模块结构与构建交付设计

- 文档状态：草稿
- 当前阶段：DESIGN
- 目标读者：架构/开发、项目维护者、训练实施者
- 负责人：Codex
- 上游输入：
  - `docs/04-project-development/04-design/technical-selection.md`
  - `docs/04-project-development/04-design/module-boundaries.md`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/graphic-click-generator-design.md`
- 关联需求：`REQ-001`、`REQ-004`、`REQ-007`、`REQ-008`

## 1. 设计结论

当前项目应长期保持两条正式实现主线：

1. Go 生成器主线
2. Python 训练与数据工程主线

它们通过文件契约对接，而不是互相嵌套调用。

收口后的正式入口只保留两个：

1. `sinan-generator`
2. `sinan`

设计约束：

- Go 负责素材目录初始化、素材校验、样本生成、批次 QA
- Python 负责素材包构建、数据转换、自动标注、训练、评估
- 不再保留 `scripts/*` 作为正式对外入口
- 如需后续批处理脚本，也只能调用这两个正式 CLI，不能承载业务逻辑

## 2. 顶层目录划分

推荐的仓库顶层目录如下：

```text
sinan-captcha/
  pyproject.toml
  uv.lock
  README.md
  .gitignore
  docs/
  generator/
  core/
  tests/
  configs/
  materials/
  datasets/
  reports/
  dist/
```

说明：

- `generator/`：Go 生成器工程
- `core/`：Python 训练与数据工程核心包，以及统一总 CLI
- `tests/`：Go 和 Python 测试
- `configs/`：运行配置
- `materials/`：背景图、图标图、类别表等素材
- `datasets/`：运行时数据目录，不作为代码包一部分
- `reports/`：评估与 QA 报告
- `dist/`：构建产物目录

## 3. 需要开发的模块

真正需要开发的代码模块分为 10 类：

1. Go 生成器 CLI
2. Go 生成器内部模块
3. Python 总 CLI
4. Python 数据契约模块
5. Python 素材包构建模块
6. Python 自动标注模块
7. Python 数据转换模块
8. Python 训练模块
9. Python 推理后处理模块
10. Python 评估与报告模块

其中：

- 必须先做：1 到 7
- 可以后续迭代：8 到 10
- 本地发布与训练目录初始化已纳入 Python CLI 的正式职责

## 4. Go 主线目录

```text
generator/
  go.mod
  cmd/
    sinan-generator/
      main.go
  internal/
    backend/
    config/
    export/
    layout/
    material/
    qa/
    render/
    sampler/
    truth/
  configs/
    default.yaml
    group1.firstpass.yaml
    group2.firstpass.yaml
```

### 4.1 `generator/cmd/sinan-generator`

- 语言：Go
- 模块职责：
  - 提供生成器总 CLI
  - 暴露 `workspace init|show`、`materials import|fetch`、`make-dataset`
  - 固定工作区初始化与默认预设展开
  - 直接输出可交给训练 CLI 的任务专属训练数据集目录
- 构建方式：
  - `go build -o ../dist/generator/windows-amd64/sinan-generator.exe ./cmd/sinan-generator`
- 打包产物：
  - Windows 下是单独 `.exe`
  - Linux 下是单独 ELF 二进制
- 部署方式：
  - 首版直接复制二进制到训练机
  - 运行时自动创建固定工作区，不依赖 EXE 同级目录

### 4.2 `generator/internal/material`

- 语言：Go
- 模块职责：
  - 初始化 `materials/` 目录骨架
  - 加载背景图、图标图、类别表
  - 在生成前执行完整解码校验
- 部署方式：
  - 随生成器主程序部署
  - 运行时依赖 `materials/`

### 4.3 `generator/internal/backend`

- 语言：Go
- 模块职责：
  - 定义 backend 接口
  - 封装 `native` 与未来的 `gocaptcha` adapter
  - 统一返回候选样本与内部真值对象

### 4.4 `generator/internal/export`

- 语言：Go
- 模块职责：
  - 导出多模式图片、`labels.jsonl`、`manifest.json`
  - 记录 `mode`、`backend`、`seed`、素材版本和真值校验结果

### 4.5 `generator/internal/qa`

- 语言：Go
- 模块职责：
  - 批次级质量检查
  - 执行真值一致性校验、重放校验和负样本校验

### 4.6 其他内部模块

- `generator/internal/config`：读取生成配置
- `generator/internal/sampler`：目标类与干扰项抽样、随机种子复现
- `generator/internal/layout`：对象摆放与碰撞处理
- `generator/internal/render`：click/slide 图像渲染
- `generator/internal/truth`：`gold` 门禁和重放逻辑

## 5. Python 主线目录

```text
core/
  __init__.py
  cli.py
  common/
  dataset/
  materials/
  autolabel/
  convert/
  ops/
  release/
  train/
    group1/
    group2/
  inference/
  evaluate/
```

### 5.1 `core/cli.py`

- 语言：Python
- 模块职责：
  - 作为 Python 侧唯一正式对外入口
  - 将训练目录初始化、环境检查、素材包构建、数据转换、训练、评估、发布等能力收口为 `sinan`
- 构建方式：
  - 打包进 Python wheel
- 打包产物：
  - `sinan-captcha` wheel 中的 console script

### 5.2 `core/dataset`

- 语言：Python
- 模块职责：
  - JSONL schema 校验
  - 类别表加载
  - 数据版本元信息

### 5.3 `core/materials`

- 语言：Python
- 模块职责：
  - 从远端 provider 或本地目录构建离线 `materials/` 包
  - 生成 `classes.yaml`、`backgrounds.csv`、`icons.csv`
  - 为 Go 生成器准备已索引的素材目录
- 正式入口：
  - `uv run sinan materials build`
- 使用边界：
  - 这是维护者或历史批次迁移入口，不是普通用户生成器主链路

### 5.4 `core/autolabel`

- 语言：Python
- 模块职责：
  - 第二专项规则法预标注
  - 第一专项暖启动模型预标注

### 5.5 `core/train/group1`

- 语言：Python
- 模块职责：
  - 第一专项训练参数组织
  - 训练前校验
  - 训练摘要归档
- 正式入口：
  - `uv run sinan train group1`

### 5.6 `core/train/group2`

- 语言：Python
- 模块职责：
  - 第二专项训练参数组织
  - 训练前校验
  - 训练摘要归档
- 正式入口：
  - `uv run sinan train group2`

### 5.7 `core/ops`

- 语言：Python
- 模块职责：
  - 训练机环境自检
  - 对 PyTorch、YOLO、GPU 能力做最小探测
  - 创建训练目录自己的运行时 `pyproject.toml`、`.python-version` 和标准目录结构
- 正式入口：
  - `uv run sinan env check`
  - `uvx --from sinan-captcha sinan env setup-train`

### 5.8 `core/release`

- 语言：Python
- 模块职责：
  - 本地构建 wheel / sdist
  - 本地上传 PyPI / TestPyPI
  - 组装 Windows 交付包
- 正式入口：
  - `uv run sinan release build`
  - `uv run sinan release publish`
  - `uv run sinan release package-windows`

### 5.9 `core/inference` 与 `core/evaluate`

- `core/inference`：推理结果到业务语义的后处理
- `core/evaluate`：指标计算、失败样本导出、报告生成

## 6. 测试目录

推荐目录：

```text
tests/
  python/
  go/
```

运行约束：

- Python：`uv run python -m unittest discover -s tests/python -p 'test_*.py'`
- Go：`go test ./...`

## 7. 配置和资产目录

### 7.1 `configs/`

- 内容：
  - Python 侧任务配置
  - 训练参数配置
  - 路径配置

### 7.2 `materials/`

- 内容：
  - 背景图
  - 图标图
  - `classes.yaml`
  - `backgrounds.csv`
  - `icons.csv`
- 规则：
  - 不打进 wheel
  - 不打进 Go 二进制
  - 作为独立运行资产管理

### 7.3 `datasets/`

- 内容：
  - `raw/`
  - `interim/`
  - `reviewed/`
  - `group1/yolo/`
  - `group2/master/`
  - `group2/tile/`
  - `group2/splits/`
  - `group2/dataset.json`

### 7.4 `reports/`

- 内容：
  - QA 报告
  - 评估报告
  - 失败样本清单

## 8. 构建与打包策略

### 8.1 Go 生成器

- 开发期运行：
  - `go run ./cmd/sinan-generator --help`
- 正式编译：
  - `go build -o ../dist/generator/windows-amd64/sinan-generator.exe ./cmd/sinan-generator`
- 交付形态：
  - `sinan-generator.exe`
  - 可选预构建素材目录或压缩包
  - 工作区会在首次运行时自动创建并展开 `presets/`

### 8.2 Python 训练链路

- 开发期运行：
  - `uv sync`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
- 正式打包：
  - `uv build`
- 交付形态：
  - `dist/*.whl`
  - `dist/*.tar.gz`

### 8.3 多交付物原则

- Go 二进制和 Python 运行时天然不同
- 素材和数据体积大，不适合进入代码包
- 训练过程依赖本地目录、权重和数据集

结论：

- 应采用“Go 二进制 + Python wheel + 运行资产目录”的交付方式

## 9. 子模块与交付物对照表

| 子模块 | 语言 | 是否编译 | 打包产物 | 部署位置 |
|---|---|---|---|---|
| `generator/cmd/sinan-generator` | Go | 是 | `.exe` / Linux binary | 训练机本地 |
| `generator/internal/*` | Go | 跟随主程序 | 无独立产物 | 随生成器部署 |
| `core/cli.py` | Python | 否 | wheel console script | Python 环境 |
| `core/dataset` | Python | 否 | wheel 内部模块 | Python 环境 |
| `core/materials` | Python | 否 | wheel 内部模块 | Python 环境 |
| `core/autolabel` | Python | 否 | wheel 内部模块 | Python 环境 |
| `core/train/group1` | Python | 否 | wheel 内部模块 | Python 环境 |
| `core/train/group2` | Python | 否 | wheel 内部模块 | Python 环境 |
| `core/inference` | Python | 否 | wheel 内部模块 | Python 环境 |
| `core/evaluate` | Python | 否 | wheel 内部模块 | Python 环境 |
| `materials/*` | 图片 / YAML | 否 | 素材包 | 训练机本地 |
| `datasets/*` | 图片 / JSONL / YAML | 否 | 数据目录 | 训练机本地 |
| `reports/*` | Markdown / JSON / CSV | 否 | 报告目录 | 训练机本地 / 归档目录 |

## 10. 推荐实现顺序

1. `generator/`
2. `materials/`
3. `core/cli.py`
4. `core/dataset`
5. `core/materials`
6. `core/autolabel`
7. `core/train/group2`
8. `core/train/group1`
9. `core/inference`
10. `core/evaluate`

不要先做：

- HTTP 服务层
- 公网部署层
- 多平台 GUI

## 11. 最终结论

从开发视角看，这个项目最合理的结构是：

- 一套 Go 生成器工程
- 一个拥有可插拔 backend 的生成器控制层
- 一套 Python 训练工程
- 一个统一的 Python 总 CLI
- 三类非代码资产目录：素材、数据、报告

从交付视角看，最合理的交付形态是：

- Go 二进制包
- Python wheel 包
- 配置包
- 素材包
- 数据目录和报告目录

不要再回到“脚本入口散落、一个功能一个脚本”的结构。对训练型项目，这种设计只会放大维护成本和口径漂移。
