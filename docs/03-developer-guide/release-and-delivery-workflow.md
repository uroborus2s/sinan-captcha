# 打包与上传发布

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：负责发版、打包训练交付物、上传 PyPI 的开发者
- 最近更新：2026-04-11

## 0. 这页解决什么问题

这页直接给出开发者发布路径：

1. 怎么更新版本号
2. 怎么在根目录一次编译三份产物
3. 怎么单独编译根仓库 Python 包、Go 生成器和 solver 包
4. 怎么导出 solver 资产
5. 怎么组装 Windows 交付包
6. 怎么上传到 PyPI

## 1. 当前发布对象

### 1.1 根仓库 Python 包

包名：

- `sinan-captcha`

版本单一事实源：

- `packages/sinan-captcha/pyproject.toml` 的 `[project].version`

构建产物：

- `packages/sinan-captcha/dist/sinan_captcha-<version>-py3-none-any.whl`
- `packages/sinan-captcha/dist/sinan_captcha-<version>.tar.gz`

### 1.2 Go 生成器二进制

主要产物：

- `packages/generator/dist/darwin-arm64/sinan-generator`
- `packages/generator/dist/windows-amd64/sinan-generator.exe`

### 1.3 Windows 训练交付包

主要产物：

- `dist/windows-bundle-<version>/`

通常包含：

- `python/`
- `generator/`
- 可选 `bundle/`
- 可选 `datasets/`
- 可选 `materials/`

### 1.4 独立 solver 包

当前目录：

- `packages/solver/`

说明：

- 当前可以独立构建和测试
- 当前不是根仓库主发布链路

## 2. 发布前先做什么

### 2.1 更新版本号

先更新：

- `packages/sinan-captcha/pyproject.toml` 的 `[project].version`

如果你这次只发布根仓库 Python 包，这里是必须改的。

### 2.2 运行最小验证

至少执行：

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
cd packages/generator && GOCACHE=/tmp/sinan-go-build-cache go test ./... && cd ..
git diff --check
```

如果这次还改了独立 solver 包，再加：

```bash
cd packages/solver
uv run pytest
cd ..
```

## 3. 根目录统一编译三份产物

开发期薄包装可直接执行：

```bash
uv run python scripts/repo.py build all
```

如果要只编译某一个子包：

```bash
uv run python scripts/repo.py build sinan-captcha
uv run python scripts/repo.py build generator
uv run python scripts/repo.py build solver
```

正式发布链路在仓库根目录执行：

```bash
uv run sinan release build-all --project-dir .
```

如果要同时产出 Windows 版生成器：

```bash
uv run sinan release build-all --project-dir . --goos windows --goarch amd64
```

产物目录固定为：

- 根仓库训练 CLI：`packages/sinan-captcha/dist/`
- Go 生成器：`packages/generator/dist/<goos>-<goarch>/`
- 独立 solver 包：`packages/solver/dist/`

当前行为：

- 每次编译前会先清理对应输出目录
- `build-generator` 会在命令结束前校验目标二进制确实存在

## 4. 编译根仓库 Python 包

命令：

```bash
uv run sinan release build --project-dir .
```

说明：

- 这一步会调用 `uv build`
- 输出进入 `packages/sinan-captcha/dist/`

建议立刻做安装烟测：

```bash
uvx --from ./packages/sinan-captcha/dist/sinan_captcha-<version>-py3-none-any.whl sinan --help
```

## 5. 上传根仓库 Python 包到 PyPI

### 5.1 上传到正式 PyPI

如果 token 放在 `UV_PUBLISH_TOKEN`：

```bash
uv run sinan release publish --project-dir . --token-env UV_PUBLISH_TOKEN
```

如果 token 放在 `PYPI_TOKEN`：

```bash
uv run sinan release publish --project-dir . --token-env PYPI_TOKEN
```

### 5.2 上传到 TestPyPI

```bash
uv run sinan release publish \
  --project-dir . \
  --repository testpypi \
  --token-env TEST_PYPI_TOKEN
```

说明：

- 当前发布器只会上传当前版本对应的 wheel 和 sdist
- 不会再把 `dist/` 里的历史工件一起上传

## 6. 编译 Go 生成器

### 6.1 根目录构建当前目标

```bash
uv run sinan release build-generator --project-dir .
```

### 6.2 Windows amd64

```bash
uv run sinan release build-generator --project-dir . --goos windows --goarch amd64
```

构建结果：

- `packages/generator/dist/<goos>-<goarch>/sinan-generator`
- `packages/generator/dist/windows-amd64/sinan-generator.exe`

注意：

- 当前不会再把二进制误写到错误的 `generator/generator/dist/` 路径
- 目标平台目录会在编译前先清空

### 6.3 构建后最低检查

```bash
cd packages/generator
GOCACHE=/tmp/sinan-go-build-cache go test ./...
cd ..
```

## 7. 导出 solver 资产

当你已经有 `group1/group2` 的 checkpoint，并要把它们导出成 `sinanz` 可消费的 ONNX 资产时，执行：

```bash
uv run sinan release export-solver-assets \
  --project-dir . \
  --group1-proposal-checkpoint runs/group1/<group1-run>/proposal-detector/weights/best.pt \
  --group1-query-checkpoint runs/group1/<group1-run>/query-parser/weights/best.pt \
  --group1-embedder-checkpoint runs/group1/<group1-run>/icon-embedder/weights/best.pt \
  --group1-run <group1-run> \
  --group2-checkpoint runs/group2/<train-name>/weights/best.pt \
  --group2-run <train-name> \
  --output-dir work_home/reports/solver-assets/<asset-version> \
  --asset-version <asset-version>
```

当前说明：

- 这一步主要服务于 solver 资产交接
- 不是上传 PyPI 的动作
- 如果只传 `group2` checkpoint，命令仍可导出滑块资产，但 `group1` metadata 会保持占位状态
- 导出完成后，若要构建内嵌资产的 `sinanz` wheel，还需执行：

```bash
uv run sinan release stage-solver-assets \
  --project-dir . \
  --asset-dir work_home/reports/solver-assets/<asset-version>
```

## 8. 组装 Windows 训练交付包

### 8.1 最小交付包

前提：

- 根仓库 wheel 已生成
- Windows 版 `sinan-generator.exe` 已生成

命令：

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe packages/generator/dist/windows-amd64/sinan-generator.exe \
  --output-dir dist/windows-bundle-<version>
```

### 8.2 带 bundle 的交付包

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe packages/generator/dist/windows-amd64/sinan-generator.exe \
  --bundle-dir bundles/solver/current \
  --output-dir dist/windows-bundle-<version>
```

### 8.3 带数据集和素材的交付包

```bash
uv run sinan release package-windows \
  --project-dir . \
  --generator-exe packages/generator/dist/windows-amd64/sinan-generator.exe \
  --bundle-dir bundles/solver/current \
  --datasets-dir work_home/datasets \
  --materials-dir work_home/materials \
  --output-dir dist/windows-bundle-<version>
```

## 9. 独立 solver 包当前怎么编译

如果你这次维护的是 `packages/solver/`，用它自己的构建链路：

```bash
cd packages/solver
uv run pytest
cd ..
uv run python scripts/repo.py build solver
```

当前边界：

- `sinanz` 的独立打包仍在迁移主线中
- 不要把它和根仓库 `sinan-captcha` 的正式 PyPI 发布混为一谈

## 10. 一条推荐的正式发版顺序

1. 修改 `packages/sinan-captcha/pyproject.toml` 的 `[project].version`
2. 跑根仓库 Python 测试
3. 跑 Go 生成器测试
4. 如有需要，跑 `solver` 测试
5. 直接运行根目录统一编译命令
6. 如需单独重编，再补 `build` / `build-generator` / `build-solver`
7. 如有需要，导出 solver 资产
8. 组装 Windows 交付包
9. 上传 PyPI
10. 更新文档和 `.factory`

## 11. 发版后必须同步

至少同步：

- `README.md`
- `docs/03-developer-guide/`
- `.factory/memory/current-state.md`
- `.factory/memory/change-summary.md`

## 11. 本页完成标志

如果开发者已经能直接照这页完成下面几件事，就说明开发者指南足够用了：

1. 找到版本号该改哪里
2. 编译根仓库 wheel 和 sdist
3. 编译 `sinan-generator.exe`
4. 组装 Windows 交付包
5. 把根仓库 Python 包上传到 PyPI
