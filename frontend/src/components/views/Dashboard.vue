<script setup>
import { computed } from 'vue'
import { useAuth } from '../../composables/useAuth'
import { useGrabTask } from '../../composables/useGrabTask'
import { useHospitalData } from '../../composables/useHospitalData'
import GlassCard from '../ui/GlassCard.vue'
import NeonButton from '../ui/NeonButton.vue'
import StatusBadge from '../ui/StatusBadge.vue'

const { 
  loggedIn, 
  loginChecked, 
  qrImageUrl, 
  qrStatus, 
  loginRunning, 
  toggleLogin, 
  userState,
  members
} = useAuth()

const { 
  grabRunning, 
  startGrab,
  stopGrab,
  targetDates,
  preferredHours,
  timeTypes,
  selectedScheduleId
} = useGrabTask()

// Status Derivations
const loginBtnLabel = computed(() => {
  if (loggedIn.value) return '已登录'
  return loginRunning.value ? '停止扫码' : '扫码登录'
})

const grabBtnVariant = computed(() => grabRunning.value ? 'danger' : 'primary')
const grabBtnLabel = computed(() => grabRunning.value ? '停止抢号' : '开始抢号')

// Simple summary
const configSummary = computed(() => {
  const parts = []
  if (userState.value?.unit_name) parts.push(userState.value.unit_name)
  if (userState.value?.dep_name) parts.push(userState.value.dep_name)
  return parts.join(' - ') || '暂无配置'
})

const proxySubmitEnabled = computed(() => {
  return userState.value?.proxy_submit_enabled !== false
})

  // Export selected IDs from useHospitalData
  const { 
    selectedCity, 
    hospitals, 
    deps, 
    doctors,
    unitId: selectedUnitId,
    depId: selectedDepId,
    doctorId: selectedDoctorId,
    memberId: selectedMemberId
  } = useHospitalData()

  const hasPreciseSelection = computed(() => {
    return Boolean(
      selectedDoctorId.value ||
      selectedScheduleId.value ||
      (Array.isArray(timeTypes.value) && timeTypes.value.length > 0) ||
      (Array.isArray(preferredHours.value) && preferredHours.value.length > 0)
    )
  })

  const executeGrab = async () => {
     // Build the config payload from shared state
     const config = {
        unit_id: selectedUnitId.value,
        dep_id: selectedDepId.value,
        member_id: selectedMemberId.value,
        // target_dates is already managed inside useGrabTask, 
        // but startGrab might expect us to pass them or it uses its own state.
        // Checking useGrabTask.js: startGrab takes configPayload.
        // It validates: unit_id, dep_id, member_id, target_dates.
        // So we MUST pass target_dates here if useGrabTask doesn't auto-include them from its state.
        // Let's check useGrabTask.js...
        // ... buildGrabConfig(rawConfig) checks rawConfig.target_dates.
        // So we need to pass it.
        target_dates: targetDates.value,
        use_proxy_submit: proxySubmitEnabled.value
     }

     if (hasPreciseSelection.value) {
        if (selectedDoctorId.value) {
           config.doctor_id = selectedDoctorId.value
        }
        if (Array.isArray(timeTypes.value) && timeTypes.value.length > 0) {
           config.time_types = timeTypes.value
        }
        if (Array.isArray(preferredHours.value) && preferredHours.value.length > 0) {
           config.preferred_hours = preferredHours.value
        }
     }
     
     // Note: Other optional fields (e.g. time_slots) can be added later if needed.
     // For now, minimal valid config.
     
     await startGrab(config)
  }

  const handleToggleGrab = () => {
    if (grabRunning.value) {
      stopGrab()
    } else {
      executeGrab()
    }
  }

  const emit = defineEmits(['navigate'])
</script>

<template>
  <div class="space-y-8 pb-24">
    <!-- Luxury Header -->
    <header class="flex flex-col md:flex-row md:items-end justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold tracking-tight text-white mb-2">
          {{ loggedIn ? '欢迎回来，天际医航' : '开启便捷就医之旅' }}
        </h1>
        <p class="text-zinc-400 max-w-lg">
          {{ loggedIn ? '系统已准备就绪，随时可以进行号源锁定与极速预约。' : '请先扫码登录，然后配置您的预约目标，我们会为您实时监控。' }}
        </p>
      </div>
      <div v-if="loggedIn" class="flex items-center gap-3 px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full animate-pulse-subtle">
        <div class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]"></div>
        <span class="text-xs font-semibold text-emerald-400 uppercase tracking-widest">服务连接正常</span>
      </div>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Status Card -->
      <GlassCard title="账号状态" className="lg:col-span-5 h-full">
        <div class="flex flex-col items-center justify-center py-6 space-y-6">
          <div class="relative group">
            <div :class="['flex items-center justify-center border-[6px] transition-all duration-700 ease-in-out overflow-hidden', 
                loggedIn 
                  ? 'w-36 h-36 rounded-full border-zinc-800 shadow-[0_20px_50px_rgba(0,0,0,0.5)] scale-100 opacity-100' 
                  : 'w-56 h-56 rounded-3xl border-white/5 bg-white shadow-2xl scale-100']">
                <img v-if="qrImageUrl && !loggedIn" :src="qrImageUrl" class="w-full h-full object-contain p-4" />
                <div v-else class="flex items-center justify-center w-full h-full bg-gradient-to-br from-zinc-800 to-zinc-900">
                   <svg v-if="loggedIn" class="w-16 h-16 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                   </svg>
                   <svg v-else class="w-20 h-20 text-blue-500/20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                   </svg>
                </div>
            </div>
            <!-- Glow effect behind QR -->
            <div v-if="!loggedIn && qrImageUrl" class="absolute -inset-4 bg-blue-500/10 blur-2xl -z-10 rounded-full animate-float opacity-50"></div>
          </div>
          
          <div class="text-center space-y-1">
             <h2 class="text-2xl font-bold tracking-tight text-white">{{ loggedIn ? '认证通过' : (qrStatus || '准备就绪') }}</h2>
             <p class="text-zinc-500 text-sm italic">{{ loggedIn ? `就诊人: ${members.length} 位已就位` : '使用微信扫一扫以确认身份' }}</p>
          </div>

          <NeonButton 
            :variant="loggedIn ? 'ghost' : 'primary'" 
            :disabled="loggedIn"
            @click="toggleLogin" 
            :loading="loginRunning && !qrImageUrl"
            size="lg"
            class="min-w-[180px]"
          >
             {{ loggedIn ? '已保持在线' : loginBtnLabel }}
          </NeonButton>
        </div>
      </GlassCard>

      <!-- Task Control -->
      <GlassCard title="任务面板" className="lg:col-span-7 h-full">
        <div class="flex flex-col justify-between h-full min-h-[300px]">
           <div class="space-y-6">
              <div class="flex justify-between items-center group">
                 <div class="space-y-1">
                    <span class="text-zinc-500 text-xs font-bold uppercase tracking-widest">预约配置</span>
                    <h4 class="text-white font-semibold flex items-center gap-2">
                       {{ configSummary !== '暂无配置' ? configSummary : '等待完善配置' }}
                       <StatusBadge v-if="configSummary !== '暂无配置'" variant="info" size="xs">READY</StatusBadge>
                    </h4>
                 </div>
                 <button @click="$emit('navigate', 'config')" class="p-2 rounded-full hover:bg-white/5 transition-colors text-zinc-500 hover:text-white">
                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>
                 </button>
              </div>

              <div class="grid grid-cols-2 gap-4">
                 <div class="p-5 bg-zinc-900/40 rounded-2xl border border-white/[0.03] space-y-2 hover:border-white/10 transition-colors">
                    <div class="flex items-center gap-2 text-zinc-500">
                       <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                       <span class="text-[10px] font-black uppercase tracking-tighter">预约日期</span>
                    </div>
                    <div class="text-zinc-200 text-lg font-bold tracking-tight">
                       {{ targetDates[0] || '未指定' }}
                       <span v-if="targetDates.length > 1" class="text-blue-500 text-xs font-medium">+{{ targetDates.length - 1 }} 天</span>
                    </div>
                 </div>
                 <div class="p-5 bg-zinc-900/40 rounded-2xl border border-white/[0.03] space-y-2 hover:border-white/10 transition-colors">
                    <div class="flex items-center gap-2 text-zinc-500">
                       <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                       <span class="text-[10px] font-black uppercase tracking-tighter">提交模式</span>
                    </div>
                    <div class="text-zinc-200 text-lg font-bold tracking-tight">
                       {{ proxySubmitEnabled ? '云端模拟' : '直链提交' }}
                    </div>
                 </div>
              </div>
           </div>
           
           <div class="mt-8 space-y-4">
               <NeonButton 
                 size="lg" 
                 :variant="grabBtnVariant" 
                 @click="handleToggleGrab" 
                 block
                 class="h-16 text-lg"
               >
                 <span class="flex items-center gap-2">
                    <svg v-if="!grabRunning" class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    <svg v-else class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                    {{ grabBtnLabel }}
                 </span>
               </NeonButton>
               <p class="text-center text-xs text-zinc-500 font-medium">
                  由 Skyline 极速引擎驱动，当前任务已自动校准服务器时间。
               </p>
           </div>
        </div>
      </GlassCard>
      
      <!-- Quick Info Bar -->
      <div class="lg:col-span-12">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
           <div v-for="(step, idx) in [
              { title: '身份认证', desc: '微信扫码接入', color: 'blue' },
              { title: '极速预置', desc: '毫秒级配置同步', color: 'indigo' },
              { title: '全时守候', desc: '云端监控及时递交', color: 'emerald' }
           ]" :key="idx" class="glass-panel p-6 rounded-3xl flex items-center gap-5 hover:bg-zinc-800/50 transition-all cursor-default overflow-hidden relative">
              <div :class="[`w-14 h-14 rounded-2xl bg-${step.color}-500/10 flex items-center justify-center text-2xl font-black text-${step.color}-500`]">
                 {{ idx + 1 }}
              </div>
              <div class="flex-1">
                 <h4 class="text-zinc-100 font-bold tracking-tight">{{ step.title }}</h4>
                 <p class="text-zinc-500 text-xs">{{ step.desc }}</p>
              </div>
              <!-- Subtle accent glow -->
              <div :class="[`absolute -right-4 -bottom-4 w-16 h-16 bg-${step.color}-500/5 blur-2xl rounded-full`]"></div>
           </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-pulse-subtle {
  animation: pulse-subtle 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse-subtle {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
</style>
