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
- 下游交付对象：
  - 生成器实现者
  - Python 训练链路实现者
  - 运维/交付维护者
- 关联需求：`REQ-001`、`REQ-004`、`REQ-007`、`REQ-008`

## 1. 设计结论

这个项目不是单一语言、单一打包物的工程。首版应明确拆成两条实现主线：

1. Go 生成器主线
2. Python 训练主线

拆分原因：

- 图形点选样本生成器最适合直接基于 `go-captcha` 思路和 Go 生态实现
- 数据转换、自动标注、训练、评估最适合保持在 Python 工程里
- 两条主线通过“文件契约”对接，而不是互相嵌套调用

结论：

- Go 负责编译成独立二进制，适合做样本生成器
- Python 负责打成 wheel 或本地项目环境，适合做训练流水线
- 数据和素材不打进代码包，单独作为运行资产管理

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
  src/
    sinan_captcha/
  scripts/
  tests/
  configs/
  materials/
  datasets/
  reports/
  dist/
```

说明：

- `generator/`：Go 生成器工程
- `src/sinan_captcha/`：Python 核心包
- `scripts/`：命令入口和 PowerShell 辅助脚本
- `tests/`：Go 和 Python 的测试
- `configs/`：Python 侧配置
- `materials/`：背景图、图标图、类别表等素材
- `datasets/`：运行时数据目录，不作为代码包一部分
- `reports/`：评估报告、QA 报告、失败样本汇总
- `dist/`：构建产物目录

## 3. 哪些是“需要开发的模块”

真正需要开发的代码模块分为 8 类：

1. Go 生成器 CLI
2. Go 生成器内部模块
3. Python 数据契约模块
4. Python 自动标注模块
5. Python 数据转换模块
6. Python 训练模块
7. Python 推理后处理模块
8. Python 评估与报告模块

其中：

- 必须先做：1 到 5
- 可以后续迭代：6 到 8

## 4. Go 主线目录

```text
generator/
  go.mod
  go.sum
  cmd/
    sinan-click-generator/
      main.go
  internal/
    config/
    material/
    sampler/
    layout/
    render/
    export/
    qa/
  configs/
    default.yaml
    smoke.yaml
  build/
    windows-amd64/
    linux-amd64/
```

### 4.1 `generator/cmd/sinan-click-generator`

- 语言：Go
- 模块职责：
  - 提供生成器总 CLI
  - 暴露 `validate-materials`、`generate`、`qa`
- 编译方式：
  - `go build -o ../../dist/generator/windows-amd64/sinan-click-generator.exe ./cmd/sinan-click-generator`
- 打包产物：
  - Windows 下是单独 `.exe`
  - Linux 下是单独 ELF 二进制
- 部署方式：
  - 首版直接复制二进制到训练机
  - 可与 `configs/`、`materials/` 配套打成 zip 包

### 4.2 `generator/internal/config`

- 语言：Go
- 模块职责：
  - 读取 YAML 配置
  - 校验样本数、画布尺寸、风格参数
- 编译方式：
  - 跟随生成器主程序一起编译
- 打包产物：
  - 无独立产物
- 部署方式：
  - 作为生成器内部代码随主程序部署

### 4.3 `generator/internal/material`

- 语言：Go
- 模块职责：
  - 加载背景图、图标图、类别表
  - 提供素材索引
- 编译方式：
  - 随主程序编译
- 打包产物：
  - 无独立产物
- 部署方式：
  - 随主程序部署
  - 运行时依赖 `materials/`

### 4.4 `generator/internal/sampler`

- 语言：Go
- 模块职责：
  - 抽样目标类别和干扰项类别
  - 管理随机种子复现
- 编译方式：
  - 随主程序编译
- 打包产物：
  - 无独立产物
- 部署方式：
  - 随主程序部署

### 4.5 `generator/internal/layout`

- 语言：Go
- 模块职责：
  - 生成对象位置、缩放、旋转、透明度
  - 处理碰撞和越界重试
- 编译方式：
  - 随主程序编译
- 打包产物：
  - 无独立产物
- 部署方式：
  - 随主程序部署

### 4.6 `generator/internal/render`

- 语言：Go
- 模块职责：
  - 渲染查询图
  - 渲染场景图
- 编译方式：
  - 随主程序编译
- 打包产物：
  - 无独立产物
- 部署方式：
  - 随主程序部署

### 4.7 `generator/internal/export`

- 语言：Go
- 模块职责：
  - 导出 `query/`、`scene/`、`labels.jsonl`、`manifest.json`
- 编译方式：
  - 随主程序编译
- 打包产物：
  - 无独立产物
- 部署方式：
  - 随主程序部署

### 4.8 `generator/internal/qa`

- 语言：Go
- 模块职责：
  - 生成 contact sheet
  - 批次级质量检查
- 编译方式：
  - 随主程序编译
- 打包产物：
  - 无独立产物
- 部署方式：
  - 随主程序部署

## 5. Python 主线目录

```text
src/sinan_captcha/
  __init__.py
  common/
  dataset/
  autolabel/
  convert/
  train/
    group1/
    group2/
  inference/
  evaluate/
```

## 5.1 `src/sinan_captcha/common`

- 语言：Python
- 模块职责：
  - 公共路径工具
  - 日志工具
  - JSONL 读写工具
  - 配置加载工具
- 构建方式：
  - 通过 `uv build` 打包进 Python wheel
- 打包产物：
  - wheel / sdist
- 部署方式：
  - 跟随 Python 项目整体通过 `uv sync` 或 `uv pip install dist/*.whl` 部署

## 5.2 `src/sinan_captcha/dataset`

- 语言：Python
- 模块职责：
  - JSONL schema 校验
  - 类别表加载
  - 数据版本元信息
- 构建方式：
  - 打包进 Python wheel
- 打包产物：
  - wheel 内部模块
- 部署方式：
  - 随 Python 包部署

## 5.3 `src/sinan_captcha/autolabel`

- 语言：Python
- 模块职责：
  - 第二专项规则法预标注
  - 第一专项暖启动模型预标注
- 构建方式：
  - 打包进 Python wheel
- 打包产物：
  - wheel 内部模块
- 部署方式：
  - 随 Python 包部署
  - 运行时依赖 `datasets/`、模型权重和 OpenCV

## 5.4 `src/sinan_captcha/convert`

- 语言：Python
- 模块职责：
  - JSONL 转 YOLO 数据集
  - 生成 `dataset.yaml`
- 构建方式：
  - 打包进 Python wheel
- 打包产物：
  - wheel 内部模块
- 部署方式：
  - 随 Python 包部署

## 5.5 `src/sinan_captcha/train/group1`

- 语言：Python
- 模块职责：
  - 第一专项训练参数组织
  - 训练前校验
  - 训练摘要归档
- 构建方式：
  - 打包进 Python wheel
- 打包产物：
  - wheel 内部模块
- 部署方式：
  - 随 Python 包部署
  - 运行时调用 `uv run yolo`

## 5.6 `src/sinan_captcha/train/group2`

- 语言：Python
- 模块职责：
  - 第二专项训练参数组织
  - 训练前校验
  - 训练摘要归档
- 构建方式：
  - 打包进 Python wheel
- 打包产物：
  - wheel 内部模块
- 部署方式：
  - 随 Python 包部署

## 5.7 `src/sinan_captcha/inference`

- 语言：Python
- 模块职责：
  - 第一专项顺序映射
  - 第二专项中心点换算
- 构建方式：
  - 打包进 Python wheel
- 打包产物：
  - wheel 内部模块
- 部署方式：
  - 随 Python 包部署

## 5.8 `src/sinan_captcha/evaluate`

- 语言：Python
- 模块职责：
  - 计算指标
  - 导出失败样本
  - 生成模型报告
- 构建方式：
  - 打包进 Python wheel
- 打包产物：
  - wheel 内部模块
- 部署方式：
  - 随 Python 包部署

## 6. 脚本入口目录

```text
scripts/
  export/
  autolabel/
  convert/
  train/
  evaluate/
  ops/
```

这些目录是“薄入口”，不承载核心业务逻辑。

### 6.1 `scripts/export`

- 语言：Python / PowerShell
- 模块职责：
  - 调用 Go 生成器
  - 组织批次导出命令
- 编译方式：
  - 无编译
- 打包产物：
  - 不单独打包
- 部署方式：
  - 跟仓库一起部署

### 6.2 `scripts/autolabel`

- 语言：Python
- 模块职责：
  - 运行预标注任务
- 编译方式：
  - 无编译
- 打包产物：
  - 不单独打包
- 部署方式：
  - 跟仓库一起部署

### 6.3 `scripts/convert`

- 语言：Python
- 模块职责：
  - 运行 JSONL 转 YOLO 命令
- 编译方式：
  - 无编译
- 打包产物：
  - 不单独打包
- 部署方式：
  - 跟仓库一起部署

### 6.4 `scripts/train`

- 语言：PowerShell + Python
- 模块职责：
  - 固定训练命令
  - 固定输出目录
- 编译方式：
  - 无编译
- 打包产物：
  - 不单独打包
- 部署方式：
  - 跟仓库一起部署

### 6.5 `scripts/evaluate`

- 语言：Python
- 模块职责：
  - 运行评估命令
  - 导出评估报告
- 编译方式：
  - 无编译
- 打包产物：
  - 不单独打包
- 部署方式：
  - 跟仓库一起部署

### 6.6 `scripts/ops`

- 语言：PowerShell
- 模块职责：
  - Windows 环境自检
  - 一键执行常用流程
- 编译方式：
  - 无编译
- 打包产物：
  - 不单独打包
- 部署方式：
  - 跟仓库一起部署

## 7. 测试目录

推荐目录：

```text
tests/
  python/
    dataset/
    autolabel/
    convert/
    train/
    evaluate/
  go/
    generator/
```

### 7.1 `tests/python`

- 语言：Python
- 构建方式：
  - 无编译
- 运行方式：
  - `uv run pytest`
- 部署方式：
  - 不部署到生产，仅开发和验收使用

### 7.2 `tests/go`

- 语言：Go
- 构建方式：
  - 无独立编译
- 运行方式：
  - `go test ./...`
- 部署方式：
  - 不部署到生产，仅开发和验收使用

## 8. 配置和资产目录

这些目录不是代码模块，但必须在设计里明确。

### 8.1 `configs/`

- 内容：
  - Python 侧任务配置
  - 训练参数配置
  - 路径配置
- 语言：
  - YAML
- 编译方式：
  - 无
- 打包方式：
  - 跟仓库一同交付
- 部署方式：
  - 作为运行配置文件放在训练机

### 8.2 `materials/`

- 内容：
  - 背景图
  - 图标图
  - `classes.yaml`
- 语言：
  - 图片 + YAML
- 编译方式：
  - 无
- 打包方式：
  - 单独素材包，不打进 wheel，不打进 Go 二进制
- 部署方式：
  - 复制到训练机本地目录

### 8.3 `datasets/`

- 内容：
  - `raw/`
  - `interim/`
  - `reviewed/`
  - `yolo/`
- 语言：
  - 图片 + JSONL + TXT + YAML
- 编译方式：
  - 无
- 打包方式：
  - 作为数据资产独立管理
- 部署方式：
  - 不进代码包，不进二进制，只存在运行环境

### 8.4 `reports/`

- 内容：
  - QA 报告
  - 评估报告
  - 失败样本清单
- 语言：
  - Markdown / JSON / CSV / 图片
- 编译方式：
  - 无
- 打包方式：
  - 独立报告包
- 部署方式：
  - 存在训练机和归档目录

## 9. 构建与打包策略

## 9.1 Go 生成器

- 开发期运行：
  - `go run ./cmd/sinan-click-generator --help`
- 正式编译：
  - `go build -o ../dist/generator/windows-amd64/sinan-click-generator.exe ./cmd/sinan-click-generator`
- 打包方式：
  - `sinan-click-generator.exe`
  - `configs/*.yaml`
  - `materials/`
  - 可选说明文档
- 交付形态：
  - zip 包

## 9.2 Python 训练链路

- 开发期运行：
  - `uv sync`
  - `uv run pytest`
- 正式打包：
  - `uv build`
- 打包产物：
  - `dist/*.whl`
  - `dist/*.tar.gz`
- 交付形态：
  - wheel 包 + 仓库脚本 + 配置文件

## 9.3 为什么不把所有东西打成一个包

- Go 二进制和 Python 运行时天然不同
- 素材和数据体积大，不适合进入代码包
- 训练过程本来就依赖本地目录、权重和数据集

结论：

- 应采用“多交付物”模式，而不是追求一个总安装包

## 10. 部署方式

## 10.1 本地训练机部署

首版唯一必须支持的部署方式：

- Windows 训练机本地部署

部署内容：

1. 部署 Python 环境
2. 部署 Go 生成器二进制
3. 部署素材目录
4. 部署配置目录
5. 准备 `datasets/`、`reports/` 运行目录

## 10.2 可选的内部 Linux 部署

不是首版必须，但可以预留：

- Go 生成器可交叉编译到 Linux
- Python 链路可在 Linux GPU 服务器部署

这部分不作为当前强制交付。

## 10.3 暂不支持的部署方式

- 不做公网验证码服务部署
- 不做 Kubernetes 部署
- 不做多节点训练集群部署
- 不做桌面安装包

## 11. 子模块与交付物对照表

| 子模块 | 语言 | 是否编译 | 打包产物 | 部署位置 |
|---|---|---|---|---|
| `generator/cmd/sinan-click-generator` | Go | 是 | `.exe` / Linux binary | 训练机本地 |
| `generator/internal/*` | Go | 跟随主程序 | 无独立产物 | 随生成器部署 |
| `src/sinan_captcha/common` | Python | 否 | wheel 内部模块 | Python 环境 |
| `src/sinan_captcha/dataset` | Python | 否 | wheel 内部模块 | Python 环境 |
| `src/sinan_captcha/autolabel` | Python | 否 | wheel 内部模块 | Python 环境 |
| `src/sinan_captcha/convert` | Python | 否 | wheel 内部模块 | Python 环境 |
| `src/sinan_captcha/train/group1` | Python | 否 | wheel 内部模块 | Python 环境 |
| `src/sinan_captcha/train/group2` | Python | 否 | wheel 内部模块 | Python 环境 |
| `src/sinan_captcha/inference` | Python | 否 | wheel 内部模块 | Python 环境 |
| `src/sinan_captcha/evaluate` | Python | 否 | wheel 内部模块 | Python 环境 |
| `scripts/*` | Python / PowerShell | 否 | 仓内脚本 | 跟仓库部署 |
| `materials/*` | 图片 / YAML | 否 | 素材包 | 训练机本地 |
| `datasets/*` | 图片 / JSONL / YAML | 否 | 数据目录 | 训练机本地 |
| `reports/*` | Markdown / JSON / CSV | 否 | 报告目录 | 训练机本地/归档目录 |

## 12. 推荐的实现先后顺序

目录和模块实现顺序建议如下：

1. `generator/`
2. `materials/`
3. `src/sinan_captcha/dataset`
4. `src/sinan_captcha/convert`
5. `scripts/export`
6. `scripts/convert`
7. `src/sinan_captcha/autolabel`
8. `src/sinan_captcha/train/group2`
9. `src/sinan_captcha/train/group1`
10. `src/sinan_captcha/inference`
11. `src/sinan_captcha/evaluate`

不要先做：

- HTTP 服务层
- 对外部署层
- 多平台 GUI

## 13. 最终结论

从开发视角看，这个项目最合理的仓库结构是：

- 一套 Go 生成器工程
- 一套 Python 训练工程
- 一套脚本入口层
- 三类非代码资产目录：素材、数据、报告

从交付视角看，这个项目最合理的交付形态是：

- Go 二进制包
- Python wheel 包
- 配置包
- 素材包
- 数据目录和报告目录

不要把它设计成“一个程序包打天下”。对训练型项目，这种设计反而最不稳。
