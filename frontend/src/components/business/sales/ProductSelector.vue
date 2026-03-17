<!--
  商品选择器 - 销售页面左栏
  显示商品列表，支持仓库/仓位/关键词筛选
  通过 emit 与父组件通信筛选状态变更
-->
<template>
  <div class="flex-1 md:min-w-0 mb-4 md:mb-0">
    <!-- 筛选栏 -->
    <div class="flex flex-wrap gap-2 mb-3">
      <!-- 仓库筛选 -->
      <select
        :value="warehouseId"
        @change="$emit('update:warehouseId', $event.target.value)"
        class="input w-auto text-sm"
      >
        <option value="">筛选仓库（可选）</option>
        <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
        <template v-if="showVirtualStock">
          <option v-for="vw in virtualWarehouses" :key="'v' + vw.id" :value="vw.id">{{ vw.name }}</option>
        </template>
      </select>
      <!-- 寄售开关 -->
      <label class="flex items-center gap-1.5 text-xs text-muted cursor-pointer whitespace-nowrap select-none">
        <span class="toggle">
          <input
            type="checkbox"
            :checked="showVirtualStock"
            @change="$emit('update:showVirtualStock', $event.target.checked)"
          >
          <span class="slider"></span>
        </span>
        寄售
      </label>
      <!-- 仓位筛选 -->
      <select
        :value="locationId"
        @change="$emit('update:locationId', $event.target.value)"
        class="input w-auto text-sm"
        v-show="warehouseId"
      >
        <option value="">筛选仓位（可选）</option>
        <option v-for="loc in filterLocations" :key="loc.id" :value="loc.id">{{ loc.code }}</option>
      </select>
      <!-- 搜索框 -->
      <input v-model="productSearch" class="input flex-1 text-sm" placeholder="搜索商品...">
      <!-- 退货订单提示 -->
      <div
        v-if="orderType === 'RETURN' && selectedReturnOrder"
        class="w-full text-sm px-2 py-2 bg-info-subtle rounded border border-primary text-primary"
      >
        <span class="font-medium">退货订单：</span>{{ selectedReturnOrder.order_no }} - {{ selectedReturnOrder.customer_name }}
      </div>
    </div>

    <!-- 商品表格 -->
    <div class="card">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-2 py-2 text-left w-24 md-hide">品牌</th>
              <th class="px-2 py-2 text-left">商品名称</th>
              <th class="px-2 py-2 text-left w-24 md-hide">仓位</th>
              <th class="px-2 py-2 text-right w-24">零售价</th>
              <th class="px-2 py-2 text-right w-24 md-hide" v-if="hasPermission('finance')">成本价</th>
              <th class="px-2 py-2 text-center w-20">库存</th>
              <th class="px-2 py-2 text-center w-20 md-hide">库龄</th>
              <th class="px-2 py-2 text-center w-16">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr
              v-for="p in displayProducts"
              :key="p.id + '-' + (p.stock_key || '')"
              @click="!p.is_virtual_stock && $emit('add-to-cart', p)"
              class="hover:bg-elevated"
              :class="{
                'bg-info-subtle': !p.is_virtual_stock && cart.some(c => c.product_id === p.id),
                'bg-purple-subtle': p.is_virtual_stock,
                'cursor-pointer': !p.is_virtual_stock
              }"
            >
              <td class="px-2 py-2 text-secondary text-xs md-hide">{{ p.brand || '-' }}</td>
              <td class="px-2 py-2">
                <div class="font-medium">{{ p.name }}</div>
                <div class="text-xs text-muted font-mono mt-0.5">{{ p.sku }}</div>
              </td>
              <td class="px-2 py-2 md-hide">
                <span v-if="p.is_virtual_stock" class="badge badge-purple text-xs">寄售</span>
                <span v-else-if="p.location_code" :class="`badge badge-${p.location_color || DEFAULT_LOCATION_COLOR} text-xs`">{{ p.location_code }}</span>
                <span v-else class="text-muted text-xs">-</span>
              </td>
              <td class="px-2 py-2 text-right text-primary font-bold">&yen;{{ p.retail_price }}</td>
              <td class="px-2 py-2 text-right text-secondary md-hide" v-if="hasPermission('finance')">&yen;{{ p.cost_price }}</td>
              <td
                class="px-2 py-2 text-center font-semibold"
                :class="p.is_virtual_stock ? 'text-purple-emphasis' : getAgeClass(p.age_days)"
              >
                {{ p.display_stock !== undefined ? p.display_stock : getStock(p) }}
              </td>
              <td class="px-2 py-2 text-center text-xs md-hide" :class="getAgeClass(p.age_days)">{{ p.age_days }}天</td>
              <td class="px-2 py-2 text-center">
                <button
                  v-if="!p.is_virtual_stock"
                  @click.stop="$emit('add-to-cart', p)"
                  class="text-primary text-xs font-semibold hover:underline"
                >加入</button>
                <span v-else class="text-xs text-muted">只读</span>
              </td>
            </tr>
            <tr v-if="!displayProducts.length">
              <td :colspan="hasPermission('finance') ? 8 : 7" class="px-3 py-8 text-center text-muted">暂无商品</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 商品选择器组件
 * 接收筛选状态作为 props，通过 emit 回传变更
 */
import { ref, computed } from 'vue'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import { fuzzyMatchAny } from '../../../utils/helpers'
import { DEFAULT_LOCATION_COLOR } from '../../../utils/constants'

const props = defineProps({
  /** 全部商品列表（已从 store 取出） */
  products: Array,
  /** 仓库列表 */
  warehouses: Array,
  /** 虚拟仓库列表 */
  virtualWarehouses: Array,
  /** 筛选仓位列表 */
  filterLocations: Array,
  /** 当前筛选仓库 ID */
  warehouseId: [String, Number],
  /** 当前筛选仓位 ID */
  locationId: [String, Number],
  /** 订单类型 */
  orderType: String,
  /** 退货关联订单 */
  selectedReturnOrder: Object,
  /** 是否显示寄售库存 */
  showVirtualStock: Boolean,
  /** 购物车（用于高亮已选商品） */
  cart: Array
})

const emit = defineEmits([
  'add-to-cart',
  'update:warehouseId',
  'update:locationId',
  'update:showVirtualStock'
])

const { getAgeClass } = useFormat()
const { hasPermission } = usePermission()

/** 本地搜索关键词 */
const productSearch = ref('')

/**
 * 获取商品库存
 * 根据订单类型和筛选仓库决定显示逻辑
 */
const getStock = (p) => {
  if (props.orderType === 'CONSIGN_SETTLE') return p.stocks?.find(s => s.is_virtual)?.quantity || 0
  if (props.warehouseId) {
    const s = p.stocks?.find(s => s.warehouse_id == props.warehouseId)
    return s ? (s.available_qty ?? s.quantity) : 0
  }
  return p.total_stock || 0
}

/** 按关键词过滤后的商品 */
const filteredProducts = computed(() => {
  const kw = productSearch.value
  if (!kw) return props.products
  return props.products.filter(p => fuzzyMatchAny([p.sku, p.name, p.brand, p.category], kw))
})

/** 最终展示商品列表（含库位展开、仓库/仓位过滤） */
const displayProducts = computed(() => {
  // 退货模式：展示原始订单商品的各仓位库存
  if (props.orderType === 'RETURN' && props.selectedReturnOrder?.items) {
    const result = []
    props.selectedReturnOrder.items.forEach(item => {
      const availableQty = item.available_return_quantity || 0
      if (availableQty <= 0) return
      const product = props.products.find(p => p.id === item.product_id)
      if (product) {
        product.stocks?.forEach(s => {
          result.push({
            ...product,
            location_code: s.location_code,
            stock_key: s.warehouse_id + '-' + s.location_id,
            display_stock: s.quantity,
            warehouse_id: s.warehouse_id,
            location_id: s.location_id,
            original_quantity: Math.abs(item.quantity),
            returned_quantity: item.returned_quantity || 0,
            max_return_qty: availableQty,
            location_color: s.location_color || DEFAULT_LOCATION_COLOR
          })
        })
        if (!product.stocks || product.stocks.length === 0) {
          result.push({
            ...product,
            location_code: null,
            stock_key: 'none',
            display_stock: 0,
            original_quantity: Math.abs(item.quantity),
            returned_quantity: item.returned_quantity || 0,
            max_return_qty: availableQty
          })
        }
      }
    })
    return result
  }

  // 普通模式：按库位展开，根据筛选条件过滤
  const filtered = filteredProducts.value
  const result = []
  filtered.forEach(p => {
    if (p.stocks && p.stocks.length > 0) {
      p.stocks.forEach(s => {
        if (!props.showVirtualStock && s.is_virtual) return
        if (props.warehouseId && s.warehouse_id != props.warehouseId) return
        if (props.locationId && s.location_id != props.locationId) return
        result.push({
          ...p,
          location_code: s.location_code,
          stock_key: s.warehouse_id + '-' + s.location_id,
          display_stock: s.available_qty ?? s.quantity,
          warehouse_id: s.warehouse_id,
          location_id: s.location_id,
          is_virtual_stock: !!s.is_virtual,
          virtual_warehouse_name: s.warehouse_name || '',
          location_color: s.location_color || DEFAULT_LOCATION_COLOR
        })
      })
    }
  })
  return result
})

// 将 getStock 暴露给父组件（用于 addToCart 时判断库存）
defineExpose({ getStock })
</script>
