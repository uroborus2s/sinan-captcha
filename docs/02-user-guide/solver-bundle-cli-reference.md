# 训练者：Solver Bundle CLI 参考（`sinan solve`）

`sinan solve` 是训练仓库内的本地 bundle 工具链，负责三件事：

1. 从训练产物构建 bundle（`build-bundle`）
2. 做发布前结构校验（`validate-bundle`）
3. 用请求 JSON 跑单次求解验收（`run`）

说明：这是训练阶段的本地交付命令，不是最终业务系统直接调用的长期线上入口。

## 1. 命令总览

```text
uv run sinan solve
├── build-bundle
├── validate-bundle
└── run
```

| 命令 | 主要用途 | 典型使用场景 |
| --- | --- | --- |
| `build-bundle` | 打包 `group1/group2` 训练产物 | 某次训练完成后准备交付 |
| `validate-bundle` | 结构与文件完整性校验 | 发布前门禁检查 |
| `run` | 使用 bundle 跑一次请求 | 本地 smoke、回归验收 |

## 2. `build-bundle`

### 2.1 用途

从 `runs/group1/<run>` 与 `runs/group2/<run>` 收口模型和配置，生成可迁移 bundle 目录。

### 2.2 适用场景

- 训练完成后需要打一个“可复制”的求解包。
- 准备做离线验收或交付测试。

### 2.3 语法

```bash
uv run sinan solve build-bundle \
  --bundle-dir <dir> \
  --group1-run <run-name> \
  --group2-run <run-name> \
  [--train-root <dir>] \
  [--bundle-version <version>] \
  [--force]
```

### 2.4 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--bundle-dir` | 是 | 无 | bundle 输出目录。 |
| `--group1-run` | 是 | 无 | `runs/group1/<run>` 来源。 |
| `--group2-run` | 是 | 无 | `runs/group2/<run>` 来源。 |
| `--train-root` | 否 | `<repo>/work_home` | 训练根目录。 |
| `--bundle-version` | 否 | `bundle-dir` 目录名 | 写入 `manifest.json` 的版本号。 |
| `--force` | 否 | `false` | 允许覆盖非空 bundle 目录。 |

### 2.5 最小示例

```bash
uv run sinan solve build-bundle \
  --bundle-dir work_home/bundles/solver/current \
  --group1-run firstpass \
  --group2-run firstpass \
  --force
```

### 2.6 成功标志

- 命令输出 bundle 摘要 JSON。
- `bundle-dir` 下存在 `manifest.json` 与所需模型文件。

### 2.7 常见误用

- `group1-run`/`group2-run` 填错，导致拿错模型版本。
- 未传 `--force` 直接覆盖旧目录，结果构建被阻断。

## 3. `validate-bundle`

### 3.1 用途

验证 bundle 的结构、清单和关键文件是否完整可用。

### 3.2 适用场景

- 每次 `build-bundle` 之后立即执行。
- 发布或回归验收前作为硬性门禁。

### 3.3 语法

```bash
uv run sinan solve validate-bundle --bundle-dir <dir>
```

### 3.4 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--bundle-dir` | 是 | 无 | 待校验 bundle 目录。 |

### 3.5 校验内容

- `manifest.json` 结构与字段合法性
- 模型文件与 matcher 配置存在性
- `bundle_format / router / matcher` 与当前版本约束一致性

### 3.6 成功标志

- 命令退出码为 `0`。
- 输出 bundle 摘要 JSON，无 `invalid_bundle` 错误。

### 3.7 常见误用

- 跳过 `validate-bundle` 直接上线，导致运行时才发现 bundle 缺文件。

## 4. `run`

### 4.1 用途

在指定 bundle 上执行一次请求 JSON，输出标准响应 JSON。

### 4.2 适用场景

- 构建后 smoke：确认 bundle 至少可完成一条 `group1/group2` 请求。
- 复现线上案例：用同一请求文件做本地回放。

### 4.3 语法

```bash
uv run sinan solve run --bundle-dir <dir> --request <request.json> [--output <response.json>]
```

### 4.4 参数说明

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--bundle-dir` | 是 | 无 | 求解使用的 bundle 目录。 |
| `--request` | 是 | 无 | 请求 JSON 文件路径。 |
| `--output` | 否 | 空 | 响应输出文件；不传则打印到 stdout。 |

### 4.5 行为约定

- 无 `--output`：响应 JSON 打印到 stdout。
- 有 `--output`：响应写入目标文件。
- 返回码：`status=ok` 返回 `0`；`status=error` 返回 `1`。

### 4.6 最小示例

```bash
uv run sinan solve run \
  --bundle-dir work_home/bundles/solver/current \
  --request work_home/requests/group2_req.json \
  --output work_home/requests/group2_resp.json
```

### 4.7 常见误用

- 误以为请求内相对路径按 shell 当前目录解析（实际按请求文件所在目录解析）。
- `task_hint` 与 `inputs` 形态冲突，导致 `invalid_request`。

## 5. 请求 JSON 合同

### 5.1 通用字段（可运行模板）

```json
{
  "request_id": "req_group1_001",
  "task_hint": "group1",
  "inputs": {
    "query_image": "inputs/query.png",
    "scene_image": "inputs/scene.png"
  },
  "options": {
    "device": "0",
    "return_debug": false
  }
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `request_id` | 是 | 非空字符串。 |
| `task_hint` | 否 | `group1` 或 `group2`；可省略。 |
| `inputs` | 是 | 必须能判定任务类型：`query_image + scene_image` 或 `master_image + tile_image`。 |
| `options.device` | 否 | 设备标识，默认 `"0"`。 |
| `options.return_debug` | 否 | 是否返回调试字段，默认 `false`。 |

### 5.2 `group1` 请求示例

```json
{
  "request_id": "req_group1_001",
  "task_hint": "group1",
  "inputs": {
    "query_image": "inputs/query.png",
    "scene_image": "inputs/scene.png"
  },
  "options": {
    "device": "0",
    "return_debug": true
  }
}
```

### 5.3 `group2` 请求示例

```json
{
  "request_id": "req_group2_001",
  "task_hint": "group2",
  "inputs": {
    "master_image": "inputs/master.png",
    "tile_image": "inputs/tile.png",
    "tile_start_bbox": [10, 20, 50, 60]
  },
  "options": {
    "device": "0",
    "return_debug": true
  }
}
```

`tile_start_bbox` 可省略；省略时响应不会返回 `offset_x/offset_y`。

路径解析规则：

- 请求内相对路径（如 `inputs/query.png`）按 `--request` 指向 JSON 所在目录解析。
- 不按 shell 当前工作目录解析。
- 生产环境建议用绝对路径，或保持请求文件与 `inputs/` 同级。

## 6. 响应 JSON 合同

### 6.1 通用结构

```json
{
  "request_id": "req_group2_001",
  "task": "group2",
  "status": "ok",
  "route_source": "task_hint",
  "bundle_version": "current",
  "result": {}
}
```

`status=error` 时包含：

```json
{
  "error": {
    "code": "invalid_request",
    "message": "...",
    "details": []
  }
}
```

### 6.2 常见错误码

| 错误码 | 说明 |
| --- | --- |
| `invalid_request` | 请求结构非法，或 `task_hint` 与输入形态冲突。 |
| `invalid_bundle` | bundle 不合法或缺文件。 |
| `missing_input` | 请求中引用的图片文件不存在。 |
| `runtime_error` | 推理执行异常。 |

## 7. `route_source` 含义

| 值 | 说明 |
| --- | --- |
| `task_hint` | 通过请求中的 `task_hint` 路由。 |
| `input_shape` | 通过 `inputs` 形态自动判定。 |
| `unknown` | 请求解析或 bundle 初始化失败时的兜底值。 |

## 8. 最小端到端顺序

```bash
uv run sinan solve build-bundle \
  --bundle-dir work_home/bundles/solver/current \
  --group1-run firstpass \
  --group2-run firstpass \
  --force

uv run sinan solve validate-bundle \
  --bundle-dir work_home/bundles/solver/current

uv run sinan solve run \
  --bundle-dir work_home/bundles/solver/current \
  --request work_home/requests/group2_req.json \
  --output work_home/requests/group2_resp.json
```
