# 用户指南

本目录现在只按两类角色组织：

- 使用者角色
  - 关心的是最终求解包、如何在自己的应用里调用、如何做业务测试
- 训练者角色
  - 关心的是训练机安装、生成器、训练器、自动化训练，以及如何把模型训练出来

## 使用者角色入口

1. [使用者角色：安装与使用最终求解包](./use-solver-bundle.md)
2. [使用者角色：在自己的应用中接入并做业务测试](./application-integration.md)

## 训练者角色入口

1. [训练者角色：训练机安装](./windows-bundle-install.md)
2. [训练者角色：快速开始](./windows-quickstart.md)
3. [训练者角色：使用生成器准备训练数据](./prepare-training-data-with-generator.md)
4. [训练者角色：使用训练器完成训练、测试与评估](./from-base-model-to-training-guide.md)
5. [训练者角色：使用自动化训练](./auto-train-on-training-machine.md)
6. [训练者角色：训练后结果验收](./use-and-test-trained-models.md)
7. [训练者角色：CUDA 版本检查](./how-to-check-cuda-version.md)

## 如果你想看状态、范围或审核结论

- [角色与功能审核结论](./user-guide.md)

## 附录

- [交付物与目录边界](./use-build-artifacts.md)

## 最短判断

- 你现在要把模型训练出来：从“训练者角色：训练机安装”开始。
- 你现在要规划最终业务接入：从“使用者角色：安装与使用最终求解包”开始。
- 你现在要开始自动训练：先完成一次手动训练主线，再读“训练者角色：使用自动化训练”。
