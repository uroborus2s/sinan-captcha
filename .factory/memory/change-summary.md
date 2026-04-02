# 变更摘要

## 2026-04-02

- 统一 Go 生成器接口，`generate` 命令新增 `--mode` 与 `--backend`
- 新增 `click/native` 与 `slide/native` 两类原生 backend 路径
- 在 JSONL 与 `manifest.json` 中补齐 `mode`、`backend`、`truth_checks`、滑块字段和 `asset_dirs`
- 新增 `gold` 真值硬门禁代码：一致性校验、重放校验、负样本校验
- Python `core/` 侧同步适配新的 group2 字段：`master_image`、`tile_image`、`target_gap`、`tile_bbox`、`offset_x`、`offset_y`
- 新增 `scripts/export/export_group2_batch.py`
- 回归验证通过：
  - `GOCACHE=/tmp/sinan-go-build-cache go test ./...`
  - `python3 -m unittest discover -s tests/python -p 'test_*.py'`

## 2026-04-02 批次 QA 强化

- 生成器 `qa` 已升级为批次逐条审计，不再只统计图片和标签数量
- QA 新增检查：
  - `truth_checks` 三项必须全部 `passed`
  - 样本 `mode/backend/source_batch` 必须与 manifest 一致
  - 资产路径必须落在对应 `asset_dirs` 下
  - 主图、查询图、滑块图尺寸必须与配置或几何真值一致
  - click/slide 样本结构会复用真值一致性与负样本校验逻辑
- 新增 Go 单测覆盖：
  - 合法 click 批次
  - 合法 slide 批次
  - 缺少 `truth_checks` 的坏批次应被拒绝

- 2026-04-02：重构 `docs/02-user-guide/from-base-model-to-training-guide.md`，将手册主线改为“仓库产物 + 训练工作目录 + 当前实现状态”，移除把 `go-captcha-service` 作为默认前置的旧叙述。
- 2026-04-02：同步更新 `docs/02-user-guide/user-guide.md` 和 `/.factory/memory/current-state.md`，明确新手阅读入口与当前仓库事实边界。
- 2026-04-02：重构用户指南信息架构，新增 `docs/02-user-guide/use-build-artifacts.md`，将 `docs/02-user-guide/user-guide.md` 改为公开总览页，并把维护者说明迁移到 `docs/03-developer-guide/maintainer-quickstart.md`。
- 2026-04-02：更新 `docs/index.md` 导航，移除用户指南中的私有页面混入，确保公开路径只围绕“使用编译结果”和“训练环境 + 模型训练”两类目标展开。
- 2026-04-02：继续压缩训练主手册，新增 `docs/02-user-guide/use-and-test-trained-models.md`，把“训练后模型如何使用与测试”从训练页拆出，并同步修正自动标注与 JSONL 评估的公开状态说明。
- 2026-04-02：新增离线素材包构建脚本与示例配置，支持批量下载背景图、提取官方图标、生成 `classes.yaml`，并同步补充到公开使用文档。
- 2026-04-02：将生成器相关需求、设计、过程文档统一收口为“受控集成 + 可插拔 backend”，消除“参考 go-captcha 思路”和“直接使用库能力”的混写。
- 2026-04-02：将第二专项正式收口为“滑块缺口定位”，并同步更新需求、架构、模块边界、执行清单与追踪矩阵。
- 2026-04-02：把“训练素材必须 100% 正确”落地为生成器 `gold` 硬门禁，新增一致性校验、重放校验和负样本校验要求。
