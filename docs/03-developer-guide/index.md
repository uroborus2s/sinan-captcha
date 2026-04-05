# 开发者指南概览

本目录回答的是：如何维护“统一验证码求解包/库 + 模型生产工具链”这一套单仓工程。

## 1. 这部分和用户指南有什么区别

用户指南主要回答：

- 训练机怎么部署
- 素材和数据怎么准备
- 当前训练链路怎么运行

开发者指南回答的是：

- 如何维护求解包、bundle 和模型生产工具链的主次关系
- 如何维护仓库结构、运行目录边界和发布流程
- 如何把训练产物真正收口成可交付的 solver 版本

## 2. 新维护者先记住什么

- 一级产品是统一求解包/库，不是训练 CLI 本身。
- `sinan-generator`、`sinan train/test/evaluate/release` 和 `sinan auto-train` 都是支撑能力。
- 当前最完整的代码主线仍然是训练和评估；统一求解与 bundle 主线已经进入正式需求和代码骨架，但还需要继续提升到正式发布层。
- 任何文档、发布或代码变更，都应该说明它影响的是：
  - 最终 solver 交付面
  - 还是内部模型生产工具链

## 3. 新维护者建议阅读顺序

按这个顺序读最稳：

1. [维护者快速使用说明](./maintainer-quickstart.md)
2. [solver bundle 与集成边界](./solver-bundle-and-integration.md)
3. [仓库结构与边界](./repository-structure-and-boundaries.md)
4. [本地开发与验证工作流](./local-development-workflow.md)
5. [发布与交付工作流](./release-and-delivery-workflow.md)

如果你还需要内部背景，再继续看：

- [项目开发文档（内）概览](../04-project-development/index.md)

## 4. 当前稳定事实

- 当前正式 CLI：
  - `sinan-generator`
  - `sinan`
- 当前最重要的目录边界：
  - 源码仓库
  - 生成器工作区
  - 训练目录
  - solver 交付目录
- 当前最重要的产品边界：
  - 最终交付：solver package/library + bundle
  - 支撑产线：generator + training + auto-train

## 5. 这部分文档的使用原则

- 先以 solver-first 产品定位理解仓库，再看具体实现路径
- 先按当前实现和当前 CLI 写维护文档，不宣称未完成能力已经交付
- 任何对外行为变更，都要回写用户指南
- 任何维护流程变更，都要回写开发者指南和 `.factory`
