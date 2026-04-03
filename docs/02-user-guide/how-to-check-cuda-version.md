# 如何确认 Windows 电脑上的 CUDA 版本

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：零基础训练操作者
- 负责人：Codex
- 关联需求：`REQ-001`、`REQ-007`
- 最近更新：2026-04-03

## 1. 先记住一句话

“CUDA 版本”在 Windows 上至少有 3 种常见说法，它们不是一回事：

1. 显卡驱动支持的 CUDA 运行时版本
2. 你本机是否安装了 CUDA Toolkit，以及 Toolkit 版本
3. 你当前 PyTorch 是按哪个 CUDA 版本编译的

训练时最常用的是第 1 种和第 3 种。

## 2. 最简单的检查方法：看 `nvidia-smi`

打开 PowerShell，执行：

```powershell
nvidia-smi
```

你会看到类似：

```text
Driver Version: 572.xx
CUDA Version: 12.8
```

这里的 `CUDA Version` 表示：

- 这是当前显卡驱动支持的 CUDA 运行时上限
- 不是说你一定安装了 CUDA Toolkit 12.8

对零基础用户来说，这一步最重要，因为它能先确认：

- NVIDIA 驱动正常
- 机器具备跑 GPU 训练的基本条件

如果你看到的是：

```text
CUDA Version: 13.2
```

也不用意外。这通常表示你的驱动已经支持 CUDA 13.x 运行时。

## 3. 第二种方法：看是否装了 CUDA Toolkit

如果你装过 NVIDIA CUDA Toolkit，再执行：

```powershell
nvcc --version
```

如果能输出版本号，说明：

- 你的电脑安装了 CUDA Toolkit
- 命令里显示的是 Toolkit 版本

如果提示 `nvcc` 不存在，也不用慌：

- 这不一定是故障
- 做 PyTorch 训练时，很多场景并不要求你本机单独安装 Toolkit

## 4. 第三种方法：看 PyTorch 绑定的 CUDA 版本

在你的训练虚拟环境里执行：

```powershell
uv run python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
```

你会看到类似：

```text
2.8.0
12.6
True
```

这里的 `torch.version.cuda` 表示：

- 你当前安装的 PyTorch 是按哪个 CUDA 版本构建的

这一步最直接决定：

- 你当前 Python 环境里的 PyTorch GPU 包是不是装对了

## 5. 三种结果怎么理解

### 情况 A

`nvidia-smi` 显示 `CUDA Version: 12.8`  
`torch.version.cuda` 显示 `12.6`

这通常是正常的。

说明：

- 你的驱动支持到 12.8
- 你装的 PyTorch 用的是 12.6 版本的 CUDA 运行时

只要 `torch.cuda.is_available()` 是 `True`，一般就能训练。

### 情况 A2

`nvidia-smi` 显示 `CUDA Version: 13.2`
`torch.version.cuda` 显示 `13.0`

这通常也是正常的。

说明：

- 你的驱动支持到 13.2
- 你装的 PyTorch 用的是 13.0 版本的 CUDA 运行时

### 情况 B

`nvidia-smi` 正常  
`torch.cuda.is_available()` 是 `False`

这通常说明：

- 你装成了 CPU 版 PyTorch
- 或者当前虚拟环境里的包不匹配

### 情况 C

`nvidia-smi` 都跑不起来

这通常说明：

- 驱动没装好
- 或系统还没有正确识别 NVIDIA 显卡

## 6. 小白最该看哪一个

如果你只是为了安装 PyTorch 并开始训练，优先按这个顺序看：

1. `nvidia-smi`
2. `torch.version.cuda`
3. `torch.cuda.is_available()`

`nvcc --version` 只在你明确装过 CUDA Toolkit 时再看。

## 6.1 和 `sinan env setup-train` 的关系

如果你使用：

```powershell
uvx --from sinan-captcha sinan env setup-train
```

这个命令本身就会先读取 `nvidia-smi` 输出，然后再决定训练目录里要绑定哪个 PyTorch 源。

你仍然建议自己先看一遍 `nvidia-smi`，原因很简单：

- 这样更容易在命令真正安装依赖前，先确认显卡驱动和 CUDA 版本是不是你预期的状态

## 7. 推荐检查顺序

按这个顺序做最稳：

1. 执行 `nvidia-smi`
2. 确认显卡和驱动正常
3. 按 PyTorch 官方页面安装 GPU 版
4. 在虚拟环境里执行：

```powershell
uv run python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-gpu')"
```

5. 如果 `torch.cuda.is_available()` 是 `True`，就说明训练环境基本可用

## 8. 一句话结论

真正决定你能不能开始训练的，不是你有没有单独装 `nvcc`，而是：

- `nvidia-smi` 正常
- `torch.cuda.is_available()` 为 `True`

这两个条件满足，就可以进入样本生成和训练环节。
