<!--
  工作台数据行 - 单个商品的可编辑行
  直接修改 item 的响应式属性（unit_price/quantity/warehouse_id/location_id）
  仅 emit 删除和拆分操作（需要父组件协调）
-->
<template>
  <tr class="transition-colors">
    <!-- 序号 -->
    <td class="px-3 py-1.5 text-center text-muted text-xs align-middle">{{ index + 1 }}</td>

    <!-- 商品 -->
    <td class="px-3 py-1.5 align-middle">
      <div class="font-medium text-sm">{{ item.name }}</div>
      <div class="text-xs text-muted font-mono mt-0.5 md-hide">{{ item.sku }}</div>
    </td>

    <!-- 数量 -->
    <td class="px-3 py-1.5 align-middle">
      <div class="inline-flex items-center gap-1">
        <button
          @click="handleDecrement"
          class="w-6 h-6 rounded border text-xs hover:bg-elevated flex items-center justify-center"
          aria-label="减少数量"
        >-</button>
        <input
          v-model.number="item.quantity"
          type="number"
          :min="minQty"
          class="input input-sm w-14 text-center"
          aria-label="数量"
          @blur="item.quantity = Math.max(minQty, Math.floor(item.quantity) || minQty)"
        >
        <button
          @click="handleIncrement"
          class="w-6 h-6 rounded border text-xs hover:bg-elevated flex items-center justify-center"
          aria-label="增加数量"
        >+</button>
      </div>
      <div v-if="orderType === 'RETURN' && item.max_return_qty" class="text-xs text-warning mt-0.5">
        最多可退: {{ item.max_return_qty }}
      </div>
    </td>

    <!-- 单价 -->
    <td class="px-3 py-1.5 align-middle">
      <input
        v-model.number="item.unit_price"
        type="number"
        step="0.01"
        class="input input-sm w-20 text-right"
      >
    </td>

    <!-- 成本价（需要 finance 权限） -->
    <td v-if="showCost" class="px-3 py-1.5 text-right text-secondary text-sm md-hide align-middle">
      &yen;{{ item.cost_price || '-' }}
    </td>

    <!-- 仓库 -->
    <td class="px-3 py-1.5 align-middle">
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
          :class="{ 'border-error': item.warehouse_id && item.location_id && availableStock < item.quantity }"
        >
          <option value="">选择仓库 *</option>
          <option
            v-for="w in physicalWarehouses"
            :key="w.id"
            :value="w.id"
          >{{ w.name }} ({{ getWarehouseStock(w.id) }})</option>
        </select>
      </template>
    </td>

    <!-- 仓位 -->
    <td class="px-3 py-1.5 md-hide align-middle">
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
          :class="{ 'border-error': item.warehouse_id && item.location_id && availableStock < item.quantity }"
        >
          <option value="">{{ item.warehouse_id ? '选仓位 *' : '先选仓库' }}</option>
          <option
            v-for="loc in itemLocations"
            :key="loc.id"
            :value="loc.id"
          >{{ loc.code }} ({{ getLocationStock(loc.id) }})</option>
        </select>
      </template>
    </td>

    <!-- 小计 -->
    <td class="px-3 py-1.5 text-right text-primary font-semibold text-sm font-mono align-middle">
      &yen;{{ lineTotal }}
    </td>

    <!-- 操作 -->
    <td class="px-3 py-1.5 text-center align-middle">
      <div class="flex gap-1 justify-center">
        <button
          v-if="showDuplicate"
          @click="$emit('duplicate', index)"
          class="w-6 h-6 rounded-full bg-info-subtle text-primary text-xs font-bold flex items-center justify-center hover:opacity-80"
          title="拆分到其他仓库"
          aria-label="拆分到其他仓库"
        >+</button>
        <button
          @click="$emit('remove', index)"
          class="w-6 h-6 rounded-full bg-error-subtle text-error text-xs font-bold flex items-center justify-center hover:opacity-80"
          title="删除"
          aria-label="删除商品"
        >&times;</button>
      </div>
    </td>
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useWarehousesStore } from '../../../stores/warehouses'
import { useFormat } from '../../../composables/useFormat'

const props = defineProps({
  item: { type: Object, required: true },
  index: { type: Number, required: true },
  orderType: { type: String, required: true },
  warehouses: { type: Array, required: true },
  showCost: { type: Boolean, default: false }
})

defineEmits(['remove', 'duplicate'])

const appStore = useAppStore()
const warehousesStore = useWarehousesStore()
const { fmt } = useFormat()

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
  fmt(Math.round(props.item.unit_price * props.item.quantity * 100) / 100)
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
