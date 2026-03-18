# 销售模块工作台化重构 - 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将销售页面从"左右分栏购物车模式"重构为"全页工作台填表模式"，商品通过表格末尾空行内联搜索添加，搜索下拉按仓库/仓位展开可直接点选预填仓库。

**Architecture:** 删除 ProductSelector + ShoppingCart + CartItem 三个组件，新建 SalesToolbar + SalesWorksheet + WorksheetRow + ProductSearchRow + SalesFooter 五个组件。SalesView 保持瘦容器角色。useSalesCart composable 新增 `addFromSearch` 和 `populateReturnItems` 方法。后端 API 不变。

**Tech Stack:** Vue 3 Composition API + Tailwind CSS 4 + 项目现有 UI 类名体系

**设计文档：** `docs/plans/2026-03-17-sales-worksheet-redesign.md`

---

### Task 1: 修改 useSalesCart.js — 新增方法

**Files:**
- Modify: `src/composables/useSalesCart.js`

**Step 1: 新增 `addFromSearch` 方法和 `populateReturnItems` 方法**

在 `clearCart` 之前，新增以下两个方法：

```javascript
/**
 * 从搜索下拉添加商品到购物车（新工作台模式用）
 * @param {Object} product - 商品对象（含 id/name/sku/retail_price/cost_price/stocks）
 * @param {Object} stockRow - 搜索下拉中选中的仓库行
 * @param {string} orderType - 订单类型
 * @param {Object} appStore - 全局应用 store
 */
const addFromSearch = (product, stockRow, orderType, appStore) => {
  // 非账期模式检查库存
  if (orderType !== 'CREDIT' && stockRow.available_qty <= 0) {
    appStore.showToast('库存不足', 'error')
    return
  }

  // 检查是否已有相同商品+仓库+仓位的行
  const existing = cart.value.find(
    c => c.product_id === product.id &&
         c.warehouse_id == stockRow.warehouse_id &&
         c.location_id == stockRow.location_id
  )

  if (existing) {
    existing.quantity++
    return existing
  }

  const item = {
    _id: ++_cartIdCounter,
    product_id: product.id,
    name: product.name,
    sku: product.sku || '',
    unit_price: product.retail_price,
    cost_price: product.cost_price || 0,
    quantity: 1,
    warehouse_id: stockRow.warehouse_id,
    warehouse_name: stockRow.warehouse_name || '',
    location_id: stockRow.location_id,
    location_code: stockRow.location_code || '',
    location_color: stockRow.location_color || 'blue',
    is_virtual_stock: !!stockRow.is_virtual,
    stocks: product.stocks || []
  }
  cart.value.push(item)
  return item
}

/**
 * 退货模式：从原始订单填充可退商品到购物车
 * @param {Object} orderData - 原始订单详情（含 items）
 * @param {import('vue').Ref<Array>} products - 全部商品列表 ref
 */
const populateReturnItems = (orderData, products) => {
  cart.value = []
  if (!orderData?.items) return
  orderData.items.forEach(item => {
    const availableQty = item.available_return_quantity || 0
    if (availableQty <= 0) return
    const product = products.value.find(p => p.id === item.product_id)
    if (!product) return
    cart.value.push({
      _id: ++_cartIdCounter,
      product_id: item.product_id,
      name: product.name,
      sku: product.sku || '',
      unit_price: Math.abs(item.unit_price),
      cost_price: product.cost_price || 0,
      quantity: 0,
      max_return_qty: availableQty,
      original_quantity: Math.abs(item.quantity),
      returned_quantity: item.returned_quantity || 0,
      warehouse_id: '',
      warehouse_name: '',
      location_id: '',
      location_code: '',
      location_color: 'blue',
      stocks: product.stocks || []
    })
  })
}
```

**Step 2: 更新 return 对象**

在 `return { ... }` 中新增 `addFromSearch` 和 `populateReturnItems`。

**Step 3: 验证**

Run: `npm run build`
Expected: 编译成功（新方法未使用不影响构建）

**Step 4: Commit**

```bash
git add src/composables/useSalesCart.js
git commit -m "feat(sales): 购物车composable新增addFromSearch和populateReturnItems方法"
```

---

### Task 2: 创建 SalesToolbar.vue — 顶栏元信息

**Files:**
- Create: `src/components/business/sales/SalesToolbar.vue`

**Step 1: 创建组件**

```vue
<!--
  销售工作台顶栏 - 页面标题 + 订单元信息
  显示订单类型、客户选择、员工选择、退货关联订单搜索
-->
<template>
  <div>
    <h2 class="text-lg font-bold mb-4">销售管理</h2>

    <div class="flex flex-wrap gap-2 mb-4">
      <!-- 订单类型 -->
      <select
        :value="orderType"
        @change="$emit('update:orderType', $event.target.value)"
        class="input w-auto text-sm"
      >
        <option value="CASH">现款</option>
        <option value="CREDIT">账期</option>
        <option value="CONSIGN_OUT">寄售调拨</option>
        <option value="CONSIGN_SETTLE">寄售结算</option>
        <option value="RETURN">退货</option>
      </select>

      <!-- 客户选择 -->
      <div class="w-48">
        <SearchableSelect
          :options="customerOptions"
          :modelValue="customerId"
          @update:modelValue="$emit('update:customerId', $event)"
          :placeholder="'选客户(' + (needCustomer ? '必选' : '可选') + ')'"
          searchPlaceholder="搜索客户名/电话"
        />
      </div>

      <!-- 员工选择 -->
      <select
        :value="employeeId"
        @change="$emit('update:employeeId', $event.target.value)"
        class="input w-auto text-sm"
      >
        <option value="">选业务员(可选)</option>
        <option v-for="s in employees" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>

      <!-- 退货模式：关联订单搜索 -->
      <div v-if="orderType === 'RETURN'" class="relative w-56">
        <input
          :value="returnOrderSearch"
          @input="$emit('update:returnOrderSearch', $event.target.value); $emit('search-return-orders')"
          @focus="$emit('update:returnOrderDropdown', true)"
          class="input text-sm w-full"
          placeholder="搜索关联订单 *"
          autocomplete="off"
        >
        <div
          v-if="returnOrderDropdown && filteredReturnOrders.length"
          class="absolute top-full mt-1 w-full bg-surface border rounded shadow-lg max-h-60 overflow-y-auto"
          style="z-index: 30"
        >
          <button
            v-for="o in filteredReturnOrders"
            :key="o.id"
            type="button"
            @click="$emit('select-return-order', o)"
            class="w-full text-left px-2 py-2 hover:bg-elevated cursor-pointer border-b"
          >
            <div class="font-medium text-sm">{{ o.order_no }}</div>
            <div class="text-xs text-muted">{{ o.customer_name }} &middot; {{ o.created_at.split('T')[0] }} &middot; &yen;{{ o.total_amount }}</div>
          </button>
        </div>
        <div v-if="returnOrderDropdown" @click="$emit('update:returnOrderDropdown', false)" class="fixed inset-0" style="z-index: 20"></div>
      </div>

      <!-- 退货关联订单提示 -->
      <div
        v-if="orderType === 'RETURN' && selectedReturnOrder"
        class="text-sm px-2 py-1.5 bg-info-subtle rounded border border-primary text-primary flex items-center"
      >
        <span class="font-medium">退货订单：</span>{{ selectedReturnOrder.order_no }} - {{ selectedReturnOrder.customer_name }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SearchableSelect from '../../common/SearchableSelect.vue'

const props = defineProps({
  orderType: String,
  customerId: [String, Number],
  employeeId: [String, Number],
  customers: Array,
  employees: Array,
  needCustomer: Boolean,
  returnOrderSearch: String,
  returnOrderDropdown: Boolean,
  filteredReturnOrders: Array,
  selectedReturnOrder: Object
})

defineEmits([
  'update:orderType', 'update:customerId', 'update:employeeId',
  'update:returnOrderSearch', 'update:returnOrderDropdown',
  'search-return-orders', 'select-return-order'
])

const customerOptions = computed(() =>
  (props.customers || []).map(c => ({
    id: c.id,
    label: c.name,
    sublabel: c.phone || ''
  }))
)
</script>
```

**Step 2: Commit**

```bash
git add src/components/business/sales/SalesToolbar.vue
git commit -m "feat(sales): 创建SalesToolbar顶栏组件"
```

---

### Task 3: 创建 WorksheetRow.vue — 数据行

**Files:**
- Create: `src/components/business/sales/WorksheetRow.vue`

**Step 1: 创建组件**

```vue
<!--
  工作台数据行 - 单个商品的可编辑行
  直接修改 item 的响应式属性（unit_price/quantity/warehouse_id/location_id）
  仅 emit 删除和拆分操作（需要父组件协调）
-->
<template>
  <tr class="hover:bg-elevated">
    <!-- 序号 -->
    <td class="px-3 py-2.5 text-center text-muted text-xs">{{ index + 1 }}</td>

    <!-- 商品 -->
    <td class="px-3 py-2.5">
      <div class="font-medium text-sm">{{ item.name }}</div>
      <div class="text-xs text-muted font-mono mt-0.5 md-hide">{{ item.sku }}</div>
    </td>

    <!-- 数量 -->
    <td class="px-3 py-2.5">
      <div class="inline-flex items-center gap-1">
        <button
          @click="handleDecrement"
          class="w-6 h-6 rounded border text-xs hover:bg-elevated flex items-center justify-center"
        >-</button>
        <input
          v-model.number="item.quantity"
          type="number"
          :min="minQty"
          class="input input-sm w-14 text-center"
          @blur="item.quantity = Math.max(minQty, Math.floor(item.quantity) || minQty)"
        >
        <button
          @click="handleIncrement"
          class="w-6 h-6 rounded border text-xs hover:bg-elevated flex items-center justify-center"
        >+</button>
      </div>
      <div v-if="orderType === 'RETURN' && item.max_return_qty" class="text-xs text-warning mt-0.5">
        最多可退: {{ item.max_return_qty }}
      </div>
    </td>

    <!-- 单价 -->
    <td class="px-3 py-2.5">
      <input
        v-model.number="item.unit_price"
        type="number"
        step="0.01"
        class="input input-sm w-20 text-right"
      >
    </td>

    <!-- 成本价（需要 finance 权限） -->
    <td v-if="showCost" class="px-3 py-2.5 text-right text-secondary text-sm md-hide">
      &yen;{{ item.cost_price || '-' }}
    </td>

    <!-- 仓库 -->
    <td class="px-3 py-2.5">
      <template v-if="isLocked">
        <span :class="item.is_virtual_stock ? 'badge badge-purple text-xs' : 'text-sm'">
          {{ item.warehouse_name || '-' }}
        </span>
      </template>
      <template v-else>
        <select
          v-model="item.warehouse_id"
          @change="onWarehouseChange"
          class="input input-sm text-xs w-full"
        >
          <option value="">选择仓库 *</option>
          <option
            v-for="w in physicalWarehouses"
            :key="w.id"
            :value="w.id"
          >{{ w.name }} (可用: {{ getWarehouseStock(w.id) }})</option>
        </select>
        <div v-if="item.warehouse_id && item.location_id" class="text-xs mt-0.5"
          :class="availableStock >= item.quantity ? 'text-success' : 'text-error'"
        >库存: {{ availableStock }}</div>
      </template>
    </td>

    <!-- 仓位 -->
    <td class="px-3 py-2.5 md-hide">
      <template v-if="isLocked">
        <span v-if="item.location_code" :class="`badge badge-${item.location_color || 'blue'} text-xs`">
          {{ item.location_code }}
        </span>
        <span v-else class="text-muted text-xs">-</span>
      </template>
      <template v-else>
        <select
          v-model="item.location_id"
          @change="onLocationChange"
          class="input input-sm text-xs w-full"
          :disabled="!item.warehouse_id"
        >
          <option value="">{{ item.warehouse_id ? '选仓位 *' : '先选仓库' }}</option>
          <option
            v-for="loc in itemLocations"
            :key="loc.id"
            :value="loc.id"
          >{{ loc.code }} (可用: {{ getLocationStock(loc.id) }})</option>
        </select>
      </template>
    </td>

    <!-- 小计 -->
    <td class="px-3 py-2.5 text-right text-primary font-semibold text-sm font-mono">
      &yen;{{ lineTotal }}
    </td>

    <!-- 操作 -->
    <td class="px-3 py-2.5 text-center">
      <div class="flex gap-1 justify-center">
        <button
          v-if="showDuplicate"
          @click="$emit('duplicate', index)"
          class="w-6 h-6 rounded-full bg-info-subtle text-primary text-xs font-bold flex items-center justify-center hover:opacity-80"
          title="拆分到其他仓库"
        >+</button>
        <button
          @click="$emit('remove', index)"
          class="w-6 h-6 rounded-full bg-error-subtle text-error text-xs font-bold flex items-center justify-center hover:opacity-80"
          title="删除"
        >&times;</button>
      </div>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useWarehousesStore } from '../../../stores/warehouses'

const props = defineProps({
  item: Object,
  index: Number,
  orderType: String,
  warehouses: Array,
  showCost: Boolean
})

defineEmits(['remove', 'duplicate'])

const appStore = useAppStore()
const warehousesStore = useWarehousesStore()

const minQty = computed(() => props.orderType === 'RETURN' ? 0 : 1)
const isLocked = computed(() => props.orderType === 'CONSIGN_SETTLE')
const showDuplicate = computed(() => !['RETURN', 'CONSIGN_SETTLE'].includes(props.orderType))

const physicalWarehouses = computed(() =>
  (props.warehouses || []).filter(w => !w.is_virtual)
)

const itemLocations = computed(() => {
  if (!props.item.warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(props.item.warehouse_id)
})

const lineTotal = computed(() =>
  (Math.round(props.item.unit_price * props.item.quantity * 100) / 100).toFixed(2)
)

const availableStock = computed(() => {
  if (!props.item.warehouse_id || !props.item.location_id) return 0
  const s = props.item.stocks?.find(
    s => s.warehouse_id === parseInt(props.item.warehouse_id) && s.location_id === parseInt(props.item.location_id)
  )
  return s ? (s.available_qty ?? s.quantity) : 0
})

const getWarehouseStock = (warehouseId) => {
  return props.item.stocks
    ?.filter(s => s.warehouse_id === warehouseId)
    .reduce((sum, s) => sum + (s.available_qty ?? s.quantity), 0) || 0
}

const getLocationStock = (locationId) => {
  const s = props.item.stocks?.find(
    s => s.warehouse_id === parseInt(props.item.warehouse_id) && s.location_id === locationId
  )
  return s ? (s.available_qty ?? s.quantity) : 0
}

const onWarehouseChange = () => {
  const wh = props.warehouses?.find(w => w.id === parseInt(props.item.warehouse_id))
  props.item.warehouse_name = wh?.name || ''
  props.item.location_id = ''
  props.item.location_code = ''
}

const onLocationChange = () => {
  const loc = itemLocations.value.find(l => l.id === parseInt(props.item.location_id))
  props.item.location_code = loc?.code || ''
  props.item.location_color = loc?.color || 'blue'
}

const handleIncrement = () => {
  if (props.orderType === 'RETURN' && props.item.max_return_qty && props.item.quantity >= props.item.max_return_qty) {
    appStore.showToast(`最多只能退${props.item.max_return_qty}件`, 'error')
    return
  }
  props.item.quantity++
}

const handleDecrement = () => {
  if (props.item.quantity > minQty.value) props.item.quantity--
}
</script>
```

**Step 2: Commit**

```bash
git add src/components/business/sales/WorksheetRow.vue
git commit -m "feat(sales): 创建WorksheetRow数据行组件"
```

---

### Task 4: 创建 ProductSearchRow.vue — 内联搜索行

**Files:**
- Create: `src/components/business/sales/ProductSearchRow.vue`

**Step 1: 创建组件**

```vue
<!--
  商品搜索行 - 工作台表格末尾的内联搜索
  输入关键词后弹出下拉面板，按商品分组显示仓库/仓位行
  点击仓库行后 emit add-item 事件
-->
<template>
  <tr>
    <td class="px-3 py-2.5 text-center text-muted text-sm">+</td>
    <td :colspan="colSpan" class="px-3 py-2.5">
      <div ref="wrapperRef" class="relative">
        <input
          ref="searchInputRef"
          v-model="searchText"
          class="input text-sm w-full"
          placeholder="输入商品名称、SKU 或品牌搜索添加..."
          @focus="showDropdown = true"
          @keydown.esc="closeDropdown"
          @keydown.down.prevent="navigateDown"
          @keydown.up.prevent="navigateUp"
          @keydown.enter.prevent="selectHighlighted"
          autocomplete="off"
        >
        <teleport to="body">
          <div
            v-if="showDropdown && searchText && searchResults.length"
            class="product-search-dropdown"
            :style="dropdownStyle"
            ref="dropdownRef"
          >
            <template v-for="group in searchResults" :key="group.product.id">
              <!-- 商品标题行（不可点击） -->
              <div class="px-3 py-1.5 text-xs font-semibold text-secondary bg-elevated border-b flex items-center gap-1.5">
                <span>{{ group.product.name }}</span>
                <span class="text-muted font-mono">{{ group.product.sku }}</span>
                <span v-if="group.product.brand" class="text-muted">&middot; {{ group.product.brand }}</span>
              </div>
              <!-- 仓库/仓位行（可点击） -->
              <button
                v-for="row in group.rows"
                :key="row.key"
                type="button"
                class="w-full text-left px-3 py-2 text-sm flex items-center gap-2 border-b transition-colors"
                :class="{
                  'bg-info-subtle': highlightIndex === row.flatIndex,
                  'opacity-40 cursor-not-allowed': row.disabled,
                  'cursor-pointer hover:bg-elevated': !row.disabled
                }"
                :disabled="row.disabled"
                @click="!row.disabled && selectRow(group.product, row)"
                @mouseenter="highlightIndex = row.flatIndex"
              >
                <span :class="row.is_virtual ? 'badge badge-purple text-xs' : `badge badge-${row.location_color} text-xs`">
                  {{ row.location_code }}
                </span>
                <span class="text-secondary text-xs">{{ row.warehouse_name }}</span>
                <span class="text-xs">
                  库存:
                  <span :class="row.available_qty > 0 ? 'text-success font-semibold' : 'text-muted'">{{ row.available_qty }}</span>
                </span>
                <span class="ml-auto text-primary font-mono text-xs">&yen;{{ group.product.retail_price }}</span>
              </button>
            </template>
          </div>
          <!-- 关闭遮罩 -->
          <div v-if="showDropdown && searchText" @click="closeDropdown" class="fixed inset-0" style="z-index: 40"></div>
        </teleport>
      </div>
    </td>
  </tr>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { fuzzyMatchAny } from '../../../utils/helpers'
import { DEFAULT_LOCATION_COLOR } from '../../../utils/constants'

const props = defineProps({
  products: Array,
  orderType: String,
  colSpan: { type: Number, default: 7 }
})

const emit = defineEmits(['add-item'])

const searchText = ref('')
const showDropdown = ref(false)
const highlightIndex = ref(-1)
const wrapperRef = ref(null)
const searchInputRef = ref(null)
const dropdownRef = ref(null)
const dropdownStyle = ref({})

/** 搜索结果：按商品分组，每组下列出仓库/仓位行 */
const searchResults = computed(() => {
  if (!searchText.value) return []
  const kw = searchText.value
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

watch(searchText, () => {
  highlightIndex.value = -1
  if (searchText.value) {
    showDropdown.value = true
    nextTick(updatePosition)
  }
})

onUnmounted(() => {
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
```

**Step 2: Commit**

```bash
git add src/components/business/sales/ProductSearchRow.vue
git commit -m "feat(sales): 创建ProductSearchRow内联搜索组件"
```

---

### Task 5: 创建 SalesFooter.vue — 底栏

**Files:**
- Create: `src/components/business/sales/SalesFooter.vue`

**Step 1: 创建组件**

```vue
<!--
  销售工作台底栏 - 备注、合计金额、操作按钮
  支持多账套分组小计显示
-->
<template>
  <div class="flex flex-wrap items-center gap-3 mt-3 px-1">
    <!-- 备注 -->
    <input
      :value="remark"
      @input="$emit('update:remark', $event.target.value)"
      class="input text-sm flex-1 min-w-48"
      placeholder="订单备注（可选）"
    >

    <!-- 多账套分组小计 -->
    <div v-if="isMultiAccountSet" class="flex items-center gap-3 text-xs text-secondary">
      <span v-for="group in accountSetGroups" :key="group.key">
        {{ group.name }}: <span class="font-mono text-foreground">&yen;{{ fmt(group.subtotal) }}</span>
      </span>
    </div>

    <!-- 合计 -->
    <div class="flex items-center gap-1">
      <span class="text-sm text-secondary">合计:</span>
      <span class="text-lg font-bold text-primary font-mono">&yen;{{ fmt(cartTotal) }}</span>
    </div>

    <!-- 操作按钮 -->
    <button @click="$emit('clear')" class="text-error text-sm hover:underline" v-show="cartLength">清空</button>
    <button @click="$emit('submit')" class="btn btn-primary text-sm" :disabled="!cartLength">提交订单</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useFormat } from '../../../composables/useFormat'

const props = defineProps({
  cartTotal: Number,
  cartLength: Number,
  remark: String,
  accountSetGroups: Array,
  isMultiAccountSet: Boolean
})

defineEmits(['clear', 'submit', 'update:remark'])

const { fmt } = useFormat()
</script>
```

**Step 2: Commit**

```bash
git add src/components/business/sales/SalesFooter.vue
git commit -m "feat(sales): 创建SalesFooter底栏组件"
```

---

### Task 6: 创建 SalesWorksheet.vue — 工作台表格

**Files:**
- Create: `src/components/business/sales/SalesWorksheet.vue`

**Step 1: 创建组件**

```vue
<!--
  销售工作台表格 - 可编辑商品明细表
  包含数据行（WorksheetRow）和搜索行（ProductSearchRow）
  退货模式下隐藏搜索行，显示预填充的退货商品
-->
<template>
  <div>
    <!-- 多账套警告 -->
    <div v-if="isMultiAccountSet" class="mb-3 p-2.5 bg-warning-subtle border border-warning rounded-lg text-xs">
      <div class="font-semibold text-warning">本单包含多个账套的商品</div>
      <div class="text-secondary mt-0.5">财务将按账套分别生成应收单</div>
    </div>

    <div class="card">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 text-center w-10">#</th>
              <th class="px-3 py-2 text-left">商品</th>
              <th class="px-3 py-2 text-center w-36">数量</th>
              <th class="px-3 py-2 text-left w-24">单价</th>
              <th v-if="showCost" class="px-3 py-2 text-right w-20 md-hide">成本</th>
              <th class="px-3 py-2 text-left w-36">仓库</th>
              <th class="px-3 py-2 text-left w-28 md-hide">仓位</th>
              <th class="px-3 py-2 text-right w-24">小计</th>
              <th class="px-3 py-2 text-center w-20">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <!-- 数据行 -->
            <WorksheetRow
              v-for="(item, idx) in cart"
              :key="item._id"
              :item="item"
              :index="idx"
              :order-type="orderType"
              :warehouses="warehouses"
              :show-cost="showCost"
              @remove="$emit('remove-item', $event)"
              @duplicate="$emit('duplicate-line', $event)"
            />

            <!-- 搜索行（退货模式下隐藏） -->
            <ProductSearchRow
              v-if="orderType !== 'RETURN'"
              :products="products"
              :order-type="orderType"
              :col-span="showCost ? 8 : 7"
              @add-item="(product, row) => $emit('add-from-search', product, row)"
            />

            <!-- 空状态 -->
            <tr v-if="!cart.length && orderType !== 'RETURN'">
              <td :colspan="showCost ? 9 : 8" class="px-3 py-8 text-center text-muted">
                在上方搜索框输入商品名称开始添加
              </td>
            </tr>
            <tr v-if="!cart.length && orderType === 'RETURN'">
              <td :colspan="showCost ? 9 : 8" class="px-3 py-8 text-center text-muted">
                请在顶栏搜索并选择要退货的原始订单
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { usePermission } from '../../../composables/usePermission'
import WorksheetRow from './WorksheetRow.vue'
import ProductSearchRow from './ProductSearchRow.vue'

const props = defineProps({
  cart: Array,
  orderType: String,
  warehouses: Array,
  products: Array,
  isMultiAccountSet: Boolean
})

defineEmits(['remove-item', 'duplicate-line', 'add-from-search'])

const { hasPermission } = usePermission()
const showCost = hasPermission('finance')
</script>
```

**Step 2: Commit**

```bash
git add src/components/business/sales/SalesWorksheet.vue
git commit -m "feat(sales): 创建SalesWorksheet工作台表格组件"
```

---

### Task 7: 重写 SalesView.vue — 组装新组件

**Files:**
- Modify: `src/views/SalesView.vue`

**Step 1: 完整重写文件**

```vue
<!--
  销售页面 - 瘦容器
  编排 SalesToolbar、SalesWorksheet、SalesFooter、OrderConfirmModal
  管理全局状态、退货订单搜索逻辑、订单提交流程
-->
<template>
  <div>
    <!-- 顶栏 -->
    <SalesToolbar
      :order-type="saleForm.order_type"
      :customer-id="saleForm.customer_id"
      :employee-id="saleForm.employee_id"
      :customers="customers"
      :employees="salespersonEmployees"
      :need-customer="needCustomer"
      :return-order-search="returnOrderSearch"
      :return-order-dropdown="returnOrderDropdown"
      :filtered-return-orders="filteredReturnOrders"
      :selected-return-order="selectedReturnOrder"
      @update:order-type="saleForm.order_type = $event"
      @update:customer-id="saleForm.customer_id = $event"
      @update:employee-id="saleForm.employee_id = $event"
      @update:return-order-search="returnOrderSearch = $event"
      @update:return-order-dropdown="returnOrderDropdown = $event"
      @search-return-orders="searchReturnOrders"
      @select-return-order="selectReturnOrder"
    />

    <!-- 工作台表格 -->
    <SalesWorksheet
      :cart="cart"
      :order-type="saleForm.order_type"
      :warehouses="warehouses"
      :products="products"
      :is-multi-account-set="isMultiAccountSet"
      @remove-item="idx => cart.splice(idx, 1)"
      @duplicate-line="handleDuplicateLine"
      @add-from-search="handleAddFromSearch"
    />

    <!-- 底栏 -->
    <SalesFooter
      :cart-total="cartTotal"
      :cart-length="cart.length"
      :remark="saleForm.remark"
      :account-set-groups="accountSetGroups"
      :is-multi-account-set="isMultiAccountSet"
      @clear="clearCart"
      @submit="submitOrder"
      @update:remark="saleForm.remark = $event"
    />

    <!-- 订单确认弹窗（保持不变） -->
    <OrderConfirmModal
      :visible="appStore.modal.show && appStore.modal.type === 'order_confirm'"
      :order-confirm="orderConfirm"
      :employees="salespersonEmployees"
      :payment-methods="paymentMethods"
      :submitting="appStore.submitting"
      @update:visible="!$event && appStore.closeModal()"
      @confirm="confirmSubmitOrder"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'
import { useProductsStore } from '../stores/products'
import { useWarehousesStore } from '../stores/warehouses'
import { useCustomersStore } from '../stores/customers'
import { useSettingsStore } from '../stores/settings'
import { useFormat } from '../composables/useFormat'
import { useSalesCart } from '../composables/useSalesCart'
import { getOrders, getOrder, createOrder } from '../api/orders'
import { getAccountSets } from '../api/accounting'
import { getPaymentMethods as getPaymentMethodsApi } from '../api/settings'
import { fuzzyMatchAny } from '../utils/helpers'
import SalesToolbar from '../components/business/sales/SalesToolbar.vue'
import SalesWorksheet from '../components/business/sales/SalesWorksheet.vue'
import SalesFooter from '../components/business/sales/SalesFooter.vue'
import OrderConfirmModal from '../components/business/sales/OrderConfirmModal.vue'

// ---------- Store ----------
const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const customersStore = useCustomersStore()
const settingsStore = useSettingsStore()

const { fmt } = useFormat()

const products = computed(() => productsStore.products)
const warehouses = computed(() => warehousesStore.warehouses)
const locations = computed(() => warehousesStore.locations)
const customers = computed(() => customersStore.customers)
const salespersonEmployees = computed(() => settingsStore.employees.filter(e => e.is_salesperson))
const allPaymentMethods = computed(() => settingsStore.paymentMethods)

// 按账套过滤的收款方式
const filteredPaymentMethodsList = ref([])
async function loadFilteredPaymentMethods(accountSetId) {
  if (!accountSetId) { filteredPaymentMethodsList.value = []; return }
  try {
    const { data } = await getPaymentMethodsApi({ account_set_id: accountSetId })
    filteredPaymentMethodsList.value = data
  } catch { filteredPaymentMethodsList.value = [] }
}
const paymentMethods = computed(() =>
  filteredPaymentMethodsList.value.length ? filteredPaymentMethodsList.value : allPaymentMethods.value
)

// ---------- 购物车 ----------
const {
  cart, addFromSearch, populateReturnItems, incrementQuantity,
  duplicateCartLine, getCartStock, cartTotal, clearCart
} = useSalesCart()

// ---------- 本地状态 ----------
const accountSets = ref([])

const saleForm = reactive({
  order_type: 'CASH',
  customer_id: '',
  employee_id: '',
  related_order_id: '',
  remark: ''
})

// 退货相关
const returnOrderSearch = ref('')
const returnOrderDropdown = ref(false)
const salesOrders = ref([])
const selectedReturnOrder = ref(null)

// 订单确认数据
const orderConfirm = ref({
  items: [], customer: null, total: 0, order_type: '',
  refunded: false, use_credit: false, available_credit: 0,
  use_rebate: false, rebate_balance: 0, employee_id: '',
  remark: '', payment_method: 'cash', account_set_id: null
})

// ---------- 计算属性 ----------
const needCustomer = computed(() =>
  ['CASH', 'CREDIT', 'CONSIGN_OUT', 'CONSIGN_SETTLE', 'RETURN'].includes(saleForm.order_type)
)

const filteredReturnOrders = computed(() => {
  const kw = returnOrderSearch.value
  if (!kw) return salesOrders.value.slice(0, 20)
  return salesOrders.value.filter(o => fuzzyMatchAny([o.order_no, o.customer_name], kw)).slice(0, 20)
})

/** 按账套分组 */
const accountSetGroups = computed(() => {
  const groups = new Map()
  for (const item of cart.value) {
    const wh = warehouses.value.find(w => w.id === parseInt(item.warehouse_id))
    const asId = wh?.account_set_id || 0
    const asName = wh?.account_set_name || '未关联账套'
    if (!groups.has(asId)) groups.set(asId, { key: asId, name: asName, subtotal: 0 })
    groups.get(asId).subtotal += Math.round(item.unit_price * item.quantity * 100) / 100
  }
  return [...groups.values()]
})

const isMultiAccountSet = computed(() => accountSetGroups.value.length > 1)

// ---------- 函数 ----------

/** 内联搜索添加商品 */
const handleAddFromSearch = (product, stockRow) => {
  addFromSearch(product, stockRow, saleForm.order_type, appStore)
}

/** 复制购物车行 */
const handleDuplicateLine = (idx) => duplicateCartLine(idx, products)

/** 搜索退货关联订单 */
let _returnOrderAbort = null
const searchReturnOrders = async () => {
  if (saleForm.order_type !== 'RETURN') return
  if (_returnOrderAbort) _returnOrderAbort.abort()
  const controller = new AbortController()
  _returnOrderAbort = controller
  try {
    const { data } = await getOrders({ limit: 200 }, { signal: controller.signal })
    salesOrders.value = (data.items || data).filter(o => ['CASH', 'CREDIT'].includes(o.order_type))
  } catch (e) {
    if (e?.code === 'ERR_CANCELED') return
    appStore.showToast(e.response?.data?.detail || '加载订单失败', 'error')
  } finally {
    if (_returnOrderAbort === controller) _returnOrderAbort = null
  }
}

/** 选中退货关联订单 */
const selectReturnOrder = async (o) => {
  returnOrderSearch.value = o.order_no + ' - ' + o.customer_name
  saleForm.related_order_id = o.id
  saleForm.customer_id = o.customer_id
  returnOrderDropdown.value = false
  try {
    const { data } = await getOrder(o.id)
    selectedReturnOrder.value = data
    populateReturnItems(data, products)
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
  }
}

/** 提交订单前校验并打开确认弹窗 */
const submitOrder = () => {
  // 退货模式过滤掉数量为0的行
  const activeItems = saleForm.order_type === 'RETURN'
    ? cart.value.filter(i => i.quantity > 0)
    : cart.value

  if (!activeItems.length) {
    appStore.showToast('请至少添加一件商品', 'error')
    return
  }

  // 校验数量和单价
  for (const item of activeItems) {
    if (!item.quantity || item.quantity <= 0) {
      appStore.showToast(`【${item.name}】数量必须大于0`, 'error'); return
    }
    if (saleForm.order_type !== 'RETURN' && item.unit_price <= 0) {
      appStore.showToast(`【${item.name}】单价必须大于0`, 'error'); return
    }
    if (saleForm.order_type === 'RETURN' && item.unit_price < 0) {
      appStore.showToast(`【${item.name}】单价不能为负数`, 'error'); return
    }
  }

  if (needCustomer.value && !saleForm.customer_id) {
    appStore.showToast('请选择客户', 'error'); return
  }
  if (saleForm.order_type === 'RETURN' && !saleForm.related_order_id) {
    appStore.showToast('退货请选择原始销售订单', 'error'); return
  }

  // 校验仓库/仓位
  if (saleForm.order_type !== 'CONSIGN_SETTLE') {
    for (const item of activeItems) {
      if (!item.warehouse_id || !item.location_id) {
        const label = saleForm.order_type === 'RETURN' ? '退货仓库和仓位' : '仓库和仓位'
        appStore.showToast(`请为【${item.name}】选择${label}`, 'error'); return
      }
    }
  }

  // 构建确认数据
  const customer = customers.value.find(c => c.id === saleForm.customer_id)
  const total = activeItems.reduce((s, i) => s + Math.round(i.quantity * i.unit_price * 100) / 100, 0)
  const availableCredit = customer && customer.balance < 0 ? Math.abs(customer.balance) : 0
  const rebateBalance = customer?.rebate_balance || 0

  // 自动检测账套
  let autoAccountSetId = null
  if (activeItems.length > 0 && activeItems[0]?.warehouse_id) {
    const firstWarehouse = warehouses.value.find(w => w.id === parseInt(activeItems[0]?.warehouse_id))
    if (firstWarehouse?.account_set_id) autoAccountSetId = firstWarehouse.account_set_id
  }

  orderConfirm.value = {
    items: activeItems.map(i => {
      const warehouse = warehouses.value.find(w => w.id === parseInt(i.warehouse_id))
      const location = locations.value.find(l => l.id === parseInt(i.location_id))
      return {
        ...i,
        warehouse_name: warehouse?.name || i.warehouse_name || '-',
        location_code: location?.code || i.location_code || '-',
        account_set_id: warehouse?.account_set_id || null,
        account_set_name: warehouse?.account_set_name || null,
        rebate_amount: 0
      }
    }),
    customer, order_type: saleForm.order_type,
    related_order_id: saleForm.related_order_id,
    total, refunded: false,
    refund_method: 'cash',
    refund_amount: Math.abs(total),
    use_credit: false, available_credit: availableCredit,
    use_rebate: false, rebate_balance: rebateBalance,
    employee_id: saleForm.employee_id || '',
    employee_name: salespersonEmployees.value.find(s => s.id === parseInt(saleForm.employee_id))?.name || '',
    remark: saleForm.remark || '',
    payment_method: 'cash',
    account_set_id: autoAccountSetId
  }
  if (orderConfirm.value.account_set_id) {
    loadFilteredPaymentMethods(orderConfirm.value.account_set_id)
  }
  appStore.openModal('order_confirm', '确认提交订单')
}

/** 确认提交订单 */
const confirmSubmitOrder = async () => {
  if (appStore.submitting) return

  const useRebate = orderConfirm.value.use_rebate
  const totalRebate = useRebate ? orderConfirm.value.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) : 0

  if (useRebate) {
    for (const item of orderConfirm.value.items) {
      if (item.rebate_amount && item.rebate_amount > item.unit_price * item.quantity) {
        appStore.showToast(`${item.name} 的返利金额不能超过商品小计`, 'error'); return
      }
    }
  }
  if (useRebate && totalRebate > orderConfirm.value.rebate_balance) {
    appStore.showToast('返利总额超过可用余额', 'error'); return
  }

  // 退货模式过滤0数量行
  const submitItems = saleForm.order_type === 'RETURN'
    ? cart.value.filter(i => i.quantity > 0)
    : cart.value

  appStore.submitting = true
  try {
    const result = await createOrder({
      order_type: saleForm.order_type,
      customer_id: saleForm.customer_id || null,
      employee_id: orderConfirm.value.employee_id ? parseInt(orderConfirm.value.employee_id) : null,
      warehouse_id: null, location_id: null,
      related_order_id: saleForm.related_order_id || null,
      refunded: orderConfirm.value.refunded || false,
      refund_method: saleForm.order_type === 'RETURN' && orderConfirm.value.refunded ? (orderConfirm.value.refund_method || null) : null,
      refund_amount: saleForm.order_type === 'RETURN' && orderConfirm.value.refunded ? (orderConfirm.value.refund_amount || null) : null,
      use_credit: orderConfirm.value.use_credit || false,
      payment_method: orderConfirm.value.payment_method || null,
      rebate_amount: totalRebate > 0 ? totalRebate : null,
      items: submitItems.map((i, idx) => ({
        product_id: i.product_id, quantity: i.quantity, unit_price: i.unit_price,
        warehouse_id: i.warehouse_id ? parseInt(i.warehouse_id) : null,
        location_id: i.location_id ? parseInt(i.location_id) : null,
        rebate_amount: useRebate && orderConfirm.value.items[idx]?.rebate_amount ? orderConfirm.value.items[idx].rebate_amount : null
      })),
      remark: orderConfirm.value.remark || null,
      account_set_id: orderConfirm.value.account_set_id || null
    })

    let msg = '订单创建成功'
    if (result.data.rebate_used && result.data.rebate_used > 0) msg += `，已使用返利 ¥${fmt(result.data.rebate_used)}`
    if (result.data.credit_used && result.data.credit_used > 0) msg += `，已使用在账资金 ¥${fmt(result.data.credit_used)}`
    if (result.data.amount_due > 0) msg += `，还需支付 ¥${fmt(result.data.amount_due)}`
    appStore.showToast(msg)

    clearCart()
    Object.assign(saleForm, {
      employee_id: '', related_order_id: '',
      customer_id: '', order_type: 'CASH', remark: ''
    })
    returnOrderSearch.value = ''
    selectedReturnOrder.value = null
    appStore.closeModal()

    productsStore.loadProducts()
    customersStore.loadCustomers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '订单创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// ---------- Watchers ----------
watch(() => orderConfirm.value.account_set_id, (newId) => {
  loadFilteredPaymentMethods(newId)
})

watch(() => saleForm.order_type, (newType, oldType) => {
  if ((newType === 'RETURN' && oldType !== 'RETURN') || (oldType === 'RETURN' && newType !== 'RETURN')) {
    clearCart()
  }
  if (newType === 'RETURN') {
    searchReturnOrders()
  } else {
    returnOrderSearch.value = ''
    saleForm.related_order_id = ''
    selectedReturnOrder.value = null
  }
})

// ---------- 生命周期 ----------
onMounted(async () => {
  if (!products.value.length) productsStore.loadProducts()
  if (!warehouses.value.length) warehousesStore.loadWarehouses()
  if (!locations.value.length) warehousesStore.loadLocations()
  if (!customers.value.length) customersStore.loadCustomers()
  if (!salespersonEmployees.value.length) settingsStore.loadEmployees()
  if (!paymentMethods.value.length) settingsStore.loadPaymentMethods()
  try {
    const { data } = await getAccountSets()
    accountSets.value = data
  } catch { /* ignore */ }
})

onUnmounted(() => {
  if (_returnOrderAbort) _returnOrderAbort.abort()
})
</script>
```

**Step 2: 构建验证**

Run: `npm run build`
Expected: 编译成功

**Step 3: Commit**

```bash
git add src/views/SalesView.vue
git commit -m "feat(sales): 重写SalesView使用工作台布局"
```

---

### Task 8: 清理旧组件 + 最终验证

**Files:**
- Delete: `src/components/business/sales/ProductSelector.vue`
- Delete: `src/components/business/sales/ShoppingCart.vue`
- Delete: `src/components/business/sales/CartItem.vue`

**Step 1: 删除旧组件**

```bash
rm src/components/business/sales/ProductSelector.vue
rm src/components/business/sales/ShoppingCart.vue
rm src/components/business/sales/CartItem.vue
```

**Step 2: 检查全局是否有其他文件引用旧组件**

```bash
grep -r "ProductSelector\|ShoppingCart\|CartItem" src/ --include="*.vue" --include="*.js"
```

Expected: 无匹配结果（SalesView.vue 已不再引用）

**Step 3: 构建验证**

Run: `npm run build`
Expected: 编译成功，无错误

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor(sales): 删除旧购物车组件（ProductSelector/ShoppingCart/CartItem）"
```

---

## 验证清单

构建通过后，手动验证以下场景：

1. **现款开单**：搜索商品 → 点击仓库行添加 → 编辑数量/单价 → 选仓库/仓位 → 提交
2. **账期开单**：同上，但库存为0也能添加
3. **退货**：切换退货类型 → 搜索关联订单 → 选择 → 设置退货数量 → 选仓库/仓位 → 提交
4. **寄售调拨**：搜索仅显示非虚拟仓库存
5. **寄售结算**：搜索仅显示虚拟仓库存，仓库/仓位锁定
6. **拆分行**：点击拆分按钮 → 新行清空仓库仓位 → 选择其他仓库
7. **多账套**：添加不同仓库（不同账套）的商品 → 显示警告
8. **键盘操作**：搜索框中 ↑/↓/Enter/Esc
9. **移动端**：缩小窗口，检查列隐藏和布局
