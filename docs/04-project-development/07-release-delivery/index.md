# 发布与交付概览

本目录收纳验收、发布、交付和回滚相关文档。

- 本页是该目录的正文首页，用于说明范围、读者和维护边界。
- 目录树、页面路径和访问级别统一由根 `docs/index.md` 声明，这里不重复维护页面清单。
- 本目录下的 Markdown 页面、契约文件和资源文件应随内容变更一起演进。

当前发布与交付主线已经收口为：

- 本地构建：`uv run sinan release build`
- 本地上传：`uv run sinan release publish --token-env PYPI_TOKEN`
- Windows 交付包：`uv run sinan release package-windows`
- 训练机初始化：`uvx --from sinan-captcha sinan env setup-train`

当前交付模型明确分为两个目录：

- 生成器安装目录：`sinan-generator.exe`、可选显式工作区 `workspace/`
- 训练目录：运行时 `pyproject.toml`、`.venv`、`datasets/`、`runs/`、`reports/`
