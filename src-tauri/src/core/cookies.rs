//! Cookie management for QuickDoctor
//! Corresponds to core/cookies.go

use std::collections::HashMap;
use std::fs;

use super::errors::{AppError, AppResult};
use super::paths::cookies_path;
use super::types::CookieRecord;

/// Load cookies from file
pub fn load_cookie_file() -> AppResult<Vec<CookieRecord>> {
    let path = cookies_path()?;
    if !path.exists() {
        return Ok(Vec::new());
    }

    let data = fs::read_to_string(&path)?;

    // Try parsing as array first
    if let Ok(list) = serde_json::from_str::<Vec<CookieRecord>>(&data) {
        return Ok(normalize_cookie_records(list));
    }

    // Try parsing as dict (legacy format)
    if let Ok(dict) = serde_json::from_str::<HashMap<String, String>>(&data) {
        let list: Vec<CookieRecord> = dict
            .into_iter()
            .map(|(name, value)| CookieRecord {
                name,
                value,
                domain: ".91160.com".into(),
                path: "/".into(),
            })
            .collect();
        return Ok(normalize_cookie_records(list));
    }

    Err(AppError::ParseError("Invalid cookie file format".into()))
}

/// Save cookies to file
pub fn save_cookie_file(records: &[CookieRecord]) -> AppResult<()> {
    let normalized = normalize_cookie_records(records.to_vec());
    if normalized.is_empty() {
        return Err(AppError::ConfigError("No cookies to save".into()));
    }

    let path = cookies_path()?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let data = serde_json::to_string_pretty(&normalized)?;
    fs::write(&path, data)?;
    Ok(())
}

/// Normalize cookie records (deduplicate and fill defaults)
pub fn normalize_cookie_records(records: Vec<CookieRecord>) -> Vec<CookieRecord> {
    let mut unique: HashMap<String, CookieRecord> = HashMap::new();

    for mut record in records {
        if record.name.is_empty() {
            continue;
        }
        if record.domain.is_empty() {
            record.domain = ".91160.com".into();
        }
        if record.path.is_empty() {
            record.path = "/".into();
        }

        let key = format!(
            "{}|{}|{}",
            record.domain.to_lowercase(),
            record.path,
            record.name
        );
        unique.insert(key, record);
    }

    unique.into_values().collect()
}

/// Check if access_hash cookie exists
pub fn has_access_hash(records: &[CookieRecord]) -> bool {
    records.iter().any(|r| r.name == "access_hash" && !r.value.is_empty())
}

/// Get cookie values by name
#[allow(dead_code)]
pub fn get_cookie_values(records: &[CookieRecord], name: &str) -> Vec<String> {
    records
        .iter()
        .filter(|r| r.name == name && !r.value.is_empty())
        .map(|r| r.value.clone())
        .collect()
}

/// Remove duplicate values from cookie list
pub fn unique_strings(values: Vec<String>) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    values.into_iter().filter(|v| seen.insert(v.clone())).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_cookies() {
        let records = vec![
            CookieRecord {
                name: "test".into(),
                value: "value1".into(),
                domain: "".into(),
                path: "".into(),
            },
            CookieRecord {
                name: "test".into(),
                value: "value2".into(),
                domain: ".91160.com".into(),
                path: "/".into(),
            },
        ];

        let normalized = normalize_cookie_records(records);
        assert_eq!(normalized.len(), 1);
        assert_eq!(normalized[0].domain, ".91160.com");
    }

    #[test]
    fn test_has_access_hash() {
        let records = vec![CookieRecord {
            name: "access_hash".into(),
            value: "abc123".into(),
            domain: ".91160.com".into(),
            path: "/".into(),
        }];
        assert!(has_access_hash(&records));
    }
}
