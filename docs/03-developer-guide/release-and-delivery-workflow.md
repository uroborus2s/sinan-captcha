# 构建、发版与交付

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：负责构建工件、导出 solver 资产、组装 Windows 交付包或上传 PyPI 的开发者
- 最近更新：2026-04-11

## 这页解决什么问题

这页覆盖当前仓库的 4 条交付链路：

1. 构建 `sinan-captcha`
2. 构建 `sinan-generator`
3. 构建 `sinanz`
4. 导出 / stage solver 资产并组装 Windows 交付包

## 当前产物矩阵

| 产物 | 目录 | 主入口 |
| --- | --- | --- |
| `sinan-captcha` wheel + sdist | `packages/sinan-captcha/dist/` | `uv run repo build sinan-captcha` |
| `sinan-generator` 二进制 | `packages/generator/dist/<goos>-<goarch>/` | `uv run repo build generator` |
| `sinanz` wheel + sdist | `packages/solver/dist/` | `uv run repo build solver` |
| 导出的 solver 资产目录 | 自定义 `--output-dir` | `uv run repo export-solver-assets ...` |
| Windows 训练交付包 | 自定义 `--output-dir` | `uv run repo package-windows ...` |

## 先记住发布边界不是对称的

第一次接手发布最容易误判的是“所有东西都能用同一条命令发出去”。当前真实规则不是这样：

1. `build-all` 会构建 `sinan-captcha`、`sinan-generator` 和 `sinanz`
2. `publish` 只上传 `sinan-captcha` 当前版本的 wheel 与 sdist
3. `sinanz` 要先导出资产、再 stage、再单独构建 wheel
4. `package-windows` 组装的是训练交付包，不等于发布 `sinanz`

用一句话速记：

- `repo build all`
  仓库级统一构建入口
- `repo publish-sinan`
  只上传 `sinan-captcha`
- `repo publish-solver`
  只上传 `sinanz`

## 先把 4 个容易混的术语拆开

- 导出资产目录：
  `export-solver-assets` 的输出目录，通常形如 `work_home/reports/solver-assets/<asset-version>/`
- staged 资源目录：
  `stage-solver-assets` 写入后的 `packages/solver/resources/`，这是下一次 `sinanz` 打包的真实输入
- runtime bundle：
  训练仓库 `sinan solve ...` 使用的外部 bundle 目录，用于 bundle 调试和回放，不等于 `sinanz` wheel 内嵌资源
- Windows 训练交付包：
  `package-windows` 产出的训练机交付目录，里面会放 wheel、生成器和可选资产，不等于 solver 资产导出目录

## 版本号事实源

当前发布器只把 `sinan-captcha` 的当前版本上传到 PyPI，因此发版前先更新：

- `packages/sinan-captcha/pyproject.toml`
  的 `[project].version`

补充说明：

- 根目录 `pyproject.toml` 是 workspace 根，不是当前发布版本的单一事实源。
- `sinanz` 有自己的版本号，但当前 `publish` 子命令不会替你上传它。

## 发布前最少验证

建议在仓库根目录完成下面这组检查：

```bash
uv run python -m unittest discover -s tests/python -p 'test_*.py'
uv run pytest packages/solver/tests -q
git diff --check
git status --short
```

Go 生成器测试在 `packages/generator/` 目录执行：

```bash
GOCACHE=/tmp/sinan-go-build-cache go test ./...
```

## 统一仓库级构建

当前仓库级正式入口只有 `repo`：

```bash
uv run repo build all
```

只构建单个模块：

```bash
uv run repo build sinan-captcha
uv run repo build generator
uv run repo build solver
```

如果需要同时产出 Windows 版生成器：

```bash
uv run repo build all --goos windows --goarch amd64
```

这个命令会依次执行：

1. 构建 `sinan-captcha`
2. 构建 `sinan-generator`
3. 构建 `sinanz`

## 单独构建每个产物

### 构建 `sinan-captcha`

```bash
uv run repo build sinan-captcha
```

建议构建后立即做一次安装烟测：

```bash
uvx --from ./packages/sinan-captcha/dist/sinan_captcha-<version>-py3-none-any.whl sinan --help
```

### 构建 `sinan-generator`

当前平台：

```bash
uv run repo build generator
```

Windows amd64：

```bash
uv run repo build generator --goos windows --goarch amd64
```

### 构建 `sinanz`

```bash
uv run repo build solver
```

## 上传 `sinan-captcha` 到 PyPI

```bash
uv run repo publish-sinan
```

默认读取顺序：

- `PYPI_TOKEN`
- `UV_PUBLISH_TOKEN`

如果你们把 token 放在其他环境变量里，显式传：

```bash
uv run repo publish-sinan --token-env <TOKEN_ENV>
```

当前行为要点：

- 发布器只读取当前版本对应的 wheel 与 sdist
- 不会把 `dist/` 中的历史工件一起上传
- 上传目标目前只覆盖 `sinan-captcha`

## 上传 `sinanz` 到 PyPI

```bash
uv run repo publish-solver
```

如果要改 token 环境变量名：

```bash
uv run repo publish-solver --token-env <TOKEN_ENV>
```

当前前提：

- `packages/solver/dist/` 中已经有当前版本 `sinanz` 的 wheel 与 sdist
- `packages/solver/resources/` 已经是你确认过的 staged 资产版本

## solver 资产导出与 staging

### 第一步：从训练产线导出资产

```bash
uv run repo export-solver-assets \
  --group1-proposal-checkpoint runs/group1/<group1-run>/proposal-detector/weights/best.pt \
  --group1-query-checkpoint runs/group1/<group1-run>/query-parser/weights/best.pt \
  --group1-embedder-checkpoint runs/group1/<group1-run>/icon-embedder/weights/best.pt \
  --group1-run <group1-run> \
  --group2-checkpoint runs/group2/<group2-run>/weights/best.pt \
  --group2-run <group2-run> \
  --output-dir work_home/reports/solver-assets/<asset-version> \
  --asset-version <asset-version>
```

当前约束：

- `group2` checkpoint 与 run 名是必填
- `group1` 相关 checkpoint 当前可选
- 导出目录是中间交接资产，不会自动进入 `sinanz` 包
- 这一步产生的是“导出资产目录”，不是训练仓库 `solve` 使用的 runtime bundle

### 第二步：stage 到 `packages/solver/resources/`

```bash
uv run repo stage-solver-assets \
  --asset-dir work_home/reports/solver-assets/<asset-version>
```

这个命令会覆盖：

- `packages/solver/resources/manifest.json`
- `packages/solver/resources/metadata/*.json`
- `packages/solver/resources/models/*`

执行后请把这些改动当作“有意的发布前 staging”来审阅，不要把它们当成随手生成的缓存。

### 第三步：重新构建 `sinanz`

```bash
uv run repo build solver
```

## 组装 Windows 训练交付包

最小前提：

1. `packages/sinan-captcha/dist/` 中已经有当前版本 wheel
2. `packages/generator/dist/windows-amd64/sinan-generator.exe` 已经生成

最小命令：

```bash
uv run repo package-windows \
  --generator-exe packages/generator/dist/windows-amd64/sinan-generator.exe \
  --output-dir dist/windows-bundle-<version>
```

如果还要一起打包 solver bundle、数据集或素材：

```bash
uv run repo package-windows \
  --generator-exe packages/generator/dist/windows-amd64/sinan-generator.exe \
  --bundle-dir <bundle-dir> \
  --datasets-dir work_home/datasets \
  --materials-dir work_home/materials \
  --output-dir dist/windows-bundle-<version>
```

当前命令会自动写入：

- `python/`
- `generator/`
- 可选 `bundle/`
- 可选 `datasets/`
- 可选 `materials/`
- `README-交付包说明.txt`

这里的 `--bundle-dir` 指的是训练仓库 `sinan solve ...` 所使用的 runtime bundle；它和 `export-solver-assets` 输出目录、`packages/solver/resources/` 都不是同一层。

## 发版时最容易漏掉的 5 件事

1. 只改了根 `pyproject.toml`，却忘了真正的版本号在 `packages/sinan-captcha/pyproject.toml`
2. 误以为还存在 `sinan release` 或 `scripts/repo.py` 这类旧入口，没有直接使用 `uv run repo ...`
3. 执行了 `stage-solver-assets` 却忘了重新构建 `sinanz`
4. 误以为 `publish` 会上传 `sinanz`
5. 没在 `git status --short` 里核对 `packages/solver/resources/` 是否正是自己要发布的资产版本
