//! Tauri commands for QuickDoctor
//! Corresponds to app.go - frontend/backend bridge

use std::collections::HashMap;
use std::fs;
use std::sync::Arc;

use serde_json::Value;
use tauri::{AppHandle, Emitter, State};
use tokio::sync::RwLock;
use tokio_util::sync::CancellationToken;

use crate::core::{
    errors::AppError,
    grabber::Grabber,
    paths::cities_path,
    qr_login::FastQRLogin,
    state::{load_user_state, save_user_state},
    HealthClient, GrabConfig, LogEntry, Member,
};

/// Application state
pub struct AppState {
    pub client: Arc<HealthClient>,
    pub qr_cancel: RwLock<Option<CancellationToken>>,
    pub grab_cancel: RwLock<Option<CancellationToken>>,
}

impl AppState {
    pub fn new() -> Result<Self, AppError> {
        let client = HealthClient::new()?;
        Ok(Self {
            client: Arc::new(client),
            qr_cancel: RwLock::new(None),
            grab_cancel: RwLock::new(None),
        })
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new().expect("Failed to create AppState")
    }
}

/// Get cities list
#[tauri::command]
pub async fn get_cities() -> Result<Vec<crate::core::types::City>, String> {
    println!(">>> Command: get_cities");
    let path = cities_path().map_err(|e| e.to_string())?;
    let data = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let cities: Vec<crate::core::types::City> = serde_json::from_str(&data).map_err(|e| e.to_string())?;
    Ok(cities)
}

/// Get user state
#[tauri::command]
pub async fn get_user_state() -> Result<crate::core::types::UserState, String> {
    println!(">>> Command: get_user_state");
    let map = load_user_state().map_err(|e| e.to_string())?;
    Ok(crate::core::state::to_user_state_struct(&map))
}

/// Save user state
#[tauri::command]
pub async fn save_user_state_cmd(state: crate::core::types::UserState) -> Result<(), String> {
    println!(">>> Command: save_user_state_cmd: {:?}", state);
    let val = serde_json::to_value(state).map_err(|e| e.to_string())?;
    if let Value::Object(map) = val {
        let converted = map.into_iter().collect();
        save_user_state(converted).map_err(|e| e.to_string())
    } else {
        Err("invalid state object".into())
    }
}

/// Export logs to file
#[tauri::command]
pub async fn export_logs(
    _app: AppHandle,
    entries: Vec<LogEntry>,
) -> Result<Option<String>, String> {
    // Dialog plugin is registered in main.rs but not used here anymore as we use paths directly
    // If needed for future interactive saves, we can re-enable it.

    if entries.is_empty() {
        return Err("log entries is empty".into());
    }

    let filename = format!(
        "quickdoctor_logs_{}.txt",
        chrono::Local::now().format("%Y%m%d_%H%M%S")
    );

    // Save to logs directory
    let logs_dir = crate::core::paths::logs_dir().map_err(|e| e.to_string())?;
    let path = logs_dir.join(&filename);

    let mut content = String::new();
    content.push_str("QuickDoctor Logs Export\n");
    content.push_str(&format!(
        "ExportedAt: {}\n",
        chrono::Local::now().format("%Y-%m-%d %H:%M:%S")
    ));
    content.push_str(&format!("Total: {}\n\n", entries.len()));

    for entry in &entries {
        let level = if entry.level.trim().is_empty() {
            "INFO"
        } else {
            &entry.level.to_uppercase()
        };
        content.push_str(&format!("[{}] [{}] {}\n", entry.time, level, entry.message));
    }

    fs::write(&path, content).map_err(|e| e.to_string())?;
    Ok(Some(path.to_string_lossy().to_string()))
}

/// Get hospitals by city
#[tauri::command]
pub async fn get_hospitals_by_city(
    state: State<'_, AppState>,
    city_id: String,
) -> Result<Vec<crate::core::types::Hospital>, String> {
    println!(">>> Command: get_hospitals_by_city(id={})", city_id);
    state.client.ensure_cookies_loaded().await;
    state
        .client
        .get_hospitals_by_city(&city_id)
        .await
        .map_err(|e| e.to_string())
}

/// Get departments by unit
#[tauri::command]
pub async fn get_deps_by_unit(
    state: State<'_, AppState>,
    unit_id: String,
    city_pinyin: String,
) -> Result<Vec<crate::core::types::DepartmentCategory>, String> {
    println!(">>> Command: get_deps_by_unit(id={}, city={})", unit_id, city_pinyin);
    state.client.ensure_cookies_loaded().await;
    state
        .client
        .get_deps_by_unit(&unit_id, &city_pinyin)
        .await
        .map_err(|e| e.to_string())
}

/// Get members
#[tauri::command]
pub async fn get_members(state: State<'_, AppState>) -> Result<Vec<Member>, String> {
    println!(">>> Command: get_members");
    state.client.ensure_cookies_loaded().await;
    state.client.get_members().await.map_err(|e| e.to_string())
}

/// Check login status
#[tauri::command]
pub async fn check_login(app: AppHandle, state: State<'_, AppState>) -> Result<bool, String> {
    println!(">>> Command: check_login");
    let loaded = state.client.ensure_cookies_loaded().await;

    if !loaded && !state.client.has_access_hash().await {
        emit_log(&app, "warn", "登录校验：未发现本地 Cookie");
    }

    if !state.client.has_access_hash().await {
        emit_log(&app, "warn", "登录校验：缺少 access_hash");
        return Ok(false);
    }

    let ok = state.client.check_login().await;
    if ok {
        emit_log(&app, "success", "登录校验通过");
    } else {
        emit_log(&app, "warn", "登录校验失败");
    }

    Ok(ok)
}

/// Get schedule
#[tauri::command]
pub async fn get_schedule(
    state: State<'_, AppState>,
    unit_id: String,
    dep_id: String,
    date: String,
) -> Result<Vec<crate::core::types::DoctorSchedule>, String> {
    println!(">>> Command: get_schedule(unit={}, dep={}, date={})", unit_id, dep_id, date);
    state.client.ensure_cookies_loaded().await;
    
    state
        .client
        .get_schedule(&unit_id, &dep_id, &date)
        .await
        .map_err(|e| e.to_string())
}

/// Get ticket detail
#[tauri::command]
pub async fn get_ticket_detail(
    state: State<'_, AppState>,
    unit_id: String,
    dep_id: String,
    schedule_id: String,
    member_id: String,
) -> Result<Value, String> {
    state.client.ensure_cookies_loaded().await;
    
    let detail = state
        .client
        .get_ticket_detail(&unit_id, &dep_id, &schedule_id, &member_id)
        .await
        .map_err(|e| e.to_string())?;

    serde_json::to_value(detail).map_err(|e| e.to_string())
}

/// Submit order
#[tauri::command]
pub async fn submit_order(
    state: State<'_, AppState>,
    params: HashMap<String, String>,
) -> Result<Value, String> {
    state.client.ensure_cookies_loaded().await;
    
    let result = state
        .client
        .submit_order(&params, None)
        .await
        .map_err(|e| e.to_string())?;

    serde_json::to_value(result).map_err(|e| e.to_string())
}

/// Start QR login
#[tauri::command]
pub async fn start_qr_login(app: AppHandle, state: State<'_, AppState>) -> Result<(), String> {
    println!(">>> Command: start_qr_login");
    // Cancel any existing QR login
    {
        let mut cancel = state.qr_cancel.write().await;
        if let Some(token) = cancel.take() {
            token.cancel();
        }
    }

    let cancel_token = CancellationToken::new();
    {
        let mut cancel = state.qr_cancel.write().await;
        *cancel = Some(cancel_token.clone());
    }

    let app_clone = app.clone();
    let client = state.client.clone();

    tokio::spawn(async move {
        run_qr_login(app_clone, client, cancel_token).await;
    });

    Ok(())
}

/// Stop QR login
#[tauri::command]
pub async fn stop_qr_login(state: State<'_, AppState>) -> Result<(), String> {
    let mut cancel = state.qr_cancel.write().await;
    if let Some(token) = cancel.take() {
        token.cancel();
    }
    Ok(())
}

/// Start grab
#[tauri::command]
pub async fn start_grab(
    app: AppHandle,
    state: State<'_, AppState>,
    config: GrabConfig,
) -> Result<(), String> {
    println!(">>> Command: start_grab(unit={})", config.unit_id);
    // Ensure logged in
    state.client.ensure_cookies_loaded().await;
    if !state.client.has_access_hash().await {
        emit_log(&app, "error", "缺少 access_hash，无法启动抢号");
        let _ = app.emit("login-status", serde_json::json!({"loggedIn": false}));
        return Err("请先扫码登录".into());
    }

    emit_log(&app, "info", "检测到 access_hash，允许启动抢号");

    // Cancel any existing grab
    {
        let mut cancel = state.grab_cancel.write().await;
        if let Some(token) = cancel.take() {
            token.cancel();
        }
    }

    let cancel_token = CancellationToken::new();
    {
        let mut cancel = state.grab_cancel.write().await;
        *cancel = Some(cancel_token.clone());
    }

    let app_clone = app.clone();
    let client = state.client.clone();

    tokio::spawn(async move {
        run_grab(app_clone, client, config, cancel_token).await;
    });

    Ok(())
}

/// Stop grab
#[tauri::command]
pub async fn stop_grab(state: State<'_, AppState>) -> Result<(), String> {
    let mut cancel = state.grab_cancel.write().await;
    if let Some(token) = cancel.take() {
        token.cancel();
    }
    Ok(())
}

/// Run QR login flow
async fn run_qr_login(app: AppHandle, client: Arc<HealthClient>, _cancel_token: CancellationToken) {
    emit_qr_status(&app, "正在获取二维码...");

    let login = match FastQRLogin::new() {
        Ok(l) => l,
        Err(e) => {
            emit_log(&app, "error", &format!("二维码登录初始化失败: {}", e));
            emit_qr_status(&app, "二维码登录初始化失败");
            return;
        }
    };

    let (base64, uuid) = match login.get_qr_image_base64().await {
        Ok(r) => r,
        Err(e) => {
            emit_log(&app, "error", &format!("获取二维码失败: {}", e));
            emit_qr_status(&app, "获取二维码失败");
            return;
        }
    };

    // Emit QR image
    println!(">>> Emitting qr-image event...");
    let _ = app.emit(
        "qr-image",
        serde_json::json!({
            "uuid": uuid,
            "base64": base64,
        }),
    );

    emit_qr_status(&app, "请使用微信扫码");

    let app_clone = app.clone();
    let result = login
        .poll_status(std::time::Duration::from_secs(300), |msg| {
            let translated = translate_qr_status(msg);
            emit_qr_status(&app_clone, &translated);
        })
        .await;

    if result.success {
        emit_log(&app, "success", "登录成功");
        let _ = app.emit("login-status", serde_json::json!({"loggedIn": true}));
        client.load_cookies().await;
    } else {
        let translated = translate_qr_error(&result.message);
        emit_log(&app, "error", &format!("登录失败: {}", translated));
        let _ = app.emit("login-status", serde_json::json!({"loggedIn": false}));
    }
}

/// Run grab flow
async fn run_grab(
    app: AppHandle,
    client: Arc<HealthClient>,
    config: GrabConfig,
    cancel_token: CancellationToken,
) {
    use tokio::sync::mpsc;
    
    let grabber = Grabber::new(client);
    
    // Create channel for log messages
    let (log_tx, mut log_rx) = mpsc::unbounded_channel::<(String, String)>();
    
    // Spawn log receiver task
    let app_for_log = app.clone();
    let log_handle = tokio::spawn(async move {
        while let Some((level, message)) = log_rx.recv().await {
            emit_log(&app_for_log, &level, &message);
        }
    });
    
    // Run grabber with channel-based logging
    let log_sender = log_tx.clone();
    let result = grabber
        .run(config, cancel_token.clone(), move |level: &str, message: &str| {
            let _ = log_sender.send((level.to_string(), message.to_string()));
        })
        .await;
    
    // Close channel and wait for log task
    drop(log_tx);
    let _ = log_handle.await;

    if cancel_token.is_cancelled() {
        let _ = app.emit(
            "grab-finished",
            serde_json::json!({
                "success": false,
                "message": "stopped",
            }),
        );
        return;
    }

    if result.success {
        let _ = app.emit(
            "grab-finished",
            serde_json::json!({
                "success": true,
                "message": result.message,
                "detail": result.detail,
            }),
        );
    } else {
        let _ = app.emit(
            "grab-finished",
            serde_json::json!({
                "success": false,
                "message": result.message,
            }),
        );
    }
}

/// Emit log message
fn emit_log(app: &AppHandle, level: &str, message: &str) {
    let _ = app.emit(
        "log-message",
        serde_json::json!({
            "level": level,
            "message": message,
        }),
    );
}

/// Emit QR status
fn emit_qr_status(app: &AppHandle, message: &str) {
    let _ = app.emit("qr-status", serde_json::json!({"message": message}));
}

/// Translate QR status message
fn translate_qr_status(message: &str) -> String {
    match message {
        "waiting for scan" => "等待扫码...".into(),
        "scanned, confirm on phone" => "已扫码，请在手机上确认".into(),
        "logging in" => "正在登录...".into(),
        "confirmed but no code, retrying" => "已确认但未获取到登录码，正在重试...".into(),
        _ => message.into(),
    }
}

/// Translate QR error message
fn translate_qr_error(message: &str) -> String {
    match message {
        "canceled" => "已取消".into(),
        "qr expired" => "二维码已过期".into(),
        "uuid not initialized" => "二维码未初始化".into(),
        "no cookies received" => "未获取到有效 Cookie".into(),
        "missing access_hash" => "登录未完成：缺少 access_hash".into(),
        _ => message.into(),
    }
}
