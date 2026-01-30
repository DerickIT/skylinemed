//! User state management for QuickDoctor
//! Corresponds to core/state.go

use std::collections::HashMap;
use std::fs;

use chrono::{Duration, Local};
use serde_json::Value;

use super::errors::{AppError, AppResult};
use super::paths::user_state_path;
use super::types::UserState;

const DEFAULT_CITY_ID: &str = "5";

/// Load user state from file
pub fn load_user_state() -> AppResult<HashMap<String, Value>> {
    let path = user_state_path()?;

    if !path.exists() {
        return Ok(default_user_state());
    }

    let data = fs::read_to_string(&path)?;
    let raw: HashMap<String, Value> = serde_json::from_str(&data)?;
    let merged = merge_user_state(default_user_state(), raw);
    Ok(normalize_user_state(merged))
}

/// Save user state to file
pub fn save_user_state(update: HashMap<String, Value>) -> AppResult<()> {
    if update.is_empty() {
        return Err(AppError::ConfigError("State is empty".into()));
    }

    let path = user_state_path()?;

    // Load existing state
    let existing = if path.exists() {
        let data = fs::read_to_string(&path)?;
        serde_json::from_str::<HashMap<String, Value>>(&data).unwrap_or_default()
    } else {
        HashMap::new()
    };

    // Merge states
    let merged = merge_user_state(default_user_state(), existing);
    let final_state = merge_user_state(merged, update);
    let normalized = normalize_user_state(final_state);

    // Save
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let data = serde_json::to_string_pretty(&normalized)?;
    fs::write(&path, data)?;
    Ok(())
}

/// Get default user state
pub fn default_user_state() -> HashMap<String, Value> {
    let mut state = HashMap::new();
    state.insert("city_id".into(), Value::String(DEFAULT_CITY_ID.into()));
    state.insert("unit_id".into(), Value::Null);
    state.insert("dep_id".into(), Value::Null);
    state.insert("doctor_id".into(), Value::Null);
    state.insert("member_id".into(), Value::Null);
    state.insert("target_dates".into(), Value::Array(vec![]));
    state.insert("target_date".into(), Value::String(default_target_date()));
    state.insert(
        "time_slots".into(),
        Value::Array(vec![Value::String("am".into()), Value::String("pm".into())]),
    );
    state.insert("proxy_submit_enabled".into(), Value::Bool(true));
    state
}

/// Merge two user states (overlay takes precedence)
fn merge_user_state(
    base: HashMap<String, Value>,
    overlay: HashMap<String, Value>,
) -> HashMap<String, Value> {
    let mut out = base;
    for (key, value) in overlay {
        out.insert(key, value);
    }
    out
}

/// Normalize user state values
fn normalize_user_state(mut state: HashMap<String, Value>) -> HashMap<String, Value> {
    // Normalize city_id
    let city_id = state
        .get("city_id")
        .and_then(|v| v.as_str())
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .unwrap_or(DEFAULT_CITY_ID);
    state.insert("city_id".into(), Value::String(city_id.into()));

    // Normalize target_date
    let target_date = state
        .get("target_date")
        .and_then(|v| v.as_str())
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .unwrap_or(&default_target_date())
        .to_string();
    state.insert("target_date".into(), Value::String(target_date));

    // Normalize target_dates
    let target_dates = normalize_string_array(state.get("target_dates"));
    state.insert("target_dates".into(), Value::Array(target_dates));

    // Normalize time_slots
    let time_slots = normalize_time_slots(state.get("time_slots"));
    state.insert("time_slots".into(), Value::Array(time_slots));

    // Normalize proxy_submit_enabled
    let proxy_enabled = normalize_bool(state.get("proxy_submit_enabled"), true);
    state.insert("proxy_submit_enabled".into(), Value::Bool(proxy_enabled));

    state
}

/// Normalize a boolean value
fn normalize_bool(value: Option<&Value>, default: bool) -> bool {
    match value {
        Some(Value::Bool(b)) => *b,
        Some(Value::String(s)) => {
            let s = s.trim().to_lowercase();
            if s.is_empty() {
                return default;
            }
            matches!(s.as_str(), "1" | "true" | "yes" | "on")
        }
        Some(Value::Number(n)) => n.as_f64().map(|v| v != 0.0).unwrap_or(default),
        _ => default,
    }
}

/// Normalize time slots array
fn normalize_time_slots(value: Option<&Value>) -> Vec<Value> {
    match value {
        Some(Value::Array(arr)) if !arr.is_empty() => arr
            .iter()
            .filter_map(|v| v.as_str().map(|s| Value::String(s.trim().to_string())))
            .filter(|v| !v.as_str().unwrap_or("").is_empty())
            .collect(),
        _ => vec![Value::String("am".into()), Value::String("pm".into())],
    }
}

/// Normalize string array
fn normalize_string_array(value: Option<&Value>) -> Vec<Value> {
    match value {
        Some(Value::Array(arr)) => arr
            .iter()
            .filter_map(|v| v.as_str().map(|s| Value::String(s.trim().to_string())))
            .filter(|v| !v.as_str().unwrap_or("").is_empty())
            .collect(),
        Some(Value::String(s)) if !s.trim().is_empty() => {
            vec![Value::String(s.trim().to_string())]
        }
        _ => vec![],
    }
}

/// Get default target date (7 days from now)
fn default_target_date() -> String {
    let future = Local::now() + Duration::days(7);
    future.format("%Y-%m-%d").to_string()
}

/// Convert HashMap to UserState struct
pub fn to_user_state_struct(map: &HashMap<String, Value>) -> UserState {
    UserState {
        city_id: map
            .get("city_id")
            .and_then(|v| v.as_str())
            .unwrap_or(DEFAULT_CITY_ID)
            .to_string(),
        unit_id: map
            .get("unit_id")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        dep_id: map
            .get("dep_id")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        doctor_id: map
            .get("doctor_id")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        member_id: map
            .get("member_id")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        target_date: map
            .get("target_date")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        target_dates: map
            .get("target_dates")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default(),
        time_slots: map
            .get("time_slots")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_else(|| vec!["am".into(), "pm".into()]),
        proxy_submit_enabled: normalize_bool(map.get("proxy_submit_enabled"), true),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_target_date() {
        let date = default_target_date();
        assert!(!date.is_empty());
        assert!(date.contains('-'));
    }

    #[test]
    fn test_normalize_bool() {
        assert!(normalize_bool(Some(&Value::Bool(true)), false));
        assert!(!normalize_bool(Some(&Value::Bool(false)), true));
        assert!(normalize_bool(Some(&Value::String("true".into())), false));
        assert!(normalize_bool(Some(&Value::String("1".into())), false));
        assert!(!normalize_bool(Some(&Value::String("false".into())), true));
        assert!(normalize_bool(None, true));
    }
}
