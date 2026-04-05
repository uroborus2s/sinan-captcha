# 发布与交付工作流

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：负责打包、发布训练交付包和后续 solver 交付物的维护者
- 负责人：Codex
- 最近更新：2026-04-05

## 0. 这页解决什么问题

这页回答的是：

- 维护者怎样从源码仓库产出 Python 包、Go 生成器和 Windows 训练交付包
- 维护者应如何理解当前训练交付物与目标 solver 交付物的边界

## 1. 当前正式交付物

当前发布链路目前稳定产出 4 类东西：

### 1.1 Python 包

位于：

- `dist/*.whl`
- `dist/*.tar.gz`

由命令生成：

```bash
uv run sinan release build --project-dir .
```

### 1.2 Go 生成器二进制

典型目标：

- `generator/dist/generator/darwin-arm64/sinan-generator`
- `generator/dist/generator/windows-amd64/sinan-generator.exe`

### 1.3 Windows 训练交付包

用于交给训练机或现场使用者。

典型目录：

- `dist/windows-bundle-<version>/`

### 1.4 目标 solver 交付物

目标态还应产出：

- solver package/library
- solver bundle

当前它已经能通过 solver CLI 和 `package-windows --bundle-dir` 进入正式交付目录。

## 2. Python 包发布工作流

### 2.1 本地构建

```bash
uv run sinan release build --project-dir .
```

### 2.2 上传到 PyPI

如果你把 token 放在 `UV_PUBLISH_TOKEN`：

```bash
uv run sinan release publish --project-dir . --token-env UV_PUBLISH_TOKEN
```

如果你把 token 放在 `PYPI_TOKEN`：

```bash
uv run sinan release publish --project-dir . --token-env PYPI_TOKEN
```

当前实现会把你指定环境变量里的 token 映射成 `uv publish` 需要的 `UV_PUBLISH_TOKEN`。

## 3. Go 生成器二进制构建工作流

在仓库根执行时，推荐显式指定输出目录。

### 3.1 mac 二进制

```bash
cd generator
mkdir -p dist/generator/darwin-arm64
GOOS=darwin GOARCH=arm64 go build -o dist/generator/darwin-arm64/sinan-generator ./cmd/sinan-generator
```

### 3.2 Windows 二进制

```bash
cd generator
mkdir -p dist/generator/windows-amd64
GOOS=windows GOARCH=amd64 go build -o dist/generator/windows-amd64/sinan-generator.exe ./cmd/sinan-generator
```

构建完成后，至少补一次：

```bash
cd generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
```

## 4. Windows 训练交付包工作流

先确保下面两样已经准备好：

1. Python wheel 已生成
2. Windows 版 `sinan-generator.exe` 已生成

然后执行：

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe generator/dist/generator/windows-amd64/sinan-generator.exe \
  --bundle-dir bundles/solver/current \
  --output-dir dist/windows-bundle-0.1.14
```

如果你要顺手把数据集或素材也打进去，可以加：

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe generator/dist/generator/windows-amd64/sinan-generator.exe \
  --output-dir dist/windows-bundle-0.1.14 \
  --datasets-dir datasets \
  --materials-dir materials
```

## 5. 当前训练交付包里应该有什么

当前实现会整理这些内容：

- `python/`
  - 最新 wheel
- `generator/`
  - `sinan-generator.exe`
- 可选 `bundle/`
  - `manifest.json`
  - `models/...`
- 可选 `datasets/`
- 可选 `materials/`
- `README-交付包说明.txt`

## 6. solver 交付当前状态

截至 2026-04-05：

- `core/solve` 已存在
- bundle 合同已存在
- 根 `sinan` CLI 已注册 `solve`
- `package-windows` 已支持 `--bundle-dir`

因此当前发布原则是：

- 可以稳定发布训练交付包
- 也可以稳定发布“wheel + bundle”的 solver 交付目录
- 但不应把 solver 模型说成“已经内嵌进 PyPI wheel”

## 7. 发布前检查单

至少确认下面 7 件事：

1. `uv run sinan release build` 成功
2. 目标 wheel 出现在 `dist/`
3. Windows 生成器二进制可用
4. `uv run sinan release package-windows` 成功
5. 用户指南里的安装命令没有漂移
6. 开发者指南里的交付流程没有漂移
7. `git diff --check` 通过

## 8. 发布后还要做什么

至少补三件事：

1. 更新公开文档里涉及版本和交付路径的地方
2. 更新 `.factory/memory/current-state.md`
3. 更新 `.factory/memory/change-summary.md`

## 9. 这页完成标志

如果你已经可以从源码仓库稳定产出：

- Python wheel
- Windows 版 `sinan-generator.exe`
- 可交付的 Windows 训练 bundle

那这页的目标就达到了。
