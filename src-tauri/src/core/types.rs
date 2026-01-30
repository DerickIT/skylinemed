//! Type definitions for SkylineMed
//! Corresponds to core/types.go

use serde::{Deserialize, Serialize};

/// Address option for patient location
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AddressOption {
    pub id: String,
    pub text: String,
}

/// Time slot for appointment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeSlot {
    pub name: String,
    pub value: String,
}

/// Ticket detail from appointment page
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TicketDetail {
    pub times: Vec<TimeSlot>,
    pub time_slots: Vec<TimeSlot>,
    pub sch_data: String,
    pub detlid_realtime: String,
    pub level_code: String,
    pub sch_date: String,
    pub order_no: String,
    pub disease_content: String,
    pub disease_input: String,
    pub is_hot: String,
    #[serde(rename = "hisMemId")]
    pub his_mem_id: String,
    #[serde(rename = "addressId")]
    pub address_id: String,
    pub address: String,
    pub addresses: Vec<AddressOption>,
}

impl Default for TicketDetail {
    fn default() -> Self {
        Self {
            times: Vec::new(),
            time_slots: Vec::new(),
            sch_data: String::new(),
            detlid_realtime: String::new(),
            level_code: String::new(),
            sch_date: String::new(),
            order_no: String::new(),
            disease_content: String::new(),
            disease_input: String::new(),
            is_hot: String::new(),
            his_mem_id: String::new(),
            address_id: String::new(),
            address: String::new(),
            addresses: Vec::new(),
        }
    }
}

/// Member (patient) information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Member {
    pub id: String,
    pub name: String,
    pub certified: bool,
}

/// Order submission result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubmitOrderResult {
    pub success: bool,
    pub status: bool,
    #[serde(rename = "msg")]
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
}

/// QR login result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QRLoginResult {
    pub success: bool,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cookie_path: Option<String>,
}

/// Grab configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GrabConfig {
    pub unit_id: String,
    #[serde(default)]
    pub unit_name: String,
    pub dep_id: String,
    #[serde(default)]
    pub dep_name: String,
    #[serde(default)]
    pub doctor_ids: Vec<String>,
    pub member_id: String,
    #[serde(default)]
    pub member_name: String,
    pub target_dates: Vec<String>,
    #[serde(default)]
    pub time_types: Vec<String>,
    #[serde(default)]
    pub preferred_hours: Vec<String>,
    #[serde(rename = "addressId", default)]
    pub address_id: String,
    #[serde(default)]
    pub address: String,
    #[serde(default)]
    pub start_time: String,
    #[serde(default)]
    pub use_server_time: bool,
    #[serde(default)]
    pub retry_interval: f64,
    #[serde(default)]
    pub max_retries: i32,
    #[serde(default = "default_true")]
    pub use_proxy_submit: bool,
}

fn default_true() -> bool {
    true
}

impl GrabConfig {
    /// Validate the configuration
    pub fn validate(&self) -> Result<(), String> {
        if self.unit_id.is_empty() {
            return Err("unit_id is required".into());
        }
        if self.dep_id.is_empty() {
            return Err("dep_id is required".into());
        }
        if self.member_id.is_empty() {
            return Err("member_id is required".into());
        }
        if self.target_dates.is_empty() {
            return Err("target_dates is required".into());
        }
        Ok(())
    }
}

/// Grab success result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GrabSuccess {
    pub unit_name: String,
    pub dep_name: String,
    pub doctor_name: String,
    pub date: String,
    pub time_slot: String,
    pub member_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
}

/// Grab result (success or failure)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GrabResult {
    pub success: bool,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<GrabSuccess>,
}

/// Cookie record for persistence
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CookieRecord {
    pub name: String,
    pub value: String,
    #[serde(default = "default_domain")]
    pub domain: String,
    #[serde(default = "default_path")]
    pub path: String,
}

fn default_domain() -> String {
    ".91160.com".into()
}

fn default_path() -> String {
    "/".into()
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct City {
    #[serde(rename = "cityId", deserialize_with = "deserialize_flexible_string")]
    pub city_id: String,
    pub name: String,
}

/// Custom deserializer for fields that can be number or string
fn deserialize_flexible_string<'de, D>(deserializer: D) -> Result<String, D::Error>
where
    D: serde::Deserializer<'de>,
{
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum StringOrInt {
        String(String),
        Int(i64),
        Float(f64),
    }

    match StringOrInt::deserialize(deserializer)? {
        StringOrInt::String(s) => Ok(s),
        StringOrInt::Int(i) => Ok(i.to_string()),
        StringOrInt::Float(f) => Ok(f.to_string()),
    }
}

/// Hospital information
#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Hospital {
    #[serde(deserialize_with = "deserialize_flexible_string")]
    pub unit_id: String,
    pub unit_name: String,
}

/// Department information
#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Department {
    #[serde(deserialize_with = "deserialize_flexible_string")]
    pub dep_id: String,
    pub dep_name: String,
    #[serde(default)]
    pub childs: Vec<Department>,
}

/// Log entry for export
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub time: String,
    pub level: String,
    pub message: String,
}

/// Schedule slot information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduleSlot {
    #[serde(deserialize_with = "deserialize_flexible_string")]
    pub schedule_id: String,
    pub time_type: String,
    pub time_type_desc: String,
    pub left_num: i32,
    pub sch_date: String,
}

/// Doctor with schedule information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DoctorSchedule {
    #[serde(deserialize_with = "deserialize_flexible_string")]
    pub doctor_id: String,
    pub doctor_name: String,
    #[serde(default)]
    pub reg_fee: String,
    #[serde(default)]
    pub total_left_num: i32,
    #[serde(default, deserialize_with = "deserialize_flexible_string")]
    pub his_doc_id: String,
    #[serde(default, deserialize_with = "deserialize_flexible_string")]
    pub his_dep_id: String,
    #[serde(default)]
    pub schedules: Vec<ScheduleSlot>,
    #[serde(default)]
    pub schedule_id: String,
    #[serde(default)]
    pub time_type_desc: String,
}

/// User state for UI persistence
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct UserState {
    #[serde(default = "default_city_id")]
    pub city_id: String,
    pub unit_id: Option<String>,
    pub dep_id: Option<String>,
    pub doctor_id: Option<String>,
    pub member_id: Option<String>,
    #[serde(default)]
    pub target_date: String,
    #[serde(default)]
    pub target_dates: Vec<String>,
    #[serde(default = "default_time_slots")]
    pub time_slots: Vec<String>,
    #[serde(default = "default_true")]
    pub proxy_submit_enabled: bool,
}

fn default_city_id() -> String {
    "5".into()
}

fn default_time_slots() -> Vec<String> {
    vec!["am".into(), "pm".into()]
}
