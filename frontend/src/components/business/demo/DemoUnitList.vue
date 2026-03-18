<!--
  样机台账列表
  工具栏 + 桌面表格 + 移动卡片 + 操作按钮 + 弹窗
-->
<template>
  <div>
    <!-- 工具栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <button class="btn btn-primary btn-sm" @click="showUnitForm = true">新增样机</button>
      <select v-model="statusFilter" @change="resetPage(); loadUnits()" class="toolbar-select">
        <option value="">全部状态</option>
        <option value="in_stock">在库</option>
        <option value="lent_out">借出中</option>
        <option value="repairing">维修中</option>
        <option value="sold">已售</option>
        <option value="scrapped">已报废</option>
        <option value="lost">已丢失</option>
        <option value="converted">已转良品</option>
      </select>
      <div class="flex-1"></div>
      <input
        v-model="search"
        @input="debouncedLoad"
        class="toolbar-search"
        style="max-width:200px"
        placeholder="搜索编号/产品/SN..."
      >
      <button class="btn btn-secondary btn-sm hidden md:inline-flex" @click="handleExport">导出</button>
    </div>

    <!-- 移动端卡片 -->
    <div class="md:hidden space-y-2">
      <div
        v-for="u in sortedUnits"
        :key="u.id"
        class="card p-3"
        :class="{ 'border-error': u.is_overdue }"
      >
        <div class="flex justify-between items-start mb-1.5">
          <div class="flex-1 min-w-0 mr-2">
            <div class="font-medium text-sm truncate">{{ u.product_name }}</div>
            <div class="text-xs text-muted font-mono">{{ u.code }}</div>
            <div v-if="u.sn_code" class="text-xs text-muted">SN: {{ u.sn_code }}</div>
          </div>
          <div class="text-right flex-shrink-0">
            <span :class="statusBadgeClass(u.status)">{{ statusLabel(u.status) }}</span>
          </div>
        </div>
        <div class="flex justify-between items-center text-xs">
          <span class="text-muted">
            {{ u.condition_label || conditionLabel(u.condition) }}
            <template v-if="u.current_holder_name"> &middot; {{ u.current_holder_name }}</template>
          </span>
          <div class="flex items-center gap-2">
            <template v-if="u.status === 'in_stock'">
              <button class="text-primary" @click="openLoan(u)">借出</button>
              <button class="text-success" @click="openDisposal(u, 'sale')">转销售</button>
            </template>
            <template v-else-if="u.status === 'lent_out'">
              <button class="text-primary" @click="openReturn(u)">归还</button>
            </template>
          </div>
        </div>
      </div>
      <div v-if="!sortedUnits.length && !loading" class="p-8 text-center text-muted text-sm">暂无样机数据</div>
    </div>

    <!-- 桌面表格 -->
    <AppTable
      :columns="columns"
      :sort-key="sortState.key"
      :sort-order="sortState.order"
      :empty="!sortedUnits.length && !loading"
      @sort="onSort"
    >
      <template #mobile>
        <!-- 移动端已在上方处理, 此处占位以触发 AppTable 的 mobile 插槽逻辑 -->
        <span></span>
      </template>

      <tr
        v-for="u in sortedUnits"
        :key="u.id"
        class="hover:bg-elevated"
        :class="{ 'text-error': u.is_overdue }"
      >
        <td class="px-3 py-2 font-mono text-xs">{{ u.code }}</td>
        <td class="px-3 py-2">
          <div class="font-medium">{{ u.product_name }}</div>
        </td>
        <td class="px-3 py-2 font-mono text-xs">{{ u.sn_code || '-' }}</td>
        <td class="px-3 py-2">
          <span :class="statusBadgeClass(u.status)">{{ statusLabel(u.status) }}</span>
        </td>
        <td class="px-3 py-2 text-xs">{{ conditionLabel(u.condition) }}</td>
        <td class="px-3 py-2 text-xs">{{ u.current_holder_name || '-' }}</td>
        <td class="px-3 py-2 text-right font-mono">{{ u.total_loan_count || 0 }}</td>
        <td class="px-3 py-2">
          <div class="flex items-center gap-1.5 justify-end">
            <template v-if="u.status === 'in_stock'">
              <button class="btn btn-primary btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="openLoan(u)">借出</button>
              <button class="btn btn-secondary btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="openDisposal(u, 'sale')">转销售</button>
              <button class="btn btn-secondary btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="openDisposal(u, 'conversion')">翻新</button>
              <button class="btn btn-danger btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="openDisposal(u, 'scrap')">报废</button>
            </template>
            <template v-else-if="u.status === 'lent_out'">
              <button class="btn btn-primary btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="openReturn(u)">归还</button>
              <button class="btn btn-secondary btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="openDisposal(u, 'sale')">转销售</button>
              <button class="btn btn-danger btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="openDisposal(u, 'loss')">登记丢失</button>
            </template>
            <template v-else-if="u.status === 'repairing'">
              <button class="btn btn-danger btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="openDisposal(u, 'scrap')">报废</button>
            </template>
          </div>
        </td>
      </tr>
    </AppTable>

    <!-- 分页 -->
    <div v-if="hasPagination" class="flex items-center justify-between mt-3 text-sm">
      <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
      <div class="flex items-center gap-1">
        <button @click="prevPage(); loadUnits()" :disabled="page <= 1" class="btn btn-secondary btn-sm" style="padding:4px 10px;min-height:28px">&lsaquo;</button>
        <template v-for="(p, i) in visiblePages" :key="i">
          <span v-if="p === '...'" class="px-1 text-muted">...</span>
          <button v-else @click="goToPage(p); loadUnits()" :class="p === page ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'" style="padding:4px 10px;min-height:28px">{{ p }}</button>
        </template>
        <button @click="nextPage(); loadUnits()" :disabled="page >= totalPages" class="btn btn-secondary btn-sm" style="padding:4px 10px;min-height:28px">&rsaquo;</button>
      </div>
      <span class="text-xs text-muted w-16"></span>
    </div>

    <!-- 弹窗 -->
    <DemoUnitForm
      :visible="showUnitForm"
      @close="showUnitForm = false"
      @saved="onUnitSaved"
    />

    <DemoLoanForm
      :visible="showLoanForm"
      :preselect-unit="loanUnit"
      @close="showLoanForm = false"
      @saved="onLoanSaved"
    />

    <DemoReturnModal
      :visible="showReturnModal"
      :unit="returnUnit"
      @close="showReturnModal = false"
      @saved="onReturnSaved"
    />

    <DemoDisposalModal
      :visible="showDisposalModal"
      :unit="disposalUnit"
      :type="disposalType"
      @close="showDisposalModal = false"
      @saved="onDisposalSaved"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import AppTable from '../../common/AppTable.vue'
import DemoUnitForm from './DemoUnitForm.vue'
import DemoLoanForm from './DemoLoanForm.vue'
import DemoReturnModal from './DemoReturnModal.vue'
import DemoDisposalModal from './DemoDisposalModal.vue'
import { useDemoUnit } from '../../../composables/useDemoUnit'
import { exportDemoUnits } from '../../../api/demo'
import { downloadBlob } from '../../../composables/useDownload'

const emit = defineEmits(['refresh'])

const {
  units, loading, statusFilter, search,
  loadUnits, debouncedLoad, sortedUnits,
  sortState, toggleSort,
  page, pageSize, total, totalPages, hasPagination,
  visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage,
} = useDemoUnit()

const columns = [
  { key: 'code', label: '编号', sortable: true },
  { key: 'product_name', label: '产品', sortable: true },
  { key: 'sn_code', label: 'SN码' },
  { key: 'status', label: '状态', sortable: true },
  { key: 'condition', label: '成色' },
  { key: 'holder', label: '当前持有人' },
  { key: 'total_loan_count', label: '累计借出', align: 'right', sortable: true },
  { key: 'actions', label: '操作', align: 'right' },
]

const onSort = ({ key, order }) => {
  toggleSort(key)
}

// 状态标签
const STATUS_MAP = {
  in_stock: { label: '在库', cls: 'badge badge-green' },
  lent_out: { label: '借出中', cls: 'badge badge-blue' },
  repairing: { label: '维修中', cls: 'badge badge-yellow' },
  sold: { label: '已售', cls: 'badge badge-gray' },
  scrapped: { label: '已报废', cls: 'badge badge-red' },
  lost: { label: '已丢失', cls: 'badge badge-red' },
  converted: { label: '已转良品', cls: 'badge badge-purple' },
}
const statusLabel = (s) => STATUS_MAP[s]?.label || s
const statusBadgeClass = (s) => STATUS_MAP[s]?.cls || 'badge badge-gray'

// 成色标签
const CONDITION_MAP = { new: '全新', good: '良好', fair: '一般', poor: '较差' }
const conditionLabel = (c) => CONDITION_MAP[c] || c || '-'

// 弹窗控制
const showUnitForm = ref(false)
const showLoanForm = ref(false)
const showReturnModal = ref(false)
const showDisposalModal = ref(false)

const loanUnit = ref(null)
const returnUnit = ref(null)
const disposalUnit = ref(null)
const disposalType = ref('sale')

const openLoan = (u) => {
  loanUnit.value = u
  showLoanForm.value = true
}
const openReturn = (u) => {
  returnUnit.value = u
  showReturnModal.value = true
}
const openDisposal = (u, type) => {
  disposalUnit.value = u
  disposalType.value = type
  showDisposalModal.value = true
}

const onUnitSaved = () => {
  showUnitForm.value = false
  loadUnits()
  emit('refresh')
}
const onLoanSaved = () => {
  showLoanForm.value = false
  loadUnits()
  emit('refresh')
}
const onReturnSaved = () => {
  showReturnModal.value = false
  loadUnits()
  emit('refresh')
}
const onDisposalSaved = () => {
  showDisposalModal.value = false
  loadUnits()
  emit('refresh')
}

// 导出
const handleExport = async () => {
  try {
    const params = {}
    if (statusFilter.value) params.status = statusFilter.value
    if (search.value) params.search = search.value
    const { data } = await exportDemoUnits(params)
    downloadBlob(data, `样机台账_${new Date().toISOString().slice(0, 10)}.xlsx`)
  } catch (e) {
    console.error('导出失败:', e)
  }
}

onMounted(() => loadUnits())
</script>
