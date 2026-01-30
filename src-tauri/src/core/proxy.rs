//! Proxy management for QuickDoctor
//! Corresponds to core/proxy.go

use std::time::Duration;

use rand::Rng;
use reqwest::Client;
use serde::Deserialize;
use tokio::sync::RwLock;

use super::errors::{AppError, AppResult};

const PROXY_API_URL: &str = "https://proxy.scdn.io/api/get_proxy.php";
const PROXY_PROBE_URL: &str = "https://www.91160.com/favicon.ico";
const DEFAULT_PROXY_PROTOCOL: &str = "https";
const DEFAULT_PROXY_COUNTRY: &str = "CN";
const DEFAULT_PROXY_FETCH_COUNT: i32 = 6;
const PROXY_API_TIMEOUT_SECS: u64 = 12;
const PROXY_PROBE_TIMEOUT_SECS: u64 = 6;
const PROXY_API_RETRY_MAX: i32 = 3;
const PROXY_API_RETRY_BACKOFF_MIN_MS: u64 = 400;
const PROXY_API_RETRY_BACKOFF_MAX_MS: u64 = 900;

#[derive(Debug, Deserialize)]
struct ProxyAPIResponse {
    code: i32,
    message: String,
    data: ProxyAPIData,
}

#[derive(Debug, Deserialize)]
struct ProxyAPIData {
    proxies: Vec<String>,
    count: i32,
}

/// Proxy pool manager
pub struct ProxyPool {
    pool: RwLock<Vec<String>>,
    protocol: RwLock<String>,
    country: RwLock<String>,
}

impl ProxyPool {
    /// Create a new proxy pool
    pub fn new() -> Self {
        Self {
            pool: RwLock::new(Vec::new()),
            protocol: RwLock::new(String::new()),
            country: RwLock::new(String::new()),
        }
    }

    /// Rotate to a new proxy
    pub async fn rotate_proxy(&self, protocol: &str, country: &str) -> AppResult<String> {
        let protocols = resolve_proxy_protocols(protocol)?;
        let normalized_country = normalize_proxy_country(country);

        let mut error_notes = Vec::new();

        for normalized_protocol in &protocols {
            // Check if we need to fetch new proxies
            let need_fetch = {
                let current_protocol = self.protocol.read().await;
                let current_country = self.country.read().await;
                let pool = self.pool.read().await;
                *normalized_protocol != *current_protocol
                    || normalized_country != *current_country
                    || pool.is_empty()
            };

            if need_fetch {
                match fetch_proxy_list(normalized_protocol, &normalized_country, DEFAULT_PROXY_FETCH_COUNT).await {
                    Ok(list) => {
                        let mut pool = self.pool.write().await;
                        let mut protocol_lock = self.protocol.write().await;
                        let mut country_lock = self.country.write().await;
                        *pool = list;
                        *protocol_lock = normalized_protocol.clone();
                        *country_lock = normalized_country.clone();
                    }
                    Err(e) => {
                        error_notes.push(format!("{}: {}", normalized_protocol, e));
                        continue;
                    }
                }
            }

            // Try proxies from pool
            let mut last_err: Option<AppError> = None;

            loop {
                let proxy_host = {
                    let mut pool = self.pool.write().await;
                    if pool.is_empty() {
                        break;
                    }
                    pool.remove(0)
                };

                let proxy_host = proxy_host.trim().to_string();
                if proxy_host.is_empty() {
                    continue;
                }

                let proxy_url = build_proxy_url(normalized_protocol, &proxy_host);
                if proxy_url.is_empty() {
                    continue;
                }

                if let Err(e) = test_proxy_connectivity(&proxy_url).await {
                    last_err = Some(e);
                    continue;
                }

                return Ok(proxy_url);
            }

            if let Some(e) = last_err {
                error_notes.push(format!("{}: {}", normalized_protocol, e));
            } else {
                error_notes.push(format!("{}: no proxy available", normalized_protocol));
            }
        }

        if error_notes.is_empty() {
            Err(AppError::ProxyError("no proxy available".into()))
        } else {
            Err(AppError::ProxyError(error_notes.join("; ")))
        }
    }

    /// Clear proxy pool
    pub async fn clear(&self) {
        let mut pool = self.pool.write().await;
        pool.clear();
    }
}

impl Default for ProxyPool {
    fn default() -> Self {
        Self::new()
    }
}

/// Resolve proxy protocols
fn resolve_proxy_protocols(protocol: &str) -> AppResult<Vec<String>> {
    let normalized = protocol.trim().to_lowercase();
    if normalized.is_empty() || normalized == "all" {
        return Ok(vec!["https".into(), "http".into(), "socks5".into()]);
    }
    match normalized.as_str() {
        "http" | "https" | "socks5" => Ok(vec![normalized]),
        "socks4" => Err(AppError::ProxyError("socks4 is not supported".into())),
        _ => Err(AppError::ProxyError(format!("unsupported proxy protocol: {}", normalized))),
    }
}

/// Normalize proxy country
fn normalize_proxy_country(country: &str) -> String {
    let normalized = country.trim().to_uppercase();
    if normalized == "CN" {
        normalized
    } else {
        DEFAULT_PROXY_COUNTRY.to_string()
    }
}

/// Fetch proxy list from API
async fn fetch_proxy_list(protocol: &str, country: &str, count: i32) -> AppResult<Vec<String>> {
    let count = if count <= 0 { DEFAULT_PROXY_FETCH_COUNT } else { count };
    let protocol = if protocol.is_empty() { DEFAULT_PROXY_PROTOCOL } else { protocol };
    let country = normalize_proxy_country(country);

    let mut last_err: Option<AppError> = None;

    for attempt in 1..=PROXY_API_RETRY_MAX {
        match fetch_proxy_list_once(protocol, &country, count).await {
            Ok(list) if !list.is_empty() => return Ok(list),
            Ok(_) => {
                last_err = Some(AppError::ProxyError("proxy list is empty".into()));
            }
            Err(e) => {
                last_err = Some(e);
            }
        }

        if attempt < PROXY_API_RETRY_MAX {
            let backoff = random_backoff_ms(PROXY_API_RETRY_BACKOFF_MIN_MS, PROXY_API_RETRY_BACKOFF_MAX_MS);
            tokio::time::sleep(Duration::from_millis(backoff)).await;
        }
    }

    Err(last_err.unwrap_or_else(|| AppError::ProxyError("proxy fetch failed".into())))
}

/// Fetch proxy list once
async fn fetch_proxy_list_once(protocol: &str, country: &str, count: i32) -> AppResult<Vec<String>> {
    let client = Client::builder()
        .timeout(Duration::from_secs(PROXY_API_TIMEOUT_SECS))
        .build()?;

    let mut url = format!("{}?protocol={}&count={}", PROXY_API_URL, protocol, count);
    if !country.is_empty() {
        url.push_str(&format!("&country_code={}", country.to_uppercase()));
    }

    let resp = client.get(&url).send().await?;
    if !resp.status().is_success() {
        return Err(AppError::ProxyError(format!("proxy api http {}", resp.status())));
    }

    let payload: ProxyAPIResponse = resp.json().await?;
    if payload.code != 200 {
        let msg = if payload.message.is_empty() {
            "proxy api error".to_string()
        } else {
            payload.message
        };
        return Err(AppError::ProxyError(msg));
    }

    let mut unique = std::collections::HashSet::new();
    let out: Vec<String> = payload
        .data
        .proxies
        .into_iter()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty() && unique.insert(s.clone()))
        .collect();

    if out.is_empty() {
        return Err(AppError::ProxyError("proxy list is empty".into()));
    }

    Ok(out)
}

/// Build proxy URL from protocol and host
fn build_proxy_url(protocol: &str, host: &str) -> String {
    let host = host.trim();
    if host.is_empty() {
        return String::new();
    }
    if host.contains("://") {
        return host.to_string();
    }
    format!("{}://{}", protocol, host)
}

/// Test proxy connectivity
async fn test_proxy_connectivity(proxy_url: &str) -> AppResult<()> {
    let proxy = reqwest::Proxy::all(proxy_url).map_err(|e| AppError::ProxyError(e.to_string()))?;

    let client = Client::builder()
        .proxy(proxy)
        .timeout(Duration::from_secs(PROXY_PROBE_TIMEOUT_SECS))
        .build()?;

    let resp = client.get(PROXY_PROBE_URL).send().await?;

    if !resp.status().is_success() && resp.status().as_u16() >= 400 {
        return Err(AppError::ProxyError(format!("proxy probe http {}", resp.status())));
    }

    Ok(())
}

/// Random backoff in milliseconds
fn random_backoff_ms(min_ms: u64, max_ms: u64) -> u64 {
    if min_ms == 0 && max_ms == 0 {
        return 0;
    }
    let max = if max_ms < min_ms { min_ms } else { max_ms };
    if max == min_ms {
        return max;
    }
    let mut rng = rand::thread_rng();
    rng.gen_range(min_ms..=max)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resolve_protocols() {
        assert!(resolve_proxy_protocols("https").unwrap().contains(&"https".to_string()));
        assert!(resolve_proxy_protocols("").unwrap().len() == 3);
        assert!(resolve_proxy_protocols("socks4").is_err());
    }

    #[test]
    fn test_build_proxy_url() {
        assert_eq!(build_proxy_url("https", "1.2.3.4:8080"), "https://1.2.3.4:8080");
        assert_eq!(build_proxy_url("https", "http://1.2.3.4:8080"), "http://1.2.3.4:8080");
        assert!(build_proxy_url("https", "").is_empty());
    }
}
