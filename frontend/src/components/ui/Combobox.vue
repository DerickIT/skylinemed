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
  labelField: { type: String, default: 'name' }
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
  // If query exactly matches selected item, show all (so we can switch) 
  // OR show filtered? Standard autocomplete keeps filtering.
  // But if I just clicked an item, I want to see it selected.
  // Let's filter simply.
  
  // Optimization: If text matches selected ID's label exactly, maybe show all?
  // Let's stick to standard filter.
  const query = searchQuery.value.toLowerCase()
  return props.options.filter(item => 
    String(item[props.labelField] || '').toLowerCase().includes(query)
  )
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
    // Reset query to match modelValue if no valid selection was made?
    // Or allow custom text? Requirement says "select", so restrict to options.
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
    <label v-if="label" class="block text-xs text-slate-400 mb-1.5 uppercase">{{ label }}</label>
    <div class="relative">
        <input 
            type="text"
            v-model="searchQuery"
            @input="handleInput"
            @focus="handleFocus"
            @keydown="onKeyDown"
            :placeholder="placeholder || '请选择...'"
            :disabled="disabled"
            class="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500/50 outline-none text-slate-200 placeholder-slate-500 transition-all"
            :class="{'cursor-not-allowed opacity-50': disabled}"
        />
        <!-- Chevron Icon -->
        <div class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500">
             <svg v-if="loading" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
             <svg v-else class="h-4 w-4 transition-transform duration-200" :class="{'rotate-180': isOpen}" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </div>
    </div>

    <!-- Dropdown -->
    <Transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="transform scale-95 opacity-0"
      enter-to-class="transform scale-100 opacity-100"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="transform scale-100 opacity-100"
      leave-to-class="transform scale-95 opacity-0"
    >
        <div v-if="isOpen" class="absolute z-[100] w-full mt-1 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-lg shadow-2xl max-h-60 overflow-y-auto custom-scrollbar ring-1 ring-black/5">
            <ul v-if="filteredOptions.length > 0" class="py-1">
                <li 
                    v-for="(option, index) in filteredOptions" 
                    :key="option[keyField]"
                    @click="selectOption(option)"
                    @mousemove="highlightIndex = index"
                    :class="[
                        'px-4 py-2.5 text-sm cursor-pointer transition-colors border-l-2',
                        index === highlightIndex ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500' : 'text-slate-300 border-transparent hover:bg-white/5'
                    ]"
                >
                    {{ option[labelField] }}
                </li>
            </ul>
            <div v-else class="px-4 py-3 text-sm text-slate-500 text-center">
                {{ searchQuery ? '无匹配结果' : '无数据' }}
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
  @apply bg-slate-700 rounded;
}
</style>
