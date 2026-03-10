<!--
  购物车 - 销售页面右栏
  显示已选商品，支持数量调整、仓库仓位选择、订单提交
  所有状态通过 props 传入，修改通过 emit 回传
-->
<template>
  <div class="card md:w-72 flex flex-col md:sticky md:top-4" style="max-height: calc(100vh - 2rem)">
    <!-- 标题栏 -->
    <div class="p-3 border-b flex justify-between items-center">
      <h3 class="font-semibold text-sm">购物车({{ cart.length }})</h3>
      <button @click="$emit('clear')" class="text-error text-xs" v-show="cart.length">清空</button>
    </div>

    <!-- 购物车商品列表 -->
    <div class="flex-1 overflow-y-auto cart-items">
      <div v-for="(item, idx) in cart" :key="item._id" class="p-2 border-b">
        <!-- 商品名称和操作按钮 -->
        <div class="flex justify-between items-center mb-1">
          <div class="font-medium truncate text-sm flex-1">{{ item.name }}</div>
          <div class="flex gap-1 ml-2">
            <!-- 复制行按钮（非退货/寄售结算模式） -->
            <button
              v-if="orderType !== 'RETURN' && orderType !== 'CONSIGN_SETTLE'"
              @click="$emit('duplicate-line', idx)"
              class="w-5 h-5 rounded-full bg-info-subtle text-primary text-xs font-bold flex items-center justify-center hover:bg-info-subtle"
              title="从其他仓库再出一行"
            >+</button>
            <!-- 删除按钮 -->
            <button
              @click="$emit('remove-item', idx)"
              class="w-5 h-5 rounded-full bg-error-subtle text-error text-xs font-bold flex items-center justify-center hover:bg-error-subtle"
              title="删除"
            >-</button>
          </div>
        </div>

        <!-- 价格和数量调整 -->
        <div class="flex items-center gap-2 text-sm">
          <span class="text-muted">&yen;</span>
          <input v-model.number="item.unit_price" type="number" step="0.01" class="input input-sm w-16 text-right">
          <span class="text-muted">&times;</span>
          <button @click="item.quantity = Math.max(1, item.quantity - 1)" class="w-6 h-6 rounded border text-xs">-</button>
          <input
            v-model.number="item.quantity"
            type="number"
            min="1"
            class="input input-sm w-14 text-center"
            @blur="item.quantity = Math.max(1, Math.floor(item.quantity) || 1)"
          >
          <button
            @click="$emit('increment-quantity', item)"
            class="w-6 h-6 rounded border text-xs"
          >+</button>
        </div>

        <!-- 仓库/仓位选择（非寄售结算模式） -->
        <div v-if="orderType !== 'CONSIGN_SETTLE'" class="mt-2 space-y-1">
          <select
            v-model="item.warehouse_id"
            @change="$emit('update-warehouse', idx, item.warehouse_id)"
            class="input input-sm text-xs w-full"
          >
            <option value="">选择仓库 *</option>
            <option
              v-for="w in warehouses.filter(x => !x.is_virtual)"
              :key="w.id"
              :value="w.id"
            >{{ w.name }} (可用: {{ item.stocks?.filter(s => s.warehouse_id === w.id).reduce((sum, s) => sum + (s.available_qty ?? s.quantity), 0) || 0 }})</option>
          </select>
          <select
            v-model="item.location_id"
            @change="$emit('update-location', idx, item.location_id)"
            class="input input-sm text-xs w-full"
            :disabled="!item.warehouse_id"
          >
            <option value="">{{ item.warehouse_id ? '选择仓位 *' : '请先选择仓库' }}</option>
            <option
              v-for="loc in getCartItemLocations(item)"
              :key="loc.id"
              :value="loc.id"
            >{{ loc.code }} (可用: {{ (s => s ? (s.available_qty ?? s.quantity) : 0)(item.stocks?.find(s => s.warehouse_id === parseInt(item.warehouse_id) && s.location_id === loc.id)) }})</option>
          </select>
          <!-- 库存提示 -->
          <div v-if="item.warehouse_id && item.location_id" class="text-xs text-secondary">
            可用库存:
            <span :class="getCartStock(item) >= item.quantity ? 'text-success font-semibold' : 'text-error font-semibold'">
              {{ getCartStock(item) }}
            </span> 件
          </div>
        </div>

        <!-- 退货数量上限提示 -->
        <div v-if="orderType === 'RETURN' && item.max_return_qty" class="text-xs text-warning mt-1">
          最多可退: {{ item.max_return_qty }} 件
        </div>

        <!-- 行小计 -->
        <div class="text-right text-primary font-semibold text-sm mt-1">
          &yen;{{ (Math.round(item.unit_price * item.quantity * 100) / 100).toFixed(2) }}
        </div>
      </div>
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
      <!-- 销售员选择 -->
      <div class="mb-2">
        <select
          :value="salespersonId"
          @change="$emit('update:salespersonId', $event.target.value)"
          class="input text-sm"
        >
          <option value="">选销售员(可选)</option>
          <option v-for="s in salespersons" :key="s.id" :value="s.id">{{ s.name }}</option>
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

      <!-- 合计金额 -->
      <div class="flex justify-between mb-2">
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
 */
import { computed } from 'vue'
import { useFormat } from '../../../composables/useFormat'
import { useWarehousesStore } from '../../../stores/warehouses'
import SearchableSelect from '../../common/SearchableSelect.vue'

const props = defineProps({
  /** 购物车数据 */
  cart: Array,
  /** 订单类型 */
  orderType: String,
  /** 客户 ID */
  customerId: [String, Number],
  /** 销售员 ID */
  salespersonId: [String, Number],
  /** 客户列表 */
  customers: Array,
  /** 销售员列表 */
  salespersons: Array,
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
  'update:customerId', 'update:salespersonId', 'update:orderType',
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
</script>
