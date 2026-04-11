# sinanz

Standalone pure-Python solver package for slider-gap and ordered-click captcha solving.

Current scope:

- exposes business-oriented public entrypoints:
  - `sn_match_slider(...)`
  - `sn_match_targets(...)`
- keeps Python modules flat under `src/`
- keeps embedded inference assets outside `src/`, under `resources/`
- `group2` service resolves `slider_gap_locator.onnx` directly from `resources/`
- `group2` preprocessing and ONNX inference both run in Python
- runtime dependencies are:
  - `numpy`
  - `onnxruntime`
  - `pillow`

Packaging intent:

- published `sinanz` wheels are now standard pure-Python wheels
- model assets remain external files bundled into the wheel under `resources/`
- installation only needs normal Python dependency resolution for `numpy` + `onnxruntime` + `pillow`

Runtime migration continues in:

- `TASK-SOLVER-MIG-008`
- `TASK-SOLVER-MIG-009`
- `TASK-SOLVER-MIG-011`
