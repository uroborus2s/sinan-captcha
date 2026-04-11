# 入门说明概览

`sinan-captcha` 的一级产品目标不是训练 CLI 本身，而是一个本地可调用的统一验证码求解包/库。仓库当前同时维护为这个最终产物服务的模型生产工具链。

如果你第一次接触这个项目，先记住三件事：

1. 最终交付物是统一求解包/库和可复制的 bundle，不是分散的训练命令集合。
2. 当前最完整的实现主线仍然是样本生成、训练、测试和评估，所以现有详细公开页面主要围绕训练产线展开。
3. V1 仍是本地 CLI / package 工作流，不是公网 API 平台。

推荐阅读顺序：

1. [用户指南概览](../02-user-guide/index.md)
2. [使用者：Solver 包使用指南](../02-user-guide/solver-package-usage-guide.md)
3. [使用者：Solver 包函数参考](../02-user-guide/solver-package-function-reference.md)
4. [训练者：完整训练操作指南](../02-user-guide/complete-training-operations-guide.md)
5. [训练者：生成器 CLI 全量参考](../02-user-guide/generator-cli-reference.md)
6. [训练者：训练器 CLI 全量参考](../02-user-guide/trainer-cli-reference.md)
7. [训练者：Solver Bundle CLI 参考](../02-user-guide/solver-bundle-cli-reference.md)

本目录只负责把新读者带到正确入口，不承载维护者过程文档和内部设计材料。
