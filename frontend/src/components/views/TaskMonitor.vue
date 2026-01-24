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
  <div class="h-full pb-20">
    <LogViewer 
      :logs="filteredLogs" 
      :filters="logFilters" 
      :stats="logStats"
      @toggleFilter="toggleLogFilter"
      @clear="clearLogs"
      @export="exportLogs"
    />
  </div>
</template>
