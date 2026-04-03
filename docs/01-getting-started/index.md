# 入门说明概览

`sinan-captcha` 是一个由两个本地 CLI 组成的训练工程：

- `sinan-generator`
  - Go 生成器
  - 负责固定工作区、素材导入/同步、原始样本生成、批次 QA、YOLO 数据集导出
- `sinan`
  - Python CLI
  - 负责训练目录初始化、训练环境检查、训练、评估和发布

如果你第一次接触这个项目，先记住三件事：

1. 这是一个本地 CLI 工程，不是 HTTP 服务。
2. 生成样本和训练模型是两条独立主线，通过文件契约对接。
3. 正式入口只有 `sinan-generator` 和 `sinan`。

推荐阅读顺序：

1. [用户指南总览](../02-user-guide/user-guide.md)
2. [Windows 快速开始](../02-user-guide/windows-quickstart.md)
3. [使用交付包在 Windows 训练机上安装](../02-user-guide/windows-bundle-install.md)
4. [使用交付物与正式 CLI](../02-user-guide/use-build-artifacts.md)
5. [Windows 训练机安装与模型训练完整指南](../02-user-guide/from-base-model-to-training-guide.md)
6. [用生成器准备训练数据](../02-user-guide/prepare-training-data-with-generator.md)
7. [训练完成后的模型使用与测试](../02-user-guide/use-and-test-trained-models.md)

本目录只负责把新读者带到正确入口，不承载维护者过程文档和内部设计材料。
