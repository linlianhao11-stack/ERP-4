<template>
  <div>
    <!-- 客户筛选 -->
    <div class="card mb-2 p-3">
      <select v-model="financeCustomerId" @change="loadUnpaid" class="input text-sm">
        <option value="">全部客户</option>
        <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }} ({{ getBalanceLabel(c.balance) }} ¥{{ formatBalance(c.balance) }})</option>
      </select>
    </div>
    <!-- 移动端欠款卡片列表 -->
    <div class="md:hidden space-y-2">
      <div v-for="o in unpaidOrders" :key="o.id" class="card p-3 flex justify-between items-center cursor-pointer" @click="handleViewOrder(o.id)">
        <div class="min-w-0 flex-1 mr-3">
          <div class="font-medium truncate"><span class="todo-dot mr-1"></span>{{ o.customer_name }}</div>
          <div class="text-xs text-muted truncate">{{ o.order_no }} · <span :class="orderTypeBadges[o.order_type]">{{ orderTypeNames[o.order_type] }}</span></div>
        </div>
        <div class="text-right flex-shrink-0">
          <div class="text-lg font-bold text-error">¥{{ fmt(o.unpaid_amount) }}</div>
          <div class="text-xs text-muted">{{ fmtDate(o.created_at) }}</div>
        </div>
      </div>
      <div v-if="!unpaidOrders.length" class="p-8 text-center text-muted text-sm">暂无欠款</div>
    </div>
    <!-- 桌面端欠款表格 -->
    <div class="card hidden md:block">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 text-left">订单号</th>
              <th class="px-3 py-2 text-left">客户</th>
              <th class="px-3 py-2 text-center">类型</th>
              <th class="px-3 py-2 text-right">订单金额</th>
              <th class="px-3 py-2 text-right">欠款金额</th>
              <th class="px-3 py-2 text-left">创建时间</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="o in unpaidOrders" :key="o.id" class="hover:bg-elevated cursor-pointer" @click="handleViewOrder(o.id)">
              <td class="px-3 py-2 font-mono text-sm text-primary"><span class="todo-dot mr-1.5"></span>{{ o.order_no }}</td>
              <td class="px-3 py-2">{{ o.customer_name }}</td>
              <td class="px-3 py-2 text-center"><StatusBadge type="orderType" :status="o.order_type" /></td>
              <td class="px-3 py-2 text-right">¥{{ fmt(o.total_amount) }}</td>
              <td class="px-3 py-2 text-right font-semibold text-error">¥{{ fmt(o.unpaid_amount) }}</td>
              <td class="px-3 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!unpaidOrders.length" class="p-8 text-center text-muted text-sm">暂无欠款</div>
    </div>

    <!-- ============ 弹窗：收款 ============ -->
    <div v-if="showPaymentModal" class="modal-overlay" @click.self="showPaymentModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="font-semibold">收款</h3>
          <button @click="showPaymentModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="savePayment" class="space-y-3">
            <!-- 客户选择 -->
            <div>
              <label class="label">客户 *</label>
              <select v-model="paymentForm.customer_id" @change="loadCustomerUnpaid" class="input" required>
                <option value="">选择客户</option>
                <option v-for="c in customers.filter(x => x.balance > 0)" :key="c.id" :value="c.id">{{ c.name }} (欠款 ¥{{ formatBalance(c.balance) }})</option>
              </select>
            </div>
            <!-- 核销订单多选 -->
            <div v-if="customerUnpaidOrders.length">
              <label class="label">核销订单</label>
              <div class="space-y-1 max-h-36 overflow-y-auto border rounded p-2">
                <label v-for="o in customerUnpaidOrders" :key="o.id" class="flex items-center p-2 hover:bg-elevated rounded cursor-pointer text-sm">
                  <input type="checkbox" v-model="paymentForm.order_ids" :value="o.id" class="mr-2">
                  <span class="flex-1">{{ o.order_no }}</span>
                  <span class="text-error font-semibold">¥{{ fmt(o.unpaid_amount) }}</span>
                </label>
              </div>
            </div>
            <!-- 金额和方式 -->
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">金额 *</label>
                <input v-model.number="paymentForm.amount" type="number" step="0.01" class="input" required>
              </div>
              <div>
                <label class="label">方式</label>
                <select v-model="paymentForm.payment_method" class="input">
                  <option v-for="pm in paymentMethods" :key="pm.code" :value="pm.code">{{ pm.name }}</option>
                </select>
              </div>
            </div>
            <!-- 操作按钮 -->
            <div class="flex gap-3 pt-3">
              <button type="button" @click="showPaymentModal = false" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-success flex-1">确认收款</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 欠款明细 Tab
 * 包含欠款列表（客户筛选）+ 收款弹窗
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useCustomersStore } from '../../../stores/customers'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import { getUnpaidOrders, createPayment } from '../../../api/finance'
import { orderTypeNames, orderTypeBadges } from '../../../utils/constants'
import StatusBadge from '../../common/StatusBadge.vue'

// --- Props & Emits ---
const props = defineProps({
  /** 当前 Tab 是否激活 */
  active: Boolean
})
const emit = defineEmits([
  'data-changed',  // 数据变更通知父组件
  'view-order'     // 请求父组件查看订单详情
])

// --- Stores ---
const appStore = useAppStore()
const customersStore = useCustomersStore()
const settingsStore = useSettingsStore()

// --- Composables ---
const { fmt, fmtDate, formatBalance, getBalanceLabel } = useFormat()
const { hasPermission } = usePermission()

// --- 计算属性（来自 store） ---
/** 客户列表 */
const customers = computed(() => customersStore.customers)
/** 收款方式列表 */
const paymentMethods = computed(() => settingsStore.paymentMethods)

// ===== 本地状态 =====
/** 提交中标志 */
const submitting = ref(false)
/** 客户筛选选中值 */
const financeCustomerId = ref('')

/** 欠款订单列表 */
const unpaidOrders = ref([])
/** 收款弹窗中选中客户的欠款订单 */
const customerUnpaidOrders = ref([])

/** 收款弹窗可见性 */
const showPaymentModal = ref(false)
/** 收款表单 */
const paymentForm = reactive({ customer_id: '', order_ids: [], amount: 0, payment_method: 'cash' })

// ===== 数据加载 =====
/** 加载欠款订单列表 */
const loadUnpaid = async () => {
  try {
    const p = financeCustomerId.value ? { customer_id: financeCustomerId.value } : {}
    const { data } = await getUnpaidOrders(p)
    unpaidOrders.value = data
  } catch (e) {
    console.error(e)
  }
}

/** 加载指定客户的欠款订单（收款弹窗用） */
const loadCustomerUnpaid = async () => {
  if (!paymentForm.customer_id) {
    customerUnpaidOrders.value = []
    return
  }
  try {
    const { data } = await getUnpaidOrders({ customer_id: paymentForm.customer_id })
    customerUnpaidOrders.value = data
    // 自动填充总欠款金额
    paymentForm.amount = data.reduce((s, o) => s + o.unpaid_amount, 0)
  } catch (e) {
    console.error(e)
  }
}

// ===== 查看订单详情（委托给父组件） =====
/** 点击欠款行查看订单——emit 到父组件转发 */
const handleViewOrder = (id) => {
  emit('view-order', id)
}

// ===== 收款 =====
/** 打开收款弹窗 */
const openPaymentModal = () => {
  paymentForm.customer_id = ''
  paymentForm.order_ids = []
  paymentForm.amount = 0
  paymentForm.payment_method = 'cash'
  customerUnpaidOrders.value = []
  showPaymentModal.value = true
}

/** 提交收款 */
const savePayment = async () => {
  if (!paymentForm.order_ids.length) {
    appStore.showToast('请选择订单', 'error')
    return
  }
  if (!paymentForm.amount || paymentForm.amount <= 0) {
    appStore.showToast('收款金额必须大于0', 'error')
    return
  }
  const confirmed = await appStore.customConfirm('确认收款', `确认收款 ¥${Number(paymentForm.amount).toFixed(2)} ？`)
  if (!confirmed) return
  if (submitting.value) return
  submitting.value = true
  try {
    await createPayment(paymentForm)
    appStore.showToast('收款成功')
    showPaymentModal.value = false
    loadUnpaid()
    customersStore.loadCustomers()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '收款失败', 'error')
  } finally {
    submitting.value = false
  }
}

// ===== 刷新方法（暴露给父组件） =====
/** 刷新欠款列表 */
const refresh = () => {
  loadUnpaid()
}

// 暴露给父组件的方法
defineExpose({ refresh, openPaymentModal })

// ===== 初始化 =====
onMounted(() => {
  // 激活时加载欠款数据
  if (props.active) loadUnpaid()
})
</script>
