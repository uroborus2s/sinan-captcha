# 使用者角色：安装与使用最终求解包

这页只面向最终调用方，不面向训练者。

本页默认你已经从维护者拿到 `sinanz` 的 wheel 或安装源，目标是把它装进本地 Python 环境并明确公开调用面。

## 1. 你会使用到什么

- Python 包：`sinanz`
- 顶层函数：
  - `sn_match_slider(...)`
  - `sn_match_targets(...)`
- 可选对象封装：
  - `CaptchaSolver(...)`

## 2. 安装方式

如果维护者给你的是 wheel 文件：

```bash
uv pip install .\sinanz-*.whl
```

或：

```bash
pip install .\sinanz-*.whl
```

如果维护者提供的是包名：

```bash
uv pip install sinanz
```

安装完成后，先做一次导入自检：

```bash
python -c "from sinanz import sn_match_slider, sn_match_targets; print('ok')"
```

当前 `sinanz` 是纯 Python 包，滑块专项运行时依赖 `onnxruntime`。维护者发布的 wheel 会把模型资产一起带上，但不会附带独立的 Rust 扩展。

## 3. 两个公开业务入口

### 3.1 滑块验证码

- 输入：
  - `background_image`
  - `puzzle_piece_image`
  - 可选 `puzzle_piece_start_bbox`
- 输出：
  - `target_center`
  - `target_bbox`
  - 可选 `puzzle_piece_offset`
- 对应函数：

```python
from sinanz import sn_match_slider
```

### 3.2 点选验证码

- 输入：
  - `query_icons_image`
  - `background_image`
- 输出：
  - `ordered_target_centers`
  - `ordered_targets`
  - `missing_query_orders`
  - `ambiguous_query_orders`
- 对应函数：

```python
from sinanz import sn_match_targets
```

## 4. 最短使用示例

```python
from sinanz import sn_match_slider

result = sn_match_slider(
    background_image=r"D:\cases\master.png",
    puzzle_piece_image=r"D:\cases\tile.png",
)

print(result.target_center)
```

如果你需要把模型资产放在包外部，改用对象封装：

```python
from pathlib import Path

from sinanz import CaptchaSolver

solver = CaptchaSolver(
    device="cpu",
    asset_root=Path(r"D:\solver-assets\models"),
)
```

`asset_root` 应指向包含 `slider_gap_locator.onnx`、`click_proposal_detector.onnx`、`click_query_parser.onnx`、`click_icon_embedder.onnx` 等模型文件的目录。普通业务接入默认不需要这个参数。

## 5. 使用边界

- 只依赖 `sinanz` 暴露出来的函数和结果类型。
- 不要让业务应用直接读取训练目录 `datasets/`、`runs/` 或 `weights/`。
- 不要让业务应用直接调用训练仓库内部的 `core.solve`。
- 如果维护者提供的是内嵌模型的 wheel，业务代码不需要手工传模型路径。
- 如果你自己从源码安装，确保 `onnxruntime` 能正常安装到当前 Python 环境。

下一页继续读：

- [使用者角色：在自己的应用中接入并做业务测试](./application-integration.md)
