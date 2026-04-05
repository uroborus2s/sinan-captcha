# 设计交付物摘要

- 交付物数：9
- 最近更新时间：2026-04-05 19:10:00

## 已登记的关键设计交付物

- `technical-selection.md`
- `system-architecture.md`
- `module-boundaries.md`
- `api-design.md`
- `solver-asset-export-contract.md`
- `module-structure-and-delivery.md`
- `graphic-click-generator-design.md`
- `generator-productization.md`
- `autonomous-training-and-opencode-design.md`

## 最新设计基线

- 一级产品为统一验证码求解包/库
- 最终交付为 solver wheel + embedded ONNX assets + Rust native extension
- generator / training / auto-train 为模型生产平面
- `group1` 输出有序中心点序列
- `group2` 输出目标中心点，偏移量为辅助字段
- `TASK-SOLVER-MIG-006` 已冻结 ONNX 导出文件名、manifest 和 export_report 合同
- `TASK-SOLVER-MIG-008` 已接通 `group2` 的首条 `export-solver-assets` 导出实现和 `native_bridge` 契约
