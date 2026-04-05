#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NativeBridgeError {
    BridgeNotWired,
}

impl NativeBridgeError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::BridgeNotWired => "bridge_not_wired",
        }
    }
}
