import { ref, reactive, computed } from 'vue'
import { ExportLogs, EventsOn } from '../api/tauri'

// Global state to share logs across components
const logs = ref([])
const logFilters = reactive({
    info: true,
    warn: true,
    error: true,
    success: true,
})

export function useLogger() {
    const normalizeLevel = (level) => {
        const normalized = String(level || 'info').toLowerCase()
        if (['warn', 'error', 'success', 'info'].includes(normalized)) {
            return normalized
        }
        return 'info'
    }

    const pushLog = (level, message) => {
        const timestamp = new Date().toLocaleTimeString()
        const normalizedLevel = normalizeLevel(level)
        logs.value.push({ level: normalizedLevel, message, time: timestamp })

        // Keep last 200 logs
        if (logs.value.length > 200) {
            logs.value.splice(0, logs.value.length - 200)
        }
    }

    const filteredLogs = computed(() => {
        return logs.value.filter((item) => {
            const level = normalizeLevel(item?.level)
            return logFilters[level] !== false
        })
    })

    const logStats = computed(() => {
        const stats = { info: 0, warn: 0, error: 0, success: 0 }
        logs.value.forEach((item) => {
            const level = normalizeLevel(item?.level)
            if (stats[level] !== undefined) {
                stats[level] += 1
            }
        })
        return stats
    })

    const failureSummary = computed(() => {
        const counts = new Map()
        let total = 0
        logs.value.forEach((item) => {
            const level = normalizeLevel(item?.level)
            if (level !== 'error' && level !== 'warn') return

            const message = String(item?.message || '').trim()
            if (!message) return

            total += 1
            counts.set(message, (counts.get(message) || 0) + 1)
        })

        const items = Array.from(counts.entries())
            .map(([message, count]) => ({ message, count }))
            .sort((a, b) => b.count - a.count)
            .slice(0, 4)
        return { total, items }
    })

    const toggleLogFilter = (level) => {
        if (logFilters[level] !== undefined) {
            logFilters[level] = !logFilters[level]
        }
    }

    const resetLogFilters = () => {
        Object.keys(logFilters).forEach((key) => {
            logFilters[key] = true
        })
    }

    const showOnlyLogLevel = (level) => {
        Object.keys(logFilters).forEach((key) => {
            logFilters[key] = key === level
        })
    }

    const stringifyError = (err) => {
        if (!err) return '未知错误'
        if (typeof err === 'string') return err
        if (err.message) return err.message
        return JSON.stringify(err)
    }

    const exportLogs = async () => {
        const payload = logs.value.map((item) => ({
            time: String(item?.time || ''),
            level: normalizeLevel(item?.level),
            message: String(item?.message || ''),
        }))

        if (payload.length === 0) {
            pushLog('warn', '暂无可导出的日志')
            return
        }

        try {
            const path = await ExportLogs(payload)
            if (path) {
                pushLog('success', `日志已导出: ${path}`)
            } else {
                pushLog('warn', '已取消导出')
            }
        } catch (err) {
            pushLog('error', `导出失败: ${stringifyError(err)}`)
        }
    }

    const clearLogs = () => {
        logs.value = []
    }

    // Init listeners
    const initLogListeners = () => {
        EventsOn('log-message', (payload) => {
            const level = payload?.level || 'info'
            const message = payload?.message || String(payload || '')
            pushLog(level, message)
        })
    }

    return {
        logs,
        logFilters,
        filteredLogs,
        logStats,
        failureSummary,
        pushLog,
        toggleLogFilter,
        resetLogFilters,
        showOnlyLogLevel,
        exportLogs,
        clearLogs,
        initLogListeners,
        normalizeLevel,
        stringifyError
    }
}
