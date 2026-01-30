//! QR Login for QuickDoctor
//! Corresponds to core/qr_login.go - WeChat QR code login flow

use std::sync::Arc;
use std::time::Duration;

use base64::Engine;
use regex::Regex;
use reqwest::cookie::Jar;
use reqwest::header::{HeaderValue, ACCEPT, CONNECTION, ORIGIN, REFERER, USER_AGENT};
use reqwest::Client;
use tokio::sync::RwLock;
use url::Url;

use super::cookies::save_cookie_file;
use super::errors::{AppError, AppResult};
use super::types::{CookieRecord, QRLoginResult};

const WECHAT_APP_ID: &str = "wxdfec0615563d691d";
const WECHAT_REDIRECT: &str = "http://user.91160.com/supplier-wechat.html";
const QR_CONNECT_ORIGIN: &str = "https://open.weixin.qq.com/";
const DEFAULT_USER_AGENT: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

/// WeChat QR Login handler
pub struct FastQRLogin {
    uuid: RwLock<String>,
    state: RwLock<String>,
    client: Client,
}

impl FastQRLogin {
    /// Create a new QR login handler
    pub fn new() -> AppResult<Self> {
        let client = Client::builder()
            .user_agent(DEFAULT_USER_AGENT)
            .timeout(Duration::from_secs(30))
            .build()
            .map_err(|e| AppError::HttpError(e))?;

        Ok(Self {
            uuid: RwLock::new(String::new()),
            state: RwLock::new(String::new()),
            client,
        })
    }

    /// Get QR code image and UUID
    pub async fn get_qr_image(&self) -> AppResult<(Vec<u8>, String)> {
        let state = format!("login_{}", chrono::Utc::now().timestamp());
        {
            let mut state_lock = self.state.write().await;
            *state_lock = state.clone();
        }

        let encoded_redirect = urlencoding::encode(WECHAT_REDIRECT);
        let target_url = format!(
            "https://open.weixin.qq.com/connect/qrconnect?appid={}&redirect_uri={}&response_type=code&scope=snsapi_login&state={}#wechat_redirect",
            WECHAT_APP_ID, encoded_redirect, state
        );

        let resp = self
            .client
            .get(&target_url)
            .headers(wechat_headers())
            .send()
            .await?;

        let body = resp.text().await?;

        // Extract UUID from response
        let re = Regex::new(r"/connect/qrcode/([a-zA-Z0-9_-]+)").unwrap();
        let uuid = re
            .captures(&body)
            .and_then(|caps| caps.get(1))
            .map(|m| m.as_str().to_string())
            .ok_or_else(|| AppError::ParseError("QR UUID not found".into()))?;

        {
            let mut uuid_lock = self.uuid.write().await;
            *uuid_lock = uuid.clone();
        }

        // Fetch QR code image
        let qr_url = format!("https://open.weixin.qq.com/connect/qrcode/{}", uuid);
        let qr_resp = self
            .client
            .get(&qr_url)
            .headers(wechat_headers())
            .send()
            .await?;

        let qr_bytes = qr_resp.bytes().await?.to_vec();

        // Validate image format (JPEG or PNG)
        if qr_bytes.len() < 4 {
            return Err(AppError::ParseError("QR image too small".into()));
        }

        let is_jpeg = qr_bytes[0] == 0xFF && qr_bytes[1] == 0xD8;
        let is_png = qr_bytes[0] == 0x89 && qr_bytes[1] == 0x50 && qr_bytes[2] == 0x4E && qr_bytes[3] == 0x47;

        if !is_jpeg && !is_png {
            return Err(AppError::ParseError("QR image invalid format".into()));
        }

        Ok((qr_bytes, uuid))
    }

    /// Poll for QR scan status
    pub async fn poll_status<F>(
        &self,
        timeout: Duration,
        mut on_status: F,
    ) -> QRLoginResult
    where
        F: FnMut(&str),
    {
        let uuid = {
            let uuid_lock = self.uuid.read().await;
            uuid_lock.clone()
        };

        if uuid.is_empty() {
            return QRLoginResult {
                success: false,
                message: "uuid not initialized".into(),
                cookie_path: None,
            };
        }

        let start = std::time::Instant::now();
        let mut last_status = String::new();
        let mut last_param = "404".to_string();
        let mut retry_404 = 0;

        let re_errcode = Regex::new(r"wx_errcode\s*=\s*(\d+)").unwrap();
        let re_code = Regex::new(r#"wx_code\s*=\s*['"]([^'"]*)['"]"#).unwrap();
        let re_redirect = Regex::new(r#"window\.location(?:\.href|\.replace)?\s*\(?['"]([^'"]+)['"]"#).unwrap();

        loop {
            if start.elapsed() > timeout {
                return QRLoginResult {
                    success: false,
                    message: "qr expired".into(),
                    cookie_path: None,
                };
            }

            let ts = chrono::Utc::now().timestamp_millis();
            let poll_url = format!(
                "https://lp.open.weixin.qq.com/connect/l/qrconnect?uuid={}&last={}&_={}",
                uuid, last_param, ts
            );

            let resp = match self.client.get(&poll_url).headers(wechat_headers()).send().await {
                Ok(r) => r,
                Err(_) => {
                    tokio::time::sleep(Duration::from_secs(2)).await;
                    continue;
                }
            };

            let body = match resp.text().await {
                Ok(b) => b,
                Err(_) => {
                    tokio::time::sleep(Duration::from_secs(1)).await;
                    continue;
                }
            };

            let mut status = "0".to_string();
            if let Some(caps) = re_errcode.captures(&body) {
                if let Some(m) = caps.get(1) {
                    status = m.as_str().to_string();
                }
            }

            let mut code = String::new();
            if let Some(caps) = re_code.captures(&body) {
                if let Some(m) = caps.get(1) {
                    code = m.as_str().to_string();
                }
            }

            let mut redirect_url = String::new();
            if let Some(caps) = re_redirect.captures(&body) {
                if let Some(m) = caps.get(1) {
                    redirect_url = m.as_str().to_string();
                }
            }

            if status == "0" && (!code.is_empty() || !redirect_url.is_empty()) {
                status = "405".to_string();
            }

            if ["408", "201", "405", "402", "404"].contains(&status.as_str()) {
                last_param = status.clone();
            }

            match status.as_str() {
                "408" => {
                    if last_status != "408" {
                        on_status("waiting for scan");
                    }
                    last_status = "408".to_string();
                    retry_404 = 0;
                }
                "404" | "402" => {
                    retry_404 += 1;
                    last_status = "404".to_string();
                    if retry_404 > 60 {
                        return QRLoginResult {
                            success: false,
                            message: "qr expired".into(),
                            cookie_path: None,
                        };
                    }
                    tokio::time::sleep(Duration::from_secs(1)).await;
                    continue;
                }
                "201" => {
                    if last_status != "201" {
                        on_status("scanned, confirm on phone");
                    }
                    last_status = "201".to_string();
                    retry_404 = 0;
                }
                "405" => {
                    // Extract code from redirect URL if needed
                    if code.is_empty() && !redirect_url.is_empty() {
                        if let Ok(parsed) = Url::parse(&redirect_url) {
                            if let Some(state_param) = parsed.query_pairs().find(|(k, _)| k == "state") {
                                let mut state_lock = self.state.write().await;
                                *state_lock = state_param.1.to_string();
                            }
                            if let Some(code_param) = parsed.query_pairs().find(|(k, _)| k == "code") {
                                code = code_param.1.to_string();
                            }
                        }
                    }

                    if code.is_empty() {
                        on_status("confirmed but no code, retrying");
                        tokio::time::sleep(Duration::from_secs(1)).await;
                        continue;
                    }

                    on_status("logging in");
                    return self.exchange_cookie(&code).await;
                }
                _ => {}
            }

            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }

    /// Exchange code for cookies
    async fn exchange_cookie(&self, code: &str) -> QRLoginResult {
        let cookie_jar = Arc::new(Jar::default());

        let client = match Client::builder()
            .user_agent(DEFAULT_USER_AGENT)
            .cookie_provider(cookie_jar.clone())
            .build()
        {
            Ok(c) => c,
            Err(e) => {
                return QRLoginResult {
                    success: false,
                    message: e.to_string(),
                    cookie_path: None,
                };
            }
        };

        let state = {
            let state_lock = self.state.read().await;
            state_lock.clone()
        };

        let callback_url = if state.is_empty() {
            format!("{}?code={}", WECHAT_REDIRECT, code)
        } else {
            format!("{}?code={}&state={}", WECHAT_REDIRECT, code, urlencoding::encode(&state))
        };

        // Follow redirect chain
        let _ = client
            .get(&callback_url)
            .header(USER_AGENT, DEFAULT_USER_AGENT)
            .header(REFERER, QR_CONNECT_ORIGIN)
            .send()
            .await;

        let _ = client.get("https://www.91160.com/").send().await;
        let _ = client.get("https://user.91160.com/user/index.html").send().await;

        // Extract cookies from jar - use CookieStore trait
        let mut records = Vec::new();
        for domain in ["www.91160.com", "user.91160.com", ".91160.com"] {
            if let Ok(url) = Url::parse(&format!("https://{}", domain)) {
                // CookieStore::cookies returns Option<HeaderValue>
                use reqwest::cookie::CookieStore;
                if let Some(header_value) = cookie_jar.cookies(&url) {
                    if let Ok(cookie_str) = header_value.to_str() {
                        for part in cookie_str.split(';') {
                            let part = part.trim();
                            if let Some(eq_pos) = part.find('=') {
                                let name = part[..eq_pos].trim().to_string();
                                let value = part[eq_pos + 1..].trim().to_string();
                                if !name.is_empty() && !value.is_empty() {
                                    records.push(CookieRecord {
                                        name,
                                        value,
                                        domain: format!(".{}", domain.trim_start_matches('.')),
                                        path: "/".into(),
                                    });
                                }
                            }
                        }
                    }
                }
            }
        }

        if records.is_empty() {
            return QRLoginResult {
                success: false,
                message: "no cookies received".into(),
                cookie_path: None,
            };
        }

        let has_access = records.iter().any(|r| r.name == "access_hash");
        if !has_access {
            return QRLoginResult {
                success: false,
                message: "missing access_hash".into(),
                cookie_path: None,
            };
        }

        match save_cookie_file(&records) {
            Ok(()) => {
                let path = super::paths::cookies_path().ok().map(|p| p.to_string_lossy().to_string());
                QRLoginResult {
                    success: true,
                    message: "login ok".into(),
                    cookie_path: path,
                }
            }
            Err(e) => QRLoginResult {
                success: false,
                message: e.to_string(),
                cookie_path: None,
            },
        }
    }

    /// Get QR image as base64
    pub async fn get_qr_image_base64(&self) -> AppResult<(String, String)> {
        let (bytes, uuid) = self.get_qr_image().await?;
        let base64 = base64::engine::general_purpose::STANDARD.encode(&bytes);
        Ok((base64, uuid))
    }
}

impl Default for FastQRLogin {
    fn default() -> Self {
        Self::new().expect("Failed to create FastQRLogin")
    }
}

/// Build WeChat API headers
fn wechat_headers() -> reqwest::header::HeaderMap {
    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert(USER_AGENT, HeaderValue::from_static(DEFAULT_USER_AGENT));
    headers.insert(REFERER, HeaderValue::from_static(QR_CONNECT_ORIGIN));
    headers.insert(ORIGIN, HeaderValue::from_static("https://open.weixin.qq.com"));
    headers.insert(ACCEPT, HeaderValue::from_static("*/*"));
    headers.insert(CONNECTION, HeaderValue::from_static("keep-alive"));
    headers
}
