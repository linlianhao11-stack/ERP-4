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
              <th v-if="financeIsColumnVisible('salesperson')" class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleOrderSort('salesperson')">业务员 <span v-if="orderSort.key === 'salesperson'" class="text-primary">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
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
                <td v-if="financeIsColumnVisible('salesperson')" class="px-2 py-2 text-muted">{{ o.salesperson_name || '-' }}</td>
                <td v-if="financeIsColumnVisible('creator')" class="px-2 py-2 text-muted">{{ o.creator_name }}</td>
                <td v-if="financeIsColumnVisible('created_at')" class="px-2 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
                <td v-if="financeIsColumnVisible('refunded')" class="px-2 py-2 text-center"><span v-if="o.refunded" class="badge badge-warning text-xs">已退款</span><span v-else class="text-xs text-muted">-</span></td>
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
    <!-- 分页 -->
    <div v-if="hasPagination" class="flex items-center justify-center gap-2 py-3 border-t">
      <button @click="prevPage(); loadOrders()" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ totalPages }}</span>
      <button @click="nextPage(); loadOrders()" :disabled="page >= totalPages" class="btn btn-secondary btn-sm">下一页</button>
    </div>
  </div>

  <!-- ============ 弹窗：订单详情 ============ -->
  <div v-if="showOrderDetailModal" class="modal-overlay" @click.self="showOrderDetailModal = false; showReturnForm = false">
    <div class="modal-content" style="max-width:920px">
      <div class="modal-header">
        <h3 class="font-semibold">订单详情</h3>
        <button @click="showOrderDetailModal = false; showReturnForm = false" class="modal-close">&times;</button>
      </div>
      <div class="modal-body" v-if="orderDetail.order_no">
        <!-- 订单基本信息 -->
        <div class="mb-5 p-4 bg-elevated rounded-xl">
          <div class="flex justify-between items-start mb-2">
            <div>
              <div class="text-[15px] font-bold font-mono">{{ orderDetail.order_no }}</div>
              <div class="text-xs text-muted mt-0.5">
                <span v-if="orderDetail.salesperson_name">销售员: {{ orderDetail.salesperson_name }} · </span>
                {{ orderDetail.creator_name }} · {{ fmtDate(orderDetail.created_at) }}
              </div>
            </div>
            <StatusBadge type="orderType" :status="orderDetail.order_type" />
          </div>
          <div class="grid detail-grid grid-cols-2 gap-1.5 gap-x-4 text-[13px]">
            <div><span class="text-muted">客户:</span> {{ orderDetail.customer?.name || '-' }}</div>
            <div><span class="text-muted">仓库:</span> {{ orderDetail.warehouse?.name || '-' }}</div>
            <div v-if="orderDetail.related_order" class="col-span-2">
              <span class="text-muted">关联原订单:</span>
              <span @click="viewOrder(orderDetail.related_order.id)" class="text-primary hover:underline cursor-pointer font-mono">{{ orderDetail.related_order.order_no }}</span>
            </div>
            <div v-if="orderDetail.related_children?.length" class="col-span-2">
              <span class="text-muted">拆分订单:</span>
              <span v-for="child in orderDetail.related_children" :key="child.id" @click="viewOrder(child.id)" class="text-primary hover:underline cursor-pointer font-mono ml-1">{{ child.order_no }}</span>
            </div>
            <div><span class="text-muted">金额:</span> <span class="font-semibold">¥{{ fmt(orderDetail.total_amount) }}</span></div>
            <div v-if="hasPermission('finance')"><span class="text-muted">毛利:</span> <span :class="orderDetail.total_profit >= 0 ? 'text-success' : 'text-error'">¥{{ fmt(orderDetail.total_profit) }}</span></div>
            <div v-if="orderDetail.rebate_used > 0" class="col-span-2">
              <span class="text-muted">已使用返利:</span> <span class="text-success font-semibold">¥{{ fmt(orderDetail.rebate_used) }}</span>
            </div>
            <div v-if="orderDetail.credit_used > 0" class="col-span-2">
              <span class="text-muted">已使用在账资金:</span> <span class="text-primary font-semibold">¥{{ fmt(orderDetail.credit_used) }}</span>
            </div>
            <!-- 收款记录 -->
            <div v-if="orderDetail.payment_records && orderDetail.payment_records.length" class="col-span-2">
              <div v-for="pr in orderDetail.payment_records" :key="pr.id" class="flex items-center gap-2 text-[13px] mb-1">
                <span class="text-muted">{{ pr.source === 'CASH' ? '销售收款' : pr.source === 'REFUND' ? '退款' : pr.source === 'CREDIT' ? '账期回款' : pr.source === 'CONSIGN_SETTLE' ? '寄售结算' : pr.source || '回款' }}:</span>
                <span :class="pr.source === 'REFUND' ? 'font-semibold text-warning' : 'font-semibold text-success'">{{ pr.source === 'REFUND' ? '-' : '' }}¥{{ fmt(Math.abs(pr.amount)) }}</span>
                <span class="badge badge-blue" style="font-size:11px">{{ getPaymentMethodName(pr.payment_method) }}</span>
                <span v-if="pr.source !== 'REFUND'" :class="pr.is_confirmed ? 'text-success' : 'text-warning'" style="font-size:11px">{{ pr.is_confirmed ? '已确认' : '待确认' }}</span>
              </div>
            </div>
            <div v-else-if="!orderDetail.credit_used"><span class="text-muted">已付:</span> ¥{{ fmt(orderDetail.paid_amount) }}</div>
            <div><span class="text-muted">状态:</span> <span :class="orderDetail.is_cleared ? 'text-success' : 'text-error'">{{ orderDetail.is_cleared ? '已结清' : '未结清' }}</span></div>
            <div v-if="orderDetail.shipping_status"><span class="text-muted">发货:</span> <StatusBadge type="shippingStatus" :status="orderDetail.shipping_status" /></div>
            <div v-if="orderDetail.order_type === 'RETURN'" class="col-span-2">
              <span class="text-muted">退款状态:</span>
              <span :class="orderDetail.refunded ? 'text-warning' : 'text-error-emphasis'">{{ orderDetail.refunded ? '已退款给客户' : '形成在账资金' }}</span>
            </div>
            <div v-if="orderDetail.rebate_refund_records?.length" class="col-span-2">
              <div v-for="rr in orderDetail.rebate_refund_records" :key="rr.id" class="flex items-center gap-2 text-[13px] mb-1">
                <span class="text-muted">退回返利:</span>
                <span class="font-semibold text-warning">¥{{ fmt(rr.amount) }}</span>
                <span v-if="rr.remark" class="text-xs text-muted">{{ rr.remark }}</span>
              </div>
            </div>
            <div v-if="orderDetail.remark" class="col-span-2 pt-2 border-t border-line"><span class="text-muted">备注:</span> <span class="text-secondary">{{ orderDetail.remark }}</span></div>
          </div>
        </div>

        <!-- 商品明细（优先展示） -->
        <div class="mb-5">
          <div class="flex items-center gap-2 mb-2.5">
            <span class="text-[13px] font-semibold text-secondary">商品明细</span>
            <span v-if="orderDetail.items?.length" class="text-[11px] text-muted bg-elevated px-2 py-0.5 rounded-full">{{ orderDetail.items.length }} 件商品</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-[13px]">
              <thead class="bg-elevated">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-secondary">商品</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-secondary">单价</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-secondary">数量</th>
                  <th v-if="orderDetail.rebate_used > 0" class="px-3 py-2 text-right text-xs font-semibold text-secondary">返利</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-secondary">金额</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-secondary" v-if="hasPermission('finance')">毛利</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-line">
                <tr v-for="item in orderDetail.items" :key="item.product_id">
                  <td class="px-3 py-2.5">
                    <div class="font-medium">{{ item.product_name }}</div>
                    <div class="text-[11px] text-muted font-mono">{{ item.product_sku }}</div>
                  </td>
                  <td class="px-3 py-2.5 text-right">{{ fmt(item.unit_price) }}</td>
                  <td class="px-3 py-2.5 text-right">{{ item.quantity }}</td>
                  <td v-if="orderDetail.rebate_used > 0" class="px-3 py-2.5 text-right text-success">{{ item.rebate_amount > 0 ? '-¥' + fmt(item.rebate_amount) : '' }}</td>
                  <td class="px-3 py-2.5 text-right font-semibold">{{ fmt(item.amount) }}</td>
                  <td class="px-3 py-2.5 text-right" v-if="hasPermission('finance')" :class="item.profit >= 0 ? 'text-success' : 'text-error'">{{ fmt(item.profit) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 物流信息（卡片式） -->
        <div v-if="orderDetail.shipments?.length" class="mb-2">
          <div class="flex items-center gap-2 mb-2.5">
            <span class="text-[13px] font-semibold text-secondary">物流信息</span>
            <span class="text-[11px] text-muted bg-elevated px-2 py-0.5 rounded-full">{{ orderDetail.shipments.length }} 个物流单</span>
          </div>
          <div v-for="(sh, shIdx) in orderDetail.shipments" :key="sh.id" class="border border-line rounded-[10px] overflow-hidden mb-2.5 last:mb-0">
            <!-- 物流单头部 -->
            <div class="flex justify-between items-center px-3.5 py-2.5 bg-elevated">
              <div class="flex items-center gap-1.5">
                <span class="text-[13px] font-semibold text-secondary">物流单 {{ shIdx + 1 }}</span>
                <span class="text-xs text-muted">{{ sh.carrier_name || '未填写承运商' }}</span>
              </div>
              <StatusBadge type="shipmentStatus" :status="sh.status" />
            </div>
            <!-- 运单号 -->
            <div v-if="sh.tracking_no" class="flex items-center gap-1.5 px-3.5 py-2 border-b border-line">
              <span class="text-[11px] text-muted">运单号:</span>
              <span class="text-xs font-mono font-medium text-primary">{{ sh.tracking_no }}</span>
            </div>
            <!-- 发货商品明细 -->
            <div v-if="sh.items?.length" class="px-3.5 py-2">
              <div v-for="(si, idx) in sh.items" :key="idx" class="flex items-start gap-2.5 py-1.5" :class="idx < sh.items.length - 1 ? 'border-b border-line' : ''">
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-medium">{{ si.product_name }}</div>
                  <div class="text-[11px] text-muted font-mono">{{ si.product_sku }}</div>
                  <div v-if="si.sn_codes" class="mt-1 p-1.5 bg-success-subtle rounded-md">
                    <span class="text-[11px] text-muted font-semibold">SN:</span>
                    <span v-for="sn in parseSN(si.sn_codes)" :key="sn" class="text-[11px] text-success font-mono ml-1">{{ sn }}</span>
                  </div>
                </div>
                <span class="text-xs font-semibold text-secondary flex-shrink-0">× {{ si.quantity }}</span>
              </div>
            </div>
            <!-- 兜底：无明细时显示聚合SN码 -->
            <div v-else-if="sh.sn_code" class="px-3.5 py-2">
              <div class="p-1.5 bg-success-subtle rounded-md">
                <span class="text-[11px] text-muted font-semibold">SN:</span>
                <span class="text-[11px] text-success font-mono ml-1">{{ sh.sn_code }}</span>
              </div>
            </div>
            <!-- 最新物流动态 -->
            <div v-if="sh.last_info" class="px-3.5 py-2 border-t border-line text-[11px] text-muted">{{ sh.last_info }}</div>
          </div>
        </div>

        <!-- 退货表单 -->
        <div v-if="showReturnForm" class="mb-2">
          <div class="flex items-center gap-2 mb-2.5">
            <span class="text-[13px] font-semibold text-secondary">退货商品</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-[13px]">
              <thead class="bg-elevated">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-secondary">商品</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-secondary">单价</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-secondary">可退</th>
                  <th class="px-3 py-2 text-center text-xs font-semibold text-secondary" style="width:100px">退货数量</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-line">
                <tr v-for="item in returnForm.items" :key="item.product_id">
                  <td class="px-3 py-2.5">
                    <div class="font-medium">{{ item.product_name }}</div>
                    <div class="text-[11px] text-muted font-mono">{{ item.product_sku }}</div>
                  </td>
                  <td class="px-3 py-2.5 text-right">{{ fmt(item.unit_price) }}</td>
                  <td class="px-3 py-2.5 text-right text-muted">{{ item.max_qty }}</td>
                  <td class="px-3 py-2.5 text-center">
                    <input type="number" v-model.number="item.qty" :min="0" :max="item.max_qty" class="input text-center" style="width:80px" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="mt-3 px-1">
            <label class="flex items-center gap-2 cursor-pointer text-[13px]">
              <input type="checkbox" v-model="returnForm.refunded" class="rounded" />
              <span>已退款给客户</span>
              <span class="text-[11px] text-muted">（不勾选则形成在账资金）</span>
            </label>
          </div>
          <div class="flex gap-3 pt-4 mt-4 border-t border-line">
            <button type="button" @click="cancelReturnForm" class="btn btn-secondary flex-1">取消</button>
            <button type="button" @click="submitReturn" :disabled="!canSubmitReturn || returnSubmitting" class="btn btn-primary flex-1">
              {{ returnSubmitting ? '提交中...' : '确认退货' }}
            </button>
          </div>
        </div>
      </div>
      <!-- 底部操作按钮（独立于滚动区域） -->
      <div v-if="!showReturnForm" class="flex gap-3 px-6 py-4 border-t border-line">
        <button type="button" @click="showOrderDetailModal = false; showReturnForm = false" class="btn btn-secondary flex-1">关闭</button>
        <button v-if="canReturn" type="button" @click="openReturnForm" class="btn btn-primary flex-1">销售退货</button>
        <button v-if="orderDetail.shipping_status && ['pending', 'partial'].includes(orderDetail.shipping_status)" type="button" @click="handleCancelOrder(orderDetail.id)" class="btn flex-1" style="background:var(--error);color:#fff">取消订单</button>
      </div>
    </div>
  </div>

  <!-- ============ 弹窗：取消订单向导（3步） ============ -->
  <teleport to="body">
    <div v-if="showCancelModal && cancelPreviewData" class="modal-overlay" @click.self="showCancelModal = false">
      <div class="modal-content" style="max-width:640px">
        <div class="modal-header">
          <h3 class="font-semibold">取消订单 {{ cancelPreviewData.order_no }}</h3>
          <button @click="showCancelModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <!-- 步骤指示器 -->
          <div v-if="cancelStepCount > 1" class="flex items-center justify-center gap-2 mb-4">
            <template v-for="s in cancelStepCount" :key="s">
              <div :class="['w-2.5 h-2.5 rounded-full transition-all', cancelStep === s ? 'bg-primary scale-125' : (cancelStep > s ? 'bg-success' : 'bg-line-strong')]"></div>
              <div v-if="s < cancelStepCount" class="w-6 h-0.5" :class="cancelStep > s ? 'bg-success' : 'bg-line-strong'"></div>
            </template>
          </div>

          <!-- 第1步：确认商品 -->
          <div v-show="cancelStep === 1 && cancelPreviewData?.is_partial" class="space-y-4">
            <!-- 已发货商品（部分取消时显示） -->
            <div v-if="cancelPreviewData.is_partial">
              <div class="flex items-center gap-2 mb-2">
                <span class="w-5 h-5 rounded-full bg-success text-white text-xs flex items-center justify-center font-bold">✓</span>
                <span class="text-sm font-semibold text-foreground">已发货商品（将生成新订单）</span>
              </div>
              <div class="p-3 bg-success-subtle rounded-lg border border-success">
                <div v-for="item in cancelPreviewData.shipped_items" :key="'s-'+item.product_sku" class="flex justify-between text-sm py-1">
                  <span class="text-foreground">{{ item.product_name }} <span class="text-muted">x{{ item.shipped_qty }}</span></span>
                  <span class="font-semibold">¥{{ fmt(item.amount) }}</span>
                </div>
                <div class="border-t border-success mt-2 pt-2 flex justify-between text-sm font-bold">
                  <span>新订单金额</span>
                  <span class="text-success">¥{{ fmt(cancelPreviewData.new_order_amount) }}</span>
                </div>
              </div>
            </div>
            <!-- 取消商品 -->
            <div>
              <div class="flex items-center gap-2 mb-2">
                <span class="w-5 h-5 rounded-full bg-error text-white text-xs flex items-center justify-center font-bold">✕</span>
                <span class="text-sm font-semibold text-foreground">取消商品（释放库存预留）</span>
              </div>
              <div class="p-3 bg-error-subtle rounded-lg border border-error">
                <div v-for="item in cancelPreviewData.cancel_items" :key="'c-'+item.product_sku" class="flex justify-between text-sm py-1">
                  <span class="text-foreground">{{ item.product_name }} <span class="text-muted">x{{ item.cancel_qty }}</span></span>
                  <span>¥{{ fmt(item.amount) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 第2步：逐商品财务分配（部分取消时） -->
          <div v-show="cancelStep === 2" class="space-y-4">
            <div class="text-center mb-2">
              <div class="text-sm font-semibold text-foreground">新订单逐商品财务分配</div>
              <div class="text-xs text-muted mt-1">每个商品的现金+返利必须等于商品金额，影响开票单价</div>
            </div>
            <div class="text-xs text-muted p-2 bg-elevated rounded">
              原订单：付款 <span class="font-semibold text-foreground">¥{{ fmt(cancelPreviewData.paid_amount) }}</span>
              + 返利 <span class="font-semibold text-success">¥{{ fmt(cancelPreviewData.rebate_used) }}</span>
              = ¥{{ fmt(cancelPreviewData.total_amount) }}
            </div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead class="bg-elevated">
                  <tr>
                    <th class="px-2 py-1.5 text-left text-xs">商品</th>
                    <th class="px-2 py-1.5 text-right text-xs">数量</th>
                    <th class="px-2 py-1.5 text-right text-xs">金额</th>
                    <th class="px-2 py-1.5 text-center text-xs" style="min-width:100px">使用现金</th>
                    <th class="px-2 py-1.5 text-center text-xs" style="min-width:100px">使用返利</th>
                  </tr>
                </thead>
                <tbody class="divide-y">
                  <tr v-for="(alloc, idx) in cancelForm.item_allocations" :key="alloc.order_item_id">
                    <td class="px-2 py-1.5">
                      <div class="text-xs">{{ alloc.product_name }}</div>
                      <div class="text-[10px] text-muted">{{ alloc.product_sku }}</div>
                    </td>
                    <td class="px-2 py-1.5 text-right text-xs">{{ alloc.shipped_qty }}</td>
                    <td class="px-2 py-1.5 text-right text-xs font-semibold">¥{{ fmt(alloc.amount) }}</td>
                    <td class="px-2 py-1 text-center" style="min-width:100px">
                      <input v-model.number="alloc.paid" @input="onItemPaidChange(idx)" type="number" step="0.01" min="0" :max="alloc.amount" class="input text-xs py-1 text-center w-full">
                    </td>
                    <td class="px-2 py-1 text-center" style="min-width:100px">
                      <input v-model.number="alloc.rebate" @input="onItemRebateChange(idx)" type="number" step="0.01" min="0" :max="alloc.amount" class="input text-xs py-1 text-center w-full">
                    </td>
                  </tr>
                </tbody>
                <tfoot class="border-t-2 border-line-strong">
                  <tr class="font-semibold text-xs">
                    <td class="px-2 py-2" colspan="2">合计</td>
                    <td class="px-2 py-2 text-right">¥{{ fmt(cancelPreviewData.new_order_amount) }}</td>
                    <td class="px-2 py-2 text-center">¥{{ cancelForm.new_order_paid_amount.toFixed(2) }}</td>
                    <td class="px-2 py-2 text-center text-success">¥{{ cancelForm.new_order_rebate_used.toFixed(2) }}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <!-- 分配平衡提示 -->
            <div class="p-2 rounded text-center text-xs font-semibold" :class="Math.abs(cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used - cancelPreviewData.new_order_amount) < 0.01 ? 'bg-success-subtle text-success' : 'bg-error-subtle text-error'">
              {{ Math.abs(cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used - cancelPreviewData.new_order_amount) < 0.01 ? '分配正确' : '分配不平衡：合计 ¥' + (cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used).toFixed(2) + ' / 需要 ¥' + cancelPreviewData.new_order_amount.toFixed(2) }}
            </div>
          </div>

          <!-- 第3步：退款方式 -->
          <div v-show="(cancelStepCount === 3 && cancelStep === 3) || (cancelStepCount === 1 && !cancelPreviewData?.is_partial)" class="space-y-4">
            <div class="text-center mb-2">
              <div class="text-sm font-semibold text-foreground">退还金额确认</div>
              <div class="text-xs text-muted mt-1">确认退款金额和退款方式</div>
            </div>
            <div class="p-4 bg-orange-subtle rounded-lg">
              <div class="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label class="label text-xs font-semibold">退款金额</label>
                  <input v-model.number="cancelForm.refund_amount" type="number" step="0.01" min="0" :max="cancelPreviewData.paid_amount" class="input text-sm py-1.5">
                </div>
                <div>
                  <label class="label text-xs font-semibold">退返利金额</label>
                  <input v-model.number="cancelForm.refund_rebate" type="number" step="0.01" min="0" :max="cancelPreviewData.rebate_used" class="input text-sm py-1.5">
                </div>
              </div>
              <div v-if="cancelForm.refund_amount > 0" class="pt-3 border-t border-warning">
                <label class="label text-xs font-semibold mb-2">退款方式</label>
                <div class="flex gap-4">
                  <label class="flex items-center gap-2 text-sm cursor-pointer p-2 rounded-lg border transition-all" :class="cancelForm.refund_method === 'balance' ? 'border-primary bg-info-subtle' : 'border-line-strong'">
                    <input type="radio" v-model="cancelForm.refund_method" value="balance" class="accent-primary"> 转入客户余额
                  </label>
                  <label class="flex items-center gap-2 text-sm cursor-pointer p-2 rounded-lg border transition-all" :class="cancelForm.refund_method === 'cash' ? 'border-primary bg-info-subtle' : 'border-line-strong'">
                    <input type="radio" v-model="cancelForm.refund_method" value="cash" class="accent-primary"> 现金退款
                  </label>
                </div>
              </div>
            </div>
          </div>

          <!-- 导航按钮 -->
          <div class="flex gap-3 pt-4 mt-4 border-t">
            <button v-if="cancelStep > 1" @click="prevCancelStep" class="btn btn-secondary flex-1">&larr; 上一步</button>
            <button v-else @click="showCancelModal = false" class="btn btn-secondary flex-1">取消</button>
            <button v-if="cancelStep < cancelStepCount" @click="nextCancelStep" class="btn btn-primary flex-1">下一步 &rarr;</button>
            <button v-else @click="confirmCancel" class="btn flex-1" style="background:#ff3b30;color:#fff">确认取消订单</button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
  </div>
</template>

<script setup>
/**
 * 订单明细 Tab
 * 包含订单列表（筛选/排序/导出）+ 订单详情弹窗 + 取消订单向导
 */
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import { useSort } from '../../../composables/useSort'
import { usePagination } from '../../../composables/usePagination'
import { useColumnConfig } from '../../../composables/useColumnConfig'
import { getAllOrders, exportOrders, getOrderItems } from '../../../api/finance'
import { getAccountSets } from '../../../api/accounting'
import { getOrder, cancelOrder, cancelPreview, createOrder } from '../../../api/orders'
import { getLocations } from '../../../api/warehouses'
import { orderTypeNames, orderTypeBadges, shipmentStatusBadges, shippingStatusNames, shippingStatusBadges } from '../../../utils/constants'
import StatusBadge from '../../common/StatusBadge.vue'
import { RotateCcw, Search } from 'lucide-vue-next'
import ColumnMenu from '../../common/ColumnMenu.vue'
import PageToolbar from '../../common/PageToolbar.vue'
import DateRangePicker from '../../common/DateRangePicker.vue'
import SegmentedControl from '../../common/SegmentedControl.vue'

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
const settingsStore = useSettingsStore()

// --- Composables ---
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()
const { sortState: orderSort, toggleSort: toggleOrderSort, genericSort: genericSortOrder } = useSort()
const { page, pageSize, total, totalPages, hasPagination, paginationParams, resetPage, prevPage, nextPage } = usePagination(50)

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
  salesperson: { label: '业务员', defaultVisible: true },
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
    try { const { data } = await getOrderItems(orderId); expandedItems[orderId] = data }
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
      try { const { data } = await getOrderItems(o.id); expandedItems[o.id] = data }
      catch (err) { console.error(err) }
      finally { loadingItems[o.id] = false }
    }
  }))
}

watch(financeViewMode, (mode) => {
  if (mode === 'detail') loadAllItems()
})

/** 解析 SN 码 JSON 字符串为数组 */
const parseSN = (raw) => {
  if (!raw) return []
  try { return JSON.parse(raw) } catch { return raw.split(',').map(s => s.trim()).filter(Boolean) }
}

// --- 收款方式列表（用于详情弹窗内显示名称） ---
const paymentMethods = computed(() => settingsStore.paymentMethods)

// ===== 本地状态 =====
/** 移动端日期预设选中值 */
const orderDatePreset = ref('')

/** 订单筛选条件 */
const orderFilter = reactive({ type: '', payment_status: '', start: '', end: '', search: '', account_set_id: '' })
/** 账套列表 */
const accountSets = ref([])

/** 全部订单数据 */
const allOrders = ref([])

/** 订单详情弹窗可见性 */
const showOrderDetailModal = ref(false)
/** 订单详情数据 */
const orderDetail = reactive({})

// --- 退货相关状态 ---
/** 是否显示退货表单 */
const showReturnForm = ref(false)
/** 退货表单数据 */
const returnForm = reactive({
  items: [],
  refunded: false,
})
/** 退货提交中 */
const returnSubmitting = ref(false)

// --- 取消订单相关状态 ---
/** 取消弹窗可见性 */
const showCancelModal = ref(false)
/** 取消向导当前步骤 */
const cancelStep = ref(1)
/** 取消预览数据 */
const cancelPreviewData = ref(null)
/** 取消表单数据 */
const cancelForm = reactive({
  new_order_paid_amount: 0,
  new_order_rebate_used: 0,
  item_allocations: [],
  refund_amount: 0,
  refund_rebate: 0,
  refund_method: 'balance',
  refund_payment_method: 'cash'
})

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
    salesperson: o => (o.salesperson_name || '').toLowerCase(),
    creator: o => (o.creator_name || '').toLowerCase(),
    time: o => o.created_at || ''
  })
})

/** 取消向导总步数 */
const cancelStepCount = computed(() => {
  const preview = cancelPreviewData.value
  if (!preview) return 1
  if (preview.order_type === 'CONSIGN_OUT') return 0
  const hasPaid = preview.paid_amount > 0 || preview.rebate_used > 0
  if (!preview.is_partial && !hasPaid) return 0
  if (!preview.is_partial && hasPaid) return 1
  if (preview.is_partial && !hasPaid) return 1
  return 3
})

/** 当前订单是否可发起退货 */
const canReturn = computed(() => {
  if (!orderDetail.order_type) return false
  if (!['CASH', 'CREDIT'].includes(orderDetail.order_type)) return false
  if (orderDetail.shipping_status === 'cancelled') return false
  return orderDetail.items?.some(i => i.available_return_quantity > 0)
})

/** 退货表单是否可提交 */
const canSubmitReturn = computed(() => {
  return returnForm.items.some(i => i.qty > 0)
})

// ===== 辅助函数 =====
/** 获取订单付款状态徽标 */
const getOrderPayStatus = (o) => {
  if (o.shipping_status === 'cancelled') return { text: '已取消', badge: 'badge badge-gray' }
  if (!o.is_cleared) return { text: '未结清', badge: 'badge badge-red' }
  if (o.has_unconfirmed_payment) return { text: '待确认', badge: 'badge badge-orange' }
  return { text: '已结清', badge: 'badge badge-green' }
}

/** 根据 code 获取收款方式名称 */
const getPaymentMethodName = (m) => {
  const found = paymentMethods.value.find(p => p.code === m)
  if (found) return found.name
  return { cash: '现金', bank: '银行转账', bank_public: '对公转账', bank_private: '对私转账', wechat: '微信', alipay: '支付宝' }[m] || m
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
const viewOrder = async (id) => {
  try {
    const { data } = await getOrder(id)
    Object.keys(orderDetail).forEach(k => delete orderDetail[k])
    Object.assign(orderDetail, data)
    showOrderDetailModal.value = true
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
  }
}

// ===== 销售退货 =====
/** 打开退货表单 */
const openReturnForm = () => {
  returnForm.items = orderDetail.items
    .filter(i => i.available_return_quantity > 0)
    .map(i => ({
      product_id: i.product_id,
      product_name: i.product_name,
      product_sku: i.product_sku,
      unit_price: i.unit_price,
      cost_price: i.cost_price,
      max_qty: i.available_return_quantity,
      qty: 0
    }))
  returnForm.refunded = false
  showReturnForm.value = true
}

/** 提交退货 */
const submitReturn = async () => {
  const items = returnForm.items.filter(i => i.qty > 0)
  if (!items.length) {
    appStore.showToast('请至少选择一件退货商品', 'error')
    return
  }
  for (const item of items) {
    if (item.qty > item.max_qty) {
      appStore.showToast(`${item.product_name} 最多可退 ${item.max_qty} 件`, 'error')
      return
    }
  }

  returnSubmitting.value = true
  try {
    const warehouseId = orderDetail.warehouse?.id
    if (!warehouseId) {
      appStore.showToast('原订单无仓库信息，无法退货', 'error')
      returnSubmitting.value = false
      return
    }
    let locationId = null
    try {
      const { data: locs } = await getLocations({ warehouse_id: warehouseId })
      if (locs.length) locationId = locs[0].id
    } catch (e) {
      console.warn('获取仓位失败:', e)
    }

    await createOrder({
      order_type: 'RETURN',
      customer_id: orderDetail.customer?.id,
      warehouse_id: warehouseId,
      related_order_id: orderDetail.id,
      refunded: returnForm.refunded,
      items: items.map(i => ({
        product_id: i.product_id,
        quantity: i.qty,
        unit_price: i.unit_price,
        warehouse_id: warehouseId,
        location_id: locationId,
      }))
    })

    appStore.showToast('退货单创建成功')
    showReturnForm.value = false
    showOrderDetailModal.value = false
    loadOrders()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '退货失败', 'error')
  } finally {
    returnSubmitting.value = false
  }
}

/** 取消退货表单 */
const cancelReturnForm = () => {
  showReturnForm.value = false
}

// ===== 取消订单 =====
/** 发起取消订单——先获取预览数据 */
const handleCancelOrder = async (orderId) => {
  try {
    const { data } = await cancelPreview(orderId)
    cancelPreviewData.value = data
    const hasPaid = data.paid_amount > 0 || data.rebate_used > 0

    if (data.order_type === 'CONSIGN_OUT' || (!data.is_partial && !hasPaid)) {
      const confirmed = await appStore.customConfirm('确认取消', `确认取消订单 ${data.order_no}？`)
      if (!confirmed) return
      cancelForm.refund_amount = 0
      cancelForm.refund_rebate = 0
      cancelForm.refund_method = 'balance'
      cancelForm.refund_payment_method = 'cash'
      cancelForm.new_order_paid_amount = 0
      cancelForm.new_order_rebate_used = 0
      cancelForm.item_allocations = []
      await confirmCancel()
      return
    }

    cancelForm.new_order_paid_amount = data.default_new_paid
    cancelForm.new_order_rebate_used = data.default_new_rebate
    cancelForm.item_allocations = (data.shipped_items || []).map(si => ({
      order_item_id: si.order_item_id,
      product_name: si.product_name,
      product_sku: si.product_sku,
      shipped_qty: si.shipped_qty,
      amount: si.amount,
      paid: si.default_paid || si.amount,
      rebate: si.default_rebate || 0
    }))
    cancelForm.refund_amount = data.default_refund
    cancelForm.refund_rebate = data.default_refund_rebate
    cancelForm.refund_method = 'balance'
    cancelForm.refund_payment_method = 'cash'
    cancelStep.value = 1
    showCancelModal.value = true
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '获取取消预览失败', 'error')
  }
}

/** 逐商品现金分配变更回调 */
const onItemPaidChange = (index) => {
  const item = cancelForm.item_allocations[index]
  let paid = Math.max(0, Math.min(item.paid, item.amount))
  item.paid = paid
  item.rebate = +(item.amount - paid).toFixed(2)
  recalcCancelTotals()
}

/** 逐商品返利分配变更回调 */
const onItemRebateChange = (index) => {
  const item = cancelForm.item_allocations[index]
  let rebate = Math.max(0, Math.min(item.rebate, item.amount))
  item.rebate = rebate
  item.paid = +(item.amount - rebate).toFixed(2)
  recalcCancelTotals()
}

/** 重新计算取消合计金额 */
const recalcCancelTotals = () => {
  const preview = cancelPreviewData.value
  if (!preview) return
  const totalPaid = Math.round(cancelForm.item_allocations.reduce((s, i) => s + i.paid, 0) * 100) / 100
  const totalRebate = Math.round(cancelForm.item_allocations.reduce((s, i) => s + i.rebate, 0) * 100) / 100
  cancelForm.new_order_paid_amount = +totalPaid.toFixed(2)
  cancelForm.new_order_rebate_used = +totalRebate.toFixed(2)
  cancelForm.refund_amount = +(preview.paid_amount - cancelForm.new_order_paid_amount).toFixed(2)
  cancelForm.refund_rebate = +(preview.rebate_used - cancelForm.new_order_rebate_used).toFixed(2)
}

/** 取消向导下一步 */
const nextCancelStep = () => {
  const preview = cancelPreviewData.value
  if (!preview) return
  const steps = cancelStepCount.value

  if (steps === 1) {
    confirmCancel()
    return
  }

  if (cancelStep.value === 1) {
    cancelStep.value = 2
  } else if (cancelStep.value === 2) {
    const sum = cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used
    if (Math.abs(sum - preview.new_order_amount) > 0.01) {
      appStore.showToast('付款 + 返利必须等于新订单金额 ¥' + preview.new_order_amount.toFixed(2), 'error')
      return
    }
    cancelStep.value = 3
  }
}

/** 取消向导上一步 */
const prevCancelStep = () => {
  if (cancelStep.value === 3) {
    cancelStep.value = 2
  } else if (cancelStep.value === 2) {
    cancelStep.value = 1
  }
}

/** 确认取消订单——提交到后端 */
const confirmCancel = async () => {
  if (appStore.submitting) return
  const preview = cancelPreviewData.value
  if (!preview) return

  // 部分取消时校验分配平衡
  if (preview.is_partial) {
    const sum = cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used
    if (Math.abs(sum - preview.new_order_amount) > 0.01) {
      appStore.showToast('付款 + 返利必须等于新订单金额 ¥' + preview.new_order_amount.toFixed(2), 'error')
      return
    }
  }

  appStore.submitting = true
  try {
    const payload = {
      refund_amount: cancelForm.refund_amount,
      refund_rebate: cancelForm.refund_rebate,
      refund_method: cancelForm.refund_method,
      refund_payment_method: cancelForm.refund_payment_method
    }
    if (preview.is_partial) {
      payload.new_order_paid_amount = cancelForm.new_order_paid_amount
      payload.new_order_rebate_used = cancelForm.new_order_rebate_used
      payload.item_allocations = cancelForm.item_allocations.map(a => ({
        order_item_id: a.order_item_id,
        paid_amount: a.paid,
        rebate_amount: a.rebate
      }))
    }
    const { data } = await cancelOrder(preview.order_id, payload)
    appStore.showToast(data.message)
    showCancelModal.value = false
    showOrderDetailModal.value = false
    loadOrders()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '取消失败', 'error')
  } finally {
    appStore.submitting = false
  }
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
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '订单明细_' + new Date().toISOString().slice(0, 19).replace(/:/g, '') + '.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
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
  try { const res = await getAccountSets(); accountSets.value = res.data || [] } catch {}
  // 激活时加载订单
  if (props.active) loadOrders()
})
</script>
