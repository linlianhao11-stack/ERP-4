<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.status" class="toolbar-select" @change="loadList">
            <option value="">全部状态</option>
            <option value="pending">待付款</option>
            <option value="partial">部分付款</option>
            <option value="completed">已付清</option>
            <option value="cancelled">已取消</option>
          </select>
          <div class="toolbar-search-wrapper">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索单号/供应商...">
          </div>
        </template>
        <template #actions>
          <button v-if="selectedIds.length" @click="openPushInvoice" class="btn btn-primary btn-sm">
            推送发票 ({{ selectedIds.length }})
          </button>
          <button v-if="hasPermission('accounting_ap_edit')" @click="showCreate = true" class="btn btn-primary btn-sm">手动新增</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 w-8">
                <input type="checkbox" :checked="allChecked" :indeterminate="someChecked" @change="toggleAll" />
              </th>
              <th v-if="apIsColumnVisible('bill_no')" class="px-3 py-2">单号</th>
              <th v-if="apIsColumnVisible('bill_date')" class="px-3 py-2">日期</th>
              <th v-if="apIsColumnVisible('supplier')" class="px-3 py-2">供应商</th>
              <th v-if="apIsColumnVisible('total_amount')" class="px-3 py-2 text-right">应付金额</th>
              <th v-if="apIsColumnVisible('paid_amount')" class="px-3 py-2 text-right">已付金额</th>
              <th v-if="apIsColumnVisible('unpaid_amount')" class="px-3 py-2 text-right">未付金额</th>
              <th v-if="apIsColumnVisible('status')" class="px-3 py-2">状态</th>
              <th v-if="apIsColumnVisible('voucher_no')" class="px-3 py-2">凭证号</th>
              <th v-if="apIsColumnVisible('purchase_order_no')" class="px-3 py-2">来源采购单</th>
              <th v-if="apIsColumnVisible('actions')" class="px-3 py-2">操作</th>
              <th class="col-selector-th">
                <ColumnMenu :labels="apColumnLabels" :visible="apVisibleColumns" pinned="bill_no"
                  @toggle="apToggleColumn" @reset="apResetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="100">
                <div class="text-center py-12 text-muted">
                  <div class="text-3xl mb-3">📋</div>
                  <p class="text-sm font-medium mb-1">暂无应付单数据</p>
                  <p class="text-xs text-muted">点击"手动新增"按钮创建第一条记录</p>
                </div>
              </td>
            </tr>
            <tr v-for="b in items" :key="b.id" class="hover:bg-elevated">
              <td class="px-3 py-2 w-8">
                <input type="checkbox" :checked="selectedIds.includes(b.id)" @change="toggleRow(b.id)" />
              </td>
              <td v-if="apIsColumnVisible('bill_no')" class="px-3 py-2 font-mono text-[12px]">
                <span v-if="b.status === 'pending' || b.status === 'partial'" class="todo-dot mr-1"></span><span class="max-w-48 truncate inline-block align-bottom" :title="b.bill_no">{{ b.bill_no }}</span>
              </td>
              <td v-if="apIsColumnVisible('bill_date')" class="px-3 py-2">{{ b.bill_date }}</td>
              <td v-if="apIsColumnVisible('supplier')" class="px-3 py-2">{{ b.supplier_name }}</td>
              <td v-if="apIsColumnVisible('total_amount')" class="px-3 py-2 text-right">{{ fmtMoney(b.total_amount) }}</td>
              <td v-if="apIsColumnVisible('paid_amount')" class="px-3 py-2 text-right">{{ fmtMoney(b.paid_amount) }}</td>
              <td v-if="apIsColumnVisible('unpaid_amount')" class="px-3 py-2 text-right">{{ fmtMoney(b.unpaid_amount) }}</td>
              <td v-if="apIsColumnVisible('status')" class="px-3 py-2"><span :class="statusBadge(b.status)">{{ statusName(b.status) }}</span></td>
              <td v-if="apIsColumnVisible('voucher_no')" class="px-3 py-2 font-mono text-[12px]"><span class="max-w-48 truncate inline-block align-bottom" :title="b.voucher_no">{{ b.voucher_no || '-' }}</span></td>
              <td v-if="apIsColumnVisible('purchase_order_no')" class="px-3 py-2 font-mono text-[12px]"><span class="max-w-48 truncate inline-block align-bottom" :title="b.purchase_order_no">{{ b.purchase_order_no || '-' }}</span></td>
              <td v-if="apIsColumnVisible('actions')" class="px-3 py-2" @click.stop>
                <div class="flex gap-1">
                  <button @click="viewDetail(b)" class="text-xs px-2.5 py-1 rounded-md bg-info-subtle text-info-emphasis font-medium">查看</button>
                  <button v-if="b.status === 'pending' || b.status === 'partial'" @click="cancelBill(b)" class="text-xs px-2.5 py-1 rounded-md bg-error-subtle text-error-emphasis font-medium">取消</button>
                </div>
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

    <!-- 详情弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal max-w-lg">
          <div class="modal-header">
            <h3>应付单详情</h3>
            <button @click="showDetail = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div v-if="detailLoading" class="text-center py-8 text-muted">加载中...</div>
            <template v-else-if="detail">
              <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px]">
                <div><span class="text-muted">单号：</span><span class="font-mono">{{ detail.bill_no }}</span></div>
                <div><span class="text-muted">日期：</span>{{ detail.bill_date }}</div>
                <div><span class="text-muted">供应商：</span>{{ detail.supplier_name }}</div>
                <div><span class="text-muted">状态：</span><span :class="statusBadge(detail.status)">{{ statusName(detail.status) }}</span></div>
                <div><span class="text-muted">应付金额：</span><span class="font-medium">{{ fmtMoney(detail.total_amount) }}</span></div>
                <div><span class="text-muted">已付金额：</span>{{ fmtMoney(detail.paid_amount) }}</div>
                <div><span class="text-muted">未付金额：</span>{{ fmtMoney(detail.unpaid_amount) }}</div>
                <div><span class="text-muted">凭证号：</span>{{ detail.voucher_no || '-' }}</div>
                <div><span class="text-muted">来源采购单：</span>{{ detail.purchase_order_no || '-' }}</div>
                <div><span class="text-muted">创建时间：</span>{{ detail.created_at?.slice(0, 19).replace('T', ' ') }}</div>
                <div class="col-span-2"><span class="text-muted">备注：</span>{{ detail.remark || '-' }}</div>
              </div>
            </template>
          </div>
          <div class="modal-footer">
            <button @click="showDetail = false" class="btn btn-secondary btn-sm">关闭</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 新增弹窗 -->
    <Transition name="fade">
      <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
        <div class="modal max-w-lg">
          <div class="modal-header">
            <h3>手动新增应付单</h3>
            <button @click="showCreate = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="label" for="ap-pay-supplier">供应商</label>
                <select id="ap-pay-supplier" v-model="form.supplier_id" class="input text-sm">
                  <option value="">请选择</option>
                  <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </div>
              <div>
                <label class="label" for="ap-pay-date">日期</label>
                <input id="ap-pay-date" v-model="form.bill_date" type="date" class="input text-sm" />
              </div>
              <div>
                <label class="label" for="ap-pay-amount">金额</label>
                <input id="ap-pay-amount" v-model="form.total_amount" type="number" step="0.01" class="input text-sm" />
              </div>
              <div>
                <label class="label" for="ap-pay-remark">备注</label>
                <input id="ap-pay-remark" v-model="form.remark" class="input text-sm" />
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showCreate = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handleCreate" :disabled="submitting" class="btn btn-primary btn-sm">{{ submitting ? '保存中...' : '保存' }}</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 推送发票弹窗 -->
    <InvoicePushModal
      :visible="showPushModal"
      mode="purchase"
      :bills="selectedBills"
      :partnerName="pushPartnerName"
      :partnerInfo="pushPartnerInfo"
      :pushFn="doPushInvoice"
      @close="showPushModal = false"
      @success="onPushSuccess"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Search } from 'lucide-vue-next'

const props = defineProps({ refreshKey: { type: Number, default: 0 } })
import ColumnMenu from '../common/ColumnMenu.vue'
import PageToolbar from '../common/PageToolbar.vue'
import InvoicePushModal from './InvoicePushModal.vue'
import { getPayableBills, getPayableBill, createPayableBill, cancelPayableBill, pushInvoiceFromPayable } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { usePermission } from '../../composables/usePermission'
import { useFormat } from '../../composables/useFormat'
import { useColumnConfig } from '../../composables/useColumnConfig'
import { useSearch } from '../../composables/useSearch'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()
const { fmtMoney } = useFormat()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = ref({ status: '' })
const showCreate = ref(false)
const submitting = ref(false)
const suppliers = ref([])
const form = ref({ supplier_id: '', bill_date: new Date().toISOString().slice(0, 10), total_amount: '', remark: '' })
const showDetail = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

// 多选相关
const selectedIds = ref([])
const showPushModal = ref(false)
const pushPartnerName = ref('')
const pushPartnerInfo = ref({})

const selectedBills = computed(() => items.value.filter(b => selectedIds.value.includes(b.id)))
const allChecked = computed(() => items.value.length > 0 && items.value.every(b => selectedIds.value.includes(b.id)))
const someChecked = computed(() => !allChecked.value && items.value.some(b => selectedIds.value.includes(b.id)))

function toggleAll() {
  if (allChecked.value) {
    selectedIds.value = []
  } else {
    selectedIds.value = items.value.map(b => b.id)
  }
}

function toggleRow(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else {
    selectedIds.value.push(id)
  }
}

async function openPushInvoice() {
  const bills = selectedBills.value
  if (!bills.length) return

  // 过滤掉已取消的单据
  const validBills = bills.filter(b => b.status !== 'cancelled')
  if (validBills.length === 0) {
    appStore.showToast('所选单据均已取消，无法推送', 'error')
    return
  }
  if (validBills.length < bills.length) {
    appStore.showToast(`已自动排除 ${bills.length - validBills.length} 张已取消的单据`, 'warning')
  }

  // 校验同一供应商
  const supplierIds = [...new Set(validBills.map(b => b.supplier_id))]
  if (supplierIds.length > 1) {
    appStore.showToast('请选择同一供应商的应付单', 'error')
    return
  }

  // 获取供应商详情
  try {
    const res = await api.get(`/suppliers/${supplierIds[0]}`)
    const s = res.data
    pushPartnerName.value = s.name
    pushPartnerInfo.value = {
      tax_id: s.tax_id,
      address: s.address,
      phone: s.phone,
      bank_name: s.bank_name,
      bank_account: s.bank_account,
    }
  } catch {
    pushPartnerName.value = validBills[0].supplier_name
    pushPartnerInfo.value = {}
  }

  showPushModal.value = true
}

async function doPushInvoice(formData) {
  return pushInvoiceFromPayable({
    account_set_id: accountingStore.currentAccountSetId,
    payable_bill_ids: selectedIds.value,
    invoice_type: formData.invoice_type,
    invoice_date: formData.invoice_date,
    tax_rate: formData.tax_rate,
    remark: formData.remark,
  })
}

function onPushSuccess() {
  selectedIds.value = []
  loadList()
}

async function viewDetail(b) {
  showDetail.value = true
  detailLoading.value = true
  try {
    const res = await getPayableBill(b.id)
    detail.value = res.data
  } catch (e) {
    appStore.showToast('加载详情失败', 'error')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

const statusName = (s) => ({ pending: '待付款', partial: '部分付款', completed: '已付清', cancelled: '已取消' }[s] || s)
const statusBadge = (s) => ({ pending: 'badge badge-yellow', partial: 'badge badge-orange', completed: 'badge badge-green', cancelled: 'badge badge-gray' }[s] || 'badge')

const payableColumnDefs = {
  bill_no: { label: '单号', defaultVisible: true },
  bill_date: { label: '日期', defaultVisible: true },
  supplier: { label: '供应商', defaultVisible: true },
  total_amount: { label: '应付金额', defaultVisible: true, align: 'right' },
  paid_amount: { label: '已付金额', defaultVisible: true, align: 'right' },
  unpaid_amount: { label: '未付金额', defaultVisible: true, align: 'right' },
  status: { label: '状态', defaultVisible: true },
  voucher_no: { label: '凭证号', defaultVisible: true },
  purchase_order_no: { label: '来源采购单', defaultVisible: true },
  actions: { label: '操作', defaultVisible: true },
}

const {
  columnLabels: apColumnLabels, visibleColumns: apVisibleColumns,
  showColumnMenu: apShowColumnMenu, menuAttr: apMenuAttr,
  toggleColumn: apToggleColumn, isColumnVisible: apIsColumnVisible,
  resetColumns: apResetColumns,
} = useColumnConfig('payable_bill_columns', payableColumnDefs)

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = { account_set_id: accountingStore.currentAccountSetId, page: page.value, page_size: pageSize }
  if (filters.value.status) params.status = filters.value.status
  if (searchQuery.value) params.search = searchQuery.value
  const res = await getPayableBills(params)
  items.value = res.data.items
  total.value = res.data.total
  // 翻页后清除不在当前页的选中
  selectedIds.value = selectedIds.value.filter(id => items.value.some(b => b.id === id))
}

const { searchQuery, debouncedSearch } = useSearch(loadList, page)

async function loadSuppliers() {
  const res = await api.get('/suppliers', { params: { limit: 1000 } })
  suppliers.value = res.data.items || res.data || []
}

async function handleCreate() {
  if (!form.value.supplier_id || !form.value.total_amount) {
    appStore.showToast('请填写供应商和金额', 'error')
    return
  }
  submitting.value = true
  try {
    await createPayableBill(accountingStore.currentAccountSetId, form.value)
    appStore.showToast('创建成功', 'success')
    showCreate.value = false
    form.value = { supplier_id: '', bill_date: new Date().toISOString().slice(0, 10), total_amount: '', remark: '' }
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    submitting.value = false
  }
}

async function cancelBill(b) {
  if (!await appStore.customConfirm('作废确认', `确认取消应付单 ${b.bill_no}？`)) return
  try {
    await cancelPayableBill(b.id)
    appStore.showToast('已取消', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '取消失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
watch(() => props.refreshKey, () => { loadList() })
onMounted(() => { loadList(); loadSuppliers() })
</script>
