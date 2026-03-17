<template>
  <div class="searchable-select" ref="wrapperRef">
    <button type="button" class="input input-sm flex items-center cursor-pointer text-left" @click="toggle" :class="{ 'text-muted': !selectedLabel }">
      <span class="flex-1 truncate">{{ selectedLabel || placeholder }}</span>
      <span v-if="modelValue" class="ml-1 text-muted hover:text-foreground" @click.stop="clear">&times;</span>
      <span v-else class="ml-1 text-muted">&#9662;</span>
    </button>
    <teleport to="body">
      <div v-if="open" class="searchable-select-dropdown" :style="dropdownStyle" ref="dropdownRef">
        <input
          ref="searchInputRef"
          v-model="searchText"
          class="input input-sm w-full mb-1"
          :placeholder="searchPlaceholder"
          @keydown.esc="open = false"
        />
        <div class="searchable-select-options">
          <button
            type="button"
            v-for="opt in filtered"
            :key="opt.id"
            class="searchable-select-option text-left w-full"
            :class="{ active: opt.id == modelValue }"
            @click="select(opt)"
          >
            <div class="truncate">{{ opt.label }}</div>
            <div v-if="opt.sublabel" class="text-xs text-muted truncate">{{ opt.sublabel }}</div>
          </button>
          <div v-if="!filtered.length" class="px-3 py-2 text-xs text-muted text-center">无匹配项</div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'

const props = defineProps({
  options: { type: Array, default: () => [] },
  modelValue: { type: [String, Number], default: '' },
  placeholder: { type: String, default: '请选择' },
  searchPlaceholder: { type: String, default: '搜索...' }
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const searchText = ref('')
const wrapperRef = ref(null)
const searchInputRef = ref(null)
const dropdownRef = ref(null)
const dropdownStyle = ref({})

const selectedLabel = computed(() => {
  const opt = props.options.find(o => o.id == props.modelValue)
  return opt ? opt.label : ''
})

const filtered = computed(() => {
  if (!searchText.value) return props.options
  const kw = searchText.value.toLowerCase()
  return props.options.filter(o =>
    (o.label || '').toLowerCase().includes(kw) ||
    (o.sublabel || '').toLowerCase().includes(kw)
  )
})

/** 计算下拉面板位置（固定定位，脱离 overflow 容器） */
const updatePosition = () => {
  if (!wrapperRef.value) return
  const rect = wrapperRef.value.getBoundingClientRect()
  dropdownStyle.value = {
    position: 'fixed',
    top: rect.bottom + 2 + 'px',
    left: rect.left + 'px',
    width: rect.width + 'px',
    zIndex: 9999
  }
}

const toggle = () => {
  open.value = !open.value
  if (open.value) {
    searchText.value = ''
    updatePosition()
    nextTick(() => searchInputRef.value?.focus())
  }
}

const select = (opt) => {
  emit('update:modelValue', opt.id)
  open.value = false
}

const clear = () => {
  emit('update:modelValue', '')
}

const onClickOutside = (e) => {
  if (!wrapperRef.value?.contains(e.target) && !dropdownRef.value?.contains(e.target)) {
    open.value = false
  }
}

/** 仅在下拉打开时注册全局监听器，关闭时移除 */
watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener('click', onClickOutside)
    window.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)
  } else {
    document.removeEventListener('click', onClickOutside)
    window.removeEventListener('scroll', updatePosition, true)
    window.removeEventListener('resize', updatePosition)
  }
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
  window.removeEventListener('scroll', updatePosition, true)
  window.removeEventListener('resize', updatePosition)
})
</script>

<style scoped>
.searchable-select {
  position: relative;
}
</style>

<style>
/* 下拉面板通过 teleport 渲染到 body，不能用 scoped */
.searchable-select-dropdown {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.searchable-select-options {
  max-height: 200px;
  overflow-y: auto;
}
.searchable-select-option {
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.searchable-select-option:hover {
  background: var(--color-elevated);
}
.searchable-select-option.active {
  background: var(--color-primary-muted);
}
</style>
