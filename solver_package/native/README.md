# Native Extension Workspace

This directory hosts the staged Rust native-extension project for `sinanz`.

Current status:

- workspace and crate layout are frozen
- Python-side bridge metadata is fixed in `src/sinanz/native_bridge.py`
- root `Cargo.toml` and crate metadata agree on module name, bridge module, and runtime target
- future tasks will add `pyo3` and `onnxruntime` integration
- the current crate is a minimal `cdylib` scaffold used to validate the build boundary
