<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.status" class="toolbar-select" @change="loadList">
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="confirmed">已确认</option>
          </select>
          <div class="toolbar-search-wrapper">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索单号/客户...">
          </div>
        </template>
        <template #actions>
          <button v-if="hasPermission('accounting_ar_edit')" @click="openCreate" class="btn btn-primary btn-sm">新增收款单</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th v-if="rcIsColumnVisible('bill_no')" class="px-2 py-2">单号</th>
              <th v-if="rcIsColumnVisible('receipt_date')" class="px-2 py-2">日期</th>
              <th v-if="rcIsColumnVisible('customer')" class="px-2 py-2">客户</th>
              <th v-if="rcIsColumnVisible('amount')" class="px-2 py-2 text-right">金额</th>
              <th v-if="rcIsColumnVisible('payment_method')" class="px-2 py-2">收款方式</th>
              <th v-if="rcIsColumnVisible('is_advance')" class="px-2 py-2">预收</th>
              <th v-if="rcIsColumnVisible('status')" class="px-2 py-2">状态</th>
              <th v-if="rcIsColumnVisible('remark')" class="px-2 py-2">备注</th>
              <th v-if="rcIsColumnVisible('voucher_no')" class="px-2 py-2">凭证号</th>
              <th v-if="rcIsColumnVisible('actions')" class="px-2 py-2">操作</th>
              <th class="col-selector-th">
                <ColumnMenu :labels="rcColumnLabels" :visible="rcVisibleColumns" pinned="bill_no"
                  @toggle="rcToggleColumn" @reset="rcResetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="100">
                <div class="text-center py-12 text-muted">
                  <div class="text-3xl mb-3">📋</div>
                  <p class="text-sm font-medium mb-1">暂无收款单数据</p>
                  <p class="text-xs text-muted">点击"手动新增"按钮创建第一条记录</p>
                </div>
              </td>
            </tr>
            <tr v-for="b in items" :key="b.id" class="hover:bg-elevated">
              <td v-if="rcIsColumnVisible('bill_no')" class="px-2 py-2 font-mono text-[12px]">
                <span class="max-w-48 truncate inline-block align-bottom" :title="b.bill_no">{{ b.bill_no }}</span>
                <span v-if="b.bill_type === 'return_refund'" class="ml-1 px-1.5 py-0.5 text-xs bg-error/10 text-error rounded">退款</span>
              </td>
              <td v-if="rcIsColumnVisible('receipt_date')" class="px-2 py-2">{{ b.receipt_date }}</td>
              <td v-if="rcIsColumnVisible('customer')" class="px-2 py-2">{{ b.customer_name }}</td>
              <td v-if="rcIsColumnVisible('amount')" class="px-2 py-2 text-right">{{ fmtMoney(b.amount) }}</td>
              <td v-if="rcIsColumnVisible('payment_method')" class="px-2 py-2">{{ b.payment_method }}</td>
              <td v-if="rcIsColumnVisible('is_advance')" class="px-2 py-2">{{ b.is_advance ? '是' : '否' }}</td>
              <td v-if="rcIsColumnVisible('status')" class="px-2 py-2"><span :class="b.status === 'confirmed' ? 'badge badge-green' : 'badge badge-gray'">{{ b.status === 'confirmed' ? '已确认' : '草稿' }}</span></td>
              <td v-if="rcIsColumnVisible('remark')" class="px-2 py-2 text-xs text-muted max-w-48 truncate" :title="b.remark">{{ b.remark || '-' }}</td>
              <td v-if="rcIsColumnVisible('voucher_no')" class="px-2 py-2 font-mono text-[12px]"><span class="max-w-48 truncate inline-block align-bottom" :title="b.voucher_no">{{ b.voucher_no || '-' }}</span></td>
              <td v-if="rcIsColumnVisible('actions')" class="px-2 py-2" @click.stop>
                <button v-if="b.status === 'draft' && hasPermission('accounting_ar_confirm')" @click="confirmBill(b)" class="text-xs px-2.5 py-1 rounded-md bg-success-subtle text-success-emphasis font-medium">确认</button>
              </td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>

    <!-- 新增弹窗 -->
    <Transition name="fade">
      <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
        <div class="modal max-w-lg">
          <div class="modal-header">
            <h3>新增收款单</h3>
            <button @click="showCreate = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="label" for="ar-rcpt-customer">客户</label>
                <select id="ar-rcpt-customer" v-model="form.customer_id" class="input text-sm" @change="form.receivable_bill_id = null">
                  <option value="">请选择</option>
                  <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
              <div>
                <label class="label" for="ar-rcpt-date">收款日期</label>
                <input id="ar-rcpt-date" v-model="form.receipt_date" type="date" class="input text-sm" />
              </div>
              <div>
                <label class="label" for="ar-rcpt-amount">金额</label>
                <input id="ar-rcpt-amount" v-model="form.amount" type="number" step="0.01" class="input text-sm" />
              </div>
              <div>
                <label class="label" for="ar-rcpt-payment-method">收款方式</label>
                <select id="ar-rcpt-payment-method" v-model="form.payment_method" class="input text-sm">
                  <option value="">请选择</option>
                  <option v-for="m in filteredPaymentMethods" :key="m.id" :value="m.name">{{ m.name }}</option>
                </select>
              </div>
              <div>
                <label class="label" for="ar-rcpt-receivable-bill-id">关联应收单</label>
                <select id="ar-rcpt-receivable-bill-id" v-model="form.receivable_bill_id" class="input text-sm">
                  <option :value="null">不关联</option>
                  <option v-for="rb in customerReceivables" :key="rb.id" :value="rb.id">
                    {{ rb.bill_no }} — ¥{{ rb.total_amount }}（未收 ¥{{ rb.unreceived_amount }}）
                  </option>
                </select>
              </div>
              <div class="flex items-end gap-2">
                <label class="flex items-center gap-1 text-[13px]" for="ar-rcpt-is-advance">
                  <input id="ar-rcpt-is-advance" type="checkbox" v-model="form.is_advance" aria-label="预收款" /> 预收款
                </label>
              </div>
              <div class="col-span-2">
                <label class="label" for="ar-rcpt-remark">备注</label>
                <input id="ar-rcpt-remark" v-model="form.remark" class="input text-sm" />
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showCreate = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handleCreate" :disabled="submitting" class="btn btn-primary btn-sm">{{ submitting ? '提交中...' : '确定' }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Search } from 'lucide-vue-next'

const emit = defineEmits(['data-changed'])
import ColumnMenu from '../common/ColumnMenu.vue'
import PageToolbar from '../common/PageToolbar.vue'
import { getReceiptBills, createReceiptBill, confirmReceiptBill, getReceivableBills } from '../../api/accounting'
import { getPaymentMethods } from '../../api/settings'
import { useAccountingStore } from '../../stores/accounting'
import { useSettingsStore } from '../../stores/settings'
import { useAppStore } from '../../stores/app'
import { usePermission } from '../../composables/usePermission'
import { useFormat } from '../../composables/useFormat'
import { useColumnConfig } from '../../composables/useColumnConfig'
import { useSearch } from '../../composables/useSearch'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const settingsStore = useSettingsStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()
const { fmtMoney } = useFormat()

// 按当前账套过滤的收款方式
const accountSetPaymentMethods = ref([])
async function loadAccountSetPaymentMethods() {
  if (!accountingStore.currentAccountSetId) {
    accountSetPaymentMethods.value = settingsStore.paymentMethods
    return
  }
  try {
    const { data } = await getPaymentMethods({ account_set_id: accountingStore.currentAccountSetId })
    accountSetPaymentMethods.value = data.items || data
  } catch {
    accountSetPaymentMethods.value = settingsStore.paymentMethods
  }
}
const filteredPaymentMethods = computed(() =>
  accountSetPaymentMethods.value.length ? accountSetPaymentMethods.value : settingsStore.paymentMethods
)

// 该客户的待收/部分收款应收单
const receivableBillsList = ref([])
const customerReceivables = computed(() => {
  if (!form.value.customer_id) return []
  return receivableBillsList.value.filter(rb => rb.customer_id === form.value.customer_id)
})

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = ref({ status: '' })
const showCreate = ref(false)
const submitting = ref(false)
const customers = ref([])
const form = ref({ customer_id: '', receipt_date: new Date().toISOString().slice(0, 10), amount: '', payment_method: '', receivable_bill_id: null, is_advance: false, remark: '' })
const receiptColumnDefs = {
  bill_no: { label: '单号', defaultVisible: true },
  receipt_date: { label: '日期', defaultVisible: true },
  customer: { label: '客户', defaultVisible: true },
  amount: { label: '金额', defaultVisible: true, align: 'right' },
  payment_method: { label: '收款方式', defaultVisible: true },
  is_advance: { label: '预收', defaultVisible: true },
  status: { label: '状态', defaultVisible: true },
  remark: { label: '备注', defaultVisible: true },
  voucher_no: { label: '凭证号', defaultVisible: true },
  actions: { label: '操作', defaultVisible: true },
}

const {
  columnLabels: rcColumnLabels, visibleColumns: rcVisibleColumns,
  showColumnMenu: rcShowColumnMenu, menuAttr: rcMenuAttr,
  toggleColumn: rcToggleColumn, isColumnVisible: rcIsColumnVisible,
  resetColumns: rcResetColumns,
} = useColumnConfig('receipt_bill_columns', receiptColumnDefs)

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = { account_set_id: accountingStore.currentAccountSetId, page: page.value, page_size: pageSize }
  if (filters.value.status) params.status = filters.value.status
  if (searchQuery.value) params.search = searchQuery.value
  const res = await getReceiptBills(params)
  items.value = res.data.items
  total.value = res.data.total
}

const { searchQuery, debouncedSearch } = useSearch(loadList, page)

async function loadCustomers() {
  const res = await api.get('/customers', { params: { limit: 1000 } })
  customers.value = res.data.items || res.data || []
}

async function loadReceivables() {
  if (!accountingStore.currentAccountSetId) return
  try {
    const res = await getReceivableBills({
      account_set_id: accountingStore.currentAccountSetId,
      page_size: 200,
    })
    // 只保留待收款和部分收款的
    receivableBillsList.value = (res.data.items || []).filter(rb => ['pending', 'partial'].includes(rb.status))
  } catch { receivableBillsList.value = [] }
}

function openCreate() {
  form.value = { customer_id: '', receipt_date: new Date().toISOString().slice(0, 10), amount: '', payment_method: '', receivable_bill_id: null, is_advance: false, remark: '' }
  loadReceivables()
  loadAccountSetPaymentMethods()
  showCreate.value = true
}

async function handleCreate() {
  if (submitting.value) return
  if (!form.value.customer_id || !form.value.amount || !form.value.payment_method) {
    appStore.showToast('请填写客户、金额和收款方式', 'error')
    return
  }
  submitting.value = true
  try {
    const data = {
      customer_id: Number(form.value.customer_id),
      receipt_date: form.value.receipt_date,
      amount: String(form.value.amount),
      payment_method: form.value.payment_method,
      is_advance: form.value.is_advance,
      remark: form.value.remark || '',
    }
    if (form.value.receivable_bill_id) data.receivable_bill_id = Number(form.value.receivable_bill_id)
    await createReceiptBill(accountingStore.currentAccountSetId, data)
    appStore.showToast('创建成功', 'success')
    showCreate.value = false
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    submitting.value = false
  }
}

async function confirmBill(b) {
  if (!await appStore.customConfirm('确认操作', `确认收款单 ${b.bill_no}？`)) return
  try {
    await confirmReceiptBill(b.id)
    appStore.showToast('确认成功', 'success')
    loadList()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => {
  page.value = 1
  loadList()
  loadAccountSetPaymentMethods()
})
onMounted(() => {
  loadList()
  loadCustomers()
  loadAccountSetPaymentMethods()
})
</script>
