# sinan-captcha

图形验证码训练工程骨架。

当前仓库分为两条主线：

- `generator/`：Go 多模式验证码样本生成器，当前包含 `click/native` 与 `slide/native`
- `core/`：Python 训练与数据工程核心包

配套目录：

- `scripts/`：CLI 和 PowerShell 入口
- `tests/`：最小测试骨架
- `configs/`：运行配置
- `materials/`：素材清单和本地素材目录
- `datasets/`：运行时数据目录
- `reports/`：评估与 QA 报告

当前状态是“实现推进中”，已具备统一的 mode/backend 入口、`gold` 真值校验门禁和两种原生样本模式骨架。
