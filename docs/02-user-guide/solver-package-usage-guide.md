# 使用者：Solver 包使用指南（`sinanz`）

这页只面向调用方（业务应用开发者），目标是让你最短路径接入 `sinanz`。

## 1. 你将使用的公开入口

`sinanz` 当前公开业务入口固定为两类：

- 滑块：`sn_match_slider(...)`
- 点选：`sn_match_targets(...)`

可选面向对象封装：

- `CaptchaSolver(device="auto", asset_root=None)`

## 2. 安装

### 2.1 从 wheel 安装

```bash
uv pip install ./dist/sinanz-<version>-py3-none-any.whl
```

### 2.2 从包名安装

```bash
uv pip install sinanz
```

安装后做导入检查：

```bash
python -c "from sinanz import sn_match_slider, sn_match_targets, CaptchaSolver; print('ok')"
```

注意：请在“刚刚安装 `sinanz` 的同一 Python 环境”里执行这条检查，不要切换到其他环境再验证。

## 3. 快速开始

### 3.1 滑块验证码

```python
from sinanz import sn_match_slider

result = sn_match_slider(
    background_image=r"D:\cases\master.png",
    puzzle_piece_image=r"D:\cases\tile.png",
    device="auto",
)

print(result.target_center)        # (x, y)
print(result.target_bbox)          # (x1, y1, x2, y2)
print(result.puzzle_piece_offset)  # 未传 start bbox 时为 None
```

### 3.2 点选验证码

```python
from sinanz import sn_match_targets

result = sn_match_targets(
    query_icons_image=r"D:\cases\query.png",
    background_image=r"D:\cases\scene.png",
    device="auto",
)

print(result.ordered_target_centers)
print(result.missing_query_orders)
print(result.ambiguous_query_orders)
```

## 4. 复用配置（推荐 `CaptchaSolver`）

如果你要在服务里高频调用，建议构建一个长生命周期 solver 对象：

```python
from pathlib import Path
from sinanz import CaptchaSolver

solver = CaptchaSolver(
    device="cpu",
    asset_root=Path(r"D:\solver-assets\models"),  # 可选，不传则使用包内资源
)

slider = solver.sn_match_slider(
    background_image=r"D:\cases\master.png",
    puzzle_piece_image=r"D:\cases\tile.png",
)

clicks = solver.sn_match_targets(
    query_icons_image=r"D:\cases\query.png",
    background_image=r"D:\cases\scene.png",
)
```

## 5. `asset_root` 什么时候需要传

默认场景不需要 `asset_root`。仅当你要覆盖包内模型资源时才需要。

当前模型文件名约定：

- `slider_gap_locator.onnx`
- `click_proposal_detector.onnx`
- `click_query_parser.onnx`
- `click_icon_embedder.onnx`

如果 `asset_root` 缺文件，会抛 `SolverAssetError`。

## 6. 错误处理（生产建议）

建议把 `sinanz` 调用放在网关层，统一捕获：

- `SolverInputError`：输入路径不存在、输入类型不支持
- `SolverAssetError`：模型资产缺失或不兼容
- `SolverRuntimeError`：推理运行时问题（如 `onnxruntime` 不可用）

示例：

```python
from sinanz import (
    SolverAssetError,
    SolverInputError,
    SolverRuntimeError,
    sn_match_slider,
)

def match_slider_safe(background_image: str, puzzle_piece_image: str):
    try:
        return sn_match_slider(
            background_image=background_image,
            puzzle_piece_image=puzzle_piece_image,
        )
    except (SolverInputError, SolverAssetError, SolverRuntimeError) as exc:
        raise RuntimeError(f"captcha solver failed: {exc}") from exc
```

## 7. 接入约束

- 不要让业务代码直接读取训练目录（`datasets/`, `runs/`, `reports/`）。
- 不要依赖训练仓库内部模块（`packages/sinan-captcha/src/...`）作为线上入口。
- 当前运行时对图片输入的实际约束是“本地文件路径”。
- `device="auto"` 会优先使用可用的推理 provider，再回退 CPU。

## 8. 你还需要读哪一页

如果你要看函数签名、类型和返回字段，请继续读：

[使用者：Solver 包函数参考](./solver-package-function-reference.md)
