# sinanz_ext

`sinanz_ext` is the staged Rust native-extension crate for the standalone `sinanz` solver package.

Planned responsibilities:

- host the Python bridge for native inference execution
- own ONNX Runtime session setup and provider selection
- execute performance-sensitive inference paths for `group1` and `group2`

The current implementation is intentionally minimal. It freezes the Cargo layout and native build boundary before `pyo3` and ONNX Runtime are wired in.

Current scaffold boundary:

- `src/lib.rs` exposes staged ABI and bridge metadata helpers
- `src/bridge.rs` reserves the Python bridge naming layer
- `src/runtime.rs` reserves runtime target and provider ordering
- `src/error.rs` reserves internal native error codes
