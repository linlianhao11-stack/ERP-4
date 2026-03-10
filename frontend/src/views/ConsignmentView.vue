<template>
  <div>
    <h2 class="text-lg font-bold mb-4">寄售管理</h2>

    <!-- Summary Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
      <div class="card p-3">
        <div class="text-xs text-muted">寄售库存(成本)</div>
        <div class="text-xl font-bold text-purple-emphasis">¥{{ fmt(consignSummary.total_cost_value) }}</div>
      </div>
      <div class="card p-3">
        <div class="text-xs text-muted">寄售库存(销售)</div>
        <div class="text-xl font-bold text-primary">¥{{ fmt(consignSummary.total_sales_value) }}</div>
      </div>
      <div class="card p-3">
        <div class="text-xs text-muted">结算欠款</div>
        <div class="text-xl font-bold text-error">¥{{ fmt(consignSummary.total_settle_unpaid) }}</div>
      </div>
      <div class="card p-3">
        <div class="text-xs text-muted">寄售数量</div>
        <div class="text-xl font-bold">{{ consignSummary.total_quantity }}</div>
      </div>
    </div>

    <!-- Customer List -->
    <div class="card mb-5">
      <div class="p-3 border-b font-semibold text-sm">寄售客户</div>
      <div class="divide-y">
        <div
          v-for="c in consignCustomers"
          :key="c.id"
          class="p-3 flex justify-between items-center hover:bg-elevated cursor-pointer"
          @click="openConsignDetail(c)"
        >
          <div>
            <div class="font-medium">{{ c.name }}</div>
            <div class="text-xs text-muted">调拨{{ c.consign_out_count }}次 / 结算{{ c.consign_settle_count }}次</div>
          </div>
          <div class="text-right">
            <div class="text-purple-emphasis font-semibold">库存¥{{ fmt(c.consign_remaining_cost) }}</div>
            <div class="text-xs" :class="getBalanceClass(c.balance)">{{ getBalanceLabel(c.balance) }} ¥{{ formatBalance(c.balance) }}</div>
          </div>
        </div>
        <div v-if="!consignCustomers.length" class="p-6 text-center text-muted text-sm">暂无寄售客户</div>
      </div>
    </div>

    <!-- Stock Detail Table -->
    <div class="card">
      <div class="p-3 border-b font-semibold text-sm">寄售库存明细</div>
      <div class="overflow-x-auto table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 text-left">SKU</th>
              <th class="px-3 py-2 text-left">商品</th>
              <th class="px-3 py-2 text-right">数量</th>
              <th v-if="hasPermission('finance')" class="px-3 py-2 text-right">成本</th>
              <th class="px-3 py-2 text-right">销售价</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="s in consignSummary.stock_details" :key="s.product_id + '-' + s.unit_price">
              <td class="px-3 py-2 font-mono text-xs">{{ s.product_sku }}</td>
              <td class="px-3 py-2">{{ s.product_name }}</td>
              <td class="px-3 py-2 text-right font-semibold">{{ s.quantity }}</td>
              <td v-if="hasPermission('finance')" class="px-3 py-2 text-right">{{ fmt(s.cost_price) }}</td>
              <td class="px-3 py-2 text-right">{{ fmt(s.unit_price) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!consignSummary.stock_details?.length" class="p-6 text-center text-muted text-sm">暂无寄售库存</div>
      </div>
    </div>

    <!-- Consign Detail Modal -->
    <teleport to="body">
      <div v-if="showDetailModal" class="modal-overlay" @click.self="closeDetailModal">
        <div class="modal-content">
          <div class="modal-header">
            <h3 class="font-semibold">寄售详情 - {{ consignDetail.customer?.name }}</h3>
            <button @click="closeDetailModal" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <!-- Customer Info Header -->
            <div class="mb-4 p-3 bg-elevated rounded-lg">
              <div class="flex justify-between items-center mb-2">
                <div>
                  <div class="font-semibold">{{ consignDetail.customer?.name }}</div>
                  <div class="text-sm text-muted">
                    <span :class="getBalanceClass(consignDetail.customer?.balance)">
                      {{ getBalanceLabel(consignDetail.customer?.balance) }}: ¥{{ formatBalance(consignDetail.customer?.balance) }}
                    </span>
                  </div>
                </div>
                <div class="flex gap-2" v-if="!consignSettleMode">
                  <button @click="openConsignReturn" class="btn btn-secondary btn-sm">寄售退货</button>
                  <button
                    @click="enterConsignSettle"
                    class="btn btn-warning btn-sm"
                    :disabled="!consignDetail.remaining_products?.length"
                  >结算</button>
                </div>
                <div v-else>
                  <button @click="consignSettleMode = false" class="btn btn-secondary btn-sm">取消结算</button>
                </div>
              </div>
            </div>

            <!-- Normal Mode: Show Remaining Products -->
            <div v-if="!consignSettleMode">
              <div class="mb-4">
                <div class="font-semibold mb-2 text-sm">待结算商品</div>
                <div class="space-y-1 max-h-40 overflow-y-auto">
                  <div
                    v-for="(p, idx) in consignDetail.remaining_products"
                    :key="p.product_id + '-' + p.unit_price"
                    class="flex justify-between items-center p-2 bg-elevated rounded text-sm"
                  >
                    <div>
                      <div>{{ p.product_name }}</div>
                      <div class="text-xs text-muted">{{ p.product_sku }}</div>
                    </div>
                    <div class="text-right">
                      <div class="font-semibold">{{ p.remaining_quantity }}件</div>
                      <div class="text-xs text-muted">¥{{ p.unit_price }}/件</div>
                    </div>
                  </div>
                  <div v-if="!consignDetail.remaining_products?.length" class="text-muted text-center py-3 text-sm">无待结算商品</div>
                </div>
              </div>
              <div class="flex gap-3 pt-3">
                <button type="button" @click="closeDetailModal" class="btn btn-secondary flex-1">关闭</button>
              </div>
            </div>

            <!-- Settle Mode: Enter Quantity and Price -->
            <div v-else>
              <div class="mb-2 p-2 bg-orange-subtle rounded border border-warning text-xs text-warning">
                输入各商品结算数量（不超过剩余数量），提交后生成寄售结算单
              </div>
              <div class="space-y-2 max-h-64 overflow-y-auto mb-3">
                <div
                  v-for="(item, idx) in consignSettleItems"
                  :key="item.product_id + '-' + item.unit_price"
                  class="p-3 bg-elevated rounded border"
                >
                  <div class="flex justify-between items-start mb-2">
                    <div>
                      <div class="font-medium text-sm">{{ item.product_name }}</div>
                      <div class="text-xs text-muted">{{ item.product_sku }}</div>
                    </div>
                    <div class="text-right text-xs text-muted">
                      剩余 <span class="font-semibold text-foreground">{{ item.remaining_quantity }}</span> 件
                    </div>
                  </div>
                  <div class="grid grid-cols-2 gap-2">
                    <div>
                      <label class="text-xs text-secondary">结算数量</label>
                      <input
                        type="number"
                        v-model.number="item.settle_quantity"
                        min="0"
                        :max="item.remaining_quantity"
                        class="input input-sm w-full"
                      >
                    </div>
                    <div>
                      <label class="text-xs text-secondary">单价</label>
                      <input
                        type="number"
                        v-model.number="item.unit_price"
                        min="0"
                        step="0.01"
                        class="input input-sm w-full"
                      >
                    </div>
                  </div>
                </div>
              </div>
              <div class="p-2 bg-info-subtle rounded text-sm mb-3">
                结算合计: <span class="font-bold text-primary">¥{{ fmt(settleTotal) }}</span>
                ({{ settleQuantity }}件)
              </div>
              <div class="flex gap-3 pt-3">
                <button type="button" @click="consignSettleMode = false" class="btn btn-secondary flex-1">取消</button>
                <button type="button" @click="submitConsignSettle" :disabled="appStore.submitting" class="btn btn-warning flex-1">{{ appStore.submitting ? '提交中...' : '确认结算' }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Consign Return Modal -->
    <teleport to="body">
      <div v-if="showReturnModal" class="modal-overlay" @click.self="closeReturnModal">
        <div class="modal-content">
          <div class="modal-header">
            <h3 class="font-semibold">寄售退货 - {{ consignDetail.customer?.name }}</h3>
            <button @click="closeReturnModal" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="mb-4 p-3 bg-error-subtle rounded-lg border border-error">
              <div class="font-semibold text-error mb-1">寄售退货</div>
              <div class="text-sm text-error">从客户虚拟仓调回商品到实际仓库</div>
            </div>
            <div class="mb-4">
              <div class="font-semibold mb-2 text-sm">可退商品列表</div>
              <div class="space-y-2 max-h-64 overflow-y-auto">
                <div
                  v-for="(p, idx) in consignReturnItems"
                  :key="p.product_id + '-' + (p.unit_price || idx)"
                  class="p-3 bg-elevated rounded border"
                >
                  <div class="flex justify-between items-start mb-2">
                    <div>
                      <div class="font-medium">{{ p.product_name }}</div>
                      <div class="text-xs text-muted">{{ p.product_sku }}</div>
                    </div>
                    <div class="text-right">
                      <div class="text-sm font-semibold">可退: {{ p.remaining_quantity }}件</div>
                    </div>
                  </div>
                  <div class="grid form-grid grid-cols-3 gap-2">
                    <div>
                      <label class="text-xs text-secondary">退货数量</label>
                      <input
                        type="number"
                        v-model.number="p.return_quantity"
                        min="1"
                        :max="p.remaining_quantity"
                        class="input input-sm w-full"
                      >
                    </div>
                    <div>
                      <label class="text-xs text-secondary">退回仓库 *</label>
                      <select v-model="p.return_warehouse_id" class="input input-sm w-full" @change="p.return_location_id = ''">
                        <option value="">选择</option>
                        <option
                          v-for="w in physicalWarehouses"
                          :key="w.id"
                          :value="w.id"
                        >{{ w.name }}</option>
                      </select>
                    </div>
                    <div>
                      <label class="text-xs text-secondary">退回仓位 *</label>
                      <select
                        v-model="p.return_location_id"
                        class="input input-sm w-full"
                        :disabled="!p.return_warehouse_id"
                      >
                        <option value="">选择</option>
                        <option
                          v-for="loc in getReturnLocations(p.return_warehouse_id)"
                          :key="loc.id"
                          :value="loc.id"
                        >{{ loc.code }}</option>
                      </select>
                    </div>
                  </div>
                </div>
                <div v-if="!consignReturnItems.length" class="text-muted text-center py-4 text-sm">无可退商品</div>
              </div>
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="closeReturnModal" class="btn btn-secondary flex-1">取消</button>
              <button type="button" @click="saveConsignReturn" :disabled="appStore.submitting" class="btn btn-primary flex-1">{{ appStore.submitting ? '提交中...' : '确认退货' }}</button>
            </div>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { useWarehousesStore } from '../stores/warehouses'
import { useFormat } from '../composables/useFormat'
import { usePermission } from '../composables/usePermission'
import { getSummary, getConsignCustomers, getCustomerDetail, returnConsignment } from '../api/consignment'
import { createOrder } from '../api/orders'

const appStore = useAppStore()
const warehousesStore = useWarehousesStore()
const { fmt, formatBalance, getBalanceLabel, getBalanceClass } = useFormat()
const { hasPermission } = usePermission()

// Local state
const consignSummary = ref({
  total_cost_value: 0,
  total_sales_value: 0,
  total_settle_unpaid: 0,
  total_quantity: 0,
  stock_details: []
})
const consignCustomers = ref([])
const consignDetail = ref({ customer: null, remaining_products: [] })
const consignSettleMode = ref(false)
const consignSettleItems = ref([])
const showDetailModal = ref(false)
const showReturnModal = ref(false)

// Computed
const physicalWarehouses = computed(() => warehousesStore.warehouses.filter(w => !w.is_virtual))
const getReturnLocations = (warehouseId) => {
  if (!warehouseId) return []
  return warehousesStore.getLocationsByWarehouse(warehouseId)
}

const settleTotal = computed(() =>
  Math.round(consignSettleItems.value.reduce((s, i) => s + Math.round((i.settle_quantity || 0) * (i.unit_price || 0) * 100) / 100, 0) * 100) / 100
)
const settleQuantity = computed(() =>
  consignSettleItems.value.reduce((s, i) => s + (i.settle_quantity || 0), 0)
)

// Data loading
const loadConsignSummary = async () => {
  try {
    const { data } = await getSummary()
    consignSummary.value = data
  } catch (e) {
    appStore.showToast('加载寄售汇总失败', 'error')
  }
}

const loadConsignCustomers = async () => {
  try {
    const { data } = await getConsignCustomers()
    consignCustomers.value = data
  } catch (e) {
    appStore.showToast('加载寄售客户失败', 'error')
  }
}

const loadConsignData = () => {
  loadConsignSummary()
  loadConsignCustomers()
}

// Detail modal
const openConsignDetail = async (c) => {
  try {
    const { data } = await getCustomerDetail(c.id)
    consignDetail.value = data
    consignSettleMode.value = false
    consignSettleItems.value = []
    showDetailModal.value = true
  } catch (e) {
    appStore.showToast('加载寄售详情失败', 'error')
  }
}

const closeDetailModal = () => {
  showDetailModal.value = false
  consignSettleMode.value = false
  consignSettleItems.value = []
}

// Settle mode
const enterConsignSettle = () => {
  if (!consignDetail.value.remaining_products?.length) {
    appStore.showToast('该客户没有可结算的寄售商品', 'error')
    return
  }
  consignSettleMode.value = true
  consignSettleItems.value = consignDetail.value.remaining_products.map(p => ({
    product_id: p.product_id,
    product_name: p.product_name,
    product_sku: p.product_sku,
    remaining_quantity: p.remaining_quantity,
    settle_quantity: 0,
    unit_price: p.unit_price
  }))
}

const submitConsignSettle = async () => {
  const items = consignSettleItems.value.filter(i => i.settle_quantity > 0)
  if (!items.length) {
    appStore.showToast('请至少输入一个商品的结算数量', 'error')
    return
  }
  for (const item of items) {
    if (!Number.isFinite(item.settle_quantity) || item.settle_quantity <= 0) {
      appStore.showToast(`${item.product_name}结算数量必须是正整数`, 'error')
      return
    }
    if (!Number.isInteger(item.settle_quantity)) {
      appStore.showToast(`${item.product_name}结算数量必须为整数`, 'error')
      return
    }
    if (item.settle_quantity > item.remaining_quantity) {
      appStore.showToast(`${item.product_name}结算数量不能超过${item.remaining_quantity}件`, 'error')
      return
    }
    if (!Number.isFinite(item.unit_price) || item.unit_price <= 0) {
      appStore.showToast(`${item.product_name}单价必须大于0`, 'error')
      return
    }
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await createOrder({
      order_type: 'CONSIGN_SETTLE',
      customer_id: consignDetail.value.customer.id,
      warehouse_id: null,
      location_id: null,
      items: items.map(i => ({
        product_id: i.product_id,
        quantity: i.settle_quantity,
        unit_price: i.unit_price,
        warehouse_id: null,
        location_id: null
      })),
      remark: null
    })
    appStore.showToast('寄售结算成功')
    consignSettleMode.value = false
    consignSettleItems.value = []
    showDetailModal.value = false
    loadConsignData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '寄售结算失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// Consign return
const openConsignReturn = () => {
  if (!consignDetail.value.remaining_products || consignDetail.value.remaining_products.length === 0) {
    appStore.showToast('该客户没有可退货的寄售商品', 'error')
    return
  }
  consignReturnItems.value = JSON.parse(JSON.stringify(consignDetail.value.remaining_products))
  consignReturnItems.value.forEach(p => {
    p.return_quantity = 1
    p.return_warehouse_id = ''
    p.return_location_id = ''
  })
  showReturnModal.value = true
}

const closeReturnModal = () => {
  showReturnModal.value = false
}

const consignReturnItems = ref([])

const saveConsignReturn = async () => {
  if (appStore.submitting) return
  const items = consignReturnItems.value.filter(
    p => p.return_quantity > 0 && p.return_warehouse_id && p.return_location_id
  )
  if (items.length === 0) {
    appStore.showToast('请至少选择一个商品并填写退货仓库和仓位', 'error')
    return
  }
  for (const item of items) {
    if (item.return_quantity > item.remaining_quantity) {
      appStore.showToast(`${item.product_name}退货数量不能超过${item.remaining_quantity}件`, 'error')
      return
    }
  }
  appStore.submitting = true
  try {
    await returnConsignment({
      customer_id: consignDetail.value.customer.id,
      items: items.map(i => ({
        product_id: i.product_id,
        quantity: i.return_quantity,
        warehouse_id: parseInt(i.return_warehouse_id),
        location_id: parseInt(i.return_location_id)
      }))
    })
    appStore.showToast('寄售退货成功')
    showReturnModal.value = false
    showDetailModal.value = false
    loadConsignData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '寄售退货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// Init
onMounted(() => {
  loadConsignData()
  if (!warehousesStore.warehouses.length) warehousesStore.loadWarehouses()
  if (!warehousesStore.locations.length) warehousesStore.loadLocations()
})
</script>
