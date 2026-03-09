<template>
  <div>
    <!-- 筛选栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="filters.period_name" class="input input-sm w-32" @change="loadList">
        <option value="">全部期间</option>
        <option v-for="p in periodOptions" :key="p" :value="p">{{ p }}</option>
      </select>
      <select v-model="filters.voucher_type" class="input input-sm w-24" @change="loadList">
        <option value="">全部</option>
        <option value="记">记</option>
        <option value="收">收</option>
        <option value="付">付</option>
        <option value="转">转</option>
      </select>
      <select v-model="filters.status" class="input input-sm w-28" @change="loadList">
        <option value="">全部状态</option>
        <option value="draft">草稿</option>
        <option value="pending">待审核</option>
        <option value="approved">已审核</option>
        <option value="posted">已过账</option>
      </select>
      <button v-if="selectedIds.length > 0" @click="handleBatchPdf" class="btn btn-secondary btn-sm ml-auto">批量打印({{ selectedIds.length }})</button>
      <button v-if="hasPermission('accounting_edit')" @click="openCreateForm" class="btn btn-primary btn-sm" :class="{ 'ml-auto': selectedIds.length === 0 }">新增凭证</button>
    </div>

    <!-- 凭证列表 -->
    <div class="table-container">
      <table class="w-full">
        <thead>
          <tr>
            <th class="w-8"><input type="checkbox" @change="toggleSelectAll" :checked="selectedIds.length === vouchers.length && vouchers.length > 0"></th>
            <th>凭证号</th>
            <th>日期</th>
            <th>摘要</th>
            <th>借方合计</th>
            <th>贷方合计</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in vouchers" :key="v.id" @click="viewVoucher(v.id)" class="cursor-pointer">
            <td @click.stop><input type="checkbox" :value="v.id" v-model="selectedIds"></td>
            <td class="font-medium">{{ v.voucher_no }}</td>
            <td>{{ v.voucher_date }}</td>
            <td>{{ v.summary || '-' }}</td>
            <td class="text-right">{{ formatAmount(v.total_debit) }}</td>
            <td class="text-right">{{ formatAmount(v.total_credit) }}</td>
            <td><span :class="statusBadge(v.status)">{{ statusName(v.status) }}</span></td>
            <td @click.stop>
              <div class="flex gap-1.5">
                <button v-if="v.status === 'draft' && hasPermission('accounting_edit')" @click="handleSubmit(v)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-[#e8f4fd] text-[#0062cc] hover:bg-[#d0e8fa] transition-colors">提交</button>
                <button v-if="v.status === 'pending' && hasPermission('accounting_approve')" @click="handleApprove(v)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-[#e8f8ee] text-[#248a3d] hover:bg-[#d0f0dc] transition-colors">审核</button>
                <button v-if="v.status === 'pending' && hasPermission('accounting_approve')" @click="handleReject(v)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-[#fff3e0] text-[#c93400] hover:bg-[#ffe6c7] transition-colors">驳回</button>
                <button v-if="v.status === 'approved' && hasPermission('accounting_post')" @click="handlePost(v)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-[#f3eef8] text-[#8944ab] hover:bg-[#e8ddf2] transition-colors">过账</button>
                <button v-if="v.status === 'posted' && hasPermission('accounting_post')" @click="handleUnpost(v)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-[#fff3e0] text-[#c93400] hover:bg-[#ffe6c7] transition-colors">反过账</button>
                <button v-if="v.status === 'draft' && hasPermission('accounting_edit')" @click="handleDelete(v)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-[#ffeaee] text-[#d70015] hover:bg-[#ffd5dc] transition-colors">删除</button>
                <button @click="handlePrintPdf(v)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-[#f0f0f0] text-[#333] hover:bg-[#e0e0e0] transition-colors">打印</button>
              </div>
            </td>
          </tr>
          <tr v-if="vouchers.length === 0">
            <td colspan="8" class="text-center text-[#86868b] py-8">暂无凭证</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-[#86868b] leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>

    <!-- 凭证详情/编辑弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal" style="max-width: 800px">
          <div class="modal-header">
            <h3>{{ isEditing ? '编辑凭证' : (isCreating ? '新增凭证' : '凭证详情') }}</h3>
            <button @click="showDetail = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-3 gap-3 mb-4">
              <div>
                <label class="label">凭证字</label>
                <select v-model="editForm.voucher_type" class="input text-sm" :disabled="!isCreating">
                  <option value="记">记</option>
                  <option value="收">收</option>
                  <option value="付">付</option>
                  <option value="转">转</option>
                </select>
              </div>
              <div>
                <label class="label">凭证日期</label>
                <input type="date" v-model="editForm.voucher_date" class="input text-sm" :disabled="!isEditing && !isCreating">
              </div>
              <div>
                <label class="label">附件张数</label>
                <input type="number" v-model.number="editForm.attachment_count" class="input text-sm" min="0" :disabled="!isEditing && !isCreating">
              </div>
            </div>
            <div class="mb-4">
              <label class="label">摘要</label>
              <input v-model="editForm.summary" class="input text-sm" :disabled="!isEditing && !isCreating">
            </div>

            <div class="table-container">
              <table class="w-full text-[13px]">
                <thead>
                  <tr>
                    <th class="w-8">#</th>
                    <th>科目</th>
                    <th>摘要</th>
                    <th class="w-32">借方金额</th>
                    <th class="w-32">贷方金额</th>
                    <th v-if="isEditing || isCreating" class="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(entry, idx) in editForm.entries" :key="idx">
                    <td>{{ idx + 1 }}</td>
                    <td>
                      <select v-if="isEditing || isCreating" v-model="entry.account_id" class="input text-xs">
                        <option v-for="a in leafAccounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</option>
                      </select>
                      <span v-else>{{ entry.account_code }} {{ entry.account_name }}</span>
                    </td>
                    <td>
                      <input v-if="isEditing || isCreating" v-model="entry.summary" class="input text-xs">
                      <span v-else>{{ entry.summary }}</span>
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
                    <td colspan="3" class="text-right">合计</td>
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
            <button v-if="isCreating" @click="handleCreate" class="btn btn-primary" :disabled="submitting || totalDebit !== totalCredit">保存</button>
            <button v-if="isEditing" @click="handleUpdate" class="btn btn-primary" :disabled="submitting || totalDebit !== totalCredit">保存</button>
            <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'posted' && hasPermission('accounting_post')" @click="handleUnpost(detailVoucher)" class="btn btn-warning">反过账</button>
            <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'draft' && hasPermission('accounting_edit')" @click="startEdit" class="btn btn-primary">编辑</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import {
  getVouchers, getVoucher, createVoucher, updateVoucher,
  deleteVoucher, submitVoucher, approveVoucher, rejectVoucher,
  postVoucher, unpostVoucher, getVoucherPdf, batchVoucherPdf
} from '../../api/accounting'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()

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

const selectedIds = ref([])

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
  return isNaN(n) || n === 0 ? '' : n.toFixed(2)
}

const addEntry = () => {
  editForm.value.entries.push({ account_id: null, summary: '', debit_amount: 0, credit_amount: 0, aux_customer_id: null, aux_supplier_id: null })
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

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; selectedIds.value = []; loadList() })
onMounted(loadList)
</script>
