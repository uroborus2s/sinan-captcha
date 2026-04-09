# 角色与功能审核结论

这页先回答你这轮最关心的 3 个问题：

1. 生成器和训练 CLI 是否已经可用。
2. 自动化训练是否已经全部完成。
3. 现在该按什么角色去读用户文档。

## 1. 生成器 CLI 审核结论

结论：**对训练产线来说，核心能力已完成，可以直接使用。**

当前已经具备的稳定命令：

- `workspace init`
- `workspace show`
- `materials import`
- `materials fetch`
- `make-dataset`

这条线已经覆盖了训练者真正需要的动作：

- 初始化工作区
- 准备素材
- 生成 `group1` 训练数据
- 生成 `group2` 训练数据
- 通过 `preset` 和 `override-file` 控制样本规模与难度

本轮实测证据：

- `go test ./cmd/sinan-generator ./internal/app ./internal/config ./internal/dataset ./internal/materialset ./internal/render ./internal/truth ./internal/qa`

当前判断：

- 作为“训练数据生成入口”，生成器 CLI 已经达到可交付状态。
- 它现在的短板不是命令不存在，而是最终 solver 产线和模型训练还没全部完成。

## 2. 手动训练 CLI 审核结论

结论：**对训练机手动训练来说，主链路已完成，可以直接使用。**

当前已经具备的稳定命令：

- `uv run sinan env check`
- `uvx --from sinan-captcha sinan env setup-train`
- `uv run sinan train group1`
- `uv run sinan train group2`
- `uv run sinan predict group1|group2`
- `uv run sinan test group1|group2`
- `uv run sinan evaluate`

这条线已经覆盖了训练者真正需要的动作：

- 初始化训练目录
- 检查训练机环境
- 训练 `group1` / `group2`
- 续训或从上一轮继续训练
- 跑预测
- 跑一键测试
- 做 JSONL 级评估

本轮实测证据：

- `./.venv/bin/python -m unittest tests.python.test_root_cli tests.python.test_training_jobs`

当前判断：

- 作为“训练机人工执行主线”，训练 CLI 已经达到可交付状态。
- 这条线可以直接用于训练机文档主线。

## 3. 自动化训练 CLI 审核结论

结论：**已经达到“训练机可启动受控自动训练”的程度，但还不能写成“训练机无人值守正式入口”。**

当前已经完成的部分：

- study / trial 目录与账本工件
- `PLAN -> BUILD_DATASET -> TRAIN -> TEST -> EVALUATE -> SUMMARIZE -> JUDGE -> NEXT_ACTION`
- `dataset_plan` 到生成器 `--preset / --override-file` 的传递
- `EVALUATE` 自动接上 `TEST` 产物
- `max_hours` 真实计时预算
- `max_new_datasets` 停止约束
- `rules` judge
- `opencode` runtime 接口
- `Optuna` runtime 边界与 fallback

本轮实测证据：

- `./.venv/bin/python -m unittest tests.python.test_auto_train_contracts tests.python.test_auto_train_runners tests.python.test_auto_train_controller tests.python.test_auto_train_optimize tests.python.test_auto_train_optuna_runtime tests.python.test_auto_train_policies tests.python.test_auto_train_opencode_runtime`

当前还不能视为“全部完成”的原因：

- 还没有完成 Windows + NVIDIA 训练机上的长流程验收。
- 还没有形成“可长期无人看守”的正式运行结论。

当前判断：

- 适合在训练机上开始**受控自动训练 / study**。
- `rules` 路线当前不需要大模型，也不需要 `opencode`。
- `opencode` 路线当前默认使用训练目录自身的 `.opencode/commands` 与 `.opencode/skills`。
- 不适合现在就宣称为“完全自动化、可无人值守投产”的入口。

## 4. 推荐阅读路径

### 如果你是使用者

1. [使用者角色：安装与使用最终求解包](./use-solver-bundle.md)
2. [使用者角色：在自己的应用中接入并做业务测试](./application-integration.md)

### 如果你是训练者

1. [训练者角色：训练机安装](./windows-bundle-install.md)
2. [训练者角色：快速开始](./windows-quickstart.md)
3. [训练者角色：使用生成器准备训练数据](./prepare-training-data-with-generator.md)
4. [训练者角色：用 X-AnyLabeling 制作商业测试试卷答案](./prepare-business-exam-with-x-anylabeling.md)
5. [训练者角色：使用训练器完成训练、测试与评估](./from-base-model-to-training-guide.md)
6. [训练者角色：使用自动化训练](./auto-train-on-training-machine.md)

## 5. 一句话结论

- 生成器 CLI：可用。
- 手动训练 CLI：可用。
- 自动化训练 CLI：现在可以在训练机上开始受控使用，但还不是“无人值守正式入口”。
