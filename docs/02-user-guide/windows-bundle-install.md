# 使用交付包在 Windows 训练机上安装

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：拿到交付包、但不准备在训练机上克隆源码仓库的人
- 负责人：Codex
- 最近更新：2026-04-04

## 0. 这页解决什么问题

这页解决的是这类场景：

- 你拿到的是别人给你的 Windows 交付包
- 你不想在训练机上克隆源码仓库
- 你希望先用交付包把训练目录搭起来，再开始训练

这页不负责解释完整训练主线。完整训练步骤仍看：

- [Windows 快速开始](./windows-quickstart.md)
- [Windows 训练机安装与模型训练完整指南](./from-base-model-to-training-guide.md)

如果你的机器没有 `D:` 盘，把本页里的 `D:\` 统一替换成你的实际盘符。

## 1. 先看清楚当前支持边界

当前交付包能稳定解决的是：

- 不需要源码仓库
- 可以直接拿到 Python wheel
- 可以直接拿到 `sinan-generator.exe`
- 可以直接拿到可选 `datasets/`、`materials-pack/` 或 `materials-pack.zip`

当前交付包还没有做到“一包完全离线解决全部 Python 依赖”。

这意味着：

- 如果训练机能访问 PyPI，最简单，直接用本页做
- 如果训练机不能访问 PyPI，但能访问公司内网镜像，也可以做
- 如果训练机完全隔离外网和内网镜像，当前版本还不能保证一条命令装齐 `torch`、`ultralytics` 等训练依赖

所以这页最适合：

- 有交付包
- 至少能访问 PyPI
  或
- 至少能访问你们自己的 Python 包镜像

## 2. 交付包里通常应该有什么

典型结构如下：

```text
D:\sinan-delivery\
  python\
    sinan_captcha-0.1.2-py3-none-any.whl
  generator\
    sinan-generator.exe
  materials-pack\
  materials-pack.zip
  datasets\
  README-交付包说明.txt
```

你至少要有：

- `python\sinan_captcha-*.whl`

如果你还要在训练机本地生成数据，再加上：

- `generator\sinan-generator.exe`
- 可选 `materials-pack\`
  或
- 可选 `materials-pack.zip`
  或
- 一个可访问的素材包下载地址

## 3. 两种安装路径怎么选

### 3.1 路线 A：训练机能访问 PyPI

优先用这个，最简单：

```powershell
Set-Location D:\
uvx --from sinan-captcha sinan env setup-train `
  --train-root D:\sinan-captcha-work `
  --generator-root D:\sinan-captcha-generator
```

这条路线不依赖你手里的 wheel，只要能访问 PyPI 就够。

### 3.2 路线 B：你要明确从交付包里的 wheel 启动

这条路线适合：

- 你已经拿到了交付包
- 你想保证训练机用的是交付包里的 wheel

直接从交付包里的 wheel 启动：

```powershell
uvx --from D:\sinan-delivery\python\sinan_captcha-0.1.2-py3-none-any.whl sinan env setup-train `
  --train-root D:\sinan-captcha-work `
  --generator-root D:\sinan-captcha-generator `
  --package-spec "sinan-captcha[train] @ file:///D:/sinan-delivery/python/sinan_captcha-0.1.2-py3-none-any.whl"
```

说明：

- 这一步不需要先克隆源码仓库
- 这一步会让训练目录自己的 `pyproject.toml` 绑定到你交付包里的 wheel
- 但后续 `uv sync` 仍然需要去解析训练依赖
- 如果完全没有可用包源，这一步还是会卡在依赖下载
- 如果你们走公司内网镜像，先确认训练机能访问镜像，再执行这一步

## 4. 什么时候你其实不能按这页继续

出现下面任一情况，就不要继续按这页硬跑：

- 训练机完全不能访问 PyPI，也没有公司镜像
- 你手里的交付包里没有 Python wheel
- 你手里的交付包里没有 `sinan-generator.exe`，但你又要本地生成数据

这时应该先补交付条件：

1. 补 wheel
2. 补生成器可执行文件
3. 补公司镜像或离线 wheelhouse

## 5. 训练目录创建完成后下一步做什么

### 5.1 如果你已经拿到 YOLO 数据集

直接放到：

- `D:\sinan-captcha-work\datasets\group1\<version>\yolo`
- `D:\sinan-captcha-work\datasets\group2\<version>\yolo`

然后继续读：

- [Windows 快速开始](./windows-quickstart.md)

### 5.2 如果你还要本地生成训练数据

把交付包里的生成器文件放到：

- `D:\sinan-captcha-generator`

然后继续读：

- [用生成器准备训练数据](./prepare-training-data-with-generator.md)

## 6. 这页完成标志

满足下面 4 条，就说明你已经掌握“用交付包安装训练机”这条路线：

1. 知道交付包里哪些文件是必须的
2. 知道自己应该走 PyPI 路线还是交付包 wheel 路线
3. 能成功创建 `D:\sinan-captcha-work`
4. 知道创建完成后应跳回哪一页继续
