# sinan-captcha

`sinan-captcha` 的最终目标是交付一个本地可调用的统一验证码求解包/库。仓库当前同时包含为这个最终产物生产模型的 Go 生成器、Python 训练 CLI 和自主训练控制器。

## 最终业务语义

- `group2`
  - 输入背景图和缺口图
  - 输出缺口图在背景图上的目标中心点
- `group1`
  - 输入查询图和背景图
  - 按查询图中的图标顺序输出对应图标的中心点序列
- 最终对外交付
  - 1 个统一求解包/库
  - 1 个可复制的 bundle 目录
  - 1 套统一业务语义和请求/响应合同

## 当前稳定入口

仓库当前最完整、最稳定的实现主线仍然是模型生产工具链：

- `sinan-generator`
  - Go CLI
  - 负责工作区、素材、样本生成、真值校验、批次 QA 和训练数据集导出
- `sinan`
  - Python CLI
  - 负责训练目录初始化、环境检查、训练、测试、评估、发布和 `auto-train`

统一求解与 bundle 合同已经进入正式需求和代码骨架，但它还需要继续提升为正式发布主线。当前请不要把仓库理解成公网 HTTP 服务，也不要把它理解成“只有一个可执行文件就能解决全部问题”的成品。

## 最短心智模型

- 一级产品：
  - 统一验证码求解包/库 + bundle
- 二级产线：
  - `sinan-generator`
  - `sinan train/test/evaluate/release`
  - `sinan auto-train`
- 当前稳定数据交接面：
  - `group1`
    - pipeline dataset 目录
    - `dataset.json`
    - `scene-yolo/`
    - `query-yolo/`
    - `splits/`
  - `group2`
    - paired dataset 目录
    - `dataset.json`
    - `master/`
    - `tile/`
    - `splits/`
- 运行目录建议始终分开：
  - 生成器安装目录
  - 生成器工作区
  - 训练目录

## 当前最短流程

如果你现在的目标是生成样本和训练模型，最短流程仍然是：

1. 用 `uvx --from sinan-captcha sinan env setup-train` 创建独立训练目录
2. 用 `sinan-generator workspace init --workspace <generator-workspace>` 初始化生成器工作区
3. 用 `sinan-generator materials import|fetch --workspace <generator-workspace>` 准备素材
4. 用 `sinan-generator make-dataset --workspace <generator-workspace>` 生成正式训练数据集
5. 用 `uv run sinan train group1` 或 `uv run sinan train group2` 启动训练
6. 用 `uv run sinan test group1|group2` 做一键预测 + 评估
7. 用 `uv run sinan auto-train ...` 启动自主训练 study

典型命令：

```powershell
uvx --from sinan-captcha sinan env setup-train --train-root D:\sinan-captcha-work
Set-Location D:\sinan-captcha-generator
.\sinan-generator.exe workspace init --workspace D:\sinan-captcha-generator\workspace
.\sinan-generator.exe materials import --workspace D:\sinan-captcha-generator\workspace --from D:\materials-pack
.\sinan-generator.exe make-dataset --workspace D:\sinan-captcha-generator\workspace --task group1 --dataset-dir D:\sinan-captcha-work\datasets\group1\firstpass
.\sinan-generator.exe make-dataset --workspace D:\sinan-captcha-generator\workspace --task group2 --dataset-dir D:\sinan-captcha-work\datasets\group2\firstpass
Set-Location D:\sinan-captcha-work
opencode serve --port 4096
uv run sinan train group1 --dataset-version firstpass --name firstpass
uv run sinan train group2 --dataset-version firstpass --name firstpass
uv run sinan test group1 --dataset-version firstpass --train-name firstpass
uv run sinan test group2 --dataset-version firstpass --train-name firstpass
```

## 当前状态

- 训练、测试、评估主链路已经可用
- 自主训练已经具备控制器骨架和 `opencode` JUDGE runtime 接入
- `env setup-train` 当前会自动把 `.opencode/commands` 与 `.opencode/skills` 铺到训练目录
- 统一求解与 bundle 已经是正式需求和代码方向，但仍需继续收口为正式对外交付主线

## 文档入口

- [入门说明概览](docs/01-getting-started/index.md)
- [角色与审核结论](docs/02-user-guide/user-guide.md)
- [使用者角色：安装与使用最终求解包](docs/02-user-guide/use-solver-bundle.md)
- [使用者角色：在自己的应用中接入并做业务测试](docs/02-user-guide/application-integration.md)
- [训练者角色：训练机安装](docs/02-user-guide/windows-bundle-install.md)
- [训练者角色：快速开始](docs/02-user-guide/windows-quickstart.md)
- [训练者角色：使用生成器准备训练数据](docs/02-user-guide/prepare-training-data-with-generator.md)
- [训练者角色：使用训练器完成训练、测试与评估](docs/02-user-guide/from-base-model-to-training-guide.md)
- [训练者角色：使用自动化训练](docs/02-user-guide/auto-train-on-training-machine.md)

## 开发者入口

- [开发者指南概览](docs/03-developer-guide/index.md)

下面是源码仓库结构，不是 Windows 训练机的推荐运行目录。训练机目录请看用户指南。

```text
sinan-captcha/
  generator/   # Go 生成器工程
  core/        # Python 训练、评估、发布与自主训练 CLI
  configs/     # 配置与素材规格
  materials/   # 本地素材目录或构建产物
  datasets/    # 原始样本、reviewed 数据和任务专属训练数据集
  reports/     # QA 与评估输出
  docs/        # 正式文档
```
