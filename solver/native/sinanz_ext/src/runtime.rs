pub const RUNTIME_TARGET: &str = "rust-onnxruntime";

pub fn preferred_execution_providers() -> [&'static str; 2] {
    ["CUDAExecutionProvider", "CPUExecutionProvider"]
}
