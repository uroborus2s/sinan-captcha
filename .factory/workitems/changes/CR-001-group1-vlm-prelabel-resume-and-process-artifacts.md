# CR-001 `group1 prelabel-vlm` 断点续传与过程工件目录

- 状态：已确认
- 提出时间：2026-04-12
- 确认时间：2026-04-12
- 提出人：用户
- 负责人：Codex
- 影响范围：`uv run sinan train group1 prelabel-vlm`、`group1` 人工复核前预标注流程、VLM 过程审计与恢复语义
- 关联需求：`REQ-008`、`REQ-017`
- 关联设计：`docs/04-project-development/04-design/group1-instance-matching-refactor.md`
- 关联任务：`TASK-G1-REF-013`

## 1. 背景

当前 `group1 prelabel-vlm` 只能整批重跑：

- 任务中断后不能按逐样本恢复
- 已完成样本缺少正式“已完成”状态来源
- 同一 `--project` 目录重跑时，已完成图片不能稳定复用
- 原始大模型返回与归一化结果只保留聚合 JSONL，不利于按文件名抽查

这会直接抬高本地多模态预标注的时间成本和审计成本。

## 2. 变更目标

为 `group1 prelabel-vlm` 新增一套正式的逐样本过程状态目录，使其同时满足：

1. 支持同一 `--project` 目录自动恢复
2. 已完成样本不再重复调用大模型
3. 大模型请求、原始响应、归一化结果可按 `sample_id` 独立检查
4. 最终 `reviewed/*.json`、`labels.jsonl`、`trace.jsonl`、`summary.json` 仍保持现有对外产物职责

## 3. 冻结决定

### 3.1 正式过程目录

在 `prelabel-vlm` 的 `--project` 目录下新增：

```text
process/
  index.json
  samples/
    <sample_id>/
      status.json
      request.json
      response.json
      normalized.json
      error.json
```

说明：

- `process/` 是正式恢复入口
- `process/index.json` 是运行级索引
- `process/samples/<sample_id>/` 是逐样本过程目录
- 最终 `reviewed/`、`labels.jsonl`、`trace.jsonl`、`summary.json` 仍保留在 `--project` 根下

### 3.2 逐样本状态语义

- `pending`：已发现样本，但尚未请求模型
- `running`：当前样本正在执行中
- `completed`：模型原始响应和归一化结果均已落盘，且可用于最终汇总
- `failed`：本轮执行失败，保留错误信息供后续重试
- `partial`：存在不完整工件，不能作为已完成样本复用

### 3.3 恢复规则

- 同一 `--project` 目录重跑时，系统必须先读取 `process/index.json` 与 `process/samples/<sample_id>/status.json`
- 仅当 `status=completed` 且 `normalized.json` 完整存在时，才允许判定该样本已完成
- 已完成样本必须直接复用，不得再次调用大模型
- `failed`、`running`、`partial` 或缺失关键过程文件的样本，只允许重跑该样本本身
- `reviewed/*.json` 是否存在，不得单独作为“已完成”的唯一依据

### 3.4 过程工件职责

- `status.json`：记录样本状态、输入文件、时间戳、工件完整性和最近一次执行摘要
- `request.json`：记录发给大模型的请求上下文
- `response.json`：记录大模型原始响应
- `normalized.json`：记录归一化后的 `query_items` 与 `scene_targets`
- `error.json`：仅在失败时记录错误详情

### 3.5 最终聚合产物

任务完成后，系统必须基于逐样本过程工件重建：

- `reviewed/query/*.json`
- `reviewed/scene/*.json`
- `labels.jsonl`
- `trace.jsonl`
- `summary.json`

换言之，逐样本过程目录是恢复和审计的事实源，聚合文件是最终交付和人工复核辅助产物。

## 4. 非目标

- 本变更不把 `prelabel-vlm` 变成正式真值源
- 本变更不取消人工复核
- 本变更不要求修改 `group1 reviewed` 正式标签合同
- 本变更不改变 `query_item` / `scene=NN` 的最终人工审核格式

## 5. 后续动作

1. 在 PRD 中新增正式需求 `REQ-017`
2. 在 `group1` 重构设计中冻结过程目录与恢复语义
3. 在任务拆解中新增实现任务 `TASK-G1-REF-013`
4. 代码实现后补齐恢复回归测试、逐样本工件测试和汇总重建测试
