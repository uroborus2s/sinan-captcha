# 背景素材扩充任务拆解

- 当前阶段：IMPLEMENTATION（`REQ-016`）
- 关联需求：`REQ-016`、`NFR-004`
- 负责人：Codex
- 最近更新：2026-04-12

## 1. 任务目标

把现有 `materials collect-backgrounds` 升级为正式可维护背景池的增量能力：

1. 冻结“原图直送 VLM、不强依赖自动前景预处理”的正式策略。
2. 为逐图分析、风格汇总和下载任务流补齐可恢复 checkpoint。
3. 把下载任务模型改成“逐图保底 1 张 + 汇总扩充”。
4. 为汇总阶段补齐 schema 漂移 guardrail，支持 repair 重试和 fallback。
5. 为下载结果补齐质量门与重复抑制。
6. 增加把新背景图并入正式 `backgrounds/` 素材根的显式入口。
7. 补齐回归测试、用户文档和 AI 记忆同步。

## 2. 任务总表

| 任务 ID | 任务名称 | 负责人 | 主要输入 | 主要输出 | 完成标准 | 估算 |
| --- | --- | --- | --- | --- | --- | --- |
| TASK-MAT-BG-001 | 冻结背景扩充正式策略 | 项目维护者 | `REQ-016`、现有 `collect-backgrounds` | 设计说明、边界冻结 | 明确 V1 不以自动修补为主链路 | 0.5 天 |
| TASK-MAT-BG-002 | 实现逐图分析 checkpoint | Python 实现者 | 设计说明、现有背景分析链路 | `background-style-image-analysis.jsonl` | 已分析成功的参考图可复用且不重复跑模型 | 0.5 天 |
| TASK-MAT-BG-003 | 实现风格汇总缓存 | Python 实现者 | 逐图分析结果、汇总提示词 | `background-style-summary.json` | 汇总结果可单独保存并在输入不变时复用 | 0.5 天 |
| TASK-MAT-BG-004 | 实现逐图保底下载任务 | Python 实现者 | 逐图分析结果、汇总结果、现有下载链路 | `reference_image` + `summary` 任务模型 | 未被更小 `limit` 截断时，每张参考图至少 1 张下载目标 | 0.5 天 |
| TASK-MAT-BG-005 | 实现下载任务恢复 | Python 实现者 | 新任务模型、Pexels 下载链路 | `background-style-download-state.json` | task 任务流可记录进度并从中断页继续 | 0.5 天 |
| TASK-MAT-BG-006 | 实现下载质量门与重复抑制 | Python 实现者 | 设计说明、现有下载链路 | 图片解码、尺寸校验、重复检测、跳过原因记录 | 坏图、小图和重复图不会进入背景索引 | 0.5 天 |
| TASK-MAT-BG-007 | 实现正式 backgrounds 合并 | Python 实现者 | 目标素材根合同、背景索引格式 | `merge-into` 合并入口 | 可增量写入正式背景根且不破坏其他 manifest | 0.5 天 |
| TASK-MAT-BG-008 | 实现汇总 schema 漂移 guardrail | Python 实现者 | 汇总提示词、解析器、报告链路 | validator、repair、fallback、drift log | 大模型字段漂移不会直接中断整批任务 | 0.5 天 |
| TASK-MAT-BG-009 | 补齐 CLI、报告、测试与记忆同步 | Python 实现者/文档维护者 | 实现代码、现有 CLI 参考 | CLI 参数说明、报告字段说明、回归结果 | 用户可按文档恢复任务并理解状态文件 | 0.5 天 |

## 3. 执行顺序

1. `TASK-MAT-BG-001`
2. `TASK-MAT-BG-002`
3. `TASK-MAT-BG-003`
4. `TASK-MAT-BG-004`
5. `TASK-MAT-BG-005`
6. `TASK-MAT-BG-006`
7. `TASK-MAT-BG-007`
8. `TASK-MAT-BG-008`
9. `TASK-MAT-BG-009`

## 4. 验收要点

- 参考图中即使存在验证码前景干扰，也不要求先手工修图。
- 逐图分析完成后必须落盘；中断重跑时不得重复分析已完成图片。
- 下载任务必须先覆盖每张参考图的保底 1 张目标，再执行汇总扩充任务。
- 下载任务状态必须记录每个 task 的来源、目标数量、已完成数量和恢复页码。
- 汇总阶段若遇到大模型 schema 漂移，必须先尝试 repair；repair 无效时也不得以解析错误中断整批任务。
- 下载图片损坏、尺寸不足或重复时，命令必须明确记录跳过原因。
- 合并到正式素材根时，`backgrounds/` 与 `backgrounds.csv` 会增量更新，`group1/group2` manifest 保持不变。
- `dry-run` 仍然不触发下载和合并，但会落盘逐图分析和汇总结果。
