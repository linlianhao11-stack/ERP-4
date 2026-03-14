<!--
  购物车 - 销售页面右栏
  显示已选商品，支持数量调整、仓库仓位选择、订单提交
  多账套时自动分组展示，含警告横幅和分组小计
  所有状态通过 props 传入，修改通过 emit 回传
-->
<template>
  <div class="card md:w-72 flex flex-col md:sticky md:top-4" style="max-height: calc(100vh - 2rem)">
    <!-- 标题栏 -->
    <div class="p-3 border-b flex justify-between items-center">
      <h3 class="font-semibold text-sm">购物车({{ cart.length }})</h3>
      <button @click="$emit('clear')" class="text-error text-xs" v-show="cart.length">清空</button>
    </div>

    <!-- 多账套警告横幅 -->
    <div v-if="isMultiAccountSet" class="px-2 pt-2">
      <div class="p-2 bg-warning-subtle border border-warning rounded-lg text-xs">
        <div class="font-semibold text-warning">本单包含多个账套的商品</div>
        <div class="text-secondary mt-0.5">财务将按账套分别生成应收单</div>
      </div>
    </div>

    <!-- 购物车商品列表 -->
    <div class="flex-1 overflow-y-auto cart-items">
      <!-- 多账套分组展示 -->
      <template v-if="isMultiAccountSet">
        <template v-for="group in itemsByAccountSet" :key="group.key">
          <!-- 分组标题 -->
          <div class="px-2 py-1.5 bg-elevated text-xs font-semibold text-secondary border-b flex justify-between items-center">
            <span>{{ group.name }}</span>
            <span class="text-primary font-mono">&yen;{{ fmt(group.subtotal) }}</span>
          </div>
          <!-- 分组内商品 -->
          <div v-for="({ item, idx }) in group.items" :key="item._id" class="p-2 border-b">
            <CartItem
              :item="item"
              :idx="idx"
              :order-type="orderType"
              :warehouses="warehouses"
              :get-cart-stock="getCartStock"
              :get-cart-item-locations="getCartItemLocations"
              @duplicate-line="$emit('duplicate-line', $event)"
              @remove-item="$emit('remove-item', $event)"
              @increment-quantity="$emit('increment-quantity', $event)"
              @update-warehouse="(i, wid) => $emit('update-warehouse', i, wid)"
              @update-location="(i, lid) => $emit('update-location', i, lid)"
            />
          </div>
        </template>
      </template>
      <!-- 单账套（或无账套）：常规列表 -->
      <template v-else>
        <div v-for="(item, idx) in cart" :key="item._id" class="p-2 border-b">
          <CartItem
            :item="item"
            :idx="idx"
            :order-type="orderType"
            :warehouses="warehouses"
            :get-cart-stock="getCartStock"
            :get-cart-item-locations="getCartItemLocations"
            @duplicate-line="$emit('duplicate-line', $event)"
            @remove-item="$emit('remove-item', $event)"
            @increment-quantity="$emit('increment-quantity', $event)"
            @update-warehouse="(i, wid) => $emit('update-warehouse', i, wid)"
            @update-location="(i, lid) => $emit('update-location', i, lid)"
          />
        </div>
      </template>
      <div v-if="!cart.length" class="text-muted text-center py-6 text-sm">空</div>
    </div>

    <!-- 底栏：客户/销售员/订单类型/退货搜索/合计/提交 -->
    <div class="p-3 border-t">
      <!-- 客户选择 -->
      <div class="mb-2">
        <SearchableSelect
          :options="customerOptions"
          :modelValue="customerId"
          @update:modelValue="$emit('update:customerId', $event)"
          :placeholder="'选客户(' + (needCustomer ? '必选' : '可选') + ')'"
          searchPlaceholder="搜索客户名/电话"
        />
      </div>
      <!-- 业务员选择 -->
      <div class="mb-2">
        <select
          :value="employeeId"
          @change="$emit('update:employeeId', $event.target.value)"
          class="input text-sm"
        >
          <option value="">选业务员(可选)</option>
          <option v-for="s in employees" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>
      <!-- 订单类型选择 -->
      <div class="mb-2">
        <select
          :value="orderType"
          @change="$emit('update:orderType', $event.target.value)"
          class="input text-sm"
        >
          <option value="CASH">现款</option>
          <option value="CREDIT">账期</option>
          <option value="CONSIGN_OUT">寄售调拨</option>
          <option value="CONSIGN_SETTLE">寄售结算</option>
          <option value="RETURN">退货</option>
        </select>
      </div>

      <!-- 退货订单搜索 -->
      <div class="mb-2" v-if="orderType === 'RETURN'">
        <div class="relative">
          <input
            :value="returnOrderSearch"
            @input="$emit('update:returnOrderSearch', $event.target.value); $emit('search-return-orders')"
            @focus="$emit('update:returnOrderDropdown', true)"
            class="input text-sm w-full"
            placeholder="搜索原始销售订单 *"
            autocomplete="off"
          >
          <!-- 退货订单下拉列表 -->
          <div
            v-if="returnOrderDropdown && filteredReturnOrders.length"
            class="absolute bottom-full mb-1 w-full bg-surface border rounded shadow-lg max-h-60 overflow-y-auto"
            style="z-index: 30"
          >
            <div
              v-for="o in filteredReturnOrders"
              :key="o.id"
              @click="$emit('select-return-order', o)"
              class="px-3 py-2 hover:bg-elevated cursor-pointer border-b"
            >
              <div class="font-medium text-sm">{{ o.order_no }}</div>
              <div class="text-xs text-muted">{{ o.customer_name }} &middot; {{ o.created_at.split('T')[0] }} &middot; &yen;{{ o.total_amount }}</div>
            </div>
          </div>
          <!-- 关闭下拉的遮罩 -->
          <div v-if="returnOrderDropdown" @click="$emit('update:returnOrderDropdown', false)" class="fixed inset-0" style="z-index: 20"></div>
        </div>
      </div>

      <!-- 多账套分组小计 -->
      <div v-if="isMultiAccountSet" class="mb-2 space-y-1">
        <div v-for="group in itemsByAccountSet" :key="'t-' + group.key" class="flex justify-between text-xs text-secondary">
          <span>{{ group.name }}</span>
          <span class="font-mono">&yen;{{ fmt(group.subtotal) }}</span>
        </div>
        <div class="border-t pt-1 flex justify-between">
          <span class="text-sm">合计</span>
          <span class="text-lg font-bold text-primary">&yen;{{ fmt(cartTotal) }}</span>
        </div>
      </div>
      <!-- 单账套合计 -->
      <div v-else class="flex justify-between mb-2">
        <span class="text-sm">合计</span>
        <span class="text-lg font-bold text-primary">&yen;{{ fmt(cartTotal) }}</span>
      </div>
      <!-- 提交按钮 -->
      <button @click="$emit('submit')" class="btn btn-primary w-full text-sm" :disabled="!cart.length">提交订单</button>
    </div>
  </div>
</template>

<script setup>
/**
 * 购物车组件
 * 通过 props 接收数据，emit 事件回传操作
 * 支持多账套分组展示
 */
import { computed } from 'vue'
import { useFormat } from '../../../composables/useFormat'
import { useWarehousesStore } from '../../../stores/warehouses'
import SearchableSelect from '../../common/SearchableSelect.vue'
import CartItem from './CartItem.vue'

const props = defineProps({
  /** 购物车数据 */
  cart: Array,
  /** 订单类型 */
  orderType: String,
  /** 客户 ID */
  customerId: [String, Number],
  /** 业务员 ID */
  employeeId: [String, Number],
  /** 客户列表 */
  customers: Array,
  /** 业务员列表 */
  employees: Array,
  /** 仓库列表 */
  warehouses: Array,
  /** 购物车合计金额 */
  cartTotal: Number,
  /** 是否必须选择客户 */
  needCustomer: Boolean,
  /** 退货订单搜索关键词 */
  returnOrderSearch: String,
  /** 退货订单下拉是否显示 */
  returnOrderDropdown: Boolean,
  /** 过滤后的退货订单列表 */
  filteredReturnOrders: Array,
  /** 已选退货关联订单 */
  selectedReturnOrder: Object,
  /** 获取购物车行可用库存的函数 */
  getCartStock: Function
})

const emit = defineEmits([
  'clear', 'submit', 'remove-item',
  'duplicate-line', 'increment-quantity',
  'update-warehouse', 'update-location',
  'update:customerId', 'update:employeeId', 'update:orderType',
  'update:returnOrderSearch', 'update:returnOrderDropdown',
  'search-return-orders', 'select-return-order'
])

const { fmt } = useFormat()
const warehousesStore = useWarehousesStore()

const customerOptions = computed(() =>
  (props.customers || []).map(c => ({
    id: c.id,
    label: c.name,
    sublabel: c.phone || ''
  }))
)

/**
 * 获取购物车商品可选仓位列表
 * @param {Object} item - 购物车行
 */
const getCartItemLocations = (item) => {
  if (!item.warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(item.warehouse_id)
}

/**
 * 获取行对应的仓库对象
 */
const getItemWarehouse = (item) => {
  if (!item.warehouse_id) return null
  return (props.warehouses || []).find(w => w.id === parseInt(item.warehouse_id))
}

/**
 * 按账套分组的购物车商品
 * 每个分组包含 key、name、items（带原始索引）、subtotal
 */
const itemsByAccountSet = computed(() => {
  const groups = new Map()
  const cart = props.cart || []
  for (let idx = 0; idx < cart.length; idx++) {
    const item = cart[idx]
    const wh = getItemWarehouse(item)
    const asId = wh?.account_set_id || 0
    const asName = wh?.account_set_name || '未关联账套'
    if (!groups.has(asId)) {
      groups.set(asId, { key: asId, name: asName, items: [], subtotal: 0 })
    }
    const group = groups.get(asId)
    group.items.push({ item, idx })
    group.subtotal += Math.round(item.unit_price * item.quantity * 100) / 100
  }
  return [...groups.values()]
})

/**
 * 是否为多账套购物车
 */
const isMultiAccountSet = computed(() => {
  return itemsByAccountSet.value.length > 1
})
</script>
