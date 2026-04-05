# 训练者角色：训练机安装

这页只解决一件事：

- 在 Windows + NVIDIA 训练机上，把训练目录和生成器目录搭起来。

## 1. 当前推荐目录

建议固定两个目录：

```text
D:\
  sinan-captcha-work\
  sinan-captcha-generator\
```

其中：

- `sinan-captcha-work`
  - 训练目录
  - 保存 `pyproject.toml`、`.venv/`、`.opencode/`、`datasets/`、`runs/`、`reports/`
- `sinan-captcha-generator`
  - 生成器安装目录
  - 保存 `sinan-generator.exe`
  - 可选保存 `workspace\`

## 2. 训练机前提

至少满足：

- Windows
- NVIDIA 显卡
- 已装显卡驱动
- 已安装 `uv`
- 能访问 PyPI 或你们自己的 Python 镜像

如果你还没确认 CUDA 版本，先看：

- [训练者角色：CUDA 版本检查](./how-to-check-cuda-version.md)

## 3. 训练目录安装

最简单的做法：

```powershell
uvx --from sinan-captcha sinan env setup-train `
  --train-root D:\sinan-captcha-work `
  --generator-root D:\sinan-captcha-generator
```

这条命令会：

- 创建训练目录
- 写入训练目录自己的 `pyproject.toml`
- 自动铺入 `.opencode/commands` 和 `.opencode/skills`
- 安装训练环境

如果你手里拿的是 wheel，也可以用 wheel 路线：

```powershell
uvx --from D:\sinan-delivery\python\sinan_captcha-0.1.14-py3-none-any.whl sinan env setup-train `
  --train-root D:\sinan-captcha-work `
  --generator-root D:\sinan-captcha-generator `
  --package-spec "sinan-captcha[train] @ file:///D:/sinan-delivery/python/sinan_captcha-0.1.14-py3-none-any.whl"
```

## 4. 安装后立即做的检查

进入训练目录：

```powershell
Set-Location D:\sinan-captcha-work
uv run sinan env check
```

通过标准：

- 能正常输出 JSON
- `torch_installed=true`
- 如果要跑 GPU，最好看到 `torch_cuda_available=true`

如果你后面要启用 `auto-train --judge-provider opencode`，此时训练目录里已经会有：

- `D:\sinan-captcha-work\.opencode\commands`
- `D:\sinan-captcha-work\.opencode\skills`

后续直接在训练目录启动 `opencode serve` 即可。

## 5. 下一步怎么走

### 你已经有训练数据

继续读：

- [训练者角色：快速开始](./windows-quickstart.md)

### 你还没有训练数据

继续读：

- [训练者角色：使用生成器准备训练数据](./prepare-training-data-with-generator.md)

### 你要尝试自动化训练

继续读：

- [训练者角色：使用自动化训练](./auto-train-on-training-machine.md)
