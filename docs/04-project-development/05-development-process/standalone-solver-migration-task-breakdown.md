# 独立 solver 迁移任务拆解

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：项目维护者、Python 实现者、Rust 实现者、发布维护者
- 负责人：Codex
- 上游输入：
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
- 下游交付：
  - `solver/` 独立 Python 项目
  - `solver/native/sinanz_ext/` Rust 原生扩展工程
  - 训练仓库推理资产导出链路
  - PyPI 平台 wheel 发布与安装冒烟验证
- 关联需求：`REQ-001`、`REQ-004`、`REQ-008`、`REQ-010`、`NFR-004`、`NFR-007`

## 1. 使用方式

这份文档不是讨论“以后可以怎么做”，而是把独立 solver 迁移拆成可执行顺序。

执行原则：

1. 严格按 `TASK-SOLVER-MIG-001` 到 `TASK-SOLVER-MIG-012` 推进。
2. 每个任务都要冻结边界、产出代码或文档、补回归验证。
3. 前一任务未通过验收，后一任务不得启动。
4. 训练仓库与 solver 包的职责一旦冻结，不允许在实现中临时回退到“直接复用旧 CLI 就行”。

## 2. 目标边界

迁移完成后，项目应稳定分成三层：

1. 训练仓库：
   - `sinan-generator`
   - `sinan train/test/evaluate/auto-train/release`
   - `PT -> ONNX` 推理资产导出
2. 独立 solver 项目：
   - `sinanz`
   - `pip install`
   - `sn_match_slider(...)`
   - `sn_match_targets(...)`
   - Python API + Rust 原生扩展
3. 内部交接资产：
   - ONNX 模型
   - 类别表 / matcher 配置
   - 导出 manifest

面向最终调用方的目标使用方式固定为：

```python
from sinanz import sn_match_slider, sn_match_targets
```

调用方默认不再接触：

- `bundle_dir`
- `request.json`
- 训练运行目录
- 模型文件路径

## 3. 总执行表

| 任务 ID | 任务名称 | 主执行角色 | 主要输入 | 主要输出 | 阶段关口 | 预计工时 |
|---|---|---|---|---|---|---|
| TASK-SOLVER-MIG-001 | 冻结边界与弃用策略 | 项目维护者 | 最新业务澄清、现有 `core/solve` | 边界表、弃用表 | 边界冻结 | 0.5 天 |
| TASK-SOLVER-MIG-002 | 冻结独立 solver API 与异常合同 | 架构负责人 | 业务语义、边界表 | API 字段表、示例代码、异常表 | API 冻结 | 0.5 天 |
| TASK-SOLVER-MIG-003 | 冻结推理资产导出合同 | 训练链路负责人 | 现有训练产物、API 合同 | 导出目录规范、manifest 字段表 | 资产合同冻结 | 0.5 天 |
| TASK-SOLVER-MIG-004 | 建立独立 solver 子项目骨架 | Python 实现者 | API 合同、资产合同 | `solver/` 工程骨架 | 子项目可构建 | 0.5 天 |
| TASK-SOLVER-MIG-005 | 抽离共享运行时与 `group2` 过渡代码 | Python 实现者 | `core/solve`、`core/train/group2` | 独立加载层、group2 过渡 runtime | 训练依赖切断 | 1 天 |
| TASK-SOLVER-MIG-006 | 冻结 `PT -> ONNX` 导出与命名合同 | 架构负责人 | 训练产物、独立 solver 需求 | ONNX 命名、metadata、导出规则 | ONNX 合同冻结 | 0.5 天 |
| TASK-SOLVER-MIG-007 | 建立 Rust 原生扩展工程与构建边界 | Rust 实现者 | ONNX 合同、子项目骨架 | `sinanz_ext` 工程、Cargo workspace | 原生工程可构建 | 0.5 天 |
| TASK-SOLVER-MIG-008 | 实现 `group2` ONNX 导出与 Rust runtime bridge | Rust 实现者 | `group2` 训练产物、Rust 工程 | `group2` ONNX runtime、桥接接口 | `group2` Rust 化 | 1 天 |
| TASK-SOLVER-MIG-009 | 实现 `group1` ONNX 导出与 Rust runtime bridge | Rust 实现者 | `group1` 训练产物、matcher 约束 | `group1` ONNX runtime、桥接接口 | 两专项都可运行 | 1 天 |
| TASK-SOLVER-MIG-010 | 迁移 `group1` 求解与后处理代码 | Python 实现者 | `core/solve/*`、`core/inference/*` | group1 service、matcher 接口、结果映射 | Python 结果面稳定 | 1 天 |
| TASK-SOLVER-MIG-011 | 实现内嵌资产加载与默认模型解析 | Python 实现者 | 子项目骨架、导出资产、Rust bridge | 资源加载器、wheel 资源规则 | `pip install` 后可直接加载 | 1 天 |
| TASK-SOLVER-MIG-012 | 补齐测试、发布链路并降级旧入口 | 测试负责人/发布维护者 | 独立 solver 项目、导出资产 | 安装测试、发布脚本、弃用说明 | 允许正式迁移 | 1 天 |

## 4. TASK-SOLVER-MIG-001 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定训练仓库、独立 solver 包和内部交接资产的边界，停止继续把 `core/solve` 当最终产品面 |
| 主执行角色 | 项目维护者 |
| 协作角色 | 架构负责人、发布维护者 |
| 前置条件 | 无 |
| 主要输入 | 最新业务澄清、`core/solve` 当前实现、现有发布文档 |
| 操作步骤 | 1. 固定“训练仓库负责什么、独立 solver 包负责什么、内部资产交接负责什么”。<br>2. 固定 `sinan solve` 的新定位：迁移期调试能力，不再作为最终用户主入口。<br>3. 固定 bundle 的新定位：内部交接资产，不再作为最终安装界面。 |
| 输出产物 | 边界表、弃用表、当前差距说明 |
| 验收标准 | 任何维护者都能明确回答“最终用户为什么不再直接使用 `sinan solve`” |
| 阻断条件 | 仍把训练 CLI、bundle 和 solver 公开 API 混在一起 |
| 失败处理 | 回到设计文档重定边界，不进入 API 冻结 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-SOLVER-MIG-002 |

## 5. TASK-SOLVER-MIG-002 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 冻结独立 solver 的公开函数名、参数名、返回对象和异常语义 |
| 主执行角色 | 架构负责人 |
| 协作角色 | Python 实现者、项目维护者 |
| 前置条件 | TASK-SOLVER-MIG-001 已通过 |
| 主要输入 | 业务定义、边界表 |
| 操作步骤 | 1. 固定顶层函数：`sn_match_slider`、`sn_match_targets`。<br>2. 固定面向对象入口 `CaptchaSolver` 是否保留及其构造参数。<br>3. 固定结果对象与异常对象，不允许继续沿用 `request/response` 包装层。 |
| 输出产物 | API 字段表、示例调用、异常表 |
| 验收标准 | 调用者只看函数名和参数名就能理解业务含义；不再需要知道 `group1/group2` 内部编排 |
| 阻断条件 | 仍存在 `bundle_dir`、`request.json`、`task_hint` 之类旧公开参数 |
| 失败处理 | 回补 API 设计，不进入资产合同 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-SOLVER-MIG-003 |

## 6. TASK-SOLVER-MIG-003 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 固定训练仓库导出给独立 solver 项目的推理专用资产合同 |
| 主执行角色 | 训练链路负责人 |
| 协作角色 | 发布维护者、Python 实现者 |
| 前置条件 | TASK-SOLVER-MIG-002 已通过 |
| 主要输入 | 现有训练权重、发布文档、API 合同 |
| 操作步骤 | 1. 固定导出目录结构、文件命名和 manifest 字段。<br>2. 明确哪些训练态字段必须剥离，例如 `optimizer_state`、绝对路径、运行目录。<br>3. 固定 solver 项目构建时如何消费这批资产。 |
| 输出产物 | 导出目录规范、manifest 字段表、导出报告字段表 |
| 验收标准 | 维护者不看训练目录，也能仅凭导出资产完成 solver 包构建 |
| 阻断条件 | 导出物仍直接引用 `runs/`、`datasets/` 或训练配置路径 |
| 失败处理 | 回补导出合同，不进入子项目搭建 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-SOLVER-MIG-004 |

## 7. TASK-SOLVER-MIG-004 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 在当前仓库内建立过渡期独立 solver 子项目，为后续拆仓或独立发布做准备 |
| 主执行角色 | Python 实现者 |
| 协作角色 | 发布维护者 |
| 前置条件 | TASK-SOLVER-MIG-003 已通过 |
| 主要输入 | API 合同、资产合同 |
| 操作步骤 | 1. 新建 `solver/pyproject.toml`、`src/sinanz/`、`tests/`。<br>2. 固定独立依赖、包资源规则和测试入口。<br>3. 保证 `uv build` 可以独立执行，不依赖训练仓库根 `pyproject.toml`。 |
| 输出产物 | 子项目骨架、最小导入测试、最小构建测试 |
| 验收标准 | `solver/` 可作为独立 Python 项目单独构建 |
| 阻断条件 | 子项目仍隐式依赖训练仓库根环境或根入口脚本 |
| 失败处理 | 回补工程边界，不进入运行时代码迁移 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-SOLVER-MIG-005 |

## 8. TASK-SOLVER-MIG-005 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 抽离共享运行时基础设施，并优先切断 `group2` 对训练私有实现的依赖，为后续 ONNX 化准备干净边界 |
| 主执行角色 | Python 实现者 |
| 协作角色 | 架构负责人 |
| 前置条件 | TASK-SOLVER-MIG-004 已通过 |
| 主要输入 | `core/solve/service.py`、`core/train/group2/*` |
| 操作步骤 | 1. 抽出图片读取、异常类型、设备解析、模型加载公共层。<br>2. 抽出 `group2` 纯推理 runtime，不再依赖训练 runner 私有函数。<br>3. 补齐 `group2` 独立单测。 |
| 输出产物 | 共享基础设施、group2 过渡 runtime、回归测试 |
| 验收标准 | `group2` 能在独立 solver 子项目中运行，且不 import 训练内部 runner |
| 阻断条件 | 仍通过 `core.train.group2.runner` 调推理 |
| 失败处理 | 先补共享运行时抽离，不进入 ONNX 合同冻结 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-SOLVER-MIG-006 |

## 9. TASK-SOLVER-MIG-006 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 冻结 `PT -> ONNX` 导出、命名和 metadata 合同，为 Rust 运行时接线提供稳定资产面 |
| 主执行角色 | 架构负责人 |
| 协作角色 | 训练链路负责人、Rust 实现者 |
| 前置条件 | TASK-SOLVER-MIG-005 已通过 |
| 主要输入 | 训练权重、当前导出合同、独立 solver 资产需求 |
| 操作步骤 | 1. 固定 `.onnx` 文件名和版本字段。<br>2. 固定输入尺寸、预处理参数、provider 兼容信息写入 metadata。<br>3. 固定 `manifest.json` 中 Python 包与 Rust 扩展共同消费的字段。 |
| 输出产物 | ONNX 命名规则、manifest 字段表、导出报告字段、仓内代码契约事实源 |
| 验收标准 | 维护者可以稳定回答“Rust 扩展到底读哪些文件和字段”，且仓库里已有可测试的字段事实源 |
| 阻断条件 | 资产命名仍跟训练运行目录耦合，或字段不足以独立构建 runtime |
| 失败处理 | 回补导出合同，不进入 Rust 工程搭建 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-SOLVER-MIG-007 |

## 10. TASK-SOLVER-MIG-007 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 在 solver 子项目内建立 Rust 原生扩展工程和 Cargo workspace，固定未来 `pyo3 + ort` 集成边界 |
| 主执行角色 | Rust 实现者 |
| 协作角色 | Python 实现者、发布维护者 |
| 前置条件 | TASK-SOLVER-MIG-006 已通过 |
| 主要输入 | ONNX 合同、独立 solver 子项目 |
| 操作步骤 | 1. 新建 `solver/Cargo.toml` workspace。<br>2. 新建 `solver/native/sinanz_ext/Cargo.toml` 和 `src/lib.rs`。<br>3. 固定 crate 类型、扩展入口、未来 `pyo3 + ort` 的接入位置和构建说明。 |
| 输出产物 | Rust 工程骨架、Cargo workspace、原生扩展说明 |
| 验收标准 | Rust 子项目可以独立被 Cargo 识别，且目录边界清晰可维护 |
| 阻断条件 | Rust 工程仍散落在 Python 包根目录，或未来 `pyo3` / wheel 构建位置不清晰 |
| 失败处理 | 回补工程骨架，不进入 ONNX runtime 实现 |
| 预计工时 | 0.5 天 |
| 完成后进入 | TASK-SOLVER-MIG-008 |

## 11. TASK-SOLVER-MIG-008 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 完成 `group2` ONNX 导出与 Rust runtime bridge，使滑块链路摆脱 PyTorch 运行时 |
| 主执行角色 | Rust 实现者 |
| 协作角色 | 训练链路负责人、Python 实现者 |
| 前置条件 | TASK-SOLVER-MIG-007 已通过 |
| 主要输入 | `group2` 训练产物、ONNX 合同、Rust 工程 |
| 操作步骤 | 1. 实现 `group2` 的 ONNX 导出脚本或发布步骤。<br>2. 在 Rust 扩展中建立 `group2` ONNX Runtime 会话和推理入口。<br>3. 固定 Python 到 Rust 的最小桥接签名。 |
| 输出产物 | `group2` ONNX 导出、Rust runtime、桥接测试 |
| 验收标准 | `group2` 求解不再依赖 PyTorch 运行时，且能通过 Rust 扩展返回业务结果 |
| 阻断条件 | `group2` 仍需要 `torch.load` 或训练侧 Python runtime 才能工作 |
| 失败处理 | 回补 `group2` ONNX 路线，不进入 `group1` ONNX 迁移 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-SOLVER-MIG-009 |

## 12. TASK-SOLVER-MIG-009 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 完成 `group1` ONNX 导出与 Rust runtime bridge，为点击链路提供统一运行时边界 |
| 主执行角色 | Rust 实现者 |
| 协作角色 | 算法负责人、Python 实现者 |
| 前置条件 | TASK-SOLVER-MIG-008 已通过 |
| 主要输入 | `group1` 训练产物、matcher 约束、Rust 工程 |
| 操作步骤 | 1. 实现 `scene detector` 与 `query parser` 的 ONNX 导出。<br>2. 在 Rust 扩展中建立双模型推理入口。<br>3. 固定检测结果到 Python matcher 的桥接格式，或把简单后处理一并下沉。 |
| 输出产物 | `group1` ONNX 导出、Rust runtime、桥接接口 |
| 验收标准 | `group1` 求解不再依赖 PyTorch 运行时，且可以向 Python 结果层输出稳定结构 |
| 阻断条件 | `group1` 仍需要 Ultralytics Python runtime 才能完成推理 |
| 失败处理 | 回补 `group1` ONNX 路线，不进入 Python 结果面收口 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-SOLVER-MIG-010 |

## 13. TASK-SOLVER-MIG-010 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 迁移 `group1` 求解服务、matcher 接口和统一结果映射，让 Python 层只承担业务结果面 |
| 主执行角色 | Python 实现者 |
| 协作角色 | Rust 实现者、算法负责人 |
| 前置条件 | TASK-SOLVER-MIG-009 已通过 |
| 主要输入 | `core/solve/*`、`core/inference/*`、Rust bridge 输出 |
| 操作步骤 | 1. 迁移 `group1` service 和 matcher 接口。<br>2. 统一 `group1/group2` 的公开结果对象。<br>3. 删除对旧 request/response 包装层的依赖。 |
| 输出产物 | group1 service、统一结果映射、专项回归测试 |
| 验收标准 | 独立 solver 包能同时完成两类业务求解，且返回业务结果对象而不是训练内部结构 |
| 阻断条件 | 仍返回旧 `request/response` 包装层，或 matcher 紧耦合训练目录 |
| 失败处理 | 回补 Python 结果层边界，不进入资源打包 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-SOLVER-MIG-011 |

## 14. TASK-SOLVER-MIG-011 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 实现 wheel 内模型与元数据加载，使 `pip install` 后可直接调用函数 |
| 主执行角色 | Python 实现者 |
| 协作角色 | Rust 实现者、发布维护者 |
| 前置条件 | TASK-SOLVER-MIG-010 已通过 |
| 主要输入 | 子项目骨架、导出资产、Rust bridge |
| 操作步骤 | 1. 固定 package data 目录与资源清单。<br>2. 实现默认资源加载器，优先读取包内 ONNX 资产。<br>3. 仅为维护者保留可选 `asset_root` 覆盖入口。 |
| 输出产物 | 资源加载器、包资源清单、构建配置 |
| 验收标准 | 新环境仅安装 wheel 后即可完成一次求解，不需要手工复制模型文件 |
| 阻断条件 | 仍要求调用方手工指定权重路径或外置 bundle 目录 |
| 失败处理 | 回补资源打包和加载规则，不进入发布链路 |
| 预计工时 | 1 天 |
| 完成后进入 | TASK-SOLVER-MIG-012 |

## 15. TASK-SOLVER-MIG-012 执行表

| 字段 | 内容 |
|---|---|
| 任务目标 | 补齐独立 solver 的回归测试、安装测试、发布链路，并降级旧 `sinan solve` 公开角色 |
| 主执行角色 | 测试负责人 / 发布维护者 |
| 协作角色 | Python 实现者、Rust 实现者、项目维护者 |
| 前置条件 | TASK-SOLVER-MIG-011 已通过 |
| 主要输入 | 导出资产、独立 solver 子项目、当前发布文档 |
| 操作步骤 | 1. 新增 API 单测、资源加载测试、异常测试和 wheel 安装冒烟。<br>2. 固定训练仓库 `export-solver-assets` 与 solver 项目构建顺序。<br>3. 把 `sinan solve` 改为内部调试或显式弃用入口，并同步文档。 |
| 输出产物 | 单测、安装测试、发布命令、版本映射表、弃用说明 |
| 验收标准 | 维护者能从训练产物稳定生成并发布 solver wheel；最终用户不再被引导去用旧入口 |
| 阻断条件 | 发布还需要手工拼装模型文件，或旧公开文档继续把 `sinan solve` 当主入口 |
| 失败处理 | 指回具体缺失项重做，不允许宣布迁移完成 |
| 预计工时 | 1 天 |
| 完成后进入 | 正式代码迁移实施 |

## 16. 不允许跳过的关口

下面 6 个关口不能跳：

1. 训练仓库与独立 solver 包边界冻结
2. 公开函数与异常合同冻结
3. `PT -> ONNX` 导出合同冻结
4. Rust 原生扩展工程边界冻结
5. `pip install` 安装后可直接调用的测试门禁
6. 旧 `sinan solve` 的弃用与文档同步

## 17. 完成标志

下面 5 条同时满足，才算“独立 solver 迁移任务已可执行”：

1. 12 个任务都有明确输入、输出、验收和阻断条件。
2. 公开 API 名称已经固定为业务语义导向，不再依赖内部术语。
3. 训练仓库与独立 solver 项目的发布交接边界已经冻结。
4. Rust 扩展和 ONNX Runtime 已被正式纳入 solver 运行时设计，而不是口头承诺。
5. 实现者不再需要追问“到底是继续改 `core/solve`，还是做独立包”。
