# 独立 solver 包迁移与集成边界

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：维护训练仓库、独立 solver 包和发布链路的开发者
- 负责人：Codex
- 最近更新：2026-04-05

## 0. 这页解决什么问题

这页回答的是：

- 最终 solver 为什么不应继续作为训练仓库里的子命令存在
- 当前仓库里哪些 solver 代码可以作为迁移源
- bundle 为什么降级为内部交接资产
- 后续代码迁移为什么应优先看 ONNX 导出、Rust 扩展桥接和安装测试

## 1. 先记住主次关系

当前仓库维护的是训练与资产生产主线，但最终 solver 交付必须分清两个项目面：

- 独立 solver 项目：
  - `sinanz`
  - `pip install`
  - `sn_match_slider(...)`
  - `sn_match_targets(...)`
- 模型生产项目：
  - `sinan-generator`
  - `sinan train/test/evaluate/release`
  - `sinan auto-train`

训练产线的目标不是把训练目录或旧 CLI 暴露给调用方，而是持续产出可被独立 solver 包吸收的 `ONNX + metadata` 推理资产版本。

## 2. 当前已存在的 solver 迁移源

截至 2026-04-05，仓库里已经有一套明确的 solver 迁移源代码：

- `core/solve/contracts.py`
  - 旧公开合同和现有业务字段来源
- `core/solve/bundle.py`
  - 旧 bundle manifest / 资源校验逻辑来源
- `core/solve/service.py`
  - `group1` / `group2` 求解服务骨架
- `core/solve/cli.py`
  - 迁移期内部调试 CLI

因此当前问题已经不再是“有没有 `solve` 入口”，而是“如何把这些代码迁移成独立 PyPI solver 包”。

## 3. 当前最关键的迁移差距

### 3.1 旧入口还在训练仓库里

当前公开实现仍主要依赖：

```bash
uv run sinan solve ...
```

这条路现在应降级为内部调试入口，而不是最终使用者合同。

### 3.2 旧 bundle 仍是内部交接资产

当前 `core/solve/bundle.py` 和 `package-windows --bundle-dir` 这套逻辑仍围绕外置 bundle。

这批能力现在的正确定位是：

- 训练仓库到独立 solver 项目之间的内部交接资产
- 维护者调试与验收资产
- 不是最终使用者安装界面

### 3.3 还没有真正形成 `pip install` 即可调用的 wheel 交付闭环

当前仓库里还没有完整的 `PT -> ONNX` 导出链路、Rust 扩展桥接和平台 wheel 安装冒烟门禁。

## 4. 求解面与训练面的边界规则

### 4.1 独立 solver 不应直接依赖训练目录或训练仓库私有实现

最终求解层不应直接读取：

- `runs/`
- `datasets/`
- `reports/`

也不应继续 import 训练侧私有 runner。它只能消费导出的推理资产和自己的运行时模块。

### 4.2 训练产线不应冒充最终公开 SDK

当前训练 CLI 的稳定职责仍然是：

- 训练
- 测试
- 评估
- 发布训练交付包
- 导出推理资产

训练命令可以为 solver 提供模型来源，但不应替代最终的函数调用合同。

## 5. 后续代码偏差评估应优先看哪里

下一轮代码偏差评估建议按下面顺序做：

1. `group2` 是否已经完全切断对训练私有 runtime 的依赖
2. `PT -> ONNX` 导出合同是否已冻结并可稳定执行
3. Rust 扩展是否已经承担 ONNX Runtime 调用边界
4. `group1` 迁移后是否仍耦合旧 request/response 和旧 matcher 结构
5. 独立 solver 测试面是否覆盖 `uv build -> pip install -> 直接函数调用`
6. 旧 `sinan solve` 与旧 bundle 文档是否已经完成降级

## 6. 改这一层时必须同步什么

如果你改的是独立 solver 迁移面，至少同步：

- `docs/04-project-development/04-design/api-design.md`
- `docs/04-project-development/04-design/solver-asset-export-contract.md`
- `docs/04-project-development/04-design/module-structure-and-delivery.md`
- `docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md`
- `docs/03-developer-guide/solver-bundle-and-integration.md`
- `.factory/memory/current-state.md`
- `.factory/memory/change-summary.md`

## 7. 这页完成标志

如果你已经能清楚回答下面 4 个问题，就说明这页达标：

1. 为什么最终 solver 应是独立 PyPI 包，而不是训练 CLI 子命令
2. 当前仓库里的哪些代码是迁移源，而不是最终公开边界
3. 为什么 bundle 现在应降级为内部交接资产
4. 后续代码迁移为什么应优先看 ONNX 导出、Rust 扩展和安装测试
