<!--
  借还记录列表
  工具栏（状态筛选 + 日期 + 搜索）+ 表格 + 操作按钮
-->
<template>
  <div>
    <!-- 工具栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="statusFilter" @change="resetPage(); loadLoans()" class="toolbar-select">
        <option value="">全部状态</option>
        <option value="pending_approval">待审批</option>
        <option value="approved">已批准</option>
        <option value="lent_out">借出中</option>
        <option value="overdue">超期</option>
        <option value="returned">已归还</option>
        <option value="rejected">已拒绝</option>
      </select>
      <DateRangePicker
        v-model:start="dateStart"
        v-model:end="dateEnd"
        @change="resetPage(); loadLoans()"
      />
      <div class="flex-1"></div>
      <input
        v-model="search"
        @input="debouncedLoad"
        class="toolbar-search"
        style="max-width:200px"
        placeholder="搜索单号/借用人..."
      >
    </div>

    <!-- 移动端卡片 -->
    <div class="md:hidden space-y-2">
      <div
        v-for="l in loans"
        :key="l.id"
        class="card p-3"
        :class="{ 'border-error': l.is_overdue }"
      >
        <div class="flex justify-between items-start mb-1.5">
          <div class="flex-1 min-w-0 mr-2">
            <div class="font-medium text-sm truncate">{{ l.unit_code }} &middot; {{ l.product_name }}</div>
            <div class="text-xs text-muted">{{ loanTypeLabel(l.loan_type) }} &middot; {{ l.borrower_name }}</div>
          </div>
          <span :class="loanStatusBadge(l.status)">{{ loanStatusLabel(l.status) }}</span>
        </div>
        <div class="flex justify-between items-center text-xs">
          <span class="text-muted">
            {{ l.lent_at?.slice(0, 10) || '-' }}
            <template v-if="l.expected_return_date"> &rarr; {{ l.expected_return_date }}</template>
          </span>
          <div class="flex items-center gap-2">
            <button v-if="l.status === 'pending_approval'" class="text-success" @click="handleApprove(l)">审批</button>
            <button v-if="l.status === 'pending_approval'" class="text-error" @click="handleReject(l)">拒绝</button>
            <button v-if="l.status === 'approved'" class="text-primary" @click="handleLend(l)">确认出库</button>
          </div>
        </div>
      </div>
      <div v-if="!loans.length && !loading" class="p-8 text-center text-muted text-sm">暂无借还记录</div>
    </div>

    <!-- 桌面表格 -->
    <AppTable
      :columns="columns"
      :empty="!loans.length && !loading"
    >
      <template #mobile>
        <span></span>
      </template>

      <tr
        v-for="l in loans"
        :key="l.id"
        class="hover:bg-elevated"
        :class="{ 'text-error': l.is_overdue }"
      >
        <td class="px-3 py-2 font-mono text-xs">{{ l.loan_no || '-' }}</td>
        <td class="px-3 py-2 font-mono text-xs">{{ l.unit_code }}</td>
        <td class="px-3 py-2">{{ l.product_name }}</td>
        <td class="px-3 py-2 text-xs">{{ loanTypeLabel(l.loan_type) }}</td>
        <td class="px-3 py-2 text-xs">{{ l.borrower_name }}</td>
        <td class="px-3 py-2 text-xs">{{ l.handler_name || '-' }}</td>
        <td class="px-3 py-2 text-xs">{{ l.lent_at?.slice(0, 10) || '-' }}</td>
        <td class="px-3 py-2 text-xs">{{ l.expected_return_date || '-' }}</td>
        <td class="px-3 py-2">
          <span :class="loanStatusBadge(l.status)">{{ loanStatusLabel(l.status) }}</span>
        </td>
        <td class="px-3 py-2">
          <div class="flex items-center gap-1.5 justify-end">
            <button v-if="l.status === 'pending_approval'" class="btn btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px;background:var(--success-subtle);color:var(--success-emphasis)" @click="handleApprove(l)">审批</button>
            <button v-if="l.status === 'pending_approval'" class="btn btn-danger btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="handleReject(l)">拒绝</button>
            <button v-if="l.status === 'approved'" class="btn btn-primary btn-sm" style="padding:4px 8px;min-height:28px;font-size:12px" @click="handleLend(l)">确认出库</button>
          </div>
        </td>
      </tr>
    </AppTable>

    <!-- 分页 -->
    <div v-if="hasPagination" class="flex items-center justify-between mt-3 text-sm">
      <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
      <div class="flex items-center gap-1">
        <button @click="prevPage(); loadLoans()" :disabled="page <= 1" class="btn btn-secondary btn-sm" style="padding:4px 10px;min-height:28px">&lsaquo;</button>
        <template v-for="(p, i) in visiblePages" :key="i">
          <span v-if="p === '...'" class="px-1 text-muted">...</span>
          <button v-else @click="goToPage(p); loadLoans()" :class="p === page ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'" style="padding:4px 10px;min-height:28px">{{ p }}</button>
        </template>
        <button @click="nextPage(); loadLoans()" :disabled="page >= totalPages" class="btn btn-secondary btn-sm" style="padding:4px 10px;min-height:28px">&rsaquo;</button>
      </div>
      <span class="text-xs text-muted w-16"></span>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import AppTable from '../../common/AppTable.vue'
import DateRangePicker from '../../common/DateRangePicker.vue'
import { useDemoLoan } from '../../../composables/useDemoUnit'
import { approveDemoLoan, rejectDemoLoan, lendDemoLoan } from '../../../api/demo'
import { useAppStore } from '../../../stores/app'

const emit = defineEmits(['refresh'])
const appStore = useAppStore()

const {
  loans, loading, statusFilter, search, dateStart, dateEnd,
  loadLoans, debouncedLoad,
  page, pageSize, total, totalPages, hasPagination,
  visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage,
} = useDemoLoan()

const columns = [
  { key: 'loan_no', label: '借出单号' },
  { key: 'unit_code', label: '样机编号' },
  { key: 'product_name', label: '产品' },
  { key: 'loan_type', label: '借用类型' },
  { key: 'borrower', label: '借用人' },
  { key: 'handler', label: '经办人' },
  { key: 'lent_at', label: '借出日期' },
  { key: 'expected_return_date', label: '预计归还' },
  { key: 'status', label: '状态' },
  { key: 'actions', label: '操作', align: 'right' },
]

// 借用类型标签
const LOAN_TYPE_MAP = { customer_trial: '客户试用', staff_carry: '业务员携带', exhibition: '展会' }
const loanTypeLabel = (t) => LOAN_TYPE_MAP[t] || t || '-'

// 借还状态标签
const LOAN_STATUS_MAP = {
  pending_approval: { label: '待审批', cls: 'badge badge-yellow' },
  approved: { label: '已批准', cls: 'badge badge-blue' },
  lent_out: { label: '借出中', cls: 'badge badge-blue' },
  overdue: { label: '超期', cls: 'badge badge-red' },
  returned: { label: '已归还', cls: 'badge badge-green' },
  rejected: { label: '已拒绝', cls: 'badge badge-gray' },
}
const loanStatusLabel = (s) => LOAN_STATUS_MAP[s]?.label || s
const loanStatusBadge = (s) => LOAN_STATUS_MAP[s]?.cls || 'badge badge-gray'

// 操作
const handleApprove = async (l) => {
  try {
    await approveDemoLoan(l.id)
    appStore.showToast('审批通过')
    loadLoans()
    emit('refresh')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '审批失败', 'error')
  }
}

const handleReject = async (l) => {
  try {
    await rejectDemoLoan(l.id)
    appStore.showToast('已拒绝')
    loadLoans()
    emit('refresh')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '拒绝失败', 'error')
  }
}

const handleLend = async (l) => {
  try {
    await lendDemoLoan(l.id)
    appStore.showToast('确认出库成功')
    loadLoans()
    emit('refresh')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '出库失败', 'error')
  }
}

onMounted(() => loadLoans())
</script>
