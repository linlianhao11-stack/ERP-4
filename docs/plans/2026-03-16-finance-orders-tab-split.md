# FinanceOrdersTab 组件拆分实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 1226 行的 FinanceOrdersTab.vue 按弹窗边界拆分为 3 个组件，降低单文件复杂度，为后续取消/退货功能扩展做准备。

**Architecture:** 按弹窗边界拆分——订单详情弹窗（含退货）和取消订单向导各自独立为子组件，主组件保留列表逻辑。取消预览的简单/复杂路径判断留在主组件，向导组件只处理多步流程。子组件通过 props 接收数据、通过 emit 通知操作结果。

**Tech Stack:** Vue 3 Composition API, `<script setup>`, Tailwind CSS

**Design doc:** `docs/plans/2026-03-16-finance-orders-tab-split-design.md`

---

### Task 1: 创建 FinanceOrderDetailModal.vue

**Files:**
- Create: `frontend/src/components/business/finance/FinanceOrderDetailModal.vue`

**Step 1: 创建详情弹窗组件**

从 FinanceOrdersTab.vue 中提取行 220-457（详情弹窗模板）和行 748-753 + 755-764 + 816-831 + 846-856 + 951-1041（相关状态和逻辑），组成独立组件。

```vue
<script setup>
/**
 * 订单详情弹窗（含退货表单）
 * 从 FinanceOrdersTab 拆分出来的独立子组件
 */
import { ref, reactive, computed, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import { getOrder, createOrder } from '../../../api/orders'
import { getLocations } from '../../../api/warehouses'
import StatusBadge from '../../common/StatusBadge.vue'
import { Maximize2, Minimize2 } from 'lucide-vue-next'

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

// --- 退货状态 ---
const showReturnForm = ref(false)
const returnForm = reactive({ items: [], refunded: false })
const returnSubmitting = ref(false)

// --- 收款方式名称 ---
const paymentMethods = computed(() => settingsStore.paymentMethods)
const getPaymentMethodName = (code) => {
  if (!code) return ''
  const m = paymentMethods.value?.find(p => p.code === code)
  return m ? m.name : code
}

// --- 计算属性 ---
/** 商品按账套分组 */
const detailItemsByAccountSet = computed(() => {
  const items = orderDetail.items || []
  if (!items.length) return []
  const groups = {}
  for (const item of items) {
    const key = item.account_set_name || '默认账套'
    if (!groups[key]) groups[key] = { key, name: key, items: [], subtotal: 0 }
    groups[key].items.push(item)
    groups[key].subtotal += item.amount
  }
  return Object.values(groups)
})

/** 是否可退货 */
const canReturn = computed(() => {
  if (!orderDetail.order_type) return false
  return ['CASH', 'CREDIT', 'CONSIGN_SETTLE'].includes(orderDetail.order_type)
    && orderDetail.shipping_status !== 'pending'
    && orderDetail.items?.some(i => i.available_return_quantity > 0)
})

/** 退货表单是否可提交 */
const canSubmitReturn = computed(() => {
  return returnForm.items.some(i => i.qty > 0)
})

/** 解析 SN 码 */
const parseSN = (raw) => {
  if (!raw) return []
  try { return JSON.parse(raw) } catch { return raw.split(',').map(s => s.trim()).filter(Boolean) }
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
  }
})

// --- 关闭弹窗 ---
const close = () => {
  emit('update:visible', false)
}

// --- 查看关联订单（自身递归） ---
const viewRelatedOrder = async (id) => {
  try {
    const { data } = await getOrder(id)
    Object.keys(orderDetail).forEach(k => delete orderDetail[k])
    Object.assign(orderDetail, data)
    showReturnForm.value = false
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
  <!-- 此处放置从原文件行 220-457 提取的模板 -->
  <!-- 关键修改点：
    1. showOrderDetailModal → visible (props)
    2. 关闭操作改为 close() 调用 emit('update:visible', false)
    3. viewOrder(id) 改为 viewRelatedOrder(id)（内部加载）
    4. handleCancelOrder(id) 改为 emit('cancel-order', id)
    5. loadOrders() 调用改为 emit('data-changed')
  -->
</template>
```

模板部分：将原文件行 220-457 的 HTML 完整复制过来，做以下替换：
- `showOrderDetailModal = false` → `close()`
- `showOrderDetailModal = false; showReturnForm = false; isDetailExpanded = false` → `close()`
- `viewOrder(xxx)` → `viewRelatedOrder(xxx)`
- `handleCancelOrder(orderDetail.id)` → `emit('cancel-order', orderDetail.id)`
- 外层 `v-if="showOrderDetailModal"` → `v-if="visible"`

**Step 2: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功（新组件虽未被引用但不影响构建）

---

### Task 2: 创建 FinanceOrderCancelWizard.vue

**Files:**
- Create: `frontend/src/components/business/finance/FinanceOrderCancelWizard.vue`

**Step 1: 创建取消向导组件**

从 FinanceOrdersTab.vue 中提取行 459-605（向导模板）和行 766-782 + 834-843 + 1088-1192（相关状态和逻辑），组成独立组件。

```vue
<script setup>
/**
 * 取消订单向导（多步流程）
 * 从 FinanceOrdersTab 拆分出来的独立子组件
 * 仅处理复杂取消路径（部分发货/已收款），简单取消由父组件直接处理
 */
import { ref, reactive, computed, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'
import { cancelOrder } from '../../../api/orders'

const props = defineProps({
  previewData: { type: Object, default: null },
  visible: { type: Boolean, default: false }
})
const emit = defineEmits(['update:visible', 'cancelled', 'data-changed'])

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { fmt } = useFormat()

// --- 向导状态 ---
const cancelStep = ref(1)
const cancelForm = reactive({
  new_order_paid_amount: 0,
  new_order_rebate_used: 0,
  item_allocations: [],
  refund_amount: 0,
  refund_rebate: 0,
  refund_method: 'balance',
  refund_payment_method: 'cash',
})

// --- 计算属性 ---
const cancelStepCount = computed(() => {
  const d = props.previewData
  if (!d) return 0
  if (!d.is_partial) return 1
  if (d.paid_amount > 0 || d.rebate_used > 0) return 3
  return 1
})

// --- visible 变为 true 时根据 previewData 初始化 cancelForm ---
watch(() => props.visible, (val) => {
  if (val && props.previewData) {
    const data = props.previewData
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
  }
})

const close = () => {
  emit('update:visible', false)
}

// --- 逐商品分配逻辑 ---
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
  const preview = props.previewData
  if (!preview) return
  const totalPaid = Math.round(cancelForm.item_allocations.reduce((s, i) => s + i.paid, 0) * 100) / 100
  const totalRebate = Math.round(cancelForm.item_allocations.reduce((s, i) => s + i.rebate, 0) * 100) / 100
  cancelForm.new_order_paid_amount = +totalPaid.toFixed(2)
  cancelForm.new_order_rebate_used = +totalRebate.toFixed(2)
  cancelForm.refund_amount = +(preview.paid_amount - cancelForm.new_order_paid_amount).toFixed(2)
  cancelForm.refund_rebate = +(preview.rebate_used - cancelForm.new_order_rebate_used).toFixed(2)
}

// --- 向导导航 ---
const nextCancelStep = () => {
  const preview = props.previewData
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

const prevCancelStep = () => {
  if (cancelStep.value === 3) cancelStep.value = 2
  else if (cancelStep.value === 2) cancelStep.value = 1
}

// --- 确认取消 ---
const confirmCancel = async () => {
  if (appStore.submitting) return
  const preview = props.previewData
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
    close()
    emit('cancelled')
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '取消失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>

<template>
  <!-- 此处放置从原文件行 460-605 提取的模板 -->
  <!-- 关键修改点：
    1. v-if="showCancelModal && cancelPreviewData" → v-if="visible && previewData"
    2. cancelPreviewData → previewData (全局替换)
    3. showCancelModal = false → close()
  -->
</template>
```

模板部分：将原文件行 460-605 的 HTML 完整复制过来，做以下替换：
- `showCancelModal` → 使用 `visible` + `close()`
- `cancelPreviewData` → `previewData`（props 引用）
- 保留 `<teleport to="body">` 包裹

**Step 2: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

---

### Task 3: 重构 FinanceOrdersTab.vue 引入子组件

**Files:**
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue`

**Step 1: 移除已提取的模板和逻辑，引入子组件**

修改内容：

**Script 部分修改：**

1. 新增 import：
```js
import FinanceOrderDetailModal from './FinanceOrderDetailModal.vue'
import FinanceOrderCancelWizard from './FinanceOrderCancelWizard.vue'
```

2. 移除不再需要的 import（已移入子组件）：
- `Maximize2, Minimize2`（仅详情弹窗用）
- `createOrder`（仅退货用）
- `getLocations`（仅退货用）

3. 新增弹窗控制状态（替换原状态）：
```js
// --- 弹窗控制 ---
const selectedOrderId = ref(null)
const showDetail = ref(false)
const cancelPreviewData = ref(null)
const showCancel = ref(false)
```

4. 移除已提取到子组件的状态：
- `showOrderDetailModal`, `isDetailExpanded`, `orderDetail` (→ 详情弹窗)
- `showReturnForm`, `returnForm`, `returnSubmitting` (→ 详情弹窗)
- `showCancelModal`, `cancelStep`, `cancelForm` (→ 取消向导)
- 保留 `cancelPreviewData`（父组件判断路径用）

5. 移除已提取到子组件的计算属性：
- `detailItemsByAccountSet`, `canReturn`, `canSubmitReturn`, `cancelStepCount`

6. 移除已提取到子组件的函数：
- `openReturnForm`, `submitReturn`, `cancelReturnForm`
- `onItemPaidChange`, `onItemRebateChange`, `recalcCancelTotals`
- `nextCancelStep`, `prevCancelStep`, `confirmCancel`
- `parseSN`, `getPaymentMethodName`

7. 重写 `viewOrder`：
```js
const viewOrder = (id) => {
  selectedOrderId.value = id
  showDetail.value = true
}
```

8. 重写 `handleCancelOrder`（保留简单/复杂路径判断）：
```js
const handleCancelOrder = async (orderId) => {
  try {
    const { data } = await cancelPreview(orderId)
    cancelPreviewData.value = data
    const hasPaid = data.paid_amount > 0 || data.rebate_used > 0

    // 简单路径：直接确认取消
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
```

9. 新增取消完成回调：
```js
const onCancelDone = () => {
  showCancel.value = false
  showDetail.value = false
  loadOrders()
}
```

**Template 部分修改：**

1. 删除行 220-605（两个弹窗的全部模板）

2. 在 `</div>` 结束标签前（原弹窗位置）插入子组件：
```html
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
```

**Step 2: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，无警告

---

### Task 4: 功能验证

**Step 1: 启动预览并验证**

1. 启动前端 dev server
2. 导航到财务页面的"订单明细" tab
3. 验证以下场景：
   - 订单列表正常加载和展示
   - 点击订单行能打开详情弹窗
   - 详情弹窗展示订单信息、商品明细、物流信息
   - 关联订单可点击跳转（弹窗内重新加载）
   - 退货按钮可打开退货表单
   - 取消订单按钮能正确触发（简单路径直接确认，复杂路径打开向导）
   - 弹窗关闭后状态正确重置
   - 筛选、排序、分页、导出功能不受影响
