<template>
  <div class="inline-flex" ref="btnRef">
    <button @click.stop="toggle" class="col-selector-btn" title="列设置">
      <MoreVertical :size="14" />
    </button>
    <Teleport to="body">
      <div v-if="open" ref="menuRef" class="col-menu-dropdown" :style="menuStyle" @click.stop>
        <template v-for="(label, key) in labels" :key="key">
          <div v-if="key !== pinned"
            @click="$emit('toggle', key)"
            class="col-menu-item">
            <span class="w-4 text-center text-[13px]">{{ visible[key] ? '✓' : '' }}</span>
            <span>{{ label }}</span>
          </div>
        </template>
        <div class="border-t mt-1 pt-1">
          <div @click="$emit('reset')" class="col-menu-item col-menu-reset">重置列</div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { MoreVertical } from 'lucide-vue-next'

defineProps({
  labels: { type: Object, required: true },
  visible: { type: Object, required: true },
  pinned: { type: String, default: '' },
})

defineEmits(['toggle', 'reset'])

const open = ref(false)
const btnRef = ref(null)
const menuRef = ref(null)
const menuStyle = ref({})

const toggle = () => {
  open.value = !open.value
}

const updatePos = async () => {
  await nextTick()
  if (!btnRef.value || !menuRef.value) return
  const r = btnRef.value.getBoundingClientRect()
  const mw = menuRef.value.offsetWidth
  const mh = menuRef.value.offsetHeight
  const vh = window.innerHeight
  const vw = window.innerWidth
  const margin = 8

  // 垂直定位：优先下方，不够则上方，都不够则贴顶+滚动
  let top
  const spaceBelow = vh - r.bottom
  const spaceAbove = r.top
  if (spaceBelow >= mh + margin) {
    top = r.bottom + 4
  } else if (spaceAbove >= mh + margin) {
    top = r.top - mh - 4
  } else {
    top = margin
  }
  // 强制不超出视口
  top = Math.max(margin, Math.min(top, vh - mh - margin))

  // 水平定位：右对齐按钮，不超出左右边界
  const left = Math.min(Math.max(margin, r.right - mw), vw - mw - margin)

  // 最大高度 = 视口 - 上下留白
  const maxH = vh - margin * 2

  menuStyle.value = { top: `${top}px`, left: `${left}px`, maxHeight: `${maxH}px` }
}

watch(open, v => { if (v) updatePos() })

const onDocClick = e => {
  if (open.value && btnRef.value && !btnRef.value.contains(e.target) && menuRef.value && !menuRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))
</script>

<style scoped>
.col-menu-dropdown {
  position: fixed;
  z-index: 50;
  background: var(--surface);
  border-radius: 8px;
  box-shadow: 0 4px 16px oklch(0 0 0 / 0.12), 0 1px 4px oklch(0 0 0 / 0.06);
  border: 1px solid var(--border);
  padding: 6px;
  min-width: 140px;
  user-select: none;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.col-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  user-select: none;
  transition: background 0.1s;
}
.col-menu-item:hover { background: var(--elevated); }
.col-menu-reset { color: var(--text-muted); }
</style>
