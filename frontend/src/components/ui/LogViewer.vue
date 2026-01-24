<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import NeonButton from './NeonButton.vue'

const props = defineProps({
  logs: { type: Array, default: () => [] },
  filters: { type: Object, default: () => ({}) },
  stats: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['toggleFilter', 'clear', 'export'])

const logContainer = ref(null)
const autoScroll = ref(true)

const scrollToBottom = async () => {
  if (!autoScroll.value || !logContainer.value) return
  await nextTick()
  logContainer.value.scrollTop = logContainer.value.scrollHeight
}

watch(() => props.logs.length, () => {
  scrollToBottom()
})

onMounted(() => {
  scrollToBottom()
})

const levelColors = {
  info: 'text-slate-400',
  warn: 'text-amber-400',
  error: 'text-rose-400',
  success: 'text-emerald-400'
}

const formatTime = (timeStr) => {
  // Simple check if it has date part, usually we just want HH:MM:SS
  if (!timeStr) return ''
  return timeStr.split(' ').pop()
}
</script>

<template>
  <div class="flex flex-col h-full bg-slate-950/50 rounded-xl border border-white/5 overflow-hidden">
    <!-- Toolbar -->
    <div class="flex items-center justify-between px-3 py-2 bg-white/5 border-b border-white/5">
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-500 font-mono">CONSOLE_OUTPUT</span>
        <div class="h-4 w-px bg-white/10 mx-1"></div>
        <button 
          v-for="(active, key) in filters" 
          :key="key"
          @click="$emit('toggleFilter', key)"
          :class="[
            'text-[10px] px-1.5 py-0.5 rounded border transition-colors uppercase',
            active 
              ? `bg-${key === 'error' ? 'rose' : key === 'warn' ? 'amber' : key === 'success' ? 'emerald' : 'blue'}-500/20 border-${key === 'error' ? 'rose' : key === 'warn' ? 'amber' : key === 'success' ? 'emerald' : 'blue'}-500/30 text-${key === 'error' ? 'rose' : key === 'warn' ? 'amber' : key === 'success' ? 'emerald' : 'blue'}-400`
              : 'bg-transparent border-slate-700 text-slate-600'
          ]"
        >
          {{ key }} {{ stats[key] || 0 }}
        </button>
      </div>
      <div class="flex items-center gap-2">
         <NeonButton size="sm" variant="ghost" @click="$emit('clear')">
            <span class="text-[10px]">CLEAR</span>
         </NeonButton>
         <NeonButton size="sm" variant="ghost" @click="$emit('export')">
            <span class="text-[10px]">EXPORT</span>
         </NeonButton>
      </div>
    </div>

    <!-- Logs -->
    <div 
      ref="logContainer"
      class="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-1 custom-scrollbar min-h-0"
    >
      <div 
        v-for="(log, idx) in logs" 
        :key="idx" 
        class="flex items-start gap-2 hover:bg-white/5 p-0.5 rounded transition-colors group"
      >
        <span class="text-slate-600 shrink-0 select-none">[{{ formatTime(log.time) }}]</span>
        <span :class="['break-all', levelColors[log.level] || 'text-slate-300']">
          <span v-if="log.level === 'error'" class="mr-1">✖</span>
          <span v-else-if="log.level === 'success'" class="mr-1">✔</span>
          <span v-else-if="log.level === 'warn'" class="mr-1">⚠</span>
          <span v-else class="mr-1">➜</span>
          {{ log.message }}
        </span>
      </div>
      
      <div v-if="logs.length === 0" class="text-slate-600 italic text-center mt-10">
        // Waiting for system events...
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  @apply bg-slate-800 rounded;
}
</style>
