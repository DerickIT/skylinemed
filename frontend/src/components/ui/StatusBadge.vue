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
    success: 'bg-emerald-50 text-emerald-600 border-emerald-200',
    warn: 'bg-amber-50 text-amber-600 border-amber-200',
    error: 'bg-rose-50 text-rose-600 border-rose-200',
    info: 'bg-blue-50 text-blue-600 border-blue-200',
    neutral: 'bg-slate-50 text-slate-500 border-slate-200'
  }
  return map[props.variant] || map.neutral
})

const dotColor = computed(() => {
  const map = {
    success: 'bg-emerald-500',
    warn: 'bg-amber-500',
    error: 'bg-rose-500',
    info: 'bg-blue-500',
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
