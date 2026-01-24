import { ref } from 'vue'
import { StartGrab, StopGrab } from '../../wailsjs/go/main/App'
import { EventsOn } from '../../wailsjs/runtime'
import { useLogger } from './useLogger'

// Task Configuration State
const targetDates = ref([])
const grabRunning = ref(false)
const grabResult = ref(null)
const preferredHours = ref([])
const timeTypes = ref([])
const selectedScheduleId = ref('')

export function useGrabTask() {
    const { pushLog, stringifyError } = useLogger()

    // Date Management
    const addDateRange = (startDateStr, days) => { // 单选日期模式：仅使用起始日期
        const count = parseInt(days, 10)
        if (!count || count <= 0) return
        if (!startDateStr) {
            pushLog('warn', '请先选择日期')
            return
        }
        targetDates.value = [startDateStr]
        pushLog('warn', `当前为单选日期，已使用起始日期 ${startDateStr}`)
    }

    const addTargetDate = (dateStr) => {
        if (!dateStr) {
            pushLog('warn', '请先选择日期')
            return
        }
        targetDates.value = [dateStr]
        pushLog('success', `已设置日期 ${dateStr}`)
    }

    const removeTargetDate = (dateStr) => {
        if (targetDates.value.length === 0) return
        if (targetDates.value[0] !== dateStr) return
        targetDates.value = []
        pushLog('warn', '已清除日期')
    }

    const clearTargetDates = () => {
        targetDates.value = []
        pushLog('warn', '已清空日期')
    }

    // Execution
    const buildGrabConfig = (rawConfig) => {
        // Validate required fields
        const errors = []
        if (!rawConfig.unit_id) errors.push('医院 ID')
        if (!rawConfig.dep_id) errors.push('科室 ID')
        if (!rawConfig.member_id) errors.push('就诊人 ID')
        if (!rawConfig.target_dates || rawConfig.target_dates.length === 0) errors.push('就诊日期')

        if (errors.length > 0) {
            throw new Error(`缺少必填项: ${errors.join(' / ')}`)
        }

        return rawConfig
    }

    const startGrab = async (configPayload) => {
        grabResult.value = null
        try {
            const validConfig = buildGrabConfig(configPayload)
            grabRunning.value = true
            // We pass the config to backend
            await StartGrab(validConfig)
            pushLog('info', '抢号任务已启动')
        } catch (err) {
            grabRunning.value = false
            pushLog('error', `启动抢号失败: ${stringifyError(err)}`)
        }
    }

    const stopGrab = async () => {
        try {
            await StopGrab()
            pushLog('warn', '正在停止任务...')
        } catch (err) {
            pushLog('error', `停止失败: ${stringifyError(err)}`)
        }
        // Note: grabRunning usually set to false by event 'grab-finished' or manual toggle
        // But immediate feedback is good
        grabRunning.value = false
    }

    const initGrabListeners = () => {
        EventsOn('grab-finished', (payload) => {
            grabRunning.value = false
            grabResult.value = payload || null
            if (payload?.success) {
                pushLog('success', payload?.message || '抢号完成')
            } else {
                pushLog('warn', payload?.message || '抢号失败')
            }
        })
    }

    return {
        targetDates,
        grabRunning,
        grabResult,
        preferredHours,
        timeTypes,
        selectedScheduleId,

        addDateRange,
        addTargetDate,
        removeTargetDate,
        clearTargetDates,
        startGrab,
        stopGrab,
        initGrabListeners
    }
}
