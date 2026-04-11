# 仓库结构与边界

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：维护仓库、调整 CLI、整理交付物的开发者
- 负责人：Codex
- 最近更新：2026-04-09

## 0. 这页解决什么问题

这页只回答一件事：

- 这个项目的源码仓库、运行目录、交付目录和 Git 边界到底怎么分

如果这一层没先分清，后面最容易出现的问题就是：

- 把训练目录当成源码仓库的一部分
- 把生成器工作区误当成安装目录
- 把运行时产物提交进 Git
- 把用户指南、开发者指南和内部设计文档混写

## 1. 先区分 5 个层次

### 1.1 源码仓库

也就是当前 Git 仓库本身。

主要目录：

- `generator/`
- `core/`
- `solver/`
- `script/`
- `configs/`
- `docs/`
- `.factory/`
- `bundles/`

这是维护者改代码、改文档、跑测试、构建交付物的地方。

### 1.2 生成器安装目录

这是交付给 Windows 机器使用的运行目录，不是源码目录。

典型结构：

```text
D:\sinan-captcha-generator\
  sinan-generator.exe
```

这里放：

- 生成器二进制

说明：

- 普通用户不需要在安装目录手工维护 `configs/*.yaml`
- 生成器预设会在首次运行时自动展开到工作区 `presets/`

### 1.3 生成器工作区

这也是运行目录，但它承载的是生成器状态，不是安装文件。

典型结构：

```text
D:\sinan-captcha-generator\workspace\
  workspace.json
  presets\
  materials\
  cache\
  jobs\
  logs\
```

这里放：

- 当前激活素材集
- 任务记录
- 中间缓存
- 日志

### 1.4 训练目录

训练目录同样是运行目录，不是源码目录。

典型结构：

```text
D:\sinan-captcha-work\
  pyproject.toml
  .python-version
  .venv\
  datasets\
  runs\
  reports\
```

这里放：

- 训练环境
- 数据集
- 训练输出
- 评估报告

### 1.5 solver 交付目录

最终调用方使用的 solver 目录也应独立于源码仓库和训练目录。

目标结构：

```text
D:\sinan-solver\
  python\
  bundle\
```

这里放：

- 可安装的 solver package/library
- 独立复制的 bundle manifest 和模型文件

这里不应放：

- 训练目录里的 `runs/`
- 生成器工作区
- 源码仓库副本

## 2. 双 CLI 的稳定边界

### 2.1 `sinan-generator`

职责只到这里为止：

- 初始化工作区
- 导入或同步素材
- 生成训练样本
- 做生成侧 QA
- 直接导出任务专属训练数据集目录

### 2.2 `sinan`

职责从这里开始：

- 初始化训练目录
- 检查训练环境
- 做数据工程和转换
- 启动训练
- 执行评估
- 构建发布和交付物

### 2.3 两者怎么交接

稳定交接面有两个专项合同：

- `group1`：instance-matching dataset 目录
- `group1/dataset.json`
- `group1/proposal-yolo/`
- `group1/embedding/`
- `group1/eval/`
- `group1/splits/`
- `group2`：paired dataset 目录
- `group2/dataset.json`
- `group2/master/`
- `group2/tile/`
- `group2/splits/`
- `.sinan/`

训练 CLI 的正式输入分别是：

- `group1`：`--dataset-config <dataset-dir>/dataset.json`
- `group2`：`--dataset-config <dataset-dir>/dataset.json`

不要让训练 CLI 去直接读取生成器工作区，也不要让生成器承担训练环境初始化。

## 3. 哪些目录是源码，哪些只是运行资产

### 3.1 需要认真维护的源码目录

- `generator/`
- `core/`
- `solver/`
- `script/`
- `docs/`
- `.factory/`
- `configs/`

补充边界：

- `solver/` 是独立 solver 项目的源码目录。
- `script/` 只放开发期辅助脚本，不进入正式 CLI / SDK 运行时边界。
- `scripts/crawl/ctrip_login.py` 当前用于开发阶段采集携程验证码素材：
  - 点选模式输出到 `materials/group1/`
  - 滑块模式输出到 `materials/result/`
  - 滑块图片当前保存为 `bg.jpg` 和 `gap.jpg`
  - `两者都保存` 模式会连续保存滑块组，直到切到点选后再保存一组点选图并结束当前浏览器会话
- `scripts/organize_group2_gap_shapes.py` 当前用于整理 `materials/result/*/gap.jpg`：
  - 按轮廓特征做稳定去重
  - 文件名按“短家族名 + 短特征码”生成，不再依赖 `_alt_001` 这类数字补丁名
  - 基名当前控制在 `20` 个字符以内，且保持无数字命名
  - 当短特征码碰撞时，当前会自动拉长特征码，但仍不超过 `20` 个字符
  - 代表图输出到 `materials/incoming/group2/`
  - 同一轮廓特征只保留一个代表图，并写出 `manifest.json`

### 3.2 可以出现样例或占位，但不应把运行结果当源码维护的目录

- `materials/`
- `datasets/`
- `reports/`
- `dist/`
- `generator/dist/`

这些目录里允许存在：

- `.gitkeep`
- 样例结构
- 交付产物占位

但不应把运行时生成结果当成长久事实源。

## 4. 什么不能提交到 Git

至少包括：

- `.venv/`
- `__pycache__/`
- `*.egg-info`
- `dist/` 下的构建产物
- `generator/dist/` 下的二进制
- 训练输出 `runs/`
- 评估导出物
- 运行时生成的 `backgrounds.csv`、`group1.icons.csv`、`group2.shapes.csv`
- 坏图隔离目录 `materials/quarantine/`
- 本地缓存 `.cache/`

提交前至少做两件事：

1. 看一次 `git status --short`
2. 跑一次 `git diff --check`

## 5. 文档也有边界

### 5.1 用户指南

只回答：

- 怎样在 Windows 机器上安装、生成、训练、验证

不要把维护者阅读顺序、源码目录说明和内部演进记录塞回用户指南。

### 5.2 开发者指南

只回答：

- 维护者如何接手、修改、验证和发布这套工程

### 5.3 项目开发文档（内）

这里才放：

- 治理
- 需求
- 设计
- 过程
- 发布策略
- 运维规则

开发者指南不要复制一整套内部设计结论，只链接到需要看的地方。

## 6. 这页完成标志

如果你已经能清楚回答下面 5 个问题，就说明这页目的达到了：

1. 源码仓库和训练目录是不是一回事
2. 生成器安装目录和生成器工作区是不是一回事
3. `sinan-generator` 和 `sinan` 的交接面是什么
4. 哪些运行时目录不该进 Git
5. 某条说明应该写进用户指南、开发者指南还是内部设计文档
