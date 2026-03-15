<template>
  <div>
    <!-- 凭证列表 -->
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.period_name" class="toolbar-select" @change="loadList">
            <option value="">全部期间</option>
            <option v-for="p in periodOptions" :key="p" :value="p">{{ p }}</option>
          </select>
          <select v-model="filters.voucher_type" class="toolbar-select" @change="loadList">
            <option value="">全部</option>
            <option value="记">记</option>
            <option value="收">收</option>
            <option value="付">付</option>
            <option value="转">转</option>
          </select>
          <select v-model="filters.status" class="toolbar-select" @change="loadList">
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="pending">待审核</option>
            <option value="approved">已审核</option>
            <option value="posted">已过账</option>
          </select>
        </template>
        <template #actions>
          <button v-if="selectedIds.length > 0" @click="handleBatchPdf" class="btn btn-secondary btn-sm">批量打印({{ selectedIds.length }})</button>
          <button v-if="hasPermission('accounting_edit')" @click="openCreateForm" class="btn btn-primary btn-sm">新增凭证</button>
        </template>
      </PageToolbar>

      <div class="table-container">
        <table class="w-full">
          <thead class="bg-elevated">
            <tr>
              <th v-if="voucherIsColumnVisible('checkbox')" class="px-3 py-2 w-8"><input type="checkbox" @change="toggleSelectAll" :checked="selectedIds.length === vouchers.length && vouchers.length > 0" aria-label="全选"></th>
              <th v-if="voucherIsColumnVisible('voucher_type_col')" class="px-3 py-2">凭证字</th>
              <th v-if="voucherIsColumnVisible('voucher_no')" class="px-3 py-2">凭证号</th>
              <th v-if="voucherIsColumnVisible('voucher_date')" class="px-3 py-2">日期</th>
              <th v-if="voucherIsColumnVisible('summary')" class="px-3 py-2">摘要</th>
              <th v-if="voucherIsColumnVisible('total_debit')" class="px-3 py-2">借方合计</th>
              <th v-if="voucherIsColumnVisible('total_credit')" class="px-3 py-2">贷方合计</th>
              <th v-if="voucherIsColumnVisible('status')" class="px-3 py-2">状态</th>
              <th v-if="voucherIsColumnVisible('actions')" class="px-3 py-2">操作</th>
              <!-- 列选择器 -->
              <th class="col-selector-th">
                <ColumnMenu :labels="voucherColumnLabels" :visible="voucherVisibleColumns" pinned="voucher_no"
                  @toggle="voucherToggleColumn" @reset="voucherResetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="v in vouchers" :key="v.id" @click="viewVoucher(v.id)" class="cursor-pointer hover:bg-elevated">
              <td v-if="voucherIsColumnVisible('checkbox')" class="px-3 py-2" @click.stop><input type="checkbox" :value="v.id" v-model="selectedIds" aria-label="选择此行"></td>
              <td v-if="voucherIsColumnVisible('voucher_type_col')" class="px-3 py-2 font-medium">{{ v.voucher_type }}</td>
              <td v-if="voucherIsColumnVisible('voucher_no')" class="px-3 py-2 font-medium">{{ v.sequence_no }}</td>
              <td v-if="voucherIsColumnVisible('voucher_date')" class="px-3 py-2">{{ v.voucher_date }}</td>
              <td v-if="voucherIsColumnVisible('summary')" class="px-3 py-2">{{ v.summary || '-' }}</td>
              <td v-if="voucherIsColumnVisible('total_debit')" class="px-3 py-2 text-right">{{ formatAmount(v.total_debit) }}</td>
              <td v-if="voucherIsColumnVisible('total_credit')" class="px-3 py-2 text-right">{{ formatAmount(v.total_credit) }}</td>
              <td v-if="voucherIsColumnVisible('status')" class="px-3 py-2"><span :class="statusBadge(v.status)">{{ statusName(v.status) }}</span></td>
              <td v-if="voucherIsColumnVisible('actions')" class="px-3 py-2" @click.stop>
                <div class="flex items-center gap-1.5 justify-end">
                  <!-- 主操作按钮（外露） -->
                  <button v-if="v.status === 'draft' && hasPermission('accounting_edit')" @click="handleSubmit(v)" class="btn btn-primary btn-sm" style="padding:4px 12px;min-height:28px;font-size:12px">提交</button>
                  <button v-if="v.status === 'pending' && hasPermission('accounting_approve')" @click="handleApprove(v)" class="btn btn-sm" style="padding:4px 12px;min-height:28px;font-size:12px;background:var(--success-subtle);color:var(--success-emphasis);border:none">审核</button>
                  <button v-if="v.status === 'approved' && hasPermission('accounting_post')" @click="handlePost(v)" class="btn btn-sm" style="padding:4px 12px;min-height:28px;font-size:12px;background:var(--purple-subtle);color:var(--purple-emphasis);border:none">过账</button>
                  <!-- 更多操作下拉 -->
                  <div class="voucher-action-menu" v-if="getSecondaryActions(v).length > 0">
                    <button ref="menuTriggerRefs" :data-vid="v.id" @click.stop="toggleActionMenu(v.id, $event)" class="voucher-action-trigger">
                      ··· <span class="text-[10px]">▾</span>
                    </button>
                    <Teleport to="body">
                      <div v-if="openMenuId === v.id" class="voucher-action-dropdown" :style="menuPosition">
                        <button v-for="act in getSecondaryActions(v)" :key="act.label" @click="act.handler(v); openMenuId = null" :class="{ 'voucher-action-danger': act.danger }">
                          {{ act.label }}
                        </button>
                      </div>
                    </Teleport>
                  </div>
                </div>
              </td>
              <td class="px-3 py-2"></td>
            </tr>
            <tr v-if="vouchers.length === 0">
              <td colspan="100">
                <div class="text-center py-12 text-muted">
                  <div class="text-3xl mb-3">📋</div>
                  <p class="text-sm font-medium mb-1">暂无凭证</p>
                  <p class="text-xs text-muted">点击「新增凭证」按钮创建凭证</p>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>

    <!-- 凭证详情/编辑弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal max-w-3xl">
          <div class="modal-header">
            <h3>{{ isEditing ? '编辑凭证' : (isCreating ? '新增凭证' : '凭证详情') }}</h3>
            <button @click="showDetail = false" class="modal-close" aria-label="关闭">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-3 gap-3 mb-4">
              <div>
                <label for="vc-voucher-type" class="label">凭证字</label>
                <select id="vc-voucher-type" v-model="editForm.voucher_type" class="input text-sm" :disabled="!isCreating" :class="{ 'opacity-60 cursor-not-allowed bg-elevated': !isCreating }">
                  <option value="记">记</option>
                  <option value="收">收</option>
                  <option value="付">付</option>
                  <option value="转">转</option>
                </select>
              </div>
              <div>
                <label for="vc-voucher-date" class="label">凭证日期</label>
                <input id="vc-voucher-date" type="date" v-model="editForm.voucher_date" class="input text-sm" :disabled="!isEditing && !isCreating" :class="{ 'opacity-60 cursor-not-allowed bg-elevated': !isEditing && !isCreating }">
              </div>
              <div>
                <label for="vc-attachment-count" class="label">附件张数</label>
                <input id="vc-attachment-count" type="number" v-model.number="editForm.attachment_count" class="input text-sm" min="0" :disabled="!isEditing && !isCreating" :class="{ 'opacity-60 cursor-not-allowed bg-elevated': !isEditing && !isCreating }">
              </div>
            </div>
            <div class="mb-4">
              <label for="vc-summary" class="label">摘要</label>
              <input id="vc-summary" v-model="editForm.summary" class="input text-sm" :disabled="!isEditing && !isCreating" :class="{ 'opacity-60 cursor-not-allowed bg-elevated': !isEditing && !isCreating }">
            </div>

            <div class="table-container">
              <table class="w-full text-[13px]">
                <thead>
                  <tr>
                    <th class="w-8">#</th>
                    <th>摘要</th>
                    <th>科目编码</th>
                    <th>科目名称</th>
                    <th>核算维度</th>
                    <th class="w-32">借方金额</th>
                    <th class="w-32">贷方金额</th>
                    <th v-if="isEditing || isCreating" class="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(entry, idx) in editForm.entries" :key="idx">
                    <td>{{ idx + 1 }}</td>
                    <td>
                      <input v-if="isEditing || isCreating" v-model="entry.summary" class="input text-xs">
                      <span v-else>{{ entry.summary }}</span>
                    </td>
                    <td>
                      <select v-if="isEditing || isCreating" v-model="entry.account_id" class="input text-xs">
                        <option v-for="a in leafAccounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</option>
                      </select>
                      <span v-else>{{ entry.account_code }}</span>
                    </td>
                    <td>
                      <span v-if="isEditing || isCreating">{{ getAccountById(entry.account_id)?.name || '' }}</span>
                      <span v-else>{{ entry.account_name }}</span>
                    </td>
                    <td>
                      <!-- 编辑模式下的辅助核算选择器 -->
                      <div v-if="(isEditing || isCreating) && entry.account_id" class="flex flex-wrap gap-1">
                        <select v-if="getAccountById(entry.account_id)?.aux_customer" v-model="entry.aux_customer_id" class="input text-xs" style="max-width:140px">
                          <option :value="null">客户…</option>
                          <option v-for="c in customerList" :key="c.id" :value="c.id">{{ c.name }}</option>
                        </select>
                        <select v-if="getAccountById(entry.account_id)?.aux_supplier" v-model="entry.aux_supplier_id" class="input text-xs" style="max-width:140px">
                          <option :value="null">供应商…</option>
                          <option v-for="s in supplierList" :key="s.id" :value="s.id">{{ s.name }}</option>
                        </select>
                        <select v-if="getAccountById(entry.account_id)?.aux_employee" v-model="entry.aux_employee_id" class="input text-xs" style="max-width:140px">
                          <option :value="null">员工…</option>
                          <option v-for="emp in employeeList" :key="emp.id" :value="emp.id">{{ emp.name }}</option>
                        </select>
                        <select v-if="getAccountById(entry.account_id)?.aux_department" v-model="entry.aux_department_id" class="input text-xs" style="max-width:140px">
                          <option :value="null">部门…</option>
                          <option v-for="dep in departmentList" :key="dep.id" :value="dep.id">{{ dep.name }}</option>
                        </select>
                      </div>
                      <!-- 查看模式下显示辅助核算名称 -->
                      <div v-if="!(isEditing || isCreating)" class="flex flex-wrap gap-1 text-[11px] text-muted">
                        <span v-if="entry.aux_customer_name" class="badge badge-blue">{{ entry.aux_customer_name }}</span>
                        <span v-if="entry.aux_supplier_name" class="badge badge-orange">{{ entry.aux_supplier_name }}</span>
                        <span v-if="entry.aux_employee_name" class="badge badge-green">{{ entry.aux_employee_name }}</span>
                        <span v-if="entry.aux_department_name" class="badge badge-purple">{{ entry.aux_department_name }}</span>
                      </div>
                    </td>
                    <td>
                      <input v-if="isEditing || isCreating" type="number" v-model.number="entry.debit_amount" class="input text-right text-xs" min="0" step="0.01">
                      <span v-else class="text-right block">{{ formatAmount(entry.debit_amount) }}</span>
                    </td>
                    <td>
                      <input v-if="isEditing || isCreating" type="number" v-model.number="entry.credit_amount" class="input text-right text-xs" min="0" step="0.01">
                      <span v-else class="text-right block">{{ formatAmount(entry.credit_amount) }}</span>
                    </td>
                    <td v-if="isEditing || isCreating">
                      <button @click="editForm.entries.splice(idx, 1)" class="text-red-500 text-[12px]" v-if="editForm.entries.length > 2">&times;</button>
                    </td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr class="font-semibold">
                    <td colspan="5" class="text-right">合计</td>
                    <td class="text-right">{{ formatAmount(totalDebit) }}</td>
                    <td class="text-right">{{ formatAmount(totalCredit) }}</td>
                    <td v-if="isEditing || isCreating"></td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <div v-if="(isEditing || isCreating) && totalDebit !== totalCredit" class="mt-2 text-[13px] text-red-500">
              借贷不平衡！差额: {{ formatAmount(Math.abs(totalDebit - totalCredit)) }}
            </div>
            <button v-if="isEditing || isCreating" @click="addEntry" class="btn btn-secondary btn-sm mt-2">+ 添加分录</button>
          </div>
          <div class="modal-footer">
            <button @click="showDetail = false" class="btn btn-secondary">{{ (isEditing || isCreating) ? '取消' : '关闭' }}</button>
            <button v-if="isCreating" @click="handleCreate" class="btn btn-primary" :disabled="submitting || totalDebit !== totalCredit">{{ submitting ? '保存中...' : '保存' }}</button>
            <button v-if="isEditing" @click="handleUpdate" class="btn btn-primary" :disabled="submitting || totalDebit !== totalCredit">{{ submitting ? '保存中...' : '保存' }}</button>
            <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'posted' && hasPermission('accounting_post')" @click="handleUnpost(detailVoucher)" class="btn btn-warning">反过账</button>
            <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'draft' && hasPermission('accounting_edit')" @click="startEdit" class="btn btn-primary">编辑</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import { useFormat } from '../../composables/useFormat'
import ColumnMenu from '../common/ColumnMenu.vue'
import { useColumnConfig } from '../../composables/useColumnConfig'
import PageToolbar from '../common/PageToolbar.vue'
import {
  getVouchers, getVoucher, createVoucher, updateVoucher,
  deleteVoucher, submitVoucher, approveVoucher, rejectVoucher,
  postVoucher, unpostVoucher, getVoucherPdf, batchVoucherPdf
} from '../../api/accounting'
import { getCustomers } from '../../api/customers'
import { getSuppliers } from '../../api/purchase'
import { getEmployees, getDepartments } from '../../api/employees'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()
const { fmtMoney } = useFormat()

const vouchers = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const submitting = ref(false)
const showDetail = ref(false)
const isCreating = ref(false)
const isEditing = ref(false)
const detailVoucher = ref(null)
const leafAccounts = ref([])
const customerList = ref([])
const supplierList = ref([])
const employeeList = ref([])
const departmentList = ref([])

const selectedIds = ref([])
const openMenuId = ref(null)
const menuPosition = ref({})
const menuTriggerRefs = ref([])

const voucherColumnDefs = {
  checkbox: { label: '选择', defaultVisible: true },
  voucher_type_col: { label: '凭证字', defaultVisible: true },
  voucher_no: { label: '凭证号', defaultVisible: true },
  voucher_date: { label: '日期', defaultVisible: true },
  summary: { label: '摘要', defaultVisible: true },
  total_debit: { label: '借方合计', defaultVisible: true, align: 'right' },
  total_credit: { label: '贷方合计', defaultVisible: true, align: 'right' },
  status: { label: '状态', defaultVisible: true },
  actions: { label: '操作', defaultVisible: true },
}

const {
  columnLabels: voucherColumnLabels, visibleColumns: voucherVisibleColumns,
  showColumnMenu: voucherShowColumnMenu, menuAttr: voucherMenuAttr,
  toggleColumn: voucherToggleColumn, isColumnVisible: voucherIsColumnVisible,
  resetColumns: voucherResetColumns,
} = useColumnConfig('voucher_columns', voucherColumnDefs)

const toggleActionMenu = (id, event) => {
  if (openMenuId.value === id) {
    openMenuId.value = null
    return
  }
  // 计算触发按钮的位置，让下拉菜单用 fixed 定位
  const btn = event.currentTarget
  const rect = btn.getBoundingClientRect()
  menuPosition.value = {
    position: 'fixed',
    top: `${rect.bottom + 4}px`,
    right: `${window.innerWidth - rect.right}px`,
    zIndex: 9999,
  }
  openMenuId.value = id
}

const getSecondaryActions = (v) => {
  const actions = []
  if (v.status === 'pending' && hasPermission('accounting_approve')) {
    actions.push({ label: '驳回', handler: handleReject })
  }
  if (v.status === 'posted' && hasPermission('accounting_post')) {
    actions.push({ label: '反过账', handler: handleUnpost })
  }
  actions.push({ label: '打印', handler: handlePrintPdf })
  if (v.status === 'draft' && hasPermission('accounting_edit')) {
    actions.push({ label: '删除', handler: handleDelete, danger: true })
  }
  return actions
}

const filters = ref({ period_name: '', voucher_type: '', status: '' })

const editForm = ref({
  voucher_type: '记', voucher_date: '', summary: '',
  attachment_count: 0, entries: []
})

const periodOptions = computed(() => {
  const periods = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i)
    periods.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  return periods
})

const totalDebit = computed(() =>
  editForm.value.entries.reduce((s, e) => s + (parseFloat(e.debit_amount) || 0), 0)
)
const totalCredit = computed(() =>
  editForm.value.entries.reduce((s, e) => s + (parseFloat(e.credit_amount) || 0), 0)
)

const statusNames = { draft: '草稿', pending: '待审核', approved: '已审核', posted: '已过账' }
const statusBadgeMap = { draft: 'badge badge-gray', pending: 'badge badge-yellow', approved: 'badge badge-blue', posted: 'badge badge-green' }
const statusName = (s) => statusNames[s] || s
const statusBadge = (s) => statusBadgeMap[s] || 'badge'

const formatAmount = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : fmtMoney(n)
}

const getAccountById = (id) => leafAccounts.value.find(a => a.id === id)

const addEntry = () => {
  editForm.value.entries.push({ account_id: null, summary: '', debit_amount: 0, credit_amount: 0, aux_customer_id: null, aux_supplier_id: null, aux_employee_id: null, aux_department_id: null })
}

const loadList = async () => {
  if (!accountingStore.currentAccountSetId) return
  try {
    const { data } = await getVouchers({
      account_set_id: accountingStore.currentAccountSetId,
      period_name: filters.value.period_name || undefined,
      voucher_type: filters.value.voucher_type || undefined,
      status: filters.value.status || undefined,
      page: page.value, page_size: pageSize,
    })
    vouchers.value = data.items
    total.value = data.total
  } catch (e) { /* ignore */ }
}

const loadLeafAccounts = async () => {
  await accountingStore.loadChartOfAccounts()
  leafAccounts.value = accountingStore.chartOfAccounts.filter(a => a.is_leaf)
  // 加载辅助核算选项列表
  const needCustomer = leafAccounts.value.some(a => a.aux_customer)
  const needSupplier = leafAccounts.value.some(a => a.aux_supplier)
  const needEmployee = leafAccounts.value.some(a => a.aux_employee)
  const needDepartment = leafAccounts.value.some(a => a.aux_department)
  const tasks = []
  if (needCustomer && !customerList.value.length) tasks.push(getCustomers().then(r => { customerList.value = r.data }).catch(() => {}))
  if (needSupplier && !supplierList.value.length) tasks.push(getSuppliers().then(r => { supplierList.value = r.data }).catch(() => {}))
  if (needEmployee && !employeeList.value.length) tasks.push(getEmployees().then(r => { employeeList.value = r.data }).catch(() => {}))
  if (needDepartment && !departmentList.value.length) tasks.push(getDepartments().then(r => { departmentList.value = r.data }).catch(() => {}))
  if (tasks.length) await Promise.all(tasks)
}

const viewVoucher = async (id) => {
  try {
    const { data } = await getVoucher(id)
    detailVoucher.value = data
    editForm.value = {
      voucher_type: data.voucher_type, voucher_date: data.voucher_date,
      summary: data.summary, attachment_count: data.attachment_count,
      entries: data.entries.map(e => ({ ...e }))
    }
    isCreating.value = false
    isEditing.value = false
    showDetail.value = true
  } catch (e) { appStore.showToast('加载凭证失败', 'error') }
}

const openCreateForm = async () => {
  await loadLeafAccounts()
  const today = new Date().toISOString().slice(0, 10)
  editForm.value = {
    voucher_type: '记', voucher_date: today, summary: '', attachment_count: 0,
    entries: [
      { account_id: null, summary: '', debit_amount: 0, credit_amount: 0 },
      { account_id: null, summary: '', debit_amount: 0, credit_amount: 0 },
    ]
  }
  isCreating.value = true
  isEditing.value = false
  detailVoucher.value = null
  showDetail.value = true
}

const startEdit = async () => {
  await loadLeafAccounts()
  isEditing.value = true
}

const handleCreate = async () => {
  submitting.value = true
  try {
    const payload = {
      voucher_type: editForm.value.voucher_type,
      voucher_date: editForm.value.voucher_date,
      summary: editForm.value.summary,
      attachment_count: editForm.value.attachment_count,
      entries: editForm.value.entries.filter(e => e.account_id).map(e => ({
        account_id: e.account_id, summary: e.summary || '',
        debit_amount: String(e.debit_amount || 0),
        credit_amount: String(e.credit_amount || 0),
        aux_customer_id: e.aux_customer_id || null,
        aux_supplier_id: e.aux_supplier_id || null,
        aux_employee_id: e.aux_employee_id || null,
        aux_department_id: e.aux_department_id || null,
      }))
    }
    const { data } = await createVoucher(accountingStore.currentAccountSetId, payload)
    appStore.showToast(`凭证 ${data.voucher_no} 创建成功`, 'success')
    showDetail.value = false
    await loadList()
  } catch (e) { appStore.showToast(e.response?.data?.detail || '创建失败', 'error') }
  finally { submitting.value = false }
}

const handleUpdate = async () => {
  submitting.value = true
  try {
    const payload = {
      voucher_date: editForm.value.voucher_date,
      summary: editForm.value.summary,
      attachment_count: editForm.value.attachment_count,
      entries: editForm.value.entries.filter(e => e.account_id).map(e => ({
        account_id: e.account_id, summary: e.summary || '',
        debit_amount: String(e.debit_amount || 0),
        credit_amount: String(e.credit_amount || 0),
        aux_customer_id: e.aux_customer_id || null,
        aux_supplier_id: e.aux_supplier_id || null,
        aux_employee_id: e.aux_employee_id || null,
        aux_department_id: e.aux_department_id || null,
      }))
    }
    await updateVoucher(detailVoucher.value.id, payload)
    appStore.showToast('更新成功', 'success')
    showDetail.value = false
    await loadList()
  } catch (e) { appStore.showToast(e.response?.data?.detail || '更新失败', 'error') }
  finally { submitting.value = false }
}

const handleSubmit = async (v) => {
  try { await submitVoucher(v.id); appStore.showToast('已提交审核', 'success'); await loadList() }
  catch (e) { appStore.showToast(e.response?.data?.detail || '提交失败', 'error') }
}
const handleApprove = async (v) => {
  if (!await appStore.customConfirm('审核确认', `确定审核通过凭证 ${v.voucher_no}？`)) return
  try { await approveVoucher(v.id); appStore.showToast('审核通过', 'success'); await loadList() }
  catch (e) { appStore.showToast(e.response?.data?.detail || '审核失败', 'error') }
}
const handleReject = async (v) => {
  if (!await appStore.customConfirm('驳回确认', `确定驳回凭证 ${v.voucher_no}？驳回后凭证将回到草稿状态。`)) return
  try { await rejectVoucher(v.id); appStore.showToast('已驳回', 'success'); await loadList() }
  catch (e) { appStore.showToast(e.response?.data?.detail || '驳回失败', 'error') }
}
const handlePost = async (v) => {
  if (!await appStore.customConfirm('过账确认', `确定过账凭证 ${v.voucher_no}？过账后将影响账簿数据。`)) return
  try { await postVoucher(v.id); appStore.showToast('过账成功', 'success'); await loadList() }
  catch (e) { appStore.showToast(e.response?.data?.detail || '过账失败', 'error') }
}
const handleUnpost = async (v) => {
  if (!await appStore.customConfirm('确认操作', `确定反过账凭证 ${v.voucher_no}？反过账后凭证将回到已审核状态。`)) return
  try {
    await unpostVoucher(v.id)
    appStore.showToast('反过账成功', 'success')
    showDetail.value = false
    await loadList()
  } catch (e) { appStore.showToast(e.response?.data?.detail || '反过账失败', 'error') }
}
const handleDelete = async (v) => {
  if (!await appStore.customConfirm('删除确认', `确定删除凭证 ${v.voucher_no}？`)) return
  try { await deleteVoucher(v.id); appStore.showToast('删除成功', 'success'); await loadList() }
  catch (e) { appStore.showToast(e.response?.data?.detail || '删除失败', 'error') }
}

const toggleSelectAll = (e) => {
  selectedIds.value = e.target.checked ? vouchers.value.map(v => v.id) : []
}

const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const handlePrintPdf = async (v) => {
  try {
    const res = await getVoucherPdf(v.id)
    downloadBlob(new Blob([res.data], { type: 'application/pdf' }), `${v.voucher_no}.pdf`)
  } catch (e) { appStore.showToast('下载PDF失败', 'error') }
}

const handleBatchPdf = async () => {
  if (!selectedIds.value.length) return
  try {
    const res = await batchVoucherPdf(selectedIds.value)
    downloadBlob(new Blob([res.data], { type: 'application/pdf' }), 'vouchers_batch.pdf')
  } catch (e) { appStore.showToast('批量下载失败', 'error') }
}

// 点击外部关闭下拉菜单
const closeMenuOnOutsideClick = (e) => {
  if (openMenuId.value !== null && !e.target.closest('.voucher-action-menu')) {
    openMenuId.value = null
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; selectedIds.value = []; loadList() })
onMounted(() => {
  loadList()
  document.addEventListener('click', closeMenuOnOutsideClick)
})
onUnmounted(() => {
  document.removeEventListener('click', closeMenuOnOutsideClick)
})
</script>

<style scoped>
.voucher-action-menu {
  position: relative;
  display: inline-block;
}
.voucher-action-trigger {
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
  min-height: 28px;
}
.voucher-action-trigger:hover {
  border-color: var(--border-strong);
  background: var(--elevated);
}

</style>

<style>
/* Teleport 到 body 的下拉菜单，不能用 scoped */
.voucher-action-dropdown {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow-md);
  min-width: 120px;
  padding: 4px;
}
.voucher-action-dropdown button {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
  border-radius: 6px;
  font-family: inherit;
  text-align: left;
  transition: background 0.1s;
}
.voucher-action-dropdown button:hover {
  background: var(--elevated);
}
.voucher-action-danger {
  color: var(--error-emphasis) !important;
}
.voucher-action-danger:hover {
  background: var(--error-subtle) !important;
}
</style>
