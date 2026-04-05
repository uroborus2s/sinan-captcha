# 交付包说明

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：项目维护者、交付负责人、调用方支持人员
- 负责人：Codex
- 最近更新：2026-04-05

## 1. 交付对象划分

本项目当前存在两类交付对象：

- 训练机操作者
- 最终 solver 使用者

这两类对象拿到的交付内容不完全相同，不能混成一个模糊“安装包”概念。

## 2. 训练机交付包

### 当前正式内容

- Python wheel / sdist
- Go 生成器二进制
- 可选 `datasets/`
- 可选 `materials/`
- 训练机安装说明

### 当前目录模型

```text
windows-bundle/
  python/
    sinan_captcha-<version>-py3-none-any.whl
  generator/
    sinan-generator.exe
  datasets/                 # 可选
  materials/                # 可选
  README-交付包说明.txt
```

### 适用场景

- 训练机不克隆源码仓库
- 训练机需要初始化训练目录
- 训练机需要本地生成样本或直接开训

## 3. 目标 solver 交付包

### 目标正式内容

- solver package/library
- solver bundle
- bundle manifest
- 调用说明
- 版本映射说明

### 目标目录模型

```text
solver-delivery/
  python/
    sinan_captcha-<version>-py3-none-any.whl
  bundle/
    manifest.json
    models/
      group1/
      group2/
  README-solver-使用说明.txt
```

### 适用场景

- 调用方只需要加载 bundle 并发起求解
- 目标机器不承担训练工作
- 目标机器不需要生成器工作区、训练目录和 study 目录

## 4. 训练资产与交付资产的边界

### 训练资产

- `materials/`
- `datasets/`
- `runs/`
- `reports/`
- `studies/`

### 交付资产

- Python 发布包
- Go 生成器二进制
- solver bundle
- 安装与调用说明

规则：

- 交付资产不得依赖训练资产的绝对路径
- 调用方不应直接消费 `runs/`
- solver bundle 不是训练目录的快捷方式

## 5. 当前实现状态

截至 2026-04-05：

- 训练机交付包：已具备正式命令和稳定路径
- solver 交付包：设计已固定，代码骨架存在，但尚未并入正式 `package-windows`

因此当前必须区分：

- “已经正式发出的训练交付包”
- “目标态中的 solver 交付包”

## 6. 交付时必须附带的元信息

无论训练交付还是 solver 交付，都必须附带：

- 版本号
- 构建时间
- Python 包版本
- 数据集版本或适用数据版本说明
- 模型运行名或 bundle 版本
- 相关文档入口

## 7. 本页完成标志

当维护者读完后，应能明确：

1. 当前到底有几类交付包
2. 每类交付包应面向谁
3. 训练资产和最终交付资产应如何隔离
