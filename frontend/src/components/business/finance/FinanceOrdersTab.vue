<template>
  <div>
  <div class="card" style="overflow: visible">
    <!-- 移动端日期预设 -->
    <div class="flex gap-1 md:hidden p-3 pb-0">
      <span @click="setOrderDatePreset('')" :class="['tab', !orderDatePreset ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">全部</span>
      <span @click="setOrderDatePreset('today')" :class="['tab', orderDatePreset === 'today' ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">今天</span>
      <span @click="setOrderDatePreset('week')" :class="['tab', orderDatePreset === 'week' ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">本周</span>
      <span @click="setOrderDatePreset('month')" :class="['tab', orderDatePreset === 'month' ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">本月</span>
      <span @click="setOrderDatePreset('custom')" :class="['tab', orderDatePreset === 'custom' ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">自定义</span>
    </div>
    <!-- 订单筛选栏 -->
    <PageToolbar>
      <template #filters>
        <select v-model="orderFilter.type" @change="resetPage(); loadOrders()" class="toolbar-select">
          <option value="">全部类型</option>
          <option value="CASH">现款</option>
          <option value="CREDIT">账期</option>
          <option value="CONSIGN_OUT">寄售调拨</option>
          <option value="CONSIGN_SETTLE">寄售结算</option>
          <option value="RETURN">退货</option>
        </select>
        <select v-model="orderFilter.payment_status" @change="resetPage(); loadOrders()" class="toolbar-select">
          <option value="">全部状态</option>
          <option value="cleared">已结清</option>
          <option value="uncleared">未结清</option>
          <option value="unconfirmed">待确认</option>
          <option value="cancelled">已取消</option>
        </select>
        <select v-if="accountSets.length" v-model="orderFilter.account_set_id" @change="resetPage(); loadOrders()" class="toolbar-select">
          <option value="">全部账套</option>
          <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <DateRangePicker v-model:start="orderFilter.start" v-model:end="orderFilter.end" @change="resetPage(); loadOrders()" />
        <div class="toolbar-search-wrapper">
          <Search :size="14" class="toolbar-search-icon" />
          <input v-model="orderFilter.search" @input="debouncedLoadOrders" class="toolbar-search" placeholder="搜索订单号/客户/SN码/快递单号">
        </div>
        <button @click="resetOrderFilters" class="toolbar-reset" title="重置筛选"><RotateCcw :size="14" /></button>
      </template>
      <template #actions>
        <SegmentedControl v-model="financeViewMode" :options="viewModeOptions" @update:modelValue="financeSetViewMode" />
        <button v-if="hasPermission('finance')" @click="emit('open-payment')" class="btn btn-success btn-sm hidden md:block">收款</button>
        <button @click="handleExportOrders" class="btn btn-primary btn-sm hidden md:block">导出Excel</button>
      </template>
    </PageToolbar>
    <!-- 移动端自定义日期展开 -->
    <div v-if="orderDatePreset === 'custom'" class="px-3 pb-3 flex gap-2 md:hidden">
      <input v-model="orderFilter.start" @change="resetPage(); loadOrders()" type="date" class="input input-sm flex-1">
      <input v-model="orderFilter.end" @change="resetPage(); loadOrders()" type="date" class="input input-sm flex-1">
    </div>
    <!-- 桌面端表格（动态列，含排序 + 展开行） -->
    <div class="hidden md:block">
      <div class="overflow-x-auto table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th v-if="financeViewMode === 'summary'" class="px-1 py-2 w-6"></th>
              <th v-if="financeIsColumnVisible('order_no')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('order_no')">订单号 <span v-if="orderSort.key === 'order_no'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('order_type')" class="px-2 py-2 text-center cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('order_type')">类型 <span v-if="orderSort.key === 'order_type'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('customer')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('customer')">客户 <span v-if="orderSort.key === 'customer'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('related_order')" class="px-2 py-2 text-left">关联订单</th>
              <th v-if="financeIsColumnVisible('total_amount')" class="px-2 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('amount')">金额 <span v-if="orderSort.key === 'amount'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('total_cost') && hasPermission('finance')" class="px-2 py-2 text-right">成本</th>
              <th v-if="financeIsColumnVisible('total_profit') && hasPermission('finance')" class="px-2 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('profit')">毛利 <span v-if="orderSort.key === 'profit'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('paid_amount')" class="px-2 py-2 text-right">已付</th>
              <th v-if="financeIsColumnVisible('status')" class="px-2 py-2 text-center cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('status')">结清状态 <span v-if="orderSort.key === 'status'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('shipping_status')" class="px-2 py-2 text-center">发货</th>
              <th v-if="financeIsColumnVisible('item_count')" class="px-2 py-2 text-center">品项数</th>
              <th v-if="financeIsColumnVisible('remark')" class="px-2 py-2 text-left">备注</th>
              <th v-if="financeIsColumnVisible('warehouse')" class="px-2 py-2 text-left">仓库</th>
              <th v-if="financeIsColumnVisible('employee')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('employee')">业务员 <span v-if="orderSort.key === 'employee'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('creator')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('creator')">创建人 <span v-if="orderSort.key === 'creator'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('created_at')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('time')">创建时间 <span v-if="orderSort.key === 'time'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="financeIsColumnVisible('refunded')" class="px-2 py-2 text-center">退款状态</th>
              <th v-if="financeIsColumnVisible('rebate_used')" class="px-2 py-2 text-right">返利已用</th>
              <th v-if="financeIsColumnVisible('account_set')" class="px-2 py-2 text-left">账套</th>
              <th class="col-selector-th">
                <ColumnMenu :labels="financeColumnLabels" :visible="financeVisibleColumns" pinned="order_no"
                  @toggle="financeToggleColumn" @reset="financeResetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <template v-for="o in sortedOrders" :key="o.id">
              <!-- 汇总行 -->
              <tr class="clickable-row" @click="viewOrder(o.id)">
                <td v-if="financeViewMode === 'summary'" class="px-1 py-2 text-center text-muted" @click="toggleExpand(o.id, $event)">
                  <span class="cursor-pointer">{{ expandedRows[o.id] ? '&#x25BC;' : '&#x25B6;' }}</span>
                </td>
                <td v-if="financeIsColumnVisible('order_no')" class="px-2 py-2 font-mono text-xs text-primary">{{ o.order_no }}</td>
                <td v-if="financeIsColumnVisible('order_type')" class="px-2 py-2 text-center"><StatusBadge type="orderType" :status="o.order_type" /></td>
                <td v-if="financeIsColumnVisible('customer')" class="px-2 py-2">{{ o.customer_name || '-' }}</td>
                <td v-if="financeIsColumnVisible('related_order')" class="px-2 py-2">
                  <span v-if="o.related_order_no" @click.stop="viewOrder(o.related_order_id)" class="text-primary hover:underline cursor-pointer font-mono text-xs">{{ o.related_order_no }}</span>
                  <span v-else class="text-muted">-</span>
                </td>
                <td v-if="financeIsColumnVisible('total_amount')" class="px-2 py-2 text-right font-semibold">&#xA5;{{ fmt(o.total_amount) }}</td>
                <td v-if="financeIsColumnVisible('total_cost') && hasPermission('finance')" class="px-2 py-2 text-right text-muted">&#xA5;{{ fmt(o.total_cost) }}</td>
                <td v-if="financeIsColumnVisible('total_profit') && hasPermission('finance')" class="px-2 py-2 text-right" :class="o.total_profit >= 0 ? 'text-success' : 'text-error'">{{ fmt(o.total_profit) }}</td>
                <td v-if="financeIsColumnVisible('paid_amount')" class="px-2 py-2 text-right text-muted">&#xA5;{{ fmt(o.paid_amount) }}</td>
                <td v-if="financeIsColumnVisible('status')" class="px-2 py-2 text-center"><span :class="getOrderPayStatus(o).badge">{{ getOrderPayStatus(o).text }}</span></td>
                <td v-if="financeIsColumnVisible('shipping_status')" class="px-2 py-2 text-center"><span v-if="o.shipping_status && o.shipping_status !== 'completed'" :class="shippingStatusBadges[o.shipping_status]">{{ shippingStatusNames[o.shipping_status] }}</span><span v-else class="text-xs text-muted">-</span></td>
                <td v-if="financeIsColumnVisible('item_count')" class="px-2 py-2 text-center">{{ o.item_count ?? '-' }}</td>
                <td v-if="financeIsColumnVisible('remark')" class="px-2 py-2 text-muted text-xs max-w-[150px] truncate">{{ o.remark || '-' }}</td>
                <td v-if="financeIsColumnVisible('warehouse')" class="px-2 py-2">{{ o.warehouse_name || '-' }}</td>
                <td v-if="financeIsColumnVisible('employee')" class="px-2 py-2 text-muted">{{ o.employee_name || '-' }}</td>
                <td v-if="financeIsColumnVisible('creator')" class="px-2 py-2 text-muted">{{ o.creator_name }}</td>
                <td v-if="financeIsColumnVisible('created_at')" class="px-2 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
                <td v-if="financeIsColumnVisible('refunded')" class="px-2 py-2 text-center"><span v-if="o.refunded && o.is_cleared" class="badge badge-green text-xs">已退款</span><span v-else-if="o.refunded" class="badge badge-warning text-xs">需要退款</span><span v-else class="text-xs text-muted">-</span></td>
                <td v-if="financeIsColumnVisible('rebate_used')" class="px-2 py-2 text-right">{{ o.rebate_used ? '&#xA5;' + fmt(o.rebate_used) : '-' }}</td>
                <td v-if="financeIsColumnVisible('account_set')" class="px-2 py-2">{{ o.account_set_name || '-' }}</td>
                <td></td>
              </tr>
              <!-- 展开行：商品明细子表 -->
              <tr v-if="(financeViewMode === 'summary' && expandedRows[o.id]) || financeViewMode === 'detail'">
                <td :colspan="100" class="bg-elevated/50 px-6 py-3">
                  <div v-if="loadingItems[o.id]" class="text-center text-muted text-sm py-2">加载中...</div>
                  <table v-else-if="expandedItems[o.id]?.length" class="w-full text-xs">
                    <thead>
                      <tr class="text-muted border-b">
                        <th class="px-2 py-1.5 text-left font-medium">商品SKU</th>
                        <th class="px-2 py-1.5 text-left font-medium">商品名称</th>
                        <th class="px-2 py-1.5 text-left font-medium">仓库</th>
                        <th class="px-2 py-1.5 text-center font-medium">数量</th>
                        <th class="px-2 py-1.5 text-right font-medium">单价</th>
                        <th v-if="hasPermission('finance')" class="px-2 py-1.5 text-right font-medium">成本价</th>
                        <th class="px-2 py-1.5 text-right font-medium">金额</th>
                        <th v-if="hasPermission('finance')" class="px-2 py-1.5 text-right font-medium">毛利</th>
                        <th class="px-2 py-1.5 text-center font-medium">已发货数</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-border-light">
                      <tr v-for="item in expandedItems[o.id]" :key="item.id">
                        <td class="px-2 py-1.5 text-primary font-mono">{{ item.product_sku }}</td>
                        <td class="px-2 py-1.5">{{ item.product_name }}</td>
                        <td class="px-2 py-1.5 text-muted">{{ item.warehouse_name || '-' }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.quantity }}</td>
                        <td class="px-2 py-1.5 text-right">&#xA5;{{ fmt(item.unit_price) }}</td>
                        <td v-if="hasPermission('finance')" class="px-2 py-1.5 text-right">&#xA5;{{ fmt(item.cost_price) }}</td>
                        <td class="px-2 py-1.5 text-right font-medium">&#xA5;{{ fmt(item.amount) }}</td>
                        <td v-if="hasPermission('finance')" class="px-2 py-1.5 text-right" :class="item.profit >= 0 ? 'text-success' : 'text-error'">{{ fmt(item.profit) }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.shipped_qty }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else class="text-muted text-sm text-center py-2">暂无明细</div>
                </td>
              </tr>
            </template>
          </tbody>
          <tfoot v-if="sortedOrders.length > 0 || hasPagination" class="bg-elevated font-semibold text-sm">
            <tr>
              <td v-if="financeViewMode === 'summary'" class="px-1 py-2"></td>
              <td v-if="financeIsColumnVisible('order_no')" class="px-2 py-2 text-left">本页合计</td>
              <td v-if="financeIsColumnVisible('order_type')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('customer')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('related_order')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('total_amount')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.total_amount) }}</td>
              <td v-if="financeIsColumnVisible('total_cost') && hasPermission('finance')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.total_cost) }}</td>
              <td v-if="financeIsColumnVisible('total_profit') && hasPermission('finance')" class="px-2 py-2 text-right" :class="pageSummary.total_profit >= 0 ? 'text-success' : 'text-error'">{{ fmt(pageSummary.total_profit) }}</td>
              <td v-if="financeIsColumnVisible('paid_amount')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.paid_amount) }}</td>
              <td v-if="financeIsColumnVisible('status')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('shipping_status')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('item_count')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('remark')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('warehouse')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('employee')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('creator')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('created_at')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('refunded')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('rebate_used')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.rebate_used) }}</td>
              <td v-if="financeIsColumnVisible('account_set')" class="px-2 py-2"></td>
              <td></td>
            </tr>
            <tr v-if="hasPagination" class="font-normal">
              <td :colspan="100" class="px-3.5 py-2.5">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
                  <div class="flex items-center gap-1">
                    <button @click="prevPage(); loadOrders()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">‹</button>
                    <template v-for="(p, i) in visiblePages" :key="i">
                      <span v-if="p === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                      <button v-else @click="goToPage(p); loadOrders()" :class="p === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ p }}</button>
                    </template>
                    <button @click="nextPage(); loadOrders()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">›</button>
                  </div>
                  <span class="text-xs text-muted w-16"></span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
        <div v-if="!allOrders.length" class="p-6 text-center text-muted text-sm">暂无订单</div>
      </div>
    </div>
    <!-- 移动端卡片列表 -->
    <div class="md:hidden divide-y">
      <div v-for="o in sortedOrders" :key="'m-' + o.id" @click="viewOrder(o.id)" class="p-3 cursor-pointer active:bg-elevated">
        <div class="flex justify-between items-center mb-1.5">
          <span class="font-mono text-xs text-primary font-semibold">{{ o.order_no }}</span>
          <span class="font-semibold">¥{{ fmt(o.total_amount) }}</span>
        </div>
        <div class="flex justify-between items-center">
          <div class="flex items-center gap-2 min-w-0 flex-1 mr-3">
            <span class="text-sm font-medium truncate">{{ o.customer_name || '-' }}</span>
            <span :class="orderTypeBadges[o.order_type]" class="text-xs flex-shrink-0">{{ orderTypeNames[o.order_type] }}</span>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <span v-if="o.shipping_status && o.shipping_status !== 'completed'" :class="shippingStatusBadges[o.shipping_status]" class="text-xs">{{ shippingStatusNames[o.shipping_status] }}</span>
            <span :class="getOrderPayStatus(o).badge" class="text-xs">{{ getOrderPayStatus(o).text }}</span>
            <span class="text-xs text-muted">{{ fmtDate(o.created_at) }}</span>
          </div>
        </div>
      </div>
      <div v-if="!allOrders.length" class="p-6 text-center text-muted text-sm">暂无订单</div>
    </div>
  </div>

  <!-- 订单详情弹窗 -->
  <FinanceOrderDetailModal
    :order-id="selectedOrderId"
    v-model:visible="showDetail"
    @cancel-order="handleCancelOrder"
    @data-changed="loadOrders(); emit('data-changed')"
    @open-payment="emit('open-payment', $event)"
  />

  <!-- 取消订单向导 -->
  <FinanceOrderCancelWizard
    :preview-data="cancelPreviewData"
    v-model:visible="showCancel"
    @cancelled="onCancelDone"
    @data-changed="emit('data-changed')"
  />
  </div>
</template>

<script setup>
/**
 * 订单明细 Tab
 * 包含订单列表（筛选/排序/导出）+ 订单详情弹窗 + 取消订单向导
 */
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import { useSort } from '../../../composables/useSort'
import { usePagination } from '../../../composables/usePagination'
import { useColumnConfig } from '../../../composables/useColumnConfig'
import { getAllOrders, exportOrders, getOrderItems } from '../../../api/finance'
import { getAccountSets } from '../../../api/accounting'
import { cancelOrder, cancelPreview } from '../../../api/orders'
import { orderTypeNames, orderTypeBadges, shipmentStatusBadges, shippingStatusNames, shippingStatusBadges } from '../../../utils/constants'
import StatusBadge from '../../common/StatusBadge.vue'
import { RotateCcw, Search } from 'lucide-vue-next'
import ColumnMenu from '../../common/ColumnMenu.vue'
import PageToolbar from '../../common/PageToolbar.vue'
import DateRangePicker from '../../common/DateRangePicker.vue'
import SegmentedControl from '../../common/SegmentedControl.vue'
import FinanceOrderDetailModal from './FinanceOrderDetailModal.vue'
import FinanceOrderCancelWizard from './FinanceOrderCancelWizard.vue'
import { downloadBlob } from '../../../composables/useDownload'

// --- Props & Emits ---
const props = defineProps({
  /** 当前 Tab 是否激活 */
  active: Boolean,
  /** 当前 Tab 名称：'orders' | 'unpaid' */
  tab: { type: String, default: 'orders' }
})
const emit = defineEmits([
  'data-changed',   // 数据变更通知父组件
  'open-payment'    // 请求打开收款弹窗
])

// --- Stores ---
const appStore = useAppStore()
// --- Composables ---
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()
const { sortState: orderSort, toggleSort: toggleOrderSort, genericSort: genericSortOrder } = useSort()
const { page, pageSize, total, totalPages, hasPagination, paginationParams, visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage, saveNextCursor } = usePagination(20)

// 视图模式选项
const viewModeOptions = [
  { value: 'summary', label: '汇总' },
  { value: 'detail', label: '明细' }
]

// 列定义
const financeColumnDefs = {
  order_no: { label: '订单号', defaultVisible: true },
  order_type: { label: '类型', defaultVisible: true, align: 'center' },
  customer: { label: '客户', defaultVisible: true },
  total_amount: { label: '金额', defaultVisible: true, align: 'right' },
  total_cost: { label: '成本', defaultVisible: false, align: 'right' },
  total_profit: { label: '毛利', defaultVisible: true, align: 'right' },
  paid_amount: { label: '已付', defaultVisible: false, align: 'right' },
  status: { label: '结清状态', defaultVisible: true, align: 'center' },
  shipping_status: { label: '发货', defaultVisible: true, align: 'center' },
  item_count: { label: '品项数', defaultVisible: true, align: 'center' },
  remark: { label: '备注', defaultVisible: true },
  warehouse: { label: '仓库', defaultVisible: true },
  employee: { label: '业务员', defaultVisible: true },
  created_at: { label: '创建时间', defaultVisible: true },
  related_order: { label: '关联订单', defaultVisible: false },
  refunded: { label: '退款状态', defaultVisible: false, align: 'center' },
  rebate_used: { label: '返利已用', defaultVisible: false, align: 'right' },
  creator: { label: '创建人', defaultVisible: false },
  account_set: { label: '账套', defaultVisible: false },
}

const {
  columnLabels: financeColumnLabels, visibleColumns: financeVisibleColumns,
  showColumnMenu: financeShowColumnMenu, menuAttr: financeMenuAttr,
  toggleColumn: financeToggleColumn, isColumnVisible: financeIsColumnVisible,
  resetColumns: financeResetColumns, viewMode: financeViewMode, setViewMode: financeSetViewMode
} = useColumnConfig('finance_order_columns', financeColumnDefs, { supportViewMode: true })

// 展开行状态
const expandedRows = reactive({})
const expandedItems = reactive({})
const loadingItems = reactive({})

const toggleExpand = async (orderId, e) => {
  e?.stopPropagation()
  if (expandedRows[orderId]) { delete expandedRows[orderId]; return }
  expandedRows[orderId] = true
  if (!expandedItems[orderId]) {
    loadingItems[orderId] = true
    try { const { data } = await getOrderItems(orderId); expandedItems[orderId] = data.items || data }
    catch (err) { console.error(err) }
    finally { loadingItems[orderId] = false }
  }
}

/** 明细模式：自动加载所有订单的商品明细 */
const loadAllItems = async () => {
  const orders = sortedOrders.value
  await Promise.all(orders.map(async (o) => {
    if (!expandedItems[o.id]) {
      loadingItems[o.id] = true
      try { const { data } = await getOrderItems(o.id); expandedItems[o.id] = data.items || data }
      catch (err) { console.error(err) }
      finally { loadingItems[o.id] = false }
    }
  }))
}

watch(financeViewMode, (mode) => {
  if (mode === 'detail') loadAllItems()
})

// ===== 本地状态 =====
/** 移动端日期预设选中值 */
const orderDatePreset = ref('')

/** 订单筛选条件 */
const orderFilter = reactive({ type: '', payment_status: '', start: '', end: '', search: '', account_set_id: '' })
/** 账套列表 */
const accountSets = ref([])

/** 全部订单数据 */
const allOrders = ref([])

// --- 弹窗控制 ---
const selectedOrderId = ref(null)
const showDetail = ref(false)
const cancelPreviewData = ref(null)
const showCancel = ref(false)

// ===== 计算属性 =====
/** 按排序条件排列的订单列表 */
const sortedOrders = computed(() => {
  return genericSortOrder(allOrders.value, {
    order_no: o => o.order_no || '',
    order_type: o => o.order_type || '',
    customer: o => (o.customer_name || '').toLowerCase(),
    amount: o => Number(o.total_amount) || 0,
    profit: o => Number(o.total_profit) || 0,
    status: o => o.is_cleared ? 1 : 0,
    employee: o => (o.employee_name || '').toLowerCase(),
    creator: o => (o.creator_name || '').toLowerCase(),
    time: o => o.created_at || ''
  })
})

/** 本页合计（基于当前排序/筛选后的数据） */
const pageSummary = computed(() => {
  const rows = sortedOrders.value
  const sum = { total_amount: 0, total_cost: 0, total_profit: 0, paid_amount: 0, rebate_used: 0 }
  for (const o of rows) {
    sum.total_amount += Number(o.total_amount) || 0
    sum.total_cost += Number(o.total_cost) || 0
    sum.total_profit += Number(o.total_profit) || 0
    sum.paid_amount += Number(o.paid_amount) || 0
    sum.rebate_used += Number(o.rebate_used) || 0
  }
  for (const k in sum) sum[k] = Math.round(sum[k] * 100) / 100
  return sum
})

// ===== 辅助函数 =====
/** 获取订单付款状态徽标 */
const getOrderPayStatus = (o) => {
  if (o.shipping_status === 'cancelled') return { text: '已取消', badge: 'badge badge-gray' }
  if (!o.is_cleared) return { text: '未结清', badge: 'badge badge-red' }
  if (o.has_unconfirmed_payment) return { text: '待确认', badge: 'badge badge-orange' }
  return { text: '已结清', badge: 'badge badge-green' }
}

// ===== 日期预设 =====
/** 设置移动端日期预设（全部/今天/本周/本月/自定义） */
const setOrderDatePreset = (preset) => {
  orderDatePreset.value = preset
  if (preset === 'custom') return
  const now = new Date()
  const pad = n => String(n).padStart(2, '0')
  const fmtD = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  if (preset === 'today') {
    orderFilter.start = fmtD(now)
    orderFilter.end = fmtD(now)
  } else if (preset === 'week') {
    const d = new Date(now)
    d.setDate(d.getDate() - d.getDay() + 1)
    orderFilter.start = fmtD(d)
    orderFilter.end = fmtD(now)
  } else if (preset === 'month') {
    const d = new Date(now.getFullYear(), now.getMonth(), 1)
    orderFilter.start = fmtD(d)
    orderFilter.end = fmtD(now)
  } else {
    orderFilter.start = ''
    orderFilter.end = ''
  }
  resetPage()
  loadOrders()
}

/** 重置所有订单筛选条件 */
const resetOrderFilters = () => {
  orderFilter.type = ''
  orderFilter.payment_status = ''
  orderFilter.start = ''
  orderFilter.end = ''
  orderFilter.search = ''
  orderFilter.account_set_id = ''
  orderDatePreset.value = ''
  resetPage()
  loadOrders()
}

// ===== 数据加载 =====
/** 加载订单列表 */
const loadOrders = async () => {
  try {
    const params = { ...paginationParams.value }
    if (orderFilter.type) params.order_type = orderFilter.type
    if (orderFilter.payment_status) params.payment_status = orderFilter.payment_status
    if (orderFilter.start) params.start_date = orderFilter.start
    if (orderFilter.end) params.end_date = orderFilter.end
    if (orderFilter.search) params.search = orderFilter.search
    if (orderFilter.account_set_id) params.account_set_id = orderFilter.account_set_id
    if (props.tab === 'unpaid') params.unpaid_only = true
    const { data } = await getAllOrders(params)
    allOrders.value = data.items || data
    total.value = data.total ?? 0
    saveNextCursor(data.next_cursor)
  } catch (e) {
    console.error('加载订单失败', e)
  }
}

// Tab 切换时重新加载数据
watch(() => props.tab, () => {
  if (props.active) { resetPage(); loadOrders() }
})

/** 防抖搜索定时器 */
let _searchTimer = null
/** 搜索输入防抖300ms后加载 */
const debouncedLoadOrders = () => {
  clearTimeout(_searchTimer)
  resetPage()
  _searchTimer = setTimeout(loadOrders, 300)
}
onUnmounted(() => clearTimeout(_searchTimer))

// ===== 订单详情 =====
/** 查看订单详情 */
const viewOrder = (id) => {
  selectedOrderId.value = id
  showDetail.value = true
}

// ===== 取消订单 =====
/** 发起取消订单——先获取预览数据 */
const handleCancelOrder = async (orderId) => {
  try {
    const { data } = await cancelPreview(orderId)
    cancelPreviewData.value = data
    const hasPaid = data.paid_amount > 0 || data.rebate_used > 0

    // 寄售调拨 / 未发货未收款 / 未发货且收款未确认 → 直接简单确认
    if (data.order_type === 'CONSIGN_OUT' || (!data.is_partial && (!hasPaid || !data.has_confirmed_payment))) {
      const confirmed = await appStore.customConfirm('确认取消', `确认取消订单 ${data.order_no}？`)
      if (!confirmed) return
      appStore.submitting = true
      try {
        const { data: result } = await cancelOrder(data.order_id, {
          refund_amount: 0, refund_rebate: 0,
          refund_method: 'balance', refund_payment_method: 'cash'
        })
        appStore.showToast(result.message)
        showDetail.value = false
        loadOrders()
        emit('data-changed')
      } catch (e) {
        appStore.showToast(e.response?.data?.detail || '取消失败', 'error')
      } finally {
        appStore.submitting = false
      }
      return
    }

    // 复杂路径：打开取消向导
    showDetail.value = false
    showCancel.value = true
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '获取取消预览失败', 'error')
  }
}

/** 取消订单完成回调 */
const onCancelDone = () => {
  showCancel.value = false
  showDetail.value = false
  loadOrders()
}

// ===== 导出订单 =====
/** 导出订单为 Excel/CSV */
const handleExportOrders = async () => {
  try {
    const params = {}
    if (orderFilter.type) params.order_type = orderFilter.type
    if (orderFilter.start) params.start_date = orderFilter.start
    if (orderFilter.end) params.end_date = orderFilter.end
    const response = await exportOrders(params)
    downloadBlob(response.data, '订单明细_' + new Date().toISOString().slice(0, 19).replace(/:/g, '') + '.csv')
    appStore.showToast('导出成功')
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}

// ===== 刷新方法（暴露给父组件） =====
/** 刷新订单列表 */
const refresh = () => {
  loadOrders()
}

// 暴露给父组件的方法
defineExpose({ refresh, viewOrder })

// ===== 初始化 =====
onMounted(async () => {
  // 加载账套列表
  try { const res = await getAccountSets(); const d = res.data; accountSets.value = d.items || d || [] } catch {}
  // 激活时加载订单
  if (props.active) loadOrders()
})
</script>
