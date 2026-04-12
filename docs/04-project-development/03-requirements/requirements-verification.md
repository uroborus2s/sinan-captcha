# 需求一致性校验报告

## 最新校验

- 校验结果：通过
- 校验时间：2026-04-12 16:40:00
- 校验人：Codex
- 备注：已复核 `group1` 新设计口径、solver 输入兼容增量需求、背景素材扩充增量需求与 `prelabel-vlm` 逐样本恢复增量需求：正式路线保持实例匹配求解，并新增多输入形态、背景素材扩充和 `prelabel-vlm` 过程工件目录与断点续传能力；一级产品仍为统一验证码求解包/库
- PRD REQ 数：17
- 分析 REQ 数：17
- NFR 数：10

## 覆盖情况

- PRD 中的需求：REQ-001、REQ-002、REQ-003、REQ-004、REQ-005、REQ-006、REQ-007、REQ-008、REQ-009、REQ-010、REQ-011、REQ-012、REQ-013、REQ-014、REQ-015、REQ-016、REQ-017
- 需求分析中的需求：REQ-001、REQ-002、REQ-003、REQ-004、REQ-005、REQ-006、REQ-007、REQ-008、REQ-009、REQ-010、REQ-011、REQ-012、REQ-013、REQ-014、REQ-015、REQ-016、REQ-017

## 问题清单

- 当前未发现 PRD 与需求分析之间的编号遗漏或语义冲突。
- 当前已消除“训练工程优先”与“最终求解包优先”之间的需求层冲突。
- 当前已显式消除 `group1` “闭集类名主线”和“实例匹配主线”在需求层的冲突。
- 当前已把“旧方案必须在 cutover 后删除”正式写入 `REQ-014` 和 `NFR-010`，不再只保留为口头要求。
- 当前已把“solver 必须支持二进制/base64/网络 URL 与全格式解码兼容”正式写入 `REQ-015`，并补入安全边界（协议、大小、超时、重定向）约束。
- 当前已把“背景素材扩充主链路不强依赖不稳定预处理，而是原图直送 VLM + 逐图 checkpoint + 下载任务恢复 + 下载质量门 + 正式 backgrounds 合并”正式写入 `REQ-016`。
- 当前已把“`group1 prelabel-vlm` 必须支持逐样本过程工件、同目录断点续传、已完成样本跳过与按文件名审计原始返回”正式写入 `REQ-017`。
- 仍需在后续设计阶段继续同步：
  - `docs/04-project-development/04-design/system-architecture.md`
  - `docs/04-project-development/04-design/module-boundaries.md`
  - `docs/04-project-development/04-design/api-design.md`
  - `docs/04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md`
  - `docs/04-project-development/07-release-delivery/` 与 `08-operations-maintenance/` 下的细节文档

## 建议动作

- 需求层已经可以作为后续 `group1` 实例匹配重构的稳定基线继续使用。
- 下一轮应优先修订 solver 输入适配层设计与迁移任务拆解，并同步回归测试矩阵，避免“需求已加、实现口径未冻结”的二次漂移。
- 下一轮应优先补齐背景素材扩充断点续传设计、CLI 报告合同与正式素材根增量合并回归，避免实现口径再次漂移。
- 下一轮应优先实现 `REQ-017` 对应的逐样本过程目录、恢复状态机和聚合重建测试，避免 `prelabel-vlm` 继续停留在“中断即整批重跑”的弱语义。
