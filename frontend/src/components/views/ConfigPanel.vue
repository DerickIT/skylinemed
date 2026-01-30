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

// Initialize default dates
const today = new Date()
const nextWeek = new Date(today)
nextWeek.setDate(today.getDate() + 7)

const formatDate = (date) => {
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    return `${y}-${m}-${d}`
}

if (!dateInput.value && targetDates.value.length === 0) {
    dateInput.value = formatDate(nextWeek)
}

if (!checkScheduleDate.value) {
    checkScheduleDate.value = formatDate(today)
}

</script>

<template>
  <div class="space-y-8 pb-32 max-w-[1600px] mx-auto">
    <!-- Clean Header -->
    <header class="flex items-end justify-between py-6 border-b border-slate-200/60 transition-all">
      <div class="space-y-2">
         <h1 class="font-display font-black text-4xl text-slate-900 tracking-tight">Configuration</h1>
         <p class="text-slate-500 font-medium text-sm">配置您的全自动化抢号策略与拦截链路。</p>
      </div>
      <div class="hidden md:flex items-center gap-3 bg-white px-4 py-2 rounded-2xl border border-slate-100 shadow-sm">
         <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
         <span class="text-xs font-bold text-slate-600 uppercase tracking-widest">Skyline Engine Ready</span>
      </div>
    </header>

    <div class="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
       
       <!-- LEFT COLUMN: Foundation (Inputs) -->
       <div class="xl:col-span-4 space-y-6">
          <GlassCard title="CORE TARGETS" class="">
             <div class="space-y-5">
                <Combobox
                   label="城市 / CITY"
                   v-model="selectedCity"
                   :options="cities"
                   key-field="cityId"
                   label-field="name"
                   placeholder="选择城市..."
                   :loading="loadingCities"
                   :disabled="!loginChecked || !loggedIn"
                   :additional-search-fields="['match', 'pinyin', 'sanzima']"
                />
                
                <Combobox
                   label="医院 / HOSPITAL"
                   v-model="unitId"
                   :options="hospitals"
                   key-field="id"
                   label-field="name"
                   placeholder="选择目标医院..."
                   :loading="loadingHospitals"
                   :disabled="!loginChecked || !loggedIn || !selectedCity"
                />

                <Combobox
                   label="科室 / DEPARTMENT"
                   v-model="depId"
                   :options="deps"
                   key-field="id"
                   label-field="name"
                   placeholder="选择目标科室..."
                   :loading="loadingDeps"
                   :disabled="!loginChecked || !loggedIn || !unitId"
                />
             </div>
          </GlassCard>

          <GlassCard title="IDENTITY">
             <div class="space-y-4">
                <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">就诊人信息</label>
                <div class="relative group">
                   <select v-model="memberId" class="w-full bg-slate-50 border border-slate-200 rounded-2xl px-5 py-4 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none hover:bg-white transition-all appearance-none text-slate-700 font-bold font-display">
                      <option v-if="!loggedIn" value="">请先登录账号</option>
                      <option v-else-if="members.length === 0" value="">未找到就诊人</option>
                      <option v-for="m in members" :key="m.id" :value="m.id">{{ m.name }} {{ m.certified ? '(已实名)' : '' }}</option>
                   </select>
                   <div class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                   </div>
                </div>
             </div>
          </GlassCard>
          
          <GlassCard title="DATES">
             <div class="space-y-4">
                 <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">预约日期</label>
                 <div class="flex gap-2">
                    <input type="date" v-model="dateInput" class="flex-1 bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3 text-sm font-bold text-slate-700 focus:ring-2 focus:ring-blue-500/20 outline-none hover:bg-white transition-all op-calendar cursor-pointer" />
                    <button @click="handleClearDate" class="px-4 rounded-2xl bg-slate-50 border border-slate-200 text-slate-400 hover:text-red-500 hover:border-red-200 transition-colors">
                       <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                 </div>
                 <div v-if="targetDates.length > 0" class="flex flex-wrap gap-2">
                    <span v-for="date in targetDates" :key="date" class="px-3 py-1 bg-blue-50 text-blue-600 rounded-lg text-xs font-black border border-blue-100">
                       {{ date }}
                    </span>
                 </div>
             </div>
          </GlassCard>
       </div>

       <!-- RIGHT COLUMN: Analysis & Pool -->
       <div class="xl:col-span-8 space-y-6">
          
          <!-- Strategy Card -->
          <GlassCard title="STRATEGY">
             <div class="flex items-center justify-between">
                <div class="flex items-center gap-4">
                   <div class="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center">
                      <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                   </div>
                   <div>
                      <h4 class="font-display font-bold text-slate-900">Smart Cloud Proxy</h4>
                      <p class="text-xs text-slate-500">Enable distributed proxy network to bypass IP rate limits.</p>
                   </div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                   <input type="checkbox" v-model="proxySubmitEnabled" class="sr-only peer" />
                   <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:bg-emerald-500 transition-all"></div>
                   <div class="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-5 shadow-sm"></div>
                </label>
             </div>
          </GlassCard>

          <!-- Deep Analysis -->
          <GlassCard title="DEEP ANALYSIS">
             <div class="space-y-8">
                <!-- Controls -->
                <div class="flex flex-col md:flex-row md:items-end gap-4 p-1">
                   <div class="flex-1 space-y-2">
                       <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">SCAN START DATE</label>
                       <input type="date" v-model="checkScheduleDate" class="w-full bg-white border border-slate-200 rounded-2xl px-4 py-3 text-sm font-bold shadow-sm focus:ring-2 focus:ring-blue-500/20 outline-none" />
                   </div>
                   <div class="w-full md:w-32 space-y-2">
                       <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">RANGE (DAYS)</label>
                       <input type="number" v-model="doctorRangeDays" min="1" max="30" class="w-full bg-white border border-slate-200 rounded-2xl px-4 py-3 text-sm font-bold shadow-sm focus:ring-2 focus:ring-blue-500/20 outline-none" />
                   </div>
                   <NeonButton 
                      @click="handleBuildDoctorPool" 
                      :loading="loadingDoctorPool || loadingDoctors"
                      :disabled="!loginChecked || !loggedIn || !unitId || !depId || !checkScheduleDate"
                      size="lg" 
                      class="!rounded-2xl"
                   >
                      <span class="font-display font-black tracking-wider text-sm">SCAN POOL</span>
                   </NeonButton>
                </div>

                <!-- Matrix -->
                <div class="relative min-h-[200px] border-t border-slate-100 pt-6">
                   <div v-if="doctorPool.length > 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      <div 
                        v-for="doc in doctorPool" 
                        :key="doc.id"
                        @click="doctorId = doc.id"
                        :class="['p-5 rounded-2xl border transition-all cursor-pointer relative overflow-hidden group', 
                            doctorId === doc.id ? 'bg-slate-900 border-slate-900 shadow-xl' : 'bg-white border-slate-100 hover:border-blue-300 hover:shadow-md']"
                      >
                         <div class="relative z-10 flex flex-col gap-3">
                            <div class="flex justify-between items-start">
                               <h5 :class="['font-display font-black text-lg', doctorId === doc.id ? 'text-white' : 'text-slate-900']">{{ doc.name }}</h5>
                               <div v-if="doctorScheduleMap.get(doc.id)?.left > 0" class="px-2 py-0.5 rounded bg-emerald-500 text-white text-[10px] font-bold">
                                  {{ doctorScheduleMap.get(doc.id)?.left }} Available
                               </div>
                            </div>
                            <div :class="['text-xs font-medium', doctorId === doc.id ? 'text-slate-400' : 'text-slate-500']">
                               Fee: <span :class="doctorId === doc.id ? 'text-emerald-400' : 'text-emerald-600'">¥{{ doc.fee }}</span>
                            </div>
                            <div :class="['text-[10px] font-black uppercase tracking-widest mt-2', doctorId === doc.id ? 'text-slate-500' : 'text-slate-400']">
                               Latest: {{ doc.latestDate }}
                            </div>
                         </div>
                      </div>
                   </div>
                   
                   <div v-else-if="!loadingDoctorPool" class="flex flex-col items-center justify-center py-12 opacity-40">
                      <svg class="w-12 h-12 text-slate-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                      <p class="text-xs font-bold uppercase tracking-widest text-slate-500">Ready to Scan</p>
                   </div>
                </div>

                <!-- Schedule & Time Selection -->
                <transition-group name="fade-slide">
                    <!-- Schedule Checkbox like buttons -->
                    <div v-if="doctorId && selectedSchedules.length > 0" key="schedule" class="space-y-4 pt-6 border-t border-slate-100">
                        <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">Available Sessions</label>
                        <div class="flex flex-wrap gap-3">
                            <button
                                v-for="slot in selectedSchedules"
                                :key="slot.schedule_id"
                                @click="handleSelectSchedule(slot)"
                                :class="['px-5 py-3 rounded-xl border text-xs font-bold transition-all',
                                    String(selectedScheduleId) === String(slot.schedule_id) 
                                    ? 'bg-blue-600 border-blue-600 text-white shadow-lg' 
                                    : 'bg-white border-slate-200 text-slate-600 hover:border-blue-400']"
                            >
                                {{ slot.time_type_desc || (slot.time_type === 'am' ? 'Morning' : 'Afternoon') }}
                                <span class="ml-1 opacity-70">({{ slot.left_num }})</span>
                            </button>
                        </div>
                    </div>

                    <!-- Time Slots -->
                    <div v-if="selectedScheduleId" key="times" class="space-y-4 pt-6 border-t border-slate-100">
                        <div class="flex items-center justify-between">
                            <label class="block text-[10px] font-black uppercase text-slate-400 tracking-widest">Precise Time Segments</label>
                            <button v-if="preferredHours.length > 0" @click="clearPreferredHours" class="text-[10px] font-bold text-red-500">RESET ALL</button>
                        </div>

                        <div v-if="timeSlotsLoading" class="py-12 flex justify-center">
                            <div class="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                        </div>
                        <div v-else-if="timeSlots.length > 0" class="flex flex-wrap gap-2">
                             <button
                                v-for="slot in timeSlots"
                                :key="slot.value"
                                @click="togglePreferredHour(slot.name)"
                                :class="['px-3 py-2 rounded-lg border text-[11px] font-bold transition-all',
                                    preferredHours.includes(slot.name)
                                    ? 'bg-slate-900 border-slate-900 text-white'
                                    : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50']"
                             >
                                {{ slot.name }}
                             </button>
                        </div>
                        <div v-else class="py-6 text-center text-xs text-slate-400 italic">No specific time segments available.</div>
                        
                        <!-- Manual Override -->
                        <div class="pt-4 flex gap-2">
                            <input type="text" v-model="manualTimeInput" placeholder="Manual Override (e.g. 09:00)" class="flex-1 bg-white border border-slate-200 rounded-xl px-4 py-2 text-xs font-bold outline-none focus:border-blue-500" />
                            <NeonButton size="sm" variant="ghost" @click="addManualPreferredHour" :disabled="!manualTimeInput" class="!rounded-xl">ADD</NeonButton>
                        </div>
                    </div>
                </transition-group>

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
