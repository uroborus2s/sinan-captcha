# 交付物与目录边界

这页是附录，不是第一次阅读入口。

## 1. 训练机上常见交付物

- `sinan-generator.exe`
- `sinan-captcha` Python 包或 wheel
- 可选训练数据集
- 可选素材包

## 2. 训练机上应该长期保留的目录

```text
D:\
  sinan-captcha-generator\
  sinan-captcha-work\
```

目录职责：

- 生成器安装目录只负责生成器和工作区
- 训练目录只负责训练环境、数据、运行结果

## 3. 业务应用不要直接依赖的东西

- `packages/sinan-captcha/src/solve/`
- `runs/`
- `weights/best.pt`
- 训练仓库内部脚本

## 4. 正确阅读顺序

### 你是使用者

- [使用者角色：安装与使用最终求解包](./use-solver-bundle.md)
- [使用者角色：在自己的应用中接入并做业务测试](./application-integration.md)

### 你是训练者

- [训练者角色：训练机安装](./windows-bundle-install.md)
- [训练者角色：快速开始](./windows-quickstart.md)
- [训练者角色：使用生成器准备训练数据](./prepare-training-data-with-generator.md)
- [训练者角色：使用训练器完成训练、测试与评估](./from-base-model-to-training-guide.md)
- [训练者角色：使用自动化训练](./auto-train-on-training-machine.md)
