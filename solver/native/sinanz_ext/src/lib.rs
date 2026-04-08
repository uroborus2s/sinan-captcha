#![forbid(unsafe_code)]

mod bridge;
mod error;
mod runtime;

/// Tracks the staged native ABI expected by the Python wrapper.
pub const SINANZ_NATIVE_ABI_VERSION: u32 = 1;

pub fn sinanz_native_abi_version() -> u32 {
    SINANZ_NATIVE_ABI_VERSION
}

pub fn bridge_stage() -> &'static str {
    bridge::BRIDGE_STAGE
}

pub fn bridge_module() -> &'static str {
    bridge::bridge_module()
}

pub fn group2_entrypoint() -> &'static str {
    bridge::group2_entrypoint()
}

pub fn runtime_target() -> &'static str {
    runtime::RUNTIME_TARGET
}

pub fn preferred_execution_providers() -> [&'static str; 2] {
    runtime::preferred_execution_providers()
}

pub fn default_bridge_error_code() -> &'static str {
    error::NativeBridgeError::BridgeNotWired.code()
}

#[cfg(test)]
mod tests {
    use super::{
        bridge_module,
        group2_entrypoint,
        bridge_stage,
        default_bridge_error_code,
        preferred_execution_providers,
        runtime_target,
        sinanz_native_abi_version,
        SINANZ_NATIVE_ABI_VERSION,
    };

    #[test]
    fn abi_version_matches_exported_symbol() {
        assert_eq!(sinanz_native_abi_version(), SINANZ_NATIVE_ABI_VERSION);
    }

    #[test]
    fn staged_bridge_metadata_is_exposed() {
        assert_eq!(bridge_stage(), "group2-onnx-bridge");
        assert_eq!(bridge_module(), "sinanz.native_bridge");
        assert_eq!(group2_entrypoint(), "match_slider_gap");
        assert_eq!(runtime_target(), "rust-onnxruntime");
        assert_eq!(
            preferred_execution_providers(),
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
        );
        assert_eq!(default_bridge_error_code(), "bridge_not_wired");
    }
}
