<template>
  <teleport to="body">
    <div v-if="visible && previewData" class="modal-overlay" @click.self="close()">
      <div class="modal-content" style="max-width:640px">
        <div class="modal-header">
          <h3 class="font-semibold">取消订单 {{ previewData.order_no }}</h3>
          <button @click="close()" class="modal-close">&times;</button>
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
          <div v-show="cancelStep === 1 && previewData?.is_partial" class="space-y-4">
            <!-- 已发货商品（部分取消时显示） -->
            <div v-if="previewData.is_partial">
              <div class="flex items-center gap-2 mb-2">
                <span class="w-5 h-5 rounded-full bg-success text-white text-xs flex items-center justify-center font-bold">✓</span>
                <span class="text-sm font-semibold text-foreground">已发货商品（将生成新订单）</span>
              </div>
              <div class="p-3 bg-success-subtle rounded-lg border border-success">
                <div v-for="item in previewData.shipped_items" :key="'s-'+item.product_sku" class="flex justify-between text-sm py-1">
                  <span class="text-foreground">{{ item.product_name }} <span class="text-muted">x{{ item.shipped_qty }}</span></span>
                  <span class="font-semibold">¥{{ fmt(item.amount) }}</span>
                </div>
                <div class="border-t border-success mt-2 pt-2 flex justify-between text-sm font-bold">
                  <span>新订单金额</span>
                  <span class="text-success">¥{{ fmt(previewData.new_order_amount) }}</span>
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
                <div v-for="item in previewData.cancel_items" :key="'c-'+item.product_sku" class="flex justify-between text-sm py-1">
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
              原订单：付款 <span class="font-semibold text-foreground">¥{{ fmt(previewData.paid_amount) }}</span>
              + 返利 <span class="font-semibold text-success">¥{{ fmt(previewData.rebate_used) }}</span>
              = ¥{{ fmt(previewData.total_amount) }}
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
                    <td class="px-2 py-2 text-right">¥{{ fmt(previewData.new_order_amount) }}</td>
                    <td class="px-2 py-2 text-center">¥{{ cancelForm.new_order_paid_amount.toFixed(2) }}</td>
                    <td class="px-2 py-2 text-center text-success">¥{{ cancelForm.new_order_rebate_used.toFixed(2) }}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <!-- 分配平衡提示 -->
            <div class="p-2 rounded text-center text-xs font-semibold" :class="Math.abs(cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used - previewData.new_order_amount) < 0.01 ? 'bg-success-subtle text-success' : 'bg-error-subtle text-error'">
              {{ Math.abs(cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used - previewData.new_order_amount) < 0.01 ? '分配正确' : '分配不平衡：合计 ¥' + (cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used).toFixed(2) + ' / 需要 ¥' + previewData.new_order_amount.toFixed(2) }}
            </div>
          </div>

          <!-- 第3步：退款方式 -->
          <div v-show="(cancelStepCount === 3 && cancelStep === 3) || (cancelStepCount === 1 && !previewData?.is_partial)" class="space-y-4">
            <div class="text-center mb-2">
              <div class="text-sm font-semibold text-foreground">退还金额确认</div>
              <div class="text-xs text-muted mt-1">确认退款金额和退款方式</div>
            </div>
            <div class="p-4 bg-orange-subtle rounded-lg">
              <div class="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label class="label text-xs font-semibold">退款金额</label>
                  <input v-model.number="cancelForm.refund_amount" type="number" step="0.01" min="0" :max="previewData.paid_amount" class="input text-sm py-1.5">
                </div>
                <div>
                  <label class="label text-xs font-semibold">退返利金额</label>
                  <input v-model.number="cancelForm.refund_rebate" type="number" step="0.01" min="0" :max="previewData.rebate_used" class="input text-sm py-1.5">
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
            <button v-else @click="close()" class="btn btn-secondary flex-1">取消</button>
            <button v-if="cancelStep < cancelStepCount" @click="nextCancelStep" class="btn btn-primary flex-1">下一步 &rarr;</button>
            <button v-else @click="confirmCancel" class="btn btn-danger flex-1">确认取消订单</button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 取消订单向导（多步流程）
 * 从 FinanceOrdersTab 拆分出来的独立子组件
 * 仅处理复杂取消路径（部分发货/已收款），简单取消由父组件直接处理
 */
import { ref, reactive, computed, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useFormat } from '../../../composables/useFormat'
import { cancelOrder } from '../../../api/orders'

const props = defineProps({
  previewData: { type: Object, default: null },
  visible: { type: Boolean, default: false }
})
const emit = defineEmits(['update:visible', 'cancelled', 'data-changed'])

const appStore = useAppStore()
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
  if (!d) return 1
  if (d.order_type === 'CONSIGN_OUT') return 0
  const hasPaid = d.paid_amount > 0 || d.rebate_used > 0
  if (!d.is_partial && !hasPaid) return 0
  if (!d.is_partial && hasPaid) return 1
  if (d.is_partial && !hasPaid) return 1
  return 3
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
