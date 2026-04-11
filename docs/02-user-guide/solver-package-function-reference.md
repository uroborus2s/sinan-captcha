# 使用者：Solver 包函数参考（`sinanz`）

本页给出 `sinanz` 的公开函数、类型与异常定义。

## 1. 模块导出（`__all__`）

```python
from sinanz import (
    BBox,
    CaptchaSolver,
    ClickCaptchaDebugInfo,
    ImageInput,
    OrderedClickTarget,
    OrderedClickTargetsResult,
    SliderGapCenterResult,
    SliderGapDebugInfo,
    SolverAssetError,
    SolverError,
    SolverInputError,
    SolverRuntimeError,
    sn_match_slider,
    sn_match_targets,
)
```

## 2. 公开调用签名

## 2.1 滑块函数

```python
def sn_match_slider(
    background_image: ImageInput,
    puzzle_piece_image: ImageInput,
    *,
    puzzle_piece_start_bbox: BBox | None = None,
    device: str = "auto",
    return_debug: bool = False,
) -> SliderGapCenterResult:
    ...
```

## 2.2 点选函数

```python
def sn_match_targets(
    query_icons_image: ImageInput,
    background_image: ImageInput,
    *,
    device: str = "auto",
    return_debug: bool = False,
) -> OrderedClickTargetsResult:
    ...
```

## 2.3 面向对象封装

```python
class CaptchaSolver:
    def __init__(self, *, device: str = "auto", asset_root: str | Path | None = None) -> None: ...

    def sn_match_slider(
        self,
        background_image: ImageInput,
        puzzle_piece_image: ImageInput,
        *,
        puzzle_piece_start_bbox: BBox | None = None,
        return_debug: bool = False,
    ) -> SliderGapCenterResult: ...

    def sn_match_targets(
        self,
        query_icons_image: ImageInput,
        background_image: ImageInput,
        *,
        return_debug: bool = False,
    ) -> OrderedClickTargetsResult: ...
```

## 3. 输入类型定义

```python
ImageInput = str | Path | bytes
BBox = tuple[int, int, int, int]
Point = tuple[int, int]
```

其中 `str` 同时支持：

- 本地路径字符串
- base64 字符串（含 `data:` URI）
- 网络图片 URL（`http://`、`https://`）

图片格式支持范围以 Pillow 可解码格式为准，例如 JPEG、PNG、WebP、BMP、GIF、TIFF。不支持或损坏输入统一返回 `SolverInputError`。

URL 输入默认安全边界：

- 协议仅 `http`/`https`
- 下载大小上限 20 MB
- 请求超时 8 秒
- 最大重定向 5 次

## 4. 返回类型定义

## 4.1 `SliderGapCenterResult`

```python
@dataclass(frozen=True, slots=True)
class SliderGapCenterResult:
    target_center: Point
    target_bbox: BBox
    puzzle_piece_offset: Point | None = None
    debug: SliderGapDebugInfo | None = None
```

字段语义：

- `target_center`: 背景图坐标系中的目标中心点。
- `target_bbox`: 背景图坐标系中的目标框。
- `puzzle_piece_offset`: 仅在传入 `puzzle_piece_start_bbox` 时可用。
- `debug`: `return_debug=True` 时包含运行时注记。

## 4.2 `OrderedClickTargetsResult`

```python
@dataclass(frozen=True, slots=True)
class OrderedClickTargetsResult:
    ordered_target_centers: list[Point]
    ordered_targets: list[OrderedClickTarget]
    missing_query_orders: list[int] = field(default_factory=list)
    ambiguous_query_orders: list[int] = field(default_factory=list)
    debug: ClickCaptchaDebugInfo | None = None
```

## 4.3 `OrderedClickTarget`

```python
@dataclass(frozen=True, slots=True)
class OrderedClickTarget:
    query_order: int
    center: Point
    class_id: int
    class_name: str
    score: float
```

## 4.4 调试结构

```python
@dataclass(frozen=True, slots=True)
class SliderGapDebugInfo:
    notes: list[str] = field(default_factory=list)

@dataclass(frozen=True, slots=True)
class ClickCaptchaDebugInfo:
    notes: list[str] = field(default_factory=list)
```

`notes` 典型内容：

- `device=<...>`
- `runtime=python-onnxruntime`
- `provider=CPUExecutionProvider` 或 CUDA provider
- 模型文件名

## 5. 异常类型

```python
class SolverError(RuntimeError): ...
class SolverInputError(SolverError): ...
class SolverAssetError(SolverError): ...
class SolverRuntimeError(SolverError): ...
```

触发场景：

- `SolverInputError`: 输入路径不存在、输入类型不支持
- `SolverAssetError`: 模型文件缺失、`asset_root` 不完整
- `SolverRuntimeError`: `onnxruntime/numpy/Pillow` 或执行流程异常

## 6. 设备参数说明

- `device="auto"`：自动选择可用 provider
- `device="cpu"`：强制 CPU
- 其他字符串：按 runtime 规则尝试映射（例如 GPU provider）

## 7. `asset_root` 覆盖策略

若传入 `asset_root`，将优先从该目录读取模型：

- `slider_gap_locator.onnx`
- `click_proposal_detector.onnx`
- `click_query_parser.onnx`
- `click_icon_embedder.onnx`

未传入 `asset_root` 时，默认读取包内 `resources/models`。

## 8. 调用示例（含 debug）

```python
from sinanz import sn_match_slider, sn_match_targets

slider = sn_match_slider(
    background_image=r"D:\cases\master.png",
    puzzle_piece_image=r"D:\cases\tile.png",
    puzzle_piece_start_bbox=(12, 88, 64, 140),
    return_debug=True,
)
print(slider.target_center, slider.debug.notes if slider.debug else [])

targets = sn_match_targets(
    query_icons_image=r"D:\cases\query.png",
    background_image=r"D:\cases\scene.png",
    return_debug=True,
)
print(targets.ordered_target_centers, targets.missing_query_orders, targets.ambiguous_query_orders)
```

如果你还没看安装与接入流程，请先读：
[使用者：Solver 包使用指南](./solver-package-usage-guide.md)
