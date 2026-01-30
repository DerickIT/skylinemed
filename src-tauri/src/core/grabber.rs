//! Grabber engine for QuickDoctor
//! Corresponds to core/grabber.go - appointment grabbing logic

use std::collections::HashSet;
use std::sync::Arc;
use std::time::Duration;

use chrono::Local;
use rand::Rng;
use tokio::sync::RwLock;
use tokio_util::sync::CancellationToken;

use super::client::HealthClient;
use super::errors::{AppError, AppResult};
use super::proxy::ProxyPool;
use super::types::{GrabConfig, GrabResult, GrabSuccess, TicketDetail, TimeSlot};

const DATE_QUERY_JITTER_MAX_MS: u64 = 40;
const SUBMIT_MIN_INTERVAL_MS: u64 = 1800;
const SUBMIT_BACKOFF_MIN_MS: u64 = 2500;
const SUBMIT_BACKOFF_MAX_MS: u64 = 4200;

/// Appointment grabber
pub struct Grabber {
    client: Arc<HealthClient>,
    proxy_pool: Arc<ProxyPool>,
    last_submit_at: RwLock<Option<std::time::Instant>>,
}

impl Grabber {
    /// Create a new grabber
    pub fn new(client: Arc<HealthClient>) -> Self {
        Self {
            client,
            proxy_pool: Arc::new(ProxyPool::new()),
            last_submit_at: RwLock::new(None),
        }
    }

    /// Run the grabber with configuration
    pub async fn run<F>(
        &self,
        config: GrabConfig,
        cancel_token: CancellationToken,
        mut on_log: F,
    ) -> GrabResult
    where
        F: FnMut(&str, &str) + Send,
    {
        // Validate config
        if let Err(e) = config.validate() {
            emit_log(&mut on_log, "error", &e);
            return GrabResult {
                success: false,
                message: e,
                detail: None,
            };
        }

        emit_log(&mut on_log, "info", "grab engine started");
        emit_log(
            &mut on_log,
            "info",
            &format!(
                "grab config: dates={} doctor_ids={} time_types={} preferred={}",
                config.target_dates.join(","),
                config.doctor_ids.join(","),
                config.time_types.join(","),
                config.preferred_hours.join(",")
            ),
        );

        let is_precise = !config.doctor_ids.is_empty()
            || !config.preferred_hours.is_empty()
            || !config.time_types.is_empty();

        emit_log(
            &mut on_log,
            "info",
            if is_precise { "grab mode: precise" } else { "grab mode: fuzzy" },
        );

        if config.time_types.is_empty() {
            emit_log(&mut on_log, "info", "time_types 未设置，默认 am/pm");
        }

        // Wait for start time if specified
        if !config.start_time.is_empty() {
            self.wait_until(&config.start_time, config.use_server_time, cancel_token.clone(), &mut on_log).await;
            if cancel_token.is_cancelled() {
                return GrabResult {
                    success: false,
                    message: "stopped".into(),
                    detail: None,
                };
            }
        }

        let retry_interval = if config.retry_interval <= 0.0 { 0.5 } else { config.retry_interval };
        let mut attempt = 0;

        loop {
            if cancel_token.is_cancelled() {
                return GrabResult {
                    success: false,
                    message: "stopped".into(),
                    detail: None,
                };
            }

            attempt += 1;
            emit_log(&mut on_log, "info", &format!("attempt {}", attempt));

            match self.try_grab_once(&config, cancel_token.clone(), &mut on_log).await {
                Ok(Some(success)) => {
                    emit_log(&mut on_log, "success", "grab success");
                    return GrabResult {
                        success: true,
                        message: "success".into(),
                        detail: Some(success),
                    };
                }
                Ok(None) => {}
                Err(e) => {
                    if matches!(e, AppError::LoginRequired(_)) {
                        return GrabResult {
                            success: false,
                            message: e.to_frontend_string(),
                            detail: None,
                        };
                    }
                }
            }

            if config.max_retries > 0 && attempt >= config.max_retries {
                emit_log(&mut on_log, "warn", &format!("max retries reached ({})", config.max_retries));
                return GrabResult {
                    success: false,
                    message: "max retries reached".into(),
                    detail: None,
                };
            }

            if !sleep_with_cancel(Duration::from_secs_f64(retry_interval), cancel_token.clone()).await {
                return GrabResult {
                    success: false,
                    message: "stopped".into(),
                    detail: None,
                };
            }
        }
    }

    /// Try to grab once (one complete cycle through all dates)
    async fn try_grab_once<F>(
        &self,
        config: &GrabConfig,
        cancel_token: CancellationToken,
        on_log: &mut F,
    ) -> AppResult<Option<GrabSuccess>>
    where
        F: FnMut(&str, &str) + Send,
    {
        let doctor_set: HashSet<String> = config.doctor_ids.iter().cloned().collect();
        let time_set: HashSet<String> = if config.time_types.is_empty() {
            vec!["am".into(), "pm".into()].into_iter().collect()
        } else {
            config.time_types.iter().cloned().collect()
        };

        for date in &config.target_dates {
            if cancel_token.is_cancelled() {
                return Err(AppError::Cancelled);
            }

            // Add jitter
            if DATE_QUERY_JITTER_MAX_MS > 0 {
                let jitter = {
                    let mut rng = rand::thread_rng();
                    rng.gen_range(0..DATE_QUERY_JITTER_MAX_MS)
                };
                tokio::time::sleep(Duration::from_millis(jitter)).await;
            }

            match self.try_grab_date(config, date, &doctor_set, &time_set, cancel_token.clone(), on_log).await {
                Ok(Some(success)) => return Ok(Some(success)),
                Ok(None) => continue,
                Err(e) => {
                    if matches!(e, AppError::LoginRequired(_)) {
                        return Err(e);
                    }
                    continue;
                }
            }
        }

        Ok(None)
    }

    /// Try to grab for a specific date
    async fn try_grab_date<F>(
        &self,
        config: &GrabConfig,
        date: &str,
        doctor_set: &HashSet<String>,
        time_set: &HashSet<String>,
        cancel_token: CancellationToken,
        on_log: &mut F,
    ) -> AppResult<Option<GrabSuccess>>
    where
        F: FnMut(&str, &str) + Send,
    {
        emit_log(on_log, "info", &format!("schedule query: {}", date));

        let docs = self.client.get_schedule(&config.unit_id, &config.dep_id, date).await?;

        if docs.is_empty() {
            emit_log(on_log, "warn", &format!("no schedule on {}", date));
            return Ok(None);
        }

        emit_log(on_log, "info", &format!("schedule result: docs={}", docs.len()));

        for doc in &docs {
            if cancel_token.is_cancelled() {
                return Err(AppError::Cancelled);
            }

            // Filter by doctor
            if !doctor_set.is_empty() && !doctor_set.contains(&doc.doctor_id) {
                continue;
            }

            for slot in &doc.schedules {
                if cancel_token.is_cancelled() {
                    return Err(AppError::Cancelled);
                }

                // Filter by time type
                if !time_set.is_empty() && !time_set.contains(&slot.time_type) {
                    continue;
                }

                // Check availability
                if slot.left_num <= 0 {
                    continue;
                }

                if slot.schedule_id.is_empty() {
                    continue;
                }

                emit_log(
                    on_log,
                    "success",
                    &format!("found slot: {} - {} (left {})", doc.doctor_name, slot.time_type_desc, slot.left_num),
                );

                // Get ticket detail
                let detail = match self.client.get_ticket_detail(&config.unit_id, &config.dep_id, &slot.schedule_id, &config.member_id).await {
                    Ok(d) => d,
                    Err(_) => {
                        emit_log(on_log, "warn", "ticket detail unavailable");
                        continue;
                    }
                };

                let times = if detail.times.is_empty() { &detail.time_slots } else { &detail.times };
                if times.is_empty() {
                    continue;
                }

                if detail.sch_data.is_empty() || detail.detlid_realtime.is_empty() || detail.level_code.is_empty() {
                    emit_log(on_log, "warn", "ticket detail missing fields");
                    continue;
                }

                // Select time slot
                let selected = pick_time_slot(times, &config.preferred_hours);
                emit_log(on_log, "info", &format!("selected time slot: {}", selected.name));

                // Resolve address
                let (address_id, address_text) = resolve_address(config, &detail, on_log);
                if address_id.is_empty() || address_text.is_empty() {
                    emit_log(on_log, "error", "missing address info");
                    continue;
                }

                // Build submit params
                let mut submit_params = std::collections::HashMap::new();
                submit_params.insert("unit_id".into(), config.unit_id.clone());
                submit_params.insert("dep_id".into(), config.dep_id.clone());
                submit_params.insert("schedule_id".into(), slot.schedule_id.clone());
                submit_params.insert("time_type".into(), slot.time_type.clone());
                submit_params.insert("doctor_id".into(), doc.doctor_id.clone());
                submit_params.insert("his_doc_id".into(), doc.his_doc_id.clone());
                submit_params.insert("his_dep_id".into(), doc.his_dep_id.clone());
                submit_params.insert("detlid".into(), selected.value.clone());
                submit_params.insert("member_id".into(), config.member_id.clone());
                submit_params.insert("addressId".into(), address_id.clone());
                submit_params.insert("address".into(), address_text.clone());
                submit_params.insert("sch_data".into(), detail.sch_data.clone());
                submit_params.insert("level_code".into(), detail.level_code.clone());
                submit_params.insert("detlid_realtime".into(), detail.detlid_realtime.clone());
                submit_params.insert("sch_date".into(), detail.sch_date.clone());
                submit_params.insert("hisMemId".into(), detail.his_mem_id.clone());
                submit_params.insert("order_no".into(), detail.order_no.clone());
                submit_params.insert("disease_input".into(), detail.disease_input.clone());
                submit_params.insert("disease_content".into(), detail.disease_content.clone());
                submit_params.insert("is_hot".into(), detail.is_hot.clone());

                // Apply throttle
                self.apply_submit_throttle(on_log).await;

                // Submit
                match self.client.submit_order(&submit_params).await {
                    Ok(result) if result.success || result.status => {
                        let unit_name = if config.unit_name.is_empty() { &config.unit_id } else { &config.unit_name };
                        let dep_name = if config.dep_name.is_empty() { &config.dep_id } else { &config.dep_name };
                        let member_name = if config.member_name.is_empty() { &config.member_id } else { &config.member_name };

                        let success = GrabSuccess {
                            unit_name: unit_name.clone(),
                            dep_name: dep_name.clone(),
                            doctor_name: doc.doctor_name.clone(),
                            date: date.to_string(),
                            time_slot: selected.name.clone(),
                            member_name: member_name.clone(),
                            url: result.url,
                        };

                        emit_log(on_log, "success", &format!("success: {} / {} / {}", unit_name, dep_name, doc.doctor_name));
                        return Ok(Some(success));
                    }
                    Ok(result) => {
                        let msg = if result.message.is_empty() { "submit failed".to_string() } else { result.message };
                        
                        if is_too_fast_message(&msg) {
                            emit_log(on_log, "warn", &format!("submit throttled, backoff"));
                            let backoff = Duration::from_millis(random_backoff_ms(SUBMIT_BACKOFF_MIN_MS, SUBMIT_BACKOFF_MAX_MS));
                            tokio::time::sleep(backoff).await;
                        } else {
                            emit_log(on_log, "error", &msg);
                        }
                    }
                    Err(e) => {
                        emit_log(on_log, "error", &format!("submit error: {}", e));
                    }
                }
            }
        }

        Ok(None)
    }

    /// Wait until specified time
    async fn wait_until<F>(
        &self,
        target_time: &str,
        use_server_time: bool,
        cancel_token: CancellationToken,
        on_log: &mut F,
    ) where
        F: FnMut(&str, &str) + Send,
    {
        let parts: Vec<&str> = target_time.split(':').collect();
        if parts.len() < 3 {
            emit_log(on_log, "error", &format!("invalid time format: {}", target_time));
            return;
        }

        let hour: u32 = parts[0].parse().unwrap_or(0);
        let min: u32 = parts[1].parse().unwrap_or(0);
        let sec: u32 = parts[2].parse().unwrap_or(0);

        let now = Local::now();
        let target = now.date_naive().and_hms_opt(hour, min, sec)
            .map(|t| t.and_local_timezone(Local).unwrap())
            .unwrap_or(now);

        let mut offset = chrono::Duration::zero();
        if use_server_time {
            if let Ok(server_time) = self.client.get_server_datetime().await {
                offset = server_time - Local::now();
                emit_log(on_log, "info", &format!("time offset {:.3}s", offset.num_milliseconds() as f64 / 1000.0));
            }
        }

        let adjusted = target - offset;
        let now = Local::now();

        if adjusted <= now {
            emit_log(on_log, "warn", &format!("target time already passed: {}", target_time));
            return;
        }

        let wait = adjusted - now;
        emit_log(on_log, "info", &format!("waiting {:.1}s to start", wait.num_seconds() as f64));

        // Wait with periodic checks
        while Local::now() < adjusted {
            if cancel_token.is_cancelled() {
                return;
            }
            let remaining = adjusted - Local::now();
            if remaining.num_seconds() <= 2 {
                break;
            }
            let sleep = std::cmp::min(remaining.num_milliseconds() as u64, 1000);
            tokio::time::sleep(Duration::from_millis(sleep)).await;
        }

        // Spin wait for precision
        while Local::now() < adjusted {
            if cancel_token.is_cancelled() {
                return;
            }
            tokio::task::yield_now().await;
        }

        emit_log(on_log, "info", "start trigger");
    }

    /// Apply submit throttle
    async fn apply_submit_throttle<F>(&self, on_log: &mut F)
    where
        F: FnMut(&str, &str) + Send,
    {
        let last = *self.last_submit_at.read().await;
        if let Some(last_time) = last {
            let elapsed = last_time.elapsed();
            let min_interval = Duration::from_millis(SUBMIT_MIN_INTERVAL_MS);
            if elapsed < min_interval {
                let wait = min_interval - elapsed;
                emit_log(on_log, "info", &format!("submit throttle: wait {}ms", wait.as_millis()));
                tokio::time::sleep(wait).await;
            }
        }
        let mut last_lock = self.last_submit_at.write().await;
        *last_lock = Some(std::time::Instant::now());
    }
}

/// Pick time slot based on preference
fn pick_time_slot(slots: &[TimeSlot], preferred: &[String]) -> TimeSlot {
    if slots.is_empty() {
        return TimeSlot { name: String::new(), value: String::new() };
    }

    if !preferred.is_empty() {
        for p in preferred {
            for slot in slots {
                if &slot.name == p {
                    return slot.clone();
                }
            }
        }
    }

    slots[0].clone()
}

/// Resolve address from config or detail
fn resolve_address<F>(config: &GrabConfig, detail: &TicketDetail, on_log: &mut F) -> (String, String)
where
    F: FnMut(&str, &str) + Send,
{
    let mut address_id = normalize_address_id(&config.address_id);
    let mut address_text = normalize_address_text(&config.address);

    if address_id.is_empty() || address_text.is_empty() {
        address_id = normalize_address_id(&detail.address_id);
        address_text = normalize_address_text(&detail.address);
    }

    if (address_id.is_empty() || address_text.is_empty()) && !detail.addresses.is_empty() {
        for item in &detail.addresses {
            let cand_id = normalize_address_id(&item.id);
            let cand_text = normalize_address_text(&item.text);
            if !cand_id.is_empty() && !cand_text.is_empty() {
                address_id = cand_id;
                address_text = cand_text.clone();
                emit_log(on_log, "warn", &format!("fallback address: {}", cand_text));
                break;
            }
        }
    }

    (address_id, address_text)
}

/// Normalize address ID
fn normalize_address_id(value: &str) -> String {
    let value = value.trim();
    if value.is_empty() || value == "0" || value == "-1" {
        String::new()
    } else {
        value.to_string()
    }
}

/// Normalize address text
fn normalize_address_text(value: &str) -> String {
    let value = value.trim();
    if value.is_empty() {
        return String::new();
    }
    let placeholders = ["请选择", "请填写", "请输入", "城市地址"];
    for p in placeholders {
        if value.contains(p) {
            return String::new();
        }
    }
    value.to_string()
}

/// Check if message indicates rate limiting
fn is_too_fast_message(message: &str) -> bool {
    let message = message.trim();
    if message.is_empty() {
        return false;
    }
    message.contains("太快") || message.contains("频繁") || message.contains("刷新")
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

/// Sleep with cancellation support
async fn sleep_with_cancel(duration: Duration, cancel_token: CancellationToken) -> bool {
    tokio::select! {
        _ = tokio::time::sleep(duration) => true,
        _ = cancel_token.cancelled() => false,
    }
}

/// Emit log message
fn emit_log<F>(on_log: &mut F, level: &str, message: &str)
where
    F: FnMut(&str, &str),
{
    on_log(level, message);
}
