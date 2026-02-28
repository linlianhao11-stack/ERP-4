<template>
  <div>
    <!-- ============ Orders view ============ -->
    <div v-if="tab === 'orders'" class="card">
      <div class="p-3 border-b flex flex-col gap-2">
        <!-- Row 1: type filter + date + buttons -->
        <div class="flex items-center gap-2 justify-between">
          <div class="flex items-center gap-1 flex-1 min-w-0">
            <select v-model="orderFilter.type" @change="loadOrders" class="input w-auto text-sm" style="flex-shrink:0">
              <option value="">全部类型</option>
              <option value="CASH">现款</option>
              <option value="CREDIT">账期</option>
              <option value="CONSIGN_OUT">寄售调拨</option>
              <option value="CONSIGN_SETTLE">寄售结算</option>
              <option value="RETURN">退货</option>
            </select>
            <select v-if="accountSets.length" v-model="orderFilter.account_set_id" @change="loadOrders" class="input w-auto text-sm" style="flex-shrink:0">
              <option value="">全部账套</option>
              <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
            <!-- Desktop date inputs -->
            <input v-model="orderFilter.start" @change="loadOrders" type="date" class="input w-auto text-sm hidden md:block">
            <input v-model="orderFilter.end" @change="loadOrders" type="date" class="input w-auto text-sm hidden md:block">
            <!-- Mobile date presets -->
            <div class="flex gap-1 md:hidden">
              <span @click="setOrderDatePreset('')" :class="['tab', !orderDatePreset ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">全部</span>
              <span @click="setOrderDatePreset('today')" :class="['tab', orderDatePreset === 'today' ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">今天</span>
              <span @click="setOrderDatePreset('week')" :class="['tab', orderDatePreset === 'week' ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">本周</span>
              <span @click="setOrderDatePreset('month')" :class="['tab', orderDatePreset === 'month' ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">本月</span>
              <span @click="setOrderDatePreset('custom')" :class="['tab', orderDatePreset === 'custom' ? 'active' : '']" style="padding:6px 8px;font-size:12px;min-height:auto">自定义</span>
            </div>
          </div>
          <button v-if="hasPermission('finance')" @click="openPaymentModal" class="btn btn-success btn-sm hidden md:block">收款</button>
          <button @click="handleExportOrders" class="btn btn-primary btn-sm hidden md:block">导出Excel</button>
        </div>
        <!-- Row 2: search -->
        <input v-model="orderFilter.search" @input="debouncedLoadOrders" class="input w-full md:w-auto text-sm" placeholder="搜索订单号/客户/SN码/快递单号">
      </div>
      <!-- Mobile custom date expand -->
      <div v-if="orderDatePreset === 'custom'" class="px-3 pb-3 flex gap-2 md:hidden">
        <input v-model="orderFilter.start" @change="loadOrders" type="date" class="input input-sm flex-1">
        <input v-model="orderFilter.end" @change="loadOrders" type="date" class="input input-sm flex-1">
      </div>
      <!-- Desktop table -->
      <div class="overflow-x-auto table-container hidden md:block">
        <table class="w-full text-sm">
          <thead class="bg-[#f5f5f7]">
            <tr>
              <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleOrderSort('order_no')">订单号 <span v-if="orderSort.key === 'order_no'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleOrderSort('order_type')">类型 <span v-if="orderSort.key === 'order_type'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleOrderSort('customer')">客户 <span v-if="orderSort.key === 'customer'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th class="px-2 py-2 text-left">关联订单</th>
              <th class="px-2 py-2 text-right cursor-pointer select-none hover:text-[#0071e3]" @click="toggleOrderSort('amount')">金额 <span v-if="orderSort.key === 'amount'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th class="px-2 py-2 text-right cursor-pointer select-none hover:text-[#0071e3]" v-if="hasPermission('finance')" @click="toggleOrderSort('profit')">毛利 <span v-if="orderSort.key === 'profit'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th class="px-2 py-2 text-center cursor-pointer select-none hover:text-[#0071e3]" @click="toggleOrderSort('status')">状态 <span v-if="orderSort.key === 'status'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th class="px-2 py-2 text-center">发货</th>
              <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleOrderSort('salesperson')">销售员 <span v-if="orderSort.key === 'salesperson'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleOrderSort('creator')">操作人 <span v-if="orderSort.key === 'creator'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleOrderSort('time')">时间 <span v-if="orderSort.key === 'time'" class="text-[#0071e3]">{{ orderSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="o in sortedOrders" :key="o.id" class="clickable-row" @click="viewOrder(o.id)">
              <td class="px-2 py-2 font-mono text-xs text-[#0071e3]">{{ o.order_no }}</td>
              <td class="px-2 py-2"><StatusBadge type="orderType" :status="o.order_type" /></td>
              <td class="px-2 py-2">{{ o.customer_name || '-' }}</td>
              <td class="px-2 py-2">
                <span v-if="o.related_order_no" @click.stop="viewOrder(o.related_order_id)" class="text-[#0071e3] hover:underline cursor-pointer font-mono text-xs">{{ o.related_order_no }}</span>
                <span v-else class="text-[#86868b]">-</span>
              </td>
              <td class="px-2 py-2 text-right font-semibold">¥{{ fmt(o.total_amount) }}</td>
              <td class="px-2 py-2 text-right" v-if="hasPermission('finance')" :class="o.total_profit >= 0 ? 'text-[#34c759]' : 'text-[#ff3b30]'">{{ fmt(o.total_profit) }}</td>
              <td class="px-2 py-2 text-center"><span :class="getOrderPayStatus(o).badge">{{ getOrderPayStatus(o).text }}</span></td>
              <td class="px-2 py-2 text-center"><span v-if="o.shipping_status && o.shipping_status !== 'completed'" :class="shippingStatusBadges[o.shipping_status]">{{ shippingStatusNames[o.shipping_status] }}</span><span v-else class="text-xs text-[#86868b]">-</span></td>
              <td class="px-2 py-2 text-[#86868b]">{{ o.salesperson_name || '-' }}</td>
              <td class="px-2 py-2 text-[#86868b]">{{ o.creator_name }}</td>
              <td class="px-2 py-2 text-[#86868b] text-xs">{{ fmtDate(o.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!allOrders.length" class="p-6 text-center text-[#86868b] text-sm">暂无订单</div>
      </div>
      <!-- Mobile card list -->
      <div class="md:hidden divide-y">
        <div v-for="o in sortedOrders" :key="'m-' + o.id" @click="viewOrder(o.id)" class="p-3 cursor-pointer active:bg-[#f5f5f7]">
          <div class="flex justify-between items-center mb-1.5">
            <span class="font-mono text-xs text-[#0071e3] font-semibold">{{ o.order_no }}</span>
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
              <span class="text-xs text-[#86868b]">{{ fmtDate(o.created_at) }}</span>
            </div>
          </div>
        </div>
        <div v-if="!allOrders.length" class="p-6 text-center text-[#86868b] text-sm">暂无订单</div>
      </div>
    </div>

    <!-- ============ Unpaid view ============ -->
    <div v-if="tab === 'unpaid'">
      <div class="card mb-2 p-3">
        <select v-model="financeCustomerId" @change="loadUnpaid" class="input text-sm">
          <option value="">全部客户</option>
          <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }} ({{ getBalanceLabel(c.balance) }} ¥{{ formatBalance(c.balance) }})</option>
        </select>
      </div>
      <!-- Mobile cards -->
      <div class="md:hidden space-y-2">
        <div v-for="o in unpaidOrders" :key="o.id" class="card p-3 flex justify-between items-center cursor-pointer" @click="viewOrder(o.id)">
          <div class="min-w-0 flex-1 mr-3">
            <div class="font-medium truncate">{{ o.customer_name }}</div>
            <div class="text-xs text-[#86868b] truncate">{{ o.order_no }} · <span :class="orderTypeBadges[o.order_type]">{{ orderTypeNames[o.order_type] }}</span></div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="text-lg font-bold text-[#ff3b30]">¥{{ fmt(o.unpaid_amount) }}</div>
            <div class="text-xs text-[#86868b]">{{ fmtDate(o.created_at) }}</div>
          </div>
        </div>
        <div v-if="!unpaidOrders.length" class="p-8 text-center text-[#86868b] text-sm">暂无欠款</div>
      </div>
      <!-- Desktop table -->
      <div class="card hidden md:block">
        <div class="table-container">
          <table class="w-full text-sm">
            <thead class="bg-[#f5f5f7]">
              <tr>
                <th class="px-3 py-2 text-left">订单号</th>
                <th class="px-3 py-2 text-left">客户</th>
                <th class="px-3 py-2 text-center">类型</th>
                <th class="px-3 py-2 text-right">订单金额</th>
                <th class="px-3 py-2 text-right">欠款金额</th>
                <th class="px-3 py-2 text-left">创建时间</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr v-for="o in unpaidOrders" :key="o.id" class="hover:bg-[#f5f5f7] cursor-pointer" @click="viewOrder(o.id)">
                <td class="px-3 py-2 font-mono text-sm text-[#0071e3]">{{ o.order_no }}</td>
                <td class="px-3 py-2">{{ o.customer_name }}</td>
                <td class="px-3 py-2 text-center"><StatusBadge type="orderType" :status="o.order_type" /></td>
                <td class="px-3 py-2 text-right">¥{{ fmt(o.total_amount) }}</td>
                <td class="px-3 py-2 text-right font-semibold text-[#ff3b30]">¥{{ fmt(o.unpaid_amount) }}</td>
                <td class="px-3 py-2 text-[#86868b] text-xs">{{ fmtDate(o.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!unpaidOrders.length" class="p-8 text-center text-[#86868b] text-sm">暂无欠款</div>
      </div>
    </div>

    <!-- ============ Modal: Order Detail ============ -->
    <div v-if="showOrderDetailModal" class="modal-overlay" @click.self="showOrderDetailModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="font-semibold">订单详情</h3>
          <button @click="showOrderDetailModal = false" class="text-[#86868b] hover:text-[#6e6e73] text-xl">&times;</button>
        </div>
        <div class="modal-body" v-if="orderDetail.order_no">
          <div class="mb-4 p-3 bg-[#f5f5f7] rounded-lg">
            <div class="flex justify-between items-start mb-2">
              <div>
                <div class="font-semibold">{{ orderDetail.order_no }}</div>
                <div class="text-sm text-[#86868b]">
                  <span v-if="orderDetail.salesperson_name">销售员: {{ orderDetail.salesperson_name }} · </span>
                  {{ orderDetail.creator_name }} · {{ fmtDate(orderDetail.created_at) }}
                </div>
              </div>
              <StatusBadge type="orderType" :status="orderDetail.order_type" />
            </div>
            <div class="grid detail-grid grid-cols-2 gap-2 text-sm">
              <div><span class="text-[#86868b]">客户:</span> {{ orderDetail.customer?.name || '-' }}</div>
              <div><span class="text-[#86868b]">仓库:</span> {{ orderDetail.warehouse?.name || '-' }}</div>
              <div v-if="orderDetail.related_order" class="col-span-2">
                <span class="text-[#86868b]">关联原订单:</span>
                <span @click="viewOrder(orderDetail.related_order.id)" class="text-[#0071e3] hover:underline cursor-pointer font-mono">{{ orderDetail.related_order.order_no }}</span>
              </div>
              <div v-if="orderDetail.related_children?.length" class="col-span-2">
                <span class="text-[#86868b]">拆分订单:</span>
                <span v-for="child in orderDetail.related_children" :key="child.id" @click="viewOrder(child.id)" class="text-[#0071e3] hover:underline cursor-pointer font-mono ml-1">{{ child.order_no }}</span>
              </div>
              <div><span class="text-[#86868b]">金额:</span> <span class="font-semibold">¥{{ fmt(orderDetail.total_amount) }}</span></div>
              <div v-if="hasPermission('finance')"><span class="text-[#86868b]">毛利:</span> <span :class="orderDetail.total_profit >= 0 ? 'text-[#34c759]' : 'text-[#ff3b30]'">¥{{ fmt(orderDetail.total_profit) }}</span></div>
              <div v-if="orderDetail.rebate_used > 0" class="col-span-2">
                <span class="text-[#86868b]">已使用返利:</span> <span class="text-[#34c759] font-semibold">¥{{ fmt(orderDetail.rebate_used) }}</span>
              </div>
              <div v-if="orderDetail.credit_used > 0" class="col-span-2">
                <span class="text-[#86868b]">已使用在账资金:</span> <span class="text-[#0071e3] font-semibold">¥{{ fmt(orderDetail.credit_used) }}</span>
              </div>
              <div v-if="orderDetail.payment_records && orderDetail.payment_records.length" class="col-span-2">
                <div v-for="pr in orderDetail.payment_records" :key="pr.id" class="flex items-center gap-2 text-sm mb-1">
                  <span class="text-[#86868b]">{{ pr.source === 'CASH' ? '销售收款' : pr.source === 'REFUND' ? '退款' : pr.source === 'CREDIT' ? '账期回款' : pr.source === 'CONSIGN_SETTLE' ? '寄售结算' : pr.source || '回款' }}:</span>
                  <span :class="pr.source === 'REFUND' ? 'font-semibold text-[#ff9f0a]' : 'font-semibold text-[#34c759]'">{{ pr.source === 'REFUND' ? '-' : '' }}¥{{ fmt(Math.abs(pr.amount)) }}</span>
                  <span class="badge badge-blue" style="font-size:11px">{{ getPaymentMethodName(pr.payment_method) }}</span>
                  <span v-if="pr.source !== 'REFUND'" :class="pr.is_confirmed ? 'text-[#34c759]' : 'text-[#ff9f0a]'" style="font-size:11px">{{ pr.is_confirmed ? '已确认' : '待确认' }}</span>
                </div>
              </div>
              <div v-else-if="!orderDetail.credit_used"><span class="text-[#86868b]">已付:</span> ¥{{ fmt(orderDetail.paid_amount) }}</div>
              <div><span class="text-[#86868b]">状态:</span> <span :class="orderDetail.is_cleared ? 'text-[#34c759]' : 'text-[#ff3b30]'">{{ orderDetail.is_cleared ? '已结清' : '未结清' }}</span></div>
              <div v-if="orderDetail.shipping_status"><span class="text-[#86868b]">发货:</span> <StatusBadge type="shippingStatus" :status="orderDetail.shipping_status" /></div>
              <div v-if="orderDetail.order_type === 'RETURN'" class="col-span-2">
                <span class="text-[#86868b]">退款状态:</span>
                <span :class="orderDetail.refunded ? 'text-[#ff9f0a]' : 'text-[#d70015]'">{{ orderDetail.refunded ? '已退款给客户' : '形成在账资金' }}</span>
              </div>
              <div v-if="orderDetail.rebate_refund_records?.length" class="col-span-2">
                <div v-for="rr in orderDetail.rebate_refund_records" :key="rr.id" class="flex items-center gap-2 text-sm mb-1">
                  <span class="text-[#86868b]">退回返利:</span>
                  <span class="font-semibold text-[#ff9f0a]">¥{{ fmt(rr.amount) }}</span>
                  <span v-if="rr.remark" class="text-xs text-[#86868b]">{{ rr.remark }}</span>
                </div>
              </div>
              <div v-if="orderDetail.remark" class="col-span-2 pt-2 border-t"><span class="text-[#86868b]">备注:</span> <span class="text-[#6e6e73]">{{ orderDetail.remark }}</span></div>
            </div>
          </div>
          <!-- Shipments -->
          <div v-if="orderDetail.shipments?.length" class="mb-4">
            <div class="font-semibold text-sm mb-2">物流信息 ({{ orderDetail.shipments.length }})</div>
            <div v-for="sh in orderDetail.shipments" :key="sh.id" class="p-3 bg-[#e8f4fd] rounded-lg mb-2">
              <div class="flex justify-between items-center mb-1">
                <div class="text-sm">{{ sh.carrier_name || '未填写' }} <span v-if="sh.tracking_no" class="font-mono text-xs">{{ sh.tracking_no }}</span></div>
                <span :class="['text-xs px-2 py-0.5 rounded-full', shipmentStatusBadges[sh.status] || 'bg-[#f5f5f7] text-[#6e6e73]']">{{ sh.status_text }}</span>
              </div>
              <div v-if="sh.sn_code" class="mt-1 p-1.5 bg-[#e8f8ee] rounded">
                <span class="text-xs text-[#86868b] font-semibold">SN码:</span>
                <span class="text-xs text-[#34c759] font-mono ml-1">{{ sh.sn_code }}</span>
              </div>
              <div v-if="sh.last_info" class="text-xs text-[#86868b] mt-1">{{ sh.last_info }}</div>
            </div>
          </div>
          <!-- Items -->
          <div class="font-semibold mb-2 text-sm">商品明细</div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-[#f5f5f7]">
                <tr>
                  <th class="px-2 py-1 text-left">商品</th>
                  <th class="px-2 py-1 text-right">单价</th>
                  <th class="px-2 py-1 text-right">数量</th>
                  <th v-if="orderDetail.rebate_used > 0" class="px-2 py-1 text-right">返利</th>
                  <th class="px-2 py-1 text-right">金额</th>
                  <th class="px-2 py-1 text-right" v-if="hasPermission('finance')">毛利</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr v-for="item in orderDetail.items" :key="item.product_id">
                  <td class="px-2 py-1"><div>{{ item.product_name }}</div><div class="text-xs text-[#86868b]">{{ item.product_sku }}</div></td>
                  <td class="px-2 py-1 text-right">{{ fmt(item.unit_price) }}</td>
                  <td class="px-2 py-1 text-right">{{ item.quantity }}</td>
                  <td v-if="orderDetail.rebate_used > 0" class="px-2 py-1 text-right text-[#34c759]">{{ item.rebate_amount > 0 ? '-¥' + fmt(item.rebate_amount) : '' }}</td>
                  <td class="px-2 py-1 text-right font-semibold">{{ fmt(item.amount) }}</td>
                  <td class="px-2 py-1 text-right" v-if="hasPermission('finance')" :class="item.profit >= 0 ? 'text-[#34c759]' : 'text-[#ff3b30]'">{{ fmt(item.profit) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="flex gap-3 pt-4">
            <button type="button" @click="showOrderDetailModal = false" class="btn btn-secondary flex-1">关闭</button>
            <button v-if="orderDetail.shipping_status && ['pending', 'partial'].includes(orderDetail.shipping_status)" type="button" @click="handleCancelOrder(orderDetail.id)" class="btn flex-1" style="background:#ff3b30;color:#fff">取消订单</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ Modal: Cancel Order ============ -->
    <teleport to="body">
      <div v-if="showCancelModal && cancelPreviewData" class="modal-overlay" @click.self="showCancelModal = false">
        <div class="modal-content" style="max-width:640px">
          <div class="modal-header">
            <h3 class="font-semibold">取消订单 {{ cancelPreviewData.order_no }}</h3>
            <button @click="showCancelModal = false" class="text-[#86868b] hover:text-[#6e6e73] text-xl">&times;</button>
          </div>
          <div class="modal-body">
            <!-- Step indicator -->
            <div v-if="cancelStepCount > 1" class="flex items-center justify-center gap-2 mb-4">
              <template v-for="s in cancelStepCount" :key="s">
                <div :class="['w-2.5 h-2.5 rounded-full transition-all', cancelStep === s ? 'bg-[#0071e3] scale-125' : (cancelStep > s ? 'bg-[#34c759]' : 'bg-[#d2d2d7]')]"></div>
                <div v-if="s < cancelStepCount" class="w-6 h-0.5" :class="cancelStep > s ? 'bg-[#34c759]' : 'bg-[#d2d2d7]'"></div>
              </template>
            </div>

            <!-- Step 1: 确认商品 -->
            <div v-show="cancelStep === 1" class="space-y-4">
              <div v-if="cancelPreviewData.is_partial">
                <div class="flex items-center gap-2 mb-2">
                  <span class="w-5 h-5 rounded-full bg-[#34c759] text-white text-xs flex items-center justify-center font-bold">✓</span>
                  <span class="text-sm font-semibold text-[#1d1d1f]">已发货商品（将生成新订单）</span>
                </div>
                <div class="p-3 bg-[#e8f8ee] rounded-lg border border-[#a8e6c1]">
                  <div v-for="item in cancelPreviewData.shipped_items" :key="'s-'+item.product_sku" class="flex justify-between text-sm py-1">
                    <span class="text-[#1d1d1f]">{{ item.product_name }} <span class="text-[#86868b]">x{{ item.shipped_qty }}</span></span>
                    <span class="font-semibold">¥{{ fmt(item.amount) }}</span>
                  </div>
                  <div class="border-t border-[#a8e6c1] mt-2 pt-2 flex justify-between text-sm font-bold">
                    <span>新订单金额</span>
                    <span class="text-[#34c759]">¥{{ fmt(cancelPreviewData.new_order_amount) }}</span>
                  </div>
                </div>
              </div>

              <div>
                <div class="flex items-center gap-2 mb-2">
                  <span class="w-5 h-5 rounded-full bg-[#ff3b30] text-white text-xs flex items-center justify-center font-bold">✕</span>
                  <span class="text-sm font-semibold text-[#1d1d1f]">取消商品（释放库存预留）</span>
                </div>
                <div class="p-3 bg-[#fee2e2] rounded-lg border border-[#fca5a5]">
                  <div v-for="item in cancelPreviewData.cancel_items" :key="'c-'+item.product_sku" class="flex justify-between text-sm py-1">
                    <span class="text-[#1d1d1f]">{{ item.product_name }} <span class="text-[#86868b]">x{{ item.cancel_qty }}</span></span>
                    <span>¥{{ fmt(item.amount) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Step 2: 逐商品财务分配（部分取消时） -->
            <div v-show="cancelStep === 2" class="space-y-4">
              <div class="text-center mb-2">
                <div class="text-sm font-semibold text-[#1d1d1f]">新订单逐商品财务分配</div>
                <div class="text-xs text-[#86868b] mt-1">每个商品的现金+返利必须等于商品金额，影响开票单价</div>
              </div>
              <div class="text-xs text-[#86868b] p-2 bg-[#f5f5f7] rounded">
                原订单：付款 <span class="font-semibold text-[#1d1d1f]">¥{{ fmt(cancelPreviewData.paid_amount) }}</span>
                + 返利 <span class="font-semibold text-[#34c759]">¥{{ fmt(cancelPreviewData.rebate_used) }}</span>
                = ¥{{ fmt(cancelPreviewData.total_amount) }}
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-sm">
                  <thead class="bg-[#f5f5f7]">
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
                        <div class="text-[10px] text-[#86868b]">{{ alloc.product_sku }}</div>
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
                  <tfoot class="border-t-2 border-[#d2d2d7]">
                    <tr class="font-semibold text-xs">
                      <td class="px-2 py-2" colspan="2">合计</td>
                      <td class="px-2 py-2 text-right">¥{{ fmt(cancelPreviewData.new_order_amount) }}</td>
                      <td class="px-2 py-2 text-center">¥{{ cancelForm.new_order_paid_amount.toFixed(2) }}</td>
                      <td class="px-2 py-2 text-center text-[#34c759]">¥{{ cancelForm.new_order_rebate_used.toFixed(2) }}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              <div class="p-2 rounded text-center text-xs font-semibold" :class="Math.abs(cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used - cancelPreviewData.new_order_amount) < 0.01 ? 'bg-[#e8f8ee] text-[#34c759]' : 'bg-[#fee2e2] text-[#ff3b30]'">
                {{ Math.abs(cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used - cancelPreviewData.new_order_amount) < 0.01 ? '分配正确' : '分配不平衡：合计 ¥' + (cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used).toFixed(2) + ' / 需要 ¥' + cancelPreviewData.new_order_amount.toFixed(2) }}
              </div>
            </div>

            <!-- Step 3: 退款方式 -->
            <div v-show="cancelStep === 3" class="space-y-4">
              <div class="text-center mb-2">
                <div class="text-sm font-semibold text-[#1d1d1f]">退还金额确认</div>
                <div class="text-xs text-[#86868b] mt-1">确认退款金额和退款方式</div>
              </div>
              <div class="p-4 bg-[#fff3e0] rounded-lg">
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
                <div v-if="cancelForm.refund_amount > 0" class="pt-3 border-t border-[#fde68a]">
                  <label class="label text-xs font-semibold mb-2">退款方式</label>
                  <div class="flex gap-4">
                    <label class="flex items-center gap-2 text-sm cursor-pointer p-2 rounded-lg border transition-all" :class="cancelForm.refund_method === 'balance' ? 'border-[#0071e3] bg-[#e8f4fd]' : 'border-[#d2d2d7]'">
                      <input type="radio" v-model="cancelForm.refund_method" value="balance" class="accent-[#0071e3]"> 转入客户余额
                    </label>
                    <label class="flex items-center gap-2 text-sm cursor-pointer p-2 rounded-lg border transition-all" :class="cancelForm.refund_method === 'cash' ? 'border-[#0071e3] bg-[#e8f4fd]' : 'border-[#d2d2d7]'">
                      <input type="radio" v-model="cancelForm.refund_method" value="cash" class="accent-[#0071e3]"> 现金退款
                    </label>
                  </div>
                </div>
              </div>
            </div>

            <!-- Navigation buttons -->
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

    <!-- ============ Modal: Payment ============ -->
    <div v-if="showPaymentModal" class="modal-overlay" @click.self="showPaymentModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="font-semibold">收款</h3>
          <button @click="showPaymentModal = false" class="text-[#86868b] hover:text-[#6e6e73] text-xl">&times;</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="savePayment" class="space-y-3">
            <div>
              <label class="label">客户 *</label>
              <select v-model="paymentForm.customer_id" @change="loadCustomerUnpaid" class="input" required>
                <option value="">选择客户</option>
                <option v-for="c in customers.filter(x => x.balance > 0)" :key="c.id" :value="c.id">{{ c.name }} (欠款 ¥{{ formatBalance(c.balance) }})</option>
              </select>
            </div>
            <div v-if="customerUnpaidOrders.length">
              <label class="label">核销订单</label>
              <div class="space-y-1 max-h-36 overflow-y-auto border rounded p-2">
                <label v-for="o in customerUnpaidOrders" :key="o.id" class="flex items-center p-2 hover:bg-[#f5f5f7] rounded cursor-pointer text-sm">
                  <input type="checkbox" v-model="paymentForm.order_ids" :value="o.id" class="mr-2">
                  <span class="flex-1">{{ o.order_no }}</span>
                  <span class="text-[#ff3b30] font-semibold">¥{{ fmt(o.unpaid_amount) }}</span>
                </label>
              </div>
            </div>
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">金额 *</label>
                <input v-model.number="paymentForm.amount" type="number" step="0.01" class="input" required>
              </div>
              <div>
                <label class="label">方式</label>
                <select v-model="paymentForm.payment_method" class="input">
                  <option v-for="pm in paymentMethods" :key="pm.code" :value="pm.code">{{ pm.name }}</option>
                </select>
              </div>
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="showPaymentModal = false" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-success flex-1">确认收款</button>
            </div>
          </form>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { useAppStore } from '../../stores/app'
import { useCustomersStore } from '../../stores/customers'
import { useSettingsStore } from '../../stores/settings'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { useSort } from '../../composables/useSort'
import { getAllOrders, exportOrders, getUnpaidOrders, createPayment } from '../../api/finance'
import { getAccountSets } from '../../api/accounting'
import { getOrder, cancelOrder, cancelPreview } from '../../api/orders'
import { orderTypeNames, orderTypeBadges, shipmentStatusBadges, shippingStatusNames, shippingStatusBadges } from '../../utils/constants'
import StatusBadge from '../common/StatusBadge.vue'

const props = defineProps({
  tab: { type: String, default: 'orders' }
})

const emit = defineEmits(['data-changed'])

// Stores
const authStore = useAuthStore()
const appStore = useAppStore()
const customersStore = useCustomersStore()
const settingsStore = useSettingsStore()

// Composables
const { fmt, fmtDate, formatBalance, getBalanceLabel, fmtMoney } = useFormat()
const { hasPermission } = usePermission()
const { sortState: orderSort, toggleSort: toggleOrderSort, genericSort: genericSortOrder } = useSort()

// Aliases
const customers = computed(() => customersStore.customers)
const paymentMethods = computed(() => settingsStore.paymentMethods)

// ===== Local State =====
const submitting = ref(false)
const financeCustomerId = ref('')
const orderDatePreset = ref('')

// Order filter
const orderFilter = reactive({ type: '', start: '', end: '', search: '', account_set_id: '' })
const accountSets = ref([])

// Data lists
const allOrders = ref([])
const unpaidOrders = ref([])
const customerUnpaidOrders = ref([])

// Modal visibility
const showOrderDetailModal = ref(false)
const showPaymentModal = ref(false)
// Modal data
const orderDetail = reactive({})

// Payment form
const paymentForm = reactive({ customer_id: '', order_ids: [], amount: 0, payment_method: 'cash' })

// Cancel order
const showCancelModal = ref(false)
const cancelStep = ref(1)
const cancelPreviewData = ref(null)
const cancelForm = reactive({
  new_order_paid_amount: 0,
  new_order_rebate_used: 0,
  item_allocations: [],
  refund_amount: 0,
  refund_rebate: 0,
  refund_method: 'balance',
  refund_payment_method: 'cash'
})

// ===== Computed =====
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

const cancelStepCount = computed(() => {
  const preview = cancelPreviewData.value
  if (!preview) return 1
  if (preview.order_type === 'CONSIGN_OUT') return 1
  if (preview.is_partial && (preview.paid_amount > 0 || preview.rebate_used > 0)) return 3
  return 2
})

// ===== Helper functions =====
const getOrderPayStatus = (o) => {
  if (!o.is_cleared) return { text: '未结清', badge: 'badge badge-red' }
  if (o.has_unconfirmed_payment) return { text: '待确认', badge: 'badge badge-orange' }
  return { text: '已结清', badge: 'badge badge-green' }
}

const getPaymentMethodName = (m) => {
  const found = paymentMethods.value.find(p => p.code === m)
  if (found) return found.name
  return { cash: '现金', bank: '银行转账', bank_public: '对公转账', bank_private: '对私转账', wechat: '微信', alipay: '支付宝' }[m] || m
}

// ===== Date presets =====
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
  loadOrders()
}

// ===== Data loading =====
const loadOrders = async () => {
  try {
    const params = {}
    if (orderFilter.type) params.order_type = orderFilter.type
    if (orderFilter.start) params.start_date = orderFilter.start
    if (orderFilter.end) params.end_date = orderFilter.end
    if (orderFilter.search) params.search = orderFilter.search
    if (orderFilter.account_set_id) params.account_set_id = orderFilter.account_set_id
    const { data } = await getAllOrders(params)
    allOrders.value = data.items || data
  } catch (e) {
    console.error('加载订单失败', e)
  }
}

let _searchTimer = null
const debouncedLoadOrders = () => {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(loadOrders, 300)
}
onUnmounted(() => clearTimeout(_searchTimer))

const loadUnpaid = async () => {
  try {
    const p = financeCustomerId.value ? { customer_id: financeCustomerId.value } : {}
    const { data } = await getUnpaidOrders(p)
    unpaidOrders.value = data
  } catch (e) {
    console.error(e)
  }
}

const loadCustomerUnpaid = async () => {
  if (!paymentForm.customer_id) {
    customerUnpaidOrders.value = []
    return
  }
  try {
    const { data } = await getUnpaidOrders({ customer_id: paymentForm.customer_id })
    customerUnpaidOrders.value = data
    paymentForm.amount = data.reduce((s, o) => s + o.unpaid_amount, 0)
  } catch (e) {
    console.error(e)
  }
}

// ===== Order detail =====
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

// ===== Cancel order =====
const handleCancelOrder = async (orderId) => {
  try {
    const { data } = await cancelPreview(orderId)
    cancelPreviewData.value = data
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

const onItemPaidChange = (index) => {
  const item = cancelForm.item_allocations[index]
  let paid = Math.max(0, Math.min(item.paid, item.amount))
  item.paid = paid
  item.rebate = +(item.amount - paid).toFixed(2)
  recalcCancelTotals()
}

const onItemRebateChange = (index) => {
  const item = cancelForm.item_allocations[index]
  let rebate = Math.max(0, Math.min(item.rebate, item.amount))
  item.rebate = rebate
  item.paid = +(item.amount - rebate).toFixed(2)
  recalcCancelTotals()
}

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

const nextCancelStep = () => {
  const preview = cancelPreviewData.value
  if (!preview) return
  if (cancelStep.value === 1) {
    if (!preview.is_partial || (preview.paid_amount <= 0 && preview.rebate_used <= 0)) {
      if (preview.order_type === 'CONSIGN_OUT') {
        confirmCancel()
        return
      }
      cancelStep.value = 3
    } else {
      cancelStep.value = 2
    }
  } else if (cancelStep.value === 2) {
    const sum = cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used
    if (Math.abs(sum - preview.new_order_amount) > 0.01) {
      appStore.showToast('付款 + 返利必须等于新订单金额 ¥' + preview.new_order_amount.toFixed(2), 'error')
      return
    }
    cancelStep.value = 3
  }
}

const prevCancelStep = () => {
  const preview = cancelPreviewData.value
  if (!preview) return
  if (cancelStep.value === 3) {
    if (preview.is_partial && (preview.paid_amount > 0 || preview.rebate_used > 0)) {
      cancelStep.value = 2
    } else {
      cancelStep.value = 1
    }
  } else if (cancelStep.value === 2) {
    cancelStep.value = 1
  }
}

const confirmCancel = async () => {
  if (appStore.submitting) return
  const preview = cancelPreviewData.value
  if (!preview) return

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

// ===== Export orders =====
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

// ===== Payment =====
const openPaymentModal = () => {
  paymentForm.customer_id = ''
  paymentForm.order_ids = []
  paymentForm.amount = 0
  paymentForm.payment_method = 'cash'
  customerUnpaidOrders.value = []
  showPaymentModal.value = true
}

const savePayment = async () => {
  if (!paymentForm.order_ids.length) {
    appStore.showToast('请选择订单', 'error')
    return
  }
  if (!paymentForm.amount || paymentForm.amount <= 0) {
    appStore.showToast('收款金额必须大于0', 'error')
    return
  }
  const confirmed = await appStore.customConfirm('确认收款', `确认收款 ¥${Number(paymentForm.amount).toFixed(2)} ？`)
  if (!confirmed) return
  if (submitting.value) return
  submitting.value = true
  try {
    await createPayment(paymentForm)
    appStore.showToast('收款成功')
    showPaymentModal.value = false
    loadOrders()
    loadUnpaid()
    customersStore.loadCustomers()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '收款失败', 'error')
  } finally {
    submitting.value = false
  }
}

// ===== Tab change =====
watch(() => props.tab, (val) => {
  if (val === 'orders') loadOrders()
  else if (val === 'unpaid') loadUnpaid()
})

// ===== Refresh methods =====
const refresh = (tabName) => {
  if (tabName === 'orders') loadOrders()
  else if (tabName === 'unpaid') loadUnpaid()
  else {
    loadOrders()
    loadUnpaid()
  }
}

defineExpose({ refresh, viewOrder })

onMounted(async () => {
  try { const res = await getAccountSets(); accountSets.value = res.data || [] } catch {}
  if (props.tab === 'orders') loadOrders()
  else if (props.tab === 'unpaid') loadUnpaid()
})
</script>
