pub const BRIDGE_STAGE: &str = "group2-onnx-bridge";
pub const GROUP2_ENTRYPOINT: &str = "match_slider_gap";

pub fn bridge_module() -> &'static str {
    "sinanz.native_bridge"
}

pub fn group2_entrypoint() -> &'static str {
    GROUP2_ENTRYPOINT
}
