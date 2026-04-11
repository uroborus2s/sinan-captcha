# 训练者：Solver Bundle CLI 参考（`sinan solve`）

`sinan solve` 是训练仓库里的本地 solver bundle 命令，用于：

1. 从训练产物构建 bundle
2. 校验 bundle
3. 以 JSON 请求运行一次求解

## 1. 命令树

```text
uv run sinan solve
├── build-bundle
├── validate-bundle
└── run
```

## 2. `build-bundle`

语法：

```bash
uv run sinan solve build-bundle \
  --bundle-dir <dir> \
  --group1-run <run-name> \
  --group2-run <run-name> \
  [--train-root <dir>] \
  [--bundle-version <version>] \
  [--force]
```

参数：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--bundle-dir` | 是 | 无 | bundle 输出目录。 |
| `--group1-run` | 是 | 无 | `runs/group1/<run>` 来源。 |
| `--group2-run` | 是 | 无 | `runs/group2/<run>` 来源。 |
| `--train-root` | 否 | `<repo>/work_home` | 训练根目录。 |
| `--bundle-version` | 否 | `bundle-dir` 目录名 | 写入 `manifest.json` 的版本号。 |
| `--force` | 否 | `false` | 允许覆盖非空 bundle 目录。 |

构建后命令会输出 bundle 摘要 JSON。

## 3. `validate-bundle`

语法：

```bash
uv run sinan solve validate-bundle --bundle-dir <dir>
```

作用：

- 校验 `manifest.json`
- 校验模型与 matcher 配置文件是否存在
- 校验 `bundle_format/router/matcher` 是否符合当前版本约束

成功时输出 bundle 摘要 JSON。

## 4. `run`

语法：

```bash
uv run sinan solve run --bundle-dir <dir> --request <request.json> [--output <response.json>]
```

行为：

- 无 `--output`：直接打印响应 JSON 到 stdout
- 有 `--output`：将响应写入指定路径
- 返回码：`status=ok` 返回 0，`status=error` 返回 1

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

### 5.2 `group1` 请求

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

### 5.3 `group2` 请求

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

- 请求里的相对路径（如 `inputs/query.png`）会按 `--request` 指向的 JSON 文件所在目录解析。
- 不按当前 shell 工作目录解析。
- 生产环境建议使用绝对路径，或把请求文件与 `inputs/` 放在同一目录层级。

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

## 8. 最小执行示例

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
