import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

// --- Auth & State ---

export const CheckLogin = () => invoke('check_login');
export const StartQRLogin = () => invoke('start_qr_login');
export const StopQRLogin = () => invoke('stop_qr_login');
export const GetUserState = () => invoke('get_user_state');
export const SaveUserState = (state) => invoke('save_user_state_cmd', { state });
export const GetMembers = () => invoke('get_members');

// --- Data Fetching ---

export const GetCities = () => invoke('get_cities');

export const GetHospitalsByCity = (cityId) => invoke('get_hospitals_by_city', { city_id: cityId });

export const GetDepsByUnit = (unitId) => invoke('get_deps_by_unit', { unit_id: unitId });

export const GetSchedule = (unitId, depId, date) => invoke('get_schedule', {
    unit_id: unitId,
    dep_id: depId,
    date: date
});

// --- Grab Task ---

export const StartGrab = (config) => invoke('start_grab', { config });
export const StopGrab = () => invoke('stop_grab');

// --- Logs ---

export const ExportLogs = (logs) => invoke('export_logs', { logs });

// --- Events ---

/**
 * Mimics Wails EventsOn behavior
 * @param {string} eventName 
 * @param {function} callback 
 */
export const EventsOn = async (eventName, callback) => {
    try {
        console.log(`[Tauri] Attempting to listen to ${eventName}...`);
        const unlisten = await listen(eventName, (event) => {
            console.log(`[Tauri Event] ${eventName} received! Payload:`, event.payload);
            callback(event.payload);
        });
        console.log(`[Tauri] Registered listener for ${eventName}`);
        return unlisten;
    } catch (err) {
        console.error(`[Tauri] Failed to listen to ${eventName}:`, err);
    }
};
