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
          <button type="button" class="font-medium text-sm font-mono text-primary hover:underline" @click="openDetail(o)">
            <span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1"></span>
            {{ o.ds_no }}
            <span v-if="o.urged_at" class="badge badge-orange text-[10px] ml-1">催</span>
          </button>
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
        <!-- 移动端操作按钮 -->
        <div v-if="getActions(o).length" class="flex items-center gap-2 mt-2 pt-2 border-t">
          <button v-for="act in getActions(o)" :key="act.key" type="button"
            :class="act.class" class="text-xs px-2 py-1 rounded-md"
            @click="handleAction(act.key, o)">
            {{ act.label }}
          </button>
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
          <button v-if="hasPermission('dropship')" @click="showImportModal = true" class="btn btn-secondary btn-sm">
            <Upload :size="14" /> 导入供应商
          </button>
          <button v-if="hasPermission('dropship')" @click="editingOrder = null; showCreateModal = true" class="btn btn-primary btn-sm">
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
              <th v-if="isColumnVisible('tracking_status')" class="px-2 py-2 text-center">物流状态</th>
              <th v-if="isColumnVisible('settlement_type')" class="px-2 py-2 text-left">结算方式</th>
              <th v-if="isColumnVisible('creator_name')" class="px-2 py-2 text-left">创建人</th>
              <th v-if="isColumnVisible('created_at')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('created_at')">
                创建时间 <span v-if="sortState.key === 'created_at'" class="text-primary">{{ sortState.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-2 py-2 text-center">操作</th>
              <!-- 列选择器 -->
              <th class="col-selector-th">
                <ColumnMenu :labels="columnLabels" :visible="visibleColumns" pinned="ds_no"
                  @toggle="toggleColumn" @reset="resetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="o in sortedItems" :key="o.id" class="hover:bg-elevated">
              <td v-if="isColumnVisible('ds_no')" class="px-2 py-2 font-mono text-sm">
                <span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1.5"></span>
                <button type="button" class="text-primary hover:underline cursor-pointer" @click="openDetail(o)">
                  {{ o.ds_no }}
                </button>
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
              <td v-if="isColumnVisible('tracking_status')" class="px-2 py-2 text-center">
                <span v-if="o.tracking_status" class="text-xs px-1.5 py-0.5 rounded-md"
                  :class="{
                    'bg-success/10 text-success': o.tracking_status === '已签收',
                    'bg-primary/10 text-primary': o.tracking_status === '运输中' || o.tracking_status === '待查询',
                    'bg-warning/10 text-warning': o.tracking_status === '待揽收',
                    'bg-elevated text-secondary': !['已签收','运输中','待查询','待揽收'].includes(o.tracking_status),
                  }">
                  {{ o.tracking_status }}
                </span>
                <span v-else class="text-muted">-</span>
              </td>
              <td v-if="isColumnVisible('settlement_type')" class="px-2 py-2">{{ o.settlement_type === 'prepaid' ? '先款后货' : o.settlement_type === 'credit' ? '赊销' : o.settlement_type || '-' }}</td>
              <td v-if="isColumnVisible('creator_name')" class="px-2 py-2 text-secondary">{{ o.creator_name || '-' }}</td>
              <td v-if="isColumnVisible('created_at')" class="px-2 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
              <!-- 操作列 -->
              <td class="px-2 py-2 text-center whitespace-nowrap">
                <div class="flex items-center justify-center gap-1">
                  <button v-for="act in getActions(o)" :key="act.key" type="button"
                    :class="act.class" class="text-xs px-2 py-1 rounded-md"
                    @click="handleAction(act.key, o)">
                    {{ act.label }}
                  </button>
                </div>
              </td>
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
              <td v-if="isColumnVisible('tracking_status')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('settlement_type')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('creator_name')" class="px-2 py-2"></td>
              <td v-if="isColumnVisible('created_at')" class="px-2 py-2"></td>
              <td class="px-2 py-2"></td>
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
      :editData="editingOrder"
      @update:visible="val => { showCreateModal = val; if (!val) editingOrder = null }"
      @saved="onFormSaved"
    />

    <!-- 订单详情弹窗 -->
    <DropshipOrderDetail
      :visible="showDetailModal"
      :orderId="detailOrderId"
      @update:visible="showDetailModal = $event"
      @status-changed="loadData"
    />

    <!-- 发货弹窗 -->
    <DropshipShipModal
      :visible="showShipModal"
      :order="shipOrder"
      @update:visible="showShipModal = $event"
      @shipped="loadData"
    />

    <!-- 取消弹窗 -->
    <DropshipCancelModal
      :visible="showCancelModal"
      :order="cancelOrder"
      @update:visible="showCancelModal = $event"
      @cancelled="loadData"
    />

    <!-- 供应商导入弹窗 -->
    <div v-if="showImportModal" class="modal-overlay" @click.self="showImportModal = false">
      <div class="modal-content" style="max-width:520px">
        <div class="modal-header">
          <h3 class="modal-title">导入供应商</h3>
          <button @click="showImportModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="space-y-4">
            <!-- 下载模板 -->
            <div class="flex items-center justify-between bg-elevated rounded-lg p-3">
              <span class="text-sm">下载导入模板</span>
              <button type="button" @click="handleDownloadTemplate" class="btn btn-sm btn-secondary">
                <Download :size="14" /> 下载模板
              </button>
            </div>
            <!-- 上传区 -->
            <div
              class="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-primary transition-colors"
              :class="isDragging ? 'border-primary bg-primary/5' : 'border-border-strong'"
              @dragover.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
              @drop.prevent="handleFileDrop"
              @click="triggerFileInput"
            >
              <Upload :size="24" class="mx-auto mb-2 text-muted" />
              <div class="text-sm text-muted">拖拽 .xlsx 文件到此处，或点击选择文件</div>
              <div v-if="importFile" class="text-sm text-primary mt-2 font-medium">{{ importFile.name }}</div>
              <input ref="fileInput" type="file" accept=".xlsx,.xls" class="hidden" @change="handleFileSelect">
            </div>
            <!-- 上传按钮 -->
            <button type="button" @click="handleImport" class="btn btn-primary btn-sm w-full"
              :disabled="!importFile || appStore.submitting">
              {{ appStore.submitting ? '导入中...' : '开始导入' }}
            </button>
            <!-- 导入结果 -->
            <div v-if="importResult" class="bg-elevated rounded-lg p-3 text-sm space-y-1">
              <div v-if="importResult.success" class="text-success">成功导入 {{ importResult.success }} 条</div>
              <div v-if="importResult.skipped" class="text-warning">跳过 {{ importResult.skipped }} 条</div>
              <div v-if="importResult.errors?.length" class="text-error">
                <div>失败 {{ importResult.errors.length }} 条：</div>
                <ul class="list-disc pl-4 mt-1 text-xs">
                  <li v-for="(err, i) in importResult.errors.slice(0, 10)" :key="i">{{ err }}</li>
                  <li v-if="importResult.errors.length > 10">...等 {{ importResult.errors.length - 10 }} 条</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 代采代发订单面板
 * 负责筛选栏、列表展示、操作按钮（发货/取消/催付款/提交/编辑/完成）
 * 包含发货弹窗、取消弹窗、供应商导入弹窗
 */
import { ref, computed, onMounted } from 'vue'
import { Search, Plus, Upload, Download } from 'lucide-vue-next'
import ColumnMenu from '../common/ColumnMenu.vue'
import StatusBadge from '../common/StatusBadge.vue'
import PageToolbar from '../common/PageToolbar.vue'
import DateRangePicker from '../common/DateRangePicker.vue'
import DropshipOrderForm from './dropship/DropshipOrderForm.vue'
import DropshipOrderDetail from './dropship/DropshipOrderDetail.vue'
import DropshipShipModal from './dropship/DropshipShipModal.vue'
import DropshipCancelModal from './dropship/DropshipCancelModal.vue'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { useDropshipOrder } from '../../composables/useDropshipOrder'
import { useAppStore } from '../../stores/app'
import {
  submitDropshipOrder, urgeDropshipOrder, completeDropshipOrder,
  importSuppliers, downloadSupplierTemplate
} from '../../api/dropship'

const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()
const appStore = useAppStore()

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

// 新建/编辑弹窗
const showCreateModal = ref(false)
const editingOrder = ref(null)
const formRef = ref(null)

/** 表单保存后刷新列表 */
const onFormSaved = () => {
  loadData()
}

// ---- 操作按钮逻辑 ----

/** 根据订单状态返回可用操作列表 */
const getActions = (order) => {
  const actions = []
  switch (order.status) {
    case 'draft':
      actions.push({ key: 'edit', label: '编辑', class: 'bg-elevated text-text hover:bg-surface-hover' })
      actions.push({ key: 'submit', label: '提交', class: 'bg-primary/10 text-primary hover:bg-primary/20' })
      actions.push({ key: 'cancel', label: '取消', class: 'bg-error/10 text-error hover:bg-error/20' })
      break
    case 'pending_payment':
      actions.push({ key: 'urge', label: '催付款', class: 'bg-warning/10 text-warning hover:bg-warning/20' })
      actions.push({ key: 'cancel', label: '取消', class: 'bg-error/10 text-error hover:bg-error/20' })
      break
    case 'paid_pending_ship':
      actions.push({ key: 'ship', label: '发货', class: 'bg-primary/10 text-primary hover:bg-primary/20' })
      actions.push({ key: 'cancel', label: '取消', class: 'bg-error/10 text-error hover:bg-error/20' })
      break
    case 'shipped':
      actions.push({ key: 'complete', label: '完成', class: 'bg-success/10 text-success hover:bg-success/20' })
      break
  }
  return actions
}

/** 处理操作按钮点击 */
const handleAction = (key, order) => {
  switch (key) {
    case 'edit':
      editingOrder.value = order
      showCreateModal.value = true
      break
    case 'submit':
      handleSubmit(order)
      break
    case 'urge':
      handleUrge(order)
      break
    case 'ship':
      openShipModal(order)
      break
    case 'complete':
      handleComplete(order)
      break
    case 'cancel':
      openCancelModal(order)
      break
  }
}

/** 提交草稿 */
const handleSubmit = async (order) => {
  const ok = await appStore.customConfirm('确认提交该订单？', `单号: ${order.ds_no}`)
  if (!ok) return
  try {
    await submitDropshipOrder(order.id)
    appStore.showToast('订单已提交')
    loadData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '提交失败', 'error')
  }
}

/** 催付款 */
const handleUrge = async (order) => {
  try {
    await urgeDropshipOrder(order.id)
    appStore.showToast('已标记催付款')
    loadData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

/** 手动完成 */
const handleComplete = async (order) => {
  const ok = await appStore.customConfirm('确认手动完成该订单？', `单号: ${order.ds_no}`)
  if (!ok) return
  try {
    await completeDropshipOrder(order.id)
    appStore.showToast('订单已完成')
    loadData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

// ---- 发货弹窗 ----
const showShipModal = ref(false)
const shipOrder = ref(null)
const openShipModal = (order) => {
  shipOrder.value = order
  showShipModal.value = true
}

// ---- 取消弹窗 ----
const showCancelModal = ref(false)
const cancelOrder = ref(null)
const openCancelModal = (order) => {
  cancelOrder.value = order
  showCancelModal.value = true
}

// ---- 详情弹窗 ----
const showDetailModal = ref(false)
const detailOrderId = ref(null)
const openDetail = (order) => {
  detailOrderId.value = order.id
  showDetailModal.value = true
}

// ---- 供应商导入弹窗 ----
const showImportModal = ref(false)
const importFile = ref(null)
const importResult = ref(null)
const isDragging = ref(false)
const fileInput = ref(null)

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (e) => {
  const file = e.target.files[0]
  if (file) {
    importFile.value = file
    importResult.value = null
  }
}

const handleFileDrop = (e) => {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
    importFile.value = file
    importResult.value = null
  } else {
    appStore.showToast('请上传 .xlsx 格式文件', 'error')
  }
}

const handleDownloadTemplate = async () => {
  try {
    const { data } = await downloadSupplierTemplate()
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = '供应商导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('下载模板失败', 'error')
  }
}

const handleImport = async () => {
  if (!importFile.value || appStore.submitting) return
  appStore.submitting = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    const { data } = await importSuppliers(formData)
    importResult.value = data
    appStore.showToast('导入完成')
    // 导入成功后刷新表单的供应商列表
    if (formRef.value?.loadSuppliers) {
      formRef.value.loadSuppliers()
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '导入失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// 暴露给父组件
defineExpose({
  refresh: loadData,
})

onMounted(() => {
  loadData()
})
</script>
