<template>
  <div>
    <!-- Mobile cards -->
    <div class="md:hidden space-y-2">
      <div v-for="o in filteredPurchaseOrders" :key="'pay' + o.id" class="card p-3 cursor-pointer" @click="viewPurchaseOrder(o.id)">
        <div class="flex justify-between items-start mb-1">
          <div class="font-medium text-sm font-mono text-primary">{{ o.po_no }}</div>
          <div class="text-lg font-bold">¥{{ fmt(o.total_amount) }}</div>
        </div>
        <div class="flex justify-between items-center">
          <div class="text-xs text-muted">{{ o.supplier_name }} · {{ fmtDate(o.created_at) }}</div>
          <div v-if="o.status === 'pending_review' && hasPermission('purchase_approve')" class="flex gap-1">
            <button @click.stop="handleApprovePO(o.id)" class="btn btn-sm text-xs" style="background:#1677FF;color:#fff">通过</button>
            <button @click.stop="handleRejectPO(o.id)" class="btn btn-sm text-xs" style="background:#ef4444;color:#fff">拒绝</button>
          </div>
          <div v-else-if="o.status === 'pending_review'" class="text-xs text-purple-emphasis">待审核</div>
          <div v-else-if="o.status === 'pending'" class="flex gap-1">
            <button @click.stop="handleConfirmPurchasePayment(o.id)" class="btn btn-warning btn-sm text-xs">确认</button>
            <button @click.stop="handleCancelPO(o.id)" class="btn btn-sm text-xs" style="background:#ef4444;color:#fff">取消</button>
          </div>
          <div v-else-if="o.status === 'cancelled'" class="text-xs text-muted">已取消</div>
          <div v-else-if="o.status === 'rejected'" class="text-xs text-error">已拒绝</div>
          <div v-else-if="o.status === 'returned'" class="text-xs text-warning">已退货</div>
          <div v-else class="text-xs text-success">已付款 {{ o.paid_by_name }} {{ fmtDate(o.paid_at) }}<span v-if="o.payment_method"> · {{ getDisbursementMethodName(o.payment_method) }}</span></div>
        </div>
      </div>
      <div v-if="!filteredPurchaseOrders.length" class="p-8 text-center text-muted text-sm">暂无应付记录</div>
    </div>
    <!-- Desktop table -->
    <div class="card hidden md:block">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 text-left">采购单号</th>
              <th class="px-3 py-2 text-left">供应商</th>
              <th class="px-3 py-2 text-right">总金额(含税)</th>
              <th class="px-3 py-2 text-left">创建时间</th>
              <th class="px-3 py-2 text-left">付款方式</th>
              <th class="px-3 py-2 text-center">状态</th>
              <th class="px-3 py-2 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="o in filteredPurchaseOrders" :key="'pay' + o.id" class="hover:bg-elevated cursor-pointer" @click="viewPurchaseOrder(o.id)">
              <td class="px-3 py-2 font-mono text-sm text-primary">{{ o.po_no }}</td>
              <td class="px-3 py-2">{{ o.supplier_name }}</td>
              <td class="px-3 py-2 text-right font-semibold">¥{{ fmt(o.total_amount) }}</td>
              <td class="px-3 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
              <td class="px-3 py-2">{{ o.payment_method ? getDisbursementMethodName(o.payment_method) : '-' }}</td>
              <td class="px-3 py-2 text-center"><StatusBadge type="purchaseStatus" :status="o.status" /></td>
              <td class="px-3 py-2 text-center">
                <div v-if="o.status === 'pending_review' && hasPermission('purchase_approve')" class="flex gap-1 justify-center">
                  <button @click.stop="handleApprovePO(o.id)" class="btn btn-sm text-xs" style="background:#1677FF;color:#fff">通过</button>
                  <button @click.stop="handleRejectPO(o.id)" class="btn btn-sm text-xs" style="background:#ef4444;color:#fff">拒绝</button>
                </div>
                <span v-else-if="o.status === 'pending_review'" class="text-xs text-purple-emphasis">待审核</span>
                <div v-else-if="o.status === 'pending'" class="flex gap-1 justify-center">
                  <button @click.stop="handleConfirmPurchasePayment(o.id)" class="btn btn-warning btn-sm text-xs">确认</button>
                  <button @click.stop="handleCancelPO(o.id)" class="btn btn-sm text-xs" style="background:#ef4444;color:#fff">取消</button>
                </div>
                <span v-else-if="o.status === 'cancelled'" class="text-xs text-muted">已取消</span>
                <span v-else-if="o.status === 'rejected'" class="text-xs text-error">已拒绝</span>
                <span v-else-if="o.status === 'returned'" class="text-xs text-warning">已退货</span>
                <span v-else class="text-xs text-success">{{ o.paid_by_name }} {{ fmtDate(o.paid_at) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!filteredPurchaseOrders.length" class="p-8 text-center text-muted text-sm">暂无应付记录</div>
    </div>

    <!-- Modal: Payable Payment Confirm -->
    <div v-if="showPayablePayModal" class="modal-overlay" @click.self="showPayablePayModal = false">
      <div class="modal-content" style="max-width:400px">
        <div class="modal-header">
          <h3 class="font-semibold">确认付款</h3>
          <button @click="showPayablePayModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body space-y-4">
          <div class="p-3 bg-elevated rounded-lg text-sm">
            <div class="font-semibold font-mono">{{ payablePayForm.po_no }}</div>
            <div class="text-lg font-bold mt-1">¥{{ fmt(payablePayForm.amount) }}</div>
          </div>
          <div>
            <label class="label">付款方式</label>
            <select v-model="payablePayForm.payment_method" class="input">
              <option value="">不指定</option>
              <option v-for="pm in disbursementMethods" :key="pm.code" :value="pm.code">{{ pm.name }}</option>
            </select>
          </div>
          <div class="flex gap-3 pt-2">
            <button @click="showPayablePayModal = false" class="btn btn-secondary flex-1">取消</button>
            <button @click="submitPayablePay" :disabled="submitting" class="btn btn-warning flex-1">{{ submitting ? '处理中...' : '确认付款' }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal: Purchase Order Detail -->
    <div v-if="showPurchaseDetailModal" class="modal-overlay" @click.self="showPurchaseDetailModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="font-semibold">采购订单详情</h3>
          <button @click="showPurchaseDetailModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body" v-if="purchaseOrderDetail">
          <div class="mb-4 p-3 bg-elevated rounded-lg">
            <div class="flex justify-between items-start mb-2">
              <div>
                <div class="font-semibold font-mono">{{ purchaseOrderDetail.po_no }}</div>
                <div class="text-sm text-muted">{{ purchaseOrderDetail.supplier_name }} · {{ fmtDate(purchaseOrderDetail.created_at) }}</div>
              </div>
              <StatusBadge type="purchaseStatus" :status="purchaseOrderDetail.status" />
            </div>
            <div class="grid detail-grid grid-cols-2 gap-2 text-sm">
              <div><span class="text-muted">总金额:</span> <span class="font-semibold">¥{{ fmt(purchaseOrderDetail.total_amount) }}</span></div>
              <div><span class="text-muted">创建人:</span> {{ purchaseOrderDetail.creator_name }}</div>
              <div v-if="purchaseOrderDetail.remark" class="col-span-2"><span class="text-muted">备注:</span> {{ purchaseOrderDetail.remark }}</div>
            </div>
          </div>
          <div class="font-semibold mb-2 text-sm">商品明细</div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-elevated">
                <tr>
                  <th class="px-2 py-1 text-left">商品</th>
                  <th class="px-2 py-1 text-right">单价</th>
                  <th class="px-2 py-1 text-right">数量</th>
                  <th class="px-2 py-1 text-right">金额</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr v-for="item in purchaseOrderDetail.items" :key="item.product_id">
                  <td class="px-2 py-1"><div>{{ item.product_name }}</div><div class="text-xs text-muted">{{ item.product_sku }}</div></td>
                  <td class="px-2 py-1 text-right">{{ fmt(item.unit_price) }}</td>
                  <td class="px-2 py-1 text-right">{{ item.quantity }}</td>
                  <td class="px-2 py-1 text-right font-semibold">{{ fmt(item.amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="flex gap-3 pt-4">
            <button type="button" @click="showPurchaseDetailModal = false" class="btn btn-secondary flex-1">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useAppStore } from '../../stores/app'
import { useSettingsStore } from '../../stores/settings'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { getPurchaseOrders, getPurchaseOrder, approvePurchaseOrder as apiApprovePO, rejectPurchaseOrder as apiRejectPO, payPurchaseOrder, cancelPurchaseOrder as apiCancelPO } from '../../api/purchase'
import StatusBadge from '../common/StatusBadge.vue'

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()

const disbursementMethods = computed(() => settingsStore.disbursementMethods)

const purchaseOrders = ref([])
const submitting = ref(false)
const showPayablePayModal = ref(false)
const showPurchaseDetailModal = ref(false)
const purchaseOrderDetail = ref(null)
const payablePayForm = reactive({ po_id: null, po_no: '', amount: 0, payment_method: '' })

const filteredPurchaseOrders = computed(() => {
  return purchaseOrders.value.filter(x => ['pending_review', 'pending', 'paid', 'partial', 'completed', 'cancelled', 'rejected', 'returned'].includes(x.status))
})

const getDisbursementMethodName = (m) => {
  const found = disbursementMethods.value.find(p => p.code === m)
  if (found) return found.name
  return { cash: '现金', bank_public: '对公转账', bank_private: '对私转账', wechat: '微信', alipay: '支付宝' }[m] || m
}

const loadPurchaseOrdersData = async () => {
  try {
    const { data } = await getPurchaseOrders({})
    purchaseOrders.value = data.items || data
  } catch (e) {
    console.error(e)
    appStore.showToast(e.response?.data?.detail || '加载数据失败', 'error')
  }
}

const viewPurchaseOrder = async (id) => {
  try {
    const { data } = await getPurchaseOrder(id)
    purchaseOrderDetail.value = data
    showPurchaseDetailModal.value = true
  } catch (e) {
    appStore.showToast('加载详情失败', 'error')
  }
}

const handleApprovePO = async (id) => {
  if (!await appStore.customConfirm('确认审核', '确认审核通过此采购单？')) return
  try {
    await apiApprovePO(id)
    appStore.showToast('审核通过')
    loadPurchaseOrdersData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

const handleRejectPO = async (id) => {
  if (!await appStore.customConfirm('拒绝确认', '确认要拒绝此采购单吗？')) return
  try {
    await apiRejectPO(id)
    appStore.showToast('已拒绝')
    loadPurchaseOrdersData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

const handleConfirmPurchasePayment = (id) => {
  const po = purchaseOrders.value.find(o => o.id === id)
  if (!po) return
  payablePayForm.po_id = id
  payablePayForm.po_no = po.po_no
  payablePayForm.amount = po.total_amount
  payablePayForm.payment_method = ''
  showPayablePayModal.value = true
}

const submitPayablePay = async () => {
  if (submitting.value) return
  const confirmed = await appStore.customConfirm('付款确认', `确认对采购单 ${payablePayForm.po_no} 付款 ¥${Number(payablePayForm.amount).toFixed(2)} ？`)
  if (!confirmed) return
  submitting.value = true
  try {
    const data = {}
    if (payablePayForm.payment_method) data.payment_method = payablePayForm.payment_method
    await payPurchaseOrder(payablePayForm.po_id, data)
    appStore.showToast('付款确认成功')
    showPayablePayModal.value = false
    loadPurchaseOrdersData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  } finally {
    submitting.value = false
  }
}

const handleCancelPO = async (id) => {
  if (!await appStore.customConfirm('取消确认', '确认要取消此采购单吗？此操作不可撤销。')) return
  try {
    await apiCancelPO(id)
    appStore.showToast('已取消')
    loadPurchaseOrdersData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

defineExpose({ refresh: loadPurchaseOrdersData })

onMounted(() => { loadPurchaseOrdersData() })
</script>
