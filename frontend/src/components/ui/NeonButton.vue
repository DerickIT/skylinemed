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
  const base = 'relative inline-flex items-center justify-center font-semibold transition-all duration-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50 disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]'
  
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 border border-white/10',
    success: 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 border border-white/10',
    danger: 'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-500/20 border border-white/10',
    ghost: 'bg-zinc-800/50 hover:bg-zinc-700/80 text-zinc-100 border border-white/5 hover:border-white/10'
  }

  const sizes = {
    sm: 'px-3.5 py-1.5 text-xs',
    md: 'px-5 py-2.5 text-sm',
    lg: 'px-8 py-3.5 text-base'
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
