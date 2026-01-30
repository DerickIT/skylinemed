<script setup>
import { computed, watch, ref } from 'vue'
import { useHospitalData } from '../../composables/useHospitalData'
import { useAuth } from '../../composables/useAuth'
import { useGrabTask } from '../../composables/useGrabTask'
import { useLogger } from '../../composables/useLogger'
import { GetTicketDetail } from '../../api/tauri' // Corrected import path
import GlassCard from '../ui/GlassCard.vue'
import NeonButton from '../ui/NeonButton.vue'
import StatusBadge from '../ui/StatusBadge.vue'
import Combobox from '../ui/Combobox.vue'

const { 
  cities, selectedCity, loadCities,
  hospitals, unitId, loadHospitals, loadingHospitals,
  deps, depId, loadDeps, loadingDeps,
  doctors, doctorId, loadDoctors, loadingDoctors,
  doctorPool, loadDoctorPool, loadingDoctorPool,
  memberId,
  loadingCities
} = useHospitalData()

const { members, loadMembers, loggedIn, loginChecked, userState, saveUserState, stateReady } = useAuth()

const { 
  targetDates,
  addTargetDate,
  clearTargetDates,
  preferredHours,
  timeTypes,
  selectedScheduleId
} = useGrabTask()

const { pushLog, stringifyError } = useLogger()

// Local UI state
const dateInput = ref('')
const timeSlots = ref([])
const timeSlotsLoading = ref(false)
const doctorRangeDays = ref(3)
const manualTimeInput = ref('')
const proxySubmitEnabled = ref(true)

watch(targetDates, (list) => {
  const value = Array.isArray(list) && list.length > 0 ? list[0] : ''
  if (dateInput.value !== value) dateInput.value = value
}, { immediate: true })

watch(
  () => userState.value?.proxy_submit_enabled,
  (value) => {
    proxySubmitEnabled.value = value !== false
  },
  { immediate: true }
)

watch(proxySubmitEnabled, (value) => {
  if (!stateReady.value) return
  if (!userState.value || typeof userState.value !== 'object') {
    userState.value = {}
  }
  const next = Boolean(value)
  if (userState.value.proxy_submit_enabled === next) return
  userState.value.proxy_submit_enabled = next
  saveUserState()
})

watch(dateInput, (value) => {
  const current = targetDates.value[0] || ''
  if (value === current) return
  if (value) {
    addTargetDate(value)
    if (!checkScheduleDate.value || checkScheduleDate.value === current) {
      checkScheduleDate.value = value
    }
    if (loginChecked.value && loggedIn.value && unitId.value && depId.value) {
      loadDoctors(unitId.value, depId.value, value)
    }
  } else {
    clearTargetDates()
  }
})

// Helpers to trigger loads when selection changes
watch(selectedCity, (newVal) => {
  if (!loginChecked.value || !loggedIn.value) return
  if (newVal) loadHospitals(newVal)
}, { immediate: true })

watch(unitId, (newVal) => {
  if (!loginChecked.value || !loggedIn.value) return
  if (newVal) loadDeps(newVal)
}, { immediate: true })

watch([loginChecked, loggedIn], ([checked, isLoggedIn]) => {
  if (!checked) return
  if (isLoggedIn) {
    if (cities.value.length === 0) loadCities()
    if (members.value.length === 0) loadMembers()
    return
  }
  cities.value = []
  selectedCity.value = ''
  hospitals.value = []
  unitId.value = ''
  deps.value = []
  depId.value = ''
  doctors.value = []
  doctorId.value = ''
  doctorPool.value = []
}, { immediate: true })

// Doctor loading depends on date too, complicated because we have multiple dates.
// Usually we check schedule for the 'first' target date or user manually checks.
// App.vue logic: loadDoctors(unitID, depID, dateValue).
// We'll add a 'Check Schedule' button or watchers.
const checkScheduleDate = ref('') 

const selectedDoctor = computed(() => {
  return doctors.value.find(item => item.id === doctorId.value) || null
})

const selectedSchedules = computed(() => {
  return Array.isArray(selectedDoctor.value?.schedules) ? selectedDoctor.value.schedules : []
})

const doctorScheduleMap = computed(() => {
  const map = new Map()
  doctors.value.forEach((doc) => {
    map.set(doc.id, doc)
  })
  return map
})

const hasPreciseSelection = computed(() => {
  return Boolean(
    doctorId.value ||
    selectedScheduleId.value ||
    (Array.isArray(preferredHours.value) && preferredHours.value.length > 0) ||
    (Array.isArray(timeTypes.value) && timeTypes.value.length > 0)
  )
})

watch(doctorId, () => {
  selectedScheduleId.value = ''
  preferredHours.value = []
  timeTypes.value = []
  timeSlots.value = []
})

const handleClearDate = () => {
  dateInput.value = ''
}

const handleCheckSchedule = () => {
    loadDoctors(unitId.value, depId.value, checkScheduleDate.value)
}

const handleBuildDoctorPool = async () => {
  syncTargetDateToSchedule()
  await loadDoctorPool(unitId.value, depId.value, checkScheduleDate.value, doctorRangeDays.value)
  await loadDoctors(unitId.value, depId.value, checkScheduleDate.value)
}
const handleSelectSchedule = async (slot) => {
  syncTargetDateToSchedule()
  const scheduleId = String(slot?.schedule_id || '')
  if (!scheduleId) return
  selectedScheduleId.value = scheduleId
  const timeType = String(slot?.time_type || '')
  timeTypes.value = timeType ? [timeType] : []
  preferredHours.value = []
  timeSlots.value = []

  if (!unitId.value || !depId.value) return
  timeSlotsLoading.value = true
  try {
    const detail = await GetTicketDetail(
      String(unitId.value),
      String(depId.value),
      scheduleId,
      String(memberId.value || '')
    )
    const times = detail?.times || detail?.time_slots || []
    timeSlots.value = Array.isArray(times)
      ? times.map(item => ({
        name: String(item?.name || '').trim(),
        value: String(item?.value || '').trim()
      })).filter(item => item.name)
      : []
    if (timeSlots.value.length === 0) {
      pushLog('warn', '未获取到具体时段')
    }
  } catch (err) {
    pushLog('error', `具体时段获取失败: ${stringifyError(err)}`)
  } finally {
    timeSlotsLoading.value = false
  }
}

const togglePreferredHour = (name) => {
  const value = String(name || '').trim()
  if (!value) return
  const set = new Set(preferredHours.value)
  if (set.has(value)) {
    set.delete(value)
  } else {
    set.add(value)
  }
  preferredHours.value = Array.from(set)
}

const clearPreferredHours = () => {
  preferredHours.value = []
}

const addManualPreferredHour = () => {
  const value = String(manualTimeInput.value || '').trim()
  if (!value) return
  const set = new Set(preferredHours.value)
  set.add(value)
  preferredHours.value = Array.from(set)
  manualTimeInput.value = ''
}

const syncTargetDateToSchedule = () => {
  const scheduleDate = String(checkScheduleDate.value || '').trim()
  if (!scheduleDate) return
  const target = targetDates.value[0] || ''
  if (target === scheduleDate) return
  addTargetDate(scheduleDate)
  pushLog('warn', `排班查询日期与抢号日期不一致，已同步为 ${scheduleDate}`)
}

const clearPreciseSelection = () => {
  doctorId.value = ''
  selectedScheduleId.value = ''
  preferredHours.value = []
  timeTypes.value = []
  timeSlots.value = []
  manualTimeInput.value = ''
}

</script>

<template>
  <div class="space-y-10 pb-24">
    <!-- Header Section -->
    <header class="flex flex-col gap-1">
      <h1 class="text-3xl font-bold tracking-tight text-slate-900">配置中心</h1>
      <p class="text-slate-500 text-sm">精确配置您的抢号目标，Skyline 引擎将全速为您护航。</p>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 relative items-start">

       <!-- Left Column: Core Settings -->
       <div class="lg:col-span-4 space-y-8 sticky top-6">
          <GlassCard title="挂号目标">
             <div class="space-y-6">
                <Combobox
                   label="所在城市"
                   v-model="selectedCity"
                   :options="cities"
                   key-field="cityId"
                   label-field="name"
                   placeholder="搜索城市..."
                   :loading="loadingCities"
                   :disabled="!loginChecked || !loggedIn"
                />
                
                <Combobox
                   label="目标医院"
                   v-model="unitId"
                   :options="hospitals"
                   key-field="id"
                   label-field="name"
                   placeholder="请选择或搜索医院..."
                   :loading="loadingHospitals"
                   :disabled="!loginChecked || !loggedIn || !selectedCity"
                />

                <Combobox
                   label="目标科室"
                   v-model="depId"
                   :options="deps"
                   key-field="id"
                   label-field="name"
                   placeholder="请选择或搜索科室..."
                   :loading="loadingDeps"
                   :disabled="!loginChecked || !loggedIn || !unitId"
                />
             </div>
          </GlassCard>

          <GlassCard title="就诊身份">
             <div class="space-y-6">
                <div>
                   <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest mb-2">预约人信息</label>
                   <div class="relative group">
                      <select v-model="memberId" class="w-full bg-slate-50 border border-slate-200 rounded-2xl px-5 py-3.5 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none hover:bg-white transition-all appearance-none text-slate-700 font-medium">
                         <option v-if="!loggedIn" value="">请先登录账号</option>
                         <option v-else-if="members.length === 0" value="">未找到就诊人信息</option>
                         <option v-for="m in members" :key="m.id" :value="m.id">{{ m.name }} {{ m.certified ? ' (已实名)' : '' }}</option>
                      </select>
                      <div class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400 transition-transform group-hover:translate-y-[-40%] group-hover:scale-110">
                         <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                      </div>
                   </div>
                </div>

                <div class="pt-6 border-t border-slate-100">
                   <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest mb-3">首选预约日期</label>
                   <div class="flex gap-3">
                      <input type="date" v-model="dateInput" class="glass-input flex-1 op-calendar cursor-pointer" />
                      <NeonButton size="sm" variant="ghost" @click="handleClearDate" :disabled="targetDates.length === 0" class="!rounded-2xl">
                         Reset
                      </NeonButton>
                   </div>
                   <div v-if="targetDates.length > 0" class="mt-3 flex items-center gap-2 px-3 py-1.5 bg-blue-50 rounded-lg border border-blue-100 w-fit">
                      <span class="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                      <span class="text-[11px] font-bold text-blue-600">已选: {{ targetDates[0] }}</span>
                   </div>
                </div>
             </div>
          </GlassCard>
       </div>

       <!-- Right Column: Precise Control -->
       <div class="lg:col-span-8 space-y-8">
          
          <GlassCard title="提交策略优化">
             <div class="flex items-center justify-between p-6 glass-panel rounded-3xl border border-slate-200 hover:border-blue-200 transition-all">
                <div class="flex items-center gap-5">
                   <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                      <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                   </div>
                   <div>
                      <div class="text-slate-900 font-bold tracking-tight">智能代理链路 (Smart Cloud Proxy)</div>
                      <div class="text-[11px] text-slate-500 max-w-sm">启用后，系统将在检测到 IP 压制时通过天际高匿名节点重试，大幅提升高频波峰下的成功率。</div>
                   </div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                   <input type="checkbox" v-model="proxySubmitEnabled" class="sr-only peer" />
                   <div class="w-14 h-7 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:bg-blue-600 transition-all shadow-inner"></div>
                   <div class="absolute left-1 top-1 w-5 h-5 bg-white rounded-full transition-transform peer-checked:translate-x-7 shadow-sm"></div>
                </label>
             </div>
          </GlassCard>

          <GlassCard title="排班深度分析">
             <div class="space-y-8">
                <!-- Data Source Selection -->
                <div class="flex flex-col gap-5 md:flex-row md:items-end p-1">
                   <div class="flex-1 space-y-3">
                      <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">扫描目标日期</label>
                      <input type="date" v-model="checkScheduleDate" class="glass-input w-full cursor-pointer h-12" />
                   </div>
                   <div class="w-full md:w-32 space-y-3">
                      <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">预测半径 (天)</label>
                      <input type="number" v-model="doctorRangeDays" min="0" max="30" class="glass-input w-full h-12" />
                   </div>
                   <NeonButton
                     @click="handleBuildDoctorPool"
                     :loading="loadingDoctorPool || loadingDoctors"
                     :disabled="!loginChecked || !loggedIn || !unitId || !depId || !checkScheduleDate"
                     size="lg"
                     class="h-12 !rounded-xl"
                   >
                      扫描候选池
                   </NeonButton>
                </div>
                
                <div class="flex items-center justify-between py-4 border-y border-slate-100">
                   <div class="flex items-center gap-3">
                      <StatusBadge :variant="hasPreciseSelection ? 'success' : 'neutral'" dot size="sm">
                         {{ hasPreciseSelection ? '已激活精细化指令' : '全自动模糊匹配' }}
                      </StatusBadge>
                      <span class="text-slate-500 text-[10px] font-medium italic">模式自动切换</span>
                   </div>
                   <button
                     v-if="hasPreciseSelection"
                     type="button"
                     class="px-3 py-1 bg-slate-100 border border-slate-200 rounded-full text-[10px] text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-all"
                     @click="clearPreciseSelection"
                   >
                     Reset AI Instructions
                   </button>
                </div>

                <!-- Doctor Pool -->
                <div v-if="doctorPool.length > 0" class="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[400px] overflow-y-auto custom-scrollbar pr-2">
                   <div 
                     v-for="doc in doctorPool" 
                     :key="doc.id"
                     @click="doctorId = doc.id"
                     :class="['p-5 rounded-3xl border cursor-pointer transition-all relative overflow-hidden group', 
                       doctorId === doc.id ? 'bg-blue-50 border-blue-200 shadow-xl shadow-blue-500/5' : 'bg-white border-slate-200 hover:border-blue-200 hover:shadow-lg hover:shadow-slate-200/50']"
                   >
                      <div class="flex justify-between items-center relative z-10">
                         <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600 border border-slate-200 group-hover:scale-110 transition-transform">
                               {{ doc.name?.charAt(0) }}
                            </div>
                            <div>
                               <h5 class="font-bold text-slate-900">{{ doc.name }}</h5>
                               <p class="text-[10px] text-slate-500 font-medium">挂号费: <span class="text-emerald-600">¥{{ doc.fee }}</span></p>
                            </div>
                         </div>
                         <div v-if="doctorScheduleMap.get(doc.id)?.left > 0" class="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-600 text-[9px] font-black border border-emerald-100">
                            余号: {{ doctorScheduleMap.get(doc.id)?.left }}
                         </div>
                      </div>
                      <div class="mt-4 flex gap-4 text-[10px] text-slate-400 font-semibold uppercase tracking-wider opacity-80 relative z-10">
                         <span>排班: {{ doc.scheduleSlots }} 场</span>
                         <span>最新: {{ doc.latestDate?.split('-').slice(1).join('/') || '-' }}</span>
                      </div>
                      <!-- Decorative background accent -->
                      <div class="absolute -right-6 -bottom-6 w-16 h-16 bg-blue-500/5 blur-2xl rounded-full"></div>
                   </div>
                </div>
                <div v-else-if="!loadingDoctorPool && checkScheduleDate" class="py-12 flex flex-col items-center justify-center space-y-3 opacity-40">
                   <svg class="w-12 h-12 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                   <p class="text-[11px] font-bold text-slate-400 uppercase tracking-widest">当前无查询结果</p>
                </div>

                <!-- Schedule Selection -->
                <Transition name="fade-slide">
                   <div v-if="doctorId && selectedSchedules.length > 0" class="space-y-4 pt-4 border-t border-slate-100">
                      <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">选择锁定场次</label>
                      <div class="flex flex-wrap gap-3">
                         <button
                           v-for="slot in selectedSchedules"
                           :key="slot.schedule_id || slot.time_type"
                           type="button"
                           @click="handleSelectSchedule(slot)"
                           :class="[
                             'px-5 py-3 rounded-2xl text-xs font-bold border transition-all active:scale-95',
                             String(selectedScheduleId) === String(slot.schedule_id)
                               ? 'bg-blue-600 border-blue-600 text-white shadow-lg shadow-blue-500/30'
                               : 'bg-white border-slate-200 text-slate-500 hover:text-slate-800 hover:border-blue-300 hover:shadow-md hover:shadow-slate-200/50'
                           ]"
                         >
                           {{ slot.time_type_desc || (slot.time_type === 'am' ? '上午' : '下午') }}
                           <span class="ml-2 opacity-60 text-[10px]">余{{ slot.left_num || 0 }}</span>
                         </button>
                      </div>
                   </div>
                </Transition>

                <!-- Time Filter -->
                <Transition name="fade-slide">
                   <div v-if="selectedScheduleId" class="space-y-4 pt-4 border-t border-slate-100">
                      <div class="flex items-center justify-between">
                         <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">精细化时段过滤</label>
                         <button v-if="preferredHours.length > 0" type="button" class="text-[10px] font-bold text-red-500 hover:text-red-400 uppercase tracking-widest transition-all" @click="clearPreferredHours">
                            CLEAR ALL
                         </button>
                      </div>
                      
                      <div v-if="timeSlotsLoading" class="p-6 bg-slate-50 animate-pulse rounded-2xl border border-slate-200 flex items-center justify-center text-[11px] text-slate-400 font-bold uppercase tracking-widest">
                         Analyzing Time Slots...
                      </div>
                      <div v-else-if="timeSlots.length > 0" class="flex flex-wrap gap-2">
                         <button
                           v-for="slot in timeSlots"
                           :key="slot.value || slot.name"
                           type="button"
                           @click="togglePreferredHour(slot.name)"
                           :class="[
                             'px-4 py-2.5 rounded-xl text-[11px] font-bold border transition-all active:scale-95',
                             preferredHours.includes(slot.name)
                               ? 'bg-emerald-50 border-emerald-200 text-emerald-600 shadow-sm'
                               : 'bg-white border-slate-200 text-slate-500 hover:text-slate-800 hover:border-blue-300'
                           ]"
                         >
                           {{ slot.name }}
                         </button>
                      </div>
                      <div v-else class="text-center py-6 text-[10px] text-slate-400 font-bold uppercase tracking-tighter">该场次暂无细分时段数据</div>

                      <!-- Manual Entry -->
                      <div v-if="doctorId" class="pt-4 flex flex-col gap-3">
                         <p class="text-[9px] text-slate-400 font-black uppercase tracking-tighter">手动补充特定时段 (E.G. 09:00 - 09:30)</p>
                         <div class="flex gap-2">
                            <input type="text" v-model="manualTimeInput" class="glass-input flex-1 py-1.5 text-xs !rounded-2xl" placeholder="请输入时段描述..." />
                            <NeonButton size="sm" variant="ghost" @click="addManualPreferredHour" :disabled="!manualTimeInput" class="!px-6 !rounded-2xl">
                               ADD
                            </NeonButton>
                         </div>
                      </div>
                   </div>
                </Transition>
             </div>
          </GlassCard>

       </div>
    </div>
  </div>
</template>

<style scoped>
.op-calendar {
  color-scheme: dark;
}

.fade-slide-enter-active, .fade-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
}
.fade-slide-enter-from, .fade-slide-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
