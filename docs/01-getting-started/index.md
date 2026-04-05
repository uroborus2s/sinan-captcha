# 入门说明概览

`sinan-captcha` 的一级产品目标不是训练 CLI 本身，而是一个本地可调用的统一验证码求解包/库。仓库当前同时维护为这个最终产物服务的模型生产工具链。

如果你第一次接触这个项目，先记住三件事：

1. 最终交付物是统一求解包/库和可复制的 bundle，不是分散的训练命令集合。
2. 当前最完整的实现主线仍然是样本生成、训练、测试和评估，所以现有详细公开页面主要围绕训练产线展开。
3. V1 仍是本地 CLI / package 工作流，不是公网 API 平台。

推荐阅读顺序：

1. [角色与审核结论](../02-user-guide/user-guide.md)
2. [使用者角色：安装与使用最终求解包](../02-user-guide/use-solver-bundle.md)
3. [使用者角色：在自己的应用中接入并做业务测试](../02-user-guide/application-integration.md)
4. [训练者角色：训练机安装](../02-user-guide/windows-bundle-install.md)
5. [训练者角色：快速开始](../02-user-guide/windows-quickstart.md)
6. [训练者角色：使用生成器准备训练数据](../02-user-guide/prepare-training-data-with-generator.md)
7. [训练者角色：使用训练器完成训练、测试与评估](../02-user-guide/from-base-model-to-training-guide.md)
8. [训练者角色：使用自动化训练](../02-user-guide/auto-train-on-training-machine.md)

本目录只负责把新读者带到正确入口，不承载维护者过程文档和内部设计材料。
