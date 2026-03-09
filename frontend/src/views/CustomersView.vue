<template>
  <div>
    <!-- Tabs -->
    <div class="flex flex-wrap gap-2 mb-3 border-b pb-2">
      <span @click="customerTab = 'transactions'" :class="['tab', customerTab === 'transactions' ? 'active' : '']">交易明细</span>
      <span @click="customerTab = 'manage'" :class="['tab', customerTab === 'manage' ? 'active' : '']">客户管理</span>
      <button v-if="customerTab === 'manage'" @click="openCustomerModal" class="btn btn-primary btn-sm ml-auto">新增客户</button>
    </div>

    <!-- Transactions Tab -->
    <div v-if="customerTab === 'transactions'">
      <input v-model="customersStore.customerSearch" class="input mb-3 text-sm" placeholder="搜索客户...">
      <div class="card divide-y">
        <div
          v-for="c in filteredCustomers"
          :key="c.id"
          class="p-3 flex justify-between items-center cursor-pointer hover:bg-[#f5f5f7]"
          @click="openCustomerTrans(c)"
        >
          <div>
            <div class="font-medium">{{ c.name }}</div>
            <div class="text-xs text-[#86868b]">{{ c.phone }}</div>
          </div>
          <div class="text-right">
            <div :class="getBalanceClass(c.balance)" class="font-semibold">{{ getBalanceLabel(c.balance) }} ¥{{ formatBalance(c.balance) }}</div>
            <div class="text-xs text-[#86868b]">点击查看交易明细 →</div>
          </div>
        </div>
        <div v-if="!filteredCustomers.length" class="p-6 text-center text-[#86868b] text-sm">暂无客户</div>
      </div>
    </div>

    <!-- Manage Tab -->
    <div v-if="customerTab === 'manage'">
      <input v-model="customersStore.customerSearch" class="input mb-3 text-sm" placeholder="搜索客户...">
      <div class="card divide-y">
        <div
          v-for="c in filteredCustomers"
          :key="c.id"
          class="p-3 flex justify-between items-center cursor-pointer hover:bg-[#f5f5f7]"
          @click="editCustomer(c)"
        >
          <div>
            <div class="font-medium">{{ c.name }}</div>
            <div class="text-xs text-[#86868b]">{{ c.contact_person }} · {{ c.phone }}</div>
          </div>
          <div :class="getBalanceClass(c.balance)" class="font-semibold">{{ getBalanceLabel(c.balance) }} ¥{{ formatBalance(c.balance) }}</div>
        </div>
        <div v-if="!filteredCustomers.length" class="p-6 text-center text-[#86868b] text-sm">暂无客户</div>
      </div>
    </div>

    <!-- Customer Form Modal -->
    <div v-if="modal.show && modal.type === 'customer'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <div class="p-4">
          <form @submit.prevent="saveCustomerHandler" class="space-y-3">
            <div>
              <label class="label">名称 *</label>
              <input v-model="customerForm.name" class="input" required>
            </div>
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">联系人</label>
                <input v-model="customerForm.contact_person" class="input">
              </div>
              <div>
                <label class="label">电话</label>
                <input v-model="customerForm.phone" class="input">
              </div>
            </div>
            <div>
              <label class="label">地址</label>
              <input v-model="customerForm.address" class="input">
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="closeModal" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-primary flex-1">保存</button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Customer Transactions Modal -->
    <div v-if="modal.show && modal.type === 'customer_trans'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <div class="p-4">
          <!-- Customer summary and filters -->
          <div class="mb-4 p-3 bg-[#f5f5f7] rounded-lg flex flex-wrap gap-2 justify-between items-center">
            <div>
              <div class="font-semibold text-lg">{{ customerTrans.customer?.name }}</div>
              <div class="text-sm text-[#86868b]">
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
              class="p-2 bg-[#e8f8ee] rounded cursor-pointer hover:ring-2 ring-[#34c759]"
              :class="transType === 'CASH' ? 'ring-2 ring-[#34c759]' : ''"
              @click="transType = transType === 'CASH' ? '' : 'CASH'"
            >
              <div class="font-semibold text-[#34c759]">现款</div>
              <div>{{ customerTrans.stats.CASH?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.CASH?.amount) }}</div>
            </div>
            <div
              class="p-2 bg-[#fff8e1] rounded cursor-pointer hover:ring-2 ring-[#ff9f0a]"
              :class="transType === 'CREDIT' ? 'ring-2 ring-[#ff9f0a]' : ''"
              @click="transType = transType === 'CREDIT' ? '' : 'CREDIT'"
            >
              <div class="font-semibold text-[#ff9f0a]">账期</div>
              <div>{{ customerTrans.stats.CREDIT?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.CREDIT?.amount) }}</div>
            </div>
            <div
              class="p-2 bg-[#f3eef8] rounded cursor-pointer hover:ring-2 ring-[#af52de]"
              :class="transType === 'CONSIGN_OUT' ? 'ring-2 ring-[#af52de]' : ''"
              @click="transType = transType === 'CONSIGN_OUT' ? '' : 'CONSIGN_OUT'"
            >
              <div class="font-semibold text-[#af52de]">寄售调拨</div>
              <div>{{ customerTrans.stats.CONSIGN_OUT?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.CONSIGN_OUT?.amount) }}</div>
            </div>
            <div
              class="p-2 bg-[#e8f4fd] rounded cursor-pointer hover:ring-2 ring-[#0071e3]"
              :class="transType === 'CONSIGN_SETTLE' ? 'ring-2 ring-[#0071e3]' : ''"
              @click="transType = transType === 'CONSIGN_SETTLE' ? '' : 'CONSIGN_SETTLE'"
            >
              <div class="font-semibold text-[#0071e3]">寄售结算</div>
              <div>{{ customerTrans.stats.CONSIGN_SETTLE?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.CONSIGN_SETTLE?.amount) }}</div>
            </div>
            <div
              class="p-2 bg-[#ffeaee] rounded cursor-pointer hover:ring-2 ring-[#ff3b30]"
              :class="transType === 'RETURN' ? 'ring-2 ring-[#ff3b30]' : ''"
              @click="transType = transType === 'RETURN' ? '' : 'RETURN'"
            >
              <div class="font-semibold text-[#ff3b30]">退货</div>
              <div>{{ customerTrans.stats.RETURN?.count || 0 }}笔</div>
              <div>¥{{ fmt(customerTrans.stats.RETURN?.amount) }}</div>
            </div>
          </div>

          <!-- Transaction list -->
          <div class="font-semibold mb-2 text-sm">
            交易记录 <span v-if="transType" class="text-[#0071e3]">({{ orderTypeNames[transType] || transType }})</span>
          </div>
          <div class="max-h-64 overflow-y-auto">
            <table class="w-full text-sm">
              <thead class="bg-[#f5f5f7] sticky top-0">
                <tr>
                  <th class="px-2 py-1 text-left">订单号</th>
                  <th class="px-2 py-1 text-left">类型</th>
                  <th class="px-2 py-1 text-right">金额</th>
                  <th class="px-2 py-1 text-center">状态</th>
                  <th class="px-2 py-1 text-left">时间</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr
                  v-for="t in filteredTransactions"
                  :key="t.id"
                  class="clickable-row"
                  @click="viewOrderFromTrans(t.id)"
                >
                  <td class="px-2 py-1 font-mono text-xs text-[#0071e3]">{{ t.order_no }}</td>
                  <td class="px-2 py-1">
                    <span :class="orderTypeBadges[t.order_type] || 'badge badge-gray'">{{ orderTypeNames[t.order_type] || t.order_type }}</span>
                  </td>
                  <td class="px-2 py-1 text-right font-semibold">¥{{ fmt(t.total_amount) }}</td>
                  <td class="px-2 py-1 text-center">
                    <span :class="t.is_cleared ? 'badge badge-green' : 'badge badge-red'">{{ t.is_cleared ? '已结' : '未结' }}</span>
                  </td>
                  <td class="px-2 py-1 text-[#86868b] text-xs">{{ fmtDate(t.created_at) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredTransactions?.length" class="p-6 text-center text-[#86868b] text-sm">暂无交易记录</div>
          </div>
          <div class="flex gap-3 pt-4">
            <button type="button" @click="closeModal" class="btn btn-secondary flex-1">关闭</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Order Detail Modal -->
    <div v-if="modal.show && modal.type === 'order_detail'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="p-4 border-b flex justify-between items-center">
          <div class="flex items-center gap-2">
            <button v-if="previousModal" @click="goBackToPrevious" class="text-[#86868b] hover:text-[#0071e3] text-xl" title="返回上一页">←</button>
            <h3 class="font-semibold">{{ modal.title }}</h3>
          </div>
          <button @click="closeModal" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <div class="p-4">
          <!-- Order header -->
          <div class="mb-4 p-3 bg-[#f5f5f7] rounded-lg">
            <div class="flex justify-between items-start mb-2">
              <div>
                <div class="font-semibold">{{ orderDetail.order_no }}</div>
                <div class="text-sm text-[#86868b]">
                  <span v-if="orderDetail.salesperson_name">销售员: {{ orderDetail.salesperson_name }} · </span>
                  {{ orderDetail.creator_name }} · {{ fmtDate(orderDetail.created_at) }}
                </div>
              </div>
              <span :class="orderTypeBadges[orderDetail.order_type] || 'badge badge-gray'">{{ orderTypeNames[orderDetail.order_type] || orderDetail.order_type }}</span>
            </div>
            <div class="grid detail-grid grid-cols-2 gap-2 text-sm">
              <div><span class="text-[#86868b]">客户:</span> {{ orderDetail.customer?.name || '-' }}</div>
              <div><span class="text-[#86868b]">仓库:</span> {{ orderDetail.warehouse?.name || '-' }}</div>
              <div v-if="orderDetail.related_order" class="col-span-2">
                <span class="text-[#86868b]">关联销售订单:</span>
                <span @click="viewOrder(orderDetail.related_order.id)" class="text-[#0071e3] hover:underline cursor-pointer font-mono">{{ orderDetail.related_order.order_no }}</span>
              </div>
              <div><span class="text-[#86868b]">金额:</span> <span class="font-semibold">¥{{ fmt(orderDetail.total_amount) }}</span></div>
              <div v-if="hasPermission('finance')">
                <span class="text-[#86868b]">毛利:</span>
                <span :class="orderDetail.total_profit >= 0 ? 'text-[#34c759]' : 'text-[#ff3b30]'">¥{{ fmt(orderDetail.total_profit) }}</span>
              </div>
              <div v-if="orderDetail.rebate_used > 0" class="col-span-2">
                <span class="text-[#86868b]">已使用返利:</span>
                <span class="text-[#34c759] font-semibold">¥{{ fmt(orderDetail.rebate_used) }}</span>
              </div>
              <div v-if="orderDetail.credit_used > 0" class="col-span-2">
                <span class="text-[#86868b]">已使用在账资金:</span>
                <span class="text-[#0071e3] font-semibold">¥{{ fmt(orderDetail.credit_used) }}</span>
              </div>
              <div v-if="orderDetail.payment_records && orderDetail.payment_records.length" class="col-span-2">
                <div v-for="pr in orderDetail.payment_records" :key="pr.id" class="flex items-center gap-2 text-sm mb-1">
                  <span class="text-[#86868b]">{{ pr.source === 'CASH' ? '销售收款' : '账期回款' }}:</span>
                  <span class="font-semibold text-[#34c759]">¥{{ fmt(pr.amount) }}</span>
                  <span class="badge badge-blue" style="font-size:11px">{{ getPaymentMethodName(pr.payment_method) }}</span>
                  <span :class="pr.is_confirmed ? 'text-[#34c759]' : 'text-[#ff9f0a]'" style="font-size:11px">{{ pr.is_confirmed ? '已确认' : '待确认' }}</span>
                </div>
              </div>
              <div v-else-if="!orderDetail.credit_used"><span class="text-[#86868b]">已付:</span> ¥{{ fmt(orderDetail.paid_amount) }}</div>
              <div><span class="text-[#86868b]">状态:</span> <span :class="orderDetail.is_cleared ? 'text-[#34c759]' : 'text-[#ff3b30]'">{{ orderDetail.is_cleared ? '已结清' : '未结清' }}</span></div>
              <div v-if="orderDetail.order_type === 'RETURN'" class="col-span-2">
                <span class="text-[#86868b]">退款状态:</span>
                <span :class="orderDetail.refunded ? 'text-[#ff9f0a]' : 'text-[#d70015]'">{{ orderDetail.refunded ? '已退款给客户' : '形成在账资金' }}</span>
              </div>
              <div v-if="orderDetail.remark" class="col-span-2 pt-2 border-t">
                <span class="text-[#86868b]">备注:</span> <span class="text-[#6e6e73]">{{ orderDetail.remark }}</span>
              </div>
            </div>
          </div>

          <!-- 物流信息与SN码 -->
          <div v-if="orderDetail.shipments?.length" class="mb-4">
            <div class="font-semibold text-sm mb-2">物流信息 ({{ orderDetail.shipments.length }})</div>
            <div v-for="sh in orderDetail.shipments" :key="sh.id" class="p-3 bg-[#e8f4fd] rounded-lg mb-2">
              <div class="flex justify-between items-center mb-1">
                <div class="text-sm">{{ sh.carrier_name || '未填写' }} <span v-if="sh.tracking_no" class="font-mono text-xs">{{ sh.tracking_no }}</span></div>
                <span class="text-xs px-2 py-0.5 rounded-full bg-[#f5f5f7] text-[#6e6e73]">{{ sh.status_text }}</span>
              </div>
              <div v-if="sh.items?.length" class="mt-1.5 space-y-1">
                <div v-for="(si, idx) in sh.items" :key="idx" class="text-xs">
                  <span class="text-[#6e6e73]">{{ si.product_name }} × {{ si.quantity }}</span>
                  <div v-if="si.sn_codes" class="mt-0.5 p-1.5 bg-[#e8f8ee] rounded">
                    <span class="text-[#86868b] font-semibold">SN码:</span>
                    <span v-for="sn in parseSN(si.sn_codes)" :key="sn" class="text-[#34c759] font-mono ml-1">{{ sn }}</span>
                  </div>
                </div>
              </div>
              <div v-else-if="sh.sn_code" class="mt-1 p-1.5 bg-[#e8f8ee] rounded">
                <span class="text-xs text-[#86868b] font-semibold">SN码:</span>
                <span class="text-xs text-[#34c759] font-mono ml-1">{{ sh.sn_code }}</span>
              </div>
              <div v-if="sh.last_info" class="text-xs text-[#86868b] mt-1">{{ sh.last_info }}</div>
            </div>
          </div>

          <!-- Items table -->
          <div class="font-semibold mb-2 text-sm">商品明细</div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-[#f5f5f7]">
                <tr>
                  <th class="px-2 py-1 text-left">商品</th>
                  <th class="px-2 py-1 text-right">单价</th>
                  <th class="px-2 py-1 text-right">数量</th>
                  <th v-if="orderDetail.rebate_used > 0" class="px-2 py-1 text-right">返利</th>
                  <th class="px-2 py-1 text-right">金额</th>
                  <th v-if="hasPermission('finance')" class="px-2 py-1 text-right">毛利</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr v-for="item in orderDetail.items" :key="item.product_id">
                  <td class="px-2 py-1">
                    <div>{{ item.product_name }}</div>
                    <div class="text-xs text-[#86868b]">{{ item.product_sku }}</div>
                  </td>
                  <td class="px-2 py-1 text-right">{{ fmt(item.unit_price) }}</td>
                  <td class="px-2 py-1 text-right">{{ item.quantity }}</td>
                  <td v-if="orderDetail.rebate_used > 0" class="px-2 py-1 text-right text-[#34c759]">{{ item.rebate_amount > 0 ? '-¥' + fmt(item.rebate_amount) : '' }}</td>
                  <td class="px-2 py-1 text-right font-semibold">{{ fmt(item.amount) }}</td>
                  <td v-if="hasPermission('finance')" class="px-2 py-1 text-right" :class="item.profit >= 0 ? 'text-[#34c759]' : 'text-[#ff3b30]'">{{ fmt(item.profit) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="flex gap-3 pt-4">
            <button type="button" @click="closeModal" class="btn btn-secondary flex-1">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, onMounted } from 'vue'
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
const closeModal = appStore.closeModal
const showToast = appStore.showToast
const { previousModal } = storeToRefs(appStore)

// Local state
const customerTab = ref('transactions')
const customerForm = reactive({ id: null, name: '', contact_person: '', phone: '', address: '' })
const customerTrans = ref({ customer: null, stats: null, transactions: [], available_months: [] })
const transMonth = ref('')
const transType = ref('')
const orderDetail = ref({})

// Computed
const filteredCustomers = computed(() => customersStore.filteredCustomers)

const filteredTransactions = computed(() => {
  if (!customerTrans.value.transactions) return []
  if (!transType.value) return customerTrans.value.transactions
  return customerTrans.value.transactions.filter(t => t.order_type === transType.value)
})

// Methods
const openCustomerModal = () => {
  Object.assign(customerForm, { id: null, name: '', contact_person: '', phone: '', address: '' })
  openModal('customer', '新增客户')
}

const editCustomer = (c) => {
  Object.assign(customerForm, {
    id: c.id, name: c.name, contact_person: c.contact_person,
    phone: c.phone, address: c.address
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
    const params = {}
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
