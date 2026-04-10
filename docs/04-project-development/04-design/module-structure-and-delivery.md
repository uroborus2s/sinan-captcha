# 模块结构与构建交付设计

- 文档状态：已重构
- 当前阶段：IMPLEMENTATION（设计基线维护）
- 目标读者：架构/开发、项目维护者、训练实施者、交付维护者
- 负责人：Codex

## 1. 设计结论

当前项目应长期保持三类正式产品面：

1. Go 生成器可执行文件
2. Python 训练 / 自动化 / 发布包
3. 独立 Python + Rust solver 包

从“正式入口”的视角看：

- 当前稳定 CLI 入口仍然只有两个：
  - `sinan-generator`
  - `sinan`
- 但从最终交付视角看，最终业务调用方不应继续面对训练仓库里的 `solve` 子命令或外置 bundle。
- 最终业务调用方应面对：
  - `pip install sinanz`
  - `sn_match_slider(...)` / `sn_match_targets(...)`
  - 默认内嵌 ONNX 推理资产
  - wheel 内随包交付的 Rust 原生扩展

设计约束：

- Go 负责素材、工作区、样本生成和 QA
- 训练仓库里的 Python 负责训练、评估、自主训练、release 和 `PT -> ONNX` 推理资产导出
- 独立 solver 项目负责公共 API、内嵌模型加载和 Rust 扩展桥接
- 训练仓库导出的推理资产不得继续依赖训练目录
- 如需批处理脚本，也只能调用正式 CLI，不能承载核心业务逻辑

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
  solver/
  script/
  tests/
  configs/
  materials/
  datasets/
  reports/
  bundles/
  dist/
```

说明：

- `generator/`：Go 生成器工程
- `core/`：Python 训练、评估、发布、自主训练与迁移期 solver 参考实现
- `solver/`：独立 solver Python 项目过渡目录，后续可抽离为单独仓库
- `solver/native/`：独立 solver 的 Rust 原生扩展工程
- `script/`：开发期辅助脚本目录，不属于正式运行时模块
- `tests/`：Go 和 Python 测试
- `configs/`：运行配置
- `materials/`：素材或素材包构建结果
- `datasets/`：运行时数据目录
- `reports/`：评估与 QA 报告
- `bundles/`：训练仓库导出的推理资产或迁移期 bundle
- `dist/`：构建产物目录

## 3. 正式代码模块

真正需要长期维护的代码模块分为 14 类：

1. Go 生成器 CLI
2. Go 生成器内部模块
3. Python 总 CLI
4. Python 数据契约模块
5. Python 素材包构建模块
6. Python 自动标注与数据转换模块
7. Python `group1` 训练模块
8. Python `group2` 训练模块
9. Python 推理后处理与评估模块
10. Python 自主训练模块
11. 训练仓库内的 solver 迁移参考模块
12. 独立 solver Python 包
13. 独立 solver Rust 扩展
14. Python release 与交付模块

优先级解释：

- 当前已较完整：1 到 10
- 当前已存在骨架但需重构边界：11、13
- 当前待新增并最终成为正式交付主线：12、13

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
```

### 4.1 `generator/cmd/sinan-generator`

- 职责：
  - 生成器总 CLI
  - `workspace init|show`
  - `materials import|fetch`
  - `make-dataset`
- 构建：
  - `go build -o ../dist/generator/windows-amd64/sinan-generator.exe ./cmd/sinan-generator`
- 交付：
  - Windows 下单独 `.exe`
  - Linux 下单独二进制

### 4.2 `generator/internal/*`

- `material`：素材骨架与完整解码校验
- `backend`：`native` 与未来 adapter 接口
- `export`：图片、标签、batch 元数据导出
- `qa`：一致性校验、重放校验、负样本校验
- `config / sampler / layout / render / truth`：生成器内部基础能力

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
  solve/
  auto_train/
  train/
    group1/
    group2/
  inference/
  evaluate/
```

### 5.1 `core/cli.py`

- 职责：
  - Python 侧总入口
  - 统一分发 env / materials / dataset / autolabel / auto-train / evaluate / predict / test / train / release
- 设计边界：
  - 不承担最终 solver 公开入口
  - 训练仓库里的 `solve` 只保留迁移期调试和资产验收价值

### 5.2 `core/dataset`

- 职责：
  - JSONL schema 校验
  - 数据集元信息
  - 类别表加载

### 5.3 `core/materials`

- 职责：
  - 构建离线 `materials/` 包
  - 生成 `materials.yaml`、`group1.classes.yaml`、`group2.shapes.yaml`
  - 生成 `backgrounds.csv`、`group1.icons.csv`、`group2.shapes.csv`

### 5.4 `core/autolabel` 与 `core/convert`

- 职责：
  - 预标注
  - 审核结果转训练数据
  - 输出 `group1` pipeline dataset 和 `group2` paired dataset

### 5.5 `core/train/group1`

- 职责：
  - `group1` 双模型训练
  - 训练参数组织、校验与摘要

### 5.6 `core/train/group2`

- 职责：
  - `group2` paired-input 训练
  - 检查点、超参数和训练摘要

### 5.7 `core/inference` 与 `core/evaluate`

- `core/inference`：
  - 推理结果到业务语义的映射
- `core/evaluate`：
  - 任务级指标、失败样本和报告

### 5.8 `core/auto_train`

- 职责：
  - study / trial 账本
  - 生成 / 训练 / 测试 / 评估编排
  - `opencode` runtime 接入
  - fallback 和策略控制

### 5.9 `core/solve`

- 职责：
  - 迁移期参考实现
  - 推理资产合同验证
  - `group1/group2` 运行时抽离前的代码来源
  - 内部调试 CLI
- 当前状态：
  - 代码已存在
  - 不应继续被定义为最终公开产品边界

### 5.10 `solver/`

- 目标目录：

```text
solver/
  pyproject.toml
  resources/
    models/
    metadata/
  src/
    sinanz.py
    sinanz_errors.py
    sinanz_types.py
    sinanz_image_io.py
    sinanz_group2_runtime.py
    sinanz_group2_service.py
    sinanz_resources.py
  tests/
```

- 职责：
  - 独立 PyPI 包
  - `sn_match_slider` / `sn_match_targets` 公开 API
  - 默认内嵌 ONNX 推理资产加载
  - Python 预处理、资源加载、ONNX Runtime 调用与异常映射
- 迁移策略：
  - 第一阶段允许作为当前仓库内的独立 Python 子项目存在
  - 第二阶段可整体抽离为独立仓库，不改变包名和函数名

### 5.11 `core/release`

- 职责：
  - 本地构建 wheel / sdist
  - 本地上传 PyPI / TestPyPI
  - 组装 Windows 训练交付包
  - 导出 solver 推理资产
- 当前状态：
  - 当前主要服务训练仓库自身发布
  - 后续需要新增“导出推理专用资产”的正式入口

## 6. 资产目录

### 6.1 `materials/`

- 内容：
  - 背景图
  - `group1` 点选图标池
  - `group2` 缺口形状池
  - `materials.yaml`
  - `group1.classes.yaml`
  - `group2.shapes.yaml`
  - `backgrounds.csv`
  - `group1.icons.csv`
  - `group2.shapes.csv`
- 规则：
  - 不打进 wheel
  - 不打进 Go 二进制
  - 作为独立运行资产管理

### 6.2 `datasets/`

- 内容：
  - 原始样本
  - `gold / auto / reviewed`
  - `group1` pipeline dataset
  - `group2` paired dataset

### 6.3 `reports/`

- 内容：
  - QA 报告
  - 评估报告
  - 失败样本清单

### 6.4 `bundles/`

- 内容：
  - `solver/<bundle-name>/manifest.json`
  - `solver/<bundle-name>/models/group1/...`
  - `solver/<bundle-name>/models/group2/...`
- 规则：
  - 作为训练仓库到独立 solver 项目的内部交接物
  - 只依赖相对路径
  - 不允许直接引用 `runs/` 的绝对路径

## 7. 构建与交付策略

### 7.1 Go 生成器

- 开发期运行：
  - `go run ./cmd/sinan-generator --help`
- 正式编译：
  - `go build -o ../dist/generator/windows-amd64/sinan-generator.exe ./cmd/sinan-generator`
- 交付形态：
  - `sinan-generator.exe`
  - 可选素材包

### 7.2 Python 包

- 开发期运行：
  - `uv sync`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
- 正式打包：
  - `uv build`
- 交付形态：
  - `dist/*.whl`
  - `dist/*.tar.gz`

### 7.3 内部 solver 资产包

- 设计目标入口：
  - `uv run sinan release export-solver-assets --project-dir . --group2-checkpoint runs/group2/<train-name>/weights/best.pt --group2-run <train-name> --output-dir dist/solver-assets/<version> --asset-version <version>`
- 交接形态：
  - `bundles/solver/<bundle-name>/`
  - 或 `dist/solver-assets/<version>/`
- 说明：
  - 这批资产用于喂给独立 solver 项目构建 wheel
  - 不再视为最终调用方主安装面
  - `TASK-SOLVER-MIG-008` 当前先导出 `group2`；`group1` ONNX 资产会在 `TASK-SOLVER-MIG-009` 补齐

### 7.4 Windows 交付包

- 目标内容：
  - `python/`
  - `generator/`
  - `README-交付包说明.txt`
- 目标角色：
  - 训练机操作者
  - 发布维护者
- 说明：
  - 它继续服务训练与维护，不代表最终 solver 安装方式

### 7.5 独立 solver 包

- 目标目录：
  - `solver/`
- 正式打包：
  - `cd solver && uv build`
- 正式交付形态：
  - `sinanz-<version>-cp312-<platform>.whl`
- 安装形态：
  - `pip install sinanz`
- 运行形态：
  - 直接导入函数
  - 默认加载包内 ONNX 推理资产
  - 通过 Rust 原生扩展执行最终推理路径

## 8. 子模块与交付物对照表

| 子模块 | 语言 | 打包产物 | 部署位置 |
|---|---|---|---|
| `generator/cmd/sinan-generator` | Go | `.exe` / 二进制 | 训练机本地 |
| `core/cli.py` | Python | wheel console script | Python 环境 |
| `core/train/*` | Python | wheel 内部模块 | Python 环境 |
| `core/auto_train/*` | Python | wheel 内部模块 | Python 环境 |
| `core/solve/*` | Python | 迁移参考实现 / 内部调试能力 | 训练仓库内部 |
| `solver/src/sinanz/*` | Python | 独立 solver wheel（含内嵌推理资产） | 调用方 Python 环境 |
| `core/release/*` | Python | wheel 内部模块 | Python 环境 |
| `materials/*` | 图片 / YAML | 素材包 | 训练机本地 |
| `datasets/*` | 图片 / JSONL | 数据目录 | 训练机本地 |
| `bundles/solver/*` | PT / JSON | 推理资产交接目录 | 训练仓库 / 构建流程 |
| `reports/*` | Markdown / JSON / CSV | 报告目录 | 训练机本地 / 归档目录 |

## 9. 推荐实现顺序

1. `generator/`
2. `core/dataset`
3. `core/train/group2`
4. `core/train/group1`
5. `core/inference`
6. `core/evaluate`
7. `core/auto_train`
8. 训练仓库导出推理资产
9. `solver/` 独立项目
10. `core/solve` 运行时抽离 / 内部调试降级
11. solver 发布链路与 PyPI 收口

不要先做：

- HTTP 服务层
- 公网部署层
- 多平台 GUI

## 10. 最终结论

从结构上看，这个项目最合理的长期形态是：

- 一套 Go 生成器工程
- 一套 Python 训练与自动化工程
- 一套独立 Python solver 项目
- 四类非代码资产目录：素材、数据、报告、推理资产交接目录

从交付上看，最合理的正式产物是：

- Go 二进制
- 训练仓库 Python wheel
- 独立 solver PyPI wheel
- Windows 训练交付包

不要再回到“训练仓库同时冒充最终 solver SDK”的结构。那种结构会继续把公开 API、发布形态和训练内部实现绑死在一起。
