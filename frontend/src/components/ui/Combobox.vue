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
  <div ref="containerRef" class="relative group">
    <label v-if="label" class="block text-[10px] font-black uppercase text-slate-400 tracking-widest mb-2">{{ label }}</label>
    
    <div class="relative">
      <input
        type="text"
        v-model="searchQuery"
        @input="handleInput"
        @focus="handleFocus"
        @keydown="onKeyDown"
        :placeholder="placeholder || '请选择...'"
        :disabled="disabled"
        class="w-full bg-slate-50 border border-slate-200 rounded-2xl px-5 py-3.5 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none hover:bg-white transition-all text-slate-700 font-medium placeholder-slate-400 disabled:opacity-50 disabled:cursor-not-allowed pr-10"
      />
      
      <div v-if="loading" class="absolute right-4 top-1/2 -translate-y-1/2">
        <svg class="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
      <div v-else-if="modelValue && !disabled" @click="handleClear" class="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer text-slate-300 hover:text-slate-500 p-1">
         <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
      </div>
      <div v-else class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
         <svg class="w-4 h-4 transition-transform group-hover:scale-110" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
      </div>
    </div>

    <!-- Dropdown -->
    <Transition name="fade-up">
      <div v-if="isOpen && !disabled" class="absolute z-50 w-full mt-2 bg-white rounded-2xl shadow-xl border border-slate-100 max-h-60 overflow-y-auto custom-scrollbar p-1">
        <ul v-if="filteredOptions.length > 0">
           <li 
             v-for="(option, index) in filteredOptions" 
             :key="option[keyField]"
             @click="selectOption(option)"
             @mousemove="highlightIndex = index"
             :class="['px-4 py-2.5 rounded-xl cursor-pointer text-sm font-medium transition-colors flex justify-between items-center', 
               index === highlightIndex ? 'bg-blue-50 text-blue-600' : 'text-slate-600 hover:bg-slate-50']"
           >
              <span>{{ option[labelField] }}</span>
              <svg v-if="modelValue === option[keyField]" class="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
           </li>
        </ul>
        <div v-else class="px-4 py-8 text-center text-xs text-slate-400 font-bold uppercase tracking-widest">
            {{ searchQuery ? '无匹配结果' : '无数据' }}
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.fade-up-enter-active, .fade-up-leave-active {
  transition: all 0.2s ease-out;
}
.fade-up-enter-from, .fade-up-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  @apply bg-slate-200 rounded-full;
}
</style>
