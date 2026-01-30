import { ref, computed } from 'vue'
import {
    CheckLogin,
    StartQRLogin,
    StopQRLogin,
    GetUserState,
    SaveUserState,
    GetMembers,
    EventsOn
} from '../api/tauri'
import { useLogger } from './useLogger'

// Global Auth State
const userState = ref({})
const stateReady = ref(false)
const loggedIn = ref(false)
const members = ref([])
const loadingMembers = ref(false)

// Login Flow State
const qrStatus = ref('等待启动')
const qrImageUrl = ref('')
const loginRunning = ref(false)
const loginChecked = ref(false)
const loginFailCount = ref(0)
const loginAttemptActive = ref(false)
const loginNotice = ref('')
const loginFailLimit = 3

export function useAuth() {
    const { pushLog, stringifyError } = useLogger()

    const statusLabel = computed(() => {
        if (!loginChecked.value) return '待检查'
        return loggedIn.value ? '已登录' : '未登录'
    })

    // Start QR Code Login Flow
    const startLogin = async () => {
        loginNotice.value = ''
        loginAttemptActive.value = true
        loginRunning.value = true
        try {
            await StartQRLogin()
        } catch (err) {
            loginRunning.value = false
            pushLog('error', `启动扫码失败: ${stringifyError(err)}`)
        }
    }

    const stopLogin = async () => {
        try {
            await StopQRLogin()
        } finally {
            loginRunning.value = false
            loginAttemptActive.value = false
        }
    }

    const toggleLogin = async () => {
        if (loginRunning.value) {
            await stopLogin()
        } else {
            await startLogin()
        }
    }

    // Load User Configuration (persisted preferences)
    const loadUserState = async () => {
        try {
            userState.value = await GetUserState() || {}
            stateReady.value = true
        } catch (err) {
            pushLog('error', `读取状态失败: ${stringifyError(err)}`)
            userState.value = {}
        }
    }

    const saveUserState = async () => {
        if (!userState.value || !stateReady.value) return
        try {
            await SaveUserState(userState.value)
        } catch (err) {
            pushLog('error', `保存状态失败: ${stringifyError(err)}`)
        }
    }

    // Fetch family members associated with the account
    const loadMembers = async () => {
        if (!loggedIn.value) {
            members.value = []
            return
        }
        loadingMembers.value = true
        try {
            const data = await GetMembers()
            members.value = Array.isArray(data)
                ? data.map(item => ({
                    id: String(item.id || ''),
                    name: String(item.name || ''),
                    certified: Boolean(item.certified),
                })).filter(item => item.id && item.name)
                : []
        } catch (err) {
            pushLog('error', `就诊人加载失败: ${stringifyError(err)}`)
        } finally {
            loadingMembers.value = false
        }
    }

    // Initialize Listeners
    const initAuthListeners = () => {
        // Check initial login status
        CheckLogin().then(ok => {
            loggedIn.value = Boolean(ok)
            loginChecked.value = true
            if (loggedIn.value) {
                loadMembers()
            }
        }).catch(err => {
            pushLog('error', `登录检查失败: ${stringifyError(err)}`)
            loginChecked.value = true
        })

        // QR Image Update
        EventsOn('qr-image', (payload) => {
            const base64 = payload?.base64 || ''
            const mime = base64.startsWith('/9j/') ? 'image/jpeg' : 'image/png'
            qrImageUrl.value = base64 ? `data:${mime};base64,${base64}` : ''
            if (payload?.uuid) {
                pushLog('info', `二维码已刷新`)
            }
        })

        // QR Status Update
        EventsOn('qr-status', (payload) => {
            if (payload?.message) {
                qrStatus.value = payload.message
            }
        })

        // Login Status Update
        EventsOn('login-status', (payload) => {
            const isLoggedIn = Boolean(payload?.loggedIn)
            loggedIn.value = isLoggedIn
            loginChecked.value = true
            loginRunning.value = false

            if (isLoggedIn) {
                loginFailCount.value = 0
                loginNotice.value = ''
                loginAttemptActive.value = false
                pushLog('success', '登录成功')
                loadMembers()
            } else {
                members.value = []
                if (loginAttemptActive.value) {
                    loginFailCount.value += 1
                    loginAttemptActive.value = false

                    if (loginFailCount.value >= loginFailLimit) {
                        loginNotice.value = `登录连续失败（${loginFailCount.value}次）`
                        pushLog('warn', loginNotice.value)
                        StopQRLogin()
                    } else {
                        loginNotice.value = '登录失败，请重试'
                    }
                } else {
                    loginNotice.value = '登录已失效'
                }
            }
        })
    }

    return {
        userState,
        stateReady,
        loggedIn,
        loginChecked,
        members,
        loadingMembers,
        qrStatus,
        qrImageUrl,
        loginRunning,
        loginNotice,
        statusLabel,

        startLogin,
        stopLogin,
        toggleLogin,
        loadUserState,
        saveUserState,
        loadMembers,
        initAuthListeners
    }
}
