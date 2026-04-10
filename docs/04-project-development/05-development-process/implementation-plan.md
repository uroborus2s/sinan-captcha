# 零基础落地实施方案

- 文档状态：草稿
- 当前阶段：DESIGN
- 目标读者：零基础训练操作者、项目维护者
- 负责人：Codex
- 上游输入：`graphical_captcha_training_guide.md`、`prd.md`、`requirements-analysis.md`
- 下游交付：设计阶段的技术选型、数据流水线和模块边界文档

## 1. 先说结论

这个项目的第一版不要做成 OCR，也不要做成一个统一大模型。最稳、最容易落地的路线是：

1. 先搭好一台 Windows + NVIDIA 单机训练环境。
2. 优先从自有验证码生成端直接导出标签，不要先做人工标框。
3. 第一专项重构为“候选检测 + 图标匹配”流水线，而不是多类别闭集检测。
4. 第二专项训练 1 个滑块缺口定位模型。
5. 自动标注优先级按下面顺序执行：
   - 生成器内部真值直出并通过校验
   - 第二组用规则法做滑块候选位置预标注
   - 第一组先做少量种子集，再训练候选检测器与预标注辅助链
6. 先把两个专项模型都跑通，再谈统一推理接口和后续优化。

## 2. 第一版成功标准

第一版不要求“最强模型”，要求“能稳定复现并继续迭代”。

- 环境目标：一台新 Windows + NVIDIA 电脑在 1 个工作日内搭建完成。
- 样本目标：
  - 第一组：训练 5000 对，验证 1000 对，测试 1000 对。
  - 第二组：训练 3000 对，验证 500 对，测试 500 对。
- 自动标注目标：每批 200 张抽检可用率不低于 97%；生成器直出 `gold` 样本必须 100% 通过真值校验。
- 训练目标：
  - 第一组：单目标点命中率 >= 98.5%，整组顺序全部命中率 >= 93%。
  - 第二组：点命中率 >= 95%，平均点误差 <= 8 像素，框 IoU 均值 >= 0.80，偏移误差均值 <= 6 像素。

## 3. 建议的 15 个工作日节奏

| 时间 | 目标 | 成功标志 |
|---|---|---|
| 第 1 天 | 电脑环境搭建 | `nvidia-smi` 正常，`torch.cuda.is_available()` 为 `True` |
| 第 2 天 | 固定样本目录和字段 | 第一组、第二组 JSONL 字段确定 |
| 第 3-4 天 | 跑通样本导出 | 能导出一批试验样本和标签 |
| 第 5 天 | 第二组滑块规则法预标注 | 200 张抽检基本可用 |
| 第 6-7 天 | 第一组种子集整理 | 300-500 张种子集完成纠正 |
| 第 8 天 | 第一组暖启动小模型 | 能批量预测出候选框 |
| 第 9-10 天 | 大批量自动标注 + 抽检 | 两组 reviewed 数据集成型 |
| 第 11-12 天 | 第二组正式训练 | 产出第一个可评估模型 |
| 第 13-14 天 | 第一组正式训练 | 产出第一个可评估模型 |
| 第 15 天 | 验收与归档 | 形成版本、指标、失败样本清单 |

## 3.1 新增第二阶段：自主训练控制器

在当前“人工可执行训练闭环”已经成立之后，新增第二阶段主线：

1. 先固定 `study` 契约、状态文件和停止规则。
2. 再接入 `opencode` 的 project-local commands 与 skills。
3. 再把结果压缩、判断、数据规划和归档拆成独立职责单元。
4. 最后接入 `Optuna` 做参数搜索，并把 group1/group2 策略分开。

这条主线的目标不是替代现有 CLI，而是把它们编排成可恢复的自动循环。实施顺序和验收任务见：

- [自主训练任务拆解](./autonomous-training-task-breakdown.md)

## 4. Windows 电脑上先准备什么

在开始之前，先确认这 6 件事：

1. Windows 10/11 可以正常更新，且你有管理员权限。
2. 有 NVIDIA 显卡，并且显存最好不少于 6GB。
3. 非系统盘至少有 100GB 可用空间。
4. 你能访问自有验证码生成服务、脚本或日志。
5. 你能接受先做小规模版本，不追求一步到位。
6. 你知道第一版的目标是“跑通闭环”，不是“论文级精度”。

建议在 Windows 上先建一个固定工作目录：

```text
D:\sinan-captcha-work\
  datasets\
    group1\
    group2\
  exports\
  runs\
  models\
  reports\
  tools\
```

## 5. 第一步：训练环境怎么搭

### 5.1 先装显卡驱动

先做这一步，不要急着装 Python。

1. 去 NVIDIA 官方驱动页面安装与你显卡匹配的稳定版驱动。
2. 安装后重启电脑。
3. 打开 PowerShell，执行：

```powershell
nvidia-smi
```

看到显卡型号、驱动版本、显存信息，说明显卡驱动正常。

如果这里就失败，先不要继续装任何 Python 包。

如果你想确认“CUDA 版本”具体怎么判断，按下面顺序看：

1. `nvidia-smi`
2. `uv run python -c "import torch; print(torch.version.cuda); print(torch.cuda.is_available())"`
3. 只有当你明确装过 CUDA Toolkit 时，再看 `nvcc --version`

这里要分清：

- `nvidia-smi` 里的 `CUDA Version` 是驱动支持版本
- `torch.version.cuda` 是当前 PyTorch 使用的 CUDA 构建版本
- `nvcc --version` 是本机 Toolkit 版本

零基础操作者优先看前两项，不要先被 `nvcc` 卡住。

### 5.2 安装 `uv` 和 Python

按 `uv` 官方文档，在 Windows 上安装 `uv`。最简单的方式通常是：

```powershell
winget install --id=astral-sh.uv -e
```

然后安装 Python 3.12：

```powershell
uv python install 3.12
```

说明：

- 截至 2026-04-01，PyTorch 官方 Windows 安装页支持 Python 3.10-3.14。
- 当前项目统一收口到 Python 3.12，避免仓库配置、文档与训练机环境再分叉。

### 5.3 创建虚拟环境

进入项目目录后执行：

```powershell
cd /d D:\sinan-captcha-work
uv venv --python 3.12
.\.venv\Scripts\activate
uv run python -V
```

### 5.4 安装 PyTorch GPU 版

不要自己猜 CUDA 包。按 PyTorch 官方 “Get Started” 页面选择：

- OS: Windows
- Package: Pip
- Language: Python
- Compute Platform: 选择与你机器兼容的 CUDA 版本

截至 2026-04-04，官方稳定页提供的 Windows 选项包含 `CUDA 11.8`、`CUDA 12.6`、`CUDA 12.8`、`CUDA 13.0`。

常见示例命令之一是：

```powershell
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

只有当你的选择器对应 `CUDA 11.8` 时才直接用这条。否则用页面生成的命令。

### 5.5 安装训练和数据处理依赖

```powershell
uv pip install ultralytics opencv-python numpy pandas pillow pyyaml matplotlib scikit-image tqdm
```

标注工具建议：

- 首选：X-AnyLabeling Windows 发布包
- 备选：多人协作用 CVAT

对零基础用户，第一版优先用 X-AnyLabeling，原因是本地启动更直接。

### 5.6 做环境自检

```powershell
uv run python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-gpu')"
uv run yolo checks
```

自检通过后，环境阶段结束。

## 6. 第二步：先把数据字段定死

不要一边导样本一边临时改字段。先把标签事实源定死。

### 6.1 第一组标签字段

第一组是多图标顺序点击，所以必须保存：

```json
{
  "sample_id": "g1_000001",
  "captcha_type": "group1_multi_icon_match",
  "query_image": "query/g1_000001.png",
  "scene_image": "scene/g1_000001.png",
  "targets": [
    {"order": 1, "class": "icon_house", "bbox": [20, 8, 42, 24], "center": [31, 16]},
    {"order": 2, "class": "icon_leaf", "bbox": [55, 10, 75, 26], "center": [65, 18]}
  ],
  "distractors": [
    {"class": "icon_boat", "bbox": [80, 12, 104, 28]}
  ],
  "label_source": "gold",
  "source_batch": "2026-04-01-export-01"
}
```

### 6.2 第二组标签字段

第二组是滑块缺口定位，所以至少保存：

```json
{
  "sample_id": "g2_000001",
  "captcha_type": "group2_slider_gap_locate",
  "master_image": "master/g2_000001.png",
  "tile_image": "tile/g2_000001.png",
  "target_gap": {
    "bbox": [148, 56, 206, 114],
    "center": [177, 85]
  },
  "offset_x": 148,
  "offset_y": 0,
  "label_source": "gold",
  "source_batch": "2026-04-01-export-01"
}
```

标签状态统一只允许三种：

- `gold`：生成器内部真值直出，且已通过一致性校验与重放校验
- `auto`：自动预标注生成，未审核
- `reviewed`：人工抽检/修正后确认可用

额外硬规则：

- 任一生成样本只要无法证明真值正确，就不得标记为 `gold`
- `gold` 失败样本不能“先拿去训练再说”

## 7. 第三步：样本从哪里来

### 7.1 最优方案：从生成端直接导出

这是最重要的建议。

如果验证码是你自己的系统生成的，最省事的做法不是截图后再标注，而是让生成逻辑直接把下面几样东西一起保存：

1. 查询图
2. 场景图
3. 目标类别
4. 目标顺序
5. 目标框和中心点
6. 干扰项框
7. 滑块缺口框、偏移量和随机种子

这一步做对了，后面大量人工工作都可以省掉。

但这里有一个比“省人工”更高的要求：

- 生成器直出的训练样本必须 100% 正确
- 不能靠图片后验反推
- 不能接受已知错误样本混入训练集

### 7.2 次优方案：拿不到生成端时怎么做

如果暂时拿不到生成端源码，不要直接开始几千张人工标框。按下面顺序做：

1. 先收集原始查询图和场景图。
2. 第二组先走规则法预标注。
3. 第一组先做 300-500 张种子集。
4. 用种子集训练一个小模型做暖启动。
5. 让暖启动模型批量预标注剩余数据。
6. 只对抽检失败或置信度低的样本做人工修正。

这条路线仍然属于“自动标注优先”，只是第一步需要少量人工启动。

## 8. 第四步：怎么做到“自动标注而不是纯人工”

### 8.1 第二组的自动标注最简单

第二组先不要上模型，先上规则法。

规则法流程：

1. 把场景图转灰度。
2. 提取高亮或接近白色的区域。
3. 做连通域或轮廓提取。
4. 用面积、宽高比、顶点数、形状相似度筛选候选区域。
5. 选出最像查询图轮廓的区域。
6. 输出 `bbox` 和 `center`。
7. 导入标注工具抽检。

这个流程的目的不是长期替代模型，而是：

- 快速做预标注
- 判断数据是不是可学
- 给第二专项模型准备初始数据

### 8.2 第一组的自动标注分两条路

#### 路线 A：能直接导出生成坐标

如果能从生成端导出坐标，第一组就不需要人工标注，直接生成 `gold` 标签。

这是第一优先级。

#### 路线 B：导不出坐标

如果拿不到生成端坐标，用“种子集 + 暖启动模型”路线：

1. 先人工纠正 300-500 张，不要一上来做 5000 张。
2. 第一组先固定 `asset_id` 与素材来源，不强依赖类名表。
3. 用这 300-500 张训练一个小候选检测模型，目标是“能把 query/scene 里的图标位置先框出来”。
4. 用这个暖启动模型去批量预测剩余几千张。
5. 将预测结果导入 X-AnyLabeling。
6. 人只需要修正明显错框、漏框和顺序字段；类别语义改为辅助信息，不再是正式验收主字段。

这才是第一组最现实的自动标注路线。

## 9. 第五步：数据集怎么组织

建议目录这样定：

```text
datasets/
  group1/
    v1/
      raw/
      interim/
      reviewed/
      proposal-yolo/
        images/
          train/
          val/
          test/
        labels/
          train/
          val/
          test/
        dataset.yaml
      embedding/
        queries/
        candidates/
        pairs.jsonl
        triplets.jsonl
      eval/
        labels.jsonl
      splits/
        train.jsonl
        val.jsonl
        test.jsonl
      dataset.json
      reports/
  group2/
    v1/
      raw/
      interim/
      reviewed/
      master/
        train/
        val/
        test/
      tile/
        train/
        val/
        test/
      splits/
        train.jsonl
        val.jsonl
        test.jsonl
      dataset.json
      reports/
```

规则：

1. 原始样本永不覆盖。
2. 自动标注结果放 `interim/`。
3. 审核通过后放 `reviewed/`。
4. 给训练框架转换后的结果放任务专属训练目录：
   - `group1` 放 `proposal-yolo/`、`embedding/`、`eval/`、`splits/` 与 `dataset.json`
   - `group2` 放 `master/`、`tile/`、`splits/` 与 `dataset.json`
5. 每次追加样本都开新版本，如 `v2`、`v3`。

## 10. 第六步：训练怎么开始

### 10.1 第二专项先训练

因为第二组最简单，适合先跑通整个流程。

示例命令：

```powershell
uv run sinan train group2 --dataset-version v1 --name v1 --epochs 100 --batch 16 --imgsz 192 --device 0
```

建议：

- 先用默认 paired model 初始化。
- 如果显存不够，把 `batch` 降到 `8` 或 `4`。
- 如果定位精度不足，再评估更大的 `imgsz` 或继续微调上一轮 `best.pt`。

### 10.2 第一专项后训练

第一组的正式目标改为实例匹配流水线：`scene proposal detector + icon embedder + matcher`。

示例命令：

```powershell
uv run sinan train group1 --dataset-config D:\sinan-captcha-work\datasets\group1\v1\dataset.json --name v1 --epochs 120 --batch 16 --imgsz 640 --device 0
```

训练入口后续应支持分别训练 proposal detector 和 embedder，推理阶段再做顺序映射：

1. 读取查询图中的目标顺序并切出 query 项。
2. 检测 scene 里的全部图标候选。
3. 对 query 项和 scene 候选做向量匹配与全局分配。
4. 输出每个目标的点击点坐标。

所以第一组验收时看的是“点位和顺序”，不是只看检测框。

## 11. 第七步：每一轮都要做什么验收

### 11.1 第二组验收

至少看 4 个指标：

- 点命中率
- 平均点误差
- 框 IoU
- 单张平均推理时间

### 11.2 第一组验收

至少看 4 个指标：

- 单目标点命中率
- 整组顺序全部命中率
- 平均点误差
- 错序率

只要“整组顺序全部命中率”还很低，就不要急着追求更多 epoch，先查：

1. query 切分是否错位
2. 候选检测是否漏检
3. 相似图标是否发生向量混淆
4. 全局分配和歧义拒判是否合理

## 12. 第八步：失败样本怎么回灌

每次训练结束后，必须留下一份失败样本清单：

- 原图
- 预测结果
- 正确标签
- 失败原因
- 是否加入下一轮数据集

失败原因至少分 5 类：

1. 环境问题
2. 标签问题
3. 类别体系问题
4. 模型容量不足
5. 背景/模板分布不足

如果不做这个动作，后面就会重复踩同样的坑。

## 13. 新手最常见的 6 个坑

1. `nvidia-smi` 不通，还继续装训练包。
2. PyTorch 装成 CPU 版，却以为在用显卡。
3. 第一组没保存顺序字段，导致后面无法评估“顺序点击”。
4. 训练集和测试集来自同一批背景模板，导致指标虚高。
5. 自动标注不抽检，直接拿脏标签训练。
6. 一开始就想做统一大模型，结果两个任务都没跑通。

## 14. 这两个参考仓库到底怎么用

### `dddd_trainer`

借鉴它的点：

- Windows/NVIDIA GPU 训练经验
- 新手友好的训练体验
- 把训练做成项目化流程

不要直接照搬的点：

- 它的主任务还是 OCR 训练，不是当前图形定位任务。

### `captcha_trainer`

借鉴它的点：

- 零基础用户视角
- Windows GPU 使用方式
- 项目化管理习惯

不要直接照搬的点：

- 该项目更偏图像分类场景，不适合作为当前两个专项定位模型的直接主线。

## 15. 建议的正式开工顺序

如果你明天就开始干，按下面顺序执行就够了：

1. 搭环境，确认 GPU 可用。
2. 固定样本字段和目录结构。
3. 想尽一切办法先打通“生成端直接导标签”。
4. 第二组先用规则法做预标注。
5. 第一组先做 300-500 张种子集。
6. 用种子集训一个暖启动小模型。
7. 批量自动标注剩余数据并抽检。
8. 第二组先正式训练。
9. 第一组再正式训练。
10. 归档版本、报告和失败样本。

这就是当前阶段最可实施的方案。

## 16. 参考来源

- PyTorch Windows 本地安装官方页：<https://pytorch.org/get-started/locally/>
- Ultralytics 官方文档首页：<https://docs.ultralytics.com/>
- X-AnyLabeling 官方发布页：<https://github.com/CVHub520/X-AnyLabeling/releases>
- `dddd_trainer`：<https://github.com/sml2h3/dddd_trainer>
- `captcha_trainer`：<https://github.com/kerlomz/captcha_trainer>

## 17. 配套清单

- [从基础模型到训练的实操手册](../../../02-user-guide/from-base-model-to-training-guide.md)
- [Windows 训练环境 Checklist](./windows-environment-checklist.md)
- [样本导出与自动标注 Checklist](./data-export-auto-labeling-checklist.md)
