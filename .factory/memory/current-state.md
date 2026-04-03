# 当前状态

- 当前模式：cli_direct
- 当前阶段：IMPLEMENTATION
- 活跃任务：0
- 活跃变更：0
- 活跃缺陷：0
- 活跃 PR：0

- 角色目录总数：9
- 当前阶段主要角色：项目协调者、方案架构师、文档与记忆管理员

- 当前技术画像：图形验证码专项模型设计画像
- 技术画像预设：custom
- 关键工程规则数：3
- 设计交付物数：6

## 当前事实

- 仓库已从种子文档阶段演进到实现骨架阶段，当前包含 Go 生成器工程、Python `core/` 包和正式设计文档
- 已完成历史项目纳管骨架补齐
- 已完成需求阶段并通过需求一致性校验
- 已新增一份可直接执行的“零基础落地实施方案”文档
- 已新增两个配套执行清单：环境搭建清单、样本导出与自动标注清单
- 已切换到设计阶段并补齐技术选型、模块边界、系统架构、入口设计首稿
- 已新增一份从基础模型、验证码服务到训练闭环的逐步实操手册
- 已新增一份生成器设计首稿，并在后续收口为覆盖图形点选与滑块两种模式的统一方案
- 已新增 CUDA 版本识别说明和生成器任务拆解，当前已具备进入实现前的文档前置条件
- 已将 `TASK-GEN-001` 到 `TASK-GEN-012` 细化为执行表，可直接用于排期和验收
- 已新增模块结构与构建交付设计，仓库目录、语言边界和交付形态已进一步明确
- 已完成 Python 核心包目录向 `core/` 的调整，并初始化了仓库骨架代码
- 已新增 `pyproject.toml`、`uv.lock`、`.gitignore`、`.python-version` 和根级 `README.md`
- 已新增 Go `generator/` 骨架、Python `core/` 核心包和最小测试
- 已按“仓库产物 / 训练工作目录”分离模型重构训练实操手册，移除 `go-captcha-service` 默认前置并对齐当前脚本状态
- 已按读者目标重构用户指南，形成两条公开路径：“使用项目编译结果”和“搭建训练环境并完成模型训练”，并将维护者入口迁移到开发者指南
- 已继续压缩训练主手册，拆出“训练完成后的模型使用与测试”公开页面，并修正自动标注与 JSONL 评估已具备离线入口的当前事实
- 已新增离线素材包构建工具，支持按配置批量下载背景图、提取官方图标并生成 `classes.yaml`，可直接落盘为生成器消费的 `materials/`
- 已将生成器设计正式收口为“受控集成 + 可插拔 backend”，统一明确控制层拥有训练契约与 `gold` 真值定义权
- 已将第二专项从“单类别目标定位”收口为“滑块缺口定位”，并补齐主图、滑块图、缺口框与偏移字段要求
- 已将“训练素材必须 100% 正确”落实为硬门禁：一致性校验、重放校验和负样本校验失败样本不得进入训练集
- 已完成生成器统一接口首轮实现：Go CLI 支持 `--mode/--backend`，控制层已接入 `click/native` 与 `slide/native`
- 已在导出契约中补齐 `mode`、`backend`、`truth_checks`、滑块字段和批次级 `asset_dirs`
- 已将 Python generator runner、转换、自动标注、评估链路同步到新的滑块字段命名，并保留最小兼容读取
- 已新增原生 slide backend 与 `gold` 校验单测，当前 Go/Python 回归均通过
- 已将生成器 `qa` 从“数量一致性检查”升级为“批次逐条审计”，会校验 `truth_checks`、样本结构、模式/backend 一致性、图片路径和尺寸
- 已完成首版真实 `materials/` 包构建：20 类 canonical icon、715 张可完整解码背景图，`classes.yaml`、`backgrounds.csv`、`icons.csv` 已同步落盘
- 已修复 `validate-materials` 漏检截断 JPEG 的问题，当前会对背景图和图标做完整解码校验，坏素材会在生成前被拦截
- 已隔离 5 张损坏背景图到 `materials/quarantine/backgrounds/`，并同步修正 `backgrounds.csv` 索引，避免素材目录与 manifest 漂移
- 已完成 `group1` click 和 `group2` slide 两批 firstpass 原始样本生成，各 200 条，批次 QA 全部通过
- 已完成 `datasets/group1/firstpass/yolo` 与 `datasets/group2/firstpass/yolo` 转换，两批数据均为 160/20/20 的 train/val/test 划分
- 当前训练数据链路已可用，但本机 Python 环境仍缺少 `torch` 与 `ultralytics`，尚不能直接启动训练
- 已将正式入口收口为两个 CLI：Go 侧 `sinan-generator`，Python 侧 `sinan`
- `sinan-generator` 当前负责 `workspace init|show`、`materials import|fetch`、`make-dataset`
- `sinan` 当前负责 `env check`、`env setup-train`、`dataset build-yolo`、`autolabel`、`evaluate`、`train group1`、`train group2`、`release build/publish/package-windows`
- 上述 Python 子命令统一通过 `uv run sinan ...` 形式调用，不再把直接执行 `sinan` 当作对外默认口径
- Python 侧执行口径已统一为 `uv`：安装使用 `uv pip`，运行使用 `uv run sinan` / `uv run yolo`
- 已新增独立训练目录初始化能力：`uvx --from sinan-captcha sinan env setup-train`
- 训练目录与生成器目录已正式分离：
  - 生成器工作区承载 `workspace.json`、`presets/`、`materials/`、`cache/`、`jobs/`、`logs/`
  - 训练 CLI 只消费数据集目录中的 `dataset.yaml`
  - 训练目录承载运行时 `pyproject.toml`、`.venv`、`runs/`、`reports/`
- 已新增本地发布与交付命令：`uv run sinan release build`、`uv run sinan release publish`、`uv run sinan release package-windows`
- 已将 `sinan-captcha[train]` 作为训练扩展依赖收口到 Python 包中，`torch` 继续通过训练目录运行时 `pyproject.toml` 和 PyTorch index 配置安装
- 已把生成器与训练 CLI 的交接面收口为 YOLO 数据集目录：`dataset.yaml`、`images/`、`labels/` 与 `.sinan/`
- 生成器产出的 `dataset.yaml` 统一采用相对路径 `path: .`，现在数据集可直接交给训练 CLI 使用
- 旧的 `scripts/*` 薄包装入口和分散命令名已移除，避免对外口径继续漂移
- 已重新构建正式交付物：
  - `generator/dist/generator/darwin-arm64/sinan-generator`
  - `generator/dist/generator/windows-amd64/sinan-generator.exe`
  - `dist/sinan_captcha-0.1.0-py3-none-any.whl`
  - `dist/sinan_captcha-0.1.0.tar.gz`
- 已完成本地 PyPI 分发构建验证，`dist/` 下已生成 `sinan_captcha-0.1.0.tar.gz` 与 `sinan_captcha-0.1.0-py3-none-any.whl`
- 当前本地发布命令已就位，仍需用户提供 `PYPI_TOKEN` 后执行实际上传
- 已将公开用户手册重构为面向 Windows 训练机的完整安装与训练文档，覆盖 wheel 交付、数据集放置、环境安装、自检、冒烟和正式训练
- 已把 Windows 环境 checklist 收口为配套核对表，避免用户在公开手册和内部过程文档之间来回切换
- 已按双 CLI 架构重写对外文档，README、入门页、用户指南、交付物页、Windows 训练手册和训练后验证页均已统一到当前正式命令与目录结构
- 已把公开文档进一步收口到“生成器安装目录 / 生成器工作区 / 训练目录”三层模型，避免把安装目录和工作区混成一个概念
- 公开文档中的生成器命令已统一显式示例 `--workspace <generator-workspace>`，并明确 Windows 默认工作区仍是 `%LOCALAPPDATA%\\SinanGenerator`
- 已将 Python 工程规则、公开文档和训练机说明统一收口到 Python 3.12
- 已将运行时生成的 `materials/manifests/backgrounds.csv`、`materials/manifests/icons.csv` 与 `materials/quarantine/` 收口为忽略项，避免运行素材索引和坏图隔离产物继续进入 Git

## 最近条目

- 任务：无
- 变更：无
- 缺陷：无

## 下一步建议

- 先校验忽略规则，确认运行时数据、构建产物和本地环境不会误入仓库
- 先确认 PyPI 发布 token 和远程仓库权限已就绪，再执行真正的发布动作
- 先把生成器 `make-dataset -> dataset.yaml` 的交接契约当作稳定基线保住
- 下一步先在目标训练机安装 `torch` 与 `ultralytics`，确认 `group1/group2 firstpass` 的训练命令可实际起跑
- 下一步补一条“生成器产出数据集 -> 训练 CLI dry-run”的跨边界回归，防止 `dataset.yaml` 契约再次漂移
- 下一步扩充图标变体和样本规模，把 firstpass 从流程验证批次提升到正式 warm-up 批次
- 下一步把素材包构建阶段也接入图片完整解码校验，避免坏图只在生成前才暴露
- 下一步继续补 slide 模式的视觉复杂度、抗规则化扰动和更多 QA 断言，再评估是否进入 `gocaptcha` adapter Spike
- 若 UX/UI 需要可视化评审，优先登记真实设计交付物而不是只写文字
- 若工作项进入收尾，确认关联 PR 已完成评审并合并
- 阶段切换前先更新正式文档，再刷新 `/.factory/memory/` 压缩记忆
