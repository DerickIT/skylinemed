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

export const GetHospitalsByCity = (cityId) => invoke('get_hospitals_by_city', { cityId: cityId });

export const GetDepsByUnit = (unitId, cityPinyin) => invoke('get_deps_by_unit', { unitId: unitId, cityPinyin: cityPinyin || '' });

export const GetSchedule = (unitId, depId, date) => invoke('get_schedule', {
    unitId: unitId,
    depId: depId,
    date: date
});

export const GetTicketDetail = (unitId, depId, scheduleId, memberId) => invoke('get_ticket_detail', {
    unitId: unitId,
    depId: depId,
    scheduleId: scheduleId,
    memberId: memberId
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
