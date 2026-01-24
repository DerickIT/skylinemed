<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String, // 'success', 'warn', 'error', 'info', 'neutral'
    default: 'neutral' 
  },
  dot: Boolean
})

const styles = computed(() => {
  const map = {
    success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    warn: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    error: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    neutral: 'bg-slate-500/10 text-slate-400 border-slate-500/20'
  }
  return map[props.variant] || map.neutral
})

const dotColor = computed(() => {
  const map = {
    success: 'bg-emerald-400',
    warn: 'bg-amber-400',
    error: 'bg-rose-400',
    info: 'bg-blue-400',
    neutral: 'bg-slate-400'
  }
  return map[props.variant] || map.neutral
})
</script>

<template>
  <span 
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border backdrop-blur-sm', 
      styles
    ]"
  >
    <span v-if="dot" :class="['w-1.5 h-1.5 rounded-full mr-1.5', dotColor, 'animate-pulse']"></span>
    <slot></slot>
  </span>
</template>
