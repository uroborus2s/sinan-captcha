# 从基础模型到样本生成的零基础实操手册

- 文档状态：草稿
- 当前阶段：DESIGN
- 目标读者：零基础训练操作者
- 负责人：Codex
- 关联需求：`REQ-001`、`REQ-002`、`REQ-003`、`REQ-005`、`REQ-006`、`REQ-007`

## 0. 先把 4 个概念分清

这是整个项目最容易搞混的地方。先用一句话说清：

- 基础模型：就是训练的起点权重，例如 `yolo26n.pt`
- 验证码服务：就是“样本工厂”，负责生成图片
- 代码：就是把“生成图片、导出标签、转换数据、训练模型、评估结果”自动化的工具
- 训练方案：就是你执行这些动作的顺序、规则、验收标准

关系是这样的：

1. 验证码服务负责“产出题目图片”
2. 导出代码负责“把图片和真值标签一起保存下来”
3. 数据转换代码负责“把标签变成 YOLO 训练格式”
4. 训练代码负责“把基础模型微调成你的专项模型”
5. 训练方案负责“规定上面 1-4 应该按什么顺序做、做到什么算通过”

结论：

- 训练方案不是代码
- 代码也不是训练方案
- 训练方案是“施工图”
- 代码是“施工工具”

没有训练方案，代码容易写偏。  
没有代码，训练方案只能靠手工做，无法规模化。

## 1. 本手册选用的具体路线

为了让新手能真正落地，这里固定一条最稳的路线：

1. 基础模型统一用 Ultralytics YOLO 的预训练检测权重 `yolo26n.pt`
2. 没有现成验证码服务时，先部署 `go-captcha-service`
3. 但训练样本不能只靠服务的公开验证接口获取，必须加“内部导出模式”
4. 第一专项训练多类别检测模型
5. 第二专项训练单类别检测模型

为什么不能只调用服务公开接口就开始训练：

- 公开验证码接口的目标是“给前端展示题目并验证用户”
- 训练需要的不只是图片，还需要真值标签
- 第一专项尤其需要：
  - 查询图
  - 场景图
  - 目标顺序
  - 目标框
  - 干扰项框
- 所以训练必须有“导出代码”介入

## 2. 你要走哪条路径

先选路径，不要混着来。

### 路径 A：你已经有自己的验证码生成逻辑

走这条：

1. 不用重新部署开源验证码服务
2. 直接在你自己的生成逻辑上加“导出图片 + 导出标签”
3. 跳到本手册第 7 节

### 路径 B：你还没有自己的生成逻辑

走这条：

1. 先部署 `go-captcha-service`
2. 用它做内部样本生成底座
3. 再加内部导出代码
4. 再开始批量生成样本

下面默认你走路径 B。

## 3. 第一步：准备 Windows 电脑

你先不要碰模型和验证码服务，先把电脑准备好。

### 3.1 确认硬件

逐条确认：

- [ ] Windows 10 或 Windows 11
- [ ] 有管理员权限
- [ ] 有 NVIDIA 显卡
- [ ] 显存最好不少于 6GB
- [ ] 非系统盘有至少 100GB 空间

### 3.2 创建固定工作目录

在 PowerShell 里执行：

```powershell
mkdir D:\sinan-captcha-work
mkdir D:\sinan-captcha-work\tools
mkdir D:\sinan-captcha-work\datasets
mkdir D:\sinan-captcha-work\exports
mkdir D:\sinan-captcha-work\runs
mkdir D:\sinan-captcha-work\reports
```

检查：

- [ ] `D:\sinan-captcha-work` 已存在
- [ ] 各子目录已创建

### 3.3 安装显卡驱动

1. 打开 NVIDIA 官方驱动页面
2. 下载适合你显卡的稳定版驱动
3. 安装并重启
4. 打开 PowerShell 执行：

```powershell
nvidia-smi
```

通过标准：

- [ ] 能看到显卡名称
- [ ] 能看到驱动版本
- [ ] 能看到显存信息

## 4. 第二步：安装训练工具链

### 4.1 安装 Git

去 Git for Windows 官网安装，安装完成后执行：

```powershell
git --version
```

通过标准：

- [ ] `git --version` 能输出版本号

### 4.2 安装 Docker Desktop

因为新手最容易部署 `go-captcha-service` 的方式就是 Docker。

安装后执行：

```powershell
docker --version
docker compose version
```

通过标准：

- [ ] `docker --version` 正常
- [ ] `docker compose version` 正常

### 4.3 安装 `uv`

推荐执行：

```powershell
winget install --id=astral-sh.uv -e
```

然后检查：

```powershell
uv --version
```

### 4.4 安装 Python 3.11

执行：

```powershell
uv python install 3.11
uv python list
```

通过标准：

- [ ] `uv python list` 里能看到 `3.11`

### 4.5 创建训练虚拟环境

执行：

```powershell
cd /d D:\sinan-captcha-work
uv venv --python 3.11
.\.venv\Scripts\activate
python -V
```

### 4.6 安装 PyTorch 和 YOLO

先到 PyTorch 官方安装页按你的 CUDA 版本选择 Windows + Pip + Python 命令。  
然后在虚拟环境里执行官方生成的命令。

再安装 YOLO 相关依赖：

```powershell
uv pip install ultralytics opencv-python numpy pandas pillow pyyaml matplotlib scikit-image tqdm
```

检查：

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-gpu')"
uv run yolo checks
```

通过标准：

- [ ] `torch.cuda.is_available()` 是 `True`
- [ ] `uv run yolo checks` 没有关键错误

## 5. 第三步：先把基础模型准备好

### 5.1 基础模型是什么

这里的基础模型不是“验证码专用模型”，而是检测模型的预训练权重。

本项目首版统一使用：

- 第一专项：`yolo26n.pt`
- 第二专项：`yolo26n.pt`

这一步的意思不是你现在马上训练，而是：

1. 你后面训练时，不是从空白开始
2. 你是拿 `yolo26n.pt` 当起点，再喂你自己的验证码样本

### 5.2 基础模型在训练里的位置

训练时你做的是：

```text
基础模型权重 + 你自己的训练数据 = 你的专项模型
```

不是：

```text
验证码服务 = 基础模型
```

验证码服务和基础模型是两件完全不同的东西。

## 6. 第四步：部署验证码服务

### 6.1 为什么这里选 `go-captcha-service`

因为它适合做“内部样本生成底座”，而不是只做线上验证服务。

你需要它的能力包括：

- 图形点选 Click CAPTCHA
- 滑块 Slide CAPTCHA
- 可自定义资源
- 可本地部署

### 6.2 克隆仓库

执行：

```powershell
cd /d D:\sinan-captcha-work\tools
git clone https://github.com/wenlng/go-captcha-service.git
cd go-captcha-service
```

检查：

- [ ] `D:\sinan-captcha-work\tools\go-captcha-service` 已存在

### 6.3 用 Docker 启动服务

在仓库根目录执行：

```powershell
docker compose up -d
```

说明：

- `go-captcha-service` 仓库自带 `docker-compose.yml`
- README 明确支持 Docker 和 Docker Compose 部署

检查容器状态：

```powershell
docker ps
```

通过标准：

- [ ] 能看到验证码服务容器
- [ ] 如果 compose 同时拉起 Redis/Etcd，也视为正常

### 6.4 验证服务能正常出题

执行：

```powershell
curl.exe "http://127.0.0.1:8080/api/v1/public/get-data?id=click-default-ch"
```

如果返回 JSON，说明服务已经能正常生成验证码。

这一步只证明“服务能出题”，还不等于“能用于训练”。

## 7. 第五步：你必须补一个“内部导出模式”

这是整个训练里最关键的一步。

### 7.1 为什么公开接口不够

公开接口主要用于：

- 把验证码展示给前端
- 接收用户点击或滑动结果
- 校验用户是否答对

但训练需要的是：

- 图片
- 真值标签
- 批次信息
- 任务类型

如果你只有公开接口，没有导出逻辑，你拿不到完整训练标签。

### 7.2 导出代码应该做什么

这部分代码的职责非常明确：

1. 调用生成器
2. 保存主图
3. 保存查询图或滑块图
4. 保存真值标签
5. 保存批次 ID
6. 保存任务类型

### 7.3 `go-captcha` 核心库能给你什么

`go-captcha` 核心库公开了这类生成数据：

- Click CAPTCHA 可获取：
  - `GetData()`
  - `GetMasterImage()`
  - `GetThumbImage()`
- Slide CAPTCHA 可获取：
  - `GetData()`
  - `GetMasterImage()`
  - `GetTileImage()`

这意味着：

- 你不能只停留在“把服务跑起来”
- 你必须在服务端或生成脚本里，把这些数据保存成训练样本

### 7.4 第一专项导出时必须保存什么

第一专项需要保存：

- 场景图 `scene_image`
- 查询图 `query_image`
- 目标顺序 `targets[].order`
- 目标类别 `targets[].class`
- 目标框 `targets[].bbox`
- 目标中心点 `targets[].center`
- 干扰项框 `distractors[]`

重点：

- 如果你只能拿到目标点，拿不到干扰项框，那还不够
- 这时必须在生成端源码层补记录逻辑

### 7.5 第二专项导出时必须保存什么

第二专项需要保存：

- 场景图 `scene_image`
- 查询图或滑块图 `query_image`
- 目标框 `target.bbox`
- 目标中心点 `target.center`

## 8. 第六步：决定你的导出代码放在哪里

你至少要有下面 4 类代码文件。它们不是训练方案本身，但它们是把训练方案落地的工具。

### 8.1 样本导出代码

建议未来放在：

```text
scripts/export/
  export_group1_samples.py
  export_group2_samples.py
```

职责：

- 批量生成样本
- 保存图片
- 保存 JSONL 标签

### 8.2 自动标注代码

建议未来放在：

```text
scripts/autolabel/
  autolabel_group1.py
  autolabel_group2.py
```

职责：

- 第二组规则法预标注
- 第一组暖启动模型预标注

### 8.3 数据转换代码

建议未来放在：

```text
scripts/convert/
  build_group1_yolo.py
  build_group2_yolo.py
```

职责：

- 把 JSONL 转成 YOLO 训练目录
- 生成 `dataset.yaml`

### 8.4 训练入口代码

建议未来放在：

```text
scripts/train/
  train_group1.ps1
  train_group2.ps1
```

职责：

- 固定训练命令
- 固定超参数
- 固定输出目录

## 9. 第七步：先小批量生成一批样本

不要一上来就生成 5 万张。

第一轮只做：

- 第一专项：100 张
- 第二专项：100 张

你的目标不是“大量数据”，而是先检查：

1. 图生成对不对
2. 标签导出对不对
3. 查询图和场景图能否一一对应
4. 真值字段有没有缺

### 9.1 第一专项检查项

逐条检查：

- [ ] 每条样本有查询图
- [ ] 每条样本有场景图
- [ ] 有目标顺序
- [ ] 有目标类别
- [ ] 有目标框
- [ ] 有目标中心点
- [ ] 有干扰项框

### 9.2 第二专项检查项

逐条检查：

- [ ] 每条样本有查询图或滑块图
- [ ] 每条样本有场景图
- [ ] 有目标框
- [ ] 有目标中心点

## 10. 第八步：把样本固化成 JSONL

你先不要碰 YOLO 格式，先把主事实源定死成 JSONL。

### 10.1 第一专项 JSONL 结构

```json
{
  "sample_id": "g1_000001",
  "captcha_type": "group1_multi_icon_match",
  "query_image": "query/g1_000001.png",
  "scene_image": "scene/g1_000001.png",
  "targets": [
    {"order": 1, "class": "icon_house", "bbox": [20, 8, 42, 24], "center": [31, 16]}
  ],
  "distractors": [
    {"class": "icon_leaf", "bbox": [55, 10, 75, 26]}
  ],
  "label_source": "gold",
  "source_batch": "batch_0001"
}
```

### 10.2 第二专项 JSONL 结构

```json
{
  "sample_id": "g2_000001",
  "captcha_type": "group2_single_shape_locate",
  "query_image": "query/g2_000001.png",
  "scene_image": "scene/g2_000001.png",
  "target": {
    "class": "target_shape",
    "bbox": [120, 44, 156, 88],
    "center": [138, 66]
  },
  "label_source": "gold",
  "source_batch": "batch_0001"
}
```

## 11. 第九步：第二专项先做规则法预标注

为什么先做第二专项：

- 它更简单
- 更容易验证整条链路
- 更容易让新手快速看到结果

规则法步骤：

1. 灰度化场景图
2. 提取高亮区域
3. 连通域或轮廓提取
4. 计算候选框
5. 输出 `bbox` 和 `center`
6. 保存为 `auto` 标签

这一步的目的：

- 先形成第二专项初始数据
- 先验证规则法能否稳定命中

## 12. 第十步：第一专项先做种子集

第一专项不要直接全自动。

先做：

- 300-500 张种子集

具体动作：

1. 先生成一批第一专项样本
2. 在 X-AnyLabeling 里复核这些样本
3. 修正错框、漏框、错类、错顺序
4. 把修正后的数据标成 `reviewed`

为什么必须做：

- 第一专项比第二专项复杂
- 它需要一个暖启动小模型，后面才能大批量自动标注

## 13. 第十一步：把 JSONL 转成 YOLO 训练集

### 13.1 第一专项目录

```text
datasets/group1/v1/yolo/
  images/
    train/
    val/
    test/
  labels/
    train/
    val/
    test/
  dataset.yaml
```

### 13.2 第二专项目录

```text
datasets/group2/v1/yolo/
  images/
    train/
    val/
    test/
  labels/
    train/
    val/
    test/
  dataset.yaml
```

### 13.3 第一专项 `dataset.yaml`

示例：

```yaml
path: D:/sinan-captcha-work/datasets/group1/v1/yolo
train: images/train
val: images/val
test: images/test
names:
  0: icon_house
  1: icon_leaf
  2: icon_boat
```

### 13.4 第二专项 `dataset.yaml`

示例：

```yaml
path: D:/sinan-captcha-work/datasets/group2/v1/yolo
train: images/train
val: images/val
test: images/test
names:
  0: target_shape
```

## 14. 第十二步：开始基于基础模型训练

### 14.1 第二专项先训练

先执行第二专项训练：

```powershell
uv run yolo detect train data=D:\sinan-captcha-work\datasets\group2\v1\yolo\dataset.yaml model=yolo26n.pt imgsz=640 epochs=100 batch=16 device=0 project=D:\sinan-captcha-work\runs\group2 name=v1
```

看什么：

- [ ] 训练能启动
- [ ] GPU 在工作
- [ ] 结果目录生成
- [ ] 有 `best.pt`

### 14.2 第一专项再训练

然后执行第一专项训练：

```powershell
uv run yolo detect train data=D:\sinan-captcha-work\datasets\group1\v1\yolo\dataset.yaml model=yolo26n.pt imgsz=640 epochs=120 batch=16 device=0 project=D:\sinan-captcha-work\runs\group1 name=v1
```

训练结束后，第一专项还要做一步后处理：

1. 读取查询顺序
2. 把顺序映射到检测结果
3. 输出点击点坐标列表

## 15. 第十三步：验收

### 15.1 第二专项验收

看：

- 点命中率
- 平均点误差
- IoU
- 推理时间

### 15.2 第一专项验收

看：

- 单目标点命中率
- 整组顺序全部命中率
- 平均点误差
- 错序率

## 16. 第十四步：失败样本回灌

每次训练后必须做：

1. 找出失败样本
2. 看失败原因是标签、类别、背景还是模型容量问题
3. 把这些失败样本回灌到下一轮候选数据池

如果不做这一步，你的模型只会反复撞同样的问题。

## 17. 新手最容易踩的 8 个坑

1. 把基础模型和验证码服务当成一回事。
2. 只把验证码服务跑起来，却没有做导出代码。
3. 只拿公开验证码接口数据，不保存真值标签。
4. 第一专项没保存顺序字段。
5. 第一专项没保存干扰项框。
6. 第二专项没保存中心点。
7. 还没把小批量 100 张跑通，就开始追求大数据量。
8. 还没把第二专项训通，就急着上第一专项复杂自动标注。

## 18. 到这一步你应该得到什么

当你按本手册做完，你应该手里有：

- 一套能运行的验证码生成服务
- 一套内部导出代码设计
- 一批带真值标签的 JSONL 样本
- 两套 YOLO 训练数据目录
- 一个第二专项基线模型
- 一个第一专项基线模型

如果这 6 样东西没有齐，就说明你还没真的跑通闭环。

## 19. 参考来源

- PyTorch Get Started: <https://pytorch.org/get-started/locally/>
- Ultralytics Docs: <https://docs.ultralytics.com/>
- Ultralytics 自定义训练示例：<https://docs.ultralytics.com/datasets/detect/>
- `go-captcha`: <https://github.com/wenlng/go-captcha>
- `go-captcha-service`: <https://github.com/wenlng/go-captcha-service>
- `tianai-captcha`: <https://github.com/dromara/tianai-captcha>
