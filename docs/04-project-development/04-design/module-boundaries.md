# 模块边界基线

- 项目名称：sinan-captcha
- 当前阶段：IMPLEMENTATION（设计基线维护）
- 当前技术栈：Python, PyTorch, Ultralytics YOLO, ONNX, ONNX Runtime, Rust, Windows, CUDA, X-AnyLabeling/CVAT, OpenCode, Optuna

## 边界设计原则

1. 先围绕最终 solver 交付面划模块，再围绕训练产线划内部模块。
2. 生成、数据治理、训练、评估、发布和求解必须解耦，避免一个脚本承担所有职责。
3. `group1` 与 `group2` 共用统一交付面，但内部训练和评估逻辑保持隔离。
4. bundle 只保留为训练仓库到独立 solver 项目之间的内部交接资产，不是最终用户交付物，也不是 `runs/` 的别名。
5. 控制器、commands/skills 和优化器各自有边界，不能互相越权。

## 模块清单

### MOD-001 统一求解合同与路由层

- 职责：
  - 维护统一请求/响应合同
  - 解析 `task_hint`
  - 根据输入形态执行确定性路由
  - 统一返回 `group1` / `group2` 结果
- 不负责：
  - 训练模型
  - 组装 bundle 文件
  - 维护原始训练目录

### MOD-002 bundle 管理与加载层

- 职责：
  - 维护 manifest schema
  - 校验导出资产目录和相对路径
  - 加载 `group1` / `group2` ONNX 模型与 matcher 配置
- 不负责：
  - 修改 bundle 内模型文件
  - 从 `runs/` 目录直接热取文件绕过 manifest

### MOD-003 发布与交付组装层

- 职责：
  - 构建 wheel / sdist
  - 组装 Windows 交付包
  - 组装平台相关 solver wheel
  - 产出交付说明和版本映射
- 不负责：
  - 重新训练模型
  - 直接执行推理

### MOD-004 生成器控制层

- 职责：
  - 统一 backend 选择、随机种子、batch 元数据和 preset
  - 统一导出 `group1` / `group2` 样本图片与真值
  - 执行真值校验和 batch QA
- 不负责：
  - 模型训练
  - 人工审核 UI
  - 最终 bundle 交付

### MOD-005 数据契约与版本管理

- 职责：
  - 定义 JSONL 主事实源
  - 维护类别表、版本元信息和切分规则
  - 维护 `gold / auto / reviewed` 状态
- 不负责：
  - 生成图片
  - 调用训练框架

### MOD-006 标注复核与数据转换层

- 职责：
  - 预标注导入
  - 审核与抽检结果汇总
  - 导出 `group1` pipeline dataset
  - 导出 `group2` paired dataset
- 不负责：
  - 训练模型
  - 发布 bundle

### MOD-007 `group1` 训练模块

- 职责：
  - 训练 `scene detector`
  - 训练 `query parser`
  - 管理 `group1` 训练超参数、日志和模型产物
- 不负责：
  - `group2` 训练
  - 最终交付打包

### MOD-008 `group2` 训练模块

- 职责：
  - 训练 paired locator
  - 管理 `group2` 训练超参数、日志和模型产物
- 不负责：
  - `group1` 训练
  - 最终交付打包

### MOD-009 推理后处理与业务映射层

- 职责：
  - `group1` 把 query/scene 结果映射成有序中心点序列
  - `group2` 把模型输出换算成中心点与辅助字段
  - 统一推理结果到业务字段
- 不负责：
  - 模型训练
  - 数据标注

### MOD-010 评估与报告模块

- 职责：
  - 计算任务级指标
  - 导出失败样本
  - 生成版本报告和对比摘要
- 不负责：
  - 训练调参决策
  - 修改正式标签

### MOD-011 自主训练控制器

- 职责：
  - 维护 study 生命周期、trial 编号、停止规则和恢复逻辑
  - 调用生成、训练、测试和评估入口
  - 校验 AI 决策并推进下一轮动作
- 不负责：
  - 直接解释业务结论
  - 直接接管 shell 做自由执行

### MOD-012 agent commands / skills 接入层

- 职责：
  - 通过 `opencode` commands / skills 承担结果摘要、判断、数据规划和 study 状态查看
  - 约束 AI 返回 JSON 契约和动作空间
- 不负责：
  - 直接持久化 study 主状态
  - 直接运行训练命令

### MOD-013 优化与策略层

- 职责：
  - 维护 `group1` / `group2` 目标函数
  - 定义参数搜索空间
  - 管理 `Optuna` 或规则 fallback
- 不负责：
  - 直接产出最终业务报告
  - 直接读取长终端日志作为唯一事实源

## 交付面与生产面的边界

### 交付面模块

- `MOD-001`
- `MOD-002`
- `MOD-003`
- `MOD-009`

这些模块共同决定调用方最终看到什么。

### 生产面模块

- `MOD-004`
- `MOD-005`
- `MOD-006`
- `MOD-007`
- `MOD-008`
- `MOD-010`
- `MOD-011`
- `MOD-012`
- `MOD-013`

这些模块共同决定 bundle 如何被持续生产出来。

## 推荐实现目录

```text
generator/
  cmd/
  internal/
core/
  cli.py
  release/
  solve/
  auto_train/
  dataset/
  autolabel/
  convert/
  train/
    group1/
    group2/
  inference/
  evaluate/
.opencode/
  commands/
  skills/
tests/
```

## 禁止耦合关系

- 统一求解层不得直接从 `runs/` 目录加载模型
- 发布层不得绕过 bundle 管理层直接拼装交付目录
- 自动标注模块不得绕过数据契约层直接写训练目录
- 评估模块不得直接篡改 `reviewed` 标签
- 生成器控制层不得直接依赖训练框架
- `opencode` commands / skills 不得直接接管训练 shell
- 控制器不得把 AI 输出当作无需校验的命令执行

## 错误与降级策略

- bundle 非法或缺文件时：
  - 在校验阶段阻断
  - 不进入求解流程
- 生成端无法证明真值正确时：
  - 阻断写入 `gold`
  - 回退到修正 backend 或显式 `auto` 路线
- 自动标注准确率不足时：
  - 阻断进入 `reviewed`
- `group1` 类别体系不稳定时：
  - 发起设计变更
  - 不在实现里临时热修业务合同
- AI 决策 JSON 非法或与当前状态冲突时：
  - 回退到规则模式
  - 当前 trial 仍需完整落盘
- 当前 `group2` 实现仍要求 `tile_start_bbox` 时：
  - 视为实现差距
  - 不反向修改最终业务合同定义
