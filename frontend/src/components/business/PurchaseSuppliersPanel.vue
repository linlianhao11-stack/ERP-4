<template>
  <div>
    <!-- Mobile cards -->
    <div class="md:hidden space-y-2">
      <!-- 移动端搜索 -->
      <div class="flex flex-wrap items-center gap-2 mb-2">
        <div class="toolbar-search-wrapper flex-1" style="max-width:none">
          <Search :size="14" class="toolbar-search-icon" />
          <input v-model="supplierSearch" class="toolbar-search" placeholder="搜索供应商...">
        </div>
      </div>
      <div v-for="s in filteredSuppliers" :key="s.id" class="card p-3 cursor-pointer" @click="openSupplierDetail(s)">
        <div class="flex justify-between items-start mb-1">
          <div class="font-medium text-sm">{{ s.name }}</div>
          <div class="flex gap-2 text-xs" @click.stop>
            <button @click="openSupplierForm(s)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-info-subtle text-info-emphasis transition-colors">编辑</button>
            <button @click="handleDeleteSupplier(s.id)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-error-subtle text-error-emphasis transition-colors">停用</button>
          </div>
        </div>
        <div class="text-xs text-muted">{{ s.contact_person || '-' }} · {{ s.phone || '-' }}</div>
        <div class="flex gap-3 mt-1 text-xs">
          <span v-if="s.rebate_balance > 0" class="text-success">返利: ¥{{ fmt(s.rebate_balance) }}</span>
          <span v-if="s.credit_balance > 0" class="text-primary">在账资金: ¥{{ fmt(s.credit_balance) }}</span>
        </div>
      </div>
      <div v-if="!filteredSuppliers.length" class="p-8 text-center text-muted text-sm">暂无供应商</div>
    </div>

    <!-- Desktop table -->
    <div class="card hidden md:block" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <div class="toolbar-search-wrapper">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="supplierSearch" class="toolbar-search" placeholder="搜索供应商...">
          </div>
        </template>
        <template #actions>
          <button @click="openSupplierForm(null)" class="btn btn-primary btn-sm">新增供应商</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-2 py-2 text-left">供应商名称</th>
              <th class="px-2 py-2 text-left">联系人</th>
              <th class="px-2 py-2 text-left">电话</th>
              <th class="px-2 py-2 text-right">返利余额</th>
              <th class="px-2 py-2 text-right">在账资金</th>
              <th class="px-2 py-2 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="s in filteredSuppliers" :key="s.id" class="hover:bg-elevated cursor-pointer" @click="openSupplierDetail(s)">
              <td class="px-2 py-2 font-medium">{{ s.name }}</td>
              <td class="px-2 py-2 text-secondary">{{ s.contact_person || '-' }}</td>
              <td class="px-2 py-2 text-secondary">{{ s.phone || '-' }}</td>
              <td class="px-2 py-2 text-right">
                <span v-if="s.rebate_balance > 0" class="text-success font-semibold">¥{{ fmt(s.rebate_balance) }}</span>
                <span v-else class="text-muted">-</span>
              </td>
              <td class="px-2 py-2 text-right">
                <span v-if="s.credit_balance > 0" class="text-primary font-semibold">¥{{ fmt(s.credit_balance) }}</span>
                <span v-else class="text-muted">-</span>
              </td>
              <td class="px-2 py-2 text-center" @click.stop>
                <div class="flex gap-1 justify-center">
                  <button @click="openSupplierForm(s)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-info-subtle text-info-emphasis transition-colors">编辑</button>
                  <button @click="handleDeleteSupplier(s.id)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-error-subtle text-error-emphasis transition-colors">停用</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!filteredSuppliers.length" class="p-8 text-center text-muted text-sm">暂无供应商</div>
    </div>

    <!-- Supplier Edit Modal -->
    <div v-if="showSupplierModal" class="modal-backdrop" @click.self="showSupplierModal = false">
      <div class="modal max-w-lg">
        <div class="modal-header">
          <h3>{{ supplierForm.id ? '编辑供应商' : '新增供应商' }}</h3>
          <button @click="showSupplierModal = false" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveSupplier">
          <div class="modal-body">
            <div class="space-y-3">
              <div>
                <label class="label">供应商名称 *</label>
                <input v-model="supplierForm.name" class="input" required placeholder="供应商名称">
              </div>
              <div class="grid form-grid grid-cols-2 gap-3">
                <div><label class="label">联系人</label><input v-model="supplierForm.contact_person" class="input"></div>
                <div><label class="label">电话</label><input v-model="supplierForm.phone" class="input"></div>
              </div>
              <div>
                <label class="label">税号</label>
                <input v-model="supplierForm.tax_id" class="input" placeholder="纳税人识别号">
              </div>
              <div class="grid form-grid grid-cols-2 gap-3">
                <div><label class="label">银行账号</label><input v-model="supplierForm.bank_account" class="input"></div>
                <div><label class="label">开户行</label><input v-model="supplierForm.bank_name" class="input"></div>
              </div>
              <div>
                <label class="label">地址</label>
                <input v-model="supplierForm.address" class="input">
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" @click="showSupplierModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1">保存</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Supplier Detail Modal -->
    <div v-if="showSupplierDetailModal" class="modal-backdrop" @click.self="showSupplierDetailModal = false">
      <div class="modal max-w-3xl">
        <div class="modal-header">
          <h3>供应商详情 - {{ supplierDetail?.supplier?.name }}</h3>
          <button @click="showSupplierDetailModal = false" class="modal-close">&times;</button>
        </div>
        <div v-if="supplierDetail" class="modal-body">
          <div class="space-y-4">
            <!-- 摘要 -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div class="bg-info-subtle rounded-lg p-3 text-center">
                <div class="text-xs text-muted">采购单数</div>
                <div class="text-lg font-bold text-primary">{{ supplierDetail.stats.total_count }}</div>
              </div>
              <div class="bg-success-subtle rounded-lg p-3 text-center">
                <div class="text-xs text-muted">采购总额</div>
                <div class="text-lg font-bold text-success">¥{{ fmt(supplierDetail.stats.total_amount) }}</div>
              </div>
              <div class="bg-purple-subtle rounded-lg p-3 text-center">
                <div class="text-xs text-muted">返利余额</div>
                <div class="text-lg font-bold text-purple-emphasis">¥{{ fmt(supplierDetail.supplier.rebate_balance) }}</div>
              </div>
              <div class="bg-orange-subtle rounded-lg p-3 text-center">
                <div class="text-xs text-muted">在账资金</div>
                <div class="text-lg font-bold text-warning">¥{{ fmt(supplierDetail.supplier.credit_balance) }}</div>
                <button v-if="supplierDetail.supplier.credit_balance > 0 && hasPermission('purchase')"
                  @click="openCreditRefund" class="text-xs text-warning underline mt-1">退款</button>
              </div>
            </div>

            <!-- 月份筛选 -->
            <div class="flex items-center gap-2">
              <select v-model="supplierTransMonth" @change="loadSupplierDetail(supplierDetail.supplier.id)" class="input text-sm" style="width:140px">
                <option value="">全部月份</option>
                <option v-for="m in supplierDetail.available_months" :key="m" :value="m">{{ m }}</option>
              </select>
              <span class="text-xs text-muted">已完成 {{ supplierDetail.stats.completed_count }} 单，退货 {{ supplierDetail.stats.returned_count }} 单(¥{{ fmt(supplierDetail.stats.returned_amount) }})</span>
            </div>

            <!-- 采购记录 -->
            <div>
              <h4 class="font-semibold text-sm mb-2">采购记录</h4>
              <div class="table-container" style="max-height:200px;overflow-y:auto">
                <table class="w-full text-xs">
                  <thead class="bg-elevated sticky top-0">
                    <tr>
                      <th class="px-2 py-1 text-left">单号</th>
                      <th class="px-2 py-1 text-center">状态</th>
                      <th class="px-2 py-1 text-right">金额</th>
                      <th class="px-2 py-1 text-right">退货</th>
                      <th class="px-2 py-1 text-left">日期</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y">
                    <tr v-for="o in supplierDetail.orders" :key="o.id" class="hover:bg-elevated cursor-pointer" @click="showSupplierDetailModal = false; emit('view-order', o.id)">
                      <td class="px-2 py-1 font-mono">{{ o.po_no }}</td>
                      <td class="px-2 py-1 text-center"><StatusBadge type="purchaseStatus" :status="o.status" /></td>
                      <td class="px-2 py-1 text-right font-semibold">¥{{ fmt(o.total_amount) }}</td>
                      <td class="px-2 py-1 text-right">
                        <span v-if="o.return_amount > 0" class="text-warning">¥{{ fmt(o.return_amount) }}</span>
                        <span v-else class="text-muted">-</span>
                      </td>
                      <td class="px-2 py-1 text-muted">{{ fmtDate(o.created_at) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-if="!supplierDetail.orders.length" class="text-center text-muted text-xs py-4">暂无采购记录</div>
            </div>

            <!-- 在账资金流水 -->
            <div v-if="supplierDetail.credit_logs.length">
              <h4 class="font-semibold text-sm mb-2">在账资金流水</h4>
              <div class="table-container" style="max-height:180px;overflow-y:auto">
                <table class="w-full text-xs">
                  <thead class="bg-elevated sticky top-0">
                    <tr>
                      <th class="px-2 py-1 text-left">时间</th>
                      <th class="px-2 py-1 text-center">类型</th>
                      <th class="px-2 py-1 text-right">金额</th>
                      <th class="px-2 py-1 text-right">余额</th>
                      <th class="px-2 py-1 text-left">备注</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y">
                    <tr v-for="log in supplierDetail.credit_logs" :key="log.id">
                      <td class="px-2 py-1 text-muted">{{ fmtDate(log.created_at) }}</td>
                      <td class="px-2 py-1 text-center">
                        <span v-if="log.type === 'credit_charge'" class="badge badge-green">退货转入</span>
                        <span v-else-if="log.type === 'credit_use'" class="badge badge-blue">采购抵扣</span>
                        <span v-else-if="log.type === 'credit_refund'" class="badge badge-orange">退款</span>
                      </td>
                      <td class="px-2 py-1 text-right" :class="log.amount > 0 ? 'text-success' : 'text-error'">
                        {{ log.amount > 0 ? '+' : '' }}¥{{ fmt(Math.abs(log.amount)) }}
                      </td>
                      <td class="px-2 py-1 text-right">¥{{ fmt(log.balance_after) }}</td>
                      <td class="px-2 py-1 text-muted truncate" style="max-width:150px">{{ log.remark }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showSupplierDetailModal = false" class="btn btn-secondary flex-1">关闭</button>
        </div>
      </div>
    </div>

    <!-- Credit Refund Modal -->
    <div v-if="showCreditRefundModal" class="modal-backdrop" @click.self="showCreditRefundModal = false">
      <div class="modal" style="max-width:400px">
        <div class="modal-header">
          <h3>在账资金退款</h3>
          <button @click="showCreditRefundModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="space-y-3">
            <div class="text-sm text-secondary">
              供应商: <b>{{ supplierDetail?.supplier?.name }}</b><br>
              可退金额: <b class="text-warning">¥{{ fmt(supplierDetail?.supplier?.credit_balance || 0) }}</b>
            </div>
            <div>
              <label class="label">退款金额 *</label>
              <input v-model.number="creditRefundForm.amount" type="number" step="0.01" min="0.01"
                :max="supplierDetail?.supplier?.credit_balance" class="input" placeholder="输入退款金额">
            </div>
            <div>
              <label class="label">备注</label>
              <input v-model="creditRefundForm.remark" class="input" placeholder="退款原因（选填）">
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showCreditRefundModal = false" class="btn btn-secondary flex-1">取消</button>
          <button @click="confirmCreditRefund" class="btn btn-warning flex-1"
            :disabled="appStore.submitting">{{ appStore.submitting ? '处理中...' : '确认退款' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Search } from 'lucide-vue-next'
import { useAppStore } from '../../stores/app'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import {
  getSuppliers, createSupplier, updateSupplier, deleteSupplier as deleteSupplierApi,
  getSupplierTransactions, refundSupplierCredit
} from '../../api/purchase'
import StatusBadge from '../common/StatusBadge.vue'
import PageToolbar from '../common/PageToolbar.vue'

const emit = defineEmits(['view-order', 'data-changed'])

const appStore = useAppStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()

// State
const suppliers = ref([])
const supplierSearch = ref('')
const showSupplierModal = ref(false)
const showSupplierDetailModal = ref(false)
const showCreditRefundModal = ref(false)
const supplierDetail = ref(null)
const supplierTransMonth = ref('')

const supplierForm = reactive({
  id: null, name: '', contact_person: '', phone: '',
  tax_id: '', bank_account: '', bank_name: '', address: ''
})

const creditRefundForm = reactive({ amount: null, remark: '' })

// 搜索过滤
const filteredSuppliers = computed(() => {
  const q = supplierSearch.value.trim().toLowerCase()
  if (!q) return suppliers.value
  return suppliers.value.filter(s => s.name.toLowerCase().includes(q))
})

// Data loading
const loadSuppliers = async () => {
  try {
    const { data } = await getSuppliers()
    suppliers.value = data.items || data
  } catch (e) {
    console.error(e)
  }
}

// Supplier CRUD
const openSupplierForm = (s) => {
  if (s) {
    Object.assign(supplierForm, {
      id: s.id, name: s.name, contact_person: s.contact_person || '',
      phone: s.phone || '', tax_id: s.tax_id || '', bank_account: s.bank_account || '',
      bank_name: s.bank_name || '', address: s.address || ''
    })
  } else {
    Object.assign(supplierForm, {
      id: null, name: '', contact_person: '', phone: '',
      tax_id: '', bank_account: '', bank_name: '', address: ''
    })
  }
  showSupplierModal.value = true
}

const saveSupplier = async () => {
  if (!supplierForm.name.trim()) {
    appStore.showToast('请输入供应商名称', 'error')
    return
  }
  try {
    if (supplierForm.id) {
      await updateSupplier(supplierForm.id, supplierForm)
    } else {
      await createSupplier(supplierForm)
    }
    appStore.showToast('保存成功')
    showSupplierModal.value = false
    loadSuppliers()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}

const handleDeleteSupplier = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定停用该供应商？')) return
  try {
    await deleteSupplierApi(id)
    appStore.showToast('已停用')
    loadSuppliers()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

// Supplier detail
const openSupplierDetail = async (s) => {
  supplierTransMonth.value = ''
  await loadSupplierDetail(s.id)
  showSupplierDetailModal.value = true
}

const loadSupplierDetail = async (supplierId) => {
  try {
    const params = {}
    if (supplierTransMonth.value) params.month = supplierTransMonth.value
    const { data } = await getSupplierTransactions(supplierId, params)
    supplierDetail.value = data
  } catch (e) {
    appStore.showToast('加载供应商详情失败', 'error')
  }
}

// Credit refund
const openCreditRefund = () => {
  creditRefundForm.amount = null
  creditRefundForm.remark = ''
  showCreditRefundModal.value = true
}

const confirmCreditRefund = async () => {
  if (!creditRefundForm.amount || creditRefundForm.amount <= 0) {
    appStore.showToast('请输入退款金额', 'error')
    return
  }
  if (creditRefundForm.amount > supplierDetail.value.supplier.credit_balance) {
    appStore.showToast('退款金额超过在账资金余额', 'error')
    return
  }
  if (!await appStore.customConfirm('确认退款', `确认向供应商 ${supplierDetail.value.supplier.name} 退还在账资金 ¥${creditRefundForm.amount.toFixed(2)}？`)) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await refundSupplierCredit(supplierDetail.value.supplier.id, {
      amount: parseFloat(creditRefundForm.amount.toFixed(2)),
      remark: creditRefundForm.remark || null
    })
    appStore.showToast('退款成功')
    showCreditRefundModal.value = false
    await loadSupplierDetail(supplierDetail.value.supplier.id)
    loadSuppliers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '退款失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

defineExpose({ refresh: loadSuppliers })

onMounted(() => { loadSuppliers() })
</script>
