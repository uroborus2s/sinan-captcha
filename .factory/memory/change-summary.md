# 变更摘要

## 2026-04-12 补齐 Ollama 连接异常包装，避免 `prelabel-vlm` 直接打印底层 traceback

- 已更新：
  - `packages/sinan-captcha/src/materials/query_audit.py`
  - `tests/python/test_group1_query_audit.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 共享 `_post_json()` 已补齐本地 Ollama 连接层异常包装
  - 当本地服务接受连接后又主动断开，或出现 `ConnectionResetError` / `TimeoutError` 一类底层异常时，CLI 现在会返回明确 `RuntimeError`
  - `train group1 prelabel-vlm` 与 `materials audit-group1-query` 复用同一包装逻辑，不再因为底层 `RemoteDisconnected` 之类异常直接向用户打印整段 Python traceback
- 已运行验证：
  - `uv run pytest tests/python/test_group1_query_audit.py -q`
  - `uv run pytest tests/python/test_group1_query_audit.py tests/python/test_train_prelabel_service.py -q`

## 2026-04-12 调整 `audit-group1-query` 为大模型结果优先，本地切图数量不一致只记 warning

- 已更新：
  - `packages/sinan-captcha/src/materials/query_audit.py`
  - `tests/python/test_group1_query_audit.py`
  - `docs/02-user-guide/trainer-cli-reference.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 本地切图数量与大模型返回数量不一致时，不再返回 `error`
  - 当前会把不一致原因写入 warning，并继续按大模型 `icons` 结果写入审计报告
  - 当前若本地切图完全未命中任何候选图标，也只写 warning，并继续按大模型结果生成模板计划
  - 当前若大模型返回的图标多于本地切图数量，也会继续把这些模型识别到的模板纳入模板计划
  - 当前 summary 已新增 `warning_count`
- 已运行验证：
  - `uv run pytest tests/python/test_group1_query_audit.py -q`
  - `uv run python -m py_compile packages/sinan-captcha/src/materials/query_audit.py tests/python/test_group1_query_audit.py`
  - `git diff --check`

## 2026-04-12 收口根目录仓库级 CLI 到 `scripts/repo_tools/` 并规范安装入口

- 已更新：
  - `pyproject.toml`
  - `scripts/repo_tools/__init__.py`
  - `scripts/repo_tools/repo_cli.py`
  - `scripts/repo_tools/repo_release.py`
  - `scripts/repo_tools/repo_solver_export.py`
  - `scripts/repo_tools/repo_solver_asset_contract.py`
  - `tests/python/test_repo_cli.py`
  - `tests/python/test_release_service.py`
  - `tests/python/test_solver_asset_contract.py`
  - `tests/python/test_solver_asset_export_group2.py`
  - `docs/03-developer-guide/index.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `scripts/README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 已删除：
  - `repo_cli.py`
  - `repo_release.py`
  - `repo_solver_export.py`
  - `repo_solver_asset_contract.py`
- 当前已完成的目标：
  - 根目录不再散落仓库级 CLI `.py` 文件
  - 仓库级实现统一迁入 `scripts/repo_tools/`
  - 根工作区安装入口改为通过 `repo_tools` 包暴露 `repo` console script
  - 保持 `uv run repo ...` 对外命令面不变
  - 开发者文档与 `.factory` 记忆层已同步新结构
- 待验证：
  - `repo` 入口与仓库级测试回归

## 2026-04-11 修复 `audit-group1-query` 真实变体 ID 碰撞并新增背景风格采集命令

- 已更新：
  - `packages/sinan-captcha/src/materials/query_audit.py`
  - `packages/sinan-captcha/src/materials/background_style.py`
  - `packages/sinan-captcha/src/materials/background_style_cli.py`
  - `packages/sinan-captcha/src/cli.py`
  - `tests/python/test_group1_query_audit.py`
  - `tests/python/test_background_style_collect.py`
  - `tests/python/test_root_cli.py`
  - `docs/02-user-guide/trainer-cli-reference.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 修复 `var_real_beach_umbrella_squa_d` 这类满长 `variant_id` 追加后缀被截断后仍然撞名的问题
  - 为真实 query 图标变体 ID 增加后缀预留空间和哈希重试兜底
  - 新增 `uv run sinan materials collect-backgrounds`，使用本地 Ollama 分析参考背景风格并用 Pexels 下载相似背景
  - 背景风格提示词明确忽略验证码图标、缺口、滑块、文字和前景符号
  - 新命令默认输出根目录已收口到 `work_home/materials/incoming`，下载图片直接落到 `incoming/backgrounds/`
  - 新命令会输出 `manifests/materials.yaml`、`manifests/backgrounds.csv` 与 `reports/background-style-collection.json`
  - 新增 `--dry-run`，可只生成风格画像和搜索词，不要求 Pexels API key
- 已运行验证：
  - `uv run pytest tests/python/test_group1_query_audit.py tests/python/test_background_style_collect.py tests/python/test_root_cli.py -q`
  - `uv run python -m py_compile packages/sinan-captcha/src/materials/query_audit.py packages/sinan-captcha/src/materials/background_style.py packages/sinan-captcha/src/materials/background_style_cli.py packages/sinan-captcha/src/cli.py tests/python/test_background_style_collect.py tests/python/test_group1_query_audit.py tests/python/test_root_cli.py`
  - `uv run ruff check packages/sinan-captcha/src/materials/background_style.py packages/sinan-captcha/src/materials/background_style_cli.py tests/python/test_background_style_collect.py`
  - `git diff --check`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`

## 2026-04-11 补齐 `materials audit-group1-query` 候选图标下载进度日志

- 已更新：
  - `packages/sinan-captcha/src/materials/query_audit.py`
  - `tests/python/test_group1_query_audit.py`
  - `docs/02-user-guide/trainer-cli-reference.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 候选图标下载阶段新增模板级开始/结束日志、候选级开始/成功/失败日志
  - 下载源处理新增 URL 请求、下载成功字节数、源处理失败上下文
  - SVG 光栅化新增命令尝试、失败和成功日志，并为外部命令设置 30 秒超时
  - SVG 光栅化候选命令从 macOS `sips` / `qlmanage` 扩展到 `magick`、`rsvg-convert`、`inkscape`，改善 Windows 环境可用性
  - 用户指南已明确默认进度日志覆盖逐图识别、模板汇总、候选下载和 SVG 光栅化，`--quiet` 会关闭这些日志
- 已运行验证：
  - `uv run pytest tests/python/test_group1_query_audit.py -q`
  - `uv run python -m py_compile packages/sinan-captcha/src/materials/query_audit.py tests/python/test_group1_query_audit.py`
  - `git diff --check`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`
- 已知未处理：
  - `uv run ruff check packages/sinan-captcha/src/materials/query_audit.py tests/python/test_group1_query_audit.py` 暴露该模块既有 E501/F841/import 排序问题；本轮未扩大范围清理历史 lint 债务

## 2026-04-11 新增 `REQ-015`：solver 多输入与全格式图片兼容需求，并补齐任务拆解与文档同步

- 已更新：
  - `docs/04-project-development/02-discovery/input.md`
  - `docs/04-project-development/03-requirements/prd.md`
  - `docs/04-project-development/03-requirements/requirements-analysis.md`
  - `docs/04-project-development/03-requirements/requirements-verification.md`
  - `docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md`
  - `docs/04-project-development/10-traceability/requirements-matrix.md`
  - `docs/02-user-guide/solver-package-usage-guide.md`
  - `docs/02-user-guide/solver-package-function-reference.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 正式新增 `REQ-015`，要求 solver 支持本地路径、`bytes`、base64/data URI、`http(s)` URL 多输入形态
  - 明确“支持所有图片格式”的工程边界：以运行时解码器（Pillow）可稳定解码格式为准，并强制结构化错误返回
  - 在独立 solver 迁移计划中新增：
    - `TASK-SOLVER-MIG-013`（统一输入适配层）
    - `TASK-SOLVER-MIG-014`（URL 输入安全策略）
    - `TASK-SOLVER-MIG-015`（全格式回归与文档切换）
  - 用户文档已同步“当前已发布能力”与“新增需求目标口径”，避免把未发布能力写成既成事实
- 已运行验证：
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`

## 2026-04-11 清理 `docs/02-user-guide` 历史页，只保留最新使用方式

- 已更新：
  - `docs/index.md`
  - `docs/02-user-guide/index.md`
  - `docs/01-getting-started/index.md`
  - `docs/04-project-development/05-development-process/windows-environment-checklist.md`
  - `docs/04-project-development/05-development-process/generator-task-breakdown.md`
  - `docs/04-project-development/05-development-process/implementation-plan.md`
  - `docs/04-project-development/10-traceability/requirements-matrix.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 已删除：
  - `docs/02-user-guide/application-integration.md`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/group1-label-reference-and-review-guide.md`
  - `docs/02-user-guide/group1-material-category-backlog.md`
  - `docs/02-user-guide/how-to-check-cuda-version.md`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/02-user-guide/use-and-test-trained-models.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/use-solver-bundle.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/windows-quickstart.md`
- 当前已完成的目标：
  - 用户指南层面不再保留历史、迁移、过渡说明，仅保留可直接执行的最新流程
  - `docs/index.md` 的用户指南导航已收敛为 6 个最新页面
  - `docs/01-getting-started/index.md` 推荐阅读链路已改为最新页面
  - 开发过程文档和追踪矩阵中的旧用户指南链接已替换为最新页面
- 已运行验证：
  - `rg -n "<旧 02-user-guide 文件名模式>" docs`（无匹配）
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`

## 2026-04-11 重构 `docs/02-user-guide` 为生产级使用指南并完成多轮子 agent 审阅打磨

- 已更新：
  - `docs/index.md`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/complete-training-operations-guide.md`
  - `docs/02-user-guide/solver-package-usage-guide.md`
  - `docs/02-user-guide/generator-cli-reference.md`
  - `docs/02-user-guide/trainer-cli-reference.md`
  - `docs/02-user-guide/solver-bundle-cli-reference.md`
  - `docs/02-user-guide/solver-package-function-reference.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 用户指南目录重排为“使用者主线 + 训练者主线 + 历史/专题补充”，阅读路径明确
  - 新增完整训练操作指南，覆盖环境初始化、生成、训练、测试评估、reviewed 预标注、auto-train、bundle 验证
  - 新增生成器/训练器/solver bundle CLI 全量参考，参数与源码帮助输出对齐
  - 新增 `sinanz` 使用指南与函数参考，明确公开调用面、异常边界和输入类型口径
  - 基于子 agent 苛刻审阅完成多轮修订，修复执行阻断点（`exam prepare` 素材前置、`prelabel` 版本一致、`solve run` 路径解析说明等）
- 已运行验证：
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`

## 2026-04-11 调整 `group1 query audit` 默认 Ollama 超时并收口 template 汇总超时恢复

- 已更新：
  - `packages/sinan-captcha/src/materials/query_audit.py`
  - `tests/python/test_group1_query_audit.py`
  - `docs/02-user-guide/trainer-cli-reference.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `materials audit-group1-query` 的默认 `--timeout-seconds` 已从 `180` 秒调整为 `600` 秒
  - 逐图识别和最终 template 汇总阶段的 Ollama 网络/超时异常会被包装为 `QueryAuditClassificationError`，保留 request context
  - template 汇总超时会进入已有 fallback 模板计划路径，不再以裸 `TimeoutError` 直接中断整批流程
- 已运行验证：
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_group1_query_audit.py'`
  - `./.venv/bin/python -m py_compile packages/sinan-captcha/src/materials/query_audit.py packages/sinan-captcha/src/materials/query_audit_cli.py tests/python/test_group1_query_audit.py`
  - `git diff --check`

## 2026-04-11 删除旧 `sinan release` / `scripts/repo.py` 结构，统一到根目录 `repo` CLI

- 已更新：
  - `pyproject.toml`
  - `repo_cli.py`
  - `repo_release.py`
  - `repo_solver_export.py`
  - `repo_solver_asset_contract.py`
  - `README.md`
  - `docs/03-developer-guide/index.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
  - `tests/python/test_repo_cli.py`
  - `tests/python/test_release_service.py`
  - `tests/python/test_solver_asset_export_group2.py`
  - `tests/python/test_solver_asset_contract.py`
- 已删除：
  - `packages/sinan-captcha/src/release/`
  - `scripts/repo.py`
  - `tests/python/test_release_cli.py`
  - `tests/python/test_repo_script.py`
- 当前已完成的目标：
  - 仓库级构建、发版、资产导出和 Windows 打包已全部迁到根目录模块
  - `uv run repo ...` 已成为唯一正式仓库级 CLI
  - `sinan` CLI 已彻底去掉仓库级 `release` 边界
  - 当前发布入口已进一步拆分为 `publish-sinan` / `publish-solver`
  - 两个发布命令当前都只支持 PyPI，默认 token 读取顺序为 `PYPI_TOKEN -> UV_PUBLISH_TOKEN`
- 已运行验证：
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_root_cli.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_repo_cli.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_release_service.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_solver_asset_export_group2.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_solver_asset_contract.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_project_metadata.py'`
  - `git diff --check`

## 2026-04-11 基于最新 monorepo 结构重构 `docs/03-developer-guide` 并同步开发者阅读路径

- 已更新：
  - `docs/03-developer-guide/index.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `packages/solver/README.md`
  - `docs/index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 开发者指南已不再混用旧 `core/` 时代路径和新版 `src/` 直出布局
  - 已明确根 `uv workspace`、独立 Go 模块、`work_home/`、`.opencode/` 和 `packages/solver/resources/` 的真实边界
  - 已把开发者阅读路径重排为“接手 -> 边界 -> 日常开发 -> 构建发版 -> solver 集成”
  - 已补上“命令入口 -> 代码入口”的冷启动索引
  - 已补齐 `sinan release build-all`、`publish`、`export-solver-assets`、`stage-solver-assets`、`package-windows` 的当前行为说明
  - 已明确 `sinanz` 的函数式入口、`CaptchaSolver` facade 与公共异常 / 类型边界
  - 已修正 `packages/solver/README.md` 中对 solver 运行时依赖的过时表述
  - 已明确 `packages/solver/resources/` 属于发布前 staging 输入而不是普通缓存
- 待补充验证：
  - 冷启动读者审查与意见回收

## 2026-04-11 收口 `auto_train` 的 OpenCode 资源来源，并增加 pytest 结束后的脏数据自动清理

- 已更新：
  - `packages/sinan-captcha/src/auto_train/opencode_assets.py`
  - `scripts/repo.py`
  - `tests/python/conftest.py`
  - `tests/python/test_auto_train_opencode_assets.py`
  - `tests/python/test_repo_script.py`
  - `tests/python/test_release_service.py`
  - `tests/python/test_test_artifact_cleanup.py`
  - `README.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 根目录 `.opencode/` 已固定为唯一受 Git 管理的 OpenCode command / skill 事实源
  - `packages/sinan-captcha/src/auto_train/resources/opencode` 不再作为常驻源码目录存在，只在 Python 包构建时临时 stage
  - wheel / sdist 仍会带上 OpenCode 资源，安装包场景不受影响
  - pytest 结束后会自动清理常见 Python 测试和构建脏数据，避免 `__pycache__`、`build/`、`*.egg-info`、工具缓存继续留在工作区
- 已运行验证：
  - `uv run pytest tests/python/test_auto_train_opencode_assets.py tests/python/test_setup_train.py tests/python/test_release_service.py tests/python/test_repo_script.py tests/python/test_auto_train_opencode_commands.py tests/python/test_auto_train_opencode_skills.py -q`
  - `./.venv/bin/python scripts/repo.py build sinan-captcha`

## 2026-04-11 将 `packages/sinan-captcha` 收口为真正的 `src/` 直出布局，并重划基础 CLI / 训练依赖边界

- 已更新：
  - `packages/sinan-captcha/pyproject.toml`
  - `pyproject.toml`
  - `packages/sinan-captcha/src/**`
  - `tests/python/test_project_metadata.py`
  - `tests/python/test_root_cli.py`
  - `tests/python/test_release_service.py`
  - `README.md`
  - `packages/sinan-captcha/README.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `scripts/README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 已删除：
  - `packages/sinan-captcha/src/__init__.py`
  - `packages/sinan-captcha/src/py.typed`
- 当前已完成的目标：
  - `packages/sinan-captcha` 已不再保留 `core/` 包前缀，源码现在直接落在 `src/auto_train`、`src/train`、`src/solve` 等功能包
  - `sinan` CLI 入口已改为 `cli:main`
  - 根 workspace 默认依赖已回到基础 `sinan-captcha`，训练栈改为显式 `uv sync --group train`
  - `sinan-captcha[train]` 已收紧为非 CUDA 专属训练依赖；训练目录继续由 `setup-train` 按 backend 单独安装 `torch/torchvision/torchaudio`
  - 根目录 `scripts/repo.py build ...` 与 `sinan release build-*` 当前已改为直接调用 Python 子项目的 `setuptools` build backend；Go 构建默认把 `GOCACHE` 写到 `work_home/.cache/go/`
  - 用户指南、开发者指南和设计基线中与 `core/`、`materials/` 相关的当前路径说明已同步到 `packages/.../src` 与 `work_home/...`

## 2026-04-11 收口 `group1` reviewed / prelabel / auto-train` 的实例匹配合同

- 已更新：
  - `packages/sinan-captcha/core/dataset/validation.py`
  - `packages/sinan-captcha/core/exam/service.py`
  - `packages/sinan-captcha/core/train/prelabel.py`
  - `packages/sinan-captcha/core/train/group1/cli.py`
  - `packages/sinan-captcha/core/evaluate/service.py`
  - `packages/sinan-captcha/core/auto_train/business_eval.py`
  - `packages/sinan-captcha/core/auto_train/runners/test.py`
  - `packages/sinan-captcha/core/auto_train/runners/train.py`
  - `tests/python/test_group1_instance_contracts.py`
  - `tests/python/test_exam_service.py`
  - `tests/python/test_train_prelabel_service.py`
  - `tests/python/test_evaluate_service.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `tests/python/test_auto_train_runners.py`
  - `README.md`
  - `docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `group1 reviewed` 正式合同已切到 `query_item + NN`
  - `export-reviewed --task group1` 现正式输出 `query_items / scene_targets` 的 `order + bbox + center`
  - 导出器保留对 legacy `query=<class>` / `scene=NN|class` 的兼容读取，并将其降级为可选 `class_guess`
  - `train group1 prelabel` 与 `prelabel-query-dir` 已统一写新 LabelMe 合同，并把旧类别提示落到 `shape.flags.class_guess`
  - `group1` 评估与 reviewed business gate 已支持稀疏 reviewed 答案按 `order + center` 判卷
  - `auto-train train/test/business-eval` 已把 `icon-embedder` 纳入正式 checkpoint 生命周期与 model-test 请求
- 当前尚未完成：
  - `group1` reviewed 用户文档的全量收口
  - `auto-train controller/judge` 对新 matcher 失败模式的细粒度归因
- 已运行验证：
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_group1_instance_contracts.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_exam_service.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_train_prelabel_service.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_evaluate_service.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_auto_train_business_eval.py'`
  - `./.venv/bin/python -m unittest discover -s tests/python -p 'test_auto_train_runners.py'`

## 2026-04-11 新增 `group1 prelabel-vlm`：本地 Ollama 多模态模型预标注入口

- 已更新：
  - `packages/sinan-captcha/src/train/prelabel.py`
  - `packages/sinan-captcha/src/train/group1/cli.py`
  - `tests/python/test_train_prelabel_service.py`
  - `tests/python/test_training_jobs.py`
  - `README.md`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `docs/04-project-development/04-design/group1-instance-matching-refactor.md`
  - `docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `uv run sinan train group1 prelabel-vlm` 可直接扫描同名 `query + scene|scence` 图片对
  - 该命令会调用本地 Ollama 多模态模型，并强制其返回 `query_items / scene_targets` 的严格 JSON
  - 结果会转换为 `reviewed/query/*.json` 与 `reviewed/scene/*.json`，供 X-AnyLabeling 人工复核
  - 中间产物会写入 `<pair-root>/.sinan/prelabel/group1/vlm/`：
    - `source.jsonl`
    - `labels.jsonl`
    - `trace.jsonl`
    - `summary.json`
  - `query_items` 会按框中心自动重排为从左到右的 `order=1..N`
  - `scene_targets` 会按模型返回顺序号归一化，并兼容缺失或重复顺序号
- 已运行验证：
  - `uv run pytest tests/python/test_train_prelabel_service.py tests/python/test_training_jobs.py -q`
  - `uv run pytest tests/python/test_root_cli.py -q`

## 2026-04-11 为 `group1 prelabel-vlm` 增加实时日志输出

- 已更新：
  - `packages/sinan-captcha/src/train/prelabel.py`
  - `tests/python/test_train_prelabel_service.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `uv run sinan train group1 prelabel-vlm ...` 执行时不再静默等待
  - 命令会持续向 `stderr` 打印：
    - 当前阶段
    - sample_id
    - prompt 内容
    - 发送请求到 Ollama 的节点
    - Ollama 原始响应 payload
    - 提取后的模型文本内容
    - 归一化后的目标数量
  - 最终结构化结果仍只写到 `stdout`，不会污染原有 JSON 结果输出
- 已运行验证：
  - `uv run pytest tests/python/test_train_prelabel_service.py tests/python/test_training_jobs.py -q`
  - `uv run pytest tests/python/test_root_cli.py -q`

## 2026-04-11 修复 `group1 query audit` 的部分落盘与失败重试

- 已更新：
  - `packages/sinan-captcha/core/materials/query_audit.py`
  - `packages/sinan-captcha/core/materials/query_audit_cli.py`
  - `tests/python/test_group1_query_audit.py`
  - `docs/02-user-guide/group1-material-category-backlog.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `materials audit-group1-query` 现在即使遇到部分图片审计失败，也会先基于成功图片生成 `tpl_* / var_*` 的 `group1` 素材包
  - CLI 已新增 `--retry-from-report`，可读取旧 `group1-query-audit.jsonl`
  - 重试模式会复用旧报告中的成功行，只重新审计失败图片，再用合并后的成功结果重建素材包与 manifest
- 已运行验证：
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_group1_query_audit.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_root_cli.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m py_compile packages/sinan-captcha/core/materials/query_audit.py packages/sinan-captcha/core/materials/query_audit_cli.py tests/python/test_group1_query_audit.py`

## 2026-04-11 落地 monorepo 目录与 work_home 本地运行目录

- 已更新：
  - `pyproject.toml`
  - `.gitignore`
  - `README.md`
  - `scripts/repo.py`
  - `scripts/crawl/ctrip_login.py`
  - `scripts/eval_solver_group2_reviewed.py`
  - `scripts/download_group1_candidate_icons.py`
  - `scripts/build_group1_generator_icon_pack.py`
  - `scripts/organize_group1_query_icons.py`
  - `scripts/organize_group2_gap_shapes.py`
  - `packages/sinan-captcha/pyproject.toml`
  - `packages/sinan-captcha/core/common/paths.py`
  - `packages/sinan-captcha/core/project_metadata.py`
  - `packages/sinan-captcha/core/release/service.py`
  - `packages/sinan-captcha/core/materials/query_audit.py`
  - `packages/sinan-captcha/core/materials/query_audit_cli.py`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 已删除：
  - `packages/solver/uv.lock`
- 当前已完成的目标：
  - 仓库源码目录已切到 `packages/sinan-captcha + packages/generator + packages/solver`
  - 根目录已切成 `uv workspace`，并统一使用根目录 `uv.lock`
  - 根目录新增 `scripts/repo.py` 作为 monorepo 薄包装构建入口
  - 运行期默认目录已统一切到 `work_home/materials`、`work_home/reports`、`work_home/.cache`
  - `materials audit-group1-query`、训练 CLI、release 构建与开发脚本默认路径已同步到 `work_home`
- 已运行验证：
  - `uv lock`
  - `UV_CACHE_DIR=/tmp/uv-cache GOCACHE=/tmp/go-cache ./.venv/bin/python scripts/repo.py build all`（沙箱外）
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_project_metadata.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_setup_train.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_ctrip_login_script.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_group1_query_audit.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_release_cli.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_release_service.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_root_cli.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_training_jobs.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_prediction_and_model_test.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_build_group1_generator_icon_pack_script.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_download_group1_candidate_icons_script.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_organize_group1_query_icons_script.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_organize_group2_gap_shapes_script.py'`
  - `env PYTHONPATH=packages/sinan-captcha ./.venv/bin/python -m unittest discover -s tests/python -p 'test_repo_script.py'`

## 2026-04-11 衔接 `group1` icon embedder 到 matcher、predict/test 与 solver bundle

- 已更新：
  - `core/inference/service.py`
  - `core/train/group1/embedder.py`
  - `core/train/group1/service.py`
  - `core/train/group1/runner.py`
  - `core/predict/cli.py`
  - `core/modeltest/cli.py`
  - `core/modeltest/service.py`
  - `core/solve/bundle.py`
  - `core/solve/service.py`
  - `tests/python/test_inference_service.py`
  - `tests/python/test_group1_embedder.py`
  - `tests/python/test_training_jobs.py`
  - `tests/python/test_prediction_and_model_test.py`
  - `tests/python/test_solve_service.py`
  - `README.md`
  - `docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `map_group1_instances(...)` 已支持注入 embedding provider
  - `IconEmbedderRuntime` 已能加载 `icon-embedder` checkpoint 并对 bbox crop 生成 embedding
  - `uv run sinan predict group1` 默认带上 `--embedder-model runs/group1/<train-name>/icon-embedder/weights/best.pt`
  - `uv run sinan test group1` 可把 `icon-embedder` 权重透传给预测链路
  - solver bundle 已复制并声明 `models/group1/icon-embedder/model.pt`
  - `UnifiedSolverService` 已能从 bundle 加载 `icon-embedder` 并传给 matcher
- 当前尚未完成：
  - group1 正式 ONNX 导出
  - solver 包内 `sinanz` group1 ONNX Runtime 编排
  - 真实大批量 recall 阈值校准
- 已运行验证：
  - `.venv/bin/python -m py_compile core/inference/service.py core/train/group1/embedder.py core/train/group1/service.py core/train/group1/runner.py core/predict/cli.py core/modeltest/service.py core/modeltest/cli.py core/solve/bundle.py core/solve/service.py tests/python/test_inference_service.py tests/python/test_group1_embedder.py tests/python/test_training_jobs.py tests/python/test_prediction_and_model_test.py tests/python/test_solve_service.py`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_inference_service.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_group1_embedder.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_solve_service.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_prediction_and_model_test.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_training_jobs.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_root_cli.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_auto_train_runners.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_train_prelabel_service.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_solver_asset_contract.py'`
  - `UV_CACHE_DIR=/tmp/uv-cache PYTHONPYCACHEPREFIX=/tmp/pycache uv run python -m unittest discover -s tests/python -p 'test_*.py'`（沙箱外，283 tests）
- 验证限制：
  - 沙箱内 `uv run` 仍会触发 macOS `system-configuration` NULL object panic
  - 当前 `.venv` 中没有 `ruff`，`ruff check/format --check` 未能执行

## 2026-04-11 落地 `group1` 可训练 icon embedder 第一切片

- 已更新：
  - `core/train/group1/embedder.py`
  - `core/train/group1/service.py`
  - `core/train/group1/cli.py`
  - `core/train/group1/runner.py`
  - `core/cli.py`
  - `tests/python/test_group1_embedder.py`
  - `tests/python/test_training_jobs.py`
  - `README.md`
  - `docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 新增 PyTorch `IconEmbedder`，输出 L2-normalized icon embeddings
  - 新增 `Group1TripletDataset`，直接消费 generator 的 `embedding/triplets.jsonl`
  - 新增 `train_icon_embedder(...)`，训练后写出 `best.pt / last.pt / summary.json`
  - 新增 `evaluate_retrieval(...)`，输出 `embedding_recall_at_1 / embedding_recall_at_3`
  - `uv run sinan train group1 --component icon-embedder ...` 已成为正式训练入口
- 当前尚未完成：
  - matcher 推理时加载训练后的 embedder checkpoint
  - 大规模训练数据上的 recall 阈值校准
  - group1 ONNX/export runtime 编排
- 已运行验证：
  - `UV_CACHE_DIR=/tmp/uv-cache PYTHONPYCACHEPREFIX=/tmp/pycache uv run python -m unittest discover -s tests/python -p 'test_group1_embedder.py'`（沙箱外）
  - `UV_CACHE_DIR=/tmp/uv-cache PYTHONPYCACHEPREFIX=/tmp/pycache uv run python -m unittest discover -s tests/python -p 'test_training_jobs.py'`（沙箱外）
  - `UV_CACHE_DIR=/tmp/uv-cache PYTHONPYCACHEPREFIX=/tmp/pycache uv run python -m unittest discover -s tests/python -p 'test_prediction_and_model_test.py'`（沙箱外）
  - `UV_CACHE_DIR=/tmp/uv-cache PYTHONPYCACHEPREFIX=/tmp/pycache uv run python -m unittest discover -s tests/python -p 'test_solve_service.py'`（沙箱外）
  - `UV_CACHE_DIR=/tmp/uv-cache PYTHONPYCACHEPREFIX=/tmp/pycache uv run python -m unittest discover -s tests/python -p 'test_root_cli.py'`（沙箱外）
  - `UV_CACHE_DIR=/tmp/uv-cache PYTHONPYCACHEPREFIX=/tmp/pycache uv run python -m unittest discover -s tests/python -p 'test_auto_train_runners.py'`（沙箱外）
  - `UV_CACHE_DIR=/tmp/uv-cache PYTHONPYCACHEPREFIX=/tmp/pycache uv run python -m unittest discover -s tests/python -p 'test_train_prelabel_service.py'`（沙箱外）
  - `.venv/bin/python -m py_compile core/train/group1/embedder.py core/train/group1/service.py core/train/group1/cli.py core/train/group1/runner.py core/inference/service.py core/solve/service.py tests/python/test_group1_embedder.py tests/python/test_training_jobs.py tests/python/test_prediction_and_model_test.py tests/python/test_solve_service.py tests/python/test_root_cli.py`
- 验证限制：
  - 当前 `.venv` 中没有 `ruff`，`ruff check/format --check` 未能执行

## 2026-04-11 落地 `group1` matcher 与 unified solve 的第一轮 cutover

- 已更新：
  - `core/inference/service.py`
  - `core/train/group1/runner.py`
  - `core/solve/service.py`
  - `core/solve/bundle.py`
  - `tests/python/test_inference_service.py`
  - `tests/python/test_training_jobs.py`
  - `tests/python/test_solve_service.py`
  - `docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `group1` 已新增 `map_group1_instances()`，能够执行基于 crop 相似度的全局匹配与歧义判定
  - `core.train.group1.runner predict` 在 `sinan.group1.instance_matching.v1` 上已切到实例匹配主线
  - 预测 `labels.jsonl` 的 `scene_targets` 在实例匹配模式下已优先输出 `asset_id/template_id/variant_id`
  - `core.solve.service` 的 `group1` 统一求解入口已改走实例匹配器
  - solver bundle 新 manifest 默认写出 `matcher.strategy = global_assignment_match_v1`，同时保留历史 bundle 读取兼容
- 当前尚未完成：
  - 可训练 `icon embedder` 与 metric-learning 训练入口
  - embedding recall 校准与 `business_eval` 新归因
  - group1 solver ONNX 导出与 runtime 编排
- 已运行验证：
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile core/inference/service.py core/train/group1/runner.py core/solve/service.py core/solve/bundle.py tests/python/test_inference_service.py tests/python/test_training_jobs.py tests/python/test_solve_service.py`
  - `PYTHONPATH=/tmp/pyshim PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.python.test_inference_service`
  - `PYTHONPATH=/tmp/pyshim PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.python.test_training_jobs.TrainingJobTests.test_group1_instance_matching_prediction_row_copies_query_identity tests.python.test_training_jobs.TrainingJobTests.test_group1_dataset_loader_accepts_instance_matching_contract`
  - `PYTHONPATH=/tmp/pyshim PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.python.test_solve_service`
  - `PYTHONPATH=/tmp/pyshim PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.python.test_prediction_and_model_test`
  - `PYTHONPATH=/tmp/pyshim PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.python.test_root_cli`

## 2026-04-11 落地 `group1` Python instance-matching cutover 第一阶段

- 已更新：
  - `core/train/group1/dataset.py`
  - `core/train/group1/runner.py`
  - `tests/python/test_training_jobs.py`
  - `tests/python/test_prediction_and_model_test.py`
  - `tests/python/test_auto_train_runners.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - Python `group1 dataset loader` 已接受新合同：
    - `sinan.group1.instance_matching.v1`
    - `proposal_detector`
    - `embedding`
    - `eval`
  - `core.train.group1.runner train` 现在会优先消费 `proposal-yolo/dataset.yaml`
  - 当 `dataset.json` 未提供 `query_parser` 数据集时，显式训练 `query-parser` 会直接报错，避免偷偷回退到旧目录
  - `auto-train` 与 `modeltest` 相关测试 fixture 已切到新的 `dataset.json` 结构
- 当前尚未完成：
  - `query splitter / embedder / matcher` 的真实训练与推理 cutover
  - `group1 predict / test / prelabel` 的用户文案与组件命名收口
- 已运行验证：
  - `uv run python -m unittest discover -s tests/python -p 'test_training_jobs.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_prediction_and_model_test.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_auto_train_runners.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_auto_train_controller.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_root_cli.py'`

## 2026-04-11 切换 generator `group1` 导出为纯 instance-matching 目录

- 已更新：
  - `generator/internal/dataset/build.go`
  - `generator/internal/app/make_dataset.go`
  - `generator/internal/app/make_dataset_test.go`
  - `README.md`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/04-project-development/05-development-process/generator-task-breakdown.md`
  - `docs/04-project-development/05-development-process/data-export-auto-labeling-checklist.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/tech-stack.summary.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `sinan-generator make-dataset --task group1` 现在只写出：
    - `proposal-yolo/`
    - `embedding/`
    - `eval/`
    - `splits/`
    - `dataset.json`
  - `proposal-yolo/` 已改为单类别 `icon_object`
  - `embedding/` 已产出：
    - `queries/`
    - `candidates/`
    - `pairs.jsonl`
    - `triplets.jsonl`
  - `eval/` 已产出：
    - `query/`
    - `scene/`
    - `labels.jsonl`
  - generator 不再写出 `scene-yolo/`、`query-yolo/` 兼容目录
- 已运行验证：
  - `env GOCACHE=/tmp/go-cache go test ./internal/app ./cmd/sinan-generator`（cwd=`generator/`)

## 2026-04-11 冻结 `group1` 新素材库规范并切换 generator 到 `template/variant` 协议

- 已更新：
  - `docs/04-project-development/04-design/group1-instance-matching-refactor.md`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/04-project-development/05-development-process/generator-task-breakdown.md`
  - `docs/02-user-guide/index.md`
  - `generator/internal/material/catalog.go`
  - `generator/internal/material/validate.go`
  - `generator/internal/sampler/sample.go`
  - `generator/internal/materialset/store.go`
  - `generator/cmd/sinan-generator/main.go`
  - `generator/cmd/sinan-generator/main_test.go`
  - `generator/internal/material/validate_test.go`
  - `generator/internal/materialset/store_test.go`
  - `generator/internal/app/make_dataset_test.go`
  - `generator/internal/qa/check_test.go`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 已删除：
  - `generator/internal/materialset/merge.go`
  - `generator/internal/materialset/merge_test.go`
- 当前已完成的目标：
  - 当前正式 `group1` 素材库规范已冻结为：
    - `schema_version: 3`
    - `manifests/group1.templates.yaml`
    - `group1/icons/<template_id>/<variant_id>.png`
  - 当前 generator 的 group1 材料校验、目录检测、catalog 加载与抽样已全部改为围绕：
    - `template_id`
    - `variant_id`
    - `asset_id`
  - 当前 `sinan-generator materials merge` 旧原料合并入口已删除，不再继续保留旧类名素材流
  - 当前 `group1.classes.yaml` 和 `group1/icons/<class_name>/` 在 generator 代码中已无残留引用
- 已运行验证：
  - `env GOCACHE=/tmp/go-cache go test ./internal/material ./internal/materialset ./internal/sampler ./internal/qa ./internal/app ./cmd/sinan-generator ./internal/render ./internal/truth`（cwd=`generator/`）

## 2026-04-11 落地 `group1` 实例匹配重构第一切片：新数据契约与 generator 身份字段

- 已更新：
  - `core/dataset/contracts.py`
  - `core/dataset/validation.py`
  - `generator/internal/export/manifest.go`
  - `generator/internal/sampler/sample.go`
  - `generator/internal/render/render.go`
  - `generator/internal/truth/check.go`
  - `generator/internal/app/make_dataset_test.go`
  - `tests/python/test_group1_instance_contracts.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前 `group1` Python 契约层已新增实例身份字段：
    - `query_items`
    - `asset_id`
    - `template_id`
    - `variant_id`
  - 当前 `validate_group1_row()` 已只保留新 schema：
    - `query_items + scene_targets + asset_id/template_id/variant_id`
    - reviewed 稀疏答案允许 `order + bbox + center`
    - 旧 `query_targets + class/class_id` 已彻底删除
  - 当前 generator 的 `group1` 原始批次与 split JSONL 已改为输出：
    - 顶层 `query_items`
    - 对象级 `asset_id / template_id / variant_id`
  - 当前 generator 会基于素材路径生成稳定的临时身份 token，并在 click 真值校验中优先按实例身份对齐 query/scene
  - 当前这一步只完成了数据合同切换的第一层地基，还未完成：
    - `proposal-yolo / embedding / eval` 目录切换
    - `dataset.json` 新格式切换
    - 旧 `group1` 训练/runtime 正式删除
- 已运行验证：
  - `env PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests/python -p 'test_group1_instance_contracts.py'`
  - `env PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests/python -p 'test_autolabel_service.py'`
  - `env PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests/python -p 'test_evaluate_service.py'`
  - `env PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests/python -p 'test_prediction_and_model_test.py'`
  - `env PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests/python -p 'test_auto_train_runners.py'`
  - `env PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests/python -p 'test_train_prelabel_service.py'`
  - `env GOCACHE=/tmp/go-cache go test ./internal/truth ./internal/qa ./internal/render ./internal/app`（cwd=`generator/`）

## 2026-04-11 冻结 `group1` 实例匹配重构的需求、设计与任务基线

- 已更新：
  - `docs/04-project-development/02-discovery/brainstorm-record.md`
  - `docs/04-project-development/03-requirements/prd.md`
  - `docs/04-project-development/03-requirements/requirements-analysis.md`
  - `docs/04-project-development/03-requirements/requirements-verification.md`
  - `docs/04-project-development/04-design/technical-selection.md`
  - `docs/04-project-development/04-design/system-architecture.md`
  - `docs/04-project-development/04-design/module-boundaries.md`
  - `docs/04-project-development/04-design/generator-productization.md`
  - `docs/04-project-development/04-design/graphic-click-generator-design.md`
  - `docs/04-project-development/04-design/index.md`
  - `docs/04-project-development/04-design/group1-instance-matching-refactor.md`
  - `docs/04-project-development/05-development-process/implementation-plan.md`
  - `docs/04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md`
  - `docs/04-project-development/10-traceability/requirements-matrix.md`
  - `docs/index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前正式需求层已把 `group1` 从闭集类名检测改为实例匹配求解
  - 当前正式 PRD 已新增：
    - `REQ-014`：`group1` 正式方案切换与旧方案清理
    - `NFR-010`：单一正式方案与代码清洁性
  - 当前正式设计主线已收口为：
    - `query splitter`
    - `proposal detector`
    - `icon embedder`
    - `matcher`
  - 当前已新增专项设计文档：
    - `group1-instance-matching-refactor.md`
  - 当前已新增专项任务拆解：
    - `TASK-G1-REF-001` 到 `TASK-G1-REF-012`
  - 当前正式文档已明确：
    - `group1` 素材库以 `asset_id / template_id / variant_id` 为主
    - 商业试卷和人工审核以“顺序 + 框”为主，不再以类名表为正式合同
    - 新方案 cutover 后必须删除旧闭集类名正式实现，不保留长期双轨
- 已运行验证：
  - 当前未运行自动化代码测试；本轮变更仅涉及文档与记忆层同步

## 2026-04-11 收口 `group1` 分阶段训练与最终位置挑选验证工作流

- 已更新：
  - `core/train/group1/service.py`
  - `core/train/group1/runner.py`
  - `core/train/group1/cli.py`
  - `core/modeltest/service.py`
  - `core/cli.py`
  - `tests/python/test_training_jobs.py`
  - `tests/python/test_prediction_and_model_test.py`
  - `README.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前 `group1` 已支持显式按组件训练：
    - `uv run sinan train group1 --component query-parser ...`
    - `uv run sinan train group1 --component proposal-detector ...`
  - 当前默认 `uv run sinan train group1 ...` 仍保持兼容：
    - 顺序训练 `query-parser + proposal-detector`
  - 当前生成器继续输出同一份 `group1 pipeline dataset`，训练侧按组件复用其中的：
    - `query-yolo/`
    - `scene-yolo/`
  - 当前 `uv run sinan test group1 ...` 的中文报告已明确写成：
    - 最终位置挑选验证
    - 即 `query-parser + proposal-detector + matcher` 整链路
- 已运行验证：
  - `uv run python -m unittest discover -s tests/python -p 'test_training_jobs.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_prediction_and_model_test.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_root_cli.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_auto_train_runners.py'`

## 2026-04-11 收口 `group1` proposal-detector 正式命名与默认路径

- 已更新：
  - `core/train/group1/service.py`
  - `core/train/group1/cli.py`
  - `core/train/group1/runner.py`
  - `core/predict/cli.py`
  - `core/modeltest/cli.py`
  - `core/modeltest/service.py`
  - `core/train/prelabel.py`
  - `core/auto_train/runners/train.py`
  - `core/auto_train/runners/test.py`
  - `core/auto_train/business_eval.py`
  - `core/solve/bundle.py`
  - `core/solve/service.py`
  - `core/release/solver_asset_contract.py`
  - `tests/python/test_training_jobs.py`
  - `tests/python/test_prediction_and_model_test.py`
  - `tests/python/test_auto_train_runners.py`
  - `tests/python/test_train_prelabel_service.py`
  - `tests/python/test_solve_service.py`
  - `tests/python/test_solver_asset_contract.py`
  - `README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/tech-stack.summary.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前 `group1` 训练、预测、模型测试、预标注和 solver bundle 的正式入口已统一到 `proposal-detector`
  - 当前默认权重目录与 dry-run 命令已切到：
    - `runs/group1/<train-name>/proposal-detector/weights/*.pt`
    - `--proposal-model`
    - `--component proposal-detector`
  - 当前旧 `scene-detector` / `--scene-model` 兼容别名已删除：
    - CLI 不再解析旧参数
    - solver bundle 不再回退旧目录或旧 manifest key
  - 当前 solver ONNX 资产合同也已切到：
    - `click_proposal_detector`
    - `proposal_detector`
  - 当前旧 `class_names.json` 占位文件也已删除，只保留 `click_matcher.json`
  - 当前 `group1 modeltest` 中文报告口径已同步为：
    - `query parser + proposal detector + matcher`
- 已运行验证：
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile core/train/group1/service.py core/train/group1/cli.py core/train/group1/runner.py core/predict/cli.py core/modeltest/cli.py core/modeltest/service.py core/train/prelabel.py core/auto_train/runners/train.py core/auto_train/runners/test.py core/auto_train/business_eval.py core/solve/bundle.py core/solve/service.py core/release/solver_asset_contract.py tests/python/test_training_jobs.py tests/python/test_prediction_and_model_test.py tests/python/test_auto_train_runners.py tests/python/test_train_prelabel_service.py tests/python/test_solve_service.py tests/python/test_solver_asset_contract.py`
  - `uv run python -m unittest discover -s tests/python -p 'test_training_jobs.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_prediction_and_model_test.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_auto_train_runners.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_train_prelabel_service.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_solve_service.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_solver_asset_contract.py'`
  - `uv run python -m unittest discover -s tests/python -p 'test_root_cli.py'`

## 2026-04-10 新增 `uv run sinan train group1 prelabel-query-dir`：对单独一批 query 图片执行本地模型预标注

- 已更新：
  - `core/train/group1/cli.py`
  - `core/train/prelabel.py`
  - `tests/python/test_train_prelabel_service.py`
  - `tests/python/test_training_jobs.py`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前新增子命令：
    - `uv run sinan train group1 prelabel-query-dir --input-dir <query-dir> --train-name <run>`
  - 当前该命令使用本地 `query-parser` 权重，对 query 目录中的每张图片直接写同名 `json` 标注文件
  - 当前额外汇总产物会写到：
    - `<input-dir>/.sinan/prelabel/group1/query/<run-name>/labels.jsonl`
    - `<input-dir>/.sinan/prelabel/group1/query/<run-name>/summary.json`
  - 当前如果目录里已存在人工 `json`，默认会拒绝覆盖；只有显式加 `--overwrite` 才会重跑
  - 当前 `--dry-run` 会输出解析后的路径计划，便于先确认输入目录、权重路径和输出目录
- 已运行验证：
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_train_prelabel_service.py'`
  - `.venv/bin/python -m unittest discover -s tests/python -p 'test_training_jobs.py'`

## 2026-04-10 调整 `scripts/crawl/ctrip_login.py`：`测试滑动` 改为按 `verify_jigsaw` 响应判定成败

- 已更新：
  - `scripts/crawl/ctrip_login.py`
  - `tests/python/test_ctrip_login_script.py`
  - `scripts/README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `4=测试滑动` 模式当前会等待：
    - `/captcha/v4/verify_jigsaw`
  - 当前会以业务字段而不是 HTTP 200 或 DOM 切换来判断是否通过：
    - `risk_info.process_type = "NONE"` 且 `risk_level = 0` 视为成功
    - `risk_info.process_type = "JIGSAW"` 视为失败
  - 当前失败时会把 `verify_jigsaw` 摘要并入失败输出，同时保存：
    - `failure.png`
  - 当前成功时如果前端尚未切到点选模式，也只作为提示打印，不再覆盖服务端通过结论
- 已运行验证：
  - `uv run python -m unittest discover -s tests/python -p 'test_ctrip_login_script.py'`

## 2026-04-10 新增 `sinan materials audit-group1-query`：用本地 Ollama 批量审查 `group1 query` 并回写素材类别 backlog

- 已更新：
  - `core/cli.py`
  - `core/materials/query_audit.py`
  - `core/materials/query_audit_cli.py`
  - `tests/python/test_group1_query_audit.py`
  - `tests/python/test_root_cli.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 新增根命令：
    - `uv run sinan materials audit-group1-query`
  - 当前默认 query 输入目录已固定为：
    - `materials/test/group1/query`
  - 当前命令必须在仓库根目录执行；若在 `solver/` 等子目录运行，会直接返回清晰错误提示，不再自动向上寻找 repo root
  - 当前命令默认会把执行进度打印到终端，覆盖：
    - 当前处理图片
    - 发送给 Ollama 的请求摘要与提示词
    - 大模型原始响应
    - 每张图的解析结果或错误
  - 当前可通过：
    - `--quiet`
    - 关闭终端逐图日志
  - 当前命令会顺序扫描 query 图片、调用本地 Ollama 多模态模型，并写出：
    - `reports/materials/group1-query-audit.jsonl`
    - `reports/materials/group1-query-audit-trace.jsonl`
    - `docs/02-user-guide/group1-material-category-backlog.md` 的自动映射区
  - 当前 `group1-query-audit-trace.jsonl` 会为每张 query 图片保留：
    - 原始模型输出文本
    - 解析后的类别序列
    - 原始 API 响应体
    - 错误信息（如果解析失败）
  - 当前如果模型判断为未知素材类，会把建议类名、中文名、图形描述和示例图片追加到 backlog 的“待补齐的新类别”
  - 当前已支持：
    - `--model`
    - `--query-dir`
    - `--manifest`
    - `--backlog-doc`
    - `--output-jsonl`
    - `--ollama-url`
    - `--timeout-seconds`
    - `--limit`
    - `--dry-run`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_group1_query_audit tests.python.test_root_cli`

## 2026-04-11 重构 `sinan materials audit-group1-query`：直接生成 `tpl_* / var_*` 的 `group1` 模板素材包

- 已更新：
  - `core/cli.py`
  - `core/materials/group1_query_icons.py`
  - `core/materials/query_audit.py`
  - `core/materials/query_audit_cli.py`
  - `tests/python/test_group1_query_audit.py`
  - `docs/02-user-guide/group1-material-category-backlog.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 保留原命令名：
    - `uv run sinan materials audit-group1-query`
  - 但命令语义已整体切换为：
    - 从 `materials/validation/group1/query` 扫描 query 图片
    - 本地切分与聚类图标实例
    - 逐张把 query 图片发送给本地 Ollama 多模态模型
    - 为每个图标生成 `tpl_<snake_case>` 格式的 `template_id`
    - 聚合全部 query 结果后再次调用 Ollama 补全模板元数据与下载候选
    - 自动写出 `group1/icons/<template_id>/<variant_id>.png`
    - 自动写出 `manifests/group1.templates.yaml`
  - 当前旧行为已删除：
    - 不再读取 `group1.classes.yaml`
    - 不再使用 `icon_*` 类名作为正式输出
    - 不再回写 `docs/02-user-guide/group1-material-category-backlog.md` 的自动映射区
    - 不再保留 `--manifest` / `--backlog-doc` 旧参数
  - 当前命令新增或切换的关键参数：
    - `--output-root`
    - `--template-report-json`
    - `--cache-dir`
    - `--min-variants-per-template`
    - `--overwrite`
  - 当前命令默认输出：
    - `reports/materials/group1-query-audit.jsonl`
    - `reports/materials/group1-query-audit-trace.jsonl`
    - `reports/materials/group1-query-audit-templates.json`
    - `materials/incoming/group1_icon_pack/manifests/materials.yaml`
    - `materials/incoming/group1_icon_pack/manifests/group1.templates.yaml`
- 已运行验证：
  - `env PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests/python -p 'test_group1_query_audit.py'`
  - `env PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests/python -p 'test_root_cli.py'`

## 2026-04-10 统一 `group2` 重复阈值语义到共享常量

- 已更新：
  - `core/group2_semantics.py`
  - `core/train/group2/runner.py`
  - `core/modeltest/service.py`
  - `core/auto_train/summary.py`
  - `core/auto_train/policies.py`
  - `core/auto_train/controller.py`
  - `tests/python/test_auto_train_summary.py`
  - `tests/python/test_auto_train_policies.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 把 `group2` 离线点位命中容差 `12px` 从分散字面量收口到：
    - `GROUP2_OFFLINE_POINT_HIT_TOLERANCE_PX`
    - `GROUP2_LOCALIZATION_ALERT_CENTER_ERROR_PX`
  - 把 `group2` summary / policy / modeltest 中重复出现的点位命中率与 IoU 阈值收口到 `core/group2_semantics.py`
  - 让训练评估、失败模式判定、自动训练决策、模型测试报告使用同一份常量来源
  - 新增边界测试，明确保证：
    - `mean_center_error_px == 12.0` 时不会被误判为 `center_offset`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_training_jobs tests.python.test_auto_train_runners tests.python.test_auto_train_business_eval tests.python.test_auto_train_controller tests.python.test_auto_train_summary tests.python.test_auto_train_policies tests.python.test_prediction_and_model_test`

## 2026-04-10 清理 `group2` 训练链路中的重复 checkpoint 回退与重复 dataset config 解析

- 已更新：
  - `core/train/base.py`
  - `core/auto_train/runners/train.py`
  - `core/auto_train/business_eval.py`
  - `core/auto_train/controller.py`
  - `core/train/group2/service.py`
  - `tests/python/test_training_jobs.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 新增共享 helper：
    - `preferred_checkpoint_path(best, last)`
    - `preferred_run_checkpoint(train_root, task, run_name)`
  - 删除 `group2` 链路里分散的重复 `best.pt -> last.pt` 选择代码，避免未来再出现不同模块回退规则不一致
  - 删除 `AutoTrainController._resolve_test_model_path()` 中未使用的 `train_name` 兼容参数
  - `core.train.group2.service` 当前只在预测入口解析一次 dataset config，再基于同一份配置判断是否需要逐样本预测
- 已运行验证：
  - `uv run python -m unittest tests.python.test_training_jobs tests.python.test_auto_train_runners tests.python.test_auto_train_business_eval tests.python.test_auto_train_controller`

## 2026-04-10 调整 `group2 auto-train` 综合排序公式，并改为按 trial 总分决定是否将 `last.pt` 提升为当前 run `best.pt`

- 已更新：
  - `core/auto_train/controller.py`
  - `core/train/group2/runner.py`
  - `tests/python/test_auto_train_controller.py`
  - `tests/python/test_training_jobs.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前综合排序公式改为 business-first：
    - `ranking_score = offline_score * difficulty_score * 0.8 + business_component * 2.0`
  - 当前商业测试通过率和 `commercial_ready` 对最终排序的影响显著高于离线分与难度分
  - 当前 `group2` 不再依赖“来源 run 的旧 `best_score` vs 当前 run 的 epoch 分数”去决定当前 run 是否应有 `best.pt`
  - 当前改为：
    - 先用新的综合公式重算各 trial 的 `ranking_score`
    - 如果当前 trial 成为 `leaderboard.best_entry`
    - 且当前 trial 缺少 `weights/best.pt` 但存在 `weights/last.pt`
    - 就把当前 trial 的 `last.pt` 提升为当前 trial 的 `best.pt`
  - 当前这让“上一轮总分 vs 当前轮总分”的比较成为唯一的 best 选择依据
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_controller`

## 2026-04-10 实现 `TASK-AT-EXAM-008`：将商业测试默认通过率门槛调整为 `0.90`

- 已更新：
  - `core/auto_train/controller.py`
  - `core/auto_train/contracts.py`
  - `core/auto_train/cli.py`
  - `core/auto_train/runners/business_eval.py`
  - `tests/python/test_auto_train_cli.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `business_eval_success_threshold` 默认值当前统一从 `0.95` 调整为 `0.90`
  - 影响范围已覆盖：
    - `AutoTrainRequest`
    - `BusinessEvalConfig`
    - CLI `--business-eval-success-threshold`
    - business-eval runner request
  - `--business-eval-success-threshold <ratio>` 显式覆盖能力保持不变
  - CLI 已新增回归测试，明确断言：
    - 默认值为 `0.90`
    - 显式传入 `0.95` 时仍按 `0.95` 转发
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_cli`

## 2026-04-10 实现 `TASK-AT-EXAM-007`：为 `group2` 商业测试失败样本导出 overlay 证据图

- 已更新：
  - `core/auto_train/business_eval.py`
  - `core/auto_train/contracts.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `group2` 商业测试失败 case 当前会额外输出：
    - `trials/<trial_id>/business_eval/failure_overlays/<case_id>.png`
  - 当前证据图生成规则为：
    - 以原始 `master_image` 为底图
    - 把原始 `tile_image` 按模型预测框位置缩放后贴回背景图
  - 当前 `BusinessEvalCaseRecord` 已新增 `artifacts` 字段
  - 当前 `business_eval.md` / `business_eval.log` 会写出失败证据图路径，便于直接追踪到单题可视化产物
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_business_eval`
  - `uv run python -m unittest tests.python.test_auto_train_controller tests.python.test_auto_train_cli`

## 2026-04-10 新增 `auto-train business_eval` 需求拆解：失败样本证据图与 `0.90` 默认成功率门槛

- 已更新：
  - `docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 在自主训练任务拆解文档中新增：
    - `TASK-AT-EXAM-007`：每个 `group2` 商业测试失败样本输出“tile 贴到模型预测位置”的背景图证据
    - `TASK-AT-EXAM-008`：把默认商业测试成功率门槛改为 `0.90`
  - 当前已明确：
    - `--business-eval-success-threshold` 外部参数覆盖能力已经存在
    - 但默认值尚未实施改成 `0.90`
  - 当前还明确冻结了新增验收标准：
    - 失败样本证据图必须可追踪到 `business_eval.md / log / commercial_report`
    - 门槛变化后的旧 study 必须按最新门槛重跑一次商业测试

## 2026-04-10 重构 `group2` 商业测试偏差规则：改为 `X/Y` 方向分别容差，不再用中心点总距离判通过

- 已更新：
  - `core/auto_train/business_eval.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `group2` 商业测试当前不再用 `center_error_px <= point_tolerance_px` 作为主判定
  - 当前已改为：
    - `abs(delta_x_px) <= point_tolerance_px`
    - `abs(delta_y_px) <= point_tolerance_px`
    - `iou >= iou_threshold`
  - 当前 `center_error_px` 仍保留在逐题报告中，但只作为参考展示，不再参与通过判定
  - 当前逐题明细会明确写出：
    - `x_hit`
    - `y_hit`
    - `axis_hit`
    - `failed_checks = delta_x / delta_y / iou`
  - 当前中文报告已同步改为说明：
    - 标准答案与模型预测在 `X/Y` 方向上的偏差
    - 哪一个轴向条件未通过
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_auto_train_business_eval tests.python.test_auto_train_controller tests.python.test_auto_train_cli`

## 2026-04-10 调整 `sinan-generator group1 query` 背景策略：改为透明背景为主，少量混入灰黑/彩色面板

- 已更新：
  - `generator/internal/config/load.go`
  - `generator/internal/config/load_test.go`
  - `generator/internal/preset/preset.go`
  - `generator/internal/preset/preset_test.go`
  - `generator/internal/render/render.go`
  - `generator/internal/render/render_test.go`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前为 `group1 query` 新增配置字段：
    - `effects.click.query_background_transparent_ratio`
  - 当前内置预设默认值已调整为：
    - `firstpass = 0.90`
    - `hard = 0.82`
  - 当前旧工作区 preset 如果尚未写入这个新字段，也会自动继承对应内置默认值
  - 当前透明模式下不再绘制旧浅灰 query 面板和分隔线
  - 当前非透明模式下会稳定随机抽样少量固定面板调色板，覆盖：
    - 浅灰
    - 深灰/近黑
    - 冷灰
    - 蓝灰
    - 暖灰
  - 当前这修复了真实 `group1 query` 为透明 PNG，而生成器长期输出固定浅灰面板的域偏差
- 已运行验证：
  - `env GOCACHE=/tmp/go-build go test ./internal/config ./internal/preset ./internal/render`（cwd=`generator/`）
  - `env GOCACHE=/tmp/go-build go test ./internal/app ./internal/config ./internal/preset ./internal/render`（cwd=`generator/`）

## 2026-04-10 修复 `env setup-train`：避免在安装依赖前因 `PIL` 预加载崩溃

- 已更新：
  - `core/auto_train/__init__.py`
  - `core/ops/setup_train.py`
  - `core/train/group2/service.py`
  - `tests/python/test_setup_train.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `core.auto_train` 当前不再通过 `__init__` 整包 eager import 所有子模块
  - `setup_train` 当前直接引用 `opencode_assets` 子模块，不再无关地拉起 `business_eval/modeltest/group2 service`
  - `group2 service` 当前只在真正检查混尺寸图片时才延迟导入 `PIL`
  - 这修复了训练机首次执行 `uvx --from sinan-captcha==... sinan env setup-train ...` 时可能出现的：
    - `ModuleNotFoundError: No module named 'PIL'`
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_setup_train tests.python.test_training_jobs tests.python.test_auto_train_business_eval tests.python.test_auto_train_controller`

## 2026-04-10 修复 `group2 predict / modeltest / business_eval`：兼容紧边界透明 tile PNG 的混尺寸输入

- 已更新：
  - `core/train/group2/service.py`
  - `tests/python/test_training_jobs.py`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `run_group2_prediction_job()` 当前会先检查预测 source 内的 `master/tile` 尺寸组合
  - 当 source 中存在混尺寸样本时，当前不会再整批调用一次 `group2.runner predict`
  - 当前会自动回退为逐样本预测，再把结果聚合回主输出目录的 `labels.jsonl`
  - 这修复了 reviewed exam 改成紧边界透明 `png` 后，`modeltest` / `business_eval` 仍可能触发的：
    - `stack expects each tensor to be equal size`
  - 当前这次修复会同时覆盖：
    - `sinan predict group2`
    - `modeltest`
    - `auto-train` 的 `business_eval`
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_training_jobs`
  - `.venv/bin/python -m unittest tests.python.test_train_prelabel_service tests.python.test_prediction_and_model_test tests.python.test_auto_train_business_eval tests.python.test_auto_train_controller`

## 2026-04-10 调整 `auto-train` 商业测试门：改为 50 题、5px 容差，并补齐 `best -> last` 回退与逐题偏差报告

- 已更新：
  - `core/auto_train/business_eval.py`
  - `core/auto_train/contracts.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/cli.py`
  - `core/auto_train/runners/business_eval.py`
  - `core/auto_train/runners/evaluate.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `tests/python/test_auto_train_cli.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 商业测试默认抽样题数已从 `30` 改为 `50`
  - 商业测试默认门槛已改为：
    - `business_eval_success_threshold = 0.95`
    - `business_eval_min_cases = 50`
    - `business_eval_sample_size = 50`
    - `point_tolerance_px = 5`
    - `iou_threshold = 0.5`
  - 当前 `group2` 商业测试在找不到 `best.pt` 时，会自动回退到 `last.pt`
  - 当前 `group1` 商业测试也同步支持组件级 `best -> last` 回退
  - 当前 `group2` 单题判卷会显式记录：
    - `center_error_px`
    - `delta_x_px`
    - `delta_y_px`
    - `iou`
    - `x_hit`
    - `y_hit`
    - `axis_hit`
    - `iou_hit`
    - `failed_checks`
  - 当前 `business_eval.md` 与 `business_eval.log` 已补成逐题明细格式
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_auto_train_business_eval`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_cli`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_controller`

## 2026-04-10 修复 `group2 prelabel`：兼容紧边界透明 tile PNG，不再因混尺寸 batch 崩溃

- 已更新：
  - `core/train/prelabel.py`
  - `tests/python/test_train_prelabel_service.py`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `run_group2_prelabel()` 当前不再把整批样本一次性交给 `group2.runner predict`
  - 当前会为每个 `sample_id` 单独写预测输入 JSONL，并逐样本调用预测 job
  - 当前会把单样本预测结果重新聚合回固定的 `labels.jsonl`
  - 这修复了 `import/tile` 改成紧边界透明 `png` 后，不同样本 `tile` tensor 尺寸不一致导致的：
    - `stack expects each tensor to be equal size`
  - 当前这次修复只覆盖 `group2 prelabel` 链路，不改变通用 `group2 predict` 的批处理默认行为
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_train_prelabel_service`

## 2026-04-10 修复 `group2` business exam 导入：`gap.jpg` 改为输出紧边界透明 `png`

- 已更新：
  - `core/exam/service.py`
  - `tests/python/test_exam_service.py`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `docs/04-project-development/05-development-process/data-export-auto-labeling-checklist.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `prepare_group2_exam_sources()` 当前不再把 `materials/result/*/gap.jpg` 原样复制到 `import/tile`
  - 当前会先按现有 `group2` 轮廓归一化逻辑推导透明通道
  - 当前会把图块裁到 alpha 非透明区域的最紧边界
  - 当前导出文件固定为 `import/tile/<sample_id>.png`
  - `manifest.json` 当前会记录新的 `.png` 相对路径
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_exam_service`

## 2026-04-09 新增真实 `group1 query` 图标整理脚本，用于反向建设生成器图标池

- 已更新：
  - `scripts/organize_group1_query_icons.py`
  - `tests/python/test_organize_group1_query_icons_script.py`
  - `scripts/README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 新增脚本，把 `materials/business_exams/group1/reviewed-v1/import/query/*` 里的 query 条切成单个小图标
  - 当前会按二值形状相似度做聚类，输出代表图、总览图和 `manifest.json`
  - 当前已在真实 query 集上完成一次整理：
    - `150` 张 query 图
    - `483` 个切分图标
    - `156` 个 cluster
  - 当前输出目录固定为：
    - `materials/incoming/group1_query_clusters/`
  - 当前这一步主要服务于：
    - 给 cluster 起语义名
    - 从官方图标库补相近图标
    - 后续把命名后的图标沉淀到 generator 的 `group1/icons/<class>/`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_organize_group1_query_icons_script`
  - `uv run python scripts/organize_group1_query_icons.py --input-root materials/business_exams/group1/reviewed-v1/import/query --output-dir materials/incoming/group1_query_clusters`

## 2026-04-09 训练 CLI 新增 reviewed exam 预标注：预测结果直接导出为 X-AnyLabeling `json`

- 已更新：
  - `core/train/prelabel.py`
  - `core/train/group1/cli.py`
  - `core/train/group2/cli.py`
  - `core/cli.py`
  - `tests/python/test_train_prelabel_service.py`
  - `tests/python/test_training_jobs.py`
  - `docs/02-user-guide/prepare-business-exam-with-x-anylabeling.md`
  - `docs/02-user-guide/use-and-test-trained-models.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 新增 `uv run sinan train group1 prelabel --exam-root <exam_root> --train-name <run_name>`
  - 新增 `uv run sinan train group2 prelabel --exam-root <exam_root> --train-name <run_name>`
  - 当前 `prelabel` 会先从 `manifest.json` 构造预测输入，再调用现有训练产物跑预测
  - 当前会把预测结果落成 `reviewed/query|scene|master/*.json`，可直接在 `X-AnyLabeling` 里人工复核
  - 当前 `import/` 里的原始图片不会被改写；复核用图片副本和 `json` 会写到 `reviewed/`
  - 当前不会直接生成最终 `reviewed/labels.jsonl`，仍需人工复核后执行 `uv run sinan exam export-reviewed`
  - 当前默认会保护已有人工复核结果；若 `reviewed/*.json` 已存在，需要显式加 `--overwrite` 才会重跑
- 已运行验证：
  - `uv run python -m unittest tests.python.test_train_prelabel_service tests.python.test_training_jobs tests.python.test_root_cli`

## 2026-04-09 重构 `sinan-generator make-dataset`：按样本随机选择 pack，并让多次运行素材来源显著变化

- 已更新：
  - `generator/internal/app/make_dataset.go`
  - `generator/internal/app/make_dataset_test.go`
  - `generator/internal/export/manifest.go`
  - `generator/internal/materialset/store.go`
  - `generator/internal/sampler/sample.go`
  - `generator/internal/slide/slide.go`
  - `generator/cmd/sinan-generator/main.go`
  - `generator/cmd/sinan-generator/main_test.go`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `make-dataset` 当前默认会扫描工作区内所有通过当前任务校验的素材包，而不是只用单一 `active_material_set`
  - 当前每生成 `1` 条样本，都会先随机选择 `1` 个 `pack_name`
  - 当前每次运行 `make-dataset` 都会自动生成新的运行 seed，因此同一 preset 多次重跑时，源文件和图标选择序列会显著变化
  - 当前样本标签已补充：
    - `material_set`
    - `source_signature`
  - 当前批次与作业元数据已补充：
    - `material_sets`
    - `seed`
  - 当前仍保留显式锁定单 pack 的能力：
    - `--materials local/<name>`
    - `--materials official/<name>`
  - 当前新增可选复现开关：
    - `--runtime-seed <seed>`
- 已运行验证：
  - `env GOCACHE=/tmp/go-build go test ./internal/app`（cwd=`generator/`）
  - `env GOCACHE=/tmp/go-build go test ./...`（cwd=`generator/`）

## 2026-04-09 修复 `sinan-generator materials merge`：支持缺失背景图时的增量合并

- 已更新：
  - `generator/internal/material/validate.go`
  - `generator/internal/materialset/merge.go`
  - `generator/internal/materialset/merge_test.go`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `materials merge` 当前不再沿用完整素材包的强制背景图校验
  - 当前允许以下增量导入场景直接成功：
    - 仅追加 `group1/` 图标
    - 仅追加 `group2/` 缺口图
    - 仅追加 `backgrounds/`
  - 当前会只校验真正存在的素材类型
  - 当前仍会在以下情况失败：
    - 没有任何可导入图片
    - 导入图片本身损坏
    - manifest 或已写入素材目录非法
- 已运行验证：
  - `env GOCACHE=/tmp/go-build go test ./internal/materialset ./internal/material`（cwd=`generator/`）
  - 本地构建 `/tmp/sinan-generator` 后，实际执行 `materials merge` 验证“仅 group1、无背景图”场景返回码为 `0`

## 2026-04-09 商业试卷改为 reviewed exam 模式，删除旧 `group2 overlay` 商业 gate

- 已更新：
  - `core/exam/__init__.py`
  - `core/exam/cli.py`
  - `core/exam/service.py`
  - `core/cli.py`
  - `core/auto_train/contracts.py`
  - `core/auto_train/business_eval.py`
  - `core/auto_train/runners/business_eval.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/cli.py`
  - `tests/python/test_exam_service.py`
  - `tests/python/test_root_cli.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `tests/python/test_auto_train_controller.py`
  - `tests/python/test_auto_train_cli.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/04-project-development/05-development-process/data-export-auto-labeling-checklist.md`
  - `docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 新增 `exam` 根 CLI，支持把 `materials/group1` 和 `materials/result` 整理成 reviewed 试卷工作目录
  - 新增 reviewed 标注导出，直接生成 `reviewed/labels.jsonl`
  - 新增 `group2` 辅助 YOLO 数据导出，只服务于 `X-AnyLabeling` 原生模型预标注
  - `auto-train` 商业测试已不再使用 `overlay/occlusion` 旧模式
  - `group1` 和 `group2` 当前都支持 reviewed exam business gate
  - 商业测试当前统一改成：
    - 从 reviewed 试卷池稳定随机抽 `30` 题
    - 物化 `_sampled_source/labels.jsonl`
    - 调项目现有 solver 预测
    - 按各自任务语义判卷
  - 默认商业门槛当前改为：
    - `business_eval_success_threshold = 0.95`
    - `business_eval_min_cases = 30`
    - `business_eval_sample_size = 30`
  - `X-AnyLabeling` 当前仅用于预标注和人工复核，不改变最终 solver 方案
- 已运行验证：
  - `uv run python -m unittest tests.python.test_exam_service tests.python.test_root_cli tests.python.test_auto_train_business_eval tests.python.test_auto_train_controller tests.python.test_auto_train_cli`

## 2026-04-09 根仓库版本事实源迁移到 `pyproject.toml`

- 已把根仓库版本单一事实源从 `core/_version.py` 迁到根目录 `pyproject.toml`
- 已删除：
  - `core/_version.py`
- 已新增：
  - `core/project_metadata.py`
- 已改为从 `pyproject.toml` 读取版本的入口：
  - `core.__version__`
  - `core/release/service.py`
  - `core/ops/setup_train.py`
- 已同步更新：
  - `tests/python/test_release_service.py`
  - `tests/python/test_setup_train.py`
  - `tests/python/test_project_metadata.py`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `.factory/memory/current-state.md`
- 已验证：
  - `uv run python -m unittest tests.python.test_project_metadata tests.python.test_release_cli tests.python.test_release_service tests.python.test_setup_train tests.python.test_root_cli`
  - `uv run sinan release build-all --project-dir . --goos windows --goarch amd64`

## 2026-04-09 修复 `build-generator` 输出路径，并改为编译前清理输出目录

- 已修复 `build-generator` 的相对路径问题：
  - 之前会把产物误写到 `generator/generator/dist/<goos>-<goarch>/`
  - 现在固定写到 `generator/dist/<goos>-<goarch>/`
- 已把以下构建动作改为“编译前清理对应输出目录”：
  - `uv run sinan release build --project-dir .`
  - `uv run sinan release build-generator --project-dir . ...`
  - `uv run sinan release build-solver --project-dir .`
- 已保留：
  - `dist/.gitignore`
  - `solver/dist/.gitignore`
- 已新增保护：
  - `build-generator` 在 `go build` 返回后会检查目标二进制是否真的存在
- 已清理历史错误产物：
  - `generator/generator/dist/`
- 已同步更新：
  - `README.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `.factory/memory/current-state.md`
- 已验证：
  - `uv run python -m unittest tests.python.test_release_service tests.python.test_release_cli tests.python.test_root_cli`
  - `uv run sinan release build-generator --project-dir . --goos windows --goarch amd64`

## 2026-04-09 根目录统一编译入口整理

- 已把根目录 `release` 子命令扩成四段构建入口：
  - `build`
  - `build-generator`
  - `build-solver`
  - `build-all`
- 已把统一构建路径固定为：
  - 训练 CLI -> `dist/`
  - 生成器 CLI -> `generator/dist/<goos>-<goarch>/`
  - solver 包 -> `solver/dist/`
- 已保留根仓库 PyPI 上传命令：
  - `uv run sinan release publish --project-dir . --token-env <TOKEN_ENV>`
- 已同步更新：
  - `README.md`
  - `docs/03-developer-guide/index.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `.factory/memory/current-state.md`
- 已新增发布链路单测并通过：
  - `tests/python/test_release_cli.py`
  - `tests/python/test_release_service.py`
  - `tests/python/test_root_cli.py`
- 已完成统一编译烟测：
  - `uv run sinan release build-all --project-dir . --goos windows --goarch amd64`

## 2026-04-09 收紧 `scripts/organize_group2_gap_shapes.py` 命名：去掉数字后缀，并压缩到 20 字符内

- 已更新：
  - `scripts/organize_group2_gap_shapes.py`
  - `tests/python/test_organize_group2_gap_shapes_script.py`
  - `scripts/README.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前不再输出 `_alt_001`、`_alt_002` 这类数字尾缀文件名
  - 当前文件名已改为“短家族名 + 短特征码”
  - 当前基名控制在 `20` 个字符以内
  - 当前文件名保持纯字母和下划线，不含数字
  - 当短特征码碰撞时，当前会自动拉长特征码，但仍保持 `<= 20` 个字符
  - 当前同一指纹轮廓仍只保留一个代表图
  - 当前已在真实 `materials/result/*/gap.jpg` 上重跑：
    - `257` 张输入
    - `160` 个唯一轮廓
    - `97` 张重复图被去重
    - 输出目录里确认 `0` 个文件名含数字
    - 当前输出文件基名最大长度是 `15`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_organize_group2_gap_shapes_script`
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile scripts/organize_group2_gap_shapes.py`
  - `uv run python -m scripts.organize_group2_gap_shapes`

## 2026-04-09 修复 `scripts/crawl/ctrip_login.py`：滑块采集统一保存为 `bg.jpg` / `gap.jpg`

- 已更新：
  - `scripts/crawl/ctrip_login.py`
  - `tests/python/test_ctrip_login_script.py`
  - `scripts/README.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 滑块模式当前不再保存 `master.<ext>` / `tile.<ext>`
  - 当前统一保存为：
    - `bg.<ext>`
    - `gap.<ext>`
  - 当前测试动态导入路径已与仓库现状中的 `scripts/` 目录对齐
  - 当前已对已有 `materials/result/*/master.jpg` 和 `tile.jpg` 做一次批量重命名：
    - `master.jpg -> bg.jpg`
    - `tile.jpg -> gap.jpg`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_ctrip_login_script`
  - `uv run python -m py_compile scripts/crawl/ctrip_login.py`
  - `git diff --check`

## 2026-04-09 新增 `script/organize_group2_gap_shapes.py`：按轮廓特征去重并整理 `group2` 滑块拼图图块

- 已更新：
  - `script/organize_group2_gap_shapes.py`
  - `tests/python/test_organize_group2_gap_shapes_script.py`
  - `script/README.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `pyproject.toml`
  - `uv.lock`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前会扫描 `materials/result/*/gap.jpg`
  - 当前会基于透明轮廓提取稳定特征并生成稳定指纹
  - 当前相同轮廓特征只保留一个代表图，不重复输出
  - 当前会生成较泛化但稳定的语义名：
    - `heart_sticker`
    - `diamond_badge`
    - `round_badge`
    - `shield_badge`
    - 以及 `rounded_badge` 等回退名
  - 当前代表图会输出到 `materials/incoming/group2/`
  - 当前会写出 `materials/incoming/group2/manifest.json`，记录来源图、重复来源和轮廓特征摘要
- 已运行验证：
  - `uv run python -m unittest tests.python.test_organize_group2_gap_shapes_script`
  - `uv run python -m py_compile script/organize_group2_gap_shapes.py`
  - `uv run python -m script.organize_group2_gap_shapes`

## 2026-04-09 发布准备 `sinan-captcha==0.1.28`

- 已更新：
  - `core/_version.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前版本号已从 `0.1.27` 提升到 `0.1.28`
  - 本次发布覆盖：
    - `group2 auto-train` 状态工件原子写入
    - leaderboard 读取损坏 `business_eval.json` 时的容错
    - `TEST` 阶段 `best.pt -> last.pt` 的权重回退
    - 更接近人眼判断的 `group2` 商业检测硬门
- 已运行验证：
  - `uv run python -m unittest discover -s tests/python`
  - `git diff --check`

## 2026-04-09 修复 `group2 auto-train`：`from_run` 续训时缺少 `best.pt` 会回退到 `last.pt`

- 已更新：
  - `core/auto_train/runners/train.py`
  - `tests/python/test_auto_train_runners.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `train_mode=from_run` 当前不再死拿上一轮 `best.pt`
  - 当上一轮只有 `last.pt` 时，当前会自动回退到 `last.pt` 继续训练
  - `group1` 的 scene/query 组件当前也做了同样的 `best -> last` 回退
  - 这修复了训练机现场的 `未找到训练检查点` 崩溃
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_runners tests.python.test_auto_train_controller tests.python.test_auto_train_business_eval`

## 2026-04-08 修复 `group2 auto-train` 恢复崩溃，并放宽商业检测到“局部最优 + 10px 容差”

- 已更新：
  - `core/auto_train/storage.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/business_eval.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `business_eval.json`、`study_status.json` 等关键工件当前改为原子写入，避免写入半截时被读取
  - leaderboard 更新阶段当前会容忍单个 trial 的损坏 `business_eval.json`，不再因为一份坏 JSON 直接打断整个 study
  - `TEST` 阶段当前会优先读取 `train.json` 里的权重记录：
    - 优先 `best_weights`
    - `best.pt` 缺失时回退到 `last_weights`
  - `group2` 商业检测当前不再把 `clean_score` 单独作为唯一硬门
  - 当前单样本通过规则收口为：
    - 模型输出与邻域内最优位置边框偏差 `<= 10px`
    - `contour_overlap_ratio >= 0.55`
    - `double_contour_ratio <= 0.45`
    - `overflow_edge_score <= 0.40`
    - `clean_score >= max(0.72, configured_threshold - 0.06)`
  - `exposed_gap_edge_ratio` 与 `tile_residue_ratio` 当前继续输出到日志，但不再单独决定 PASS/FAIL
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_business_eval tests.python.test_auto_train_controller`
  - `uv run python -m unittest discover -s tests/python`
  - `git diff --check`

## 2026-04-09 目录更名：`sript/ -> script/`

- 已更新：
  - `script/README.md`
  - `script/crawl/ctrip_login.py`
  - `tests/python/test_ctrip_login_script.py`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 开发期脚本目录当前已从 `sript/` 正式更名为 `script/`
  - 脚本源码、README、测试动态导入路径和文档目录说明当前已统一改名
  - `Ctrip Login` 调试配置当前使用的 `script.crawl.ctrip_login` 已与实际目录名一致
- 已运行验证：
  - `uv run python -m unittest tests.python.test_ctrip_login_script`
  - `uv run python -m py_compile script/crawl/ctrip_login.py`
  - `git diff --check`

## 2026-04-09 调整 `script/crawl/ctrip_login.py`：`两者都保存` 会连续保存滑块，直到点选出现

- 已更新：
  - `script/crawl/ctrip_login.py`
  - `tests/python/test_ctrip_login_script.py`
  - `script/README.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `两者都保存` 当前不再只是“保存一次滑块再去点选”
  - 当前会先保存一组滑块图
  - 每次随机拖动后如果仍是滑块，当前会继续保存一组新的滑块图
  - 一旦切到点选模式，当前会保存一组点选图并结束本轮浏览器会话
  - 滑块图当前仍输出到 `materials/result/<timestamp>_<index>/`
  - 点选图当前仍输出到 `materials/group1/<timestamp>_<index>/`
  - 新增 `capture_both_mode(...)` 状态机，统一管理滑块连续保存、拖动次数和点选收口
- 已运行验证：
  - `uv run python -m unittest tests.python.test_ctrip_login_script`
  - `uv run python -m py_compile script/crawl/ctrip_login.py`

## 2026-04-08 扩展 `script/crawl/ctrip_login.py`：启动时可选“点选 / 滑块 / 两者都保存”

- 已更新：
  - `script/crawl/ctrip_login.py`
  - `tests/python/test_ctrip_login_script.py`
  - `script/README.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 脚本当前启动时会先让用户选择：
    - `点选`
    - `滑块`
    - `两者都保存`
  - 当前会在发送验证码后按模式执行：
    - 滑块模式：直接保存滑块图片
    - 点选模式：循环随机拖动 `.cpt-drop-btn` 后保存点选图片
    - 两者都保存：先保存滑块，再切换到点选后继续保存
  - 当前检测 `.icon-image-container / .big-icon-image / .small-icon-img` 进入点选模式
  - 当前会把点选背景图保存为 `bg.<ext>`
  - 当前会把点选小图保存为 `icon.<ext>`
  - 当前会把滑块背景图保存为 `master.<ext>`
  - 当前会把滑块拼图块保存为 `tile.<ext>`
  - 当前输出目录已切到：
    - 点选：`materials/group1/<timestamp>_<index>/`
    - 滑块：`materials/result/<timestamp>_<index>/`
  - 当前把 `data:image` 解码、目录创建、保存逻辑拆成可测试辅助函数，避免脚本完全不可验证
  - 当前开发者文档已明确该脚本属于 `script/` 开发期边界，并会产出 `materials/group1/` 与 `materials/result/`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_ctrip_login_script`
  - `uv run python -m py_compile script/crawl/ctrip_login.py`

## 2026-04-08 收口目录结构：`solver_package/ -> solver/`，并把 crawl 脚本迁到 `script/`

- 已更新：
  - `.gitignore`
  - `script/README.md`
  - `script/crawl/ctrip_login.py`
  - `docs/03-developer-guide/index.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/04-project-development/04-design/technical-selection.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 独立 solver 子项目当前统一以 `solver/` 作为项目根目录
  - 开发者与设计文档当前已同步从 `solver_package/` 切换到 `solver/`
  - `core/` 当前不再保留 crawl 采集脚本，避免 dev-only 脚本继续进入正式 Python 包边界
  - 当前新增 `script/` 目录说明，明确该目录只承载开发阶段辅助脚本
  - `.gitignore` 当前已补充 Rust `target/` 目录忽略规则
- 已运行验证：
  - `cargo test`（cwd=`solver/`）
  - `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`（cwd=`solver/`）
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile script/crawl/ctrip_login.py`
  - `git diff --check`

## 2026-04-08 调整 `group2` 商业检测与排行榜：改为“轮廓重合率主判 + 综合评分排名 + 前 3 模型保留”

- 已更新：
  - `core/auto_train/business_eval.py`
  - `core/auto_train/contracts.py`
  - `core/auto_train/controller.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `tests/python/test_auto_train_controller.py`
  - `tests/python/test_auto_train_layout.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 商业检测当前不再主判“背景图里猜出来的参考缺口位置”
  - 当前会直接分析 `overlay.png`，把“图块轮廓是否和背景缺口轮廓真正重合”作为主判
  - 当前新增并主用：
    - `contour_overlap_ratio`
    - `exposed_gap_edge_ratio`
    - `double_contour_ratio`
    - `best_local_bbox`
    - `best_local_offset_px`
    - `best_local_clean_score`
    - `result_cn`
    - `final_score`
    - `required_score`
    - `failed_checks_cn`
  - 当前单样本通过条件：
    - 模型输出位置与邻域内最干净位置的边框偏差 `<= 10px`
    - 邻域内最优 `clean_score` 达标
    - `contour_overlap_ratio >= 0.55`
  - `leaderboard.json / best_trial.json` 当前不再只按离线 `primary_score` 排序
  - 当前会综合：
    - `offline_score`
    - `difficulty_score`
    - `business_success_rate`
    - `commercial_ready`
    - `ranking_score`
  - `difficulty_score` 当前具体来自：
    - `smoke = 0.85`
    - `firstpass = 1.00`
    - `hard = 1.12`
    - 每一层 `_rNNNN` 数据重生深度再额外加 `0.02`，最多加到 `0.08`
  - 下一轮 `from_run` 当前会优先继承 `leaderboard.best_entry.train_name`
  - 当前还会自动删除排行榜前三之外的 run 目录，只保留综合评分最优的 3 个模型
  - 这修复了“简单题 trial_0001 永远排第一、后续更难更接近商用的模型排不上去”的问题，也避免模型目录无限增长
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_layout`
  - `uv run python -m unittest tests.python.test_auto_train_controller`
  - `uv run python -m unittest tests.python.test_auto_train_business_eval`

## 2026-04-08 调整 `auto-train` 自动样本目录命名：改为 `study-name_trial-id`

- 已更新：
  - `core/auto_train/layout.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/resources/opencode/commands/result-read.md`
  - `tests/python/test_auto_train_layout.py`
  - `tests/python/test_auto_train_controller.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `auto-train` 在 `dataset_action = new_version` 时，不再把数据集目录继续命名成 `firstpass_r0002_r0003...`
  - 当前自动生成的数据集版本会固定收口为 `study-name_trial-id`
  - 例如：
    - `study_001_trial_0002`
    - `study_group2_llm_trial_0004`
  - 用户显式传入的初始 `--dataset-version` 当前保持不变，不会被这条规则覆盖
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_layout tests.python.test_auto_train_controller tests.python.test_auto_train_business_eval.BusinessEvalControllerTests tests.python.test_auto_train_opencode_runtime`
  - 更大范围的 `test_auto_train_business_eval` 当前仍有既存 `BusinessEvalScoringTests` 失败，表现与本次命名调整无关

## 2026-04-08 调整 `group2` 商业检测：改为 `overlay` 痕迹检测 + 局部 5px 容差

- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/business_eval.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 不再把背景图里启发式反推的 `reference_bbox / reference_center` 作为商业检测主判
  - 当前会直接分析模型输出生成的 `overlay.png`
  - 商业检测当前会在模型输出位置附近做局部搜索，找到附近“痕迹最干净”的贴合位置
  - 当前新增主字段：
    - `best_local_bbox`
    - `best_local_offset_px`
    - `best_local_clean_score`
    - `tile_residue_ratio`
    - `double_edge_score`
    - `overflow_edge_score`
  - 当前单样本通过条件：
    - `best_local_clean_score >= main_score_threshold`
    - 且模型输出位置与局部最优位置的边框偏差 `<= 5px`
  - 这让商业检测更接近人眼标准：
    - 是否还有大面积图块痕迹
    - 是否有明显双边缘/重影
    - 是否有明显越界边缘
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_auto_train_business_eval`
  - `.venv/bin/python -m unittest discover -s tests/python`
  - `git diff --check`

## 2026-04-08 调整 `auto-train` 结束语义：默认支持“目标驱动停止 + 中断恢复”

- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/cli.py`
  - `tests/python/test_auto_train_cli.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 只要配置了 `--business-eval-dir`，`auto-train run` 当前默认就会切到目标驱动停止模式
  - 当前也支持显式传入 `--goal-only-stop`
  - `--max-steps` 当前支持 `0`，表示本次命令持续运行直到真正 `STOP`
  - `StudyRecord` 当前会持久化 `goal_only_stop`，同一个 `study-name` 恢复时会沿用这条语义
  - 当前在 `goal_only_stop=true` 时，不再因为：
    - `max_trials`
    - `max_hours`
    - `max_new_datasets`
    - `max_no_improve_trials`
    - `plateau`
    自动停掉 study
  - 当前真正结束条件收口为：
    - 商业测试通过
    - `STOP` 文件
    - 或进程/机器中断后等待恢复
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_auto_train_cli`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_controller`

## 2026-04-08 发布 `sinan-captcha==0.1.25`：`group2` 商业测试切换为“参考槽位定位 + 位置误差门”

- 已更新：
  - `core/_version.py`
  - `core/auto_train/contracts.py`
  - `core/auto_train/business_eval.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `group2` 商业测试当前不再把“贴回后原图残差是否几乎消失”作为单样本主判
  - 商业测试当前会从背景图中自动反推出 `reference_bbox / reference_center`
  - 当前日志和报告会明确写出：
    - `predicted_bbox / predicted_center`
    - `reference_bbox / reference_center`
    - `position_error_px`
    - `bbox_edge_error_px`
    - `slot_signal(fill_score)`
    - `reference_alignment(seam_score)`
    - `main_score(occlusion_score)`
  - 当前规则已进一步放宽：
    - `predicted_bbox` 与 `reference_bbox` 四条边最大偏差 `<= 5px` 直接视为定位正常
  - `0.1.25` 当前已成功上传到 PyPI
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_business_eval`
  - `git diff --check`
  - `uv run sinan release build --project-dir .`
  - `uv run sinan release publish --project-dir . --token-env UV_PUBLISH_TOKEN`
  - `https://pypi.org/pypi/sinan-captcha/json`

## 2026-04-08 调整 `group2` 商业测试规则：改为“参考槽位定位 + 位置误差门”

- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/business_eval.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `group2` 商业测试当前不再把“贴回后原图残差是否几乎消失”作为单样本主判
  - 商业测试当前会先从背景图中自动反推出：
    - `reference_bbox`
    - `reference_center`
  - 然后再计算：
    - `position_error_px`
    - `slot_signal(fill_score)`：预测位置本身像不像真实槽位
    - `reference_alignment(seam_score)`：预测位置与参考槽位是否对齐
    - `main_score(occlusion_score) = 0.4 * slot_signal + 0.6 * reference_alignment`
  - `boundary_before / boundary_after` 当前保留为辅诊断字段，用于排查，不再单独决定 PASS/FAIL
  - `business_eval.log / business_eval.md / commercial_report.md` 当前已同步改成围绕“参考槽位对齐”解释结果
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_business_eval`
  - `./.venv/bin/python -m unittest discover -s tests/python`
  - `git diff --check`

## 2026-04-08 发布 `sinan-captcha==0.1.24`：修复 `auto-train` 终态误导

- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/study_status.py`
  - `core/auto_train/business_eval.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/cli.py`
  - `tests/python/test_auto_train_contracts.py`
  - `tests/python/test_auto_train_cli.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的修复：
  - `StudyRecord / StudyStatusRecord` 当前新增 `final_reason / final_detail`
  - study 终态现在会显式落盘停止原因，不再只有 `status=stopped`
  - `summary.md / study_status.json` 当前会区分：
    - 流程已经停止
    - 商业测试未通过
  - `commercial_report.md` 当前升级为详细最终报告，固定包含：
    - 最终结论
    - 流程状态
    - 训练过程结论
    - 晋级结论
    - 商业测试结论
    - 商业测试字段说明
  - `business_eval.log` 当前会先解释字段含义，再写逐 case 数据来源与评分结果
  - `auto-train run` 当前在 `final_stage=STOP` 且 `commercial_ready=false` 时会返回非零退出码，并打印 `final_verdict=FAILED_GOAL`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_contracts tests.python.test_auto_train_cli tests.python.test_auto_train_business_eval`
  - `uv run python -m unittest tests.python.test_auto_train_controller tests.python.test_solve_group2_runtime tests.python.test_solve_service`
  - `https://pypi.org/pypi/sinan-captcha/json`

## 2026-04-08 发布 `sinan-captcha==0.1.23`：`group2` 商业验收切换为“商用目标优先”闭环

- 已更新：
  - `core/_version.py`
  - `core/solve/group2_runtime.py`
  - `core/auto_train/business_eval.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/layout.py`
  - `tests/python/test_solve_group2_runtime.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前准备发布的能力：
  - `gap.jpg` / `tile.jpg` 当前可按图块四周背景自动提轮廓掩码，不再强依赖透明 alpha
  - `group2` 商业验收当前会写出 `business_eval.log`，逐 case 落盘预测框、中心点和评分
  - `group2 + business gate` 当前已收口为“新样本 -> 训练 -> 晋级判断 -> 商业测试，不通过就重新建样本”的闭环
  - 未达到最终商用门时，下一轮当前统一走：
    - `decision = REGENERATE_DATA`
    - `dataset_action = new_version`
    - `train_action = from_run`
    - `base_run = 当前最佳 run`
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_solve_group2_runtime`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_business_eval`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_controller`
  - `.venv/bin/python -m unittest tests.python.test_solve_service`
  - `.venv/bin/python -m unittest discover -s tests/python`
  - `git diff --check`
  - `uv build`
  - `uv publish --publish-url https://upload.pypi.org/legacy/ --check-url https://pypi.org/simple dist/sinan_captcha-0.1.23-py3-none-any.whl dist/sinan_captcha-0.1.23.tar.gz`
  - `curl -s https://pypi.org/pypi/sinan-captcha/json`

## 2026-04-08 补强 `group2` 商业验收：`gap.jpg` 自动提轮廓掩码，并写出逐 case 预测日志

- 已更新：
  - `core/solve/group2_runtime.py`
  - `core/auto_train/business_eval.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/layout.py`
  - `tests/python/test_solve_group2_runtime.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `group2` 商业验收当前不再强依赖透明 PNG 的 alpha 通道
  - 当真实样本使用 `gap.jpg` / `tile.jpg` 这类无 alpha 图块时，运行时当前会按图块四周背景自动提取轮廓掩码
  - 同一套掩码当前会同时作用于：
    - `group2` 推理输入
    - 商业验收贴回评分
  - 当前已新增 `trials/<trial_id>/business_eval.log`，逐 case 记录：
    - `predicted_bbox`
    - `predicted_center`
    - `inference_ms`
    - `occlusion/fill/seam`
    - `PASS/FAIL`
  - `business_eval.md` 与 `commercial_report.md` 当前也会同步展示预测框和中心点，便于训练机排查
  - `group2 + business gate` 当前已把状态机收口为“商用目标优先”：
    - 训练未晋级：下一轮改为 `REGENERATE_DATA`
    - 候选晋级但 business gate 未通过：下一轮同样改为 `REGENERATE_DATA`
    - `base_run` 当前优先继承 leaderboard 中的最佳 run，而不是盲目沿用当前轮次
    - 这让自动训练更接近“新样本 -> 训练 -> 晋级判断 -> 商业测试，不通过就重新建样本”的闭环
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_solve_group2_runtime`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_business_eval`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_controller`
  - `.venv/bin/python -m unittest tests.python.test_solve_service`
  - `.venv/bin/python -m unittest discover -s tests/python`
  - `git diff --check`

## 2026-04-08 发布 `sinan-captcha==0.1.22`，修复 `auto-train` 续训时错误继承 `model` 参数

- 已更新：
  - `core/_version.py`
  - `core/auto_train/controller.py`
  - `tests/python/test_auto_train_controller.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已修复 `auto-train` 在 `train_mode=from_run` / `resume` 时继续沿用上一轮 `params.model` 的问题
  - 当前控制器在为下一轮 trial 生成 `input.json` 时，会在续训路径上主动移除继承来的 `model`
  - 这修复了训练机上 `group2` 续训反复报错 `train_mode=from_run 时不要再显式传入 model`
  - `group2` 续训回归测试当前已明确断言：下一轮 trial 不再携带 `model`
  - `group1` 的 Optuna 建议与规则 fallback 路径当前也已同步到相同口径，避免再次把 `model` 写回 `from_run` trial
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_auto_train_controller`
  - `git diff --check`
  - `uv build`
  - `uv publish --publish-url https://upload.pypi.org/legacy/ --check-url https://pypi.org/simple dist/sinan_captcha-0.1.22-py3-none-any.whl dist/sinan_captcha-0.1.22.tar.gz`
  - `curl https://pypi.org/pypi/sinan-captcha/json`

## 2026-04-07 调整 `group2` 商业验收 gate：固定推荐目录、稳定随机抽样 100 组、阈值提升到 98%

- 已更新：
  - `core/auto_train/business_eval.py`
  - `core/auto_train/contracts.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/runners/business_eval.py`
  - `core/auto_train/cli.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `tests/python/test_auto_train_cli.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当前推荐把商业验收样本固定放在 `<train_root>/business_eval/group2`
  - `group2` 商业验收当前不再全量扫描样本池，而是按 `trial_id` 做稳定随机抽样，每轮最多抽 `100` 组样本
  - 同一 `trial` 重跑会命中同一批样本，新的 `trial` 会更换样本子集，兼顾随机性与可复盘性
  - 商业验收默认门槛当前已调整为：
    - `success_threshold = 0.98`
    - `min_cases = 100`
    - `sample_size = 100`
  - `business_eval.json` 与 `commercial_report.md` 当前会同时记录：
    - 样本池总量 `available_cases`
    - 本轮实际抽样量 `total_cases`
    - 目标抽样量 `sample_size`
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_auto_train_business_eval`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_cli`
  - `git diff --check`

## 2026-04-06 为 `group2 auto-train` 接入真实样本 business eval gate 与商业可用性中文报告

- 已更新：
  - `core/auto_train/business_eval.py`
  - `core/auto_train/runners/business_eval.py`
  - `core/auto_train/contracts.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/layout.py`
  - `core/auto_train/storage.py`
  - `core/auto_train/study_status.py`
  - `core/auto_train/cli.py`
  - `core/auto_train/__init__.py`
  - `core/auto_train/runners/__init__.py`
  - `tests/python/test_auto_train_business_eval.py`
  - `tests/python/test_auto_train_cli.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `group2` 当前可以把真实样本目录接入 `auto-train` 的最终停止条件
  - 当配置 `business_eval_dir` 后，`PROMOTE_BRANCH` 当前只表示“候选可晋级”，还必须通过真实样本遮挡 gate 才会真正 `STOP`
  - 当前 business gate 使用“预测缺口位置 -> 把 tile 贴回 master -> 计算边界残差改善与拼缝质量”的混合判定，不再把最终放行完全交给大模型主观看图
  - 当前会额外写出：
    - `trials/<trial_id>/business_eval.json`
    - `trials/<trial_id>/business_eval.md`
    - `study_root/commercial_report.md`
  - 当配置了 business gate 但尚未通过时，`plateau` / `max_no_improve_trials` 当前不会提前终止 study；仍由 `max_trials / max_hours / max_new_datasets / STOP` 等硬约束兜底
  - `auto-train` CLI 当前已新增：
    - `--business-eval-dir`
    - `--business-eval-success-threshold`
    - `--business-eval-min-cases`
    - `--business-eval-occlusion-threshold`
- 已运行验证：
  - `.venv/bin/python -m unittest tests.python.test_auto_train_business_eval`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_cli`
  - `.venv/bin/python -m unittest tests.python.test_auto_train_controller`
  - `.venv/bin/python -m unittest discover -s tests/python`

## 2026-04-06 重构开发者指南，收口为“快速上手 -> 模块编译 -> 打包发布”

- 已更新：
  - `docs/03-developer-guide/index.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已把 `03-developer-guide` 从概念性说明重写成开发者动作手册
  - 已明确根仓库 Python 包、Go 生成器、`solver_package` 三个模块各自的最快编译命令
  - 已把版本号更新、Python 构建、PyPI 上传、生成器构建、solver 资产导出、Windows 交付包组装整理成单条正式发版顺序
  - 已把文档导航标题同步改成更直接的动作名称
- 已运行验证：
  - `git diff --check`

## 2026-04-06 补强 OpenCode 原始输出落盘，便于训练机直接排查模型返回

- 已更新：
  - `core/auto_train/controller.py`
  - `core/auto_train/storage.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 每次 OpenCode trace 当前除了 `*.json` 外，还会额外生成同序号的 `*.stdout.txt` 与 `*.stderr.txt`
  - `opencode.log` 当前会显式记录 `raw_stdout_file` 和 `raw_stderr_file`
  - 训练机当前可以不经过 JSON 转义，直接查看模型原始返回文本
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_controller.AutoTrainControllerTests.test_record_opencode_trace_writes_log_json_and_terminal_output tests.python.test_auto_train_controller.AutoTrainControllerTests.test_record_opencode_trace_handles_none_stdout_and_stderr`

## 2026-04-06 发布 `sinan-captcha==0.1.20`，修复 OpenCode `step_start-only` 不完整事件流

- 已更新：
  - `core/_version.py`
  - `core/auto_train/opencode_runtime.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已把 OpenCode attach 只返回起始事件、没有最终 JSON 的情况识别为 `opencode_incomplete_event_stream`
  - 当前在本机 attach 场景下，会对这类不完整事件流自动做一次本地直连重试
  - 当前本机 attach 下的 3 类不完整返回都已纳入统一重试：
    - `opencode_empty_stdout`
    - `opencode_incomplete_tool_calls`
    - `opencode_incomplete_event_stream`
  - 训练机排障文档当前已补充 `step_start-only` 现象与升级建议
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_json_extract tests.python.test_auto_train_controller tests.python.test_auto_train_runners tests.python.test_training_jobs tests.python.test_auto_train_optimize tests.python.test_release_service tests.python.test_setup_train`
  - `uv run sinan release build --project-dir .`
  - `uv run sinan release publish --project-dir . --token-env UV_PUBLISH_TOKEN`
  - `uvx --no-config --refresh --default-index https://pypi.org/simple --python 3.12 --from sinan-captcha==0.1.20 sinan --help`

## 2026-04-06 发布 `sinan-captcha==0.1.19`

- 已更新：
  - `core/_version.py`
  - `core/release/service.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `tests/python/test_release_service.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已把 Python 包版本提升到 `0.1.19`
  - 已把训练机文档中的推荐升级版本同步到 `0.1.19`
  - 已修复 `release publish` 会误上传 `dist/` 中历史版本工件的问题
  - 发布器当前只上传当前版本的 `wheel + sdist`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_release_service tests.python.test_setup_train tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_json_extract tests.python.test_auto_train_controller tests.python.test_auto_train_runners tests.python.test_training_jobs tests.python.test_auto_train_optimize`
  - `uv run sinan release build --project-dir .`
  - `uv run sinan release publish --project-dir . --token-env UV_PUBLISH_TOKEN`
  - `uvx --no-config --refresh --default-index https://pypi.org/simple --python 3.12 --from sinan-captcha==0.1.19 sinan --help`

## 2026-04-06 修复 `auto-train` 将 `group2` fresh 误解析为 `yolo26n.pt`

- 已更新：
  - `core/auto_train/runners/train.py`
  - `tests/python/test_auto_train_runners.py`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已把 `auto-train` 的 fresh 默认模型改成按任务分流
  - `group1` 当前继续使用 `yolo26n.pt`
  - `group2` 当前改为使用 `paired_cnn_v1`
  - 已补上 `group2 fresh` 回归测试，避免再次把 YOLO 权重误传给 `group2`
  - 已把 `group2` 的 `fresh / resume / from_run` 模式语义和自动训练业务门示例补进训练者文档
- 已运行验证：
  - `uv run python -m unittest tests/python/test_auto_train_runners.py`
  - `uv run python -m unittest tests/python/test_training_jobs.py tests/python/test_auto_train_optimize.py`

## 2026-04-06 发布 `sinan-captcha==0.1.18`，修复 OpenCode headless 停在 `tool-calls` 不返回最终 JSON

- 已更新：
  - `core/_version.py`
  - `core/auto_train/opencode_commands.py`
  - `core/auto_train/opencode_runtime.py`
  - `.opencode/commands/result-read.md`
  - `.opencode/commands/judge-trial.md`
  - `.opencode/commands/plan-dataset.md`
  - `.opencode/commands/study-status.md`
  - `core/auto_train/resources/opencode/commands/result-read.md`
  - `core/auto_train/resources/opencode/commands/judge-trial.md`
  - `core/auto_train/resources/opencode/commands/plan-dataset.md`
  - `core/auto_train/resources/opencode/commands/study-status.md`
  - `tests/python/test_auto_train_opencode_commands.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已确认用户最新 trace 不是空 stdout，而是 `stdout` 只包含 `tool_use` 和 `step_finish(reason=tool-calls)`
  - headless OpenCode prompt 当前会直接内联 skill 指南，不再要求模型先调用 `skill` 工具
  - 运行时当前会把这类只停在工具回合的返回明确标记成 `opencode_incomplete_tool_calls`
  - 训练机排障文档当前已补充 `tool-calls` 作为单独故障特征
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_opencode_commands.AutoTrainOpenCodeCommandsTests.test_headless_invocation_inlines_files_into_prompt tests.python.test_auto_train_opencode_runtime.AutoTrainOpenCodeRuntimeTests.test_runtime_raises_when_opencode_finishes_at_tool_calls`
  - `uv run python -m unittest tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_json_extract tests.python.test_auto_train_controller`
  - 外沙箱实测 `opencode run --format json --model opencode/qwen3.6-plus-free -- '{"ok":true}'`
  - 外沙箱实测 `plan-dataset` 新 prompt：`reason=stop`、`contains_tool_use=false`、成功提取 `dataset_action`
  - 外沙箱实测 `result-read` 新 prompt：`reason=stop`、`contains_tool_use=false`、成功提取 `study_name/task/trial_id`
  - `uv build`
  - `uv publish --publish-url https://upload.pypi.org/legacy/ --check-url https://pypi.org/simple dist/sinan_captcha-0.1.18-py3-none-any.whl dist/sinan_captcha-0.1.18.tar.gz`
  - `uvx --no-config --refresh --default-index https://pypi.org/simple --python 3.12 --from sinan-captcha==0.1.18 sinan --help`

## 2026-04-06 发布 `sinan-captcha==0.1.17`，补上 OpenCode attach 空 stdout 的本地重试防线

- 已更新：
  - `core/_version.py`
  - `core/auto_train/opencode_runtime.py`
  - `core/auto_train/opencode_commands.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `tests/python/test_auto_train_opencode_commands.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - Python 包版本当前已提升到 `0.1.17`
  - `OpenCodeRuntimeAdapter` 当前会在本机 attach 成功退出但 stdout 为空时，自动做一次无 `--attach` 的本地直连重试
  - 这条降级重试当前只对 `127.0.0.1` / `localhost` attach 地址生效，避免误伤远程 attach
  - prompt 当前已移除“可以调用 skill”与“不要调用 skill tools”的矛盾约束
  - 训练机排障文档当前已改为重放 trace 里的最终 message，而不是旧 `--command` / `--file` 路线
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_json_extract tests.python.test_auto_train_controller`
  - `uv build`
  - `uv publish --publish-url https://upload.pypi.org/legacy/ --check-url https://pypi.org/simple dist/sinan_captcha-0.1.17-py3-none-any.whl dist/sinan_captcha-0.1.17.tar.gz`
  - `uvx --no-config --refresh --default-index https://pypi.org/simple --python 3.12 --from sinan-captcha==0.1.17 sinan --help`
  - `git diff --check`

## 2026-04-06 修复训练机上 OpenCode attach 偶发空 stdout 导致的 auto-train 空错误

- 已更新：
  - `core/auto_train/opencode_runtime.py`
  - `core/auto_train/opencode_commands.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `tests/python/test_auto_train_opencode_commands.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已用用户提供的 `0003_plan-dataset.json` / `0005_plan-dataset.json` trace 完成问题归因
  - 已确认旧 `--command + --file + agent: plan/subtask` 路径会把请求送入 Plan Mode，而不是返回最终 JSON
  - 已确认当前 `message + inline files + agent: build` prompt 在本机 `opencode==1.3.13 + ollama/gemma4:26b` 下可以成功重放，不是 prompt 本身必现失败
  - `OpenCodeRuntimeAdapter` 当前在 `--attach` 成功退出但 stdout 为空时，会自动降级为不带 `--attach` 的本地直连重试一次
  - trace 当前会正确区分 attach 首次尝试与本地重试，不再把两次调用都记成同一个 `attach_url`
  - prompt 渲染当前已移除“允许调用 skill”与“不要调用 skill tools”之间的矛盾提示
  - 训练机排障文档当前已改为：
    - 先做最小 `{"ok":true}` 连通性测试
    - 再直接重放 trace 里的 `command[-1]`
    - 不再建议手工走旧 `--command` / `--file` 路线
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_opencode_runtime`
  - `uv run python -m unittest tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_json_extract tests.python.test_auto_train_controller`
  - 本机实测 `opencode serve --port 4096`
  - 本机实测重放 `0003_plan-dataset.json` 的原始 prompt，成功返回 `dataset_plan.json` JSON event
  - `git diff --check`

## 2026-04-06 将自主训练设计升级为 harness-first 无人值守训练工厂口径

- 已更新：
  - `docs/04-project-development/03-requirements/prd.md`
  - `docs/04-project-development/03-requirements/requirements-analysis.md`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已把 harness 方法论正式写入自主训练设计，而不是只停留在口头说明
  - 已明确“大模型主观能动性”的正式承载面：
    - 一句话目标编译
    - typed tool adapters
    - `ObservationPacket` / `TrialEvidencePack`
    - `Judge` / `Verifier` / `Reducer` verdict 链
    - watchdog、promotion gate、solver smoke gate
  - 已明确为什么不能把生成器和训练 CLI 直接作为对模型裸露的自由工具
  - 已把需求层同步补齐：
    - `REQ-011` 一句话目标编译与 Harness 合同
    - `REQ-012` 严格 Schema I/O、角色分工与多 agent 交叉核查
    - `REQ-013` 无人值守看门狗、自动验收与晋级门
  - 已把 API-006 和自主训练任务拆解同步扩展到 harness-first 口径
- 已运行验证：
  - 待执行 `git diff --check`

## 2026-04-05 准备 `sinan-captcha==0.1.16`，移除 OpenCode `--file` 依赖并将文件内容内联进 prompt

- 已更新：
  - `core/auto_train/opencode_commands.py`
  - `tests/python/test_auto_train_opencode_commands.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `core/_version.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已移除 OpenCode headless 调用对 `--file` 的依赖
  - 当前会把 study/trial 输入文件的内容直接内联到 prompt 中
  - prompt 当前会明确要求模型不要调用任何 file/search/glob/skill 工具
  - 这绕开了训练机上 `glob_search` 这类不存在工具名被模型误调用的问题
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_controller tests.python.test_setup_train tests.python.test_release_service`
  - `git diff --check`

## 2026-04-05 发布 `sinan-captcha==0.1.15`，修复 OpenCode 将内联 skill 误当成工具调用，并收口版本单一事实源

- 已更新：
  - `core/auto_train/opencode_commands.py`
  - `.opencode/commands/result-read.md`
  - `.opencode/commands/judge-trial.md`
  - `.opencode/commands/plan-dataset.md`
  - `.opencode/commands/study-status.md`
  - `core/auto_train/resources/opencode/commands/result-read.md`
  - `core/auto_train/resources/opencode/commands/judge-trial.md`
  - `core/auto_train/resources/opencode/commands/plan-dataset.md`
  - `core/auto_train/resources/opencode/commands/study-status.md`
  - `core/_version.py`
  - `core/__init__.py`
  - `pyproject.toml`
  - `core/ops/setup_train.py`
  - `tests/python/test_auto_train_opencode_commands.py`
  - `tests/python/test_setup_train.py`
  - `tests/python/test_release_service.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已修复训练机上 `0.1.14` 使用普通 message 模式时，模型因为提示词中存在“Load and follow the local ... skill”而尝试调用 `skill:skill` 无效工具的问题
  - OpenCode commands 当前不再要求模型加载本地 skill，而是要求直接遵循“inline guidance”
  - `render_prompt(...)` 当前会直接内联 skill 正文，并明确声明“do not call any skill tool”
  - 已把版本号收口到 `core/_version.py` 单一事实源
  - `pyproject.toml` 当前使用 setuptools dynamic version 读取 `core._version.VERSION`
  - `setup-train` 与相关测试当前已从版本常量派生，不再多处写死 `0.1.15`
  - 已完成 `python3 -m build`
  - 已完成 `uv publish dist/sinan_captcha-0.1.15-py3-none-any.whl dist/sinan_captcha-0.1.15.tar.gz`
  - 已完成 `uvx --no-config --refresh --default-index https://pypi.org/simple --from sinan-captcha==0.1.15 sinan --help`
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_setup_train tests.python.test_release_service tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_controller`
  - `git diff --check`
  - `python3 -m build`
  - `uv publish dist/sinan_captcha-0.1.15-py3-none-any.whl dist/sinan_captcha-0.1.15.tar.gz`
  - `uvx --no-config --refresh --default-index https://pypi.org/simple --python 3.12 --from sinan-captcha==0.1.15 sinan --help`

## 2026-04-05 准备 `sinan-captcha==0.1.14`，绕开 OpenCode attach 模式下 `--command` 强制进入 Plan Mode 的问题

- 已更新：
  - `core/auto_train/opencode_runtime.py`
  - `core/auto_train/controller.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `core/auto_train/json_extract.py`
  - `core/auto_train/opencode_commands.py`
  - `core/auto_train/decision_protocol.py`
  - `core/auto_train/controller.py`
  - `tests/python/test_auto_train_opencode_commands.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `tests/python/test_auto_train_json_extract.py`
  - `tests/python/test_auto_train_decision_protocol.py`
  - `.opencode/commands/result-read.md`
  - `.opencode/commands/judge-trial.md`
  - `.opencode/commands/plan-dataset.md`
  - `.opencode/commands/study-status.md`
  - `core/auto_train/resources/opencode/commands/result-read.md`
  - `core/auto_train/resources/opencode/commands/judge-trial.md`
  - `core/auto_train/resources/opencode/commands/plan-dataset.md`
  - `core/auto_train/resources/opencode/commands/study-status.md`
  - `core/auto_train/summary.py`
  - `tests/python/test_auto_train_summary.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `pyproject.toml`
  - `core/__init__.py`
  - `core/ops/setup_train.py`
  - `uv.lock`
  - `tests/python/test_setup_train.py`
  - `tests/python/test_release_service.py`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/assets/setup-train-terminal.svg`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已修复 Windows 训练机上 `subprocess.run(..., text=True)` 使用系统默认编码读取 OpenCode 输出时触发的 `UnicodeDecodeError: 'gbk' codec can't decode byte ...`
  - OpenCode runtime 当前会显式使用 `encoding='utf-8', errors='replace'`
  - 已修复 trace 记录在 `stdout` 或 `stderr` 为 `None` 时调用 `.strip()` 触发的二次崩溃
  - 已把 OpenCode 默认超时从 `60` 秒提升到 `300` 秒
  - 超时错误当前会明确提示增加 `--opencode-timeout-seconds`
  - 已修复 `SUMMARIZE` 阶段当 `primary_score=None` 且 `best_primary_score` 存在时，证据拼接执行 `None - float` 的崩溃
  - `summary.py` 当前只会在当前分数和对比分数都存在时输出 `delta_vs_previous` / `delta_vs_best`
  - 已修复 OpenCode headless 调用把位置参数误并入 `--file` 解析的问题
  - `opencode run` 当前会在附带文件参数和 `study_name/task/trial_id` 之间显式插入 `--`
  - 已修复 OpenCode headless 调用误把 `--format json` 原始事件流当成最终 JSON 输出的问题
  - 已修复 OpenCode custom command 使用 `agent: plan` + `subtask: true` 导致模型进入 Plan Mode 而不返回最终 JSON 的问题
  - OpenCode commands 当前已切到 `agent: build`，并移除 `subtask: true`
  - 自动训练当前会从 markdown fenced JSON 或带少量前后文字的输出中提取最终对象，减少无意义 fallback
  - 训练机用户指南中的 `study-status` / `judge-trial` 手工排错命令当前已移除 `--format json`
  - Python 包版本当前已提升到 `0.1.13`
  - 训练目录初始化默认包规格当前已切到 `sinan-captcha[train]==0.1.13`
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_json_extract tests.python.test_auto_train_decision_protocol tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_opencode_runtime`
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_controller tests.python.test_root_cli`
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_opencode_commands tests.python.test_auto_train_opencode_runtime`
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_controller tests.python.test_root_cli`
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_summary`
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_controller tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_runners`
  - `git diff --check`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`

## 2026-04-05 发布 `sinan-captcha==0.1.7` 并补齐训练机 OpenCode 排错命令

- 已更新：
  - `pyproject.toml`
  - `core/__init__.py`
  - `core/ops/setup_train.py`
  - `uv.lock`
  - `tests/python/test_setup_train.py`
  - `tests/python/test_release_service.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/assets/setup-train-terminal.svg`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - Python 包版本当前已提升到 `0.1.7`
  - `uv publish` 已成功把 `sinan_captcha-0.1.7-py3-none-any.whl` 和 `sinan_captcha-0.1.7.tar.gz` 上传到 PyPI
  - 训练目录初始化默认包规格当前已切到 `sinan-captcha[train]==0.1.7`
  - 训练机用户指南当前已补齐 `opencode` 命令存在性检查、`study-status` 自检命令和 `judge-trial` 自检命令
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_setup_train tests.python.test_release_service tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_controller`
  - `git diff --check`
  - `uv build`
  - `uv publish --publish-url https://upload.pypi.org/legacy/ --check-url https://pypi.org/simple dist/sinan_captcha-0.1.7-py3-none-any.whl dist/sinan_captcha-0.1.7.tar.gz`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`

## 2026-04-05 增强 auto-train 对 OpenCode 交互的终端与日志可观测性

- 已更新：
  - `core/auto_train/opencode_runtime.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/layout.py`
  - `core/auto_train/storage.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 默认 OpenCode runtime 当前会为每次 `result-read` / `judge-trial` / `plan-dataset` / `study-status` 调用生成结构化 trace
  - trace 当前会记录 `.opencode/commands/*.md` 文本、调用参数、附带文件内容预览、原始 `stdout/stderr`、返回码和错误信息
  - controller 当前会把 trace 同时打印到终端并写入 `studies/<task>/<study>/opencode.log`
  - trial 级和 study 级 trace 当前会分别落到 `trials/<trial_id>/opencode/*.json` 与 `opencode/*.json`
  - 训练者文档当前已明确如何在训练机上查看这些 trace，以确认 OpenCode 如何判断和如何给出数据计划
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_controller tests.python.test_root_cli tests.python.test_auto_train_runners`
  - `git diff --check`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`

## 2026-04-05 按方案 B 重构 materials schema，彻底分离 `group1` 图标池与 `group2` 缺口形状池

- 已更新：
  - `generator/internal/material/catalog.go`
  - `generator/internal/material/validate.go`
  - `generator/internal/material/validate_test.go`
  - `generator/internal/materialset/store.go`
  - `generator/internal/materialset/store_test.go`
  - `generator/internal/app/make_dataset.go`
  - `generator/internal/app/make_dataset_test.go`
  - `generator/internal/sampler/sample.go`
  - `generator/internal/slide/slide.go`
  - `generator/internal/slide/slide_test.go`
  - `generator/internal/qa/check_test.go`
  - `core/materials/service.py`
  - `tests/python/test_materials_service.py`
  - `configs/materials-pack.toml`
  - `configs/materials-pack.example.toml`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/04-project-development/05-development-process/generator-task-breakdown.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 已删除：
  - `generator/internal/material/scaffold.go`
  - `generator/internal/material/scaffold_test.go`
- 当前已完成的目标：
  - Go generator 当前只接受 `schema_version: 2` 的 materials pack
  - `group1` 当前只读取 `group1/icons/` 和 `group1.classes.yaml`
  - `group2` 当前只读取 `group2/shapes/` 和 `group2.shapes.yaml`
  - Python materials builder 当前会直接产出 `materials.yaml`、`group1.classes.yaml`、`group2.shapes.yaml`、`group1.icons.csv`、`group2.shapes.csv`
  - 旧的共享 `icons/ + classes.yaml` 契约和无用 scaffold 代码已完全移除
- 已运行验证：
  - `GOCACHE=/tmp/go-cache go test ./...`（`generator/` 子模块）
  - `./.venv/bin/python -m unittest tests.python.test_materials_service`
  - `git diff --check`

## 2026-04-05 修正 materials 重构后的 task-scoped 校验与迁移说明

- 已更新：
  - `generator/internal/material/validate.go`
  - `generator/internal/material/validate_test.go`
  - `generator/internal/materialset/store.go`
  - `generator/internal/materialset/store_test.go`
  - `generator/internal/app/make_dataset.go`
  - `generator/internal/app/make_dataset_test.go`
  - `generator/cmd/sinan-generator/main.go`
  - `generator/cmd/sinan-generator/main_test.go`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 保留 `materials import/fetch` 默认全量校验语义
  - 新增 `ValidateForTask(...)` 供 `make-dataset` 与自动训练的建数阶段按任务校验
  - `materials import/fetch` 当前已支持 `--task group1|group2`，可导入单任务素材包
  - zip 包导入时的 materials root 探测当前已支持单任务 pack
  - 用户文档当前已补齐旧 materials 包向新目录结构的迁移说明
- 已运行验证：
  - `GOCACHE=/tmp/go-build go test ./internal/material ./internal/materialset ./internal/app ./cmd/sinan-generator`

## 2026-04-05 准备训练 CLI 新版本发布

- 已更新：
  - `pyproject.toml`
  - `core/__init__.py`
  - `core/ops/setup_train.py`
  - `tests/python/test_setup_train.py`
  - `tests/python/test_release_service.py`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
- 当前已完成的目标：
  - 根 Python 包版本当前已从 `0.1.3` 提升到 `0.1.5`
  - 训练目录初始化默认包规格当前已切到 `sinan-captcha[train]==0.1.5`
  - 发布与安装文档中的 wheel 文件名当前已同步到 `0.1.5`

## 2026-04-05 修复 auto-train 恢复 study 时误跳过建数的问题

- 已更新：
  - `core/auto_train/controller.py`
  - `tests/python/test_auto_train_controller.py`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 当 trial 工件里已有 `dataset.json` 但训练目录中的真实 dataset config 已缺失时，控制器当前会把恢复阶段从 `TRAIN/TEST` 回退到 `BUILD_DATASET`
  - `BUILD_DATASET` 当前会校验真实 dataset config，而不是仅凭目录存在就判定为可用
  - 当目录存在但数据集不完整时，当前会以 `force=True` 重新调用生成器覆盖重建
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_controller tests.python.test_auto_train_runners tests.python.test_root_cli`

## 2026-04-05 修复 auto-train 在 Windows 训练机上找不到生成器命令的问题

- 已更新：
  - `core/auto_train/controller.py`
  - `core/auto_train/cli.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `pyproject.toml`
  - `core/__init__.py`
  - `core/ops/setup_train.py`
  - `tests/python/test_setup_train.py`
  - `tests/python/test_release_service.py`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/assets/setup-train-terminal.svg`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `uv.lock`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `auto-train` 当前已支持 `--generator-executable`
  - `BUILD_DATASET` 当前会把该路径透传给 dataset runner
  - Windows 默认生成器命令名当前已切到 `sinan-generator.exe`
  - 文档当前已明确建议在训练机上显式传完整 exe 路径
  - Python 包版本当前已提升到 `0.1.6`
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_controller tests.python.test_auto_train_runners tests.python.test_root_cli`

## 2026-04-05 将 OpenCode 训练机部署默认切到 `train_root`

- 已更新：
  - `core/auto_train/opencode_assets.py`
  - `core/auto_train/resources/opencode/commands/*.md`
  - `core/auto_train/resources/opencode/skills/*/SKILL.md`
  - `core/ops/setup_train.py`
  - `core/auto_train/controller.py`
  - `pyproject.toml`
  - `tests/python/test_setup_train.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/windows-quickstart.md`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/02-user-guide/user-guide.md`
  - `README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `env setup-train` 现在会自动把 `.opencode/commands` 和 `.opencode/skills` 复制到训练目录
  - `auto-train` 现在默认把 `train_root` 当成 OpenCode `project_root`
  - 训练者现在可以直接在 `sinan-captcha-work` 内执行 `opencode serve`
  - Python 包现在会随发行物分发 `core.auto_train.resources/opencode/**`，为训练目录初始化提供资产来源
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_setup_train tests.python.test_auto_train_controller tests.python.test_auto_train_opencode_runtime`

## 2026-04-05 优化 `auto-train-on-training-machine` 的训练机搭建说明

- 已更新：
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/02-user-guide/user-guide.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已把自动训练文档明确拆成 `rules` 与 `opencode` 两条训练机部署路线
  - 已明确 `rules` 路线不需要大模型，也不需要 `opencode`
  - 已明确 `.opencode/commands/` 与 `.opencode/skills/` 当前不是单独安装到训练机的 pip 包
  - 当时的控制目录部署建议已被后续的“训练目录内置 `.opencode`”方案替代
- 已运行验证：
  - `git diff --check`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`

## 2026-04-05 修正 `02-user-guide` 的 4 个使用者视角问题

- 已更新：
  - `docs/02-user-guide/use-solver-bundle.md`
  - `docs/02-user-guide/application-integration.md`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已把 `use-solver-bundle` 改成纯安装与公开调用面说明，不再夹带交付状态与实现进度
  - 已把 `application-integration` 改成库调用手册，补齐函数参数、返回值、异常和接入样例
  - 已把 `prepare-training-data-with-generator` 补成可执行操作文档，明确素材结构、放置目录、导入/下载方式、`make-dataset` 参数与 `override-file` 字段语义
  - 已把 `auto-train-on-training-machine` 改成训练机操作页，补齐启动命令、预算参数、恢复方式、停止方式和 study 工件阅读顺序
- 已运行验证：
  - `git diff --check`

## 2026-04-05 修复 `auto-train` 的 3 个关键闭环缺口

- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/stop_rules.py`
  - `tests/python/test_auto_train_controller.py`
  - `tests/python/test_auto_train_state_machine.py`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - `EVALUATE` 现在会自动接上 `TEST` 产物生成的 `_gold/labels.jsonl` 和预测目录
  - `max_hours` 现在会基于 study `started_at` 形成真实计时停止规则
  - `max_new_datasets` 现在会在需要继续 `new_version` 时阻止超预算再生数据
  - `02-user-guide` 中关于 `auto-train` 的公开结论已同步到最新事实
- 当前判断：
  - `auto-train` 已达到“训练机可开始受控自动训练”的程度
  - 当前仍不应宣称为“Windows 训练机无人值守正式入口”
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_controller tests.python.test_auto_train_state_machine`
  - `./.venv/bin/python -m unittest tests.python.test_auto_train_contracts tests.python.test_auto_train_runners tests.python.test_auto_train_controller tests.python.test_auto_train_state_machine tests.python.test_auto_train_optimize tests.python.test_auto_train_optuna_runtime tests.python.test_auto_train_policies tests.python.test_auto_train_opencode_runtime`

## 2026-04-05 完成训练产线审核并重构 `02-user-guide` 角色结构

- 已新增：
  - `docs/02-user-guide/application-integration.md`
  - `docs/02-user-guide/auto-train-on-training-machine.md`
- 已更新：
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/use-solver-bundle.md`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/windows-quickstart.md`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/use-and-test-trained-models.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/index.md`
  - `docs/01-getting-started/index.md`
  - `README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 已按“使用者角色 / 训练者角色”重排公开用户文档入口
  - 已把生成器 CLI、手动训练 CLI、自动化训练 CLI 的审核结论写入公开总览页
  - 已为业务方补齐“在自己的应用里接入并做业务测试”的专页
  - 已为训练者补齐“训练机安装 / 生成器 / 训练器 / 自动化训练 / 训练后验收”的角色化阅读路径
- 当前审核结论：
  - `sinan-generator`：训练数据准备主线可用
  - `sinan` 手动训练主线：可用
  - `auto-train`：可做受控 study，但还不是“全部完成”的无人值守正式入口
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_root_cli tests.python.test_training_jobs tests.python.test_auto_train_contracts tests.python.test_auto_train_runners tests.python.test_auto_train_controller tests.python.test_auto_train_optimize tests.python.test_auto_train_optuna_runtime tests.python.test_auto_train_policies tests.python.test_auto_train_opencode_runtime`
  - `GOCACHE=/tmp/go-build go test ./cmd/sinan-generator ./internal/app ./internal/config ./internal/dataset ./internal/materialset ./internal/render ./internal/truth ./internal/qa`

## 2026-04-05 启动 `TASK-SOLVER-MIG-008`，落地 group2 ONNX 导出与原生桥接合同

- 已新增：
  - `core/release/solver_export.py`
  - `tests/python/test_solver_asset_export_group2.py`
  - `tests/python/test_release_cli.py`
  - `solver_package/tests/test_group2_service.py`
- 已更新：
  - `core/release/__init__.py`
  - `core/release/cli.py`
  - `core/release/service.py`
  - `solver_package/src/sinanz/native_bridge.py`
  - `solver_package/src/sinanz/group2/service.py`
  - `solver_package/native/sinanz_ext/Cargo.toml`
  - `solver_package/native/sinanz_ext/src/bridge.rs`
  - `solver_package/native/sinanz_ext/src/lib.rs`
  - `solver_package/tests/test_native_bridge.py`
  - `solver_package/tests/test_native_project_layout.py`
  - `solver_package/tests/test_public_api.py`
  - `docs/04-project-development/04-design/solver-asset-export-contract.md`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `solver_package/README.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 训练仓库已具备 `group2` 专项的 `export-solver-assets` 命令和导出服务
  - `manifest / metadata / export_report` 已能围绕 `slider_gap_locator.onnx` 真正落盘
  - `sinanz` 的滑块求解面已从 `.pt + PyTorch runtime` 切到 `.onnx + native_bridge` 契约
  - Rust crate 的阶段元数据已升级为 `group2-onnx-bridge`
- 当前仍未完成的实现：
  - `sinanz_ext` 还没有真正接入 `pyo3 + ONNX Runtime`
  - `group1` 资产仍未导出，相关 metadata 目前是占位文件
  - 平台相关 wheel 与原生扩展打包仍在 `TASK-SOLVER-MIG-011`
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_release_service tests.python.test_release_cli tests.python.test_solver_asset_contract tests.python.test_solver_asset_export_group2`
  - `PYTHONPATH=solver_package/src ./.venv/bin/python -m unittest discover -s solver_package/tests -p 'test_*.py'`
  - `cargo test --manifest-path solver_package/native/sinanz_ext/Cargo.toml`
  - `git diff --check`

## 2026-04-05 完成 `TASK-SOLVER-MIG-007`，固定 Rust 原生扩展工程边界

- 已新增：
  - `solver_package/src/sinanz/native_bridge.py`
  - `solver_package/tests/test_native_bridge.py`
  - `solver_package/tests/test_native_project_layout.py`
  - `solver_package/native/sinanz_ext/src/bridge.rs`
  - `solver_package/native/sinanz_ext/src/runtime.rs`
  - `solver_package/native/sinanz_ext/src/error.rs`
- 已更新：
  - `solver_package/src/sinanz/__init__.py`
  - `solver_package/src/sinanz/group2/service.py`
  - `solver_package/pyproject.toml`
  - `solver_package/Cargo.toml`
  - `solver_package/README.md`
  - `solver_package/native/README.md`
  - `solver_package/native/sinanz_ext/Cargo.toml`
  - `solver_package/native/sinanz_ext/README.md`
  - `solver_package/native/sinanz_ext/src/lib.rs`
  - `solver_package/src/sinanz/resources/models/README.md`
  - `solver_package/src/sinanz/resources/metadata/README.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - Python 侧已有稳定的 `native_bridge` 占位和运行时元数据读取面
  - Cargo workspace 与 crate metadata 已固定 `native_module`、`bridge_module`、`runtime_target` 和 future feature 名称
  - Rust crate 内部模块边界已拆开，为后续 `pyo3 + ort` 接线预留明确位置
- 当前仍未完成的实现：
  - Rust 扩展仍未接入 `pyo3`
  - ONNX Runtime 仍未接入 Rust crate
  - Python 构建后端仍未把原生扩展打进 wheel
- 已运行验证：
  - `PYTHONPATH=solver_package/src ./.venv/bin/python -m unittest discover -s solver_package/tests -p 'test_*.py'`
  - `cargo test --manifest-path solver_package/native/sinanz_ext/Cargo.toml`
  - `uv build --directory solver_package`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`
  - `git diff --check`

## 2026-04-05 完成 `TASK-SOLVER-MIG-006`，冻结 `PT -> ONNX` 导出合同

- 已新增：
  - `docs/04-project-development/04-design/solver-asset-export-contract.md`
  - `core/release/solver_asset_contract.py`
  - `tests/python/test_solver_asset_contract.py`
- 已更新：
  - `core/release/__init__.py`
  - `docs/index.md`
  - `docs/04-project-development/04-design/index.md`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/project-index.md`
  - `.factory/memory/design-assets.summary.md`
  - `.factory/memory/tech-stack.summary.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - ONNX 文件名与相对路径规则已冻结
  - `manifest.json` 顶层字段、模型字段和 `metadata_files` 已冻结
  - per-model metadata 与 `export_report.json` 字段已冻结
  - 仓库内已有可执行的 Python 契约事实源，后续导出实现可直接复用
- 当前仍未完成的实现：
  - `export-solver-assets` 命令仍未落地
  - 真实 `PT -> ONNX` 导出还没接到训练链路
  - Rust 扩展还没开始消费这套导出资产
- 已运行验证：
  - `./.venv/bin/python -m unittest tests.python.test_solver_asset_contract tests.python.test_release_service`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`
  - `git diff --check`

## 2026-04-05 冻结 `sinanz` 的 ONNX + Rust 路线，并收口公开方法名

- 已新增：
  - `solver_package/Cargo.toml`
  - `solver_package/native/README.md`
  - `solver_package/native/sinanz_ext/Cargo.toml`
  - `solver_package/native/sinanz_ext/README.md`
  - `solver_package/native/sinanz_ext/src/lib.rs`
- 已更新：
  - `solver_package/pyproject.toml`
  - `solver_package/README.md`
  - `solver_package/src/sinanz/api.py`
  - `solver_package/src/sinanz/__init__.py`
  - `solver_package/tests/test_public_api.py`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/technical-selection.md`
  - `docs/04-project-development/04-design/system-architecture.md`
  - `docs/04-project-development/04-design/module-boundaries.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `.factory/project.json`
  - `.factory/memory/project-index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 独立 solver 的公开函数名已收口为 `sn_match_slider(...)` 和 `sn_match_targets(...)`
  - 设计基线已从“Python 包 + 外置 bundle”切到“平台 wheel + embedded ONNX assets + Rust native extension”
  - 独立 solver 迁移任务已重排为 `TASK-SOLVER-MIG-001` 到 `TASK-SOLVER-MIG-012`
  - 已在 `solver_package/` 下新增可被 Cargo 识别的 Rust 原生扩展骨架
- 当前仍未完成的实现：
  - `pyo3 + ONNX Runtime` 尚未接入 Rust 扩展
  - `sn_match_targets(...)` 仍处于占位阶段
  - `group2` 当前运行时仍是 Python/PyTorch 过渡实现，不是最终 ONNX 路线
  - `uv build --directory solver_package` 当前仍输出 `py3-none-any` wheel，Rust 扩展尚未接入打包后端
- 已运行验证：
  - `PYTHONPATH=solver_package/src ./.venv/bin/python -m unittest solver_package.tests.test_public_api solver_package.tests.test_group2_runtime`
  - `cargo test --manifest-path solver_package/native/sinanz_ext/Cargo.toml`
  - `uv build --directory solver_package`
  - `uvx --from docs-stratego docs-stratego source validate --repo-path .`
  - `git diff --check`

## 2026-04-05 完成 `TASK-SOLVER-MIG-005` 并将独立包名改为 `sinanz`

- 已新增：
  - `core/solve/group2_runtime.py`
  - `solver_package/src/sinanz/group2/runtime.py`
  - `solver_package/src/sinanz/group2/service.py`
  - `tests/python/test_solve_group2_runtime.py`
  - `solver_package/tests/test_group2_runtime.py`
- 已更新：
  - `solver_package/pyproject.toml`
  - `solver_package/README.md`
  - `solver_package/uv.lock`
  - `solver_package/tests/test_public_api.py`
  - `core/solve/service.py`
  - `tests/python/test_solve_service.py`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md`
  - `.factory/project.json`
  - `.factory/memory/project-index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的目标：
  - 独立 solver 的公开包名与导入名统一收口为 `sinanz`
  - 训练仓库 solver 的 group2 运行时已从训练 runner 私有函数中抽离
  - `sinanz` 的滑块入口已接入真实 runtime 与资产解析层
- 当前 `sinanz` 的 group2 行为：
  - 默认查找内嵌 `slider_gap_locator.pt`
  - 若内嵌资产缺失，则显式抛出 `SolverAssetError`
  - 支持通过 `asset_root` 覆盖模型资产目录
- 已运行验证：
  - `PYTHONPATH=solver_package/src ./.venv/bin/python -m unittest discover -s solver_package/tests -p 'test_*.py'`
  - `./.venv/bin/python -m unittest tests.python.test_solve_service tests.python.test_solve_group2_runtime`
  - `uv build --directory solver_package`

## 2026-04-05 完成 `TASK-SOLVER-MIG-004` 独立子项目骨架

- 已新增：
  - `solver_package/pyproject.toml`
  - `solver_package/README.md`
  - `solver_package/src/sinanz/__init__.py`
  - `solver_package/src/sinanz/api.py`
  - `solver_package/src/sinanz/errors.py`
  - `solver_package/src/sinanz/types.py`
  - `solver_package/src/sinanz/image_io.py`
  - `solver_package/src/sinanz/resources/__init__.py`
  - `solver_package/src/sinanz/resources/models/README.md`
  - `solver_package/src/sinanz/resources/metadata/README.md`
  - `solver_package/src/sinanz/group1/__init__.py`
  - `solver_package/src/sinanz/group2/__init__.py`
  - `solver_package/src/sinanz/py.typed`
  - `solver_package/tests/test_public_api.py`
- 已更新：
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成的任务目标：
  - 在当前仓库内建立 `solver_package/` 独立 Python 子项目
  - 固定独立 `pyproject.toml`、`src/` 布局、测试入口和资源目录规则
  - 暴露业务语义导向的最小公开 API 名称
- 当前公开 API 仍是占位运行时：
  - 会显式抛出 `SolverRuntimeError`
  - 提示继续完成 `TASK-SOLVER-MIG-005/006/007`
- 已运行验证：
  - `uv build --directory solver_package`
  - `PYTHONPATH=solver_package/src ./.venv/bin/python -m unittest discover -s solver_package/tests -p 'test_*.py'`

## 2026-04-05 冻结独立 solver 迁移任务与设计边界

- 已新增：
  - `docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md`
- 已更新：
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `docs/04-project-development/05-development-process/index.md`
  - `docs/index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/project-index.md`
  - `.factory/project.json`
  - `.factory/memory/change-summary.md`
- 当前已把 solver 的最终交付目标从“训练仓库里的 CLI + 外置 bundle”重新冻结为：
  - 独立 PyPI 项目 `sinanz`
  - 见名知义的业务函数 API
  - 默认内嵌推理资产
- 当前已把现有 `core/solve`、`bundle` 和 `sinan solve` 重新定义为迁移期参考实现与内部交接能力
- 当前已把独立 solver 迁移拆成 `TASK-SOLVER-MIG-001` 到 `TASK-SOLVER-MIG-009`
- 本轮没有修改业务代码；下一步应按任务拆解先从边界冻结、子项目骨架和推理资产导出链路开始实施

## 2026-04-05 落地 auto-train 第二阶段最小数据控制面

- 已新增：
  - `generator/internal/config/override.go`
- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/dataset_plan.py`
  - `core/auto_train/layout.py`
  - `core/auto_train/runners/dataset.py`
  - `generator/cmd/sinan-generator/main.go`
  - `generator/internal/app/make_dataset.go`
  - `tests/python/test_auto_train_contracts.py`
  - `tests/python/test_auto_train_runners.py`
  - `tests/python/test_auto_train_controller.py`
  - `generator/cmd/sinan-generator/main_test.go`
  - `generator/internal/app/make_dataset_test.go`
  - `.opencode/commands/plan-dataset.md`
  - `.opencode/skills/dataset-planner/SKILL.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `docs/04-project-development/04-design/system-architecture.md`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/05-development-process/autonomous-training-implementation-readiness.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已把 `REGENERATE_DATA` 从“只会出计划”补到“会把最小数据控制参数真正传给生成器”：
  - `dataset_plan.json` 可携带 `generator_preset` 与 `generator_overrides`
  - 下一轮 `input.json` 会写入 `dataset_preset` 与 `dataset_override`
  - `BUILD_DATASET` 会物化 `generator_override.json`
  - `sinan-generator make-dataset` 会通过 `--preset` 和 `--override-file` 消费这些参数
- 当前最小打通范围仅覆盖：
  - `project.sample_count`
  - `sampling.target_count_*`
  - `sampling.distractor_count_*`
  - `effects.common.*`
  - `effects.click.*`
  - `effects.slide.*`
- 当前仍未覆盖的更高阶数据控制包括：
  - 素材集切换
  - 类目定向采样
  - 失败模式定向素材策略
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_contracts tests.python.test_auto_train_runners tests.python.test_auto_train_controller`
  - `GOCACHE=/tmp/go-build go test ./cmd/sinan-generator ./internal/app`

## 2026-04-05 落地 solver 第一阶段交付主线

- 已新增：
  - `tests/python/test_solve_service.py`
- 已更新：
  - `core/cli.py`
  - `core/release/cli.py`
  - `core/release/service.py`
  - `core/solve/contracts.py`
  - `core/solve/service.py`
  - `tests/python/test_root_cli.py`
  - `tests/python/test_release_service.py`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/use-solver-bundle.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/04-project-development/04-design/technical-selection.md`
  - `docs/04-project-development/04-design/system-architecture.md`
  - `docs/04-project-development/07-release-delivery/release-notes.md`
  - `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已完成 4 个第一阶段任务：
  - 根 `sinan` CLI 接入 `solve`
  - `package-windows` 支持打入 solver bundle
  - `group2` 合同改为 `tile_start_bbox` 可选
  - solver 回归测试补齐到正式测试面
- 已运行验证：
  - `uv run python -m unittest tests.python.test_root_cli tests.python.test_release_service tests.python.test_solve_service`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 `125` 个 Python 测试通过

## 2026-04-05 补齐 solver 使用与集成文档

- 已新增：
  - `docs/02-user-guide/use-solver-bundle.md`
  - `docs/03-developer-guide/solver-bundle-and-integration.md`
- 已更新：
  - `README.md`
  - `docs/index.md`
  - `docs/01-getting-started/index.md`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/03-developer-guide/index.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/04-project-development/10-traceability/requirements-matrix.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
  - `.factory/memory/traceability.summary.md`
- 当前已把 solver 的“最终调用方说明”和“维护者集成边界”从零散总览提升为两张正式页面
- 当前 README、入门页、用户指南、开发者指南和全站导航都已接入 solver 专属入口
- 当前文档基线已经可以直接支撑下一步代码偏差评估，不再需要先去内部设计文档里拼装产品目标
- 本轮没有修改业务代码，也没有新增代码测试执行

## 2026-04-05 重构发布与部署文档（solver-first）

- 已新增：
  - `docs/04-project-development/07-release-delivery/release-notes.md`
  - `docs/04-project-development/07-release-delivery/delivery-package.md`
  - `docs/04-project-development/07-release-delivery/release-checklist.md`
  - `docs/04-project-development/08-operations-maintenance/deployment-guide.md`
- 已更新：
  - `docs/04-project-development/07-release-delivery/index.md`
  - `docs/04-project-development/08-operations-maintenance/index.md`
  - `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/index.md`
  - `docs/04-project-development/10-traceability/requirements-matrix.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已把发布与部署文档明确拆成两条口径：
  - 当前稳定的训练机交付包
  - 目标 solver 交付包及其尚未接通的发布差距
- 当前已补齐内部发布页、交付包页、检查清单、部署说明和运维手册
- 当前没有修改业务代码，也没有新增测试执行

## 2026-04-05 落地实现真实 `Optuna` RETUNE runtime

- 已新增：
  - `core/auto_train/optuna_runtime.py`
  - `tests/python/test_auto_train_optuna_runtime.py`
- 已更新：
  - `core/auto_train/controller.py`
  - `core/auto_train/layout.py`
  - `core/auto_train/__init__.py`
  - `tests/python/test_auto_train_controller.py`
  - `pyproject.toml`
  - `docs/04-project-development/04-design/technical-selection.md`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/05-development-process/autonomous-training-implementation-readiness.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/change-summary.md`
- 当前已把 `RETUNE` 正式切到真实 `Optuna` runtime：
  - `controller` 在 `RETUNE` 时会先构建 `OptimizationPlan`
  - `OptunaRuntimeAdapter` 会把当前完成 trial 注册到 `optuna.sqlite3`
  - 然后为下一轮生成真实 suggestion，并把最小元数据写回 `input.json`
- 当前已固定 `Optuna` runtime 的恢复与回退边界：
  - 若下一轮 trial 已有挂起的 `Optuna` trial，则直接复用已有 suggestion
  - 若当前 trial 本身带有 `_optuna_trial_number`，则优先 `tell(...)`
  - 若 `Optuna` 缺失或 runtime 失败，则稳定回退到 deterministic fallback 参数
- 当前已把 `optuna` 纳入 `sinan-captcha[train]` 训练依赖
- 已新增回归覆盖：
  - `Optuna` runtime completed-trial import
  - 复用已有 pending suggestion
  - tell existing Optuna trial
  - controller `RETUNE` 成功注入 suggestion
  - controller `RETUNE` runtime error fallback
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_optuna_runtime tests.python.test_auto_train_controller`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 `119` 个 Python 测试通过

## 2026-04-05 重构设计文档口径（solver-first）

- 已更新：
  - `docs/04-project-development/04-design/technical-selection.md`
  - `docs/04-project-development/04-design/system-architecture.md`
  - `docs/04-project-development/04-design/module-boundaries.md`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/04-project-development/10-traceability/requirements-matrix.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/project-index.md`
  - `.factory/memory/design-assets.summary.md`
  - `.factory/memory/tech-stack.summary.md`
  - `.factory/memory/change-summary.md`
- 当前已把设计层正式切换为 solver-first：
  - 最终交付为 `solver package/library + bundle`
  - generator / training / auto-train 为模型生产平面
- 当前已在设计文档里显式标注实现差距：
  - 根 `sinan` CLI 未注册 `solve`
  - `package-windows` 未纳入 solver bundle
  - `group2` 仍把 `tile_start_bbox` 视为必填
- 当前 `requirements-matrix` 已同步把已修订的设计文档行状态改为有效
- 本轮为设计文档与记忆层收口，没有修改业务代码，也没有新增测试执行

## 2026-04-05 重构需求与公开文档口径（solver-first）

- 已更新：
  - `docs/04-project-development/01-governance/project-charter.md`
  - `docs/04-project-development/02-discovery/input.md`
  - `docs/04-project-development/02-discovery/brainstorm-record.md`
  - `docs/04-project-development/03-requirements/prd.md`
  - `docs/04-project-development/03-requirements/requirements-analysis.md`
  - `docs/04-project-development/03-requirements/requirements-verification.md`
  - `docs/04-project-development/10-traceability/requirements-matrix.md`
  - `README.md`
  - `docs/01-getting-started/index.md`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/03-developer-guide/index.md`
  - `.factory/project.json`
  - `.factory/memory/current-state.md`
  - `.factory/memory/project-index.md`
  - `.factory/memory/motivation-state.md`
  - `.factory/memory/prd.summary.md`
  - `.factory/memory/requirements-verification.summary.md`
  - `.factory/memory/traceability.summary.md`
- 当前已把项目正式定位从“训练工程优先”改为“统一验证码求解包/库优先”
- 当前已把 Go 生成器、Windows 训练 CLI 和自主训练 CLI 明确降为模型生产工具链
- 当前已把公开入口文档改成同时说明：
  - 最终业务交付物是什么
  - 当前最完整的稳定实现仍是哪条主线
- 当前仍待后续继续同步：
  - `docs/04-project-development/04-design/`
  - `docs/04-project-development/07-release-delivery/`
  - `docs/04-project-development/08-operations-maintenance/`
- 本轮为正式文档与记忆层重构，没有修改业务代码，也没有新增测试执行

## 2026-04-05 落地实现 `plan-dataset` 的真实 OpenCode 接入

- 已新增：
  - `core/auto_train/dataset_plan.py`
- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/layout.py`
  - `core/auto_train/storage.py`
  - `core/auto_train/opencode_runtime.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/__init__.py`
  - `tests/python/test_auto_train_contracts.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/05-development-process/autonomous-training-implementation-readiness.md`
- 当前已新增正式数据规划工件：
  - `dataset_plan.json`
  - `DatasetPlanRecord`
- 当前 `REGENERATE_DATA` 路径会优先调用真实 `opencode plan-dataset`：
  - 成功时直接落盘 `dataset_plan.json`
  - 失败或非法 JSON 时回退到本地 `dataset_plan.build_dataset_plan(...)`
- 当前 `dataset_plan.json` 会直接参与下一轮准备：
  - `dataset_action = new_version` 时，下一轮自动生成新的 `dataset_version`
  - `dataset_action = reuse` 时，继续复用当前数据版本
- 当前至此已经补齐 4 个 OpenCode command 的真实运行时接入：
  - `result-read`
  - `judge-trial`
  - `plan-dataset`
  - `study-status`
- 已新增回归覆盖：
  - `dataset_plan.json` / `study_status.json` round-trip
  - `plan-dataset` 命令构造
  - planner 成功时写入真实 `dataset_plan.json`
  - planner 失败时回退到本地 dataset plan
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_contracts tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_controller tests.python.test_auto_train_summary tests.python.test_auto_train_decision_protocol tests.python.test_root_cli`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 `114` 个 Python 测试通过

## 2026-04-05 落地实现 `result-read` 与 `study-status` 的真实 OpenCode 接入

- 已新增：
  - `core/auto_train/study_status.py`
- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/layout.py`
  - `core/auto_train/storage.py`
  - `core/auto_train/opencode_runtime.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/__init__.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/05-development-process/autonomous-training-implementation-readiness.md`
- 当前已新增 `study_status.json` 契约与本地 fallback builder：
  - `StudyStatusRecord`
  - `build_study_status(...)`
  - `markdown_from_study_status(...)`
- 当前真实 OpenCode 接入范围已扩展为：
  - `result-read` -> `result_summary.json`
  - `judge-trial` -> `decision.json`
  - `study-status` -> `study_status.json`
- 当前 `SUMMARIZE` 阶段会优先调用真实 `opencode result-read`：
  - 成功时直接落盘 `result_summary.json`
  - 失败或非法 JSON 时回退到本地 `summary.build_result_summary(...)`
- 当前 `NEXT_ACTION` 阶段会优先调用真实 `opencode study-status`：
  - 成功时落盘 `study_status.json` 并据此生成 `summary.md`
  - 失败或非法 JSON 时回退到本地 `study_status.build_study_status(...)`
- 当前仍未接入真实 runtime 的 OpenCode command 只剩：
  - `plan-dataset`
- 已新增回归覆盖：
  - `result-read` 命令构造
  - `study-status` 命令构造
  - 控制器成功使用真实 `result_summary.json`
  - 控制器成功使用真实 `study_status.json`
  - `result-read` 失败时回退到本地 summary
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_controller tests.python.test_auto_train_summary tests.python.test_auto_train_decision_protocol tests.python.test_root_cli`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 `110` 个 Python 测试通过

## 2026-04-05 落地实现 `opencode` runtime adapter（JUDGE 阶段）

- 已新增：
  - `core/auto_train/opencode_runtime.py`
  - `tests/python/test_auto_train_opencode_runtime.py`
- 已更新：
  - `core/auto_train/__init__.py`
  - `core/auto_train/controller.py`
  - `core/auto_train/cli.py`
  - `core/auto_train/decision_protocol.py`
  - `tests/python/test_auto_train_controller.py`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/05-development-process/autonomous-training-implementation-readiness.md`
- 当前已把真实 OpenCode 调用正式接入到 `JUDGE` 阶段：
  - `judge_provider = opencode` 时，控制器会调用 `opencode run --command judge-trial --format json`
  - 支持可选 `--attach <url>`、`--model <model>`、自定义 `opencode` binary 和超时
- 当前 CLI 已新增 OpenCode 运行时参数：
  - `--opencode-attach-url`
  - `--opencode-binary`
  - `--opencode-timeout-seconds`
- 当前真实 OpenCode 接入范围先只覆盖 `judge-trial`：
  - `SUMMARIZE` 仍由 Python 直接生成 `result_summary.json`
  - `study-status` 仍未接入真实 runtime
- 当前 runtime 失败不会卡死 study：
  - 进程失败 -> `fallback_runtime_error`
  - 超时 -> `fallback_runtime_error`
  - 空 stdout -> `fallback_runtime_error`
  - 非法 JSON / 非法 payload -> 继续走既有 fallback
- 已新增回归覆盖：
  - `judge-trial` 命令构造、cwd、timeout、attach/model 传递
  - OpenCode 成功返回时，控制器使用真实 `decision.json`
  - OpenCode 运行失败时，控制器回退到 rules fallback 并继续下一轮
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_opencode_runtime tests.python.test_auto_train_controller tests.python.test_auto_train_decision_protocol tests.python.test_root_cli`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 `107` 个 Python 测试通过

## 2026-04-04 落地实现 `auto-train` 控制器骨架

- 已新增：
  - `core/auto_train/controller.py`
  - `core/auto_train/cli.py`
  - `tests/python/test_auto_train_controller.py`
- 已更新：
  - `core/auto_train/__init__.py`
  - `core/cli.py`
  - `tests/python/test_root_cli.py`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/05-development-process/autonomous-training-implementation-readiness.md`
- 当前已新增正式入口：
  - `uv run sinan auto-train run <task> ...`
  - `uv run sinan auto-train stage <stage> <task> ...`
- 当前已把控制循环先收口为阶段胶囊：
  - `PLAN`
  - `BUILD_DATASET`
  - `TRAIN`
  - `TEST`
  - `EVALUATE`
  - `SUMMARIZE`
  - `JUDGE`
  - `NEXT_ACTION`
- 当前已把阶段边界固定为文件接力，而不是上下文接力：
  - 读 `study.json` / `trial/*.json`
  - 写本阶段工件
  - 阶段完成后立即退出
- 当前已实现的骨架能力：
  - 自动创建或恢复 study
  - 自动分配 `trial_0001` / `trial_0002`
  - 复用现成数据集或调用 dataset runner
  - 调用 train/test/evaluate runner
  - 生成 `result_summary.json`
  - 用 task policy 直接生成 `decision.json`
  - 更新 `leaderboard.json`、`best_trial.json`、`decisions.jsonl`
  - 继续下一轮或进入 `STOP`
- 当前 `JUDGE` 仍是 rules-only：
  - `provider = rules`
  - `model = policy-v1`
  - 尚未接真实 `opencode run --attach ...`
- 当前 `RETUNE` 仍是 fallback-only：
  - 通过 `optimize.build_optimization_plan(..., optuna_available=False)` 生成下一轮参数
  - 尚未接真实 `Optuna` driver
- 已新增回归覆盖：
  - 单轮达标后完成 study
  - `RETUNE` 后为下一轮写入新的 `input.json`
  - 根 CLI `auto-train` 分发
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_controller tests.python.test_root_cli`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 `103` 个 Python 测试通过

## 2026-04-04 落地完成 `TASK-AT-010` 自主训练实施准入验收

- 已新增：
  - `docs/04-project-development/05-development-process/autonomous-training-implementation-readiness.md`
- 已更新：
  - `docs/index.md`
  - `docs/04-project-development/05-development-process/index.md`
  - `docs/04-project-development/10-traceability/requirements-matrix.md`
- 当前已把 `TASK-AT-001` 到 `TASK-AT-009` 的验收结论、开放风险和补项清单收口为正式文档，不再只保留在口头说明或 `.factory` 记忆里
- 当前准入结论已明确为：
  - 允许进入自主训练控制器整合实现阶段
  - 这不等于功能已端到端完成或已通过训练机长流程验证
- 当前文档已把“允许进入实现”和“仍待实现”拆开：
  - 已冻结的契约、状态机、runner、summary、command/skill、policy、optimize 边界
  - 尚未完成的 `auto-train` 控制器整合、真实 `opencode` 联调、真实 `Optuna` driver 和训练机演练
- 当前已把剩余开放风险显式列出：
  - 主控制循环尚未整合
  - `opencode` 运行时未做端到端联调
  - `Optuna` 仍处于边界冻结阶段
  - 缺少 Windows + NVIDIA 长流程演练
- 当前已把后续补项清单显式列出：
  - `auto-train` CLI
  - 控制器整合
  - `opencode` runtime adapter
  - `Optuna` driver
  - E2E study 演练
  - 训练机恢复/停止/fallback 演练
- 本轮为文档和追踪矩阵同步，没有新增代码实现，也没有额外重跑测试；准入文档引用的最近全量回归结论仍为 `100` 个 Python 测试通过

## 2026-04-04 落地实现 `TASK-AT-009` Optuna 接入边界、pruning 与规则 fallback

- 已新增：
  - `core/auto_train/optimize.py`
  - `tests/python/test_auto_train_optimize.py`
- 已更新：
  - `core/auto_train/__init__.py`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
- 当前已把 `Optuna` 接入边界正式收口为代码契约：
  - `build_optimization_plan(...)`
  - `deterministic_fallback_parameters(...)`
  - `assess_pruning(...)`
  - `SearchSpace`
  - `OptimizationPlan`
  - `PruningRequest`
  - `PruningDecision`
- 当前已固定 `Optuna` 只在 `RETUNE` 决策下介入：
  - 非 `RETUNE` 决策直接返回 `engine=disabled`
  - `Optuna` 不允许覆盖 `PROMOTE_BRANCH`、`REGENERATE_DATA`、`ABANDON_BRANCH`
- 当前已固定允许搜索的参数空间：
  - `group1`
    - `model`: `yolo26n.pt`, `yolo26s.pt`
    - `epochs`: `100`, `120`, `140`, `160`
    - `batch`: `8`, `16`
    - `imgsz`: `512`, `640`
  - `group2`
    - `model`: `paired_cnn_v1`
    - `epochs`: `80`, `100`, `120`, `140`
    - `batch`: `8`, `16`
    - `imgsz`: `160`, `192`, `224`
- 当前已固定 pruning 与 no-improve 交互规则：
  - plateau 但未到 no-improve 上限：只 prune 当前候选，搜索继续
  - 达到 no-improve 上限：停止 `Optuna`，切回规则 fallback
  - 若规则层已判定 `PROMOTE_BRANCH` / `REGENERATE_DATA` / `ABANDON_BRANCH`：立即停止 `Optuna`
- 当前已固定 `Optuna` 不可用时的纯规则回退：
  - 若规则动作不是 `RETUNE`：直接执行规则动作
  - 若规则动作仍是 `RETUNE`：使用 deterministic fallback 参数继续下一轮
- 当前实现仍未把 `optuna` 加入运行时依赖；本轮先冻结边界与回退契约，避免在未接 driver 前把依赖和行为绑死
- 已新增回归覆盖：
  - `RETUNE` 才能进搜索
  - 两组搜索空间冻结
  - `Optuna` 缺失时回退到确定性参数
  - plateau pruning
  - no-improve 封顶后的规则 fallback
  - 规则边界覆盖 `RETUNE`
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_optimize tests.python.test_auto_train_decision_protocol tests.python.test_auto_train_policies`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 100 个 Python 测试通过

## 2026-04-04 落地实现 `TASK-AT-008` 自主训练 group1/group2 策略模块

- 已新增：
  - `core/auto_train/policies.py`
  - `tests/python/test_auto_train_policies.py`
- 已更新：
  - `core/auto_train/__init__.py`
  - `core/auto_train/decision_protocol.py`
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
- 当前已把两组自主训练策略正式收口为代码契约：
  - `group1`
    - 主指标：`map50_95`
    - 次指标：`recall`
    - 业务指标：`full_sequence_hit_rate`
    - plateau：最近 `3` 轮提升不足 `0.005`
  - `group2`
    - 主指标：`point_hit_rate`
    - 次指标：`mean_iou`
    - 惩罚项：`mean_center_error_px`
    - plateau：最近 `3` 轮提升不足 `0.01`
- 当前已固定首轮晋级/放弃规则：
  - `group1`
    - `PROMOTE_BRANCH`：`map50_95 >= 0.82`、`recall >= 0.88`、`full_sequence_hit_rate >= 0.85`
    - `REGENERATE_DATA`：弱类或顺序/序列失败持续存在
    - `ABANDON_BRANCH`：明显退化且 `map50_95 < 0.75`
  - `group2`
    - `PROMOTE_BRANCH`：`point_hit_rate >= 0.93`、`mean_iou >= 0.85`、`mean_center_error_px <= 8.0`
    - `REGENERATE_DATA`：命中率过低或 `low_iou`/`point_hits` 暗示数据契约问题
    - `ABANDON_BRANCH`：明显退化且 `point_hit_rate < 0.75`
- 当前 `decision_protocol` 的 fallback 已切到 task-specific policy：
  - 非法 JSON/非法 payload 不再使用粗粒度通用规则
  - 会根据 `group1/group2` 独立阈值返回 `PROMOTE_BRANCH / REGENERATE_DATA / ABANDON_BRANCH / RETUNE`
  - fallback evidence 中会保留 `policy_reason`
- 已新增回归覆盖：
  - 两组主/次/惩罚指标冻结
  - `group1` promote / regenerate / abandon
  - `group2` promote / regenerate / retune
  - decision fallback 与策略模块联动
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_policies tests.python.test_auto_train_decision_protocol`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 94 个 Python 测试通过

## 2026-04-04 落地实现 `TASK-AT-007` 自主训练 skills、`decision.json` schema 与 fallback

- 已新增：
  - `core/auto_train/opencode_skills.py`
  - `core/auto_train/decision_protocol.py`
  - `.opencode/skills/result-reader/SKILL.md`
  - `.opencode/skills/training-judge/SKILL.md`
  - `.opencode/skills/dataset-planner/SKILL.md`
  - `.opencode/skills/study-archivist/SKILL.md`
  - `tests/python/test_auto_train_opencode_skills.py`
  - `tests/python/test_auto_train_decision_protocol.py`
- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/__init__.py`
  - `.opencode/commands/result-read.md`
  - `.opencode/commands/judge-trial.md`
  - `.opencode/commands/plan-dataset.md`
  - `.opencode/commands/study-status.md`
- 当前已把自主训练首版 skill 数量正式冻结为 4 个：
  - `result-reader`
  - `training-judge`
  - `dataset-planner`
  - `study-archivist`
- 当前 skill 契约已固定到 Python 注册表与 `.opencode/skills/*/SKILL.md` 两层，避免技能职责只停留在设计文档
- 当前 skill 模板已统一要求：
  - 只读取附加文件
  - 不运行 shell 命令
  - 不请求训练执行权限
  - 只返回 JSON
- 当前已新增 `JudgeDecisionPayload`，把模型原始输出的 JSON schema 与最终落盘 `DecisionRecord` 分离
- 当前已实现 `parse_or_fallback_decision(...)`：
  - 合法 JSON 输出 -> 直接转成 `DecisionRecord`
  - 非法 JSON -> `fallback_invalid_json`
  - 非法动作/缺字段 -> `fallback_invalid_payload`
- 当前已实现首轮确定性 fallback：
  - 弱类或失败模式明显 -> `REGENERATE_DATA`
  - 明显退化 -> `ABANDON_BRANCH`
  - 持续改善且无显著失败 -> `PROMOTE_BRANCH`
  - 其他情况 -> `RETUNE`
- 当前 `.opencode/commands/*.md` 已与四个 skill 显式绑定，避免 command 名与 skill 名再度漂移
- 已新增回归覆盖：
  - skill 注册表数量与输出工件
  - `.opencode/skills/*/SKILL.md` front matter 与边界文本
  - 合法 decision 解析
  - 非法 JSON fallback
  - 非法动作 fallback
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_opencode_skills tests.python.test_auto_train_decision_protocol`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 86 个 Python 测试通过

## 2026-04-04 `group2` 全量切换到双输入 paired dataset 契约

- 已更新 Go 生成器 `group2`：
  - `generator/internal/slide/slide.go`
  - `generator/internal/slide/slide_test.go`
  - `generator/internal/dataset/build.go`
  - `generator/internal/app/make_dataset.go`
  - `generator/internal/app/make_dataset_test.go`
- 当前 `group2` 已从“矩形洞旧结构”切到“图案 mask 挖洞 + master/tile paired dataset”：
  - 缺口由同一图案 mask 在背景图上雕刻生成
  - `tile_image` 与 `master_image` 缺口保持同源
  - 训练导出不再写 `dataset.yaml/images/labels`
  - 正式训练入口改为 `dataset.json + master/ + tile/ + splits/*.jsonl`
- 已新增 Python 双输入执行链：
  - `core/train/group2/dataset.py`
  - `core/train/group2/runner.py`
  - `core/train/group2/service.py`
- 已更新 Python 入口与 runner：
  - `core/train/group2/cli.py`
  - `core/predict/cli.py`
  - `core/modeltest/cli.py`
  - `core/modeltest/service.py`
  - `core/auto_train/runners/train.py`
  - `core/auto_train/runners/test.py`
  - `core/ops/setup_train.py`
  - `core/cli.py`
- 当前 `uv run sinan train group2`、`predict group2`、`test group2` 已全部切到 paired-input runner，入口统一为 `dataset.json`
- 已同步更新正式需求/设计与用户入口文档，明确：
  - `group1` 正式合同为 `dataset.json + scene-yolo/query-yolo/splits` pipeline dataset
  - `group2` 正式合同为 paired dataset
- 已运行验证：
  - `go test ./internal/slide ./internal/dataset ./internal/app`
  - `uv run python -m unittest tests.python.test_training_jobs tests.python.test_prediction_and_model_test tests.python.test_auto_train_runners`
  - `uv run python -m unittest tests.python.test_setup_train tests.python.test_root_cli`

## 2026-04-04 落地实现 `TASK-AT-006` 自主训练 OpenCode commands 契约

- 已新增：
  - `core/auto_train/opencode_commands.py`
  - `.opencode/commands/result-read.md`
  - `.opencode/commands/judge-trial.md`
  - `.opencode/commands/plan-dataset.md`
  - `.opencode/commands/study-status.md`
  - `tests/python/test_auto_train_opencode_commands.py`
- 已更新：
  - `core/auto_train/__init__.py`
- 当前已把自主训练首版 OpenCode command 数量正式冻结为 4 个：
  - `result-read`
  - `judge-trial`
  - `plan-dataset`
  - `study-status`
- 当前 command 契约已固定到 Python 注册表与 `.opencode/commands/*.md` 两层，避免控制器依赖临时 prompt
- 当前已固定 headless 调用方式：
  - `opencode run --command <name> --format json`
  - 可选 `--attach <server-url>`
  - 使用多个 `--file <path>` 附加结构化工件
  - 最后传递 message arguments
- 当前 `.opencode/commands/*.md` 已固定 front matter：
  - `description`
  - `agent: plan`
  - `subtask: true`
- 当前四个 command 的输出工件已固定：
  - `result-read` -> `result_summary.json`
  - `judge-trial` -> `decision.json`
  - `plan-dataset` -> `dataset_plan.json`
  - `study-status` -> `study_status.json`
- 当前命令模板已统一要求：
  - 只读附加文件
  - 只返回一个 JSON 对象
  - 不输出 markdown fence
  - 不输出 JSON 之外的自然语言
  - 不请求 shell 访问
- 已新增回归覆盖：
  - command 注册表数量与输出工件
  - headless 调用参数拼装
  - `.opencode/commands/*.md` 文件内容与 front matter
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_opencode_commands`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 79 个 Python 测试通过

## 2026-04-04 落地实现 `TASK-AT-005` 自主训练结果摘要层

- 已新增：
  - `core/auto_train/summary.py`
  - `tests/python/test_auto_train_summary.py`
- 已更新：
  - `core/auto_train/contracts.py`
  - `core/auto_train/storage.py`
  - `core/auto_train/__init__.py`
- 当前已把 `result_summary.json` 正式固化为代码契约：
  - `ResultSummaryRecord`
  - `ResultSummarySnapshot`
- 当前 `result_summary.json` 已固定以下判断所需字段：
  - 当前 trial 基本信息
  - `primary_metric` / `primary_score`
  - `test_metrics`
  - `evaluation_metrics`
  - `failure_count`
  - `trend`
  - `delta_vs_previous`
  - `delta_vs_best`
  - `weak_classes`
  - `failure_patterns`
  - `recent_trials`
  - `best_trial`
  - `evidence`
- 当前已固定“最近 N 轮 + 最佳轮”压缩策略：
  - 最近 N 轮来自当前 trial 之前、且已存在 `result_summary.json` 的历史 trial
  - 最佳轮来自 `best_trial.json`
  - 摘要层只看结构化工件，不依赖长终端输出
- 当前已实现首轮压缩规则：
  - 可从 `per_class_metrics` 提取 `weak_classes`
  - group1 可压出 `sequence_consistency`、`order_errors`
  - group2 可压出 `point_hits`、`center_offset`、`low_iou`
  - 通用检测侧可压出 `detection_precision`、`detection_recall`、`strict_localization`
- 当前已实现趋势分类：
  - `baseline`
  - `improving`
  - `declining`
  - `plateau`
- 已新增回归覆盖：
  - 当前 trial 摘要字段
  - 最近窗口截断
  - best trial 读取
  - 弱类提取
  - 失败模式压缩
  - `result_summary.json` round-trip
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_summary`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 76 个 Python 测试通过

## 2026-04-04 落地实现 `TASK-AT-004` 自主训练 runner 适配层

- 已新增 `core/auto_train/runners/` 目录：
  - `core/auto_train/runners/__init__.py`
  - `core/auto_train/runners/common.py`
  - `core/auto_train/runners/dataset.py`
  - `core/auto_train/runners/train.py`
  - `core/auto_train/runners/test.py`
  - `core/auto_train/runners/evaluate.py`
- 已更新：
  - `core/auto_train/__init__.py`
- 当前已把控制器与现有执行入口的边界收口为四类 runner：
  - dataset runner：封装 `sinan-generator make-dataset`
  - train runner：封装现有 group1/group2 task-specific training job
  - test runner：封装现有 `predict + val + 中文报告`
  - evaluate runner：封装现有 JSONL 评估流程
- 当前 runner 层只负责执行与结果采集，不负责 AI 判断、状态机推进或排行榜更新
- 已新增统一的 runner 错误封装：
  - `RunnerExecutionError`
  - `stage`
  - `reason`
  - `retryable`
  - `command`
- 当前已固定的错误边界包括：
  - `missing_input`
  - `missing_launcher`
  - `missing_dependency`
  - `command_failed`
  - `invalid_request`
- 已新增回归覆盖：
  - `tests/python/test_auto_train_runners.py`
  - 覆盖 dataset runner 命令构造与工作区缺失
  - 覆盖 train runner 的 `from_run` 路径解析与非法请求
  - 覆盖 test runner 到 `TestRecord` 的归一化
  - 覆盖 evaluate runner 到 `EvaluateRecord` 的归一化与失败分类
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_runners`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 73 个 Python 测试通过

## 2026-04-04 落地实现 `TASK-AT-003` 自主训练目录蓝图、排行榜与恢复语义

- 已新增 `core/auto_train/` 第三批实现文件：
  - `core/auto_train/layout.py`
  - `core/auto_train/recovery.py`
- 已扩展自主训练状态契约与持久化层：
  - `core/auto_train/contracts.py`
  - `core/auto_train/storage.py`
  - `core/auto_train/state_machine.py`
  - `core/auto_train/__init__.py`
- 当前已把 study/trial 物理目录约定固化为代码路径助手：
  - `studies/<task>/<study_name>/study.json`
  - `best_trial.json`
  - `trial_history.jsonl`
  - `decisions.jsonl`
  - `leaderboard.json`
  - `summary.md`
  - `STOP`
  - `trials/trial_0001/...`
- 当前已把 trial 命名规则固定为 `trial_0001` 四位零填充，并为 `group1/group2` 提供独立 study 根目录路径，避免交叉覆盖
- 当前已新增排行榜与最佳 trial 契约：
  - `LeaderboardEntry`
  - `LeaderboardRecord`
  - `BestTrialRecord`
- 当前恢复逻辑已从“读取最高层已存在工件”升级为“按顺序完整性寻找最早缺失边界”：
  - 如果 `dataset.json` 缺失，即使 `train.json` 已存在，也会回退到 `BUILD_DATASET`
  - 如果 `decision.json` 已存在，当前 trial 视为完成并进入 `NEXT_ACTION`
  - `STOP` 文件仍然优先把恢复入口切到 `STOP`
- 已新增回归覆盖：
  - `tests/python/test_auto_train_layout.py`
  - 覆盖 study 路径蓝图
  - 覆盖 trial 命名规则
  - 覆盖 `leaderboard.json` 排序与 `best_trial.json` 落盘
  - 覆盖“中间工件缺失时回退重跑”的恢复语义
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_layout`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 66 个 Python 测试通过

## 2026-04-04 落地实现 `TASK-AT-002` 自主训练状态机与停止规则

- 已新增 `core/auto_train/` 第二批实现文件：
  - `core/auto_train/state_machine.py`
  - `core/auto_train/stop_rules.py`
- 当前已把自主训练阶段顺序固定为：
  - `PLAN`
  - `BUILD_DATASET`
  - `TRAIN`
  - `TEST`
  - `EVALUATE`
  - `SUMMARIZE`
  - `JUDGE`
  - `NEXT_ACTION`
  - `STOP`
- 当前已实现基于 trial 工件的恢复入口推断：
  - `input.json` -> `BUILD_DATASET`
  - `dataset.json` -> `TRAIN`
  - `train.json` -> `TEST`
  - `test.json` -> `EVALUATE`
  - `evaluate.json` -> `SUMMARIZE`
  - `result_summary.json` -> `JUDGE`
  - `decision.json` -> `NEXT_ACTION`
  - `STOP` 文件 -> `STOP`
- 当前已实现首轮停止规则：
  - trial 数上限
  - 小时数上限
  - no-improve 上限
  - 平台期检测
  - `STOP` 文件
  - fatal error
- 已新增回归覆盖：
  - `tests/python/test_auto_train_state_machine.py`
  - 覆盖阶段迁移、恢复入口、STOP 文件、预算停止、平台期和继续执行场景
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_state_machine`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 61 个 Python 测试通过

## 2026-04-04 落地实现 `TASK-AT-001` 自主训练状态契约

- 已新增 `core/auto_train/` 首批实现文件：
  - `core/auto_train/__init__.py`
  - `core/auto_train/contracts.py`
  - `core/auto_train/storage.py`
- 当前已把自主训练的核心状态工件固化成代码契约：
  - `study.json`
  - `input.json`
  - `dataset.json`
  - `train.json`
  - `test.json`
  - `evaluate.json`
  - `decision.json`
  - `trial_history.jsonl`
  - `decisions.jsonl`
- 已为以下关键约束增加校验：
  - `task` 只能是 `group1/group2`
  - `train_mode=from_run` 时必须提供 `base_run`
  - `decision` 只能落在允许动作集
  - `confidence` 必须位于 `0.0-1.0`
- 已新增回归覆盖：
  - `tests/python/test_auto_train_contracts.py`
  - 覆盖 study 嵌套字段 round-trip
  - 覆盖 trial JSON/JSONL 落盘回读
  - 覆盖非法 decision 拦截
  - 覆盖 `from_run` 缺少 `base_run` 的阻断
- 已运行验证：
  - `uv run python -m unittest tests.python.test_auto_train_contracts`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`
  - 当前 53 个 Python 测试通过

## 2026-04-04 将“自主训练控制器 + OpenCode 先行接入”落到正式需求、设计与任务文档

- 已把新增要求正式落到需求层：
  - `REQ-009` 自主训练控制器与 `opencode` 接入
  - `NFR-006` 自主训练可控性与上下文隔离
- 已同步更新：
  - `docs/04-project-development/02-discovery/input.md`
  - `docs/04-project-development/02-discovery/brainstorm-record.md`
  - `docs/04-project-development/03-requirements/prd.md`
  - `docs/04-project-development/03-requirements/requirements-analysis.md`
  - `docs/04-project-development/03-requirements/requirements-verification.md`
- 已把设计层收口为：
  - Python 控制器负责确定性执行与状态机
  - `opencode` 负责 commands / skills / 结构化判断
  - `Optuna` 负责可插拔参数搜索
  - group1/group2 保持独立 study 和独立指标
- 已新增设计与任务文档：
  - `docs/04-project-development/04-design/autonomous-training-and-opencode-design.md`
  - `docs/04-project-development/05-development-process/autonomous-training-task-breakdown.md`
- 已同步更新导航、追踪矩阵与 `.factory` 摘要，避免新设计停留在单页草稿

## 2026-04-04 生成器新增可配置视觉难度参数与 `hard` preset

- 已为 Go 生成器配置模型新增 `effects` 区块，正式支持：
  - `common`：`scene_veil_strength`、`background_blur_radius_*`
  - `click`：图标阴影透明度、阴影偏移、边缘模糊半径
  - `slide`：缺口阴影透明度、阴影偏移、滑块边缘模糊半径
- 已新增共享视觉扰动实现：
  - `generator/internal/imagefx/effects.go`
  - 统一承载 scene veil、box blur、shadow sprite 和确定性范围采样
- 已把 `group1` 与 `group2` 两条渲染链都接到新参数上：
  - `generator/internal/render/render.go`
  - `generator/internal/slide/slide.go`
- 已新增内置 `hard` preset：
  - `group1.hard.yaml`
  - `group2.hard.yaml`
- 已把 workspace preset 机制收口为固定命名自动覆盖：
  - `workspace\presets\smoke.yaml`
  - `workspace\presets\group1.firstpass.yaml`
  - `workspace\presets\group1.hard.yaml`
  - `workspace\presets\group2.firstpass.yaml`
  - `workspace\presets\group2.hard.yaml`
- `workspace init` 现在只会补齐缺失 preset，不再覆盖已有工作区覆盖文件
- `make-dataset` 当前会自动优先读取工作区同名 preset，找不到时回退内置 preset
- 已补充回归覆盖：
  - `generator/internal/config/load_test.go`
  - `generator/internal/preset/preset_test.go`
  - `generator/internal/render/render_test.go`
  - `generator/internal/slide/slide_test.go`
  - `generator/internal/app/make_dataset_test.go`
  - `generator/internal/workspace/workspace_test.go`
- 已同步更新帮助文本和公开用户文档：
  - `generator/cmd/sinan-generator/main.go`
  - `README.md`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
- 在需求变更后已继续补齐测试与正式设计文档：
  - 新增 `ResolveForWorkspace` 的回退、共享 `smoke.yaml` 覆盖和损坏配置报错测试
  - 已把像素级视觉增强边界、workspace preset 固定命名规则和 truth-preserving 约束同步写入 PRD、需求分析、需求校验、技术选型、系统架构和模块边界文档

## 2026-04-04 修复 `sinan test` 在 `val` 无 `results.csv` 时中文报告生成失败

- 已修复 `core/modeltest/service.py` 中对 Ultralytics `val` 产物的错误假设
- 旧逻辑会把 `results.csv` 当成 `val` 的必有文件，导致：
  - `predict` 成功
  - `val` 成功
  - 但中文报告在读取指标时中断
- 新逻辑已改为：
  - 优先读取 `results.csv`
  - 若 `results.csv` 不存在，则回退解析 `val` 终端输出中的 `P/R/mAP50/mAP50-95`
  - 只要验证命令成功并能识别汇总指标，就继续生成 `summary.md` 和 `summary.json`
- 已新增回归覆盖：
  - `tests/python/test_prediction_and_model_test.py`
  - 覆盖“无 `results.csv` 但终端输出含 `all` 汇总行”的真实兼容场景

## 2026-04-04 发布 `sinan-captcha 0.1.3` 到 PyPI

- 已把 Python 包版本从 `0.1.2` 提升到 `0.1.3`
- 已同步更新当前正式用户/维护者文档中的版本化安装示例：
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/windows-quickstart.md`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
- 已同步更新训练目录初始化默认版本与包内版本：
  - `pyproject.toml`
  - `core/__init__.py`
  - `core/ops/setup_train.py`
- 已同步更新回归断言与交付物文件名：
  - `tests/python/test_setup_train.py`
  - `tests/python/test_release_service.py`
- 已完成本地构建：
  - `dist/sinan_captcha-0.1.3-py3-none-any.whl`
  - `dist/sinan_captcha-0.1.3.tar.gz`
- 已完成 PyPI 上传：
  - `sinan-captcha 0.1.3`

## 2026-04-04 训练后测试入口、中文报告与续训命令补齐

- 已为训练目录新增两个正式用户入口：
  - `uv run sinan predict group1|group2`
  - `uv run sinan test group1|group2`
- `predict` 当前已支持默认路径机制：
  - `model` 默认指向 `runs/<task>/<train-name>/weights/best.pt`
  - `source` 默认指向 `datasets/<task>/<dataset-version>/yolo/images/val`
  - `project` 默认指向 `reports/<task>`
- `test` 当前会串联执行 `predict + val`，并在 `reports/<task>/test_<train-name>/` 下生成：
  - `summary.md`
  - `summary.json`
  - 终端中文摘要
- 已为训练 CLI 补齐两种续训口径：
  - `--resume`：从当前训练版本的 `weights/last.pt` 继续
  - `--from-run <旧训练名>`：从上一轮 `weights/best.pt` 新开一轮
- 已新增/更新 Python 回归覆盖：
  - `tests/python/test_prediction_and_model_test.py`
  - `tests/python/test_training_jobs.py`
  - `tests/python/test_root_cli.py`
- 已同步更新当前生效文档与记忆：
  - `README.md`
  - `docs/02-user-guide/use-and-test-trained-models.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `.factory/memory/current-state.md`

## 2026-04-04 删除 Python 数据集迁移链路并收口 dataset.yaml 责任

- 已删除 Python 侧旧数据集迁移命令与对应转换模块
- 当前正式口径已收口为：
  - `group1`：`dataset.json`、`scene-yolo/`、`query-yolo/`、`splits/`、`.sinan/` 只由 `sinan-generator make-dataset` 产出
  - `group2`：`dataset.json`、`master/`、`tile/`、`splits/`、`.sinan/` 只由 `sinan-generator make-dataset` 产出
  - Python `sinan` CLI 只消费现成 `dataset.json` 并负责训练、评估、环境初始化与发布
- 已同步修正 Go 生成器数据集导出：
  - `group1` 写出 `dataset.json + scene-yolo/query-yolo/splits`
  - `group2` 写出 `dataset.json + master/tile/splits`
- 已补充回归：
  - Python 根 CLI 不再接受旧数据集迁移命令
  - Go `make-dataset` 测试会校验 `group1 dataset.json` 及其子组件路径
- 已同步更新：
  - `core/cli.py`
  - `generator/internal/dataset/build.go`
  - `generator/internal/app/make_dataset_test.go`
  - `tests/python/test_root_cli.py`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`

## 2026-04-04 训练数据集路径解析兼容修复

- 已修正训练数据集导出契约：
  - `group1` 正式主入口改为 `dataset.json`
  - `group1` 的 `scene-yolo/query-yolo` 子数据集继续保留内部 `dataset.yaml`
  - `group2` 继续以 `dataset.json + master/tile/splits` 交接
- 已为训练 CLI 保留旧 YOLO YAML 兼容层：
  - 仅在内部调用 Ultralytics 时，为 `scene-yolo/query-yolo` 规范化生成兼容 YAML
  - 旧版 `group1 yolo/` 数据集不再是正式合同，但旧修复逻辑仍可作为迁移缓冲
- 已补充单测覆盖：
  - 新 `group1` 数据集会产出 `dataset.json + scene-yolo/query-yolo/splits`
  - 旧版 `path: .` 子 YAML 在训练前仍会被自动改写为可用的绝对数据集根
- 已同步更新：
  - `core/train/base.py`
  - `tests/python/test_training_jobs.py`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/04-project-development/04-design/generator-productization.md`

## 2026-04-04 训练机旧版 CLI 升级说明补齐

- 已把“训练机当前仍是 `0.1.1` 时如何升级到 `0.1.2`”补进正式用户指南
- 已明确推荐的升级路径是：
  - 重新执行 `uvx --from "sinan-captcha==0.1.2" sinan env setup-train ...`
  - 或在交付包场景下改为从新的 wheel 执行 `setup-train`
- 已明确升级行为：
  - 会重写训练目录里的 `pyproject.toml`
  - 会重新执行 `uv sync`
  - 不会删除既有 `datasets/`、`runs/`、`reports/`
- 已同步更新：
  - `docs/02-user-guide/windows-quickstart.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/use-build-artifacts.md`

## 2026-04-04 CUDA 13.x 支持、默认训练路径与 PyPI 版本升级

- 已修正 `core/ops/setup_train.py` 中的 PyTorch backend 自动映射：
  - `>= 13.0` 现在选择 `cu130`
  - `>= 12.8 && < 13.0` 继续选择 `cu128`
  - `>= 12.6 && < 12.8` 继续选择 `cu126`
  - `11.8` 继续选择 `cu118`
- 已把 `--torch-backend` 的可选值扩展到 `cu130`
- 已新增 Python 单测覆盖 CUDA 13.2 -> `cu130` 的自动映射
- 训练 CLI 已支持默认训练路径机制：
  - 在训练目录下可省略 `--dataset-yaml`
  - 在训练目录下可省略 `--project`
  - 新增 `--dataset-version <版本目录名>`，用于从 `datasets/<task>/<dataset-version>/yolo/dataset.yaml` 推导默认数据集路径
- 已把 Python 包版本从 `0.1.0` 提升到 `0.1.2`
- 已构建并上传：
  - `dist/sinan_captcha-0.1.2-py3-none-any.whl`
  - `dist/sinan_captcha-0.1.2.tar.gz`
  - PyPI 包版本：`sinan-captcha 0.1.2`
- 已同步更新当前生效的文档与终端示意图：
  - `docs/02-user-guide/how-to-check-cuda-version.md`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/assets/setup-train-terminal.svg`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/02-user-guide/windows-quickstart.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`

## 2026-04-03 用户指南结构重构与读者视角复审

- 已把公开用户指南重构为更清晰的阅读路径：
  - `docs/02-user-guide/windows-quickstart.md`
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
- 已按首次上手的 Windows 训练执行者视角复审文档，并补齐关键认知缺口：
  - 先解释“生成器安装目录 / 生成器工作区 / 训练目录”三层模型
  - 新增常用占位符说明：`<generator-root>`、`<generator-workspace>`、`<train-root>`、`<version>`
  - 显式补充“没有 `D:` 盘时如何替换盘符”
  - 显式补充生成器配置文件应放到 `D:\sinan-captcha-generator\configs\`
  - 显式补充旧版绝对路径 `dataset.yaml` 的识别与处理方式
  - 显式补充 `uvx --from sinan-captcha ...` 不要求本机先克隆源码仓库
- 已同步更新导航入口：
  - `README.md`
  - `docs/index.md`
  - `docs/01-getting-started/index.md`
  - `docs/02-user-guide/index.md`
- 当前公开文档已可支持一名第一次接触项目的 Windows 读者，按“快速开始”或“本地生成再训练”两条路线完成环境初始化、数据放置和训练启动

## 2026-04-04 交付包安装页与第三部分开发者指南重构

- 已补充用户侧交付包安装页：
  - `docs/02-user-guide/windows-bundle-install.md`
- 当前该页已明确说明：
  - 交付包典型结构
  - PyPI 路线与交付包 wheel 路线的区别
  - 当前版本对“完全离线安装”的真实边界
  - 训练目录创建完成后下一步应该跳转到哪一页
- 已补充两张终端示意图资源：
  - `docs/02-user-guide/assets/setup-train-terminal.svg`
  - `docs/02-user-guide/assets/train-smoke-terminal.svg`
- 已把第三部分“开发者指南”从占位结构扩展为 4 条主线：
  - `docs/03-developer-guide/index.md`
  - `docs/03-developer-guide/maintainer-quickstart.md`
  - `docs/03-developer-guide/repository-structure-and-boundaries.md`
  - `docs/03-developer-guide/local-development-workflow.md`
  - `docs/03-developer-guide/release-and-delivery-workflow.md`
- 已把开发者文档收口到维护者真正会使用的主题：
  - 新维护者接手顺序
  - 仓库与运行目录边界
  - 本地修改、验证、同步文档与 `.factory` 的闭环
  - Python 包、Go 二进制和 Windows 交付包的发布流程
- 已同步更新：
  - `README.md`
  - `docs/index.md`
  - `docs/01-getting-started/index.md`
  - `docs/02-user-guide/index.md`

## 2026-04-03 文档读者视角收口与仓库忽略规则修正

- 已按读者视角重审公开文档，并收口到统一目录心智模型：
  - 生成器安装目录
  - 生成器工作区
  - 训练目录
- 已修正文档中容易混淆的点：
  - 不再把 `sinan-captcha-generator` 直接描述成工作区本身
  - 显式说明 Windows 默认工作区仍落在 `%LOCALAPPDATA%\\SinanGenerator`
  - 公开命令示例统一补上 `sinan-generator --workspace <generator-workspace>`
- 已同步更新：
  - `README.md`
  - `configs/workspace.example.yaml`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/how-to-check-cuda-version.md`
  - `docs/04-project-development/07-release-delivery/index.md`
  - `.factory/memory/current-state.md`
  - `.factory/memory/tech-stack.summary.md`
- 已修正忽略规则，避免下列运行时产物继续进入 Git：
  - `materials/manifests/backgrounds.csv`
  - `materials/manifests/icons.csv`
  - `materials/quarantine/`

## 2026-04-03 生成器产品化与训练 CLI 交接面收口

- 已新增生成器产品化规范文档：
  - `docs/04-project-development/04-design/generator-productization.md`
- 已把生成器与训练 CLI 的正式交界面收口为：
  - `group1` 生成器输出 `dataset.json`、`scene-yolo/`、`query-yolo/`、`splits/` 与 `.sinan/`
  - `group2` 生成器输出 `dataset.json`、`master/`、`tile/`、`splits/` 与 `.sinan/`
  - 训练 CLI 统一消费 `--dataset-config <dataset-dir>/dataset.json`
- 已重写 Go 侧生成器入口：
  - `workspace init|show`
  - `materials import|fetch`
  - `make-dataset`
- 已新增固定工作区能力：
  - 首次启动自动创建默认工作区
  - 默认工作区展开 `presets/`、`materials/`、`cache/`、`jobs/`、`logs/`
  - 不再支持 EXE 同级便携模式
- 已新增素材产品层：
  - 可把本地素材目录导入工作区
  - 可把 zip 包或远程地址同步到 `materials/official/`
  - 工作区会维护当前激活素材集
- 已新增 Go 侧数据集导出层：
  - 生成器内部直接把 raw batch 导出成 YOLO 数据集目录
  - `dataset.yaml` 曾写入 `path:` 字段，现已废止
  - `.sinan/raw/`、`manifest.json`、`job.json` 保留审计线索，但不参与训练 CLI 输入
- 已更新公开文档与设计文档，移除旧的公开口径：
  - `README.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/04-project-development/04-design/module-structure-and-delivery.md`
  - `docs/04-project-development/04-design/graphic-click-generator-design.md`
  - `docs/04-project-development/04-design/api-design.md`
- 已新增/通过 Go 回归：
  - `generator/internal/workspace/workspace_test.go`
  - `generator/internal/materialset/store_test.go`
  - `generator/internal/app/make_dataset_test.go`
- 已完成命令级冒烟：
  - `go run ./cmd/sinan-generator workspace init --workspace /tmp/sinan-generator-smoke-workspace`
  - `go run ./cmd/sinan-generator make-dataset --task group1 --preset smoke --workspace /tmp/sinan-generator-smoke-workspace --materials-source /Users/uroborus/AiProject/sinan-captcha/materials --dataset-dir /tmp/sinan-generator-smoke-dataset`
- 回归验证通过：
  - `GOCACHE=/tmp/sinan-go-build go test ./...`

## 2026-04-03 本地发布与训练目录初始化

- 已新增训练扩展依赖：`sinan-captcha[train]`
- `torch` 继续不直接打进主包，而是由训练目录运行时 `pyproject.toml` 根据检测到的 CUDA 后端安装
- 已新增 `core/ops/setup_train.py`，提供：
  - `uvx --from sinan-captcha sinan env setup-train`
  - 自动检测 `nvidia-smi` / CUDA 版本
  - 输出中文摘要并在确认后创建独立训练目录
  - 自动生成 `.python-version`、`pyproject.toml`、`README-训练机使用说明.txt`
  - 自动执行 `uv sync`
- 已明确分离两个运行目录：
  - 生成器目录：`sinan-generator.exe`、配置、`materials/`
  - 训练目录：运行时 `pyproject.toml`、`.venv`、`datasets/`、`runs/`、`reports/`
- 已新增本地发布 CLI：
  - `uv run sinan release build`
  - `uv run sinan release publish --token-env PYPI_TOKEN`
  - `uv run sinan release package-windows`
- 已新增 Windows 交付打包能力，可把 wheel、生成器二进制、配置和可选资产整理成独立交付包
- 已把训练前依赖缺失提示改成中文引导，明确提示先创建训练目录并执行 `uv sync`
- 已将 `dataset.yaml` 的 `path:` 改为相对路径写法（该方案后续已废止）
- 已新增 Python 单测覆盖：
  - 发布 CLI 分发
  - 本地发布服务
  - 训练目录初始化
  - 训练目录运行时数据集契约
- 回归验证通过：
  - `/Users/uroborus/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12 -m unittest discover -s tests/python -p 'test_*.py'`
  - `GOCACHE=/tmp/sinan-go-build-cache go test ./...`
  - `git diff --check`

## 2026-04-03 双 CLI 边界重构与仓库净化

- 已重新对齐项目正式边界：
  - Go 生成器统一为 `sinan-generator`
  - Python 训练与数据工程统一为 `sinan`
- 已为 Go 生成器补齐 `init-materials`，让素材目录骨架初始化也由 Go CLI 负责
- 已删除旧的 `scripts/*` 薄包装入口，避免继续出现“一个功能一个脚本”的散乱入口形态
- 已删除过时的 Python generator runner，生成器与训练链路改为通过文件契约对接
- 已清理 `.cache/`、`materials_stage*/`、空脚本目录与 `__pycache__`，减少仓库噪音
- 已同步更新设计文档与记忆层，正式文档不再把旧脚本目录和旧命令名当作当前事实
- 已新增根 CLI 分发测试与 Go 素材脚手架测试
- 已重新构建交付物，当前有效产物为：
  - `generator/dist/generator/darwin-arm64/sinan-generator`
  - `generator/dist/generator/windows-amd64/sinan-generator.exe`
  - `dist/sinan_captcha-0.1.0-py3-none-any.whl`
  - `dist/sinan_captcha-0.1.0.tar.gz`
- 已重写公开文档，当前对外页面统一采用双 CLI 口径：
  - README
  - `docs/01-getting-started/index.md`
  - `docs/02-user-guide/index.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/use-and-test-trained-models.md`
- 已同步更新 `docs/index.md` 中的公开导航标题，使导航和正文保持一致
- 已将 Python 版本目标统一收口到 3.12，并同步更新 `pyproject.toml`、用户文档、内部设计文档和 Windows 环境清单
- 已清理构建产生的 `sinan_captcha.egg-info` 元数据目录，保持工作区净化
- 已把 Python 侧执行口径统一为 `uv`：安装使用 `uv pip`，运行使用 `uv run sinan` / `uv run yolo`

## 2026-04-03 首版真实素材与 firstpass 数据集

- 已完成首版真实 `materials/` 包构建并回填主目录：
  - `materials/manifests/classes.yaml`
  - `materials/manifests/backgrounds.csv`
  - `materials/manifests/icons.csv`
  - `materials/icons/<class>/001.png`
- 当前素材规模为 20 类 canonical icon 和 715 张可用背景图
- 修复生成阶段暴露出的坏背景图问题：
  - `generator/internal/material/validate.go` 从“只数图片文件”升级为“逐张完整解码校验”
  - 新增 `generator/internal/material/validate_test.go`
  - 新增截断 JPEG、坏背景图、坏图标三类回归用例
- 已隔离 5 张损坏背景图到 `materials/quarantine/backgrounds/`，并同步修正 `backgrounds.csv`，避免目录与 manifest 不一致
- 已重新编译 mac 生成器二进制并完成 firstpass 数据链路实跑：
  - `datasets/group1/firstpass/raw/group1_fp_0001`
  - `datasets/group2/firstpass/raw/group2_fp_0001`
  - 两批各生成 200 条样本
- 两批原始样本 QA 均通过：
  - click：`query=200`、`scene=200`、`labels=200`
  - slide：`master=200`、`tile=200`、`labels=200`
- 已完成正式训练数据导出：
  - `datasets/group1/firstpass`
  - `datasets/group2/firstpass`
  - 两批均为 `train=160`、`val=20`、`test=20`
  - 其中 `group1` 当前正式合同已升级为 `dataset.json + scene-yolo/query-yolo/splits` pipeline dataset
- 当前仍未进入正式训练，原因是本机 Python 环境缺少 `torch` 与 `ultralytics`

## 2026-04-03 PyPI/CLI 收口

- 已把 Python 训练与数据工程入口收口为统一总 CLI：`sinan`
- 当前子命令包括：
  - `uv run sinan env check`
  - `uv run sinan materials build`
  - `uv run sinan dataset validate`
  - `uv run sinan autolabel`
  - `uv run sinan evaluate`
  - `uv run sinan train group1`
  - `uv run sinan train group2`
- 已把 Go 生成器正式入口收口为 `sinan-generator`
- `core/train/base.py` 的训练命令已改为通过 `uv run yolo` 启动，避免 Python 侧再出现绕开 `uv` 的直接执行入口
- `core/train/group1/cli.py` 与 `core/train/group2/cli.py` 现在默认会直接启动训练，并支持：
  - `--dry-run`
  - `--epochs`
  - `--batch`
  - `--imgsz`
  - `--device`
- 已新增 Python 自动标注、评估与环境检查入口
- 已删除原 `scripts/convert/*`、`scripts/autolabel/run_autolabel.py`、`scripts/evaluate/evaluate_model.py` 等薄包装入口
- 已新增训练 CLI 单测并通过；Python 全量测试通过，共 28 个测试
- 已完成本地分发构建验证，`dist/` 下已产出：
  - `sinan_captcha-0.1.0.tar.gz`
  - `sinan_captcha-0.1.0-py3-none-any.whl`
- 当前仍未实际上传 PyPI；还需要 PyPI 发布凭据和最终包名确认

## 2026-04-03 Windows 训练机文档重构

- 已将 `docs/02-user-guide/from-base-model-to-training-guide.md` 重构为面向 Windows 训练机的完整操作文档
- 新文档主线已覆盖：
  - 从其他机器拷贝 wheel 与 YOLO 数据集
  - 修正 `dataset.yaml` 路径
  - 安装驱动、`uv`、Python 3.12、PyTorch GPU
  - 安装本地 wheel 与训练依赖
  - 执行 `uv run sinan env check`
  - 运行冒烟训练与正式训练
- 已同步更新：
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/04-project-development/05-development-process/windows-environment-checklist.md`
- 当前公开用户路径已不再要求读者先理解内部开发过程文档，就可以在 Windows 训练机上完成安装与训练

## 2026-04-04 公开使用指南纠偏

- 已复查 `README.md`、入门页和主要用户指南，清理生成器产品化之后残留的旧口径
- 已从普通用户路径中移除“手工拷贝 `configs/*.yaml` 到 EXE 同级目录”的过时要求
- 已把素材准备口径统一为：
  - 本地 `materials-pack/`
  - 本地 `materials-pack.zip`
  - 可访问的素材包下载地址
- 已把 `uv run sinan materials build` 从生成器主链路中降级为非普通用户默认路径
- 已同步修正以下公开页面：
  - `docs/02-user-guide/prepare-training-data-with-generator.md`
  - `docs/02-user-guide/use-build-artifacts.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/windows-bundle-install.md`
  - `docs/02-user-guide/user-guide.md`
  - `docs/01-getting-started/index.md`
  - `README.md`
- 已继续复查开发者与交付文档，并同步修正 `release package-windows`：
  - 交付包不再默认复制 `generator/configs/`
  - 交付包说明改为“单 EXE + 可选素材/数据集”
  - 开发者文档已统一到“安装目录不要求手工维护 `configs/*.yaml`”
- 已补齐生成器用户指南中的高频实操问题：
  - PowerShell 下应使用 `.\sinan-generator.exe`
  - 如何判断素材包结构是否合格
  - 如何补齐/增加素材并保留素材版本
  - 如何通过 `PEXELS_API_KEY` + `materials-pack.toml` 构建远程素材包
  - `smoke=20`、`firstpass=200` 的生成规模说明
  - 如何多次生成不同版本数据集，以及数据集可重复用于多轮训练
- 已补齐训练后验证指南中的“第一次训练完成后先看什么”和“同一份数据集可重复训练”说明
- 已继续把同类说明补到：
  - `docs/02-user-guide/windows-quickstart.md`
  - `docs/02-user-guide/from-base-model-to-training-guide.md`
  - `docs/02-user-guide/user-guide.md`
- 现在快速开始、完整训练手册和总览页都已对齐：
  - 训练后第一眼看哪里
  - 同一份数据集可以重复训练
  - 需要更多数据时应新建数据版本，而不是覆盖旧目录
- 已把命令行帮助和交付包说明同步到当前口径：
  - `sinan-generator --help` 现在明确提示 PowerShell 用 `.\sinan-generator.exe`
  - 帮助文本已补充素材来源、默认预设规模和 `--force` 覆盖语义
  - `README-交付包说明.txt` 现在包含工作区初始化、素材导入/抓取、样本规模和覆盖规则
- 已继续收口仓库首页 `README.md`：
  - 用户入口前置
  - 典型命令改为用户视角
  - 开发者信息后置
  - 移除首页上的维护者工作流干扰
- 2026-04-11：修正 `sinan materials audit-group1-query` 的 CLI 运行根语义，不再强制检查仓库根目录；当前相对路径按命令执行目录解释，默认路径会提示确认，批处理可用 `--yes` 接受默认路径。
- 2026-04-05：修复 `auto-train` 的 OpenCode JSON 输出稳定性，`result-read / judge-trial / plan-dataset / study-status` 命令模板补充明确 JSON 字符串示例，并恢复通过 prompt 点名本地 skill 的方式。
- 2026-04-05：新增 `core/auto_train/json_extract.py` 的轻量 JSON 修复逻辑，可容错模型输出中的键名引号缺失和尾逗号。
- 2026-04-05：`result-read` 命令补充 `dataset_version/train_name` 参数；控制器新增对 `ResultSummaryRecord` 缺失字段的 deterministic hydration，避免模型遗漏嵌套快照元数据时直接 fallback。
- 2026-04-05：已在本机真实 `opencode + ollama/gemma4:26b` 环境下完成 `study-status / judge-trial / plan-dataset / result-read` 端到端验证。

- 已继续收口 `docs/02-user-guide/index.md`：
  - 结构与 README 首页对齐
  - 先按起点选入口
  - 再给最短心智模型、最短流程和补充入口

## 2026-04-02

- 2026-04-11：完成 `TASK-G1-REF-008/011` 的首版正式收口。`core/release/solver_export.py` 已从 group2-only 扩到 `group1 + group2` 统一导出，当前可同时产出 `click_proposal_detector.onnx`、`click_query_parser.onnx`、`click_icon_embedder.onnx`、`slider_gap_locator.onnx`，并写出真实 `click_matcher.json` 配置。
- 2026-04-11：新增 `solver/src/sinanz_group1_runtime.py` 与 `solver/src/sinanz_group1_service.py`，让 `CaptchaSolver.sn_match_targets(...)` / `sn_match_targets(...)` 进入真实 ONNX Runtime 推理、embedding 全局 assignment 和歧义拒判链路，不再抛占位异常。
- 2026-04-11：同步更新 `solver/pyproject.toml` 的资源打包规则，改为通配收集 `resources/models/*.onnx*` 与 `resources/metadata/*.json`，确保后续 `stage-solver-assets` 后构建出来的 `sinanz` wheel 能携带完整新规范 group1 资产。
- 2026-04-11：补齐并通过定向测试：
  - `solver/tests/test_group1_runtime.py`
  - `solver/tests/test_group1_service.py`
  - `solver/tests/test_public_api.py`
  - `tests/python/test_solver_asset_contract.py`
  - `tests/python/test_solver_asset_export_group2.py`
  - `tests/python/test_release_cli.py`

- 2026-04-10：`scripts/crawl/ctrip_login.py` 已接入本地 `sinanz` solver；脚本当前不再随机选择滑块终点，而是先保存当前 `bg/gap`，再根据 `sn_match_slider(..., puzzle_piece_start_bbox=...)` 返回的位移换算真实拖动距离，并用轻微人类轨迹完成拖动。
- 2026-04-10：同步更新 `tests/python/test_ctrip_login_script.py`，把原来的随机拖动断言改为模型拖动流程，并新增 solver 位移到页面拖动距离的换算测试。
- 2026-04-10：`ctrip_login.py` 当前还新增了 `4=测试滑动` 模式；该模式只做一次 solver 拖动验证，成功时直接打印结果，失败时打印当前验证码区域的页面响应信息，便于现场排查。

- 2026-04-10：撤销 `solver` 的 Rust 原生扩展路线，删除 `solver_native/` 与 `maturin` 打包方向；`sinanz` 当前重新收口为纯 Python wheel，运行时依赖为 `onnxruntime`。
- 2026-04-10：拉平 `solver/src/` 模块布局，并把非 `.py` 文件统一迁到 `solver/resources/`；当前公开运行链路为 Python 预处理 -> Python `onnxruntime` -> 业务结果封装。
- 2026-04-10：`solver/pyproject.toml` 已切回 `setuptools` 构建，`solver/resources/manifest.json` 与 `metadata/*.json` 的 `runtime_target` 已统一改为 `python-onnxruntime`。
- 2026-04-10：纯 Python `solver` 已在 `materials/solver/group2/reviewed` 的 `257` 组样本上跑完回归，结果为 `failure_count=8`、`point_hit_rate=0.9688715953307393`、`mean_center_error_px=6.155523243332449`、`mean_iou=0.8024894202411161`、`mean_inference_ms=19.014062256809336`。

- 2026-04-10：将 Rust 原生项目从 `solver/native/sinanz_ext/` 收平到仓库根 `solver_native/`，当前只保留一套 crate：`solver_native/Cargo.toml + solver_native/src/*`。
- 2026-04-10：将 `solver/pyproject.toml` 的构建后端切换为 `maturin`，并把 `manifest-path` 与 `native_extension_dir` 都改为指向 `../solver_native`；`sinanz` 交付包后续将按平台发布 wheel，而不是 `py3-none-any`。
- 2026-04-10：移除 `solver` Python 运行环境中的 `onnxruntime` 依赖，并删除 Python `onnxruntime` fallback 路径；当前 Python 只负责 group2 预处理，Rust 扩展负责真实 ONNX 推理。
- 2026-04-10：为 `solver_native/Cargo.toml` 补充 `pyo3`、`numpy`、`ndarray`、`ort` 以及 `python-extension / onnx-runtime` feature，并把 `match_slider_gap(...)` 的 Rust/Python 边界改为“接收预处理后的 numpy 张量 + 元数据”。
- 2026-04-10：同步更新 `solver/tests/test_native_project_layout.py`、`solver/tests/test_native_bridge.py`、`solver/tests/test_group2_service.py`、`solver/README.md` 和 `solver_native/README.md`，确保目录结构与运行责任边界一致。

- 2026-04-10：将 `materials/solver/group2/best.pt` 正式导出为 solver 标准资产，产物位于 `materials/solver/group2/exported/`，模型文件为 `models/slider_gap_locator.onnx`，当前 manifest/metadata 已统一到 `asset_version=20260410-group2`、`opset=18`。
- 2026-04-10：修正 `core/release/solver_export.py` 的 group2 ONNX 导出链路，改为使用 `torch.onnx` 新导出器并按模型真实参数名 `master / tile` 提供 `dynamic_shapes`，恢复正确输入契约：`master_image=1x1x192x192`、`tile_image=1x1x(tile_h)x(tile_w)`。
- 2026-04-10：新增 `stage-solver-assets` 交付动作，把导出资产复制到 `solver/src/sinanz/resources/`；`solver` 打包侧已能携带最新 group2 ONNX 资产。
- 2026-04-10：`solver/src/sinanz/native_bridge.py` 与 `solver/src/sinanz/group2/runtime.py` 已完成 group2 ONNX 接线；在 Rust 原生扩展缺席时，当前自动走 Python `onnxruntime` fallback，保证 `CaptchaSolver.sn_match_slider(...)` 可先稳定运行。
- 2026-04-10：新增 `scripts/eval_solver_group2_reviewed.py` 作为 reviewed 金标回归入口，并在 `materials/solver/group2/reviewed` 的 257 组样本上完成一次完整验证，结果为 `failure_count=8`、`point_hit_rate=0.9688715953307393`、`mean_center_error_px=6.155523243332449`、`mean_iou=0.8024894202411161`、`mean_inference_ms=5.612566147859922`。
- 2026-04-10：将 `solver` 的原生扩展模块路径从顶层 `sinanz_ext` 调整为包内 `sinanz.sinanz_ext`，修复了 `maturin` 因 `python-source = "src"` 与模块布局不匹配导致的构建失败。
- 2026-04-10：把 `solver_native` 的 `group2` ONNX 执行路径改为 Rust 真正执行，Python 只负责预处理并将 shape+slice 传给 `sinanz.sinanz_ext.match_slider_gap(...)`；同时去掉了 Python `onnxruntime` fallback。
- 2026-04-10：已在本机通过 `uvx maturin develop --uv` 成功编译并安装 `solver_native`，随后用 `solver/.venv/bin/python scripts/eval_solver_group2_reviewed.py --device cpu` 跑完 `257` 组 Rust 原生回归，结果为 `failure_count=8`、`point_hit_rate=0.9688715953307393`、`mean_center_error_px=6.21494371735901`、`mean_iou=0.7978065198298222`、`mean_inference_ms=6.078681322957198`。

- 2026-04-10：新增 `scripts/organize_group1_query_icons.py`，把真实 `group1` query 图切成单个小图标并按形状聚类；当前已在真实试卷集上整理出 `483` 个图标和 `156` 个 cluster。
- 2026-04-10：新增 `materials/incoming/group1_query_clusters/semantic_candidates.json`，收口前 32 个高频 cluster 的候选语义名与外部图标来源；同步新增 `scripts/download_group1_candidate_icons.py`，并已下载 23 个高置信 Tabler 候选图标到 `materials/incoming/group1_icon_candidates/`。
- 2026-04-10：新增 `scripts/build_group1_generator_icon_pack.py`，将候选图标继续扩展到 Lucide raw、Tabler outline/filled 变体，并把已确认语义的真实 query cluster 成员直接裁成透明 PNG 并入素材包；随后又把 `materials/incoming/old/` 纳入正式构建链，并把剩余模糊高频 cluster 拆分为 `icon_yen_shield`、`icon_letter_a_circle`、`icon_lantern`、`icon_knot`、`icon_seated_person`。最后一轮已让 old 扩类也能自动拉官方变体。当前 `materials/incoming/group1_icon_pack/` 已得到 47 个类、367 个 generator-ready PNG，其中 202 个来自真实 query 成员裁图，20 个来自旧图标目录；`cluster_025` 被确认为误切子部件，未纳入正式 class。
- 2026-04-10：优化生成器 `group1 query` 渲染，新增轻缩放、轻透明度漂移、1px 级抖动，并让 query 图标复用现有 `click.icon_edge_blur_radius_*` 轻模糊参数；相关 Go 回归已通过。

- 统一 Go 生成器接口，`generate` 命令新增 `--mode` 与 `--backend`
- 新增 `click/native` 与 `slide/native` 两类原生 backend 路径
- 在 JSONL 与 `manifest.json` 中补齐 `mode`、`backend`、`truth_checks`、滑块字段和 `asset_dirs`
- 新增 `gold` 真值硬门禁代码：一致性校验、重放校验、负样本校验
- Python `core/` 侧同步适配新的 group2 字段：`master_image`、`tile_image`、`target_gap`、`tile_bbox`、`offset_x`、`offset_y`
- 当日曾新增过 `scripts/export/export_group2_batch.py` 作为过渡入口，后续已在 CLI 收口中移除
- 回归验证通过：
  - `GOCACHE=/tmp/sinan-go-build-cache go test ./...`
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`

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
