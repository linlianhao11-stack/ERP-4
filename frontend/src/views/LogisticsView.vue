<template>
  <div>
    <!-- Status Filter Tabs -->
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

    <!-- Search -->
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

    <!-- Desktop Table -->
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

    <!-- Mobile Card List -->
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

    <!-- Shipment Detail Modal -->
    <teleport to="body">
      <div v-if="showDetailModal" class="modal-overlay" @click.self="closeDetailModal">
        <div class="modal-content">
          <div class="modal-header">
            <h3 class="font-semibold">物流详情</h3>
            <button @click="closeDetailModal" class="text-[#86868b] hover:text-[#6e6e73]">&times;</button>
          </div>
          <div class="modal-body space-y-4" v-if="shipmentDetail">
            <!-- Order Info -->
            <div class="p-3 bg-[#f5f5f7] rounded-lg">
              <div class="flex justify-between items-center mb-2">
                <div class="font-semibold">订单信息</div>
                <span :class="getShippingBadge(shipmentDetail.order.shipping_status)">{{ getShippingName(shipmentDetail.order.shipping_status) }}</span>
              </div>
              <div class="grid form-grid grid-cols-2 gap-2 text-sm">
                <div>订单号: <span class="font-mono">{{ shipmentDetail.order.order_no }}</span></div>
                <div>类型: <span :class="getOrderTypeBadge(shipmentDetail.order.order_type)">{{ getOrderTypeName(shipmentDetail.order.order_type) }}</span></div>
                <div>客户: {{ shipmentDetail.order.customer_name || '-' }}</div>
                <div>金额: ¥{{ fmt(shipmentDetail.order.total_amount) }}</div>
                <div v-if="shipmentDetail.order.remark" class="col-span-2 pt-1 border-t mt-1">
                  <span class="text-[#86868b]">发货地址/备注:</span>
                  <span class="text-[#6e6e73] font-medium">{{ shipmentDetail.order.remark }}</span>
                </div>
              </div>
              <!-- Order Items with shipping progress -->
              <div v-if="shipmentDetail.order.items?.length" class="mt-2">
                <div class="text-xs text-[#86868b] mb-1">商品明细:</div>
                <div v-for="item in shipmentDetail.order.items" :key="item.id || item.product_sku" class="text-xs text-[#6e6e73] flex justify-between">
                  <span>{{ item.product_name }} x{{ item.quantity }} ¥{{ fmt(item.unit_price) }}</span>
                  <span v-if="item.remaining_qty > 0" class="text-[#ff9f0a]">待发 {{ item.remaining_qty }}</span>
                  <span v-else class="text-[#34c759]">已发完</span>
                </div>
              </div>
            </div>

            <!-- Shipment List Header -->
            <div class="flex justify-between items-center p-3 bg-white border rounded-lg">
              <div class="font-semibold">物流单 ({{ shipmentDetail.shipments?.length || 0 }})</div>
              <div class="flex gap-2">
                <button
                  v-if="shipmentDetail.shipments?.filter(s => s.tracking_no).length"
                  @click="copyAllTracking(shipmentDetail.shipments.filter(s => s.tracking_no).map(s => ({ carrier_name: s.carrier_name, tracking_no: s.tracking_no, sn_code: s.sn_code })))"
                  class="btn btn-secondary btn-sm"
                >复制全部单号</button>
                <button
                  v-if="canShip"
                  @click="openShipForm"
                  class="btn btn-primary btn-sm"
                >发货</button>
                <button
                  v-if="!canShip"
                  @click="openNewShipmentForm"
                  class="btn btn-success btn-sm"
                >+ 添加物流单</button>
              </div>
            </div>

            <!-- Individual Shipments -->
            <div
              v-for="(s, idx) in shipmentDetail.shipments"
              :key="s.id"
              class="p-3 border rounded-lg"
              :class="editingShipmentId === s.id ? 'border-[#b3d7f5] bg-[#e8f4fd]' : 'bg-white'"
            >
              <div class="flex justify-between items-center mb-1">
                <div class="text-sm font-semibold">物流单 #{{ idx + 1 }}</div>
                <span :class="['text-xs px-2 py-0.5 rounded-full', getShipmentStatusBadge(s.status)]">{{ s.status_text }}</span>
              </div>
              <div v-if="s.tracking_no" class="text-sm mb-1">
                {{ s.carrier_name }} <span class="font-mono text-xs">{{ s.tracking_no }}</span>
              </div>
              <div v-else class="text-sm text-[#86868b] mb-1">未填写快递信息</div>
              <div v-if="s.last_info" class="text-xs text-[#86868b] mb-2">{{ s.last_info }}</div>

              <!-- Shipment Items (per-package product detail) -->
              <div v-if="s.items?.length" class="mb-2 p-2 bg-[#f5f5f7] rounded border border-[#e8e8ed]">
                <div class="text-xs text-[#86868b] font-semibold mb-1">发货商品:</div>
                <div v-for="si in s.items" :key="si.product_sku" class="text-xs text-[#6e6e73] flex justify-between">
                  <span>{{ si.product_name }} ({{ si.product_sku }})</span>
                  <span class="font-semibold">x{{ si.quantity }}</span>
                </div>
              </div>

              <!-- SN Code Area -->
              <div class="mb-2 p-2 rounded border" :class="s.sn_code ? 'bg-[#e8f8ee] border-[#a8e6c1]' : 'bg-[#f5f5f7] border-[#d2d2d7]'">
                <div v-if="editingSNId === s.id" class="space-y-1">
                  <label class="text-xs text-[#86868b] font-semibold">
                    SN码 <span class="font-normal text-[#86868b]">(多个用逗号/空格/换行分隔)</span>
                  </label>
                  <textarea v-model="snInput" class="input text-sm py-1" rows="2" placeholder="输入SN码"></textarea>
                  <div class="flex gap-2">
                    <button @click="saveSN(s.id)" class="btn btn-primary btn-sm text-xs flex-1">保存SN码</button>
                    <button @click="editingSNId = null; snInput = ''" class="btn btn-secondary btn-sm text-xs flex-1">取消</button>
                  </div>
                </div>
                <div v-else class="flex items-start justify-between gap-2">
                  <div v-if="s.sn_code" class="flex-1">
                    <span class="text-xs text-[#86868b] font-semibold">SN码:</span>
                    <div v-for="sn in formatSN(s.sn_code)" :key="sn" class="text-xs text-[#34c759] font-mono">{{ sn }}</div>
                  </div>
                  <div v-else class="flex-1 text-xs text-[#86868b]">未填写SN码</div>
                  <button
                    @click="editingSNId = s.id; snInput = s.sn_code || ''"
                    class="text-xs text-[#0071e3] hover:text-[#0071e3] flex-shrink-0"
                  >{{ s.sn_code ? '编辑' : '添加' }}</button>
                </div>
              </div>

              <!-- Per-shipment Actions -->
              <div class="flex gap-2 flex-wrap">
                <button @click="editShipmentItem(s)" class="btn btn-secondary btn-sm text-xs">编辑</button>
                <button v-if="s.tracking_no" @click="refreshShipmentItem(s.id)" class="btn btn-warning btn-sm text-xs">刷新物流</button>
                <button
                  v-if="s.tracking_no"
                  @click="copyTrackingNo((s.carrier_name || '未知') + ' 单号：' + s.tracking_no + (s.sn_code ? ' SN：' + s.sn_code : ''))"
                  class="btn btn-secondary btn-sm text-xs"
                >复制</button>
                <button @click="deleteShipmentItem(s.id)" class="btn btn-sm text-xs" style="background:#fee2e2;color:#b91c1c">删除</button>
              </div>

              <!-- Tracking Timeline -->
              <div v-if="s.tracking_info?.length" class="mt-3 pt-2 border-t">
                <div class="text-xs text-[#86868b] mb-1">物流轨迹:</div>
                <div class="space-y-1 max-h-32 overflow-y-auto">
                  <div v-for="(t, i) in s.tracking_info" :key="(t.ftime || t.time || '') + i" class="flex gap-2 text-xs">
                    <div class="flex flex-col items-center flex-shrink-0">
                      <div :class="['w-2 h-2 rounded-full mt-1', i === 0 ? 'bg-[#34c759]' : 'bg-[#d2d2d7]']"></div>
                      <div v-if="i < s.tracking_info.length - 1" class="w-0.5 h-5 bg-[#e8e8ed]"></div>
                    </div>
                    <div>
                      <div class="text-[#86868b]">{{ t.ftime || t.time }}</div>
                      <div class="text-[#6e6e73]">{{ t.context || t.desc }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Ship Form (new shipping flow) -->
            <div v-if="showShipForm" class="p-3 bg-[#e8f4fd] rounded-lg border border-[#b3d7f5]">
              <div class="font-semibold mb-2 text-sm">发货</div>
              <!-- Product selection -->
              <div class="mb-3">
                <div class="text-xs text-[#86868b] font-semibold mb-1">选择发货商品:</div>
                <div v-for="item in shipItems" :key="item.order_item_id" class="flex items-center gap-2 mb-2 p-2 bg-white rounded border">
                  <div class="flex-1">
                    <div class="text-sm font-medium">{{ item.product_name }}</div>
                    <div class="text-xs text-[#86868b]">{{ item.product_sku }} | 总{{ item.total_qty }} 已发{{ item.shipped_qty }} 待发{{ item.remaining_qty }}</div>
                  </div>
                  <div class="flex items-center gap-1">
                    <label class="text-xs text-[#86868b]">本次:</label>
                    <input
                      v-model.number="item.ship_qty"
                      type="number"
                      :min="0"
                      :max="item.remaining_qty"
                      class="input text-sm py-1 w-16 text-center"
                    >
                  </div>
                  <div v-if="item.sn_required" class="w-full mt-1">
                    <label class="text-xs text-[#86868b]">SN码 (必填，{{ item.ship_qty }}个):</label>
                    <textarea v-model="item.sn_input" class="input text-sm py-1 w-full" rows="1" placeholder="逗号/空格/换行分隔"></textarea>
                  </div>
                </div>
              </div>
              <!-- Carrier info -->
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="label text-xs">快递公司</label>
                  <select v-model="shipForm.carrier_code" @change="onShipCarrierChange" class="input text-sm py-1">
                    <option value="">请选择</option>
                    <option v-for="c in carriers" :key="c.code" :value="c.code">{{ c.name }}</option>
                  </select>
                </div>
                <div v-if="shipForm.carrier_code === 'self_pickup'" class="flex items-end pb-1">
                  <span class="text-sm text-[#34c759] font-semibold">客户上门自提</span>
                </div>
                <div v-else>
                  <label class="label text-xs">快递单号</label>
                  <input v-model="shipForm.tracking_no" class="input text-sm py-1" placeholder="输入快递单号">
                </div>
                <div
                  v-if="shipForm.carrier_code !== 'self_pickup' && ['shunfeng', 'shunfengkuaiyun', 'zhongtong'].includes(shipForm.carrier_code)"
                  class="col-span-2"
                >
                  <label class="label text-xs">
                    手机号后四位
                    <span class="text-[#ff9f0a] font-normal">
                      （{{ carriers.find(c => c.code === shipForm.carrier_code)?.name }}必填）
                    </span>
                  </label>
                  <input v-model="shipForm.phone" class="input text-sm py-1" placeholder="收/寄件人手机号后四位" maxlength="11">
                </div>
              </div>
              <div class="flex gap-2 pt-2">
                <button @click="submitShip" class="btn btn-primary btn-sm flex-1">
                  {{ shipForm.carrier_code === 'self_pickup' ? '确认自提' : '确认发货' }}
                </button>
                <button @click="showShipForm = false" class="btn btn-secondary btn-sm flex-1">取消</button>
              </div>
            </div>

            <!-- Add/Edit Shipment Form (legacy, for editing existing shipments) -->
            <div v-if="showShipmentForm" class="p-3 bg-[#e8f4fd] rounded-lg border border-[#b3d7f5]">
              <div class="font-semibold mb-2 text-sm">{{ editingShipmentId ? '编辑物流单' : '添加物流单' }}</div>
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="label text-xs">快递公司</label>
                  <select v-model="shipmentForm.carrier_code" @change="onCarrierChange" class="input text-sm py-1">
                    <option value="">请选择</option>
                    <option v-for="c in carriers" :key="c.code" :value="c.code">{{ c.name }}</option>
                  </select>
                </div>
                <div v-if="shipmentForm.carrier_code === 'self_pickup'" class="flex items-end pb-1">
                  <span class="text-sm text-[#34c759] font-semibold">客户上门自提，无需快递单号</span>
                </div>
                <div v-else>
                  <label class="label text-xs">快递单号</label>
                  <input v-model="shipmentForm.tracking_no" class="input text-sm py-1" placeholder="输入快递单号">
                </div>
                <div
                  v-if="shipmentForm.carrier_code !== 'self_pickup' && ['shunfeng', 'shunfengkuaiyun', 'zhongtong'].includes(shipmentForm.carrier_code)"
                  class="col-span-2"
                >
                  <label class="label text-xs">
                    手机号后四位
                    <span class="text-[#ff9f0a] font-normal">
                      （{{ carriers.find(c => c.code === shipmentForm.carrier_code)?.name }}必填）
                    </span>
                  </label>
                  <input v-model="shipmentForm.phone" class="input text-sm py-1" placeholder="收/寄件人手机号后四位" maxlength="11">
                </div>
                <div class="col-span-2">
                  <label class="label text-xs">SN码 <span class="text-[#86868b] font-normal">(选填，多个用逗号/空格/换行分隔)</span></label>
                  <textarea v-model="shipmentForm.sn_code" class="input text-sm py-1" rows="2" placeholder="输入SN码"></textarea>
                </div>
              </div>
              <div class="flex gap-2 pt-2">
                <button @click="saveShipment(shipmentDetail.order.id)" class="btn btn-primary btn-sm flex-1">
                  {{ shipmentForm.carrier_code === 'self_pickup' ? '确认自提' : (editingShipmentId ? '保存修改' : '添加') }}
                </button>
                <button @click="resetShipmentForm" class="btn btn-secondary btn-sm flex-1">取消</button>
              </div>
            </div>

            <div class="flex gap-3 pt-3">
              <button type="button" @click="closeDetailModal" class="btn btn-secondary flex-1">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'
import { useFormat } from '../composables/useFormat'
import { useSort } from '../composables/useSort'
import {
  getShipments,
  getShipmentDetail,
  getCarriers,
  addShipment,
  updateShipment,
  deleteShipment,
  refreshShipment,
  updateSN,
  shipOrder
} from '../api/logistics'
import { orderTypeNames, orderTypeBadges, shipmentStatusBadges, shippingStatusNames, shippingStatusBadges } from '../utils/constants'
import { parseSnCodes } from '../utils/helpers'

const appStore = useAppStore()
const { fmt } = useFormat()

// Sort
const { sortState: shipmentSort, toggleSort, genericSort } = useSort()

// Local state
const shipments = ref([])
const shipmentFilter = reactive({ status: '', search: '' })
const carriers = ref([])
const shipmentDetail = ref(null)
const shipmentForm = reactive({
  carrier_code: '',
  carrier_name: '',
  tracking_no: '',
  phone: '',
  sn_code: ''
})
const editingShipmentId = ref(null)
const showShipmentForm = ref(false)
const editingSNId = ref(null)
const snInput = ref('')
const showDetailModal = ref(false)

// New ship form state
const showShipForm = ref(false)
const shipItems = ref([])
const shipForm = reactive({
  carrier_code: '',
  carrier_name: '',
  tracking_no: '',
  phone: ''
})

// Column visibility config (persisted in localStorage)
const defaultColumns = {
  order_no: true,
  order_type: true,
  customer: true,
  shipping_status: true,
  carrier: true,
  tracking_no: true,
  sn: false,
  status: true,
  last_info: false,
  actions: true
}

const columnLabels = {
  order_no: '订单号',
  order_type: '类型',
  customer: '客户',
  shipping_status: '发货状态',
  carrier: '快递公司',
  tracking_no: '快递单号',
  sn: 'SN码',
  status: '物流状态',
  last_info: '物流信息',
  actions: '操作'
}

let _savedColumns = null
try { _savedColumns = JSON.parse(localStorage.getItem('logistics_columns')) } catch (e) { /* ignore corrupt data */ }
const visibleColumns = reactive(_savedColumns || { ...defaultColumns })

const showColumnMenu = ref(false)

const toggleColumn = (key) => {
  visibleColumns[key] = !visibleColumns[key]
  localStorage.setItem('logistics_columns', JSON.stringify(visibleColumns))
}

const isColumnVisible = (key) => visibleColumns[key]

// Computed
const sortedShipments = computed(() => {
  return genericSort(shipments.value, {
    order_no: s => s.order_no || '',
    order_type: s => s.order_type || '',
    customer: s => s.customer_name || '',
    carrier: s => s.carrier_name || '',
    status: s => s.status || ''
  })
})

const canShip = computed(() => {
  if (!shipmentDetail.value) return false
  const ss = shipmentDetail.value.order.shipping_status
  return ss === 'pending' || ss === 'partial'
})

// Helper functions
const getOrderTypeName = (type) => orderTypeNames[type] || type
const getOrderTypeBadge = (type) => orderTypeBadges[type] || 'badge badge-gray'
const getShipmentStatusBadge = (status) => shipmentStatusBadges[status] || 'bg-[#f5f5f7] text-[#6e6e73]'
const getShippingName = (status) => shippingStatusNames[status] || status || '-'
const getShippingBadge = (status) => shippingStatusBadges[status] || 'badge badge-gray'

const formatSN = (snText) => {
  if (!snText) return []
  return snText.split(/[,，.\/\s\n]+/).map(s => s.trim()).filter(s => s)
}

const extractPhoneFromRemark = () => {
  const remark = shipmentDetail.value?.order?.remark || ''
  const m = remark.match(/1[3-9]\d{9}/)
  return m ? m[0] : ''
}

// Data loading
let _searchTimer = null
const debouncedLoadShipments = () => {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(loadShipments, 300)
}

const loadShipments = async () => {
  try {
    const params = {}
    if (shipmentFilter.status) params.status = shipmentFilter.status
    if (shipmentFilter.search) params.search = shipmentFilter.search
    const { data } = await getShipments(params)
    shipments.value = data
  } catch (e) {
    console.error(e)
  }
}

const loadCarriers = async () => {
  try {
    const { data } = await getCarriers()
    carriers.value = data
  } catch (e) {
    console.error(e)
  }
}

// Shipment detail
const viewShipment = async (orderId) => {
  try {
    const { data } = await getShipmentDetail(orderId)
    shipmentDetail.value = data
    resetShipmentForm()
    showShipForm.value = false
    if (!carriers.value.length) await loadCarriers()
    showDetailModal.value = true
    // If order is pending/partial and no shipments yet, auto-open ship form
    const ss = data.order.shipping_status
    if ((ss === 'pending' || ss === 'partial') && !data.shipments?.length) {
      openShipForm()
    }
  } catch (e) {
    appStore.showToast('加载物流详情失败', 'error')
  }
}

const closeDetailModal = () => {
  showDetailModal.value = false
  shipmentDetail.value = null
  resetShipmentForm()
  showShipForm.value = false
}

// New ship form
const openShipForm = () => {
  resetShipmentForm()
  showShipForm.value = true
  shipForm.carrier_code = ''
  shipForm.carrier_name = ''
  shipForm.tracking_no = ''
  shipForm.phone = extractPhoneFromRemark()

  const items = shipmentDetail.value?.order?.items || []
  shipItems.value = items.filter(i => (i.remaining_qty || 0) > 0).map(i => ({
    order_item_id: i.id,
    product_name: i.product_name,
    product_sku: i.product_sku,
    total_qty: i.quantity,
    shipped_qty: i.shipped_qty || 0,
    remaining_qty: i.remaining_qty || (i.quantity - (i.shipped_qty || 0)),
    ship_qty: i.remaining_qty || (i.quantity - (i.shipped_qty || 0)),
    sn_required: false,
    sn_input: ''
  }))
}

const onShipCarrierChange = () => {
  const c = carriers.value.find(x => x.code === shipForm.carrier_code)
  if (c) shipForm.carrier_name = c.name
}

const submitShip = async () => {
  if (appStore.submitting) return
  if (!shipForm.carrier_code) {
    appStore.showToast('请选择快递公司', 'error')
    return
  }
  const isSelfPickup = shipForm.carrier_code === 'self_pickup'
  if (!isSelfPickup && !shipForm.tracking_no) {
    appStore.showToast('请填写快递单号', 'error')
    return
  }

  const itemsToShip = shipItems.value.filter(i => i.ship_qty > 0)
  if (!itemsToShip.length) {
    appStore.showToast('请选择要发货的商品', 'error')
    return
  }

  for (const item of itemsToShip) {
    if (item.ship_qty > item.remaining_qty) {
      appStore.showToast(`${item.product_name} 发货数量超过剩余数量`, 'error')
      return
    }
  }

  const payload = {
    carrier_code: shipForm.carrier_code,
    carrier_name: shipForm.carrier_name,
    tracking_no: shipForm.tracking_no || null,
    phone: shipForm.phone || null,
    is_self_pickup: isSelfPickup,
    items: itemsToShip.map(i => {
      const snList = i.sn_input ? parseSnCodes(i.sn_input) : []
      return {
        order_item_id: i.order_item_id,
        quantity: i.ship_qty,
        sn_codes: snList.length ? snList : null
      }
    })
  }

  appStore.submitting = true
  try {
    const { data } = await shipOrder(shipmentDetail.value.order.id, payload)
    appStore.showToast(data.message)
    showShipForm.value = false
    // Reload detail
    await viewShipment(shipmentDetail.value.order.id)
    loadShipments()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '发货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// Legacy shipment form (for editing existing shipments)
const resetShipmentForm = () => {
  editingShipmentId.value = null
  shipmentForm.carrier_code = ''
  shipmentForm.carrier_name = ''
  shipmentForm.tracking_no = ''
  shipmentForm.phone = ''
  shipmentForm.sn_code = ''
  showShipmentForm.value = false
  editingSNId.value = null
  snInput.value = ''
}

const openNewShipmentForm = () => {
  editingShipmentId.value = null
  shipmentForm.carrier_code = ''
  shipmentForm.carrier_name = ''
  shipmentForm.tracking_no = ''
  shipmentForm.phone = extractPhoneFromRemark()
  shipmentForm.sn_code = ''
  showShipmentForm.value = true
  showShipForm.value = false
}

const editShipmentItem = (s) => {
  editingShipmentId.value = s.id
  shipmentForm.carrier_code = s.carrier_code || ''
  shipmentForm.carrier_name = s.carrier_name || ''
  shipmentForm.tracking_no = s.tracking_no || ''
  shipmentForm.phone = s.phone || extractPhoneFromRemark()
  shipmentForm.sn_code = s.sn_code || ''
  showShipmentForm.value = true
  showShipForm.value = false
}

const onCarrierChange = () => {
  const c = carriers.value.find(x => x.code === shipmentForm.carrier_code)
  if (c) shipmentForm.carrier_name = c.name
}

const saveShipment = async (orderId) => {
  if (!shipmentForm.carrier_code) {
    appStore.showToast('请选择快递公司', 'error')
    return
  }
  if (shipmentForm.carrier_code !== 'self_pickup' && !shipmentForm.tracking_no) {
    appStore.showToast('请填写快递单号', 'error')
    return
  }
  const snList = parseSnCodes(shipmentForm.sn_code)
  const payload = { ...shipmentForm, sn_codes: snList.length ? snList : null }
  try {
    let data
    if (editingShipmentId.value) {
      const resp = await updateShipment(editingShipmentId.value, payload)
      data = resp.data
    } else {
      const resp = await addShipment(orderId, payload)
      data = resp.data
    }
    appStore.showToast(data.message)
    if (data.shipment) {
      const list = shipmentDetail.value.shipments
      const idx = list.findIndex(s => s.id === data.shipment.id)
      if (idx >= 0) list[idx] = data.shipment
      else list.push(data.shipment)
    }
    resetShipmentForm()
    loadShipments()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}

const deleteShipmentItem = async (shipmentId) => {
  if (!await appStore.customConfirm('删除确认', '确定删除此物流单？')) return
  try {
    await deleteShipment(shipmentId)
    shipmentDetail.value.shipments = shipmentDetail.value.shipments.filter(s => s.id !== shipmentId)
    appStore.showToast('已删除')
    loadShipments()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

const refreshShipmentItem = async (shipmentId) => {
  try {
    const { data } = await refreshShipment(shipmentId)
    appStore.showToast(data.message)
    if (data.shipment) {
      const list = shipmentDetail.value.shipments
      const idx = list.findIndex(s => s.id === shipmentId)
      if (idx >= 0) list[idx] = data.shipment
    }
    loadShipments()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  }
}

// Copy functions
const copyTrackingNo = (no) => {
  if (!no) return
  navigator.clipboard.writeText(no).then(() => {
    appStore.showToast('已复制快递单号')
  }).catch(() => {
    const t = document.createElement('textarea')
    t.value = no
    document.body.appendChild(t)
    t.select()
    document.execCommand('copy')
    document.body.removeChild(t)
    appStore.showToast('已复制快递单号')
  })
}

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

// SN editing
const saveSN = async (shipmentId) => {
  const snList = parseSnCodes(snInput.value)
  try {
    const { data } = await updateSN(shipmentId, {
      sn_code: snInput.value,
      sn_codes: snList.length ? snList : null
    })
    appStore.showToast(data.message)
    if (data.shipment) {
      const list = shipmentDetail.value.shipments
      const idx = list.findIndex(s => s.id === shipmentId)
      if (idx >= 0) list[idx] = data.shipment
    }
    editingSNId.value = null
    snInput.value = ''
    loadShipments()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}

// Init
const handleDocClick = (e) => {
  if (showColumnMenu.value && !e.target.closest('[data-column-menu]')) {
    showColumnMenu.value = false
  }
}
onMounted(() => {
  loadShipments()
  loadCarriers()
  document.addEventListener('click', handleDocClick)
})
onUnmounted(() => {
  document.removeEventListener('click', handleDocClick)
})
</script>
