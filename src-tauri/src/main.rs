//! QuickDoctor - Hospital Appointment Assistant
//! Main entry point for Tauri application

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod core;

use commands::AppState;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            commands::get_cities,
            commands::get_user_state,
            commands::save_user_state_cmd,
            commands::export_logs,
            commands::get_hospitals_by_city,
            commands::get_deps_by_unit,
            commands::get_members,
            commands::check_login,
            commands::get_schedule,
            commands::get_ticket_detail,
            commands::submit_order,
            commands::start_qr_login,
            commands::stop_qr_login,
            commands::start_grab,
            commands::stop_grab,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
