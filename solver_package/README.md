# sinanz

Standalone Python solver package scaffold for slider-gap and ordered-click captcha solving.

Current scope:

- exposes business-oriented public entrypoints:
  - `sn_match_slider(...)`
  - `sn_match_targets(...)`
- reserves package resource directories for embedded inference assets
- includes a staged Rust native-extension project in `native/sinanz_ext/`
- includes a Python-side native bridge contract in `src/sinanz/native_bridge.py`
- `group2` service now resolves `slider_gap_locator.onnx` and calls the native bridge contract
- does not implement the final `pyo3 + ONNX Runtime` native module yet

Runtime migration continues in:

- `TASK-SOLVER-MIG-008`
- `TASK-SOLVER-MIG-009`
- `TASK-SOLVER-MIG-011`
