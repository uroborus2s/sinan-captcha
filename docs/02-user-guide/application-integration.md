# 使用者角色：在自己的应用中接入并做业务测试

这页只讲如何把 `sinanz` 接到你自己的应用中。

## 1. 推荐的接入方式

对业务应用来说，推荐只封装两件事：

- `sn_match_slider(...)`
- `sn_match_targets(...)`

这样你的业务代码就不会直接依赖训练仓库内部目录、模型文件名或推理细节。

## 2. 顶层函数与对象封装

最简单的用法是直接调用顶层函数：

```python
from sinanz import sn_match_slider, sn_match_targets
```

如果你需要复用同一个 `device` 或自定义模型资产目录，改用对象封装：

```python
from pathlib import Path

from sinanz import CaptchaSolver

solver = CaptchaSolver(
    device="cpu",
    asset_root=Path(r"D:\solver-assets\models"),
)
```

`asset_root` 应指向包含模型文件的目录。普通业务接入通常不需要它。

## 3. `sn_match_slider(...)`

示例：

```python
from sinanz import sn_match_slider

result = sn_match_slider(
    background_image=r"D:\cases\master.png",
    puzzle_piece_image=r"D:\cases\tile.png",
    puzzle_piece_start_bbox=(12, 88, 64, 140),
    device="auto",
    return_debug=True,
)

print(result.target_center)
print(result.target_bbox)
print(result.puzzle_piece_offset)
```

参数说明：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `background_image` | 是 | 背景图路径。当前运行时只接受本地文件路径字符串或 `Path`。 |
| `puzzle_piece_image` | 是 | 拼图块图片路径。当前运行时只接受本地文件路径字符串或 `Path`。 |
| `puzzle_piece_start_bbox` | 否 | 拼图块初始框，格式为 `(x1, y1, x2, y2)`，坐标系与背景图一致。传入后结果里会额外返回 `puzzle_piece_offset`。 |
| `device` | 否 | 推理设备，默认 `auto`。常见值是 `auto`、`cpu`、`0`。 |
| `return_debug` | 否 | 是否返回调试信息。开启后结果中的 `debug.notes` 会包含运行时备注。 |

返回结果 `SliderGapCenterResult`：

| 字段 | 说明 |
| --- | --- |
| `target_center` | 目标中心点 `(x, y)`，坐标系与背景图一致。 |
| `target_bbox` | 目标框 `(x1, y1, x2, y2)`，坐标系与背景图一致。 |
| `puzzle_piece_offset` | 仅当传入 `puzzle_piece_start_bbox` 时返回，表示预测目标框左上角相对起始框左上角的偏移。 |
| `debug` | 仅当 `return_debug=True` 时返回。 |

## 4. `sn_match_targets(...)`

示例：

```python
from sinanz import sn_match_targets

result = sn_match_targets(
    query_icons_image=r"D:\cases\query.png",
    background_image=r"D:\cases\scene.png",
    device="auto",
    return_debug=True,
)

print(result.ordered_target_centers)
```

参数说明：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `query_icons_image` | 是 | 查询图路径，图里应按业务顺序列出待点击图标。当前运行时只接受本地文件路径字符串或 `Path`。 |
| `background_image` | 是 | 背景图路径。当前运行时只接受本地文件路径字符串或 `Path`。 |
| `device` | 否 | 推理设备，默认 `auto`。 |
| `return_debug` | 否 | 是否返回调试信息。 |

返回结果 `OrderedClickTargetsResult`：

| 字段 | 说明 |
| --- | --- |
| `ordered_target_centers` | 按查询图顺序排列的中心点列表。 |
| `ordered_targets` | 详细命中结果列表，每项包含 `query_order`、`center`、`class_id`、`class_name`、`score`。 |
| `missing_query_orders` | 当前轮次没有找到结果的查询序号。 |
| `ambiguous_query_orders` | 当前轮次存在歧义的查询序号。 |
| `debug` | 仅当 `return_debug=True` 时返回。 |

如果当前安装包没有提供点选运行时，调用 `sn_match_targets(...)` 会抛出 `SolverRuntimeError`。业务侧应把这类错误统一捕获并上报。

## 5. 推荐的应用内封装

```python
from pathlib import Path

from sinanz import (
    SolverAssetError,
    SolverInputError,
    SolverRuntimeError,
    sn_match_slider,
    sn_match_targets,
)


class CaptchaSolverGateway:
    def match_slider(self, background_image: str | Path, puzzle_piece_image: str | Path):
        try:
            return sn_match_slider(
                background_image=background_image,
                puzzle_piece_image=puzzle_piece_image,
            )
        except (SolverInputError, SolverAssetError, SolverRuntimeError) as exc:
            raise RuntimeError(f"slider solve failed: {exc}") from exc

    def match_targets(self, query_icons_image: str | Path, background_image: str | Path):
        try:
            return sn_match_targets(
                query_icons_image=query_icons_image,
                background_image=background_image,
            )
        except (SolverInputError, SolverAssetError, SolverRuntimeError) as exc:
            raise RuntimeError(f"click solve failed: {exc}") from exc
```

## 6. 你需要处理的异常

| 异常类型 | 什么时候会出现 |
| --- | --- |
| `SolverInputError` | 图片路径不存在，或者传入了当前运行时不支持的图片类型。 |
| `SolverAssetError` | 模型资产缺失、路径错误或资产版本不兼容。 |
| `SolverRuntimeError` | 推理运行时不可用、模型无法加载，或当前 wheel 尚未提供某个专项的运行时。 |

## 7. 业务侧测试建议

- 用一层业务网关隔离第三方库调用。
- 把原始输入图片、返回结果和异常日志打到同一条业务日志里。
- 对滑块记录中心点误差，对点选记录单点命中率和整组命中率。
- 不要让业务代码自己解析模型文件、metadata 或包内资源目录。

如果你当前是训练者，请先回到训练者路线：

- [训练者角色：训练机安装](./windows-bundle-install.md)
