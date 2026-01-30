//! HTTP Client for QuickDoctor
//! Corresponds to core/client.go - HTTP client with cookie management and API methods

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use reqwest::cookie::Jar;
use reqwest::header::{HeaderMap, HeaderValue, ACCEPT, CONTENT_TYPE, ORIGIN, REFERER, USER_AGENT};
use reqwest::Client;
use scraper::{Html, Selector};
use tokio::sync::RwLock;
use url::Url;

use super::cookies::{has_access_hash, load_cookie_file, save_cookie_file, unique_strings};
use super::errors::{AppError, AppResult};
use super::types::{CookieRecord, DepartmentCategory, DoctorSchedule, Member, ScheduleSlot, SubmitOrderResult, TicketDetail, TimeSlot, AddressOption, Hospital};

const DEFAULT_USER_AGENT: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

/// Health client for 91160 API
pub struct HealthClient {
    client: Client,
    cookie_jar: Arc<Jar>,
    cookies: RwLock<Vec<CookieRecord>>,
    last_error: RwLock<String>,
    last_status_code: RwLock<i32>,
}

impl HealthClient {
    /// Create a new health client
    pub fn new() -> AppResult<Self> {
        let cookie_jar = Arc::new(Jar::default());

        let client = Client::builder()
            .user_agent(DEFAULT_USER_AGENT)
            .cookie_provider(cookie_jar.clone())
            .timeout(Duration::from_secs(30))
            .connect_timeout(Duration::from_secs(10))
            .gzip(true)
            .brotli(true)
            .build()
            .map_err(|e| AppError::HttpError(e))?;

        Ok(Self {
            client,
            cookie_jar,
            cookies: RwLock::new(Vec::new()),
            last_error: RwLock::new(String::new()),
            last_status_code: RwLock::new(0),
        })
    }

    /// Load cookies from file and apply to client
    pub async fn load_cookies(&self) -> bool {
        match load_cookie_file() {
            Ok(records) if !records.is_empty() => {
                self.apply_cookies(&records).await;
                let mut cookies = self.cookies.write().await;
                *cookies = records;
                true
            }
            _ => false,
        }
    }

    /// Ensure cookies are loaded
    pub async fn ensure_cookies_loaded(&self) -> bool {
        if self.has_access_hash().await {
            return true;
        }
        self.load_cookies().await
    }

    /// Check if access_hash cookie exists
    pub async fn has_access_hash(&self) -> bool {
        let cookies = self.cookies.read().await;
        has_access_hash(&cookies)
    }

    /// Get access_hash values
    pub async fn get_access_hash_values(&self) -> Vec<String> {
        let cookies = self.cookies.read().await;
        unique_strings(
            cookies
                .iter()
                .filter(|c| c.name == "access_hash" && !c.value.is_empty())
                .map(|c| c.value.clone())
                .collect(),
        )
    }

    /// Apply cookies to the client jar
    async fn apply_cookies(&self, records: &[CookieRecord]) {
        for record in records {
            let domain = record.domain.trim_start_matches('.');
            if domain.is_empty() {
                continue;
            }
            if let Ok(url) = Url::parse(&format!("https://{}", domain)) {
                let cookie_str = format!(
                    "{}={}; Domain={}; Path={}",
                    record.name, record.value, record.domain, record.path
                );
                self.cookie_jar.add_cookie_str(&cookie_str, &url);
            }
        }
    }

    /// Save cookies from current jar to file
    #[allow(dead_code)]
    pub async fn save_cookies_from_records(&self, records: Vec<CookieRecord>) -> AppResult<()> {
        if records.is_empty() {
            return Err(AppError::ConfigError("No cookies to save".into()));
        }
        save_cookie_file(&records)?;
        self.apply_cookies(&records).await;
        let mut cookies = self.cookies.write().await;
        *cookies = records;
        Ok(())
    }

    /// Set last error
    async fn set_last_error(&self, message: &str) {
        let mut error = self.last_error.write().await;
        *error = message.to_string();
    }

    /// Set last status code
    async fn set_last_status_code(&self, code: i32) {
        let mut status = self.last_status_code.write().await;
        *status = code;
    }

    /// Get last error
    pub async fn last_error(&self) -> String {
        self.last_error.read().await.clone()
    }

    /// Get last status code
    #[allow(dead_code)]
    pub async fn last_status_code(&self) -> i32 {
        *self.last_status_code.read().await
    }

    /// Build default headers
    fn default_headers() -> HeaderMap {
        let mut headers = HeaderMap::new();
        headers.insert(USER_AGENT, HeaderValue::from_static("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"));
        headers.insert(ACCEPT, HeaderValue::from_static("application/json, text/javascript, */*; q=0.01"));
        headers.insert("Accept-Language", HeaderValue::from_static("zh-CN,zh;q=0.9,en;q=0.8"));
        headers.insert("Sec-Fetch-Dest", HeaderValue::from_static("empty"));
        headers.insert("Sec-Fetch-Mode", HeaderValue::from_static("cors"));
        headers.insert("Sec-Fetch-Site", HeaderValue::from_static("same-origin"));
        headers.insert("sec-ch-ua", HeaderValue::from_static("\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\", \"Google Chrome\";v=\"120\""));
        headers.insert("sec-ch-ua-mobile", HeaderValue::from_static("?0"));
        headers.insert("sec-ch-ua-platform", HeaderValue::from_static("\"Windows\""));
        headers
    }

    /// Check login status
    pub async fn check_login(&self) -> bool {
        if !self.has_access_hash().await {
            return false;
        }

        // Try to access user page
        let mut headers = Self::default_headers();
        headers.insert("X-Requested-With", HeaderValue::from_static("XMLHttpRequest"));
        // For page requests, Accept should include html
        headers.insert(ACCEPT, HeaderValue::from_static("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"));
        headers.insert("Sec-Fetch-Dest", HeaderValue::from_static("document"));
        headers.insert("Sec-Fetch-Mode", HeaderValue::from_static("navigate"));
        headers.insert("Sec-Fetch-Site", HeaderValue::from_static("none")); // Initial navigation
        headers.insert("Sec-Fetch-User", HeaderValue::from_static("?1"));
        headers.insert("Upgrade-Insecure-Requests", HeaderValue::from_static("1"));

        let result = self
            .client
            .get("https://user.91160.com/user/index.html")
            .headers(headers)
            .send()
            .await;

        match result {
            Ok(resp) if resp.status().is_success() => true,
            _ => {
                // Fallback: try to get members
                self.get_members().await.map(|m| !m.is_empty()).unwrap_or(false)
            }
        }
    }

    /// Get hospitals by city
    pub async fn get_hospitals_by_city(&self, city_id: &str) -> AppResult<Vec<Hospital>> {
        let city = if city_id.is_empty() { "5" } else { city_id };

        let mut headers = Self::default_headers();
        headers.insert("X-Requested-With", HeaderValue::from_static("XMLHttpRequest"));
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/x-www-form-urlencoded; charset=UTF-8"));
        headers.insert(REFERER, HeaderValue::from_static("https://www.91160.com/"));
        headers.insert(ORIGIN, HeaderValue::from_static("https://www.91160.com"));

        let resp = self
            .client
            .post("https://www.91160.com/ajax/getunitbycity.html")
            .headers(headers)
            .form(&[("c", city)])
            .send()
            .await?;

        let text = resp.text().await?;
        let data: Vec<Hospital> = serde_json::from_str(&text)?;
        Ok(data)
    }

    /// Get departments by unit
    /// city_pinyin is used to construct the correct subdomain (e.g., "sz" -> "sz.91160.com")
    pub async fn get_deps_by_unit(&self, unit_id: &str, city_pinyin: &str) -> AppResult<Vec<DepartmentCategory>> {
        // Use city pinyin as subdomain, fallback to "www" if empty
        let subdomain = if city_pinyin.is_empty() { "www" } else { city_pinyin };
        let url = format!("https://{}.91160.com/ajax/getdepbyunit.html", subdomain);
        
        println!(">>> [get_deps_by_unit] Request URL: {}", url);
        println!(">>> [get_deps_by_unit] Request body: keyValue={}", unit_id);
        
        let mut headers = Self::default_headers();
        headers.insert("X-Requested-With", HeaderValue::from_static("XMLHttpRequest"));
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/x-www-form-urlencoded; charset=UTF-8"));
        
        // Dynamic Referer and Origin based on subdomain
        let referer = format!("https://{}.91160.com/", subdomain);
        let origin = format!("https://{}.91160.com", subdomain);
        headers.insert(REFERER, HeaderValue::from_str(&referer).unwrap_or(HeaderValue::from_static("https://www.91160.com/")));
        headers.insert(ORIGIN, HeaderValue::from_str(&origin).unwrap_or(HeaderValue::from_static("https://www.91160.com")));

        let resp = self
            .client
            .post(&url)
            .headers(headers)
            .form(&[("keyValue", unit_id)])
            .send()
            .await?;

        let status = resp.status();
        println!(">>> [get_deps_by_unit] Response status: {}", status);
        
        let text = resp.text().await?;
        // Print first 500 chars of response for debugging
        let preview = if text.len() > 500 { &text[..500] } else { &text };
        println!(">>> [get_deps_by_unit] Response body (preview): {}", preview);
        
        // API returns: [{pubcat, yuyue_num, childs: [departments]}]
        // We return the raw category structure so frontend can handle hierarchy
        match serde_json::from_str::<Vec<DepartmentCategory>>(&text) {
            Ok(categories) => {
                println!(">>> [get_deps_by_unit] Parsed {} categories successfully", categories.len());
                Ok(categories)
            }
            Err(e) => {
                println!(">>> [get_deps_by_unit] JSON parse error: {}", e);
                println!(">>> [get_deps_by_unit] Full response: {}", text);
                Err(AppError::JsonError(e))
            }
        }
    }

    /// Get members (patients)
    pub async fn get_members(&self) -> AppResult<Vec<Member>> {
        let mut headers = Self::default_headers();
        // Page request - no XMLHttpRequest
        headers.insert(ACCEPT, HeaderValue::from_static("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"));
        headers.insert("Sec-Fetch-Dest", HeaderValue::from_static("document"));
        headers.insert("Sec-Fetch-Mode", HeaderValue::from_static("navigate"));
        headers.insert("Sec-Fetch-Site", HeaderValue::from_static("same-origin"));
        headers.insert("Sec-Fetch-User", HeaderValue::from_static("?1"));
        headers.insert("Upgrade-Insecure-Requests", HeaderValue::from_static("1"));
        headers.insert(REFERER, HeaderValue::from_static("https://user.91160.com/user/index.html"));

        let resp = self
            .client
            .get("https://user.91160.com/member.html")
            .headers(headers)
            .send()
            .await?;

        let url = resp.url().to_string();
        let body = resp.text().await?;

        // Check if redirected to login
        if url.to_lowercase().contains("login") || body.contains("登录") {
            return Ok(Vec::new());
        }

        // Parse HTML
        let document = Html::parse_document(&body);
        let row_selector = Selector::parse("tbody#mem_list tr").unwrap();
        let td_selector = Selector::parse("td").unwrap();

        let mut members = Vec::new();

        for row in document.select(&row_selector) {
            let id = row
                .value()
                .attr("id")
                .unwrap_or("")
                .trim_start_matches("mem")
                .to_string();

            let tds: Vec<_> = row.select(&td_selector).collect();
            if tds.is_empty() {
                continue;
            }

            let mut name = tds[0].text().collect::<String>().trim().to_string();
            name = name.replace("默认", "");

            let certified = tds.iter().any(|td| td.text().collect::<String>().contains("认证"));

            if id.is_empty() && name.is_empty() {
                continue;
            }

            members.push(Member { id, name, certified });
        }

        Ok(members)
    }

    /// Get schedule for a department on a date
    pub async fn get_schedule(
        &self,
        unit_id: &str,
        dep_id: &str,
        date: &str,
    ) -> AppResult<Vec<DoctorSchedule>> {
        self.set_last_error("").await;
        self.set_last_status_code(0).await;

        let date = if date.is_empty() {
            chrono::Local::now().format("%Y-%m-%d").to_string()
        } else {
            date.to_string()
        };

        let user_keys = self.get_access_hash_values().await;
        if user_keys.is_empty() {
            self.set_last_error("missing access_hash").await;
            return Err(AppError::LoginRequired("missing access_hash".into()));
        }

        let mut login_expired = false;

        for key in &user_keys {
            let url = format!(
                "https://gate.91160.com/guahao/v1/pc/sch/dep?unit_id={}&dep_id={}&date={}&p=0&user_key={}",
                unit_id, dep_id, date, key
            );

            let mut headers = Self::default_headers();
            headers.insert("X-Requested-With", HeaderValue::from_static("XMLHttpRequest"));
            headers.insert("Sec-Fetch-Site", HeaderValue::from_static("same-site"));
            let referer = format!("https://www.91160.com/guahao/ystep1/uid-{}/depid-{}.html", unit_id, dep_id);
            if let Ok(v) = HeaderValue::from_str(&referer) {
                headers.insert(REFERER, v);
            }

            let resp = match self.client.get(&url).headers(headers).send().await {
                Ok(r) => r,
                Err(e) => {
                    self.set_last_error(&format!("schedule request failed: {}", e)).await;
                    continue;
                }
            };

            self.set_last_status_code(resp.status().as_u16() as i32).await;

            if !resp.status().is_success() {
                self.set_last_error(&format!("schedule http {}", resp.status())).await;
                continue;
            }

            let payload: serde_json::Value = match resp.json().await {
                Ok(v) => v,
                Err(e) => {
                    self.set_last_error(&format!("schedule decode failed: {}", e)).await;
                    continue;
                }
            };

            let result_code = payload.get("result_code").and_then(|v| v.as_str()).unwrap_or("");

            if result_code == "1" {
                let data = payload.get("data");
                let doc_list = data
                    .and_then(|d| d.get("doc"))
                    .and_then(|d| d.as_array())
                    .cloned()
                    .unwrap_or_default();
                let sch_map = data
                    .and_then(|d| d.get("sch"))
                    .and_then(|s| s.as_object())
                    .cloned()
                    .unwrap_or_default();

                let mut valid_docs = Vec::new();

                for doc_value in &doc_list {
                    let doctor_id = if let Some(s) = doc_value.get("doctor_id").and_then(|v| v.as_str()) {
                        s.to_string()
                    } else if let Some(n) = doc_value.get("doctor_id").and_then(|v| v.as_i64()) {
                        n.to_string()
                    } else {
                        String::new()
                    };

                    if doctor_id.is_empty() {
                        continue;
                    }

                    let raw_schedule = sch_map.get(&doctor_id);
                    if raw_schedule.is_none() {
                        continue;
                    }

                    let mut schedules = Vec::new();

                    if let Some(sch_data) = raw_schedule.and_then(|s| s.as_object()) {
                        for time_type in ["am", "pm"] {
                            if let Some(type_data) = sch_data.get(time_type) {
                                let slots: Vec<&serde_json::Value> = if type_data.is_object() {
                                    type_data.as_object().unwrap().values().collect()
                                } else if type_data.is_array() {
                                    type_data.as_array().unwrap().iter().collect()
                                } else {
                                    continue;
                                };

                                for slot in slots {
                                    let schedule_id = if let Some(s) = slot.get("schedule_id").and_then(|v| v.as_str()) {
                                        s.to_string()
                                    } else if let Some(n) = slot.get("schedule_id").and_then(|v| v.as_i64()) {
                                        n.to_string()
                                    } else {
                                        String::new()
                                    };

                                    if !schedule_id.is_empty() {
                                        schedules.push(ScheduleSlot {
                                            schedule_id,
                                            time_type: slot.get("time_type").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                                            time_type_desc: slot.get("time_type_desc").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                                            left_num: slot.get("left_num").and_then(|v| v.as_i64()).unwrap_or(0) as i32,
                                            sch_date: slot.get("sch_date").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                                        });
                                    }
                                }
                            }
                        }
                    }

                    if schedules.is_empty() {
                        continue;
                    }

                    let total_left: i32 = schedules.iter().map(|s| s.left_num).sum();

                    valid_docs.push(DoctorSchedule {
                        doctor_id,
                        doctor_name: doc_value.get("doctor_name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        reg_fee: doc_value.get("reg_fee").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        total_left_num: total_left,
                        his_doc_id: doc_value.get("his_doc_id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        his_dep_id: doc_value.get("his_dep_id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        schedule_id: schedules.first().map(|s| s.schedule_id.clone()).unwrap_or_default(),
                        time_type_desc: schedules.first().map(|s| s.time_type_desc.clone()).unwrap_or_default(),
                        schedules,
                    });
                }

                if !valid_docs.is_empty() {
                    self.set_last_error("").await;
                    return Ok(valid_docs);
                }

                if !doc_list.is_empty() {
                    self.set_last_error("").await;
                    return Ok(Vec::new());
                }
            } else if payload.get("error_code").and_then(|v| v.as_str()) == Some("10022") {
                login_expired = true;
                continue;
            } else {
                let error_msg = payload
                    .get("error_msg")
                    .or_else(|| payload.get("error_desc"))
                    .or_else(|| payload.get("msg"))
                    .or_else(|| payload.get("message"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let error_code = payload
                    .get("error_code")
                    .or_else(|| payload.get("result_code"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                self.set_last_error(&format!("schedule api error: code={} msg={}", error_code, error_msg)).await;
            }
        }

        if login_expired {
            self.set_last_error("login expired or insufficient permissions (error_code=10022)").await;
            return Err(AppError::LoginRequired("error_code=10022".into()));
        }

        let err = self.last_error().await;
        if err.is_empty() {
            self.set_last_error("schedule query failed").await;
        }
        Err(AppError::ApiError(self.last_error().await))
    }

    /// Get ticket detail for a schedule
    pub async fn get_ticket_detail(
        &self,
        unit_id: &str,
        dep_id: &str,
        schedule_id: &str,
        _member_id: &str,
    ) -> AppResult<TicketDetail> {
        let url = format!(
            "https://www.91160.com/guahao/ystep1/uid-{}/depid-{}/schid-{}.html",
            unit_id, dep_id, schedule_id
        );

        let resp = self
            .client
            .get(&url)
            .headers(Self::default_headers())
            .send()
            .await?;

        let body = resp.text().await?;
        let document = Html::parse_document(&body);

        // Parse time slots
        let li_selector = Selector::parse("#delts li").unwrap();
        let time_slots: Vec<TimeSlot> = document
            .select(&li_selector)
            .filter_map(|el| {
                let name = el.text().collect::<String>().trim().to_string();
                let value = el.value().attr("val").unwrap_or("").to_string();
                if value.is_empty() {
                    None
                } else {
                    Some(TimeSlot { name, value })
                }
            })
            .collect();

        // Helper to get input value
        let get_input_value = |selectors: &[&str]| -> String {
            for selector in selectors {
                if let Ok(sel) = Selector::parse(selector) {
                    if let Some(el) = document.select(&sel).next() {
                        if let Some(val) = el.value().attr("value") {
                            return val.trim().to_string();
                        }
                    }
                }
            }
            String::new()
        };

        // Parse addresses from select
        let mut addresses = Vec::new();
        let address_selectors = ["select[name='addressId']", "#addressId", "#useraddress_area"];
        for selector in address_selectors {
            if let Ok(sel) = Selector::parse(selector) {
                if let Some(select_el) = document.select(&sel).next() {
                    if let Ok(option_sel) = Selector::parse("option") {
                        for option in select_el.select(&option_sel) {
                            let id = option.value().attr("value").unwrap_or("").trim().to_string();
                            let text = option.text().collect::<String>().trim().to_string();
                            if !id.is_empty() && id != "0" && id != "-1" && !text.is_empty() {
                                addresses.push(AddressOption { id, text });
                            }
                        }
                    }
                    break;
                }
            }
        }

        let mut address_id = get_input_value(&["input[name='addressId']", "#addressId"]);
        let mut address = get_input_value(&["input[name='address']", "#address"]);

        // Fallback to first address
        if (address_id.is_empty() || address.is_empty()) && !addresses.is_empty() {
            if address_id.is_empty() {
                address_id = addresses[0].id.clone();
            }
            if address.is_empty() {
                address = addresses[0].text.clone();
            }
        }

        Ok(TicketDetail {
            times: time_slots.clone(),
            time_slots,
            sch_data: get_input_value(&["input[name='sch_data']"]),
            detlid_realtime: get_input_value(&["#detlid_realtime"]),
            level_code: get_input_value(&["#level_code"]),
            sch_date: get_input_value(&["input[name='sch_date']", "#sch_date"]),
            order_no: get_input_value(&["input[name='order_no']", "#order_no"]),
            disease_content: get_input_value(&["input[name='disease_content']", "#disease_content"]),
            disease_input: get_input_value(&["textarea[name='disease_input']", "#disease_input"]),
            is_hot: get_input_value(&["input[name='is_hot']", "#is_hot"]),
            his_mem_id: get_input_value(&["input[name='hisMemId']", "#hismemid"]),
            address_id,
            address,
            addresses,
        })
    }

    /// Submit an order with optional proxy
    pub async fn submit_order(&self, params: &HashMap<String, String>, proxy_url: Option<String>) -> AppResult<SubmitOrderResult> {
        let mut data: HashMap<String, String> = HashMap::new();
        
        // Map parameters
        data.insert("sch_data".into(), params.get("sch_data").cloned().unwrap_or_default());
        data.insert("mid".into(), params.get("member_id").cloned().unwrap_or_default());
        data.insert("addressId".into(), params.get("addressId").cloned().unwrap_or_default());
        data.insert("address".into(), params.get("address").cloned().unwrap_or_default());
        data.insert("hisMemId".into(), params.get("hisMemId").or(params.get("his_mem_id")).cloned().unwrap_or_default());
        data.insert("disease_input".into(), params.get("disease_input").cloned().unwrap_or_default());
        data.insert("order_no".into(), params.get("order_no").cloned().unwrap_or_default());
        data.insert("disease_content".into(), params.get("disease_content").cloned().unwrap_or_default());
        data.insert("accept".into(), "1".into());
        data.insert("unit_id".into(), params.get("unit_id").cloned().unwrap_or_default());
        data.insert("schedule_id".into(), params.get("schedule_id").cloned().unwrap_or_default());
        data.insert("dep_id".into(), params.get("dep_id").cloned().unwrap_or_default());
        data.insert("his_dep_id".into(), params.get("his_dep_id").cloned().unwrap_or_default());
        data.insert("sch_date".into(), params.get("sch_date").cloned().unwrap_or_default());
        data.insert("time_type".into(), params.get("time_type").cloned().unwrap_or_default());
        data.insert("doctor_id".into(), params.get("doctor_id").cloned().unwrap_or_default());
        data.insert("his_doc_id".into(), params.get("his_doc_id").cloned().unwrap_or_default());
        data.insert("detlid".into(), params.get("detlid").cloned().unwrap_or_default());
        data.insert("detlid_realtime".into(), params.get("detlid_realtime").cloned().unwrap_or_default());
        data.insert("level_code".into(), params.get("level_code").cloned().unwrap_or_default());
        data.insert("is_hot".into(), params.get("is_hot").cloned().unwrap_or_default());

        let unit_id = data.get("unit_id").cloned().unwrap_or_default();
        let dep_id = data.get("dep_id").cloned().unwrap_or_default();
        let schedule_id = data.get("schedule_id").cloned().unwrap_or_default();

        let mut headers = Self::default_headers();
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/x-www-form-urlencoded"));
        headers.insert(ORIGIN, HeaderValue::from_static("https://www.91160.com"));
        headers.insert("Sec-Fetch-Dest", HeaderValue::from_static("document"));
        headers.insert("Sec-Fetch-Mode", HeaderValue::from_static("navigate"));
        headers.insert("Sec-Fetch-Site", HeaderValue::from_static("same-origin"));
        headers.insert("Sec-Fetch-User", HeaderValue::from_static("?1"));
        headers.insert("Upgrade-Insecure-Requests", HeaderValue::from_static("1"));
        
        let referer = format!(
            "https://www.91160.com/guahao/ystep1/uid-{}/depid-{}/schid-{}.html",
            unit_id, dep_id, schedule_id
        );
        if let Ok(v) = HeaderValue::from_str(&referer) {
            headers.insert(REFERER, v);
        }

        let client = if let Some(url) = proxy_url {
            let proxy = reqwest::Proxy::all(&url).map_err(|e| AppError::ProxyError(e.to_string()))?;
            reqwest::Client::builder()
                .user_agent(DEFAULT_USER_AGENT)
                .cookie_provider(self.cookie_jar.clone())
                .proxy(proxy)
                .timeout(Duration::from_secs(30))
                .build()?
        } else {
            self.client.clone()
        };

        let resp = client
            .post("https://www.91160.com/guahao/ysubmit.html")
            .headers(headers)
            .form(&data)
            .send()
            .await?;

        let status = resp.status();
        let url = resp.url().to_string();

        // Check for redirect to success
        if url.to_lowercase().contains("success") {
            return Ok(SubmitOrderResult {
                success: true,
                status: true,
                message: "OK".into(),
                url: Some(url),
            });
        }

        let body = resp.text().await?;

        // Extract error message from response
        let msg = self.extract_submit_message(&body);
        if !msg.is_empty() {
            self.set_last_error(&msg).await;
            return Ok(SubmitOrderResult {
                success: false,
                status: false,
                message: format!("submit failed: {}", msg),
                url: None,
            });
        }

        let snippet = if body.len() > 200 { &body[..200] } else { &body };
        let msg = format!("submit failed code={}, resp={}", status, snippet);
        self.set_last_error(&msg).await;

        Ok(SubmitOrderResult {
            success: false,
            status: false,
            message: msg,
            url: None,
        })
    }

    /// Extract error message from submit response
    fn extract_submit_message(&self, body: &str) -> String {
        // Try to find common error patterns
        let patterns = [
            r#"<div class="error"[^>]*>([^<]+)</div>"#,
            r#"<span class="error"[^>]*>([^<]+)</span>"#,
            r#"alert\(['"]([^'"]+)['"]\)"#,
            r#""msg"\s*:\s*"([^"]+)""#,
            r#""message"\s*:\s*"([^"]+)""#,
        ];

        for pattern in patterns {
            if let Ok(re) = regex::Regex::new(pattern) {
                if let Some(caps) = re.captures(body) {
                    if let Some(m) = caps.get(1) {
                        let msg = m.as_str().trim();
                        if !msg.is_empty() {
                            return msg.to_string();
                        }
                    }
                }
            }
        }

        String::new()
    }

    /// Get server datetime
    pub async fn get_server_datetime(&self) -> AppResult<chrono::DateTime<chrono::Local>> {
        let resp = self
            .client
            .get("https://www.91160.com/favicon.ico")
            .headers(Self::default_headers())
            .send()
            .await?;

        if let Some(date_header) = resp.headers().get("date") {
            if let Ok(date_str) = date_header.to_str() {
                if let Ok(parsed) = chrono::DateTime::parse_from_rfc2822(date_str) {
                    return Ok(parsed.with_timezone(&chrono::Local));
                }
            }
        }

        Ok(chrono::Local::now())
    }
}

impl Default for HealthClient {
    fn default() -> Self {
        Self::new().expect("Failed to create HealthClient")
    }
}
