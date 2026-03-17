<!--
  商品搜索行 - 工作台表格末尾的内联搜索
  输入关键词后弹出下拉面板，每个商品一行标题+横排仓位badge
  点击仓位 badge 后 emit add-item 事件
-->
<template>
  <tr>
    <td class="px-3 py-1.5 text-center text-muted text-sm">+</td>
    <td class="px-3 py-1.5">
      <div ref="wrapperRef" class="relative">
        <input
          ref="searchInputRef"
          v-model="searchText"
          class="input text-sm w-full"
          placeholder="搜索商品..."
          aria-label="搜索商品"
          @focus="showDropdown = true"
          @keydown.esc="closeDropdown"
          @keydown.down.prevent="navigateDown"
          @keydown.up.prevent="navigateUp"
          @keydown.enter.prevent="selectHighlighted"
          autocomplete="off"
        >
        <teleport to="body">
          <div
            v-if="showDropdown && debouncedSearch && searchResults.length"
            class="product-search-dropdown"
            :style="dropdownStyle"
            ref="dropdownRef"
            role="listbox"
          >
            <div
              v-for="group in searchResults"
              :key="group.product.id"
              class="px-3 py-2 border-b last:border-b-0"
            >
              <!-- 商品标题行 -->
              <div class="flex items-center gap-1.5 mb-1.5">
                <span class="font-medium text-sm">{{ group.product.name }}</span>
                <span class="text-muted font-mono text-xs">{{ group.product.sku }}</span>
                <span v-if="group.product.brand" class="text-muted text-xs">&middot; {{ group.product.brand }}</span>
                <span class="ml-auto text-primary font-mono text-xs">&yen;{{ group.product.retail_price }}</span>
              </div>
              <!-- 仓位 badge 横排 -->
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="row in group.rows"
                  :key="row.key"
                  type="button"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs border transition-colors"
                  :class="badgeClass(row)"
                  :disabled="row.disabled"
                  :aria-label="'选择 ' + row.warehouse_name + '-' + row.location_code + ' 库存:' + row.available_qty"
                  @click="!row.disabled && selectRow(group.product, row)"
                  @mouseenter="highlightIndex = row.flatIndex"
                >
                  <span
                    class="w-1.5 h-1.5 rounded-full shrink-0"
                    :style="{ background: `var(--color-${row.is_virtual ? 'purple-emphasis' : (locationColorCssVarMap[row.location_color] || 'info-emphasis')})` }"
                  ></span>
                  <span>{{ row.warehouse_name }}-{{ row.location_code }}</span>
                  <span class="font-mono tabular-nums" :class="row.available_qty > 0 ? 'text-success' : 'text-muted'">:{{ row.available_qty }}</span>
                </button>
              </div>
            </div>
          </div>
          <!-- 关闭遮罩 -->
          <div v-if="showDropdown && debouncedSearch" @click="closeDropdown" class="fixed inset-0" style="z-index: 40"></div>
        </teleport>
      </div>
    </td>
    <td colspan="99"></td>
  </tr>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { fuzzyMatchAny } from '../../../utils/helpers'
import { DEFAULT_LOCATION_COLOR, locationColorCssVarMap } from '../../../utils/constants'

const props = defineProps({
  products: { type: Array, required: true },
  orderType: { type: String, required: true }
})

const emit = defineEmits(['add-item'])

const searchText = ref('')
const debouncedSearch = ref('')
const showDropdown = ref(false)
const highlightIndex = ref(-1)
let _debounceTimer = null
const wrapperRef = ref(null)
const searchInputRef = ref(null)
const dropdownRef = ref(null)
const dropdownStyle = ref({})

/** 搜索结果：按商品分组，每组下列出仓库/仓位行 */
const searchResults = computed(() => {
  if (!debouncedSearch.value) return []
  const kw = debouncedSearch.value
  const filtered = (props.products || []).filter(p =>
    fuzzyMatchAny([p.sku, p.name, p.brand, p.category], kw)
  )

  let flatIndex = 0
  return filtered.slice(0, 10).map(product => {
    const rows = (product.stocks || [])
      .filter(s => {
        if (props.orderType === 'CONSIGN_SETTLE') return s.is_virtual
        return !s.is_virtual
      })
      .map(s => {
        const available = s.available_qty ?? s.quantity
        const disabled = props.orderType !== 'CREDIT' && available <= 0
        return {
          key: `${s.warehouse_id}-${s.location_id}`,
          warehouse_id: s.warehouse_id,
          warehouse_name: s.warehouse_name || '',
          location_id: s.location_id,
          location_code: s.location_code || '-',
          location_color: s.location_color || DEFAULT_LOCATION_COLOR,
          available_qty: available,
          is_virtual: !!s.is_virtual,
          disabled,
          flatIndex: flatIndex++
        }
      })
    return { product, rows }
  }).filter(g => g.rows.length > 0)
})

/** badge 样式 */
const badgeClass = (row) => {
  if (row.disabled) return 'opacity-30 cursor-not-allowed border-transparent bg-elevated'
  if (highlightIndex.value === row.flatIndex) return 'border-primary bg-info-subtle cursor-pointer'
  return 'border-line hover:border-primary hover:bg-info-subtle cursor-pointer'
}

/** 所有可选行（用于键盘导航） */
const allRows = computed(() => {
  const rows = []
  searchResults.value.forEach(g => {
    g.rows.forEach(r => {
      if (!r.disabled) rows.push({ product: g.product, row: r })
    })
  })
  return rows
})

const updatePosition = () => {
  if (!wrapperRef.value) return
  const rect = wrapperRef.value.getBoundingClientRect()
  const maxH = Math.min(400, window.innerHeight - rect.bottom - 10)
  dropdownStyle.value = {
    position: 'fixed',
    top: rect.bottom + 2 + 'px',
    left: rect.left + 'px',
    width: Math.max(rect.width, 400) + 'px',
    maxHeight: maxH + 'px',
    overflowY: 'auto',
    zIndex: 50
  }
}

const closeDropdown = () => {
  showDropdown.value = false
  highlightIndex.value = -1
}

const selectRow = (product, row) => {
  emit('add-item', product, row)
  searchText.value = ''
  closeDropdown()
  nextTick(() => searchInputRef.value?.focus())
}

const navigateDown = () => {
  if (!allRows.value.length) return
  const currentIdx = allRows.value.findIndex(r => r.row.flatIndex === highlightIndex.value)
  const nextIdx = currentIdx < allRows.value.length - 1 ? currentIdx + 1 : 0
  highlightIndex.value = allRows.value[nextIdx].row.flatIndex
}

const navigateUp = () => {
  if (!allRows.value.length) return
  const currentIdx = allRows.value.findIndex(r => r.row.flatIndex === highlightIndex.value)
  const prevIdx = currentIdx > 0 ? currentIdx - 1 : allRows.value.length - 1
  highlightIndex.value = allRows.value[prevIdx].row.flatIndex
}

const selectHighlighted = () => {
  const found = allRows.value.find(r => r.row.flatIndex === highlightIndex.value)
  if (found) selectRow(found.product, found.row)
}

watch(showDropdown, (isOpen) => {
  if (isOpen) {
    updatePosition()
    document.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)
  } else {
    document.removeEventListener('scroll', updatePosition, true)
    window.removeEventListener('resize', updatePosition)
  }
})

watch(searchText, (val) => {
  highlightIndex.value = -1
  clearTimeout(_debounceTimer)
  if (val) {
    showDropdown.value = true
    _debounceTimer = setTimeout(() => {
      debouncedSearch.value = val
      nextTick(updatePosition)
    }, 150)
  } else {
    debouncedSearch.value = ''
  }
})

onUnmounted(() => {
  clearTimeout(_debounceTimer)
  document.removeEventListener('scroll', updatePosition, true)
  window.removeEventListener('resize', updatePosition)
})
</script>

<style>
.product-search-dropdown {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}
</style>
