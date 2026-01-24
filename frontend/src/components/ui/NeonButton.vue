<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary', // primary, success, danger, ghost
    validator: (value) => ['primary', 'success', 'danger', 'ghost'].includes(value)
  },
  size: {
    type: String,
    default: 'md', // sm, md, lg
  },
  disabled: Boolean,
  loading: Boolean,
  block: Boolean
})

defineEmits(['click'])

const classes = computed(() => {
  const base = 'relative inline-flex items-center justify-center font-medium transition-all duration-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed'
  
  const variants = {
    primary: 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-[0_0_15px_rgba(79,70,229,0.4)] hover:shadow-[0_0_25px_rgba(79,70,229,0.6)] border border-indigo-500/50',
    success: 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)] hover:shadow-[0_0_25px_rgba(16,185,129,0.6)] border border-emerald-500/50',
    danger: 'bg-rose-600 hover:bg-rose-500 text-white shadow-[0_0_15px_rgba(225,29,72,0.4)] hover:shadow-[0_0_25px_rgba(225,29,72,0.6)] border border-rose-500/50',
    ghost: 'bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white border border-white/5 hover:border-white/20'
  }

  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base'
  }

  return [
    base,
    variants[props.variant],
    sizes[props.size],
    props.block ? 'w-full' : '',
    props.loading ? 'cursor-wait' : ''
  ].join(' ')
})
</script>

<template>
  <button 
    :class="classes" 
    :disabled="disabled || loading" 
    @click="$emit('click', $event)"
  >
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center">
      <svg class="animate-spin h-4 w-4 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    </div>
    <span :class="{'opacity-0': loading}" class="flex items-center gap-2">
      <slot></slot>
    </span>
  </button>
</template>
