<template>
  <Transition name="fade">
    <div v-if="visible" class="modal-backdrop" @click.self="close">
      <div class="modal max-w-5xl">
        <div class="modal-header">
          <h3>{{ isEditing ? '编辑凭证' : (isCreating ? '新增凭证' : '凭证详情') }}</h3>
          <button @click="close" class="modal-close" aria-label="关闭">&times;</button>
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
          <div class="mb-4" v-if="isCreating && previewVoucherNo">
            <span class="text-xs text-muted">预计凭证号：</span>
            <span class="text-sm font-mono font-medium">{{ previewVoucherNo }}</span>
          </div>
          <div class="mb-4">
            <label for="vc-summary" class="label">摘要</label>
            <input id="vc-summary" v-model="editForm.summary" class="input text-sm" :disabled="!isEditing && !isCreating" :class="{ 'opacity-60 cursor-not-allowed bg-elevated': !isEditing && !isCreating }">
          </div>

          <div class="table-container">
            <table class="w-full text-sm">
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
                    <SearchableSelect v-if="isEditing || isCreating"
                      :options="accountOptions"
                      :model-value="entry.account_id"
                      @update:model-value="entry.account_id = $event"
                      placeholder="选择科目"
                      search-placeholder="搜索编码或名称..."
                    />
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
                      <select v-if="getAccountById(entry.account_id)?.aux_product" v-model="entry.aux_product_id" class="input text-xs" style="max-width:140px">
                        <option :value="null">商品…</option>
                        <option v-for="p in productList" :key="p.id" :value="p.id">{{ p.name }}</option>
                      </select>
                      <select v-if="getAccountById(entry.account_id)?.aux_bank" v-model="entry.aux_bank_account_id" class="input text-xs" style="max-width:140px">
                        <option :value="null">银行账户…</option>
                        <option v-for="b in bankAccountList" :key="b.id" :value="b.id">{{ b.short_name || b.bank_name }}</option>
                      </select>
                    </div>
                    <!-- 查看模式下显示辅助核算名称 -->
                    <div v-if="!(isEditing || isCreating)" class="flex flex-wrap gap-1 text-[11px] text-muted">
                      <span v-if="entry.aux_customer_name" class="badge badge-blue">{{ entry.aux_customer_name }}</span>
                      <span v-if="entry.aux_supplier_name" class="badge badge-orange">{{ entry.aux_supplier_name }}</span>
                      <span v-if="entry.aux_employee_name" class="badge badge-green">{{ entry.aux_employee_name }}</span>
                      <span v-if="entry.aux_department_name" class="badge badge-purple">{{ entry.aux_department_name }}</span>
                      <span v-if="entry.aux_product_name" class="badge badge-red">{{ entry.aux_product_name }}</span>
                      <span v-if="entry.aux_bank_account_name" class="badge" style="background: oklch(0.55 0.15 195 / 0.1); color: oklch(0.45 0.15 195)">{{ entry.aux_bank_account_name }}</span>
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
          <button @click="close" class="btn btn-sm btn-secondary">{{ (isEditing || isCreating) ? '取消' : '关闭' }}</button>
          <button v-if="isCreating" @click="handleCreate" class="btn btn-sm btn-primary" :disabled="submitting || totalDebit !== totalCredit">{{ submitting ? '保存中...' : '保存' }}</button>
          <button v-if="isEditing" @click="handleUpdate" class="btn btn-sm btn-primary" :disabled="submitting || totalDebit !== totalCredit">{{ submitting ? '保存中...' : '保存' }}</button>
          <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'posted' && hasPermission('accounting_post')" @click="handleUnpost(detailVoucher)" class="btn btn-sm btn-warning">反过账</button>
          <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'draft' && hasPermission('accounting_edit')" @click="startEdit" class="btn btn-sm btn-primary">编辑</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import { useFormat } from '../../composables/useFormat'
import { getVoucher, createVoucher, updateVoucher, unpostVoucher, getNextVoucherNumber } from '../../api/accounting'
import SearchableSelect from '../common/SearchableSelect.vue'
import { getCustomers } from '../../api/customers'
import { getSuppliers } from '../../api/purchase'
import { getEmployees, getDepartments } from '../../api/employees'
import { getProducts } from '../../api/products'
import { getBankAccounts } from '../../api/accounting'

const props = defineProps({
  visible: Boolean,
  voucherId: { type: Number, default: null },
  mode: { type: String, default: 'view' }, // view / create / edit
  accountSetId: { type: Number, required: true }
})
const emit = defineEmits(['update:visible', 'saved'])

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()
const { fmtMoney } = useFormat()

const submitting = ref(false)
const previewVoucherNo = ref('')
const isCreating = ref(false)
const isEditing = ref(false)
const detailVoucher = ref(null)
const leafAccounts = ref([])
const customerList = ref([])
const supplierList = ref([])
const employeeList = ref([])
const departmentList = ref([])
const productList = ref([])
const bankAccountList = ref([])

const editForm = ref({
  voucher_type: '记', voucher_date: '', summary: '',
  attachment_count: 0, entries: []
})

const accountOptions = computed(() =>
  leafAccounts.value.map(a => ({
    id: a.id,
    label: `${a.code} ${a.name}`,
    sublabel: a.category || ''
  }))
)

const fetchPreviewNo = async () => {
  if (!isCreating.value || !props.accountSetId) return
  try {
    const period = editForm.value.voucher_date ? editForm.value.voucher_date.slice(0, 7) : new Date().toISOString().slice(0, 7)
    const { data } = await getNextVoucherNumber({
      account_set_id: props.accountSetId,
      period: period,
      voucher_type: editForm.value.voucher_type || '记'
    })
    previewVoucherNo.value = data.voucher_no
  } catch (e) { previewVoucherNo.value = '' }
}

const totalDebit = computed(() =>
  editForm.value.entries.reduce((s, e) => s + (parseFloat(e.debit_amount) || 0), 0)
)
const totalCredit = computed(() =>
  editForm.value.entries.reduce((s, e) => s + (parseFloat(e.credit_amount) || 0), 0)
)

const formatAmount = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : fmtMoney(n)
}

const getAccountById = (id) => leafAccounts.value.find(a => a.id === id)

const addEntry = () => {
  editForm.value.entries.push({ account_id: null, summary: '', debit_amount: 0, credit_amount: 0, aux_customer_id: null, aux_supplier_id: null, aux_employee_id: null, aux_department_id: null, aux_product_id: null, aux_bank_account_id: null })
}

const close = () => {
  emit('update:visible', false)
}

const loadLeafAccounts = async () => {
  await accountingStore.loadChartOfAccounts()
  leafAccounts.value = accountingStore.chartOfAccounts.filter(a => a.is_leaf)
  // 加载辅助核算选项列表
  const needCustomer = leafAccounts.value.some(a => a.aux_customer)
  const needSupplier = leafAccounts.value.some(a => a.aux_supplier)
  const needEmployee = leafAccounts.value.some(a => a.aux_employee)
  const needDepartment = leafAccounts.value.some(a => a.aux_department)
  const needProduct = leafAccounts.value.some(a => a.aux_product)
  const needBank = leafAccounts.value.some(a => a.aux_bank)
  const tasks = []
  if (needCustomer && !customerList.value.length) tasks.push(getCustomers().then(r => { customerList.value = r.data.items || r.data }).catch(() => {}))
  if (needSupplier && !supplierList.value.length) tasks.push(getSuppliers().then(r => { supplierList.value = r.data.items || r.data }).catch(() => {}))
  if (needEmployee && !employeeList.value.length) tasks.push(getEmployees().then(r => { employeeList.value = r.data.items || r.data }).catch(() => {}))
  if (needDepartment && !departmentList.value.length) tasks.push(getDepartments().then(r => { departmentList.value = r.data.items || r.data }).catch(() => {}))
  if (needProduct && !productList.value.length) tasks.push(getProducts().then(r => { productList.value = r.data.items || r.data }).catch(() => {}))
  if (needBank && !bankAccountList.value.length) tasks.push(getBankAccounts({ account_set_id: props.accountSetId }).then(r => { bankAccountList.value = r.data.items || r.data }).catch(() => {}))
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
  fetchPreviewNo()
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
        aux_product_id: e.aux_product_id || null,
        aux_bank_account_id: e.aux_bank_account_id || null,
      }))
    }
    const { data } = await createVoucher(props.accountSetId, payload)
    appStore.showToast(`凭证 ${data.voucher_no} 创建成功`, 'success')
    close()
    emit('saved')
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
        aux_product_id: e.aux_product_id || null,
        aux_bank_account_id: e.aux_bank_account_id || null,
      }))
    }
    await updateVoucher(detailVoucher.value.id, payload)
    appStore.showToast('更新成功', 'success')
    close()
    emit('saved')
  } catch (e) { appStore.showToast(e.response?.data?.detail || '更新失败', 'error') }
  finally { submitting.value = false }
}

const handleUnpost = async (v) => {
  if (!await appStore.customConfirm('确认操作', `确定反过账凭证 ${v.voucher_no}？反过账后凭证将回到已审核状态。`)) return
  try {
    await unpostVoucher(v.id)
    appStore.showToast('反过账成功', 'success')
    close()
    emit('saved')
  } catch (e) { appStore.showToast(e.response?.data?.detail || '反过账失败', 'error') }
}

watch([() => editForm.value.voucher_type, () => editForm.value.voucher_date], () => {
  if (isCreating.value) fetchPreviewNo()
})

// 当 visible 变为 true 时根据 mode 决定行为
watch(() => props.visible, async (val) => {
  if (!val) return
  if (props.mode === 'view' && props.voucherId) {
    await viewVoucher(props.voucherId)
  } else if (props.mode === 'create') {
    await openCreateForm()
  }
})
</script>
