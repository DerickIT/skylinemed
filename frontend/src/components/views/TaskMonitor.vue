<script setup>
import { useLogger } from '../../composables/useLogger'
import LogViewer from '../ui/LogViewer.vue'

const { 
  filteredLogs, 
  logFilters, 
  logStats, 
  toggleLogFilter, 
  clearLogs, 
  exportLogs 
} = useLogger()
</script>

<template>
  <div class="h-full space-y-8 pb-24">
    <header class="flex flex-col gap-1">
      <h1 class="text-3xl font-bold tracking-tight text-slate-900">任务监控</h1>
      <p class="text-slate-500 text-sm">实时追踪 Skyline 引擎的执行路径与响应状态。</p>
    </header>

    <div class="h-[calc(100vh-280px)] min-h-[500px]">
      <LogViewer 
        :logs="filteredLogs" 
        :filters="logFilters" 
        :stats="logStats"
        @toggleFilter="toggleLogFilter"
        @clear="clearLogs"
        @export="exportLogs"
      />
    </div>
  </div>
</template>
