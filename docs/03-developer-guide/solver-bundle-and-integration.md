# `sinanz` 集成与资产 staging

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：维护训练仓库与独立 solver 包边界的开发者
- 最近更新：2026-04-11

## 这页解决什么问题

这页说明 3 件事：

1. 当前 `sinanz` 在仓库中的真实状态
2. `sinan solve`、导出资产目录、`packages/solver/resources/` 之间的关系
3. 修改 solver 集成面时，哪些目录是参考实现，哪些目录才是最终包边界

## 当前 `sinanz` 的真实状态

`packages/solver` 已经是独立 Python 包，而不是概念稿。

当前已成立的事实：

- 包名：`sinanz`
- 正式对外优先入口：
  - `sn_match_slider(...)`
  - `sn_match_targets(...)`
- 同时导出：
  - `CaptchaSolver`
  - 异常类
  - 结果类型和输入类型别名
- 运行时依赖：
  - `numpy`
  - `onnxruntime`
  - `pillow`
- 当前运行目标：
  - 纯 Python + `onnxruntime`
- 当前资源布局：
  - `packages/solver/src/`
  - `packages/solver/resources/manifest.json`
  - `packages/solver/resources/metadata/`
  - `packages/solver/resources/models/`

这意味着：

- `sinanz` 已经可以本地构建和测试
- 它不再只是“未来计划”
- 但它的嵌入式模型资源依然依赖训练仓库先导出、再 stage
- 训练仓库里仍保留 `packages/sinan-captcha/src/solve/` 这条参考实现 / bundle 调试路径；不要用它去反推 `sinanz` 的公共包边界

当前 API 边界再强调一次：

- 业务接入默认优先函数式入口 `sn_match_slider(...)` 与 `sn_match_targets(...)`
- `CaptchaSolver` 是显式持有 `device` / `asset_root` 的 facade，适合上层应用复用实例
- 类型别名和异常类属于公共包接口的一部分，但不应被误解为另一套业务语义入口

## 训练仓库与 `sinanz` 的边界

### 训练仓库负责什么

训练仓库负责：

- 训练
- 评估
- 生成 bundle
- 导出 solver 资产
- 为独立 solver 包提供模型和 metadata 来源

对应目录主要是：

- `packages/sinan-captcha/src/release/`
- `packages/sinan-captcha/src/solve/`
- `work_home/reports/solver-assets/`

这里的 `packages/sinan-captcha/src/solve/` 是训练仓库视角的参考实现与调试路径，不等于 `packages/solver/src/` 的正式公共包边界。

### `sinanz` 负责什么

`sinanz` 负责：

- 暴露公共函数合同
- 从包内 `resources/` 读取资产
- 用独立运行时完成推理

它不应该直接依赖：

- `runs/`
- `datasets/`
- `reports/`
- 训练仓库私有 runner

## `sinan solve` 现在的定位

`uv run sinan solve ...` 仍然有价值，但它的角色是：

- 训练仓库内的维护者调试入口
- bundle 校验与单次请求回放入口
- 训练仓库侧参考实现

它不是最终对外 SDK 合同。

对外稳定合同应优先看：

- `packages/solver/src/`
- `packages/solver/pyproject.toml`
- `packages/solver/resources/`

## 资产生命周期

当前 solver 资产的正确流向是：

1. 训练产线产生 checkpoint
2. `sinan release export-solver-assets` 导出一份独立资产目录
3. `sinan release stage-solver-assets` 把这份资产写入 `packages/solver/resources/`
4. `sinan release build-solver` 或 `scripts/repo.py build solver` 打出新的 `sinanz` wheel

用一句话概括：

导出目录是中间交接资产，`packages/solver/resources/` 是真正的打包输入。

如果你还需要记一个更短的术语表：

- 导出资产目录：
  `export-solver-assets` 产物
- staged 资源目录：
  `packages/solver/resources/`
- runtime bundle：
  训练仓库 `sinan solve ...` 使用的外部 bundle
- 最终交付包：
  `sinanz` wheel 或 `package-windows` 输出的训练机交付目录

再强调一次：

- `packages/solver/resources/` 不是缓存目录。
- 它是发布前 staging 输入，清理它等于清理下一次 `sinanz` 打包要吃进去的真实资源。

## 哪些代码是“迁移源”，哪些是“最终边界”

### 迁移源 / 参考实现

- `packages/sinan-captcha/src/solve/contracts.py`
- `packages/sinan-captcha/src/solve/bundle.py`
- `packages/sinan-captcha/src/solve/service.py`
- `packages/sinan-captcha/src/solve/cli.py`

这些文件能帮助你理解训练仓库当前的 bundle 合同和调试路径，但它们不是最终公共 SDK 的唯一边界。

### 最终包边界

- `packages/solver/src/sinanz.py`
- `packages/solver/src/sinanz_group1_service.py`
- `packages/solver/src/sinanz_group2_service.py`
- `packages/solver/src/sinanz_resources.py`
- `packages/solver/resources/`

如果你在做业务接入、公共 API 审查、安装测试或 wheel 交付，这一层才是优先对象。

## 修改这一层时必须同步什么

至少同步：

- `docs/03-developer-guide/solver-bundle-and-integration.md`
- `docs/03-developer-guide/release-and-delivery-workflow.md`
- `docs/04-project-development/04-design/api-design.md`
- `docs/04-project-development/04-design/solver-asset-export-contract.md`
- `docs/04-project-development/04-design/module-structure-and-delivery.md`
- `.factory/memory/current-state.md`
- `.factory/memory/change-summary.md`

## 改这一层前先自问

1. 这次改动是在修训练仓库内部调试路径，还是在改独立 solver 的公共边界。
2. 这次改动会不会改变 `packages/solver/resources/` 的文件结构或内容要求。
3. 这次改动后，`sinanz` 是否还能在不依赖训练目录的前提下独立运行。
4. 如果执行了资产 staging，是否已经把目标资产版本和 Git 变更核对清楚。
