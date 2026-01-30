<script setup>
import { computed } from 'vue'

const props = defineProps({
  currentPage: String, // 'dashboard', 'config', 'logs'
  userInitials: String,
  userName: String,
  connectionStatus: String // 'connected', 'disconnected'
})

const emit = defineEmits(['navigate'])

const navItems = [
  { id: 'dashboard', label: '主控台', icon: 'LayoutDashboard' },
  { id: 'config', label: '配置中心', icon: 'Settings2' },
  { id: 'logs', label: '日志监控', icon: 'Terminal' },
]

</script>

<template>
  <div class="h-screen w-screen bg-slate-950 text-slate-200 flex overflow-hidden selection:bg-indigo-500/30">
    
    <!-- Sidebar -->
    <aside class="w-64 bg-slate-900/50 backdrop-blur-xl border-r border-white/5 flex flex-col z-20">
      <!-- Logo -->
      <div class="h-16 flex items-center px-6 border-b border-white/5">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20 mr-3">
          <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </div>
        <span class="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">SkylineMed</span>
      </div>

      <!-- Nav -->
      <nav class="flex-1 p-4 space-y-1">
        <button 
          v-for="item in navItems" 
          :key="item.id"
          @click="$emit('navigate', item.id)"
          :class="[
            'w-full flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group',
            currentPage === item.id 
              ? 'bg-indigo-600/10 text-indigo-400 border border-indigo-500/20 shadow-[0_0_15px_rgba(79,70,229,0.1)]' 
              : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
          ]"
        >
          <!-- Simple Icon Placeholder since we might not have lucide-vue installed yet, or use text fallback -->
          <!-- Ideally we would use lucide-vue-next here, but task list said infrastructure is done. I'll use SVGs roughly -->
          <span class="mr-3 opacity-70 group-hover:opacity-100 transition-opacity">
            <svg v-if="item.id === 'dashboard'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
            <svg v-else-if="item.id === 'config'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>
            <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
          </span>
          {{ item.label }}
        </button>
      </nav>

      <!-- User/Status Footer -->
      <div class="p-4 border-t border-white/5 bg-slate-900/30">
         <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold ring-2 ring-white/10">
               {{ userInitials || 'G' }}
            </div>
            <div class="flex-1 min-w-0">
               <p class="text-sm font-medium text-white truncate">{{ userName || 'Guest User' }}</p>
               <p :class="['text-xs truncate', connectionStatus === 'connected' ? 'text-emerald-400' : 'text-slate-500']">
                  {{ connectionStatus === 'connected' ? 'Online' : 'Disconnected' }}
               </p>
            </div>
         </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 relative z-10 flex flex-col h-full overflow-hidden bg-[url('/bg-glow.svg')] bg-no-repeat bg-top bg-contain">
       <!-- Gradient blob for atmosphere -->
       <div class="absolute top-[-20%] left-[20%] w-[500px] h-[500px] bg-indigo-600/20 rounded-full blur-[120px] pointer-events-none"></div>
       <div class="absolute bottom-[-10%] right-[-10%] w-[400px] h-[400px] bg-emerald-600/10 rounded-full blur-[100px] pointer-events-none"></div>

       <div class="flex-1 overflow-y-auto overflow-x-hidden p-6 custom-scrollbar">
          <slot></slot>
       </div>
    </main>

  </div>
</template>
