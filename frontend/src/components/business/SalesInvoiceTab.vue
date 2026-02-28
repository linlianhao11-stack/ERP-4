<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="filters.status" class="form-input w-28" @change="loadList">
        <option value="">全部状态</option>
        <option value="draft">草稿</option>
        <option value="confirmed">已确认</option>
        <option value="cancelled">已作废</option>
      </select>
      <select v-model="filters.customer_id" class="form-input w-36" @change="loadList">
        <option value="">全部客户</option>
        <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <input v-model="filters.date_from" type="date" class="form-input w-36" @change="loadList" placeholder="开始日期" />
      <input v-model="filters.date_to" type="date" class="form-input w-36" @change="loadList" placeholder="结束日期" />
      <button @click="openPushModal" class="btn btn-primary btn-sm ml-auto">从应收单推送</button>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>发票号</th>
            <th>日期</th>
            <th>客户</th>
            <th>类型</th>
            <th class="text-right">不含税金额</th>
            <th class="text-right">税额</th>
            <th class="text-right">价税合计</th>
            <th>状态</th>
            <th>凭证号</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="10" class="text-center text-[#86868b] py-8">暂无数据</td>
          </tr>
          <tr v-for="inv in items" :key="inv.id">
            <td class="font-mono text-[12px]">{{ inv.invoice_no }}</td>
            <td>{{ inv.invoice_date }}</td>
            <td>{{ inv.customer_name || inv.counterparty_name }}</td>
            <td><span :class="inv.invoice_type === 'special' ? 'badge badge-blue' : 'badge badge-gray'">{{ inv.invoice_type === 'special' ? '专票' : '普票' }}</span></td>
            <td class="text-right">{{ inv.amount_without_tax }}</td>
            <td class="text-right">{{ inv.tax_amount }}</td>
            <td class="text-right">{{ inv.total_amount }}</td>
            <td><span :class="statusBadge(inv.status)">{{ statusName(inv.status) }}</span></td>
            <td class="font-mono text-[12px]">{{ inv.voucher_no || '-' }}</td>
            <td @click.stop>
              <div class="flex gap-1">
                <button v-if="inv.status === 'draft'" @click="handleConfirm(inv)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#e8f8ee] text-[#248a3d]">确认</button>
                <button v-if="inv.status === 'draft' || inv.status === 'confirmed'" @click="handleCancel(inv)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#ffeaee] text-[#ff3b30]">作废</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-[#86868b] leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>

    <!-- 从应收单推送弹窗 -->
    <Transition name="fade">
      <div v-if="showPush" class="modal-backdrop" @click.self="showPush = false">
        <div class="modal" style="max-width: 700px">
          <div class="modal-header">
            <h3>从应收单推送销项发票</h3>
            <button @click="showPush = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <!-- 选择应收单 -->
            <div class="mb-4">
              <label class="label mb-1">选择已完成的应收单</label>
              <select v-model="pushForm.receivable_bill_id" class="form-input w-full" @change="onReceivableBillSelect">
                <option value="">请选择</option>
                <option v-for="rb in receivableBills" :key="rb.id" :value="rb.id">
                  {{ rb.bill_no }} - {{ rb.customer_name }} - {{ rb.total_amount }}
                </option>
              </select>
            </div>

            <template v-if="pushForm.receivable_bill_id">
              <div class="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <label class="label">发票类型</label>
                  <select v-model="pushForm.invoice_type" class="form-input">
                    <option value="special">增值税专用发票</option>
                    <option value="normal">增值税普通发票</option>
                  </select>
                </div>
                <div>
                  <label class="label">发票日期</label>
                  <input v-model="pushForm.invoice_date" type="date" class="form-input" />
                </div>
                <div>
                  <label class="label">税率 (%)</label>
                  <input v-model.number="pushForm.tax_rate" type="number" step="0.01" min="0" max="100" class="form-input" />
                </div>
                <div>
                  <label class="label">备注</label>
                  <input v-model="pushForm.remark" class="form-input" />
                </div>
              </div>

              <!-- 明细预览 -->
              <div v-if="selectedReceivable" class="bg-[#f5f5f7] rounded-xl p-3 mb-3">
                <div class="text-[12px] font-semibold text-[#86868b] mb-2">发票金额预览</div>
                <div class="grid grid-cols-3 gap-2 text-[13px]">
                  <div>不含税金额: <span class="font-medium">{{ previewAmountWithoutTax }}</span></div>
                  <div>税额: <span class="font-medium">{{ previewTaxAmount }}</span></div>
                  <div>价税合计: <span class="font-medium">{{ selectedReceivable.total_amount }}</span></div>
                </div>
              </div>
            </template>
          </div>
          <div class="modal-footer">
            <button @click="showPush = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handlePush" :disabled="submitting || !pushForm.receivable_bill_id" class="btn btn-primary btn-sm">确认推送</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getInvoices, pushInvoiceFromReceivable, confirmInvoice, cancelInvoice, getReceivableBills } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const filters = ref({ status: '', customer_id: '', date_from: '', date_to: '' })
const customers = ref([])
const showPush = ref(false)
const submitting = ref(false)
const receivableBills = ref([])
const selectedReceivable = ref(null)

const pushForm = ref({
  receivable_bill_id: '',
  invoice_type: 'special',
  invoice_date: new Date().toISOString().slice(0, 10),
  tax_rate: 13,
  remark: '',
})

const statusName = (s) => ({ draft: '草稿', confirmed: '已确认', cancelled: '已作废' }[s] || s)
const statusBadge = (s) => ({ draft: 'badge badge-yellow', confirmed: 'badge badge-green', cancelled: 'badge badge-gray' }[s] || 'badge')

const previewAmountWithoutTax = computed(() => {
  if (!selectedReceivable.value) return '0.00'
  const total = parseFloat(selectedReceivable.value.total_amount) || 0
  const rate = pushForm.value.tax_rate / 100
  return (total / (1 + rate)).toFixed(2)
})

const previewTaxAmount = computed(() => {
  if (!selectedReceivable.value) return '0.00'
  const total = parseFloat(selectedReceivable.value.total_amount) || 0
  return (total - parseFloat(previewAmountWithoutTax.value)).toFixed(2)
})

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = {
    account_set_id: accountingStore.currentAccountSetId,
    direction: 'output',
    page: page.value,
    page_size: pageSize,
  }
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.customer_id) params.customer_id = filters.value.customer_id
  if (filters.value.date_from) params.date_from = filters.value.date_from
  if (filters.value.date_to) params.date_to = filters.value.date_to
  try {
    const res = await getInvoices(params)
    items.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    items.value = []
    total.value = 0
  }
}

async function loadCustomers() {
  const res = await api.get('/customers', { params: { limit: 1000 } })
  customers.value = res.data.items || res.data || []
}

async function loadReceivableBills() {
  if (!accountingStore.currentAccountSetId) return
  try {
    const res = await getReceivableBills({
      account_set_id: accountingStore.currentAccountSetId,
      status: 'completed',
      page_size: 500,
    })
    receivableBills.value = res.data.items || []
  } catch {
    receivableBills.value = []
  }
}

function openPushModal() {
  pushForm.value = {
    receivable_bill_id: '',
    invoice_type: 'special',
    invoice_date: new Date().toISOString().slice(0, 10),
    tax_rate: 13,
    remark: '',
  }
  selectedReceivable.value = null
  loadReceivableBills()
  showPush.value = true
}

function onReceivableBillSelect() {
  const id = pushForm.value.receivable_bill_id
  selectedReceivable.value = receivableBills.value.find((rb) => rb.id === id) || null
}

async function handlePush() {
  if (!pushForm.value.receivable_bill_id) {
    appStore.showToast('请选择应收单', 'error')
    return
  }
  submitting.value = true
  try {
    await pushInvoiceFromReceivable({
      account_set_id: accountingStore.currentAccountSetId,
      receivable_bill_id: pushForm.value.receivable_bill_id,
      invoice_type: pushForm.value.invoice_type,
      invoice_date: pushForm.value.invoice_date,
      tax_rate: pushForm.value.tax_rate,
      remark: pushForm.value.remark,
    })
    appStore.showToast('发票推送成功', 'success')
    showPush.value = false
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '推送失败', 'error')
  } finally {
    submitting.value = false
  }
}

async function handleConfirm(inv) {
  if (!confirm(`确认发票 ${inv.invoice_no}？`)) return
  try {
    await confirmInvoice(inv.id)
    appStore.showToast('确认成功', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}

async function handleCancel(inv) {
  if (!confirm(`确认作废发票 ${inv.invoice_no}？此操作不可撤回。`)) return
  try {
    await cancelInvoice(inv.id)
    appStore.showToast('已作废', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '作废失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => { loadList(); loadCustomers() })
</script>
