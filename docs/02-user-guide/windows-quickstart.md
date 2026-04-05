# 训练者角色：快速开始

这页给第一次在训练机上开工的人一条最短路径。

## 1. 三种起步方式

### 路线 A：你已经有数据集

1. 安装训练目录
2. 把数据集放进 `datasets/`
3. 直接训练
4. 跑测试

### 路线 B：你还没有数据集

1. 安装训练目录
2. 安装生成器
3. 准备素材
4. 生成 `group1` / `group2` 数据集
5. 训练
6. 测试

### 路线 C：你要试自动化训练

1. 安装训练目录
2. 安装生成器并准备素材
3. 如果要用 `opencode`，直接在训练目录启动 `opencode serve`
4. 先确认手动训练链路能跑通
5. 再启动 `auto-train`

## 2. 最短命令

### 2.1 安装训练目录

```powershell
uvx --from sinan-captcha sinan env setup-train `
  --train-root D:\sinan-captcha-work `
  --generator-root D:\sinan-captcha-generator
```

这一步完成后，训练目录里已经会有：

- `D:\sinan-captcha-work\.opencode\commands`
- `D:\sinan-captcha-work\.opencode\skills`

### 2.2 如果你已经有数据集

把数据集放到：

- `D:\sinan-captcha-work\datasets\group1\firstpass`
- `D:\sinan-captcha-work\datasets\group2\firstpass`

然后训练：

```powershell
Set-Location D:\sinan-captcha-work
uv run sinan train group1 --dataset-version firstpass --name firstpass
uv run sinan train group2 --dataset-version firstpass --name firstpass
```

### 2.3 跑一轮测试

```powershell
uv run sinan test group1 --dataset-version firstpass --train-name firstpass
uv run sinan test group2 --dataset-version firstpass --train-name firstpass
```

## 3. 如果你没有数据集

先回到生成器路线：

- [训练者角色：使用生成器准备训练数据](./prepare-training-data-with-generator.md)

## 4. 如果你要试自动化训练

先确认手动链路至少成功做过一轮，然后再执行：

如果你走 `opencode` 路线，先在训练目录启动：

```powershell
Set-Location D:\sinan-captcha-work
opencode serve --port 4096
```

```powershell
uv run sinan auto-train run group1 `
  --study-name study_group1_firstpass `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --max-steps 8
```

或者：

```powershell
uv run sinan auto-train run group2 `
  --study-name study_group2_firstpass `
  --train-root D:\sinan-captcha-work `
  --generator-workspace D:\sinan-captcha-generator\workspace `
  --max-steps 8
```

更完整的说明看：

- [训练者角色：使用自动化训练](./auto-train-on-training-machine.md)

## 5. 这页的完成标志

满足下面 3 条就算这页完成：

1. 训练目录已创建。
2. 至少一个专项已经开始训练。
3. 至少一条 `test group1|group2` 命令已经成功执行。
