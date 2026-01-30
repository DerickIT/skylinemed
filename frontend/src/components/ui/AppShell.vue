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
  <div class="h-screen w-screen bg-slate-50 text-slate-600 flex overflow-hidden selection:bg-blue-500/20">
    
    <!-- Sidebar -->
    <aside class="w-72 bg-[#09090b] flex flex-col z-20 relative overflow-hidden group/sidebar shadow-2xl shadow-black/50">
      <!-- Texture overlay -->
      <div class="absolute inset-0 opacity-[0.03] pointer-events-none bg-[url('https://www.transparenttextures.com/patterns/asfalt-dark.png')]"></div>
      
      <!-- Logo Section -->
      <div class="h-24 flex flex-col justify-center px-8 relative z-10">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-2xl shadow-blue-500/40 border border-white/10 ring-4 ring-blue-500/10">
            <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </div>
          <div class="flex flex-col">
            <span class="font-display font-black text-xl tracking-tighter text-white leading-none">SkylineMed</span>
            <span class="text-[9px] font-black uppercase tracking-[0.3em] text-blue-500/80 mt-1">Intelligence Loop</span>
          </div>
        </div>
      </div>

      <!-- Navigation Content -->
      <nav class="flex-1 px-4 py-8 space-y-3 relative z-10">
        <div v-for="(item, index) in navItems" :key="item.id">
          <button 
            @click="$emit('navigate', item.id)"
            :class="[
              'w-full flex items-center gap-4 px-5 py-4 rounded-2xl transition-all duration-300 group/nav relative',
              currentPage === item.id 
                ? 'bg-white/5 border border-white/10 text-white shadow-2xl shadow-black/50' 
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.02]'
            ]"
          >
            <!-- Active Indicator Dot -->
            <div v-if="currentPage === item.id" class="absolute left-0 w-1.5 h-6 bg-blue-500 rounded-r-full shadow-[4px_0_15px_rgba(59,130,246,0.5)] transition-all"></div>
            
            <div :class="['p-2 rounded-xl transition-all duration-300', currentPage === item.id ? 'bg-blue-500/10 text-blue-400' : 'bg-transparent text-zinc-600 group-hover/nav:text-zinc-400']">
              <svg v-if="item.id === 'dashboard'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
              <svg v-else-if="item.id === 'config'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>
              <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
            </div>
            
            <span class="font-display font-bold text-sm tracking-wide">{{ item.label }}</span>
            
            <!-- Glow Effect on Active -->
            <div v-if="currentPage === item.id" class="absolute inset-0 bg-blue-500/5 blur-xl rounded-2xl pointer-events-none"></div>
          </button>
        </div>
      </nav>

      <!-- User/Status Footer -->
      <div class="p-6 mt-auto relative z-10">
         <div class="p-4 rounded-3xl bg-white/[0.03] border border-white/[0.05] backdrop-blur-md flex items-center gap-4 group/user cursor-pointer hover:bg-white/[0.05] transition-all">
            <div class="relative">
              <div class="w-10 h-10 rounded-2xl bg-zinc-800 flex items-center justify-center text-xs font-black text-white border border-white/5 transition-transform group-hover/user:scale-110">
                 {{ userInitials || 'G' }}
              </div>
              <div :class="['absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-[#09090b] shadow-lg', connectionStatus === 'connected' ? 'bg-emerald-500' : 'bg-zinc-600']"></div>
            </div>
            <div class="flex-1 min-w-0">
               <p class="text-xs font-black text-white truncate uppercase tracking-widest leading-none">{{ userName || 'Guest' }}</p>
               <p class="text-[9px] font-bold text-zinc-500 mt-1 uppercase tracking-tighter">{{ connectionStatus === 'connected' ? 'Secure Link Active' : 'Offline' }}</p>
            </div>
         </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 relative z-10 flex flex-col h-full overflow-hidden bg-slate-50">
       <!-- Decoration blobs -->
       <div class="absolute top-[-20%] left-[20%] w-[500px] h-[500px] bg-blue-100/50 rounded-full blur-[120px] pointer-events-none mix-blend-multiply"></div>
       <div class="absolute bottom-[-10%] right-[-10%] w-[400px] h-[400px] bg-indigo-100/50 rounded-full blur-[100px] pointer-events-none mix-blend-multiply"></div>

       <div class="flex-1 overflow-y-auto overflow-x-hidden p-10 custom-scrollbar relative z-10 h-full">
          <slot></slot>
       </div>
    </main>

  </div>
</template>
