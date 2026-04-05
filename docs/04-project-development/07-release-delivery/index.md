# 发布与交付概览

本目录收纳验收、发布、交付和回滚相关文档。

- 本页是该目录的正文首页，用于说明范围、读者和维护边界。
- 目录树、页面路径和访问级别统一由根 `docs/index.md` 声明，这里不重复维护页面清单。
- 本目录下的 Markdown 页面、契约文件和资源文件应随内容变更一起演进。

当前发布与交付文档围绕两条线组织：

- 当前稳定发布线：
  - Python wheel / sdist
  - Go 生成器二进制
  - 面向训练机的 Windows 交付包
- 目标正式交付线：
  - solver package/library
  - solver bundle
  - 面向调用方的可复制交付包

阅读顺序建议：

1. [发布说明](./release-notes.md)
2. [交付包说明](./delivery-package.md)
3. [发布检查清单](./release-checklist.md)

本目录的原则是：

- 可以定义目标交付物，但不能把尚未接通的代码路径写成“已经稳定可发”
- 当前 `package-windows` 仍以训练机交付为主
- solver bundle 已经进入正式设计和代码骨架，但仍需继续接通根 CLI 与 release 主线
