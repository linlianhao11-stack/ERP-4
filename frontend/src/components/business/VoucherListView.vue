<template>
  <div>
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
          <tr v-for="v in vouchers" :key="v.id" @click="emit('view-voucher', v.id)" class="cursor-pointer hover:bg-elevated">
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

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import { useFormat } from '../../composables/useFormat'
import ColumnMenu from '../common/ColumnMenu.vue'
import { useColumnConfig } from '../../composables/useColumnConfig'
import {
  getVouchers, submitVoucher, approveVoucher, rejectVoucher,
  postVoucher, unpostVoucher, deleteVoucher, getVoucherPdf, batchVoucherPdf
} from '../../api/accounting'

const props = defineProps({
  accountSetId: { type: Number, required: true },
  filters: { type: Object, required: true }, // { period_name, voucher_type, status }
})
const emit = defineEmits(['view-voucher'])

const appStore = useAppStore()
const { hasPermission } = usePermission()
const { fmtMoney } = useFormat()

const vouchers = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

const selectedIds = ref([])
const openMenuId = ref(null)
const menuPosition = ref({})
const menuTriggerRefs = ref([])

// 列配置
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
  toggleColumn: voucherToggleColumn, isColumnVisible: voucherIsColumnVisible,
  resetColumns: voucherResetColumns,
} = useColumnConfig('voucher_columns', voucherColumnDefs)

// 状态
const statusNames = { draft: '草稿', pending: '待审核', approved: '已审核', posted: '已过账' }
const statusBadgeMap = { draft: 'badge badge-gray', pending: 'badge badge-yellow', approved: 'badge badge-blue', posted: 'badge badge-green' }
const statusName = (s) => statusNames[s] || s
const statusBadge = (s) => statusBadgeMap[s] || 'badge'

const formatAmount = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : fmtMoney(n)
}

// 操作菜单
const toggleActionMenu = (id, event) => {
  if (openMenuId.value === id) {
    openMenuId.value = null
    return
  }
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

// 列表加载
const loadList = async () => {
  if (!props.accountSetId) return
  try {
    const { data } = await getVouchers({
      account_set_id: props.accountSetId,
      period_name: props.filters.period_name || undefined,
      voucher_type: props.filters.voucher_type || undefined,
      status: props.filters.status || undefined,
      page: page.value, page_size: pageSize,
    })
    vouchers.value = data.items
    total.value = data.total
  } catch (e) { /* ignore */ }
}

const toggleSelectAll = (e) => {
  selectedIds.value = e.target.checked ? vouchers.value.map(v => v.id) : []
}

// 工作流操作
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
  try { await unpostVoucher(v.id); appStore.showToast('反过账成功', 'success'); await loadList() }
  catch (e) { appStore.showToast(e.response?.data?.detail || '反过账失败', 'error') }
}
const handleDelete = async (v) => {
  if (!await appStore.customConfirm('删除确认', `确定删除凭证 ${v.voucher_no}？`)) return
  try { await deleteVoucher(v.id); appStore.showToast('删除成功', 'success'); await loadList() }
  catch (e) { appStore.showToast(e.response?.data?.detail || '删除失败', 'error') }
}

// PDF 操作
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

// 监听 filters 变化重新加载
watch(() => props.filters, () => { page.value = 1; loadList() }, { deep: true })
// 监听 accountSetId 变化重新加载
watch(() => props.accountSetId, () => { page.value = 1; selectedIds.value = []; loadList() })

onMounted(() => {
  loadList()
  document.addEventListener('click', closeMenuOnOutsideClick)
})
onUnmounted(() => {
  document.removeEventListener('click', closeMenuOnOutsideClick)
})

defineExpose({ selectedIds, loadList, handleBatchPdf })
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
