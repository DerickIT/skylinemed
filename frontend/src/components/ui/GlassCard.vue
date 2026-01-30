<script setup>
defineProps({
  title: String,
  noPadding: Boolean,
  className: String
})
</script>

<template>
  <div :class="['glass rounded-2xl flex flex-col', className]">
    <div v-if="title" class="px-5 py-4 border-b border-white/50 bg-white/40 flex items-center justify-between rounded-t-2xl">
      <h3 class="font-semibold text-slate-800 tracking-wide text-sm uppercase">{{ title }}</h3>
      <slot name="action"></slot>
    </div>
    <div :class="[noPadding ? '' : 'p-5']">
      <slot></slot>
    </div>
  </div>
</template>
