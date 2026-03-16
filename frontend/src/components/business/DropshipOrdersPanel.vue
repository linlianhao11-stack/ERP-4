<template>
  <div>
    <!-- 移动端卡片列表 -->
    <div class="md:hidden space-y-2">
      <!-- 移动端筛选 -->
      <div class="flex flex-wrap items-center gap-2 mb-2">
        <select v-model="statusFilter" @change="resetPage(); loadData()" class="toolbar-select flex-1">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="pending_payment">待付款</option>
          <option value="paid_pending_ship">已付待发</option>
          <option value="shipped">已发货</option>
          <option value="completed">已完成</option>
          <option value="cancelled">已取消</option>
        </select>
        <div class="toolbar-search-wrapper flex-1" style="max-width:none">
          <Search :size="14" class="toolbar-search-icon" />
          <input v-model="search" @input="debouncedLoad" class="toolbar-search" placeholder="搜索单号/供应商/客户...">
        </div>
      </div>
      <!-- 移动端卡片 -->
      <div v-for="o in sortedItems" :key="o.id" class="card p-3">
        <div class="flex justify-between items-start mb-1">
          <div class="font-medium text-sm font-mono">
            <span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1"></span>
            {{ o.ds_no }}
            <span v-if="o.urged_at" class="badge badge-orange text-[10px] ml-1">催</span>
          </div>
          <div class="text-lg font-bold text-primary">¥{{ fmt(o.sale_total) }}</div>
        </div>
        <div class="text-xs text-muted mb-1">
          {{ o.supplier_name }} → {{ o.customer_name }}
        </div>
        <div class="flex justify-between items-center text-xs">
          <div>
            <span class="text-muted">{{ o.product_name }} × {{ o.quantity }}</span>
          </div>
          <StatusBadge type="dropshipStatus" :status="o.status" />
        </div>
        <div class="flex justify-between items-center text-xs mt-1">
          <span class="text-muted">{{ fmtDate(o.created_at) }}</span>
          <span v-if="Number(o.gross_profit)" :class="Number(o.gross_profit) >= 0 ? 'text-success' : 'text-error'">
            毛利 ¥{{ fmt(o.gross_profit) }}
          </span>
        </div>
      </div>
      <div v-if="!items.length" class="p-8 text-center text-muted text-sm">暂无代采代发订单</div>
    </div>

    <!-- 桌面端表格 -->
    <div class="card hidden md:block" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="statusFilter" @change="resetPage(); loadData()" class="toolbar-select">
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="pending_payment">待付款</option>
            <option value="paid_pending_ship">已付待发</option>
            <option value="shipped">已发货</option>
            <option value="completed">已完成</option>
            <option value="cancelled">已取消</option>
          </select>
          <DateRangePicker v-model:start="dateStart" v-model:end="dateEnd" @change="resetPage(); loadData()" />
          <div class="toolbar-search-wrapper">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="search" @input="debouncedLoad" class="toolbar-search" placeholder="搜索单号/供应商/客户...">
          </div>
        </template>
        <template #actions>
          <button v-if="hasPermission('dropship')" @click="showCreateModal = true" class="btn btn-primary btn-sm">
            <Plus :size="14" /> 新建
          </button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th v-if="isColumnVisible('ds_no')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('ds_no')">
                单号 <span v-if="sortState.key === 'ds_no'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('status')" class="px-2 py-2 text-center cursor-pointer select-none hover:text-primary" @click="toggleSort('status')">
                状态 <span v-if="sortState.key === 'status'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('supplier_name')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('supplier_name')">
                供应商 <span v-if="sortState.key === 'supplier_name'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('product_name')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('product_name')">
                商品 <span v-if="sortState.key === 'product_name'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('quantity')" class="px-2 py-2 text-right">数量</th>
              <th v-if="isColumnVisible('customer_name')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('customer_name')">
                客户 <span v-if="sortState.key === 'customer_name'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('purchase_total')" class="px-2 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleSort('purchase_total')">
                采购额 <span v-if="sortState.key === 'purchase_total'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('sale_total')" class="px-2 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleSort('sale_total')">
                销售额 <span v-if="sortState.key === 'sale_total'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('gross_profit')" class="px-2 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleSort('gross_profit')">
                毛利 <span v-if="sortState.key === 'gross_profit'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('gross_margin')" class="px-2 py-2 text-right">毛利率</th>
              <th v-if="isColumnVisible('platform_order_no')" class="px-2 py-2 text-left">平台单号</th>
              <th v-if="isColumnVisible('tracking_no')" class="px-2 py-2 text-left">快递单号</th>
              <th v-if="isColumnVisible('settlement_type')" class="px-2 py-2 text-left">结算方式</th>
              <th v-if="isColumnVisible('creator_name')" class="px-2 py-2 text-left">创建人</th>
              <th v-if="isColumnVisible('created_at')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('created_at')">
                创建时间 <span v-if="sortState.key === 'created_at'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <!-- 列选择器 -->
              <th class="col-selector-th">
                <ColumnMenu :labels="columnLabels" :visible="visibleColumns" pinned="ds_no"
                  @toggle="toggleColumn" @reset="resetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="o in sortedItems" :key="o.id" class="hover:bg-elevated cursor-pointer">
              <td v-if="isColumnVisible('ds_no')" class="px-2 py-2 font-mono text-sm">
                <span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1.5"></span>
                {{ o.ds_no }}
                <span v-if="o.urged_at" class="badge badge-orange text-[10px] ml-1">催</span>
              </td>
              <td v-if="isColumnVisible('status')" class="px-2 py-2 text-center">
                <StatusBadge type="dropshipStatus" :status="o.status" />
              </td>
              <td v-if="isColumnVisible('supplier_name')" class="px-2 py-2">{{ o.supplier_name }}</td>
              <td v-if="isColumnVisible('product_name')" class="px-2 py-2">
                {{ o.product_name }}
              </td>
              <td v-if="isColumnVisible('quantity')" class="px-2 py-2 text-right">{{ o.quantity }}</td>
              <td v-if="isColumnVisible('customer_name')" class="px-2 py-2">{{ o.customer_name }}</td>
              <td v-if="isColumnVisible('purchase_total')" class="px-2 py-2 text-right">¥{{ fmt(o.purchase_total) }}</td>
              <td v-if="isColumnVisible('sale_total')" class="px-2 py-2 text-right font-semibold">¥{{ fmt(o.sale_total) }}</td>
              <td v-if="isColumnVisible('gross_profit')" class="px-2 py-2 text-right" :class="Number(o.gross_profit) >= 0 ? 'text-success' : 'text-error'">
                ¥{{ fmt(o.gross_profit) }}
              </td>
              <td v-if="isColumnVisible('gross_margin')" class="px-2 py-2 text-right text-muted">
                {{ o.gross_margin != null ? Number(o.gross_margin).toFixed(1) + '%' : '-' }}
              </td>
              <td v-if="isColumnVisible('platform_order_no')" class="px-2 py-2 font-mono text-xs text-muted">{{ o.platform_order_no || '-' }}</td>
              <td v-if="isColumnVisible('tracking_no')" class="px-2 py-2 font-mono text-xs text-muted">{{ o.tracking_no || '-' }}</td>
              <td v-if="isColumnVisible('settlement_type')" class="px-2 py-2">{{ o.settlement_type === 'prepay' ? '先款后货' : o.settlement_type === 'credit' ? '赊销' : o.settlement_type || '-' }}</td>
              <td v-if="isColumnVisible('creator_name')" class="px-2 py-2 text-secondary">{{ o.creator_name || '-' }}</td>
              <td v-if="isColumnVisible('created_at')" class="px-2 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
              <td></td>
            </tr>
          </tbody>
          <tfoot v-if="sortedItems.length > 0" class="bg-elevated font-semibold text-sm">
            <tr>
              <td v-if="isColumnVisible('ds_no')" class="px-2 py-2 text-left">本页合计</td>
              <td v-if="isColumnVisible('status')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('supplier_name')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('product_name')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('quantity')" class="px-2 py-2 text-right">{{ pageSummary.quantity }}</td>
              <td v-if="isColumnVisible('customer_name')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('purchase_total')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.purchase_total) }}</td>
              <td v-if="isColumnVisible('sale_total')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.sale_total) }}</td>
              <td v-if="isColumnVisible('gross_profit')" class="px-2 py-2 text-right" :class="pageSummary.gross_profit >= 0 ? 'text-success' : 'text-error'">
                ¥{{ fmt(pageSummary.gross_profit) }}
              </td>
              <td v-if="isColumnVisible('gross_margin')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('platform_order_no')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('tracking_no')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('settlement_type')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('creator_name')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('created_at')" class="px-2 py-2"></td>
              <td></td>
            </tr>
            <tr v-if="hasPagination" class="font-normal">
              <td :colspan="100" class="px-3.5 py-2.5">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
                  <div class="flex items-center gap-1">
                    <button @click="prevPage(); loadData()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">&#8249;</button>
                    <template v-for="(p, i) in visiblePages" :key="i">
                      <span v-if="p === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                      <button v-else @click="goToPage(p); loadData()" :class="p === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ p }}</button>
                    </template>
                    <button @click="nextPage(); loadData()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">&#8250;</button>
                  </div>
                  <span class="text-xs text-muted w-16"></span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div v-if="!items.length" class="p-8 text-center text-muted text-sm">暂无代采代发订单</div>
    </div>

    <!-- 新建/编辑代采代发订单弹窗 -->
    <DropshipOrderForm
      ref="formRef"
      :visible="showCreateModal"
      @update:visible="showCreateModal = $event"
      @saved="onFormSaved"
    />
  </div>
</template>

<script setup>
/**
 * 代采代发订单面板（瘦容器）
 * 负责筛选栏、列表展示，将表单逻辑委托给子组件
 */
import { ref, computed, onMounted } from 'vue'
import { Search, Plus } from 'lucide-vue-next'
import ColumnMenu from '../common/ColumnMenu.vue'
import StatusBadge from '../common/StatusBadge.vue'
import PageToolbar from '../common/PageToolbar.vue'
import DateRangePicker from '../common/DateRangePicker.vue'
import DropshipOrderForm from './dropship/DropshipOrderForm.vue'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { useDropshipOrder } from '../../composables/useDropshipOrder'

const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()

// 使用 composable 管理列表逻辑
const {
  items, statusFilter, search, dateStart, dateEnd,
  loadData, debouncedLoad,
  page, total, totalPages, hasPagination, visiblePages, pageItemCount,
  resetPage, prevPage, nextPage, goToPage,
  sortState, toggleSort, sortedItems,
  columnLabels, visibleColumns, toggleColumn, isColumnVisible, resetColumns,
} = useDropshipOrder()

/** 本页合计 */
const pageSummary = computed(() => {
  const rows = sortedItems.value
  const sum = { quantity: 0, purchase_total: 0, sale_total: 0, gross_profit: 0 }
  for (const o of rows) {
    sum.quantity += Number(o.quantity) || 0
    sum.purchase_total += Number(o.purchase_total) || 0
    sum.sale_total += Number(o.sale_total) || 0
    sum.gross_profit += Number(o.gross_profit) || 0
  }
  for (const k of ['purchase_total', 'sale_total', 'gross_profit']) {
    sum[k] = Math.round(sum[k] * 100) / 100
  }
  return sum
})

// 新建弹窗可见性
const showCreateModal = ref(false)
const formRef = ref(null)

/** 表单保存后刷新列表 */
const onFormSaved = () => {
  loadData()
}

// 暴露给父组件
defineExpose({
  refresh: loadData,
})

onMounted(() => {
  loadData()
})
</script>
