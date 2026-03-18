<script setup>
/**
 * 订单详情弹窗（含退货表单）
 * 从 FinanceOrdersTab 拆分出来的独立子组件
 */
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import { getOrder, createOrder, updateOrderRemark } from '../../../api/orders'
import { getLocations } from '../../../api/warehouses'
import StatusBadge from '../../common/StatusBadge.vue'
import { Maximize2, Minimize2, Copy, Pencil } from 'lucide-vue-next'

const props = defineProps({
  orderId: { type: Number, default: null },
  visible: { type: Boolean, default: false }
})
const emit = defineEmits(['update:visible', 'cancel-order', 'data-changed', 'open-payment'])

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()

// --- 详情状态 ---
const isDetailExpanded = ref(false)
const orderDetail = reactive({})

// --- 备注编辑状态 ---
const isEditingRemark = ref(false)
const editingRemark = ref('')
const remarkSaving = ref(false)
const remarkTextarea = ref(null)

const startEditRemark = () => {
  editingRemark.value = orderDetail.remark || ''
  isEditingRemark.value = true
  nextTick(() => remarkTextarea.value?.focus())
}

const cancelEditRemark = () => {
  isEditingRemark.value = false
  editingRemark.value = ''
}

const saveRemark = async () => {
  remarkSaving.value = true
  try {
    await updateOrderRemark(orderDetail.id, editingRemark.value)
    orderDetail.remark = editingRemark.value
    isEditingRemark.value = false
    appStore.showToast('备注更新成功')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '备注保存失败', 'error')
  } finally {
    remarkSaving.value = false
  }
}

// --- 退货状态 ---
const showReturnForm = ref(false)
const returnForm = reactive({ items: [], refunded: false })
const returnSubmitting = ref(false)

// --- 收款方式名称 ---
const paymentMethods = computed(() => settingsStore.paymentMethods)
const getPaymentMethodName = (m) => {
  const found = paymentMethods.value.find(p => p.code === m)
  if (found) return found.name
  return { cash: '现金', bank: '银行转账', bank_public: '对公转账', bank_private: '对私转账', wechat: '微信', alipay: '支付宝' }[m] || m
}

// --- 计算属性 ---
/** 商品按账套分组 */
const detailItemsByAccountSet = computed(() => {
  const items = orderDetail.items || []
  if (!items.length) return []
  const groups = new Map()
  for (const item of items) {
    const asId = item.account_set_id || 0
    const asName = item.account_set_name || '未关联账套'
    if (!groups.has(asId)) {
      groups.set(asId, { key: asId, name: asName, items: [], subtotal: 0 })
    }
    const group = groups.get(asId)
    group.items.push(item)
    group.subtotal += Number(item.amount) || 0
  }
  return [...groups.values()]
})

/** 是否可退货 */
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

/** 解析 SN 码（兼容 JSON 数组和逗号分隔字符串） */
const parseSN = (raw) => {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed.map(String)
  } catch {}
  return String(raw).split(',').map(s => s.trim()).filter(Boolean)
}

/** 获取物流单的 SN 码列表（合并 ShipmentItem + Shipment 两个数据源，去重） */
const getShipmentSNCodes = (sh) => {
  const codes = []
  for (const si of (sh.items || [])) {
    codes.push(...parseSN(si.sn_codes))
  }
  if (!codes.length && sh.sn_code) {
    codes.push(...parseSN(sh.sn_code))
  }
  return [...new Set(codes)]
}

/** 复制文本到剪贴板 */
const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    appStore.showToast('已复制', 'success')
  } catch {
    appStore.showToast('复制失败', 'error')
  }
}

// --- 数据加载 ---
/** visible 变为 true 时加载订单详情 */
watch(() => props.visible, async (val) => {
  if (val && props.orderId) {
    try {
      const { data } = await getOrder(props.orderId)
      Object.keys(orderDetail).forEach(k => delete orderDetail[k])
      Object.assign(orderDetail, data)
    } catch (e) {
      appStore.showToast('加载订单详情失败', 'error')
      emit('update:visible', false)
    }
  } else if (!val) {
    // 关闭时重置状态
    showReturnForm.value = false
    isDetailExpanded.value = false
    isEditingRemark.value = false
  }
})

// --- 关闭弹窗 ---
const close = () => {
  emit('update:visible', false)
}

// --- 查看关联订单（组件内重新加载） ---
const viewRelatedOrder = async (id) => {
  try {
    const { data } = await getOrder(id)
    Object.keys(orderDetail).forEach(k => delete orderDetail[k])
    Object.assign(orderDetail, data)
    showReturnForm.value = false
    isEditingRemark.value = false
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
  }
}

// --- 退货逻辑 ---
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
      const { data: rawLocs } = await getLocations({ warehouse_id: warehouseId })
      const locs = rawLocs.items || rawLocs
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
    close()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '退货失败', 'error')
  } finally {
    returnSubmitting.value = false
  }
}

const cancelReturnForm = () => {
  showReturnForm.value = false
}
</script>

<template>
  <!-- ============ 弹窗：订单详情 ============ -->
  <div v-if="visible" class="modal-overlay" @click.self="close()">
    <div class="modal-content" :class="{ 'modal-expanded': isDetailExpanded }" style="max-width:920px">
      <div class="modal-header">
        <h3 class="font-semibold">订单详情</h3>
        <div class="flex items-center gap-1">
          <button @click="isDetailExpanded = !isDetailExpanded" class="modal-expand-btn hidden md:inline-flex" :aria-label="isDetailExpanded ? '收起弹窗' : '展开弹窗'">
            <Minimize2 v-if="isDetailExpanded" :size="16" />
            <Maximize2 v-else :size="16" />
          </button>
          <button @click="close()" class="modal-close">&times;</button>
        </div>
      </div>
      <div class="modal-body" v-if="orderDetail.order_no">
        <!-- 订单基本信息 -->
        <div class="mb-5 p-4 bg-elevated rounded-xl">
          <div class="flex justify-between items-start mb-2">
            <div>
              <div class="text-[15px] font-bold font-mono">{{ orderDetail.order_no }}</div>
              <div class="text-xs text-muted mt-0.5">
                <span v-if="orderDetail.employee_name">销售员: {{ orderDetail.employee_name }} · </span>
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
              <span @click="viewRelatedOrder(orderDetail.related_order.id)" class="text-primary hover:underline cursor-pointer font-mono">{{ orderDetail.related_order.order_no }}</span>
            </div>
            <div v-if="orderDetail.related_children?.length" class="col-span-2">
              <span class="text-muted">拆分订单:</span>
              <span v-for="child in orderDetail.related_children" :key="child.id" @click="viewRelatedOrder(child.id)" class="text-primary hover:underline cursor-pointer font-mono ml-1">{{ child.order_no }}</span>
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
            <div class="col-span-2 pt-2 border-t border-line">
              <template v-if="isEditingRemark">
                <div class="text-muted text-xs mb-1.5">备注</div>
                <textarea
                  ref="remarkTextarea"
                  v-model="editingRemark"
                  class="input text-sm"
                  rows="3"
                  maxlength="2000"
                  placeholder="输入订单备注信息..."
                  @keyup.escape="cancelEditRemark"
                ></textarea>
                <div class="flex items-center gap-3 mt-2">
                  <button @click="saveRemark" :disabled="remarkSaving" class="text-success-emphasis text-xs font-medium">
                    {{ remarkSaving ? '保存中...' : '保存' }}
                  </button>
                  <button @click="cancelEditRemark" class="text-muted text-xs">取消</button>
                </div>
              </template>
              <template v-else>
                <div class="flex items-start gap-2">
                  <div class="flex-1 min-w-0">
                    <span class="text-muted">备注:</span>
                    <span class="text-secondary">{{ orderDetail.remark || '无备注' }}</span>
                  </div>
                  <button
                    @click="startEditRemark"
                    class="text-muted hover:text-primary transition-colors flex-shrink-0 mt-0.5"
                    title="编辑备注"
                    aria-label="编辑备注"
                  >
                    <Pencil :size="14" />
                  </button>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- 商品明细（按账套分组） -->
        <div class="mb-5">
          <div class="flex items-center gap-2 mb-2.5">
            <span class="text-[13px] font-semibold text-secondary">商品明细</span>
            <span v-if="orderDetail.items?.length" class="text-[11px] text-muted bg-elevated px-2 py-0.5 rounded-full">{{ orderDetail.items.length }} 件商品</span>
            <span v-if="detailItemsByAccountSet.length > 1" class="text-[11px] text-warning bg-warning-subtle px-2 py-0.5 rounded-full">{{ detailItemsByAccountSet.length }} 个账套</span>
          </div>
          <div class="overflow-x-auto">
            <template v-for="(group, gIdx) in detailItemsByAccountSet" :key="group.key">
              <!-- 分组标题（仅多账套时显示） -->
              <div v-if="detailItemsByAccountSet.length > 1" class="flex justify-between items-center px-3 py-1.5 bg-elevated border-b text-xs" :class="gIdx > 0 ? 'mt-3' : ''">
                <span class="font-semibold text-secondary">{{ group.name }}</span>
                <span class="text-primary font-mono font-semibold">&yen;{{ fmt(group.subtotal) }}</span>
              </div>
              <table class="w-full text-sm">
                <thead class="bg-elevated" v-if="gIdx === 0 || detailItemsByAccountSet.length > 1">
                  <tr>
                    <th class="px-2 py-2 text-left text-xs font-semibold text-secondary">商品</th>
                    <th class="px-2 py-2 text-left text-xs font-semibold text-secondary">仓库</th>
                    <th class="px-2 py-2 text-right text-xs font-semibold text-secondary">单价</th>
                    <th class="px-2 py-2 text-right text-xs font-semibold text-secondary">数量</th>
                    <th v-if="orderDetail.rebate_used > 0" class="px-2 py-2 text-right text-xs font-semibold text-secondary">返利</th>
                    <th class="px-2 py-2 text-right text-xs font-semibold text-secondary">金额</th>
                    <th class="px-2 py-2 text-right text-xs font-semibold text-secondary" v-if="hasPermission('finance')">毛利</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-line">
                  <tr v-for="item in group.items" :key="item.id || item.product_id">
                    <td class="px-2 py-2.5">
                      <div class="font-medium">{{ item.product_name }}</div>
                      <div class="text-[11px] text-muted font-mono">{{ item.product_sku }}</div>
                    </td>
                    <td class="px-2 py-2.5 text-muted">{{ item.warehouse_name || '-' }}</td>
                    <td class="px-2 py-2.5 text-right">{{ fmt(item.unit_price) }}</td>
                    <td class="px-2 py-2.5 text-right">{{ item.quantity }}</td>
                    <td v-if="orderDetail.rebate_used > 0" class="px-2 py-2.5 text-right text-success">{{ item.rebate_amount > 0 ? '-¥' + fmt(item.rebate_amount) : '' }}</td>
                    <td class="px-2 py-2.5 text-right font-semibold">{{ fmt(item.amount) }}</td>
                    <td class="px-2 py-2.5 text-right" v-if="hasPermission('finance')" :class="item.profit >= 0 ? 'text-success' : 'text-error'">{{ fmt(item.profit) }}</td>
                  </tr>
                </tbody>
              </table>
            </template>
          </div>
        </div>

        <!-- 关联应收单（按账套分组） -->
        <div v-if="orderDetail.receivable_bills?.length" class="mb-5">
          <div class="flex items-center gap-2 mb-2.5">
            <span class="text-[13px] font-semibold text-secondary">关联应收单</span>
            <span class="text-[11px] text-muted bg-elevated px-2 py-0.5 rounded-full">{{ orderDetail.receivable_bills.length }} 笔</span>
          </div>
          <div class="space-y-2">
            <div v-for="rb in orderDetail.receivable_bills" :key="rb.id" class="flex items-center justify-between px-2 py-2 bg-elevated rounded-lg border text-[13px]">
              <div class="flex items-center gap-2">
                <span class="font-mono text-xs text-primary">{{ rb.bill_no }}</span>
                <span v-if="rb.account_set_name" class="text-[11px] text-muted bg-surface px-1.5 py-0.5 rounded">{{ rb.account_set_name }}</span>
              </div>
              <div class="flex items-center gap-3">
                <span class="font-semibold">&yen;{{ fmt(rb.total_amount) }}</span>
                <span :class="rb.status === 'completed' ? 'badge badge-green' : rb.status === 'partial' ? 'badge badge-orange' : 'badge badge-gray'" class="text-[11px]">
                  {{ rb.status === 'completed' ? '已收' : rb.status === 'partial' ? '部分收' : rb.status === 'cancelled' ? '已取消' : '待收' }}
                </span>
              </div>
            </div>
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
            <!-- 运单号（带复制） -->
            <div v-if="sh.tracking_no" class="flex items-center justify-between px-3.5 py-2 border-b border-line">
              <div class="flex items-center gap-1.5">
                <span class="text-[11px] text-muted">运单号:</span>
                <span class="text-xs font-mono font-medium text-primary">{{ sh.tracking_no }}</span>
              </div>
              <button @click="copyToClipboard(sh.tracking_no)" class="text-muted hover:text-primary transition-colors" title="复制运单号">
                <Copy :size="14" />
              </button>
            </div>
            <!-- 发货商品明细 -->
            <div v-if="sh.items?.length" class="px-3.5 py-2">
              <div v-for="(si, idx) in sh.items" :key="idx" class="flex items-start gap-2.5 py-1.5" :class="idx < sh.items.length - 1 ? 'border-b border-line' : ''">
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-medium">{{ si.product_name }}</div>
                  <div class="text-[11px] text-muted font-mono">{{ si.product_sku }}</div>
                </div>
                <span class="text-xs font-semibold text-secondary flex-shrink-0">× {{ si.quantity }}</span>
              </div>
            </div>
            <!-- SN 码面板 -->
            <div v-if="getShipmentSNCodes(sh).length" class="px-3.5 py-2 border-t border-line">
              <div class="text-[11px] font-semibold text-muted mb-1.5">SN码</div>
              <div class="space-y-1">
                <div v-for="sn in getShipmentSNCodes(sh)" :key="sn" class="flex items-center justify-between px-2.5 py-1.5 bg-elevated border border-line rounded-lg group">
                  <span class="text-[12px] font-mono text-text">{{ sn }}</span>
                  <button @click="copyToClipboard(sn)" class="text-muted opacity-0 group-hover:opacity-100 hover:text-primary transition-all" title="复制SN码">
                    <Copy :size="14" />
                  </button>
                </div>
              </div>
              <div v-if="getShipmentSNCodes(sh).length > 1" class="mt-2 flex justify-end">
                <button @click="copyToClipboard(getShipmentSNCodes(sh).join('\n'))" class="text-[11px] text-primary hover:text-primary-hover font-medium">
                  复制全部SN码
                </button>
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
            <table class="w-full text-sm">
              <thead class="bg-elevated">
                <tr>
                  <th class="px-2 py-2 text-left text-xs font-semibold text-secondary">商品</th>
                  <th class="px-2 py-2 text-right text-xs font-semibold text-secondary">单价</th>
                  <th class="px-2 py-2 text-right text-xs font-semibold text-secondary">可退</th>
                  <th class="px-2 py-2 text-center text-xs font-semibold text-secondary" style="width:100px">退货数量</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-line">
                <tr v-for="item in returnForm.items" :key="item.product_id">
                  <td class="px-2 py-2.5">
                    <div class="font-medium">{{ item.product_name }}</div>
                    <div class="text-[11px] text-muted font-mono">{{ item.product_sku }}</div>
                  </td>
                  <td class="px-2 py-2.5 text-right">{{ fmt(item.unit_price) }}</td>
                  <td class="px-2 py-2.5 text-right text-muted">{{ item.max_qty }}</td>
                  <td class="px-2 py-2.5 text-center">
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
      <div v-if="!showReturnForm" class="modal-footer">
        <button type="button" @click="close()" class="btn btn-secondary btn-sm">关闭</button>
        <button v-if="canReturn" type="button" @click="openReturnForm" class="btn btn-primary btn-sm">销售退货</button>
        <button v-if="orderDetail.shipping_status && ['pending', 'partial'].includes(orderDetail.shipping_status)" type="button" @click="emit('cancel-order', orderDetail.id)" class="btn btn-sm btn-danger">取消订单</button>
      </div>
    </div>
  </div>
</template>
