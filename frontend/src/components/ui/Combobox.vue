<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: [String, Number],
  options: { type: Array, default: () => [] }, // Expects { id, name } objects by default
  placeholder: String,
  label: String,
  loading: Boolean,
  disabled: Boolean,
  keyField: { type: String, default: 'id' },
  labelField: { type: String, default: 'name' },
  additionalSearchFields: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:modelValue', 'change'])

const isOpen = ref(false)
const searchQuery = ref('')
const containerRef = ref(null)
const highlightIndex = ref(-1)

// Initialize query from modelValue
watch(() => props.modelValue, (val) => {
  const found = props.options.find(o => o[props.keyField] === val)
  if (found) {
    searchQuery.value = found[props.labelField]
  } else if (!val) {
    searchQuery.value = ''
  }
}, { immediate: true })

// Also watch options to update query if modelValue exists but options were loading
watch(() => props.options, (newOptions) => {
  if (props.modelValue && newOptions.length > 0) {
    const found = newOptions.find(o => o[props.keyField] === props.modelValue)
    if (found) {
      searchQuery.value = found[props.labelField]
    }
  }
})

const filteredOptions = computed(() => {
  if (!searchQuery.value) return props.options
  
  const query = searchQuery.value.toLowerCase()
  return props.options.filter(item => {
    // Check label
    if (String(item[props.labelField] || '').toLowerCase().includes(query)) return true
    // Check additional fields (e.g. pinyin, match code)
    if (props.additionalSearchFields.length > 0) {
        return props.additionalSearchFields.some(field => 
            String(item[field] || '').toLowerCase().includes(query)
        )
    }
    return false
  })
})

const handleInput = () => {
  isOpen.value = true
  highlightIndex.value = 0
  // If user clears input, we might want to clear model?
  if (!searchQuery.value) {
    emit('update:modelValue', '')
    emit('change', null)
  }
}

const handleClear = (e) => {
    e.stopPropagation()
    searchQuery.value = ''
    emit('update:modelValue', '')
    emit('change', null)
    isOpen.value = true // Keep open to show all options
}

const handleFocus = () => {
    if (props.disabled) return
    isOpen.value = true
    // If empty, show all.
}

const selectOption = (option) => {
  emit('update:modelValue', option[props.keyField])
  emit('change', option)
  searchQuery.value = option[props.labelField]
  isOpen.value = false
}

// Click Outside Logic
const handleClickOutside = (e) => {
  if (containerRef.value && !containerRef.value.contains(e.target)) {
    isOpen.value = false
    // Reset query to match modelValue if no valid selection was made
    const found = props.options.find(o => o[props.keyField] === props.modelValue)
    if (found) {
      searchQuery.value = found[props.labelField]
    } else {
      searchQuery.value = '' // Clear if invalid
    }
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

// Keyboard Nav
const onKeyDown = (e) => {
    if (!isOpen.value) {
        if (e.key === 'ArrowDown' || e.key === 'Enter') isOpen.value = true
        return
    }
    
    switch(e.key) {
        case 'ArrowDown':
            e.preventDefault()
            if (highlightIndex.value < filteredOptions.value.length - 1) highlightIndex.value++
            break
        case 'ArrowUp':
            e.preventDefault()
            if (highlightIndex.value > 0) highlightIndex.value--
            break
        case 'Enter':
            e.preventDefault()
            if (highlightIndex.value >= 0 && filteredOptions.value[highlightIndex.value]) {
                selectOption(filteredOptions.value[highlightIndex.value])
            }
            break
        case 'Escape':
            isOpen.value = false
            break
        case 'Tab':
            isOpen.value = false
            break
    }
}

// ensure highlight is reset when list changes
watch(filteredOptions, () => {
    highlightIndex.value = 0
})

</script>

<template>
  <div ref="containerRef" class="relative group/combo">
    <label v-if="label" class="block text-[10px] font-black uppercase text-slate-400 tracking-[0.3em] mb-3 ml-1 font-display">{{ label }}</label>
    
    <div class="relative">
      <input
        type="text"
        v-model="searchQuery"
        @input="handleInput"
        @focus="handleFocus"
        @keydown="onKeyDown"
        :placeholder="placeholder || '请通过关键字搜索锁定目标...'"
        :disabled="disabled"
        class="w-full bg-slate-50 border-2 border-slate-100 rounded-[28px] px-8 py-5 text-base focus:ring-8 focus:ring-blue-500/5 focus:border-blue-500 outline-none hover:bg-white transition-all text-slate-900 font-display font-black placeholder-slate-300 disabled:opacity-50 disabled:cursor-not-allowed pr-14 shadow-sm"
      />
      
      <!-- Icons -->
      <div class="absolute right-6 top-1/2 -translate-y-1/2 flex items-center gap-2">
        <div v-if="loading" class="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <div v-else-if="modelValue && !disabled" @click="handleClear" class="cursor-pointer text-slate-300 hover:text-red-500 p-1 transition-colors">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12" /></svg>
        </div>
        <div v-else class="text-slate-300 group-hover/combo:text-blue-500 transition-colors pointer-events-none">
          <svg v-if="isOpen" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7" /></svg>
          <svg v-else class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7" /></svg>
        </div>
      </div>
    </div>

    <!-- Dropdown -->
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="opacity-0 translate-y-4 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="opacity-100 translate-y-0 scale-100"
      leave-to-class="opacity-0 translate-y-4 scale-95"
    >
      <div v-if="isOpen && !disabled" class="absolute z-50 w-full mt-4 bg-white/90 backdrop-blur-xl border border-slate-100 rounded-[32px] shadow-2xl shadow-slate-200/60 overflow-hidden">
        <div class="max-h-[320px] overflow-y-auto custom-scrollbar p-2">
          <div v-if="filteredOptions.length === 0" class="py-12 text-center text-[10px] font-black text-slate-400 uppercase tracking-widest italic font-display">
            {{ searchQuery ? 'No Matching Targets' : 'System Ready / Idle' }}
          </div>
          <ul v-else>
            <li
              v-for="(option, index) in filteredOptions"
              :key="option[keyField]"
              @click="selectOption(option)"
              @mousemove="highlightIndex = index"
              :class="[
                'w-full text-left px-6 py-4 rounded-2xl text-sm font-bold transition-all flex items-center justify-between group/item cursor-pointer',
                index === highlightIndex ? 'bg-slate-950 text-white translate-x-1' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              ]"
            >
              <span class="font-display">{{ option[labelField] }}</span>
              <div v-if="modelValue === option[keyField]" class="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_10px_#3B82F6]"></div>
              <svg v-else class="w-5 h-5 opacity-0 group-hover/item:opacity-100 transition-opacity text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
            </li>
          </ul>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  @apply bg-slate-200 rounded-full;
}
</style>
