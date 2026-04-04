# 系统架构基线

- 项目名称：sinan-captcha
- 当前阶段：DESIGN
- 当前技术栈：Python, Ultralytics YOLO, Windows, CUDA, X-AnyLabeling/CVAT, OpenCode, Optuna, SQLite

## 架构结论

本项目的首版架构是“内部离线训练系统 + 自主训练控制平面”，不是线上验证码服务。生成器按“受控集成 + 可插拔 backend”实现，核心链路围绕训练数据闭环和 study 账本展开：

1. Python 控制器维护 study、trial、停止规则和恢复逻辑
2. `opencode` commands/skills 负责结果压缩、判断和归档建议
3. 生成器控制层选择模式与 backend
4. backend 生成候选样本和内部真值
5. 真值一致性校验与重放校验阻断坏样本
6. 合格样本以 `raw + JSONL gold` 形式落盘
7. 自动标注、抽检、转换、训练、评估继续复用现有训练主线

## 架构图

```mermaid
flowchart LR
    A["Study 配置 + 停止规则"] --> B["Python auto-train 控制器"]
    B --> C["OpenCode commands / skills"]
    B --> D["生成器控制层"]
    C --> E["结构化判断 JSON"]
    D --> F["backend 适配层"]
    F --> G["自有 native backend"]
    F --> H["go-captcha adapter backend"]
    G --> I["候选样本 + 内部真值"]
    H --> I
    I --> J["一致性校验 + 重放校验 + 负样本校验"]
    J --> K["raw + JSONL gold"]
    K --> L["自动标注流水线"]
    L --> M["interim auto 标签"]
    K --> N["人工复核 / 抽检"]
    M --> N
    N --> O["reviewed 标签"]
    O --> P["YOLO 数据转换"]
    P --> Q["第一专项训练"]
    P --> R["第二专项训练"]
    Q --> S["第一专项后处理"]
    R --> T["第二专项后处理"]
    S --> U["统一评估与报告"]
    T --> U
    U --> V["study 账本 + leaderboard + decisions"]
    V --> B
    U --> W["失败样本回灌池"]
```

## 主要组成

### 1. 生成器控制层

- 作用：统一模式选择、batch 管理、真值导出和阻断规则
- 控制模式：
  - 第一专项：图形点选
  - 第二专项：滑块缺口定位
- 控制职责补充：
  - 先解析内置 preset 与 workspace 固定命名覆盖
  - 先确定样本布局与 `gold` 真值
  - 再在渲染阶段施加 truth-preserving 的像素级视觉增强
- backend 候选：
  - 自有 native backend
  - `go-captcha` 适配 backend

### 2. 数据层

- `raw`：仅保存通过真值校验的原始图片与 `gold`
- `interim`：自动预标注结果
- `reviewed`：抽检通过数据
- `yolo`：训练派生产物
- `reports`：统计和质检报告

### 3. 算法层

- 第一专项：多类别检测
- 第二专项：滑块缺口定位
- 第二组规则法：预标注和对照，不是最终主交付

### 4. 评估层

- 第一专项指标：
  - 单目标点命中率
  - 整组顺序全部命中率
  - 平均点误差
  - 错序率
- 第二专项指标：
  - 点命中率
  - 平均点误差
  - IoU
  - 偏移误差
  - 推理时间

### 5. 自主训练控制平面

- Python 控制器：
  - 推进状态机
  - 调用 `sinan-generator` / `sinan` CLI
  - 落盘 study 与 trial 工件
  - 处理停止、恢复和 fallback
- `opencode`：
  - 通过 project-local commands 与 skills 承担结果查看、摘要压缩、下一轮判断和 study 归档建议
  - 不直接替代 Python 控制器
- `Optuna`：
  - 仅负责允许范围内的数值搜索与 pruning
  - 不负责业务规则判断

## 数据流说明

### 第一组

1. 生成器输出查询图、场景图、目标顺序、目标框、干扰项框
2. 同一份内部真值同时驱动渲染和标签导出
3. 若启用 `firstpass` / `hard` 或 workspace preset 覆盖，则只允许在渲染末端增加阴影、背景模糊、边缘软化等像素级扰动
4. 标签字段和几何语义不得因视觉难度 preset 而漂移
5. 通过一致性校验后写入 `gold`
6. 转换为多类别 YOLO 检测数据
7. 训练多类别检测模型
8. 用查询顺序将检测结果映射成点击点

### 第二组

1. 生成器输出主图、滑块图、缺口目标框、中心点和偏移量
2. 同一份内部真值同时驱动渲染和标签导出
3. 若启用 `firstpass` / `hard` 或 workspace preset 覆盖，则只允许在渲染末端增加缺口阴影、背景模糊、tile 边缘软化等像素级扰动
4. 标签字段和几何语义不得因视觉难度 preset 而漂移
5. 通过一致性校验后写入 `gold`
6. 转换为滑块定位训练数据
7. 训练滑块缺口定位模型
8. 输出目标框、中心点和偏移量

## 为什么不先做线上服务

- 当前目标是训练闭环，不是业务接入
- 先做线上服务会放大部署、鉴权、接口和运维复杂度
- 训练阶段需要的是“高质量标签”，而不是“对外稳定 SLA”

## 主要风险

- backend 无法稳定提供训练所需真值
- 第一组类别表不稳定
- 第二组滑块语义扩张为多缺口或轨迹任务
- 视觉难度增强若越过像素级边界，会直接破坏 `gold` 真值可信度
- Windows GPU 环境兼容问题
- 自动标注污染训练集
- agent 输出 JSON 失效、状态文件缺失或权限边界漂移会导致自主训练失控

## 架构守则

- 生成器控制层拥有训练契约与 gold 真值定义权
- backend 只能提供生成能力，不能反向定义 JSONL 主事实源
- 两专项模型独立训练与独立验收
- JSONL 是标签主事实源
- 测试集冻结，不随训练批次频繁变化
- AI 判断只消费摘要工件，不直接把长日志和整段历史上下文当成唯一事实源
