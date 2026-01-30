//! Error types for QuickDoctor
//! Corresponds to core/errors.go

use thiserror::Error;

/// Application error types
#[derive(Error, Debug)]
pub enum AppError {
    #[error("Login required: {0}")]
    LoginRequired(String),

    #[error("HTTP request failed: {0}")]
    HttpError(#[from] reqwest::Error),

    #[error("JSON parse error: {0}")]
    JsonError(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Configuration error: {0}")]
    ConfigError(String),

    #[error("Parse error: {0}")]
    ParseError(String),

    #[error("API error: {0}")]
    ApiError(String),

    #[error("Timeout: {0}")]
    Timeout(String),

    #[error("Cancelled")]
    Cancelled,

    #[error("Proxy error: {0}")]
    ProxyError(String),

    #[error("{0}")]
    Other(String),
}

impl From<String> for AppError {
    fn from(s: String) -> Self {
        AppError::Other(s)
    }
}

impl From<&str> for AppError {
    fn from(s: &str) -> Self {
        AppError::Other(s.to_string())
    }
}

/// Convert AppError to a user-friendly string for frontend
impl AppError {
    pub fn to_frontend_string(&self) -> String {
        match self {
            AppError::LoginRequired(_) => "登录已失效，请重新扫码".to_string(),
            AppError::HttpError(e) => format!("网络请求失败: {}", e),
            AppError::JsonError(e) => format!("数据解析失败: {}", e),
            AppError::IoError(e) => format!("文件操作失败: {}", e),
            AppError::ConfigError(msg) => format!("配置错误: {}", msg),
            AppError::ParseError(msg) => format!("解析错误: {}", msg),
            AppError::ApiError(msg) => format!("API 错误: {}", msg),
            AppError::Timeout(msg) => format!("超时: {}", msg),
            AppError::Cancelled => "操作已取消".to_string(),
            AppError::ProxyError(msg) => format!("代理错误: {}", msg),
            AppError::Other(msg) => msg.clone(),
        }
    }
}

/// Result type alias for the application
pub type AppResult<T> = Result<T, AppError>;

/// Serialize error for Tauri commands
impl serde::Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_frontend_string())
    }
}
