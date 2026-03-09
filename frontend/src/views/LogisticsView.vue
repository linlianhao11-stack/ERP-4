<template>
  <div>
    <!-- 状态筛选 Tabs -->
    <div class="flex flex-wrap gap-1 mb-3">
      <span
        @click="shipmentFilter.status = ''; loadShipments()"
        :class="['tab', !shipmentFilter.status ? 'active' : '']"
      >全部</span>
      <span
        @click="shipmentFilter.status = 'pending'; loadShipments()"
        :class="['tab', shipmentFilter.status === 'pending' ? 'active' : '']"
      >待发货</span>
      <span
        @click="shipmentFilter.status = 'shipped'; loadShipments()"
        :class="['tab', shipmentFilter.status === 'shipped' ? 'active' : '']"
      >已发货</span>
      <span
        @click="shipmentFilter.status = 'in_transit'; loadShipments()"
        :class="['tab', shipmentFilter.status === 'in_transit' ? 'active' : '']"
      >在途</span>
      <span
        @click="shipmentFilter.status = 'signed'; loadShipments()"
        :class="['tab', shipmentFilter.status === 'signed' ? 'active' : '']"
      >已签收</span>
      <span
        @click="shipmentFilter.status = 'problem'; loadShipments()"
        :class="['tab', shipmentFilter.status === 'problem' ? 'active' : '']"
      >异常</span>
    </div>

    <!-- 搜索栏 + 列设置菜单 -->
    <div class="mb-3 flex items-center gap-2">
      <input
        v-model="shipmentFilter.search"
        @input="debouncedLoadShipments"
        class="input input-sm flex-1 md:max-w-64"
        placeholder="搜索订单号/快递单号/客户"
      >
      <div class="relative hidden md:block" data-column-menu>
        <button @click="showColumnMenu = !showColumnMenu" class="btn btn-secondary btn-sm text-lg px-2" title="列设置">⋯</button>
        <div v-if="showColumnMenu" class="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border p-2 z-50 min-w-[140px]">
          <div v-for="(label, key) in columnLabels" :key="key"
            @click="toggleColumn(key)"
            class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-[#f5f5f7] cursor-pointer text-sm select-none">
            <span class="w-4 text-center">{{ visibleColumns[key] ? '✓' : '' }}</span>
            <span>{{ label }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 桌面端表格 -->
    <div class="card hidden md:block">
      <div class="overflow-x-auto">
        <table class="w-full text-sm" style="min-width:900px">
          <thead>
            <tr class="bg-[#f5f5f7] text-left">
              <th v-if="isColumnVisible('order_no')" class="p-3 cursor-pointer select-none hover:text-[#0071e3]" @click="toggleSort('order_no')">
                订单号
                <span v-if="shipmentSort.key === 'order_no'" class="text-[#0071e3]">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('order_type')" class="p-3 cursor-pointer select-none hover:text-[#0071e3]" @click="toggleSort('order_type')">
                类型
                <span v-if="shipmentSort.key === 'order_type'" class="text-[#0071e3]">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('customer')" class="p-3 cursor-pointer select-none hover:text-[#0071e3]" @click="toggleSort('customer')">
                客户
                <span v-if="shipmentSort.key === 'customer'" class="text-[#0071e3]">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('shipping_status')" class="p-3">发货状态</th>
              <th v-if="isColumnVisible('carrier')" class="p-3 cursor-pointer select-none hover:text-[#0071e3]" @click="toggleSort('carrier')">
                快递公司
                <span v-if="shipmentSort.key === 'carrier'" class="text-[#0071e3]">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('tracking_no')" class="p-3">快递单号</th>
              <th v-if="isColumnVisible('sn')" class="p-3">SN码</th>
              <th v-if="isColumnVisible('shipped_at')" class="p-3 cursor-pointer select-none hover:text-[#0071e3]" @click="toggleSort('shipped_at')">
                发货时间
                <span v-if="shipmentSort.key === 'shipped_at'" class="text-[#0071e3]">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('status')" class="p-3 cursor-pointer select-none hover:text-[#0071e3]" @click="toggleSort('status')">
                物流状态
                <span v-if="shipmentSort.key === 'status'" class="text-[#0071e3]">{{ shipmentSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('last_info')" class="p-3">物流信息</th>
              <th v-if="isColumnVisible('actions')" class="p-3">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in sortedShipments"
              :key="s.order_id"
              @click="viewShipment(s.order_id)"
              class="border-t hover:bg-[#f5f5f7] cursor-pointer"
            >
              <td v-if="isColumnVisible('order_no')" class="p-3 font-mono text-xs">{{ s.order_no }}</td>
              <td v-if="isColumnVisible('order_type')" class="p-3">
                <span :class="getOrderTypeBadge(s.order_type)">{{ getOrderTypeName(s.order_type) }}</span>
              </td>
              <td v-if="isColumnVisible('customer')" class="p-3">{{ s.customer_name || '-' }}</td>
              <td v-if="isColumnVisible('shipping_status')" class="p-3">
                <span :class="getShippingBadge(s.shipping_status)">{{ getShippingName(s.shipping_status) }}</span>
              </td>
              <td v-if="isColumnVisible('carrier')" class="p-3">{{ s.carrier_name || '-' }}</td>
              <td v-if="isColumnVisible('tracking_no')" class="p-3">
                <span v-if="s.tracking_no" class="font-mono text-xs">{{ s.tracking_no }}</span>
                <span v-else class="text-[#86868b]">-</span>
                <span
                  v-if="s.shipment_count > 1"
                  class="ml-1 text-xs text-[#ff9f0a] bg-[#fff3e0] px-1.5 py-0.5 rounded"
                >({{ s.shipment_count }}个单号)</span>
              </td>
              <td v-if="isColumnVisible('sn')" class="p-3">
                <span :class="['text-xs px-2 py-0.5 rounded-full', s.sn_status === '已添加' ? 'bg-[#e8f8ee] text-[#34c759]' : 'bg-[#f5f5f7] text-[#86868b]']">
                  {{ s.sn_status }}
                </span>
              </td>
              <td v-if="isColumnVisible('shipped_at')" class="p-3 text-xs text-[#6e6e73] whitespace-nowrap">{{ s.created_at ? fmtDate(s.created_at) : '-' }}</td>
              <td v-if="isColumnVisible('status')" class="p-3">
                <span :class="['text-xs px-2 py-1 rounded-full', getShipmentStatusBadge(s.status)]">{{ s.status_text }}</span>
              </td>
              <td v-if="isColumnVisible('last_info')" class="p-3 text-xs text-[#6e6e73] max-w-[200px] truncate" :title="s.last_info">{{ s.last_info || '-' }}</td>
              <td v-if="isColumnVisible('actions')" class="p-3" @click.stop>
                <button
                  v-if="s.all_tracking?.length"
                  @click="copyAllTracking(s.all_tracking)"
                  class="btn btn-secondary btn-sm text-xs"
                >复制</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!shipments.length" class="p-6 text-center text-[#86868b] text-sm">暂无物流记录</div>
      </div>
    </div>

    <!-- 移动端卡片列表 -->
    <div class="md:hidden space-y-2">
      <div
        v-for="s in sortedShipments"
        :key="'m-' + s.order_id"
        @click="viewShipment(s.order_id)"
        class="card p-3 cursor-pointer active:bg-[#f5f5f7]"
      >
        <div class="flex justify-between items-center mb-1.5">
          <span class="font-mono text-xs text-[#0071e3] font-semibold">{{ s.order_no }}</span>
          <div class="flex gap-1">
            <span :class="getShippingBadge(s.shipping_status)" class="text-xs">{{ getShippingName(s.shipping_status) }}</span>
            <span :class="['text-xs px-2 py-0.5 rounded-full', getShipmentStatusBadge(s.status)]">{{ s.status_text }}</span>
          </div>
        </div>
        <div class="flex justify-between items-center mb-1.5">
          <span class="text-sm font-medium">{{ s.customer_name || '-' }}</span>
          <span :class="getOrderTypeBadge(s.order_type)" class="text-xs">{{ getOrderTypeName(s.order_type) }}</span>
        </div>
        <div v-if="s.tracking_no" class="flex items-center gap-2 mb-1">
          <span class="text-xs text-[#86868b]">{{ s.carrier_name || '快递' }}</span>
          <span class="font-mono text-xs flex-1 truncate">{{ s.tracking_no }}</span>
          <span
            v-if="s.shipment_count > 1"
            class="text-xs text-[#ff9f0a] bg-[#fff3e0] px-1.5 py-0.5 rounded flex-shrink-0"
          >({{ s.shipment_count }}个)</span>
          <button
            v-if="s.all_tracking?.length"
            @click.stop="copyAllTracking(s.all_tracking)"
            class="text-xs text-[#0071e3] font-semibold flex-shrink-0 px-2 py-1 bg-[#e8f4fd] rounded"
          >复制</button>
        </div>
        <div v-else class="text-xs text-[#86868b] mb-1">未填写快递信息</div>
        <div v-if="s.last_info" class="text-xs text-[#86868b] truncate">{{ s.last_info }}</div>
      </div>
      <div v-if="!shipments.length" class="card p-6 text-center text-[#86868b] text-sm">暂无物流记录</div>
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
import { useFormat } from '../composables/useFormat'
import { useShipment } from '../composables/useShipment'
import { useAppStore } from '../stores/app'
import { orderTypeNames, orderTypeBadges, shipmentStatusBadges, shippingStatusNames, shippingStatusBadges } from '../utils/constants'
import ShipmentDetailModal from '../components/business/logistics/ShipmentDetailModal.vue'

const appStore = useAppStore()
const { fmtDate } = useFormat()

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
  toggleSort,
  loadShipments,
  debouncedLoadShipments
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
const getShipmentStatusBadge = (status) => shipmentStatusBadges[status] || 'bg-[#f5f5f7] text-[#6e6e73]'
const getShippingName = (status) => shippingStatusNames[status] || status || '-'
const getShippingBadge = (status) => shippingStatusBadges[status] || 'badge badge-gray'

/** 复制所有快递单号（表格行中的复制按钮）*/
const copyAllTracking = (trackingList) => {
  if (!trackingList?.length) return
  const text = trackingList.map(t => {
    let s = (t.carrier_name || '未知') + ' 单号：' + t.tracking_no
    if (t.sn_code) s += ' SN：' + t.sn_code
    return s
  }).join(', ')
  navigator.clipboard.writeText(text).then(() => {
    appStore.showToast('已复制' + trackingList.length + '个快递单号')
  }).catch(() => {
    const t = document.createElement('textarea')
    t.value = text
    document.body.appendChild(t)
    t.select()
    document.execCommand('copy')
    document.body.removeChild(t)
    appStore.showToast('已复制' + trackingList.length + '个快递单号')
  })
}
</script>
