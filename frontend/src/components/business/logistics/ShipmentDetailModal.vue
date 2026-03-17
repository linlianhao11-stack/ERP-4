<template>
  <!-- 物流详情弹窗 -->
  <teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="font-semibold">物流详情</h3>
          <button @click="close" class="modal-close">&times;</button>
        </div>
        <div class="modal-body space-y-4" v-if="shipmentDetail">
          <!-- 订单信息区 -->
          <div class="p-3 bg-elevated rounded-lg">
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
                <span class="text-muted">发货地址/备注:</span>
                <span class="text-secondary font-medium">{{ shipmentDetail.order.remark }}</span>
              </div>
            </div>
            <!-- 商品明细及发货进度 -->
            <div v-if="shipmentDetail.order.items?.length" class="mt-2">
              <div class="text-xs text-muted mb-1">商品明细:</div>
              <div v-for="item in shipmentDetail.order.items" :key="item.id || item.product_sku" class="text-xs text-secondary flex justify-between">
                <span>{{ item.product_name }} x{{ item.quantity }} ¥{{ fmt(item.unit_price) }}</span>
                <span v-if="item.remaining_qty > 0" class="text-warning">待发 {{ item.remaining_qty }}</span>
                <span v-else class="text-success">已发完</span>
              </div>
            </div>
          </div>

          <!-- 物流单列表头 -->
          <div class="flex justify-between items-center p-3 bg-surface border rounded-lg">
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

          <!-- 各物流单详情 -->
          <div
            v-for="(s, idx) in shipmentDetail.shipments"
            :key="s.id"
            class="p-3 border rounded-lg"
            :class="editingShipmentId === s.id ? 'border-primary bg-info-subtle' : 'bg-surface'"
          >
            <div class="flex justify-between items-center mb-1">
              <div class="text-sm font-semibold">物流单 #{{ idx + 1 }}</div>
              <span :class="['text-xs px-2 py-0.5 rounded-full', getShipmentStatusBadge(s.status)]">{{ getShipmentStatusName(s.status, s.status_text) }}</span>
            </div>
            <div v-if="s.tracking_no" class="text-sm mb-1">
              {{ s.carrier_name }} <span class="font-mono text-xs">{{ s.tracking_no }}</span>
            </div>
            <div v-else class="text-sm text-muted mb-1">未填写快递信息</div>
            <div v-if="s.last_info" class="text-xs text-muted mb-2">{{ s.last_info }}</div>

            <!-- 包裹内商品明细 -->
            <div v-if="s.items?.length" class="mb-2 p-2 bg-elevated rounded border border-line">
              <div class="text-xs text-muted font-semibold mb-1">发货商品:</div>
              <div v-for="si in s.items" :key="si.product_sku" class="text-xs text-secondary flex justify-between">
                <span>{{ si.product_name }} ({{ si.product_sku }})</span>
                <span class="font-semibold">x{{ si.quantity }}</span>
              </div>
            </div>

            <!-- SN码区域 -->
            <div class="mb-2 p-2 rounded border" :class="s.sn_code ? 'bg-success-subtle border-success' : 'bg-elevated border-line-strong'">
              <div v-if="editingSNId === s.id" class="space-y-1">
                <label class="text-xs text-muted font-semibold">
                  SN码 <span class="font-normal text-muted">(多个用逗号/空格/换行分隔)</span>
                </label>
                <textarea v-model="snInput" class="input text-sm py-1" rows="2" placeholder="输入SN码"></textarea>
                <div class="flex gap-2">
                  <button @click="saveSN(s.id)" class="btn btn-primary btn-sm text-xs flex-1">保存SN码</button>
                  <button @click="editingSNId = null; snInput = ''" class="btn btn-secondary btn-sm text-xs flex-1">取消</button>
                </div>
              </div>
              <div v-else class="flex items-start justify-between gap-2">
                <div v-if="s.sn_code" class="flex-1">
                  <span class="text-xs text-muted font-semibold">SN码:</span>
                  <div v-for="sn in formatSN(s.sn_code)" :key="sn" class="text-xs text-success font-mono">{{ sn }}</div>
                </div>
                <div v-else class="flex-1 text-xs text-muted">未填写SN码</div>
                <button
                  @click="editingSNId = s.id; snInput = s.sn_code || ''"
                  class="text-xs text-primary hover:text-primary flex-shrink-0"
                >{{ s.sn_code ? '编辑' : '添加' }}</button>
              </div>
            </div>

            <!-- 单个物流单操作按钮 -->
            <div class="flex gap-2 flex-wrap">
              <button @click="editShipmentItem(s)" class="btn btn-secondary btn-sm text-xs">编辑</button>
              <button v-if="s.tracking_no" @click="refreshShipmentItem(s.id)" class="btn btn-warning btn-sm text-xs">刷新物流</button>
              <button
                v-if="s.tracking_no"
                @click="copyTrackingNo((s.carrier_name || '未知') + ' 单号：' + s.tracking_no + (s.sn_code ? ' SN：' + s.sn_code : ''))"
                class="btn btn-secondary btn-sm text-xs"
              >复制</button>
              <button @click="deleteShipmentItem(s.id)" class="btn btn-sm btn-danger text-xs">删除</button>
            </div>

            <!-- 物流轨迹时间线 -->
            <div v-if="s.tracking_info?.length" class="mt-3 pt-2 border-t">
              <div class="text-xs text-muted mb-1">物流轨迹:</div>
              <div class="space-y-1 max-h-32 overflow-y-auto">
                <div v-for="(t, i) in s.tracking_info" :key="(t.ftime || t.time || '') + i" class="flex gap-2 text-xs">
                  <div class="flex flex-col items-center flex-shrink-0">
                    <div :class="['w-2 h-2 rounded-full mt-1', i === 0 ? 'bg-success' : 'bg-line-strong']"></div>
                    <div v-if="i < s.tracking_info.length - 1" class="w-0.5 h-5 bg-line"></div>
                  </div>
                  <div>
                    <div class="text-muted">{{ t.ftime || t.time }}</div>
                    <div class="text-secondary">{{ t.context || t.desc }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 发货表单（新发货流程，含商品选择）-->
          <div v-if="showShipForm" class="p-3 bg-info-subtle rounded-lg border border-primary">
            <div class="font-semibold mb-2 text-sm">发货</div>
            <!-- 选择发货商品 -->
            <div class="mb-3">
              <div class="text-xs text-muted font-semibold mb-1">选择发货商品:</div>
              <div v-for="item in shipItems" :key="item.order_item_id" class="flex items-center gap-2 mb-2 p-2 bg-surface rounded border">
                <div class="flex-1">
                  <div class="text-sm font-medium">{{ item.product_name }}</div>
                  <div class="text-xs text-muted">{{ item.product_sku }} | 总{{ item.total_qty }} 已发{{ item.shipped_qty }} 待发{{ item.remaining_qty }}</div>
                </div>
                <div class="flex items-center gap-1">
                  <label class="text-xs text-muted">本次:</label>
                  <input
                    v-model.number="item.ship_qty"
                    type="number"
                    :min="0"
                    :max="item.remaining_qty"
                    class="input text-sm py-1 w-16 text-center"
                  >
                </div>
                <div v-if="item.sn_required" class="w-full mt-1">
                  <label class="text-xs text-muted">SN码 (必填，{{ item.ship_qty }}个):</label>
                  <textarea v-model="item.sn_input" class="input text-sm py-1 w-full" rows="1" placeholder="逗号/空格/换行分隔"></textarea>
                </div>
              </div>
            </div>
            <!-- 快递信息 -->
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="label text-xs">快递公司</label>
                <select v-model="shipForm.carrier_code" @change="onShipCarrierChange" class="input text-sm py-1">
                  <option value="">请选择</option>
                  <option v-for="c in carriers" :key="c.code" :value="c.code">{{ c.name }}</option>
                </select>
              </div>
              <div v-if="shipForm.carrier_code === 'self_pickup'" class="flex items-end pb-1">
                <span class="text-sm text-success font-semibold">客户上门自提</span>
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
                  <span class="text-warning font-normal">
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

          <!-- 编辑/添加物流单表单（legacy）-->
          <div v-if="showShipmentForm" class="p-3 bg-info-subtle rounded-lg border border-primary">
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
                <span class="text-sm text-success font-semibold">客户上门自提，无需快递单号</span>
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
                  <span class="text-warning font-normal">
                    （{{ carriers.find(c => c.code === shipmentForm.carrier_code)?.name }}必填）
                  </span>
                </label>
                <input v-model="shipmentForm.phone" class="input text-sm py-1" placeholder="收/寄件人手机号后四位" maxlength="11">
              </div>
              <div class="col-span-2">
                <label class="label text-xs">SN码 <span class="text-muted font-normal">(选填，多个用逗号/空格/换行分隔)</span></label>
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
            <button type="button" @click="close" class="btn btn-secondary flex-1">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 物流详情弹窗
 * 包含订单信息、物流单列表、发货表单、编辑表单、SN码编辑、物流轨迹
 */
import { ref, reactive, computed, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useFormat } from '../../../composables/useFormat'
import {
  getShipmentDetail,
  addShipment,
  updateShipment,
  deleteShipment,
  refreshShipment,
  updateSN,
  shipOrder
} from '../../../api/logistics'
import { orderTypeNames, orderTypeBadges, shipmentStatusNames, shipmentStatusBadges, shippingStatusNames, shippingStatusBadges } from '../../../utils/constants'
import { parseSnCodes } from '../../../utils/helpers'

const props = defineProps({
  /** 弹窗是否显示 */
  visible: Boolean,
  /** 当前查看的订单ID */
  orderId: Number,
  /** 快递公司列表（从父组件传入避免重复请求）*/
  carriers: Array
})

const emit = defineEmits(['update:visible', 'data-changed'])

const appStore = useAppStore()
const { fmt } = useFormat()

// ---- 详情数据 ----
const shipmentDetail = ref(null)

// ---- 编辑物流单表单（legacy）----
const shipmentForm = reactive({
  carrier_code: '',
  carrier_name: '',
  tracking_no: '',
  phone: '',
  sn_code: ''
})
const editingShipmentId = ref(null)
const showShipmentForm = ref(false)

// ---- SN码编辑 ----
const editingSNId = ref(null)
const snInput = ref('')

// ---- 新发货表单 ----
const showShipForm = ref(false)
const shipItems = ref([])
const shipForm = reactive({
  carrier_code: '',
  carrier_name: '',
  tracking_no: '',
  phone: ''
})

// ---- 计算属性：是否可发货（pending/partial 状态）----
const canShip = computed(() => {
  if (!shipmentDetail.value) return false
  const ss = shipmentDetail.value.order.shipping_status
  return ss === 'pending' || ss === 'partial'
})

// ---- 辅助函数 ----
const getOrderTypeName = (type) => orderTypeNames[type] || type
const getOrderTypeBadge = (type) => orderTypeBadges[type] || 'badge badge-gray'
const getShipmentStatusBadge = (status) => shipmentStatusBadges[status] || 'bg-elevated text-secondary'
const getShipmentStatusName = (status, fallback) => shipmentStatusNames[status] || fallback || status || '-'
const getShippingName = (status) => shippingStatusNames[status] || status || '-'
const getShippingBadge = (status) => shippingStatusBadges[status] || 'badge badge-gray'

/** 解析 SN 码文本为数组 */
const formatSN = (snText) => {
  if (!snText) return []
  return snText.split(/[,，.\/\s\n]+/).map(s => s.trim()).filter(s => s)
}

/** 从订单备注中提取手机号 */
const extractPhoneFromRemark = () => {
  const remark = shipmentDetail.value?.order?.remark || ''
  const m = remark.match(/1[3-9]\d{9}/)
  return m ? m[0] : ''
}

// ---- 关闭弹窗 ----
const close = () => {
  emit('update:visible', false)
  shipmentDetail.value = null
  resetShipmentForm()
  showShipForm.value = false
}

// ---- 加载物流详情（watch orderId 自动触发）----
const loadDetail = async (orderId) => {
  if (!orderId) return
  try {
    const { data } = await getShipmentDetail(orderId)
    shipmentDetail.value = data
    resetShipmentForm()
    showShipForm.value = false
    // 如果订单待发货/部分发货且无物流单，自动打开发货表单
    const ss = data.order.shipping_status
    if ((ss === 'pending' || ss === 'partial') && !data.shipments?.length) {
      openShipForm()
    }
  } catch (e) {
    appStore.showToast('加载物流详情失败', 'error')
  }
}

/** 监听 orderId 变化自动加载详情 */
watch(() => props.orderId, (newId) => {
  if (newId && props.visible) {
    loadDetail(newId)
  }
})

/** 监听 visible 为 true 时也加载 */
watch(() => props.visible, (val) => {
  if (val && props.orderId) {
    loadDetail(props.orderId)
  }
})

// ---- 新发货表单操作 ----
/** 打开发货表单，初始化发货商品列表 */
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
    sn_required: i.sn_required || false,
    sn_input: ''
  }))
}

/** 发货表单快递公司选择变化 */
const onShipCarrierChange = () => {
  const c = props.carriers.find(x => x.code === shipForm.carrier_code)
  if (c) shipForm.carrier_name = c.name
}

/** 提交发货 */
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

  // 校验发货数量不超过剩余数量
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
    // 重新加载详情
    await loadDetail(shipmentDetail.value.order.id)
    // 通知父组件数据已变化（刷新列表）
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '发货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// ---- Legacy 物流单表单操作 ----
/** 重置编辑表单 */
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

/** 打开新建物流单表单 */
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

/** 编辑已有物流单 */
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

/** 编辑表单快递公司选择变化 */
const onCarrierChange = () => {
  const c = props.carriers.find(x => x.code === shipmentForm.carrier_code)
  if (c) shipmentForm.carrier_name = c.name
}

/** 保存物流单（新增或更新）*/
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
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}

/** 删除物流单 */
const deleteShipmentItem = async (shipmentId) => {
  if (!await appStore.customConfirm('删除确认', '确定删除此物流单？')) return
  try {
    await deleteShipment(shipmentId)
    shipmentDetail.value.shipments = shipmentDetail.value.shipments.filter(s => s.id !== shipmentId)
    appStore.showToast('已删除')
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

/** 刷新单个物流单的物流信息 */
const refreshShipmentItem = async (shipmentId) => {
  try {
    const { data } = await refreshShipment(shipmentId)
    appStore.showToast(data.message)
    if (data.shipment) {
      const list = shipmentDetail.value.shipments
      const idx = list.findIndex(s => s.id === shipmentId)
      if (idx >= 0) list[idx] = data.shipment
    }
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  }
}

// ---- 复制功能 ----
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

/** 复制单个快递单号文本 */
const copyTrackingNo = (no) => {
  if (!no) return
  copyText(no, '已复制快递单号')
}

/** 复制所有快递单号 */
const copyAllTracking = (trackingList) => {
  if (!trackingList?.length) return
  const text = trackingList.map(t => {
    let s = (t.carrier_name || '未知') + ' 单号：' + t.tracking_no
    if (t.sn_code) s += ' SN：' + t.sn_code
    return s
  }).join(', ')
  copyText(text, '已复制' + trackingList.length + '个快递单号')
}

// ---- SN码编辑 ----
/** 保存 SN 码 */
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
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}
</script>
