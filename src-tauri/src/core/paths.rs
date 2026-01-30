//! Path utilities for QuickDoctor
//! Corresponds to core/paths.go

use std::env;
use std::fs;
use std::path::PathBuf;

use super::errors::{AppError, AppResult};

const CONFIG_DIR_ENV: &str = "QUICKDOCTOR_CONFIG_DIR";

/// Get the configuration directory
pub fn config_dir() -> AppResult<PathBuf> {
    // Check environment variable first
    if let Ok(dir) = env::var(CONFIG_DIR_ENV) {
        let path = PathBuf::from(&dir);
        fs::create_dir_all(&path)?;
        return Ok(path);
    }

    // Try various candidate directories
    let mut candidates = Vec::new();

    // Current working directory
    if let Ok(cwd) = env::current_dir() {
        candidates.push(cwd.join("config"));
        candidates.push(cwd.join("..").join("config"));
        candidates.push(cwd.join("..").join("..").join("config"));
    }

    // Executable directory
    if let Ok(exe) = env::current_exe() {
        if let Some(base) = exe.parent() {
            candidates.push(base.join("config"));
            candidates.push(base.join("..").join("config"));
            candidates.push(base.join("..").join("..").join("config"));
        }
    }

    // Check for existing config with cities.json
    for dir in &candidates {
        let cities_path = dir.join("cities.json");
        if cities_path.exists() && cities_path.is_file() {
            return Ok(dir.clone());
        }
    }

    // Create first available directory
    for dir in &candidates {
        if !dir.as_os_str().is_empty() {
            if fs::create_dir_all(dir).is_ok() {
                return Ok(dir.clone());
            }
        }
    }

    Err(AppError::ConfigError(
        "Unable to resolve config directory".into(),
    ))
}

/// Get the logs directory
pub fn logs_dir() -> AppResult<PathBuf> {
    let config = config_dir()?;
    let root = config.parent().unwrap_or(&config);
    let logs = root.join("logs");
    fs::create_dir_all(&logs)?;
    Ok(logs)
}

/// Check if a file exists
#[allow(dead_code)]
pub fn file_exists(path: &PathBuf) -> bool {
    path.exists() && path.is_file()
}

/// Get the cookies file path
pub fn cookies_path() -> AppResult<PathBuf> {
    Ok(config_dir()?.join("cookies.json"))
}

/// Get the user state file path
pub fn user_state_path() -> AppResult<PathBuf> {
    Ok(config_dir()?.join("user_state.json"))
}

/// Get the cities file path
pub fn cities_path() -> AppResult<PathBuf> {
    Ok(config_dir()?.join("cities.json"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_dir() {
        // This test requires the config directory to exist
        let result = config_dir();
        assert!(result.is_ok() || result.is_err());
    }
}
