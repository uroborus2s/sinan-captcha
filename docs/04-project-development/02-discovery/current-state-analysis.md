# 当前状态分析

- 项目名称：sinan-captcha
- 仓库路径：`.`
- 分析时间：2026-04-01
- 当前阶段：REQUIREMENTS
- 本次目标：形成面向零基础用户的图形验证码专项模型训练方案

## 一句话基线

当前仓库是一个“已有种子知识、尚无实现资产”的项目：目录非空，因此不能走空仓初始化；已通过历史项目纳管补齐治理骨架，并转入需求阶段。

## 已识别的项目摘要

- 仓库当前仅有 `graphical_captcha_training_guide.md` 一份核心输入文档。
- 该文档已经明确当前问题不是 OCR，而是两类图形验证码定位任务。
- 用户已明确最终目标是训练 2 个专项模型，并让零基础用户可以在 Windows + NVIDIA 电脑上落地执行。

## 技术与工程线索

- 首选语言/生态：Python
- 首选训练框架：Ultralytics YOLO
- 首选运行环境：Windows + NVIDIA GPU
- 首选环境管理：`uv`
- 首选标注/复核工具：X-AnyLabeling 或 CVAT
- 参考项目：`dddd_trainer`、`captcha_trainer`

## 当前已知缺口

- 没有现成代码结构
- 没有数据集目录与标签 schema
- 没有环境版本说明
- 没有训练、评估和回灌流程
- 没有自动标注脚本或数据导出入口说明

## 当前阶段判断

当前最合适的阶段是 `REQUIREMENTS`，因为：

- 任务定义刚刚被明确，尚未形成正式 REQ/NFR
- 技术路线虽有倾向，但还未进入技术选型和模块设计细化
- 样本、自动标注、验收门槛都还需要先定义清楚
- 若现在直接编码，极易把问题错误实现成 OCR 或图像分类

## 建议的推进顺序

1. 固化需求、验收和数据契约
2. 进入设计阶段，明确技术选型和模块边界
3. 先实现样本导出和自动标注最小闭环
4. 再进入两专项模型训练

## 事实来源

- `graphical_captcha_training_guide.md`
- 用户本轮输入
- [dddd_trainer](https://github.com/sml2h3/dddd_trainer)
- [captcha_trainer](https://github.com/kerlomz/captcha_trainer)
