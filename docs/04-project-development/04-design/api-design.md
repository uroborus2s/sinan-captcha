# 接口与入口基线

- 项目名称：sinan-captcha
- 当前阶段：DESIGN

## 设计结论

当前阶段不要求先实现公开 HTTP API。首版优先定义“内部入口合同”，包括：

- 数据导出入口
- 自动标注入口
- 数据转换入口
- 训练入口
- 评估入口

其中数据导出入口必须由生成器控制层统一接管，确保 `mode`、`backend`、`seed` 和真值校验结果一起进入批次记录。

如果未来需要把内部生成器升级成服务，再把这些入口映射成正式 HTTP 或 RPC API。

## API-001 数据导出合同

- 类型：内部函数 / 脚本入口
- 调用方：生成器适配层、数据工程脚本
- 输入：
  - 验证码类型
  - 生成模式：`click` / `slide`
  - backend：`native` / `gocaptcha`
  - 生成数量
  - 输出目录
  - 资源配置
- 输出：
  - 图片文件
  - JSONL 标签
  - 批次元数据
  - 真值校验结果

### 推荐命令形态

```bash
uv run python scripts/export/export_samples.py --task group1 --mode click --backend native --count 1000 --out datasets/group1/v1/raw
```

## API-002 自动标注合同

- 类型：内部函数 / 脚本入口
- 调用方：自动标注流水线
- 输入：
  - 原始样本目录
  - 标签主事实源
  - 模式：`rule` / `warmup-model`
- 输出：
  - `interim` 标签
  - 预标注统计

### 推荐命令形态

```bash
uv run python scripts/autolabel/run_autolabel.py --task group2 --mode rule --input datasets/group2/v1/raw --out datasets/group2/v1/interim
```

## API-003 数据转换合同

- 类型：内部函数 / 脚本入口
- 调用方：数据工程脚本
- 输入：
  - `reviewed` 标签
  - 目标任务
  - 类别表
- 输出：
  - YOLO 图片目录
  - YOLO 标签目录
  - `dataset.yaml`

### 推荐命令形态

```bash
uv run python scripts/convert/build_yolo_dataset.py --task group1 --version v1
```

## API-004 训练入口合同

- 类型：CLI 入口
- 调用方：训练执行脚本、维护者
- 输入：
  - `dataset.yaml`
  - 预训练权重
  - 训练超参数
- 输出：
  - 权重
  - 日志
  - 训练摘要

### 第二专项训练

```bash
uv run yolo detect train data=datasets/group2/v1/yolo/dataset.yaml model=yolo26n.pt imgsz=640 epochs=100 batch=16 device=0
```

### 第一专项训练

```bash
uv run yolo detect train data=datasets/group1/v1/yolo/dataset.yaml model=yolo26n.pt imgsz=640 epochs=120 batch=16 device=0
```

## API-005 评估入口合同

- 类型：内部函数 / 脚本入口
- 调用方：评估与报告模块
- 输入：
  - 模型权重
  - 测试集
  - 任务类型
- 输出：
  - 指标报告
  - 失败样本清单
  - 版本摘要

### 推荐命令形态

```bash
uv run python scripts/evaluate/evaluate_model.py --task group1 --weights runs/group1/v1/weights/best.pt --dataset datasets/group1/v1
```

## 未来 HTTP 服务的边界

如果未来需要把生成器升级成内部服务，建议只开放：

- `POST /generator/group1/generate`
- `POST /generator/group2/generate`
- `POST /generator/export-batch`

当前不设计：

- 对外公网服务契约
- 多租户鉴权
- 高可用部署拓扑

## 契约规则

- 命令行入口统一通过 `uv run`
- 图片和标签写盘后才视为成功
- 标签主事实源始终是 JSONL
- 任何入口的输出都要带批次标识
- `gold` 只有在真值一致性校验通过后才允许写盘
