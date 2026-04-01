# Windows 训练环境 Checklist

- 文档状态：草稿
- 当前阶段：REQUIREMENTS
- 目标读者：零基础训练操作者
- 负责人：Codex
- 关联需求：`REQ-001`、`REQ-007`

## 1. 开始前先确认

在开始前，逐条确认：

- [ ] 电脑系统是 Windows 10 或 Windows 11
- [ ] 你拥有管理员权限
- [ ] 电脑装有 NVIDIA 显卡
- [ ] 非系统盘至少有 100GB 可用空间
- [ ] 网络可以正常访问 PyTorch、GitHub 和 Python 包源
- [ ] 你准备把训练工作目录放在非系统盘，例如 `D:\sinan-captcha-work`

## 2. 创建工作目录

建议手工创建以下目录：

```text
D:\sinan-captcha-work\
  datasets\
  exports\
  runs\
  models\
  reports\
  tools\
```

检查项：

- [ ] 目录已创建
- [ ] 路径没有中文和空格
- [ ] 目录位于非系统盘

## 3. 安装和检查显卡驱动

操作步骤：

1. 打开 NVIDIA 官方驱动下载页。
2. 选择你的显卡型号，安装稳定版驱动。
3. 安装完成后重启电脑。
4. 打开 PowerShell，执行：

```powershell
nvidia-smi
```

通过标准：

- [ ] 能看到显卡名称
- [ ] 能看到驱动版本
- [ ] 能看到显存信息

如果失败：

- 先不要继续安装 Python 和训练包
- 先解决驱动问题，再继续后续步骤

## 4. 安装 `uv`

推荐方式：

```powershell
winget install --id=astral-sh.uv -e
```

安装后检查：

```powershell
uv --version
```

通过标准：

- [ ] `uv --version` 能输出版本号

## 5. 安装 Python 3.11

执行：

```powershell
uv python install 3.11
uv python list
```

通过标准：

- [ ] `uv python list` 能看到 `3.11`

说明：

- 第一版统一建议用 Python 3.11
- 不建议直接用系统里来路不明的旧 Python

## 6. 创建虚拟环境

进入工作目录：

```powershell
cd /d D:\sinan-captcha-work
uv venv --python 3.11
.\.venv\Scripts\activate
python -V
```

通过标准：

- [ ] 虚拟环境已创建
- [ ] `python -V` 显示 `3.11.x`
- [ ] 命令行前面能看到虚拟环境提示，或确认当前使用的是 `.venv`

## 7. 升级 pip

执行：

```powershell
python -m pip install --upgrade pip
```

通过标准：

- [ ] 升级过程没有报错

## 8. 安装 PyTorch GPU 版

操作原则：

1. 打开 PyTorch 官方安装页。
2. 选择：
   - Windows
   - Pip
   - Python
   - 与你机器兼容的 CUDA 版本
3. 使用网页生成的命令安装。

常见示例：

```powershell
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

只有当官方页面给你的就是 `cu118` 时才直接用这条。

安装后检查：

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
```

通过标准：

- [ ] 没有安装报错
- [ ] `torch.cuda.is_available()` 输出 `True`

## 9. 安装训练依赖

执行：

```powershell
uv pip install ultralytics opencv-python numpy pandas pillow pyyaml matplotlib scikit-image tqdm
```

通过标准：

- [ ] 所有包安装完成
- [ ] 没有出现关键依赖冲突

## 10. 安装或准备标注工具

优先方案：

- [ ] 下载 X-AnyLabeling Windows 发布包
- [ ] 解压到 `D:\sinan-captcha-work\tools\X-AnyLabeling`

备选方案：

- [ ] 如果多人协作，准备 CVAT

第一版建议：

- [ ] 单人先用 X-AnyLabeling

## 11. 做完整环境自检

执行：

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-gpu')"
uv run yolo checks
```

通过标准：

- [ ] 能打印 torch 版本
- [ ] 能打印显卡名称
- [ ] `yolo checks` 没有关键错误

## 12. 做一次最小冒烟训练

目标不是训好模型，只是确认环境能跑通。

操作：

1. 准备一个最小样本集，例如 20-50 张图片。
2. 准备一个最简单的 `dataset.yaml`。
3. 运行一次最小训练：

```powershell
uv run yolo detect train data=D:\sinan-captcha-work\datasets\smoke\dataset.yaml model=yolo11n.pt imgsz=640 epochs=1 batch=4 device=0 project=D:\sinan-captcha-work\runs\smoke name=env-check
```

通过标准：

- [ ] 训练能启动
- [ ] GPU 显存有占用
- [ ] 训练能完整跑完 1 个 epoch
- [ ] `runs\smoke\env-check` 下生成结果目录

## 13. 常见故障快速判断

### 现象：`nvidia-smi` 不存在

结论：

- 显卡驱动未正常安装，先修驱动

### 现象：`torch.cuda.is_available()` 是 `False`

结论：

- 大概率装成了 CPU 版 PyTorch，或 CUDA 版本不匹配

### 现象：训练一启动就显存爆掉

结论：

- 先把 `batch` 降低
- 先用 `yolo11n.pt`
- 必要时把 `imgsz` 调小

### 现象：`uv run yolo checks` 报依赖错误

结论：

- 优先重建虚拟环境，不要在脏环境上硬补

## 14. 本清单完成标志

以下项目全部勾上，才算环境阶段完成：

- [ ] 驱动正常
- [ ] `uv` 正常
- [ ] Python 3.11 正常
- [ ] 虚拟环境正常
- [ ] PyTorch GPU 版正常
- [ ] `ultralytics` 正常
- [ ] 标注工具已就位
- [ ] 冒烟训练成功
