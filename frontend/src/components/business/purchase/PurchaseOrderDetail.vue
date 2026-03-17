<template>
  <!-- 采购订单详情弹窗 -->
  <div v-if="showPODetailModal && purchaseOrderDetail" class="modal-overlay active" @click.self="showPODetailModal = false">
    <div class="modal-content" style="max-width:700px">
      <div class="modal-header">
        <h3 class="modal-title">采购订单详情</h3>
        <button @click="showPODetailModal = false" class="modal-close">&times;</button>
      </div>
      <div class="modal-body"><div class="space-y-4">
        <!-- 基本信息 -->
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div><span class="text-muted">采购单号:</span> <span class="font-mono font-semibold">{{ purchaseOrderDetail.po_no }}</span></div>
          <div><span class="text-muted">状态:</span> <StatusBadge type="purchaseStatus" :status="purchaseOrderDetail.status" /></div>
          <div><span class="text-muted">供应商:</span> {{ purchaseOrderDetail.supplier_name }}</div>
          <div v-if="purchaseOrderDetail.rebate_used > 0 || purchaseOrderDetail.credit_used > 0">
            <span class="text-muted">原价合计:</span>
            <span class="font-semibold">¥{{ fmt(purchaseOrderDetail.total_amount + purchaseOrderDetail.rebate_used + (purchaseOrderDetail.credit_used || 0)) }}</span>
          </div>
          <div v-if="purchaseOrderDetail.rebate_used > 0"><span class="text-muted">返利抵扣:</span> <span class="text-success font-semibold">-¥{{ fmt(purchaseOrderDetail.rebate_used) }}</span></div>
          <div v-if="purchaseOrderDetail.credit_used > 0"><span class="text-muted">在账资金抵扣:</span> <span class="text-primary font-semibold">-¥{{ fmt(purchaseOrderDetail.credit_used) }}</span></div>
          <div><span class="text-muted">{{ purchaseOrderDetail.rebate_used > 0 || purchaseOrderDetail.credit_used > 0 ? '实付金额' : '总金额' }}:</span> <span class="font-semibold text-primary">¥{{ fmt(purchaseOrderDetail.total_amount) }}</span></div>
          <div><span class="text-muted">创建人:</span> {{ purchaseOrderDetail.creator_name }}</div>
          <div><span class="text-muted">创建时间:</span> {{ fmtDate(purchaseOrderDetail.created_at) }}</div>
          <div v-if="purchaseOrderDetail.reviewed_by_name"><span class="text-muted">审核人:</span> {{ purchaseOrderDetail.reviewed_by_name }} {{ fmtDate(purchaseOrderDetail.reviewed_at) }}</div>
          <div v-if="purchaseOrderDetail.paid_by_name"><span class="text-muted">付款确认:</span> {{ purchaseOrderDetail.paid_by_name }} {{ fmtDate(purchaseOrderDetail.paid_at) }}</div>
          <div v-if="purchaseOrderDetail.remark"><span class="text-muted">备注:</span> {{ purchaseOrderDetail.remark }}</div>
        </div>
        <!-- 退货信息 -->
        <div v-if="purchaseOrderDetail.return_amount > 0" class="bg-orange-subtle border border-warning rounded-lg p-3">
          <h4 class="font-semibold text-sm text-warning mb-2">退货信息</h4>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div><span class="text-muted">退货金额:</span> <span class="font-semibold text-warning">¥{{ fmt(purchaseOrderDetail.return_amount) }}</span></div>
            <div><span class="text-muted">退款状态:</span> <span :class="purchaseOrderDetail.is_refunded ? 'text-success' : 'text-error-emphasis'">{{ purchaseOrderDetail.is_refunded ? '已退款' : '转为在账资金' }}</span></div>
            <div v-if="purchaseOrderDetail.return_tracking_no"><span class="text-muted">退货物流:</span> {{ purchaseOrderDetail.return_tracking_no }}</div>
            <div v-if="purchaseOrderDetail.returned_by_name"><span class="text-muted">处理人:</span> {{ purchaseOrderDetail.returned_by_name }} {{ fmtDate(purchaseOrderDetail.returned_at) }}</div>
          </div>
        </div>
        <!-- 关联退货单 -->
        <div v-if="purchaseOrderDetail.returns?.length" class="bg-elevated border rounded-lg p-3 mt-2">
          <h4 class="font-semibold text-sm mb-2">关联退货单</h4>
          <div v-for="r in purchaseOrderDetail.returns" :key="r.id"
               class="flex justify-between items-center p-2 border-b last:border-0 text-sm">
            <span class="font-mono text-primary">{{ r.return_no }}</span>
            <span class="font-semibold text-warning">¥{{ fmt(r.total_amount) }}</span>
            <span :class="{
              'text-warning': r.refund_status === 'pending',
              'text-success': r.refund_status === 'confirmed',
              'text-muted': r.refund_status === 'n/a'
            }">{{ r.refund_status === 'pending' ? '待退款' : r.refund_status === 'confirmed' ? '已到账' : '转为在账资金' }}</span>
            <span class="text-muted text-xs">{{ fmtDate(r.created_at) }}</span>
          </div>
        </div>
        <!-- 商品明细表格 -->
        <div class="border-t pt-3">
          <h4 class="font-semibold text-sm mb-2">商品明细</h4>
          <div class="table-container">
            <table class="w-full text-xs">
              <thead class="bg-elevated">
                <tr>
                  <th class="px-2 py-1 text-left">商品</th>
                  <th class="px-2 py-1 text-right">含税单价</th>
                  <th class="px-2 py-1 text-right">数量</th>
                  <th v-if="purchaseOrderDetail.rebate_used > 0" class="px-2 py-1 text-right">返利</th>
                  <th class="px-2 py-1 text-right">金额</th>
                  <th class="px-2 py-1 text-center">收货进度</th>
                  <th v-if="purchaseOrderDetail.return_amount > 0 || purchaseOrderDetail.status === 'completed'" class="px-2 py-1 text-center">退货</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr v-for="it in purchaseOrderDetail.items" :key="it.id">
                  <td class="px-2 py-1">
                    <div class="font-medium">{{ it.product_name }}</div>
                    <div class="text-muted font-mono">{{ it.product_sku }}</div>
                  </td>
                  <td class="px-2 py-1 text-right">¥{{ fmt(it.tax_inclusive_price) }}</td>
                  <td class="px-2 py-1 text-right">{{ it.quantity }}</td>
                  <td v-if="purchaseOrderDetail.rebate_used > 0" class="px-2 py-1 text-right text-success">{{ it.rebate_amount > 0 ? '-¥' + fmt(it.rebate_amount) : '' }}</td>
                  <td class="px-2 py-1 text-right font-semibold">¥{{ fmt(it.amount) }}</td>
                  <td class="px-2 py-1 text-center">
                    <span :class="it.received_quantity >= it.quantity ? 'text-success' : 'text-warning'">{{ it.received_quantity }}/{{ it.quantity }}</span>
                  </td>
                  <td v-if="purchaseOrderDetail.return_amount > 0 || purchaseOrderDetail.status === 'completed'" class="px-2 py-1 text-center">
                    <span v-if="it.returned_quantity > 0" class="text-warning">{{ it.returned_quantity }}</span>
                    <span v-else class="text-muted">-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      </div>
      <div class="modal-footer flex-wrap">
        <button v-if="purchaseOrderDetail.status === 'pending_review' && hasPermission('purchase_approve')" @click="handleApprovePO(purchaseOrderDetail.id)" class="btn btn-sm btn-primary">审核通过</button>
        <button v-if="purchaseOrderDetail.status === 'pending_review' && hasPermission('purchase_approve')" @click="handleRejectPO(purchaseOrderDetail.id)" class="btn btn-sm btn-danger">拒绝</button>
        <button v-if="['paid','partial'].includes(purchaseOrderDetail.status) && hasPermission('purchase_receive')" @click="openReceiveFromDetail(purchaseOrderDetail.id)" class="btn btn-sm btn-success">采购收货</button>
        <button v-if="purchaseOrderDetail.status === 'completed' && hasPermission('purchase')" @click="openReturnModal(purchaseOrderDetail)" class="btn btn-sm btn-warning">采购退货</button>
        <button @click="showPODetailModal = false" class="btn btn-sm btn-secondary">关闭</button>
      </div>
    </div>
  </div>

  <!-- 采购收货弹窗 -->
  <div v-if="showReceiveModal" class="modal-overlay active" @click.self="showReceiveModal = false">
    <div class="modal-content" style="max-width:700px">
      <div class="modal-header">
        <h3 class="modal-title">采购收货</h3>
        <button @click="showReceiveModal = false" class="modal-close">&times;</button>
      </div>
      <div class="space-y-4 p-4">
        <div v-if="!receivablePOs.length" class="p-8 text-center text-muted">暂无可收货的采购订单</div>
        <div v-for="po in receivablePOs" :key="po.id" class="border rounded-lg p-3">
          <!-- 可收货PO头部（点击展开/收起） -->
          <div class="flex justify-between items-center mb-2 cursor-pointer" @click="receiveForm.po_id === po.id ? receiveForm.po_id = null : initReceiveItems(po)">
            <div>
              <span class="font-mono font-semibold text-sm">{{ po.po_no }}</span>
              <span class="text-muted text-xs ml-2">{{ po.supplier_name }}</span>
            </div>
            <div class="flex items-center gap-2">
              <StatusBadge type="purchaseStatus" :status="po.status" />
              <span class="text-sm font-semibold">¥{{ fmt(po.total_amount) }}</span>
              <span class="text-muted">{{ receiveForm.po_id === po.id ? '&#9650;' : '&#9660;' }}</span>
            </div>
          </div>
          <!-- 收货明细（选中PO后展开） -->
          <div v-if="receiveForm.po_id === po.id" class="space-y-2 border-t pt-2">
            <div v-for="(item, idx) in receiveForm.items" :key="item.item_id" class="p-2 bg-elevated rounded">
              <div class="flex items-center gap-2 mb-1">
                <label class="flex items-center text-sm">
                  <input type="checkbox" v-model="item.checked" class="mr-1">
                  {{ item.product_name }}
                </label>
                <span class="text-xs text-muted ml-auto">
                  待收:{{ item.pending_qty }}
                  <template v-if="item.checked && item.splits.length > 1">
                    | 已分配:<span :class="getSplitTotal(item) > item.pending_qty ? 'text-error font-semibold' : 'text-success'">{{ getSplitTotal(item) }}</span>
                  </template>
                </span>
              </div>
              <!-- 收货分组（支持拆分到多个仓库） -->
              <div v-if="item.checked" class="space-y-2 mt-1">
                <div v-for="(sp, si) in item.splits" :key="sp.id"
                  :class="['space-y-2', item.splits.length > 1 ? 'border border-primary rounded p-2 bg-surface' : '']">
                  <div class="flex items-center justify-between" v-if="item.splits.length > 1">
                    <span class="text-xs font-semibold text-primary">分组 {{ si + 1 }}</span>
                    <button @click="removeSplit(item, si)" class="text-xs text-error hover:text-error">删除</button>
                  </div>
                  <div class="grid grid-cols-3 gap-2">
                    <div>
                      <label class="text-xs text-muted">本次收货</label>
                      <input v-model.number="sp.receive_quantity" type="number" :max="item.pending_qty" min="1"
                        :class="['input text-sm', getSplitTotal(item) > item.pending_qty ? 'border-error' : '']">
                    </div>
                    <div>
                      <label class="text-xs text-muted">仓库</label>
                      <select v-model="sp.warehouse_id" @change="handleSplitWarehouseChange(item, sp)" class="input text-sm">
                        <option value="">选择</option>
                        <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
                      </select>
                    </div>
                    <div>
                      <label class="text-xs text-muted">仓位</label>
                      <select v-model="sp.location_id" class="input text-sm" :disabled="!sp.warehouse_id">
                        <option value="">{{ sp.warehouse_id ? '选择' : '先选仓库' }}</option>
                        <option v-for="loc in getReceiveLocations(sp.warehouse_id)" :key="loc.id" :value="loc.id">{{ loc.code }}</option>
                      </select>
                    </div>
                  </div>
                  <!-- SN码输入（需要时显示） -->
                  <div v-if="sp.sn_required" class="bg-warning-subtle border border-warning rounded p-2">
                    <label class="text-xs font-semibold">
                      SN码 *
                      <span :class="parseSnCodes(sp.sn_input).length === Number(sp.receive_quantity || 0) ? 'text-success' : 'text-error'">
                        ({{ parseSnCodes(sp.sn_input).length }} / {{ sp.receive_quantity || 0 }})
                      </span>
                    </label>
                    <textarea v-model="sp.sn_input" class="input text-xs mt-1" rows="2" placeholder="每行一个SN码，或用逗号/空格分隔"></textarea>
                  </div>
                </div>
                <!-- 拆分操作 -->
                <div class="flex items-center justify-between">
                  <button @click="addSplit(item)" class="text-xs text-primary hover:text-primary-hover">+ 拆分到其他仓库</button>
                  <span v-if="item.splits.length > 1" class="text-xs" :class="getSplitRemaining(item) < 0 ? 'text-error' : 'text-muted'">
                    剩余未分配: {{ getSplitRemaining(item) }}
                  </span>
                </div>
              </div>
            </div>
            <!-- 收货操作按钮 -->
            <div class="flex gap-3 pt-2">
              <button @click="showReceiveModal = false" class="btn btn-secondary flex-1">取消</button>
              <button @click="confirmReceive" class="btn btn-success flex-1" :disabled="appStore.submitting">{{ appStore.submitting ? '提交中...' : '确认收货入库' }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 采购退货弹窗 -->
  <div v-if="showReturnModal" class="modal-overlay active" @click.self="showReturnModal = false">
    <div class="modal-content" style="max-width:600px">
      <div class="modal-header">
        <h3 class="modal-title">采购退货 - {{ returnForm.po_no }}</h3>
        <button @click="showReturnModal = false" class="modal-close">&times;</button>
      </div>
      <div class="space-y-4 p-4">
        <!-- 退货商品选择 -->
        <div v-for="item in returnForm.items" :key="item.item_id" class="p-3 bg-elevated rounded-lg">
          <label class="flex items-center gap-2 mb-2">
            <input type="checkbox" v-model="item.checked" class="w-4 h-4">
            <span class="font-medium text-sm">{{ item.product_name }}</span>
            <span class="text-xs text-muted ml-auto">可退: {{ item.returnable_qty }}</span>
          </label>
          <div v-if="item.checked" class="flex items-center gap-3">
            <label class="text-xs text-muted">退货数量:</label>
            <input v-model.number="item.return_quantity" type="number" min="1" :max="item.returnable_qty" class="input text-sm w-24">
            <span class="text-xs text-muted">单价: ¥{{ fmt(item.unit_amount) }}</span>
            <span class="text-sm font-semibold text-warning ml-auto">¥{{ (item.return_quantity * item.unit_amount).toFixed(2) }}</span>
          </div>
        </div>
        <!-- 退货选项 -->
        <div class="border-t pt-3 space-y-3">
          <label class="flex items-center gap-2">
            <input type="checkbox" v-model="returnForm.is_refunded" class="w-4 h-4">
            <span class="text-sm">供应商已退款</span>
          </label>
          <div v-if="!returnForm.is_refunded" class="text-xs text-primary bg-info-subtle rounded p-2">
            未退款的金额将转为供应商"在账资金"，可在后续采购单中抵扣
          </div>
          <div v-if="returnForm.is_refunded">
            <label class="label text-xs" for="purchase-return-refund-method">退款方式</label>
            <select id="purchase-return-refund-method" v-model="returnForm.refund_method" class="input text-sm">
              <option value="">请选择</option>
              <option v-for="m in disbursementMethods" :key="m.code" :value="m.name">{{ m.name }}</option>
            </select>
          </div>
          <div>
            <label class="label text-xs">退货物流单号（选填）</label>
            <input v-model="returnForm.tracking_no" class="input text-sm" placeholder="退货物流单号">
          </div>
          <div class="flex justify-between items-center text-sm">
            <span>退货总金额:</span>
            <span class="text-xl font-bold text-warning">¥{{ returnTotalAmount.toFixed(2) }}</span>
          </div>
        </div>
        <!-- 退货操作按钮 -->
        <div class="flex gap-3 pt-2">
          <button @click="showReturnModal = false" class="btn btn-secondary flex-1">取消</button>
          <button @click="confirmReturn" class="btn btn-warning flex-1" :disabled="appStore.submitting">{{ appStore.submitting ? '处理中...' : '确认退货' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 采购订单详情、收货、退货组件
 * 管理详情展示、审核/拒绝、收货分组（含SN码）、退货流程
 */
import { ref, reactive, computed, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useProductsStore } from '../../../stores/products'
import { useWarehousesStore } from '../../../stores/warehouses'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import {
  getPurchaseOrder, approvePurchaseOrder, rejectPurchaseOrder,
  getReceivablePOs, receivePurchaseOrder, returnPurchaseOrder
} from '../../../api/purchase'
import { checkSnRequired } from '../../../api/sn'
import { parseSnCodes } from '../../../utils/helpers'
import StatusBadge from '../../common/StatusBadge.vue'

const props = defineProps({
  /** 详情弹窗是否可见 */
  visible: Boolean,
  /** 要查看的采购订单 ID（传入时自动加载详情） */
  purchaseOrderId: Number
})

const emit = defineEmits(['update:visible', 'data-changed'])

const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const settingsStore = useSettingsStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()
const warehouses = computed(() => warehousesStore.warehouses)
const disbursementMethods = computed(() => settingsStore.disbursementMethods)

// ---- 详情状态 ----
const purchaseOrderDetail = ref(null)
const showPODetailModal = ref(false)

// ---- 收货状态 ----
const showReceiveModal = ref(false)
const receiveForm = reactive({ po_id: null, items: [] })
const receivablePOs = ref([])

// ---- 退货状态 ----
const showReturnModal = ref(false)
const returnForm = reactive({ po_id: null, po_no: '', items: [], is_refunded: false, tracking_no: '', refund_method: '' })

/** 退货总金额 */
const returnTotalAmount = computed(() => {
  return Math.round(returnForm.items
    .filter(i => i.checked && i.return_quantity > 0)
    .reduce((s, i) => s + i.return_quantity * i.unit_amount, 0) * 100) / 100
})

// 监听 purchaseOrderId 变化，自动加载详情
watch(() => props.purchaseOrderId, (id) => {
  if (id) viewPurchaseOrder(id)
})

// 详情弹窗关闭时同步 visible 给父组件
watch(showPODetailModal, (val) => {
  if (!val) emit('update:visible', false)
})

// ---- 详情操作 ----

/** 加载采购订单详情并打开详情弹窗 */
const viewPurchaseOrder = async (id) => {
  try {
    const { data } = await getPurchaseOrder(id)
    purchaseOrderDetail.value = data
    showPODetailModal.value = true
  } catch (e) {
    appStore.showToast('加载详情失败', 'error')
  }
}

/** 审核通过采购订单 */
const handleApprovePO = async (id) => {
  const po = purchaseOrderDetail.value
  if (!po) return
  if (!await appStore.customConfirm('审核通过', `确认通过采购单 ${po.po_no}？通过后将进入待付款状态。`)) return
  try {
    await approvePurchaseOrder(id)
    appStore.showToast('审核通过')
    emit('data-changed')
    // 刷新详情
    if (purchaseOrderDetail.value && purchaseOrderDetail.value.id === id) {
      viewPurchaseOrder(id)
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

/** 拒绝采购订单 */
const handleRejectPO = async (id) => {
  const po = purchaseOrderDetail.value
  if (!po) return
  if (!await appStore.customConfirm('拒绝采购单', `确认拒绝采购单 ${po.po_no}？拒绝后该订单将完结。`)) return
  try {
    await rejectPurchaseOrder(id)
    appStore.showToast('已拒绝')
    emit('data-changed')
    // 刷新详情
    if (purchaseOrderDetail.value && purchaseOrderDetail.value.id === id) {
      viewPurchaseOrder(id)
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

// ---- 收货操作 ----

/** 从详情弹窗进入收货 */
const openReceiveFromDetail = (poId) => {
  showPODetailModal.value = false
  openReceive()
}

/** 打开收货弹窗并加载可收货PO列表 */
const openReceive = () => {
  loadReceivablePOs()
  showReceiveModal.value = true
}

/** 加载可收货的采购订单列表 */
const loadReceivablePOs = async () => {
  try {
    const { data } = await getReceivablePOs()
    receivablePOs.value = data
  } catch (e) {
    console.error(e)
  }
}

// 收货分组 ID 计数器
let splitIdCounter = 0

/** 创建一个收货分组对象 */
const makeSplit = (opts = {}) => ({
  id: ++splitIdCounter,
  receive_quantity: opts.receive_quantity || 0,
  warehouse_id: opts.warehouse_id || '',
  location_id: opts.location_id || '',
  sn_required: false,
  sn_input: ''
})

/** 初始化某个PO的收货明细 */
const initReceiveItems = (po) => {
  receiveForm.po_id = po.id
  receiveForm.items = po.items.map(it => {
    const split = makeSplit({
      receive_quantity: it.pending_quantity,
      warehouse_id: it.target_warehouse_id || '',
      location_id: it.target_location_id || ''
    })
    return {
      item_id: it.id,
      product_id: it.product_id,
      product_name: it.product_name,
      pending_qty: it.pending_quantity,
      checked: true,
      splits: [split]
    }
  })
  // 初始化时检查各分组的SN码要求
  receiveForm.items.forEach(item => {
    item.splits.forEach(sp => {
      if (sp.warehouse_id) handleSplitWarehouseChange(item, sp)
    })
  })
}

/** 计算某商品所有分组的收货总量 */
const getSplitTotal = (item) => item.splits.reduce((s, sp) => s + (Number(sp.receive_quantity) || 0), 0)
/** 计算某商品剩余未分配数量 */
const getSplitRemaining = (item) => item.pending_qty - getSplitTotal(item)

/** 添加一个收货分组 */
const addSplit = (item) => {
  const remaining = getSplitRemaining(item)
  item.splits.push(makeSplit({ receive_quantity: remaining > 0 ? remaining : 0 }))
}

/** 删除一个收货分组 */
const removeSplit = (item, idx) => {
  if (item.splits.length <= 1) return
  item.splits.splice(idx, 1)
}

/** 根据仓库ID获取仓位列表 */
const getReceiveLocations = (warehouseId) => {
  if (!warehouseId) return []
  return warehousesStore.getLocationsByWarehouse(warehouseId)
}

/** 收货分组切换仓库时：重置仓位、检查SN码要求 */
const handleSplitWarehouseChange = async (item, split) => {
  split.location_id = ''
  if (!split.warehouse_id) {
    split.sn_required = false
    split.sn_input = ''
    return
  }
  try {
    const { data } = await checkSnRequired({
      warehouse_id: split.warehouse_id,
      product_id: item.product_id
    })
    split.sn_required = data.required
    if (!data.required) {
      split.sn_input = ''
    }
  } catch (e) {
    split.sn_required = false
  }
}

/** 校验并提交收货 */
const confirmReceive = async () => {
  if (!receiveForm.po_id) {
    appStore.showToast('请选择采购单', 'error')
    return
  }
  const checkedItems = receiveForm.items.filter(i => i.checked)
  if (!checkedItems.length) {
    appStore.showToast('请选择要收货的商品', 'error')
    return
  }
  // 将分组数据扁平化为提交项
  const flatItems = []
  const allSnCodes = new Set()
  for (const item of checkedItems) {
    const total = getSplitTotal(item)
    if (total <= 0) {
      appStore.showToast(`${item.product_name} 收货数量须大于0`, 'error')
      return
    }
    if (total > item.pending_qty) {
      appStore.showToast(`${item.product_name} 收货总量(${total})超过待收数量(${item.pending_qty})`, 'error')
      return
    }
    for (let si = 0; si < item.splits.length; si++) {
      const sp = item.splits[si]
      const qty = Number(sp.receive_quantity) || 0
      if (qty <= 0) continue
      if (!sp.warehouse_id || !sp.location_id) {
        appStore.showToast(`${item.product_name}${item.splits.length > 1 ? ' 分组' + (si + 1) : ''} 缺少仓库或仓位`, 'error')
        return
      }
      // SN码校验
      if (sp.sn_required) {
        const snList = parseSnCodes(sp.sn_input)
        if (!snList.length) {
          appStore.showToast(`${item.product_name}${item.splits.length > 1 ? ' 分组' + (si + 1) : ''} 已启用SN管理，请填写SN码`, 'error')
          return
        }
        if (snList.length !== qty) {
          appStore.showToast(`${item.product_name}${item.splits.length > 1 ? ' 分组' + (si + 1) : ''} SN码数量(${snList.length})与收货数量(${qty})不匹配`, 'error')
          return
        }
        // SN码去重校验
        for (const sn of snList) {
          if (allSnCodes.has(sn)) {
            appStore.showToast(`SN码 ${sn} 重复，请检查`, 'error')
            return
          }
          allSnCodes.add(sn)
        }
      }
      flatItems.push({
        item_id: item.item_id,
        receive_quantity: qty,
        warehouse_id: parseInt(sp.warehouse_id),
        location_id: parseInt(sp.location_id),
        sn_codes: sp.sn_required ? parseSnCodes(sp.sn_input) : null
      })
    }
  }
  if (!flatItems.length) {
    appStore.showToast('请填写收货数量', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await receivePurchaseOrder(receiveForm.po_id, { items: flatItems })
    appStore.showToast('收货成功')
    showReceiveModal.value = false
    productsStore.loadProducts()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '收货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// ---- 退货操作 ----

/** 打开退货弹窗，初始化退货表单 */
const openReturnModal = (po) => {
  returnForm.po_id = po.id
  returnForm.po_no = po.po_no
  returnForm.is_refunded = false
  returnForm.tracking_no = ''
  returnForm.refund_method = ''
  // 确保付款方式已加载
  if (!settingsStore.disbursementMethods.length) settingsStore.loadDisbursementMethods()
  returnForm.items = po.items
    .filter(it => it.returnable_quantity > 0)
    .map(it => ({
      item_id: it.id,
      product_name: `${it.product_sku} - ${it.product_name}`,
      returnable_qty: it.returnable_quantity,
      return_quantity: it.returnable_quantity,
      unit_amount: it.quantity > 0 ? it.amount / it.quantity : 0,
      checked: false
    }))
  showReturnModal.value = true
}

/** 校验并提交退货 */
const confirmReturn = async () => {
  const checkedItems = returnForm.items.filter(i => i.checked && i.return_quantity > 0)
  if (!checkedItems.length) {
    appStore.showToast('请选择退货商品', 'error')
    return
  }
  for (const item of checkedItems) {
    if (item.return_quantity > item.returnable_qty) {
      appStore.showToast(`${item.product_name} 退货数量超过可退数量`, 'error')
      return
    }
  }
  if (!await appStore.customConfirm('确认退货', `确认退货 ${checkedItems.length} 项商品，退货金额 ¥${returnTotalAmount.value.toFixed(2)}？${returnForm.is_refunded ? '' : '未退款金额将转为供应商在账资金。'}`)) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await returnPurchaseOrder(returnForm.po_id, {
      items: checkedItems.map(i => ({ item_id: i.item_id, return_quantity: i.return_quantity })),
      is_refunded: returnForm.is_refunded,
      tracking_no: returnForm.tracking_no || null,
      refund_method: returnForm.is_refunded ? (returnForm.refund_method || null) : null
    })
    appStore.showToast('退货成功')
    showReturnModal.value = false
    showPODetailModal.value = false
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '退货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// 暴露给父组件的方法
defineExpose({
  /** 打开采购收货弹窗 */
  openReceive,
  /** 查看采购订单详情 */
  viewPurchaseOrder
})
</script>
