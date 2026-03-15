<template>
  <div>
    <!-- 凭证列表 -->
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.period_name" class="toolbar-select">
            <option value="">全部期间</option>
            <option v-for="p in periodOptions" :key="p" :value="p">{{ p }}</option>
          </select>
          <select v-model="filters.voucher_type" class="toolbar-select">
            <option value="">全部</option>
            <option value="记">记</option>
            <option value="收">收</option>
            <option value="付">付</option>
            <option value="转">转</option>
          </select>
          <select v-model="filters.status" class="toolbar-select">
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="pending">待审核</option>
            <option value="approved">已审核</option>
            <option value="posted">已过账</option>
          </select>
        </template>
        <template #actions>
          <button v-if="selectedCount > 0" @click="handleBatchSubmit" class="btn btn-primary btn-sm">批量提交({{ selectedCount }})</button>
          <button v-if="selectedCount > 0" @click="handleBatchApprove" class="btn btn-sm" style="background:var(--success-subtle);color:var(--success-emphasis);border:none">批量审核({{ selectedCount }})</button>
          <button v-if="selectedCount > 0" @click="handleBatchPost" class="btn btn-sm" style="background:var(--purple-subtle);color:var(--purple-emphasis);border:none">批量过账({{ selectedCount }})</button>
          <button v-if="selectedCount > 0" @click="handleBatchPdf" class="btn btn-secondary btn-sm">批量打印({{ selectedCount }})</button>
          <button v-if="hasPermission('accounting_edit')" @click="openCreate" class="btn btn-primary btn-sm">新增凭证</button>
        </template>
      </PageToolbar>

      <VoucherListView ref="listViewRef"
        :account-set-id="accountingStore.currentAccountSetId"
        :filters="currentFilters"
        @view-voucher="onViewVoucher" />
    </div>

    <VoucherDetailModal
      :visible="showModal"
      :voucher-id="modalVoucherId"
      :mode="modalMode"
      :account-set-id="accountingStore.currentAccountSetId"
      @update:visible="showModal = $event"
      @saved="onSaved" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { usePermission } from '../../composables/usePermission'
import { batchSubmitVouchers, batchApproveVouchers, batchPostVouchers } from '../../api/accounting'
import PageToolbar from '../common/PageToolbar.vue'
import VoucherListView from './VoucherListView.vue'
import VoucherDetailModal from './VoucherDetailModal.vue'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()

// 筛选条件
const filters = ref({ period_name: '', voucher_type: '', status: '' })

const periodOptions = computed(() => {
  const periods = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i)
    periods.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  return periods
})

// 构造给子组件的 filters（排除空字符串）
const currentFilters = computed(() => {
  const result = {}
  if (filters.value.period_name) result.period_name = filters.value.period_name
  if (filters.value.voucher_type) result.voucher_type = filters.value.voucher_type
  if (filters.value.status) result.status = filters.value.status
  return result
})

// 列表子组件引用
const listViewRef = ref(null)
const selectedCount = computed(() => listViewRef.value?.selectedIds?.length || 0)

// 弹窗状态
const showModal = ref(false)
const modalVoucherId = ref(null)
const modalMode = ref('view')

// 事件处理
const onViewVoucher = (id) => {
  modalVoucherId.value = id
  modalMode.value = 'view'
  showModal.value = true
}

const openCreate = () => {
  modalMode.value = 'create'
  modalVoucherId.value = null
  showModal.value = true
}

const onSaved = () => {
  listViewRef.value?.loadList()
}

const handleBatchPdf = () => {
  listViewRef.value?.handleBatchPdf()
}

const handleBatchSubmit = async () => {
  const ids = listViewRef.value?.selectedIds || []
  if (!ids.length) return
  if (!await appStore.customConfirm('批量提交', `确认提交 ${ids.length} 张凭证？`)) return
  try {
    const { data } = await batchSubmitVouchers(ids)
    const msg = `成功 ${data.success.length} 条` + (data.failed.length ? `，失败 ${data.failed.length} 条` : '')
    appStore.showToast(msg, data.failed.length ? 'warning' : 'success')
    if (listViewRef.value) listViewRef.value.selectedIds = []
    listViewRef.value?.loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

const handleBatchApprove = async () => {
  const ids = listViewRef.value?.selectedIds || []
  if (!ids.length) return
  if (!await appStore.customConfirm('批量审核', `确认审核 ${ids.length} 张凭证？`)) return
  try {
    const { data } = await batchApproveVouchers(ids)
    const msg = `成功 ${data.success.length} 条` + (data.failed.length ? `，失败 ${data.failed.length} 条` : '')
    appStore.showToast(msg, data.failed.length ? 'warning' : 'success')
    if (listViewRef.value) listViewRef.value.selectedIds = []
    listViewRef.value?.loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

const handleBatchPost = async () => {
  const ids = listViewRef.value?.selectedIds || []
  if (!ids.length) return
  if (!await appStore.customConfirm('批量过账', `确认过账 ${ids.length} 张凭证？过账后将影响账簿数据。`)) return
  try {
    const { data } = await batchPostVouchers(ids)
    const msg = `成功 ${data.success.length} 条` + (data.failed.length ? `，失败 ${data.failed.length} 条` : '')
    appStore.showToast(msg, data.failed.length ? 'warning' : 'success')
    if (listViewRef.value) listViewRef.value.selectedIds = []
    listViewRef.value?.loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}
</script>
