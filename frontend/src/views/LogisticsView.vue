<template>
  <div>
    <!-- 状态筛选 Tabs -->
    <div class="flex flex-wrap gap-1 mb-3">
      <span
        @click="shipmentFilter.status = ''; resetPage(); loadShipments()"
        :class="['tab', !shipmentFilter.status ? 'active' : '']"
      >全部</span>
      <span
        @click="shipmentFilter.status = 'pending'; resetPage(); loadShipments()"
        :class="['tab', shipmentFilter.status === 'pending' ? 'active' : '']"
      >待发货</span>
      <span
        @click="shipmentFilter.status = 'shipped'; resetPage(); loadShipments()"
        :class="['tab', shipmentFilter.status === 'shipped' ? 'active' : '']"
      >已发货</span>
      <span
        @click="shipmentFilter.status = 'in_transit'; resetPage(); loadShipments()"
        :class="['tab', shipmentFilter.status === 'in_transit' ? 'active' : '']"
      >在途</span>
      <span
        @click="shipmentFilter.status = 'signed'; resetPage(); loadShipments()"
        :class="['tab', shipmentFilter.status === 'signed' ? 'active' : '']"
      >已签收</span>
      <span
        @click="shipmentFilter.status = 'problem'; resetPage(); loadShipments()"
        :class="['tab', shipmentFilter.status === 'problem' ? 'active' : '']"
      >异常</span>
    </div>

    <!-- 移动端搜索栏 -->
    <div class="mb-3 md:hidden">
      <div class="toolbar-search-wrapper flex-1" style="max-width:none">
        <Search :size="14" class="toolbar-search-icon" />
        <input v-model="shipmentFilter.search" @input="debouncedLoadShipments" class="toolbar-search" placeholder="搜索订单号/快递单号...">
      </div>
    </div>

    <!-- 桌面端表格 -->
    <div class="card hidden md:block" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <div class="toolbar-search-wrapper" style="max-width:360px">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="shipmentFilter.search" @input="debouncedLoadShipments" class="toolbar-search" placeholder="搜索订单号/快递单号...">
          </div>
        </template>
      </PageToolbar>
      <div class="overflow-x-auto">
        <table class="w-full text-sm" style="min-width:900px">
          <thead class="bg-elevated">
            <tr>
              <th v-if="isColumnVisible('order_no')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('order_no')">
                订单号
                <span v-if="shipmentSort.key === 'order_no'" class="text-primary">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('order_type')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('order_type')">
                类型
                <span v-if="shipmentSort.key === 'order_type'" class="text-primary">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('customer')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('customer')">
                客户
                <span v-if="shipmentSort.key === 'customer'" class="text-primary">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('shipping_status')" class="px-2 py-2 text-left">发货状态</th>
              <th v-if="isColumnVisible('carrier')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('carrier')">
                快递公司
                <span v-if="shipmentSort.key === 'carrier'" class="text-primary">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('tracking_no')" class="px-2 py-2 text-left">快递单号</th>
              <th v-if="isColumnVisible('sn')" class="px-2 py-2 text-left">SN码</th>
              <th v-if="isColumnVisible('shipped_at')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('shipped_at')">
                发货时间
                <span v-if="shipmentSort.key === 'shipped_at'" class="text-primary">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('status')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleSort('status')">
                物流状态
                <span v-if="shipmentSort.key === 'status'" class="text-primary">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('last_info')" class="px-2 py-2 text-left">物流信息</th>
              <th v-if="isColumnVisible('order_amount')" class="px-2 py-2 text-right whitespace-nowrap cursor-pointer select-none hover:text-primary" @click="toggleSort('order_amount')">订单金额 <span v-if="shipmentSort.key === 'order_amount'" class="text-primary">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('remark')" class="px-2 py-2 text-left whitespace-nowrap">备注</th>
              <th v-if="isColumnVisible('employee')" class="px-2 py-2 text-left whitespace-nowrap cursor-pointer select-none hover:text-primary" @click="toggleSort('employee')">业务员 <span v-if="shipmentSort.key === 'employee'" class="text-primary">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('phone')" class="px-2 py-2 text-left whitespace-nowrap">收件电话</th>
              <th v-if="isColumnVisible('order_created_at')" class="px-2 py-2 text-left whitespace-nowrap">创建时间</th>
              <th v-if="isColumnVisible('actions')" class="px-2 py-2 text-left">操作</th>
              <!-- 列选择器 -->
              <th class="col-selector-th">
                <ColumnMenu :labels="columnLabels" :visible="visibleColumns"
                  @toggle="toggleColumn" @reset="resetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr
              v-for="s in sortedShipments"
              :key="s.order_id"
              @click="viewShipment(s.order_id)"
              class="hover:bg-elevated cursor-pointer"
            >
              <td v-if="isColumnVisible('order_no')" class="px-2 py-2 font-mono text-xs">
                <span v-if="s.shipping_status === 'pending' || s.shipping_status === 'partial'" class="todo-dot mr-1.5"></span>{{ s.order_no }}
              </td>
              <td v-if="isColumnVisible('order_type')" class="px-2 py-2">
                <span :class="getOrderTypeBadge(s.order_type)">{{ getOrderTypeName(s.order_type) }}</span>
              </td>
              <td v-if="isColumnVisible('customer')" class="px-2 py-2">{{ s.customer_name || '-' }}</td>
              <td v-if="isColumnVisible('shipping_status')" class="px-2 py-2">
                <span :class="getShippingBadge(s.shipping_status)">{{ getShippingName(s.shipping_status) }}</span>
              </td>
              <td v-if="isColumnVisible('carrier')" class="px-2 py-2">{{ s.carrier_name || '-' }}</td>
              <td v-if="isColumnVisible('tracking_no')" class="px-2 py-2">
                <span v-if="s.tracking_no" class="font-mono text-xs">{{ s.tracking_no }}</span>
                <span v-else class="text-muted">-</span>
                <span
                  v-if="s.shipment_count > 1"
                  class="ml-1 text-xs text-warning bg-orange-subtle px-1.5 py-0.5 rounded"
                >({{ s.shipment_count }}个单号)</span>
              </td>
              <td v-if="isColumnVisible('sn')" class="px-2 py-2">
                <span :class="['text-xs px-2 py-0.5 rounded-full', s.sn_status === '已添加' ? 'bg-success-subtle text-success' : 'bg-elevated text-muted']">
                  {{ s.sn_status }}
                </span>
              </td>
              <td v-if="isColumnVisible('shipped_at')" class="px-2 py-2 text-xs text-secondary whitespace-nowrap">{{ s.created_at ? fmtDate(s.created_at) : '-' }}</td>
              <td v-if="isColumnVisible('status')" class="px-2 py-2">
                <span :class="['text-xs px-2 py-1 rounded-full', getShipmentStatusBadge(s.status)]">{{ getShipmentStatusName(s.status, s.status_text) }}</span>
              </td>
              <td v-if="isColumnVisible('last_info')" class="px-2 py-2 text-xs text-secondary max-w-[200px] truncate" :title="s.last_info">{{ s.last_info || '-' }}</td>
              <td v-if="isColumnVisible('order_amount')" class="px-2 py-2 text-right font-semibold whitespace-nowrap">¥{{ fmt(s.total_amount) }}</td>
              <td v-if="isColumnVisible('remark')" class="px-2 py-2 text-muted text-xs max-w-[150px] truncate">{{ s.remark || '-' }}</td>
              <td v-if="isColumnVisible('employee')" class="px-2 py-2 whitespace-nowrap">{{ s.employee_name || '-' }}</td>
              <td v-if="isColumnVisible('phone')" class="px-2 py-2 text-xs whitespace-nowrap">{{ s.phone || '-' }}</td>
              <td v-if="isColumnVisible('order_created_at')" class="px-2 py-2 text-muted text-xs whitespace-nowrap">{{ fmtDate(s.created_at) }}</td>
              <td v-if="isColumnVisible('actions')" class="px-2 py-2" @click.stop>
                <button
                  v-if="s.all_tracking?.length"
                  @click="copyAllTracking(s.all_tracking)"
                  class="btn btn-secondary btn-sm text-xs"
                >复制</button>
              </td>
              <td></td>
            </tr>
          </tbody>
          <tfoot v-if="hasPagination" class="bg-elevated text-sm">
            <tr>
              <td :colspan="100" class="px-3.5 py-2.5">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
                  <div class="flex items-center gap-1">
                    <button @click="prevPage(); loadShipments()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">‹</button>
                    <template v-for="(p, i) in visiblePages" :key="i">
                      <span v-if="p === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                      <button v-else @click="goToPage(p); loadShipments()" :class="p === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ p }}</button>
                    </template>
                    <button @click="nextPage(); loadShipments()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">›</button>
                  </div>
                  <span class="text-xs text-muted w-16"></span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
        <div v-if="!shipments.length" class="p-6 text-center text-muted text-sm">暂无物流记录</div>
      </div>
    </div>

    <!-- 移动端卡片列表 -->
    <div class="md:hidden space-y-2">
      <div
        v-for="s in sortedShipments"
        :key="'m-' + s.order_id"
        @click="viewShipment(s.order_id)"
        class="card p-3 cursor-pointer active:bg-elevated"
      >
        <div class="flex justify-between items-center mb-1.5">
          <span class="font-mono text-xs text-primary font-semibold">
            <span v-if="s.shipping_status === 'pending' || s.shipping_status === 'partial'" class="todo-dot mr-1"></span>{{ s.order_no }}
          </span>
          <div class="flex gap-1">
            <span :class="getShippingBadge(s.shipping_status)" class="text-xs">{{ getShippingName(s.shipping_status) }}</span>
            <span :class="['text-xs px-2 py-0.5 rounded-full', getShipmentStatusBadge(s.status)]">{{ getShipmentStatusName(s.status, s.status_text) }}</span>
          </div>
        </div>
        <div class="flex justify-between items-center mb-1.5">
          <span class="text-sm font-medium">{{ s.customer_name || '-' }}</span>
          <span :class="getOrderTypeBadge(s.order_type)" class="text-xs">{{ getOrderTypeName(s.order_type) }}</span>
        </div>
        <div v-if="s.tracking_no" class="flex items-center gap-2 mb-1">
          <span class="text-xs text-muted">{{ s.carrier_name || '快递' }}</span>
          <span class="font-mono text-xs flex-1 truncate">{{ s.tracking_no }}</span>
          <span
            v-if="s.shipment_count > 1"
            class="text-xs text-warning bg-orange-subtle px-1.5 py-0.5 rounded flex-shrink-0"
          >({{ s.shipment_count }}个)</span>
          <button
            v-if="s.all_tracking?.length"
            @click.stop="copyAllTracking(s.all_tracking)"
            class="text-xs text-primary font-semibold flex-shrink-0 px-2 py-1 bg-info-subtle rounded"
          >复制</button>
        </div>
        <div v-else class="text-xs text-muted mb-1">未填写快递信息</div>
        <div v-if="s.last_info" class="text-xs text-muted truncate">{{ s.last_info }}</div>
      </div>
      <div v-if="!shipments.length" class="card p-6 text-center text-muted text-sm">暂无物流记录</div>
    </div>

    <!-- 物流详情弹窗 -->
    <ShipmentDetailModal
      :visible="showDetailModal"
      :order-id="detailOrderId"
      :carriers="carriers"
      @update:visible="showDetailModal = $event"
      @data-changed="loadShipments"
    />
  </div>
</template>

<script setup>
/**
 * LogisticsView — 物流管理页面（瘦容器）
 * 使用 useShipment composable 获取列表数据，ShipmentDetailModal 处理详情弹窗
 */
import { ref } from 'vue'
import { Search } from 'lucide-vue-next'
import ColumnMenu from '../components/common/ColumnMenu.vue'
import { useFormat } from '../composables/useFormat'
import { useShipment } from '../composables/useShipment'
import { useAppStore } from '../stores/app'
import { orderTypeNames, orderTypeBadges, shipmentStatusNames, shipmentStatusBadges, shippingStatusNames, shippingStatusBadges } from '../utils/constants'
import ShipmentDetailModal from '../components/business/logistics/ShipmentDetailModal.vue'
import PageToolbar from '../components/common/PageToolbar.vue'

const appStore = useAppStore()
const { fmt, fmtDate } = useFormat()

// 从 composable 获取列表数据和操作
const {
  shipments,
  shipmentFilter,
  carriers,
  shipmentSort,
  sortedShipments,
  columnLabels,
  visibleColumns,
  showColumnMenu,
  toggleColumn,
  isColumnVisible,
  resetColumns,
  menuAttr,
  toggleSort,
  loadShipments,
  debouncedLoadShipments,
  page, total, totalPages, hasPagination, visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage
} = useShipment()

// ---- 弹窗控制 ----
const showDetailModal = ref(false)
/** 当前查看详情的订单ID */
const detailOrderId = ref(null)

/** 打开物流详情弹窗 */
const viewShipment = (orderId) => {
  detailOrderId.value = orderId
  showDetailModal.value = true
}

// ---- 辅助函数（表格中使用）----
const getOrderTypeName = (type) => orderTypeNames[type] || type
const getOrderTypeBadge = (type) => orderTypeBadges[type] || 'badge badge-gray'
const getShipmentStatusBadge = (status) => shipmentStatusBadges[status] || 'bg-elevated text-secondary'
const getShipmentStatusName = (status, fallback) => shipmentStatusNames[status] || fallback || status || '-'
const getShippingName = (status) => shippingStatusNames[status] || status || '-'
const getShippingBadge = (status) => shippingStatusBadges[status] || 'badge badge-gray'

/** 复制文本到剪贴板（兼容非 HTTPS 环境） */
const copyText = (text, toast) => {
  const fallback = () => {
    const t = document.createElement('textarea')
    t.value = text
    t.style.position = 'fixed'
    t.style.opacity = '0'
    document.body.appendChild(t)
    t.select()
    document.execCommand('copy')
    document.body.removeChild(t)
    appStore.showToast(toast)
  }
  try {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => appStore.showToast(toast)).catch(fallback)
    } else {
      fallback()
    }
  } catch { fallback() }
}

/** 复制所有快递单号（表格行中的复制按钮）*/
const copyAllTracking = (trackingList) => {
  if (!trackingList?.length) return
  const text = trackingList.map(t => {
    let s = (t.carrier_name || '未知') + ' 单号：' + t.tracking_no
    if (t.sn_code) s += ' SN：' + t.sn_code
    return s
  }).join(', ')
  copyText(text, '已复制' + trackingList.length + '个快递单号')
}
</script>
