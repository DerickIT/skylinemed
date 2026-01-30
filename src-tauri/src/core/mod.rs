//! Core module exports for QuickDoctor

pub mod types;
pub mod errors;
pub mod paths;
pub mod cookies;
pub mod state;
pub mod client;
pub mod proxy;
pub mod qr_login;
pub mod grabber;

// Re-export common types
pub use types::*;
pub use client::HealthClient;
pub use grabber::Grabber;
pub use qr_login::FastQRLogin;
pub use proxy::ProxyPool;
pub use errors::{AppError, AppResult};
