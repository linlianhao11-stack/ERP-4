<template>
  <div class="md:flex md:gap-5 md:items-start">
    <!-- Product list (left) -->
    <div class="flex-1 md:min-w-0 mb-4 md:mb-0">
      <!-- Filters row -->
      <div class="flex flex-wrap gap-2 mb-3">
        <select v-model="saleForm.warehouse_id" class="input w-auto text-sm">
          <option value="">筛选仓库（可选）</option>
          <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
          <template v-if="showVirtualStock">
            <option v-for="vw in virtualWarehouses" :key="'v' + vw.id" :value="vw.id">{{ vw.name }}</option>
          </template>
        </select>
        <label class="flex items-center gap-1.5 text-xs text-[#86868b] cursor-pointer whitespace-nowrap select-none">
          <span class="toggle">
            <input type="checkbox" v-model="showVirtualStock" @change="onToggleVirtualStock">
            <span class="slider"></span>
          </span>
          寄售
        </label>
        <select v-model="saleForm.location_id" class="input w-auto text-sm" v-show="saleForm.warehouse_id">
          <option value="">筛选仓位（可选）</option>
          <option v-for="loc in filterLocations" :key="loc.id" :value="loc.id">{{ loc.code }}</option>
        </select>
        <input v-model="productSearch" class="input flex-1 text-sm" placeholder="搜索商品...">
        <div v-if="saleForm.order_type === 'RETURN' && selectedReturnOrder" class="w-full text-sm px-3 py-2 bg-[#e8f4fd] rounded border border-[#b3d7f5] text-[#0071e3]">
          <span class="font-medium">退货订单：</span>{{ selectedReturnOrder.order_no }} - {{ selectedReturnOrder.customer_name }}
        </div>
      </div>

      <!-- Product table -->
      <div class="card">
        <div class="table-container">
          <table class="w-full text-sm">
            <thead class="bg-[#f5f5f7]">
              <tr>
                <th class="px-3 py-2 text-left w-24 md-hide">品牌</th>
                <th class="px-3 py-2 text-left">商品名称</th>
                <th class="px-3 py-2 text-left w-24 md-hide">仓位</th>
                <th class="px-3 py-2 text-right w-24">零售价</th>
                <th class="px-3 py-2 text-right w-24 md-hide" v-if="hasPermission('finance')">成本价</th>
                <th class="px-3 py-2 text-center w-20">库存</th>
                <th class="px-3 py-2 text-center w-20 md-hide">库龄</th>
                <th class="px-3 py-2 text-center w-16">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr
                v-for="p in displayProducts"
                :key="p.id + '-' + (p.stock_key || '')"
                @click="!p.is_virtual_stock && addToCart(p)"
                class="hover:bg-[#f5f5f7]"
                :class="{
                  'bg-[#e8f4fd]': !p.is_virtual_stock && cart.some(c => c.product_id === p.id),
                  'bg-[#f3eef8]': p.is_virtual_stock,
                  'cursor-pointer': !p.is_virtual_stock
                }"
              >
                <td class="px-3 py-2 text-[#6e6e73] text-xs md-hide">{{ p.brand || '-' }}</td>
                <td class="px-3 py-2">
                  <div class="font-medium">{{ p.name }}</div>
                  <div class="text-xs text-[#86868b] font-mono mt-0.5">{{ p.sku }}</div>
                </td>
                <td class="px-3 py-2 md-hide">
                  <span v-if="p.is_virtual_stock" class="badge badge-purple text-xs">寄售</span>
                  <span v-else-if="p.location_code" class="badge badge-blue text-xs">{{ p.location_code }}</span>
                  <span v-else class="text-[#86868b] text-xs">-</span>
                </td>
                <td class="px-3 py-2 text-right text-[#0071e3] font-bold">&yen;{{ p.retail_price }}</td>
                <td class="px-3 py-2 text-right text-[#6e6e73] md-hide" v-if="hasPermission('finance')">&yen;{{ p.cost_price }}</td>
                <td
                  class="px-3 py-2 text-center font-semibold"
                  :class="p.is_virtual_stock ? 'text-[#af52de]' : getAgeClass(p.age_days)"
                >
                  {{ p.display_stock !== undefined ? p.display_stock : getStock(p) }}
                </td>
                <td class="px-3 py-2 text-center text-xs md-hide" :class="getAgeClass(p.age_days)">{{ p.age_days }}天</td>
                <td class="px-3 py-2 text-center">
                  <button
                    v-if="!p.is_virtual_stock"
                    @click.stop="addToCart(p)"
                    class="text-[#0071e3] text-xs font-semibold hover:underline"
                  >加入</button>
                  <span v-else class="text-xs text-[#86868b]">只读</span>
                </td>
              </tr>
              <tr v-if="!displayProducts.length">
                <td :colspan="hasPermission('finance') ? 8 : 7" class="px-3 py-8 text-center text-[#86868b]">暂无商品</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Cart (right) -->
    <div class="card md:w-72 flex flex-col md:sticky md:top-4" style="max-height: calc(100vh - 2rem)">
      <div class="p-3 border-b flex justify-between items-center">
        <h3 class="font-semibold text-sm">购物车({{ cart.length }})</h3>
        <button @click="cart = []" class="text-[#ff3b30] text-xs" v-show="cart.length">清空</button>
      </div>
      <div class="flex-1 overflow-y-auto cart-items">
        <div v-for="(item, idx) in cart" :key="item._id" class="p-2 border-b">
          <div class="flex justify-between items-center mb-1">
            <div class="font-medium truncate text-sm flex-1">{{ item.name }}</div>
            <div class="flex gap-1 ml-2">
              <button
                v-if="saleForm.order_type !== 'RETURN' && saleForm.order_type !== 'CONSIGN_SETTLE'"
                @click="duplicateCartLine(idx)"
                class="w-5 h-5 rounded-full bg-[#e8f4fd] text-[#0071e3] text-xs font-bold flex items-center justify-center hover:bg-[#d1e8f8]"
                title="从其他仓库再出一行"
              >+</button>
              <button
                @click="cart.splice(idx, 1)"
                class="w-5 h-5 rounded-full bg-[#ffeaee] text-[#ff3b30] text-xs font-bold flex items-center justify-center hover:bg-[#ffd6d6]"
                title="删除"
              >-</button>
            </div>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <span class="text-[#86868b]">&yen;</span>
            <input v-model.number="item.unit_price" type="number" step="0.01" class="input input-sm w-16 text-right">
            <span class="text-[#86868b]">&times;</span>
            <button @click="item.quantity = Math.max(1, item.quantity - 1)" class="w-6 h-6 rounded border text-xs">-</button>
            <span class="w-5 text-center">{{ item.quantity }}</span>
            <button
              @click="incrementQuantity(item)"
              class="w-6 h-6 rounded border text-xs"
            >+</button>
          </div>
          <div v-if="saleForm.order_type !== 'CONSIGN_SETTLE'" class="mt-2 space-y-1">
            <select
              v-model="item.warehouse_id"
              @change="updateCartWarehouse(idx, item.warehouse_id)"
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
              @change="updateCartLocation(idx, item.location_id)"
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
            <div v-if="item.warehouse_id && item.location_id" class="text-xs text-[#6e6e73]">
              可用库存:
              <span :class="getCartStock(item) >= item.quantity ? 'text-[#34c759] font-semibold' : 'text-[#ff3b30] font-semibold'">
                {{ getCartStock(item) }}
              </span> 件
            </div>
          </div>
          <div v-if="saleForm.order_type === 'RETURN' && item.max_return_qty" class="text-xs text-[#ff9f0a] mt-1">
            最多可退: {{ item.max_return_qty }} 件
          </div>
          <div class="text-right text-[#0071e3] font-semibold text-sm mt-1">
            &yen;{{ (Math.round(item.unit_price * item.quantity * 100) / 100).toFixed(2) }}
          </div>
        </div>
        <div v-if="!cart.length" class="text-[#86868b] text-center py-6 text-sm">空</div>
      </div>

      <!-- Cart footer -->
      <div class="p-3 border-t">
        <div class="mb-2">
          <select v-model="saleForm.customer_id" class="input text-sm">
            <option value="">选客户({{ needCustomer ? '必选' : '可选' }})</option>
            <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>
        <div class="mb-2">
          <select v-model="saleForm.salesperson_id" class="input text-sm">
            <option value="">选销售员(可选)</option>
            <option v-for="s in salespersons" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="mb-2">
          <select v-model="saleForm.order_type" class="input text-sm">
            <option value="CASH">现款</option>
            <option value="CREDIT">账期</option>
            <option value="CONSIGN_OUT">寄售调拨</option>
            <option value="CONSIGN_SETTLE">寄售结算</option>
            <option value="RETURN">退货</option>
          </select>
        </div>

        <!-- Return order search -->
        <div class="mb-2" v-if="saleForm.order_type === 'RETURN'">
          <div class="relative">
            <input
              v-model="returnOrderSearch"
              @input="searchReturnOrders"
              @focus="returnOrderDropdown = true"
              class="input text-sm w-full"
              placeholder="搜索原始销售订单 *"
              autocomplete="off"
            >
            <div
              v-if="returnOrderDropdown && filteredReturnOrders.length"
              class="absolute bottom-full mb-1 w-full bg-white border rounded shadow-lg max-h-60 overflow-y-auto"
              style="z-index: 30"
            >
              <div
                v-for="o in filteredReturnOrders"
                :key="o.id"
                @click="selectReturnOrder(o)"
                class="px-3 py-2 hover:bg-[#f5f5f7] cursor-pointer border-b"
              >
                <div class="font-medium text-sm">{{ o.order_no }}</div>
                <div class="text-xs text-[#86868b]">{{ o.customer_name }} &middot; {{ o.created_at.split('T')[0] }} &middot; &yen;{{ o.total_amount }}</div>
              </div>
            </div>
            <div v-if="returnOrderDropdown" @click="returnOrderDropdown = false" class="fixed inset-0" style="z-index: 20"></div>
          </div>
        </div>

        <div class="flex justify-between mb-2">
          <span class="text-sm">合计</span>
          <span class="text-lg font-bold text-[#0071e3]">&yen;{{ fmt(cartTotal) }}</span>
        </div>
        <button @click="submitOrder" class="btn btn-primary w-full text-sm" :disabled="!cart.length">提交订单</button>
      </div>
    </div>
  </div>

  <!-- Order Confirmation Modal -->
  <!-- This is rendered inside the global modal when appStore.modal.type === 'order_confirm' -->
  <teleport to="body">
    <div v-if="appStore.modal.show && appStore.modal.type === 'order_confirm'" class="modal-overlay" @click.self="appStore.closeModal()">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3 class="modal-title">确认提交订单</h3>
          <button @click="appStore.closeModal()" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <!-- Order summary -->
          <div class="mb-4 p-3 bg-[#e8f4fd] rounded-lg border border-[#b3d7f5]">
            <div class="flex justify-between items-start mb-3">
              <div class="font-semibold text-lg text-[#0071e3]">订单确认</div>
              <span :class="orderTypeBadges[orderConfirm.order_type] || 'badge badge-gray'">
                {{ orderTypeNames[orderConfirm.order_type] || orderConfirm.order_type }}
              </span>
            </div>
            <div class="grid form-grid grid-cols-2 gap-2 text-sm">
              <div><span class="text-[#6e6e73]">客户:</span> <span class="font-medium">{{ orderConfirm.customer?.name || '-' }}</span></div>
              <div><span class="text-[#6e6e73]">订单金额:</span> <span class="font-semibold text-lg text-[#0071e3]">&yen;{{ fmt(orderConfirm.total) }}</span></div>
            </div>
          </div>

          <!-- Salesperson -->
          <div class="mb-4">
            <label class="label">销售员（可选）</label>
            <select v-model="orderConfirm.salesperson_id" class="input text-sm">
              <option value="">不指定销售员</option>
              <option v-for="s in salespersons" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>

          <!-- Item details -->
          <div class="font-semibold mb-2 text-sm">商品明细（共{{ orderConfirm.items.length }}种商品）</div>
          <div class="mb-4 max-h-64 overflow-y-auto border rounded-lg">
            <table class="w-full text-sm">
              <thead class="bg-[#f5f5f7] sticky top-0">
                <tr>
                  <th class="px-3 py-2 text-left">商品</th>
                  <th class="px-3 py-2 text-left">出库仓位</th>
                  <th class="px-3 py-2 text-right">单价</th>
                  <th class="px-3 py-2 text-right">数量</th>
                  <th class="px-3 py-2 text-right">小计</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr v-for="(item, idx) in orderConfirm.items" :key="idx">
                  <td class="px-3 py-2"><div class="font-medium">{{ item.name }}</div></td>
                  <td class="px-3 py-2">
                    <span class="text-xs bg-[#e8f4fd] text-[#0071e3] px-2 py-1 rounded">{{ item.warehouse_name }} - {{ item.location_code }}</span>
                  </td>
                  <td class="px-3 py-2 text-right">&yen;{{ fmt(item.unit_price) }}</td>
                  <td class="px-3 py-2 text-right font-medium">{{ item.quantity }}</td>
                  <td class="px-3 py-2 text-right font-semibold text-[#0071e3]">&yen;{{ fmt(Math.round(item.unit_price * item.quantity * 100) / 100) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Return refund checkbox -->
          <div v-if="orderConfirm.order_type === 'RETURN'" class="mb-4 p-3 bg-[#fff8e1] border border-[#ffe082] rounded-lg">
            <label class="flex items-center cursor-pointer">
              <input type="checkbox" v-model="orderConfirm.refunded" class="mr-2 w-4 h-4">
              <span class="font-medium text-sm">已退款给客户</span>
            </label>
            <div class="text-xs text-[#6e6e73] mt-2">
              <div class="mb-1"><b>已勾选</b>：货款已经退还给客户，不产生在账资金</div>
              <div><b>未勾选</b>：货款未退还，将形成客户的在账资金（预付款），下次购货时可以抵扣</div>
            </div>
          </div>

          <!-- Use credit checkbox -->
          <div v-if="orderConfirm.order_type === 'CASH' && orderConfirm.available_credit > 0" class="mb-4 p-3 bg-[#e8f4fd] border border-[#b3d7f5] rounded-lg">
            <label class="flex items-center cursor-pointer">
              <input type="checkbox" v-model="orderConfirm.use_credit" class="mr-2 w-4 h-4">
              <span class="font-medium text-sm">使用在账资金</span>
            </label>
            <div class="text-xs text-[#6e6e73] mt-2">
              <div class="mb-1">该客户有 <b class="text-[#0071e3]">&yen;{{ fmt(orderConfirm.available_credit) }}</b> 在账资金可用</div>
              <div>勾选后将自动抵扣，最多抵扣 &yen;{{ fmt(Math.min(orderConfirm.available_credit, orderConfirm.total)) }}</div>
            </div>
          </div>

          <!-- Use rebate -->
          <div
            v-if="['CASH', 'CREDIT', 'CONSIGN_SETTLE'].includes(orderConfirm.order_type) && orderConfirm.rebate_balance > 0"
            class="mb-4 p-3 bg-[#e8f8ee] border border-[#a8e6c1] rounded-lg"
          >
            <label class="flex items-center cursor-pointer mb-2">
              <input
                type="checkbox"
                v-model="orderConfirm.use_rebate"
                class="mr-2 w-4 h-4"
                @change="!orderConfirm.use_rebate && orderConfirm.items.forEach(i => i.rebate_amount = 0)"
              >
              <span class="font-medium text-sm">使用返利</span>
              <span class="text-xs text-[#34c759] ml-2">可用: &yen;{{ fmt(orderConfirm.rebate_balance) }}</span>
            </label>
            <div v-if="orderConfirm.use_rebate">
              <div class="max-h-48 overflow-y-auto border rounded-lg bg-white">
                <table class="w-full text-xs">
                  <thead class="bg-[#f5f5f7] sticky top-0">
                    <tr>
                      <th class="px-2 py-1 text-left">商品</th>
                      <th class="px-2 py-1 text-right">数量</th>
                      <th class="px-2 py-1 text-right">原单价</th>
                      <th class="px-2 py-1 text-right">返利金额</th>
                      <th class="px-2 py-1 text-right">实际小计</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y">
                    <tr v-for="(item, idx) in orderConfirm.items" :key="idx">
                      <td class="px-2 py-1">{{ item.name }}</td>
                      <td class="px-2 py-1 text-right">{{ item.quantity }}</td>
                      <td class="px-2 py-1 text-right">&yen;{{ fmt(item.unit_price) }}</td>
                      <td class="px-2 py-1 text-right">
                        <input
                          v-model.number="item.rebate_amount"
                          type="number"
                          step="0.01"
                          min="0"
                          :max="item.unit_price * item.quantity"
                          class="w-20 text-right border rounded px-1 py-0.5 text-xs"
                          placeholder="0"
                        >
                      </td>
                      <td class="px-2 py-1 text-right font-semibold">&yen;{{ fmt(item.unit_price * item.quantity - (item.rebate_amount || 0)) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="flex justify-between mt-2 text-sm">
                <span class="text-[#34c759]">返利总额: <b>&yen;{{ fmt(rebateTotal) }}</b></span>
                <span class="font-semibold">抵扣后总额: <b class="text-[#0071e3]">&yen;{{ fmt(orderConfirm.total - rebateTotal) }}</b></span>
              </div>
              <div v-if="rebateTotal > orderConfirm.rebate_balance" class="text-xs text-[#ff3b30] mt-1">返利总额超过可用余额!</div>
            </div>
          </div>

          <!-- Payment method -->
          <div v-if="orderConfirm.order_type === 'CASH'" class="mb-4">
            <label class="label">收款方式 *</label>
            <select v-model="orderConfirm.payment_method" class="input text-sm">
              <option v-for="pm in paymentMethods" :key="pm.code" :value="pm.code">{{ pm.name }}</option>
            </select>
          </div>

          <!-- Account set -->
          <div v-if="accountSets.length" class="mb-4">
            <label class="label">财务账套（可选）</label>
            <select v-model="orderConfirm.account_set_id" class="input text-sm">
              <option :value="null">不指定</option>
              <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
            <div class="text-xs text-[#86868b] mt-1">选择仓库后将自动带入关联账套，也可手动修改</div>
          </div>

          <!-- Remark -->
          <div class="mb-4">
            <label class="label">订单备注（可选）</label>
            <textarea v-model="orderConfirm.remark" class="input text-sm" rows="3" placeholder="输入订单备注信息..."></textarea>
            <div class="text-xs text-[#86868b] mt-1">备注信息将保存在订单中，可在订单详情中查看</div>
          </div>

          <!-- Action buttons -->
          <div class="flex gap-3 pt-3">
            <button type="button" @click="appStore.closeModal()" class="btn btn-secondary flex-1">取消</button>
            <button type="button" @click="confirmSubmitOrder" :disabled="appStore.submitting" class="btn btn-primary flex-1">
              {{ appStore.submitting ? '提交中...' : '确认提交' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'
import { useProductsStore } from '../stores/products'
import { useWarehousesStore } from '../stores/warehouses'
import { useCustomersStore } from '../stores/customers'
import { useSettingsStore } from '../stores/settings'
import { useFormat } from '../composables/useFormat'
import { usePermission } from '../composables/usePermission'
import { getOrders, getOrder, createOrder } from '../api/orders'
import { getWarehouses } from '../api/warehouses'
import { getAccountSets } from '../api/accounting'
import { fuzzyMatchAny } from '../utils/helpers'
import { orderTypeNames, orderTypeBadges } from '../utils/constants'

const authStore = useAuthStore()
const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const customersStore = useCustomersStore()
const settingsStore = useSettingsStore()

const { fmt, getAgeClass } = useFormat()
const { hasPermission } = usePermission()

// Aliases from stores
const products = computed(() => productsStore.products)
const warehouses = computed(() => warehousesStore.warehouses)
const locations = computed(() => warehousesStore.locations)
const customers = computed(() => customersStore.customers)
const salespersons = computed(() => settingsStore.salespersons)
const paymentMethods = computed(() => settingsStore.paymentMethods)

// ---------- Local state ----------
const accountSets = ref([])
const productSearch = ref('')
const showVirtualStock = ref(false)
const virtualWarehouses = ref([])

const cart = ref([])

const saleForm = reactive({
  order_type: 'CASH',
  warehouse_id: '',
  location_id: '',
  customer_id: '',
  salesperson_id: '',
  related_order_id: '',
  remark: ''
})

const returnOrderSearch = ref('')
const returnOrderDropdown = ref(false)
const salesOrders = ref([])
const selectedReturnOrder = ref(null)

const orderConfirm = ref({
  items: [],
  customer: null,
  total: 0,
  order_type: '',
  refunded: false,
  use_credit: false,
  available_credit: 0,
  use_rebate: false,
  rebate_balance: 0,
  salesperson_id: '',
  remark: '',
  payment_method: 'cash',
  account_set_id: null
})

// ---------- Computed ----------
const filteredProducts = computed(() => {
  const kw = productSearch.value
  if (!kw) return products.value
  return products.value.filter(p => fuzzyMatchAny([p.sku, p.name, p.brand, p.category], kw))
})

const displayProducts = computed(() => {
  // RETURN type with selected return order
  if (saleForm.order_type === 'RETURN' && selectedReturnOrder.value?.items) {
    const result = []
    selectedReturnOrder.value.items.forEach(item => {
      const availableQty = item.available_return_quantity || 0
      if (availableQty <= 0) return
      const product = products.value.find(p => p.id === item.product_id)
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
            max_return_qty: availableQty
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

  // Normal mode
  const filtered = filteredProducts.value
  const result = []
  filtered.forEach(p => {
    if (p.stocks && p.stocks.length > 0) {
      p.stocks.forEach(s => {
        if (!showVirtualStock.value && s.is_virtual) return
        if (saleForm.warehouse_id && s.warehouse_id != saleForm.warehouse_id) return
        if (saleForm.location_id && s.location_id != saleForm.location_id) return
        result.push({
          ...p,
          location_code: s.location_code,
          stock_key: s.warehouse_id + '-' + s.location_id,
          display_stock: s.available_qty ?? s.quantity,
          warehouse_id: s.warehouse_id,
          location_id: s.location_id,
          is_virtual_stock: !!s.is_virtual,
          virtual_warehouse_name: s.warehouse_name || ''
        })
      })
    }
  })
  return result
})

const cartTotal = computed(() => cart.value.reduce((s, i) => s + Math.round(i.quantity * i.unit_price * 100) / 100, 0))

const needCustomer = computed(() => ['CASH', 'CREDIT', 'CONSIGN_OUT', 'CONSIGN_SETTLE', 'RETURN'].includes(saleForm.order_type))

const filteredReturnOrders = computed(() => {
  const kw = returnOrderSearch.value
  if (!kw) return salesOrders.value.slice(0, 20)
  return salesOrders.value.filter(o => fuzzyMatchAny([o.order_no, o.customer_name], kw)).slice(0, 20)
})

const rebateTotal = computed(() => orderConfirm.value.items.reduce((s, i) => s + (i.rebate_amount || 0), 0))

const filterLocations = computed(() => {
  if (!saleForm.warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(saleForm.warehouse_id)
})

const getCartItemLocations = (item) => {
  if (!item.warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(item.warehouse_id)
}

// ---------- Functions ----------
const getStock = (p) => {
  if (saleForm.order_type === 'CONSIGN_SETTLE') return p.stocks?.find(s => s.is_virtual)?.quantity || 0
  if (saleForm.warehouse_id) {
    const s = p.stocks?.find(s => s.warehouse_id == saleForm.warehouse_id)
    return s ? (s.available_qty ?? s.quantity) : 0
  }
  return p.total_stock || 0
}

const onToggleVirtualStock = async () => {
  if (showVirtualStock.value && !virtualWarehouses.value.length) {
    try {
      const { data } = await getWarehouses({ include_virtual: true })
      virtualWarehouses.value = data.filter(w => w.is_virtual)
    } catch (e) {
      console.error(e)
      appStore.showToast(e.response?.data?.detail || '加载数据失败', 'error')
    }
  }
}

let _cartIdCounter = 0
const addToCart = (p) => {
  const stock = getStock(p)
  if (stock <= 0 && saleForm.order_type !== 'RETURN') {
    appStore.showToast('库存不足', 'error')
    return
  }

  if (saleForm.order_type === 'RETURN') {
    const e = cart.value.find(c => c.product_id === p.id)
    const maxQty = p.max_return_qty || p.original_quantity || 0
    if (e) {
      if (e.quantity >= maxQty) {
        appStore.showToast(`最多只能退${maxQty}件`, 'error')
        return
      }
      e.quantity++
    } else {
      cart.value.push({
        _id: ++_cartIdCounter,
        product_id: p.id,
        name: p.name,
        unit_price: p.retail_price,
        quantity: 1,
        max_return_qty: maxQty,
        warehouse_id: p.warehouse_id || '',
        location_id: p.location_id || '',
        stocks: p.stocks || []
      })
    }
  } else {
    const e = cart.value.find(c => c.product_id === p.id && (!c.warehouse_id || c.warehouse_id === ''))
    if (e) {
      e.quantity++
    } else {
      const hasLine = cart.value.some(c => c.product_id === p.id)
      if (hasLine) {
        const last = cart.value.filter(c => c.product_id === p.id).pop()
        last.quantity++
      } else {
        const fullProduct = products.value.find(prod => prod.id === p.id)
        cart.value.push({
          _id: ++_cartIdCounter,
          product_id: p.id,
          name: p.name,
          unit_price: p.retail_price,
          quantity: 1,
          warehouse_id: '',
          location_id: '',
          stocks: fullProduct?.stocks || []
        })
      }
    }
  }
}

const incrementQuantity = (item) => {
  if (saleForm.order_type === 'RETURN' && item.max_return_qty && item.quantity >= item.max_return_qty) {
    appStore.showToast('最多只能退' + item.max_return_qty + '件', 'error')
  } else {
    item.quantity++
  }
}

const duplicateCartLine = (idx) => {
  const item = cart.value[idx]
  const fullProduct = products.value.find(prod => prod.id === item.product_id)
  cart.value.splice(idx + 1, 0, {
    _id: ++_cartIdCounter,
    product_id: item.product_id,
    name: item.name,
    unit_price: item.unit_price,
    quantity: 1,
    warehouse_id: '',
    location_id: '',
    stocks: fullProduct?.stocks || item.stocks || []
  })
}

const updateCartWarehouse = (idx, warehouseId) => {
  cart.value[idx].warehouse_id = warehouseId
  cart.value[idx].location_id = ''
}

const updateCartLocation = (idx, locationId) => {
  cart.value[idx].location_id = locationId
}

const getCartStock = (item) => {
  if (!item.warehouse_id || !item.location_id) return 0
  const stock = item.stocks?.find(s => s.warehouse_id === parseInt(item.warehouse_id) && s.location_id === parseInt(item.location_id))
  return stock ? (stock.available_qty ?? stock.quantity) : 0
}

let _returnOrderAbort = null
const searchReturnOrders = async () => {
  if (saleForm.order_type !== 'RETURN') return
  // 取消上次进行中的请求，避免竞态
  if (_returnOrderAbort) _returnOrderAbort.abort()
  const controller = new AbortController()
  _returnOrderAbort = controller
  try {
    const { data } = await getOrders({ limit: 200 }, { signal: controller.signal })
    salesOrders.value = data.filter(o => ['CASH', 'CREDIT'].includes(o.order_type))
  } catch (e) {
    if (e?.code === 'ERR_CANCELED') return
    appStore.showToast(e.response?.data?.detail || '加载订单失败', 'error')
  } finally {
    if (_returnOrderAbort === controller) _returnOrderAbort = null
  }
}

const selectReturnOrder = async (o) => {
  returnOrderSearch.value = o.order_no + ' - ' + o.customer_name
  saleForm.related_order_id = o.id
  saleForm.customer_id = o.customer_id
  returnOrderDropdown.value = false
  try {
    const { data } = await getOrder(o.id)
    selectedReturnOrder.value = data
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
  }
}

const submitOrder = () => {
  if (!cart.value.length) return

  for (const item of cart.value) {
    if (!item.quantity || item.quantity <= 0) {
      appStore.showToast(`【${item.name}】数量必须大于0`, 'error')
      return
    }
    if (saleForm.order_type !== 'RETURN' && item.unit_price <= 0) {
      appStore.showToast(`【${item.name}】单价必须大于0`, 'error')
      return
    }
    if (saleForm.order_type === 'RETURN' && item.unit_price < 0) {
      appStore.showToast(`【${item.name}】单价不能为负数`, 'error')
      return
    }
  }

  if (needCustomer.value && !saleForm.customer_id) {
    appStore.showToast('请选择客户', 'error')
    return
  }

  if (saleForm.order_type === 'RETURN') {
    if (!saleForm.related_order_id) {
      appStore.showToast('退货请选择原始销售订单', 'error')
      return
    }
  }

  // Validate warehouse/location for non-CONSIGN_SETTLE and non-RETURN
  if (saleForm.order_type !== 'CONSIGN_SETTLE' && saleForm.order_type !== 'RETURN') {
    for (let i = 0; i < cart.value.length; i++) {
      if (!cart.value[i].warehouse_id || !cart.value[i].location_id) {
        appStore.showToast(`请为【${cart.value[i].name}】选择仓库和仓位`, 'error')
        return
      }
    }
  }

  // Validate warehouse/location for RETURN
  if (saleForm.order_type === 'RETURN') {
    for (let i = 0; i < cart.value.length; i++) {
      if (!cart.value[i].warehouse_id || !cart.value[i].location_id) {
        appStore.showToast(`请为【${cart.value[i].name}】选择退货仓库和仓位`, 'error')
        return
      }
    }
  }

  const customer = customers.value.find(c => c.id === saleForm.customer_id)
  const total = cart.value.reduce((s, i) => s + Math.round(i.quantity * i.unit_price * 100) / 100, 0)
  const availableCredit = customer && customer.balance < 0 ? Math.abs(customer.balance) : 0
  const sp = salespersons.value.find(s => s.id === parseInt(saleForm.salesperson_id))
  const rebateBalance = customer?.rebate_balance || 0

  // Auto-detect account_set from the first cart item's warehouse
  let autoAccountSetId = null
  if (cart.value.length > 0 && cart.value[0].warehouse_id) {
    const firstWarehouse = warehouses.value.find(w => w.id === parseInt(cart.value[0].warehouse_id))
    if (firstWarehouse?.account_set_id) autoAccountSetId = firstWarehouse.account_set_id
  }

  orderConfirm.value = {
    items: cart.value.map(i => {
      const warehouse = warehouses.value.find(w => w.id === parseInt(i.warehouse_id))
      const location = locations.value.find(l => l.id === parseInt(i.location_id))
      return {
        ...i,
        warehouse_name: warehouse?.name || '-',
        location_code: location?.code || '-',
        rebate_amount: 0
      }
    }),
    customer: customer,
    order_type: saleForm.order_type,
    related_order_id: saleForm.related_order_id,
    total: total,
    refunded: false,
    use_credit: false,
    available_credit: availableCredit,
    use_rebate: false,
    rebate_balance: rebateBalance,
    salesperson_id: saleForm.salesperson_id || '',
    salesperson_name: sp?.name || '',
    remark: '',
    payment_method: 'cash',
    account_set_id: autoAccountSetId
  }

  appStore.openModal('order_confirm', '确认提交订单')
}

const confirmSubmitOrder = async () => {
  if (appStore.submitting) return

  const useRebate = orderConfirm.value.use_rebate
  const totalRebate = useRebate ? orderConfirm.value.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) : 0

  if (useRebate) {
    for (const item of orderConfirm.value.items) {
      if (item.rebate_amount && item.rebate_amount > item.unit_price * item.quantity) {
        appStore.showToast(`${item.name} 的返利金额不能超过商品小计`, 'error')
        return
      }
    }
  }

  if (useRebate && totalRebate > orderConfirm.value.rebate_balance) {
    appStore.showToast('返利总额超过可用余额', 'error')
    return
  }

  appStore.submitting = true
  try {
    const result = await createOrder({
      order_type: saleForm.order_type,
      customer_id: saleForm.customer_id || null,
      salesperson_id: orderConfirm.value.salesperson_id ? parseInt(orderConfirm.value.salesperson_id) : null,
      warehouse_id: null,
      location_id: null,
      related_order_id: saleForm.related_order_id || null,
      refunded: orderConfirm.value.refunded || false,
      use_credit: orderConfirm.value.use_credit || false,
      payment_method: orderConfirm.value.payment_method || null,
      rebate_amount: totalRebate > 0 ? totalRebate : null,
      items: cart.value.map((i, idx) => ({
        product_id: i.product_id,
        quantity: i.quantity,
        unit_price: i.unit_price,
        warehouse_id: i.warehouse_id ? parseInt(i.warehouse_id) : null,
        location_id: i.location_id ? parseInt(i.location_id) : null,
        rebate_amount: useRebate && orderConfirm.value.items[idx]?.rebate_amount ? orderConfirm.value.items[idx].rebate_amount : null
      })),
      remark: orderConfirm.value.remark || null,
      account_set_id: orderConfirm.value.account_set_id || null
    })

    let msg = '订单创建成功'
    if (result.data.rebate_used && result.data.rebate_used > 0) {
      msg += `，已使用返利 ¥${fmt(result.data.rebate_used)}`
    }
    if (result.data.credit_used && result.data.credit_used > 0) {
      msg += `，已使用在账资金 ¥${fmt(result.data.credit_used)}`
    }
    if (result.data.amount_due > 0) {
      msg += `，还需支付 ¥${fmt(result.data.amount_due)}`
    }
    appStore.showToast(msg)

    // Reset state
    cart.value = []
    saleForm.warehouse_id = ''
    saleForm.location_id = ''
    saleForm.salesperson_id = ''
    saleForm.related_order_id = ''
    saleForm.customer_id = ''
    saleForm.order_type = 'CASH'
    returnOrderSearch.value = ''
    selectedReturnOrder.value = null
    appStore.closeModal()

    // Reload data
    productsStore.loadProducts()
    customersStore.loadCustomers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '订单创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// ---------- Watchers ----------
watch(() => saleForm.warehouse_id, () => { saleForm.location_id = '' })

watch(() => saleForm.order_type, (newType, oldType) => {
  if ((newType === 'RETURN' && oldType !== 'RETURN') || (oldType === 'RETURN' && newType !== 'RETURN')) {
    cart.value = []
  }
  if (newType === 'RETURN') {
    searchReturnOrders()
  } else {
    returnOrderSearch.value = ''
    saleForm.related_order_id = ''
    selectedReturnOrder.value = null
  }
})

// ---------- Init ----------
onMounted(async () => {
  if (!products.value.length) productsStore.loadProducts()
  if (!warehouses.value.length) warehousesStore.loadWarehouses()
  if (!locations.value.length) warehousesStore.loadLocations()
  if (!customers.value.length) customersStore.loadCustomers()
  if (!salespersons.value.length) settingsStore.loadSalespersons()
  if (!paymentMethods.value.length) settingsStore.loadPaymentMethods()
  try {
    const { data } = await getAccountSets()
    accountSets.value = data
  } catch (e) { /* ignore */ }
})

onUnmounted(() => {
  if (_returnOrderAbort) _returnOrderAbort.abort()
})
</script>
