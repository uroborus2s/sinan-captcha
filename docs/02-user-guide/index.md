# 用户指南（02-user-guide）

本目录面向两类读者：

- 使用者：只关心如何安装并调用最终 `sinanz` 求解包。
- 训练者：负责生成数据、训练模型、测试评估、组装本地 solver bundle。

## 建议阅读顺序

### 路线 A：你是业务接入方（使用者）

1. [使用者：Solver 包使用指南](./solver-package-usage-guide.md)
2. [使用者：Solver 包函数参考](./solver-package-function-reference.md)

### 路线 B：你是模型生产方（训练者）

1. [训练者：完整训练操作指南](./complete-training-operations-guide.md)
2. [训练者：生成器 CLI 全量参考](./generator-cli-reference.md)
3. [训练者：训练器 CLI 全量参考](./trainer-cli-reference.md)
4. [训练者：Solver Bundle CLI 参考](./solver-bundle-cli-reference.md)

## 文档设计原则

- 所有命令说明以当前源码（`2026-04-11`）为准。
- 主线文档先给“可直接执行”的步骤，再给完整参数参考。
- Solver 包分为两层说明：
  - 使用指南：安装、接入、错误处理。
  - 函数参考：签名、参数、返回类型、异常与调试字段。
