<template>
  <div>
    <!-- Tabs -->
    <div class="flex flex-wrap gap-2 mb-3 border-b pb-2">
      <span @click="customerTab = 'transactions'" :class="['tab', customerTab === 'transactions' ? 'active' : '']">交易明细</span>
      <span @click="customerTab = 'manage'" :class="['tab', customerTab === 'manage' ? 'active' : '']">客户管理</span>
      <button v-if="customerTab === 'manage'" @click="openCustomerModal" class="btn btn-primary btn-sm ml-auto">新增客户</button>
    </div>

    <!-- Transactions Tab -->
    <div v-if="customerTab === 'transactions'" key="transactions">
      <div class="card" style="overflow: visible">
        <div class="px-2 py-2">
          <div class="toolbar-search-wrapper" style="max-width:320px">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="customersStore.customerSearch" class="toolbar-search" placeholder="搜索客户...">
          </div>
        </div>
        <div class="table-container">
          <table class="w-full text-sm">
            <thead class="bg-elevated">
              <tr>
                <th class="px-2 py-2 text-left w-80">客户名称</th>
                <th class="px-2 py-2 text-left w-36">电话</th>
                <th class="px-2 py-2 text-right">余额状态</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr
                v-for="c in filteredCustomers"
                :key="c.id"
                class="hover:bg-elevated cursor-pointer"
                @click="openCustomerTrans(c)"
              >
                <td class="px-2 py-2 font-medium">{{ c.name }}</td>
                <td class="px-2 py-2 text-secondary">{{ c.phone || '-' }}</td>
                <td class="px-2 py-2 text-right">
                  <span :class="getBalanceClass(c.balance)" class="font-semibold">{{ getBalanceLabel(c.balance) }} ¥{{ formatBalance(c.balance) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!filteredCustomers.length" class="p-6 text-center text-muted text-sm">暂无客户</div>
        </div>
      </div>
    </div>

    <!-- Manage Tab -->
    <div v-else-if="customerTab === 'manage'" key="manage">
      <div class="card" style="overflow: visible">
        <div class="px-2 py-2">
          <div class="toolbar-search-wrapper" style="max-width:320px">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="customersStore.customerSearch" class="toolbar-search" placeholder="搜索客户...">
          </div>
        </div>
        <div class="table-container">
          <table class="w-full text-sm">
            <thead class="bg-elevated">
              <tr>
                <th class="px-2 py-2 text-left w-80">客户名称</th>
                <th class="px-2 py-2 text-left w-28">联系人</th>
                <th class="px-2 py-2 text-left w-36">电话</th>
                <th class="px-2 py-2 text-right">余额状态</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr
                v-for="c in filteredCustomers"
                :key="c.id"
                class="hover:bg-elevated cursor-pointer"
                @click="editCustomer(c)"
              >
                <td class="px-2 py-2 font-medium">{{ c.name }}</td>
                <td class="px-2 py-2 text-secondary">{{ c.contact_person || '-' }}</td>
                <td class="px-2 py-2 text-secondary">{{ c.phone || '-' }}</td>
                <td class="px-2 py-2 text-right">
                  <span :class="getBalanceClass(c.balance)" class="font-semibold">{{ getBalanceLabel(c.balance) }} ¥{{ formatBalance(c.balance) }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!filteredCustomers.length" class="p-6 text-center text-muted text-sm">暂无客户</div>
        </div>
      </div>
    </div>

    <!-- Customer Form Modal -->
    <div v-if="modal.show && modal.type === 'customer'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveCustomerHandler">
          <div class="modal-body">
            <div class="space-y-3">
              <div>
                <label class="label">名称 *</label>
                <input v-model="customerForm.name" class="input" required>
              </div>
              <div>
                <label class="label">联系人</label>
                <input v-model="customerForm.contact_person" class="input">
              </div>
              <div class="text-xs font-semibold text-secondary mt-3 mb-1">开票信息</div>
              <div>
                <label class="label">纳税人识别号</label>
                <input v-model="customerForm.tax_id" class="input" placeholder="统一社会信用代码">
              </div>
              <div class="grid form-grid grid-cols-2 gap-3">
                <div>
                  <label class="label">地址</label>
                  <input v-model="customerForm.address" class="input" placeholder="注册地址">
                </div>
                <div>
                  <label class="label">电话</label>
                  <input v-model="customerForm.phone" class="input" placeholder="固定电话">
                </div>
              </div>
              <div class="grid form-grid grid-cols-2 gap-3">
                <div>
                  <label class="label">开户行</label>
                  <input v-model="customerForm.bank_name" class="input">
                </div>
                <div>
                  <label class="label">银行账号</label>
                  <input v-model="customerForm.bank_account" class="input">
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" @click="closeModal" class="btn btn-sm btn-secondary">取消</button>
            <button type="submit" class="btn btn-sm btn-primary">保存</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Customer Transactions Modal -->
    <div v-if="modal.show && modal.type === 'customer_trans'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <!-- Customer summary and filters -->
          <div class="mb-4 p-3 bg-elevated rounded-lg flex flex-wrap gap-2 justify-between items-center">
            <div>
              <div class="font-semibold text-lg">{{ customerTrans.customer?.name }}</div>
              <div class="text-sm text-muted">
                <span :class="getBalanceClass(customerTrans.customer?.balance)" class="font-semibold">
                  {{ getBalanceLabel(customerTrans.customer?.balance) }}: ¥{{ formatBalance(customerTrans.customer?.balance) }}
                </span>
              </div>
            </div>
            <div class="flex gap-2">
              <select v-model="transType" class="input w-auto text-sm">
                <option value="">全部类型</option>
                <option value="CASH">现款</option>
                <option value="CREDIT">账期</option>
                <option value="CONSIGN_OUT">寄售调拨</option>
                <option value="CONSIGN_SETTLE">寄售结算</option>
                <option value="RETURN">退货</option>
              </select>
              <select v-model="transMonth" @change="loadCustomerTrans(customerTrans.customer?.id)" class="input w-auto text-sm">
                <option value="">全部时间</option>
                <option v-for="m in customerTrans.available_months" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>
          </div>

          <!-- Stats cards (finance permission) -->
          <div v-if="customerTrans.stats && hasPermission('finance')" class="grid grid-cols-3 md:grid-cols-5 gap-2 mb-4 text-center text-xs">
            <div
              class="p-2 bg-success-subtle rounded cursor-pointer hover:ring-2 ring-success"
              :class="transType === 'CASH' ? 'ring-2 ring-success' : ''"
              @click="transType = transType === 'CASH' ? '' : 'CASH'"
            >
              <div class="font-semibold text-success">现款</div>
              <div>{{ customerTrans.stats.CASH?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.CASH?.amount) }}</div>
            </div>
            <div
              class="p-2 bg-warning-subtle rounded cursor-pointer hover:ring-2 ring-warning"
              :class="transType === 'CREDIT' ? 'ring-2 ring-warning' : ''"
              @click="transType = transType === 'CREDIT' ? '' : 'CREDIT'"
            >
              <div class="font-semibold text-warning">账期</div>
              <div>{{ customerTrans.stats.CREDIT?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.CREDIT?.amount) }}</div>
            </div>
            <div
              class="p-2 bg-purple-subtle rounded cursor-pointer hover:ring-2 ring-purple-emphasis"
              :class="transType === 'CONSIGN_OUT' ? 'ring-2 ring-purple-emphasis' : ''"
              @click="transType = transType === 'CONSIGN_OUT' ? '' : 'CONSIGN_OUT'"
            >
              <div class="font-semibold text-purple-emphasis">寄售调拨</div>
              <div>{{ customerTrans.stats.CONSIGN_OUT?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.CONSIGN_OUT?.amount) }}</div>
            </div>
            <div
              class="p-2 bg-info-subtle rounded cursor-pointer hover:ring-2 ring-primary"
              :class="transType === 'CONSIGN_SETTLE' ? 'ring-2 ring-primary' : ''"
              @click="transType = transType === 'CONSIGN_SETTLE' ? '' : 'CONSIGN_SETTLE'"
            >
              <div class="font-semibold text-primary">寄售结算</div>
              <div>{{ customerTrans.stats.CONSIGN_SETTLE?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.CONSIGN_SETTLE?.amount) }}</div>
            </div>
            <div
              class="p-2 bg-error-subtle rounded cursor-pointer hover:ring-2 ring-error"
              :class="transType === 'RETURN' ? 'ring-2 ring-error' : ''"
              @click="transType = transType === 'RETURN' ? '' : 'RETURN'"
            >
              <div class="font-semibold text-error">退货</div>
              <div>{{ customerTrans.stats.RETURN?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.RETURN?.amount) }}</div>
            </div>
          </div>

          <!-- Transaction list -->
          <div class="font-semibold mb-2 text-sm">
            交易记录 <span v-if="transType" class="text-primary">({{ orderTypeNames[transType] || transType }})</span>
          </div>
          <div>
            <table class="w-full text-sm">
              <thead class="bg-elevated sticky top-0">
                <tr>
                  <th class="px-2 py-2 text-left">订单号</th>
                  <th class="px-2 py-2 text-left">类型</th>
                  <th class="px-2 py-2 text-right">金额</th>
                  <th class="px-2 py-2 text-center">状态</th>
                  <th class="px-2 py-2 text-left">时间</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr
                  v-for="t in filteredTransactions"
                  :key="t.id"
                  class="clickable-row"
                  @click="viewOrderFromTrans(t.id)"
                >
                  <td class="px-2 py-2 font-mono text-xs text-primary">{{ t.order_no }}</td>
                  <td class="px-2 py-2">
                    <span :class="orderTypeBadges[t.order_type] || 'badge badge-gray'">{{ orderTypeNames[t.order_type] || t.order_type }}</span>
                  </td>
                  <td class="px-2 py-2 text-right font-semibold">¥{{ fmt(t.total_amount) }}</td>
                  <td class="px-2 py-2 text-center">
                    <span :class="t.is_cleared ? 'badge badge-green' : 'badge badge-red'">{{ t.is_cleared ? '已结' : '未结' }}</span>
                  </td>
                  <td class="px-2 py-2 text-muted text-xs">{{ fmtDate(t.created_at) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredTransactions?.length" class="p-6 text-center text-muted text-sm">暂无交易记录</div>
            <div v-if="customerTrans.total > 20" class="flex items-center justify-between mt-3 text-sm text-secondary">
              <span>共 {{ customerTrans.total }} 条</span>
              <div class="flex gap-2">
                <button class="btn btn-sm" :disabled="transPage <= 1" @click="transPage--; loadCustomerTrans(customerTrans.customer?.id)">上一页</button>
                <span class="px-2 leading-8">{{ transPage }} / {{ Math.ceil(customerTrans.total / 20) }}</span>
                <button class="btn btn-sm" :disabled="transPage >= Math.ceil(customerTrans.total / 20)" @click="transPage++; loadCustomerTrans(customerTrans.customer?.id)">下一页</button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" @click="closeModal" class="btn btn-sm btn-secondary">关闭</button>
        </div>
      </div>
    </div>

    <!-- Order Detail Modal -->
    <div v-if="modal.show && modal.type === 'order_detail'" class="modal-overlay" @click.self="closeModal">
      <div class="modal" :class="{ 'modal-expanded': isDetailExpanded }">
        <div class="modal-header">
          <div class="flex items-center gap-2">
            <button v-if="previousModal" @click="goBackToPrevious" class="text-muted hover:text-primary text-xl" title="返回上一页">←</button>
            <h3 class="font-semibold">{{ modal.title }}</h3>
          </div>
          <div class="flex items-center gap-1">
            <button @click="isDetailExpanded = !isDetailExpanded" class="modal-expand-btn hidden md:inline-flex" :aria-label="isDetailExpanded ? '收起弹窗' : '展开弹窗'">
              <Minimize2 v-if="isDetailExpanded" :size="16" />
              <Maximize2 v-else :size="16" />
            </button>
            <button @click="closeModal" class="modal-close">&times;</button>
          </div>
        </div>
        <div class="modal-body">
          <!-- Order header -->
          <div class="mb-4 p-3 bg-elevated rounded-lg">
            <div class="flex justify-between items-start mb-2">
              <div>
                <div class="font-semibold">{{ orderDetail.order_no }}</div>
                <div class="text-sm text-muted">
                  <span v-if="orderDetail.employee_name">业务员: {{ orderDetail.employee_name }} · </span>
                  {{ orderDetail.creator_name }} · {{ fmtDate(orderDetail.created_at) }}
                </div>
              </div>
              <span :class="orderTypeBadges[orderDetail.order_type] || 'badge badge-gray'">{{ orderTypeNames[orderDetail.order_type] || orderDetail.order_type }}</span>
            </div>
            <div class="grid detail-grid grid-cols-2 gap-2 text-sm">
              <div><span class="text-muted">客户:</span> {{ orderDetail.customer?.name || '-' }}</div>
              <div><span class="text-muted">仓库:</span> {{ orderDetail.warehouse?.name || '-' }}</div>
              <div v-if="orderDetail.related_order?.id" class="col-span-2">
                <span class="text-muted">关联销售订单:</span>
                <span @click="viewOrder(orderDetail.related_order?.id)" class="text-primary hover:underline cursor-pointer font-mono">{{ orderDetail.related_order?.order_no }}</span>
              </div>
              <div><span class="text-muted">金额:</span> <span class="font-semibold">¥{{ fmt(orderDetail.total_amount) }}</span></div>
              <div v-if="hasPermission('finance')">
                <span class="text-muted">毛利:</span>
                <span :class="orderDetail.total_profit >= 0 ? 'text-success' : 'text-error'">¥{{ fmt(orderDetail.total_profit) }}</span>
              </div>
              <div v-if="orderDetail.rebate_used > 0" class="col-span-2">
                <span class="text-muted">已使用返利:</span>
                <span class="text-success font-semibold">¥{{ fmt(orderDetail.rebate_used) }}</span>
              </div>
              <div v-if="orderDetail.credit_used > 0" class="col-span-2">
                <span class="text-muted">已使用在账资金:</span>
                <span class="text-primary font-semibold">¥{{ fmt(orderDetail.credit_used) }}</span>
              </div>
              <div v-if="orderDetail.payment_records && orderDetail.payment_records.length" class="col-span-2">
                <div v-for="pr in orderDetail.payment_records" :key="pr.id" class="flex items-center gap-2 text-sm mb-1">
                  <span class="text-muted">{{ pr.source === 'CASH' ? '销售收款' : '账期回款' }}:</span>
                  <span class="font-semibold text-success">¥{{ fmt(pr.amount) }}</span>
                  <span class="badge badge-blue" style="font-size:11px">{{ getPaymentMethodName(pr.payment_method) }}</span>
                  <span :class="pr.is_confirmed ? 'text-success' : 'text-warning'" style="font-size:11px">{{ pr.is_confirmed ? '已确认' : '待确认' }}</span>
                </div>
              </div>
              <div v-else-if="!orderDetail.credit_used"><span class="text-muted">已付:</span> ¥{{ fmt(orderDetail.paid_amount) }}</div>
              <div><span class="text-muted">状态:</span> <span :class="orderDetail.is_cleared ? 'text-success' : 'text-error'">{{ orderDetail.is_cleared ? '已结清' : '未结清' }}</span></div>
              <div v-if="orderDetail.order_type === 'RETURN'" class="col-span-2">
                <span class="text-muted">退款状态:</span>
                <span :class="orderDetail.refunded ? 'text-warning' : 'text-error-emphasis'">{{ orderDetail.refunded ? '已退款给客户' : '形成在账资金' }}</span>
              </div>
              <div v-if="orderDetail.remark" class="col-span-2 pt-2 border-t">
                <span class="text-muted">备注:</span> <span class="text-secondary">{{ orderDetail.remark }}</span>
              </div>
            </div>
          </div>

          <!-- 物流信息与SN码 -->
          <div v-if="orderDetail.shipments?.length" class="mb-4">
            <div class="font-semibold text-sm mb-2">物流信息 ({{ orderDetail.shipments.length }})</div>
            <div v-for="sh in orderDetail.shipments" :key="sh.id" class="p-3 bg-info-subtle rounded-lg mb-2">
              <div class="flex justify-between items-center mb-1">
                <div class="text-sm">{{ sh.carrier_name || '未填写' }} <span v-if="sh.tracking_no" class="font-mono text-xs">{{ sh.tracking_no }}</span></div>
                <span class="text-xs px-2 py-0.5 rounded-full bg-elevated text-secondary">{{ sh.status_text }}</span>
              </div>
              <div v-if="sh.items?.length" class="mt-1.5 space-y-1">
                <div v-for="(si, idx) in sh.items" :key="idx" class="text-xs">
                  <span class="text-secondary">{{ si.product_name }} × {{ si.quantity }}</span>
                  <div v-if="si.sn_codes" class="mt-0.5 p-1.5 bg-success-subtle rounded">
                    <span class="text-muted font-semibold">SN码:</span>
                    <span v-for="sn in parseSN(si.sn_codes)" :key="sn" class="text-success font-mono ml-1">{{ sn }}</span>
                  </div>
                </div>
              </div>
              <div v-else-if="sh.sn_code" class="mt-1 p-1.5 bg-success-subtle rounded">
                <span class="text-xs text-muted font-semibold">SN码:</span>
                <span class="text-xs text-success font-mono ml-1">{{ sh.sn_code }}</span>
              </div>
              <div v-if="sh.last_info" class="text-xs text-muted mt-1">{{ sh.last_info }}</div>
            </div>
          </div>

          <!-- Items table -->
          <div class="font-semibold mb-2 text-sm">商品明细</div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-elevated">
                <tr>
                  <th class="px-2 py-2 text-left">商品</th>
                  <th class="px-2 py-2 text-left">仓库</th>
                  <th class="px-2 py-2 text-right">单价</th>
                  <th class="px-2 py-2 text-right">数量</th>
                  <th v-if="orderDetail.rebate_used > 0" class="px-2 py-2 text-right">返利</th>
                  <th class="px-2 py-2 text-right">金额</th>
                  <th v-if="hasPermission('finance')" class="px-2 py-2 text-right">毛利</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr v-for="item in orderDetail.items" :key="item.product_id">
                  <td class="px-2 py-2">
                    <div>{{ item.product_name }}</div>
                    <div class="text-xs text-muted">{{ item.product_sku }}</div>
                  </td>
                  <td class="px-2 py-2 text-muted">{{ item.warehouse_name || '-' }}</td>
                  <td class="px-2 py-2 text-right">{{ fmt(item.unit_price) }}</td>
                  <td class="px-2 py-2 text-right">{{ item.quantity }}</td>
                  <td v-if="orderDetail.rebate_used > 0" class="px-2 py-2 text-right text-success">{{ item.rebate_amount > 0 ? '-¥' + fmt(item.rebate_amount) : '' }}</td>
                  <td class="px-2 py-2 text-right font-semibold">{{ fmt(item.amount) }}</td>
                  <td v-if="hasPermission('finance')" class="px-2 py-2 text-right" :class="item.profit >= 0 ? 'text-success' : 'text-error'">{{ fmt(item.profit) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" @click="closeModal" class="btn btn-sm btn-secondary">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Maximize2, Minimize2, Search } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'
import { useAppStore } from '../stores/app'
import { useCustomersStore } from '../stores/customers'
import { useSettingsStore } from '../stores/settings'
import { useFormat } from '../composables/useFormat'
import { usePermission } from '../composables/usePermission'
import { createCustomer, updateCustomer, getCustomerTransactions } from '../api/customers'
import { getOrder } from '../api/orders'
import { orderTypeNames, orderTypeBadges } from '../utils/constants'

const appStore = useAppStore()
const customersStore = useCustomersStore()
const settingsStore = useSettingsStore()
const { fmt, fmtDate, formatBalance, getBalanceLabel, getBalanceClass } = useFormat()
const { hasPermission } = usePermission()

/** 解析 SN 码 JSON 字符串为数组 */
const parseSN = (raw) => {
  if (!raw) return []
  try { return JSON.parse(raw) } catch { return raw.split(',').map(s => s.trim()).filter(Boolean) }
}

onMounted(() => {
  customersStore.loadCustomers()
  settingsStore.loadPaymentMethods()
})

const getPaymentMethodName = (code) => {
  const m = settingsStore.paymentMethods.find(pm => pm.code === code)
  return m ? m.name : code
}

// App store shortcuts
const modal = appStore.modal
const openModal = appStore.openModal
const _closeModal = appStore.closeModal
const closeModal = () => {
  isDetailExpanded.value = false
  _closeModal()
}
const showToast = appStore.showToast
const { previousModal } = storeToRefs(appStore)

// Local state
const route = useRoute()
const router = useRouter()
const customerValidTabs = ['transactions', 'manage']
const customerTab = ref(customerValidTabs.includes(route.query.tab) ? route.query.tab : 'transactions')
watch(customerTab, (val) => router.replace({ query: { ...route.query, tab: val === 'transactions' ? undefined : val } }))
const customerForm = reactive({ id: null, name: '', contact_person: '', phone: '', address: '', tax_id: '', bank_name: '', bank_account: '' })
const customerTrans = ref({ customer: null, stats: null, transactions: [], available_months: [] })
const transMonth = ref('')
const transType = ref('')
const transPage = ref(1)
const orderDetail = ref({})
const isDetailExpanded = ref(false)

// Computed
const filteredCustomers = computed(() => customersStore.filteredCustomers)

const filteredTransactions = computed(() => {
  if (!customerTrans.value.transactions) return []
  if (!transType.value) return customerTrans.value.transactions
  return customerTrans.value.transactions.filter(t => t.order_type === transType.value)
})

// Methods
const openCustomerModal = () => {
  Object.assign(customerForm, { id: null, name: '', contact_person: '', phone: '', address: '', tax_id: '', bank_name: '', bank_account: '' })
  openModal('customer', '新增客户')
}

const editCustomer = (c) => {
  Object.assign(customerForm, {
    id: c.id, name: c.name, contact_person: c.contact_person,
    phone: c.phone, address: c.address,
    tax_id: c.tax_id || '', bank_name: c.bank_name || '', bank_account: c.bank_account || ''
  })
  openModal('customer', '编辑客户')
}

const saveCustomerHandler = async () => {
  if (!customerForm.name || !customerForm.name.trim()) {
    showToast('请输入客户名称', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    if (customerForm.id) await updateCustomer(customerForm.id, customerForm)
    else await createCustomer(customerForm)
    showToast('保存成功')
    closeModal()
    customersStore.loadCustomers()
  } catch (e) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const loadCustomerTrans = async (cid) => {
  if (!cid) return
  try {
    const params = { page: transPage.value, page_size: 20 }
    if (transMonth.value) {
      const [y, m] = transMonth.value.split('-')
      params.year = parseInt(y)
      params.month = parseInt(m)
    }
    const { data } = await getCustomerTransactions(cid, params)
    customerTrans.value = data
  } catch (e) {
    console.error(e)
    appStore.showToast(e.response?.data?.detail || '加载交易记录失败', 'error')
  }
}

const openCustomerTrans = async (c) => {
  transMonth.value = ''
  transType.value = ''
  transPage.value = 1
  await loadCustomerTrans(c.id)
  openModal('customer_trans', '客户交易明细 - ' + c.name)
}

const viewOrderFromTrans = async (id) => {
  previousModal.value = {
    type: 'customer_trans',
    title: '客户交易明细 - ' + (customerTrans.value.customer?.name || '')
  }
  try {
    const { data } = await getOrder(id)
    orderDetail.value = data
    openModal('order_detail', '订单详情')
  } catch (e) {
    showToast('加载订单详情失败', 'error')
  }
}

const viewOrder = async (id) => {
  try {
    const { data } = await getOrder(id)
    orderDetail.value = data
    previousModal.value = null
    openModal('order_detail', '订单详情')
  } catch (e) {
    showToast('加载订单详情失败', 'error')
  }
}

const goBackToPrevious = () => {
  if (previousModal.value) {
    openModal(previousModal.value.type, previousModal.value.title)
    previousModal.value = null
  }
}
</script>
