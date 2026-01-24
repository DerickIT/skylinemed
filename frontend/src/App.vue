<script setup>
import { ref, onMounted } from 'vue'
import AppShell from './components/ui/AppShell.vue'
import Dashboard from './components/views/Dashboard.vue'
import ConfigPanel from './components/views/ConfigPanel.vue'
import TaskMonitor from './components/views/TaskMonitor.vue'

import { useLogger } from './composables/useLogger'
import { useAuth } from './composables/useAuth'
import { useGrabTask } from './composables/useGrabTask'

// Initialize Composables
const { initLogListeners } = useLogger()
const { initAuthListeners, loadUserState, userState, loggedIn } = useAuth()
const { initGrabListeners } = useGrabTask()

// Navigation State
const currentPage = ref('dashboard')

// Initialize Logic
onMounted(async () => {
    initLogListeners()
    initGrabListeners()
    await loadUserState() // Load preferences
    initAuthListeners() // Check login
})

// Quick helper for user name display
const userName = ref('User') // We could parse from members or userState if available
// userState might store last login info? 
// For now mostly static or derived.
</script>

<template>
  <AppShell 
    :current-page="currentPage" 
    :user-name="loggedIn ? 'Verified User' : 'Guest'"
    :connection-status="'connected'"
    @navigate="(page) => currentPage = page"
  >
    <div class="max-w-7xl mx-auto h-full">
       <Transition name="fade" mode="out-in">
          <Dashboard v-if="currentPage === 'dashboard'" @navigate="(page) => currentPage = page" />
          <ConfigPanel v-else-if="currentPage === 'config'" />
          <TaskMonitor v-else-if="currentPage === 'logs'" />
       </Transition>
    </div>
  </AppShell>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
