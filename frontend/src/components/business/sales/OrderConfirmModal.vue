<!--
  订单确认弹窗
  展示订单摘要，支持修改业务员、返利、收款方式、备注
  账套从商品所在仓库自动推断，只读展示（支持多账套提示）
  使用 teleport 渲染到 body，通过 appStore.modal 控制显示
-->
<template>
  <teleport to="body">
    <div
      v-if="visible"
      class="modal-overlay"
      @click.self="$emit('update:visible', false)"
    >
      <div class="modal-content" @click.stop>
        <!-- 弹窗标题 -->
        <div class="modal-header">
          <h3 class="modal-title">确认提交订单</h3>
          <button @click="$emit('update:visible', false)" class="modal-close">&times;</button>
        </div>

        <div class="modal-body">
          <!-- 订单摘要 -->
          <div class="mb-4 p-3 bg-info-subtle rounded-lg border border-primary">
            <div class="flex justify-between items-start mb-3">
              <div class="font-semibold text-lg text-primary">订单确认</div>
              <span :class="orderTypeBadges[orderConfirm.order_type] || 'badge badge-gray'">
                {{ orderTypeNames[orderConfirm.order_type] || orderConfirm.order_type }}
              </span>
            </div>
            <div class="grid form-grid grid-cols-2 gap-2 text-sm">
              <div><span class="text-secondary">客户:</span> <span class="font-medium">{{ orderConfirm.customer?.name || '-' }}</span></div>
              <div><span class="text-secondary">订单金额:</span> <span class="font-semibold text-lg text-primary">&yen;{{ fmt(orderConfirm.total) }}</span></div>
            </div>
          </div>

          <!-- 业务员选择 -->
          <div class="mb-4">
            <label class="label" for="order-confirm-employee">业务员（可选）</label>
            <select id="order-confirm-employee" v-model="orderConfirm.employee_id" class="input text-sm">
              <option value="">不指定业务员</option>
              <option v-for="s in employees" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>

          <!-- 商品明细表格 -->
          <div class="font-semibold mb-2 text-sm">商品明细（共{{ orderConfirm.items.length }}种商品）</div>
          <div class="mb-4 max-h-64 overflow-y-auto border rounded-lg">
            <table class="w-full text-sm">
              <thead class="bg-elevated sticky top-0">
                <tr>
                  <th class="px-3 py-2 text-left">商品</th>
                  <th class="px-3 py-2 text-left">出库仓位</th>
                  <th class="px-3 py-2 text-right">单价</th>
                  <th class="px-3 py-2 text-right">数量</th>
                  <th class="px-3 py-2 text-right">小计</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr v-for="(item, idx) in orderConfirm.items" :key="idx">
                  <td class="px-3 py-2"><div class="font-medium">{{ item.name }}</div></td>
                  <td class="px-3 py-2">
                    <span class="text-xs bg-info-subtle text-primary px-2 py-1 rounded">{{ item.warehouse_name }} - {{ item.location_code }}</span>
                  </td>
                  <td class="px-3 py-2 text-right">&yen;{{ fmt(item.unit_price) }}</td>
                  <td class="px-3 py-2 text-right font-medium">{{ item.quantity }}</td>
                  <td class="px-3 py-2 text-right font-semibold text-primary">&yen;{{ fmt(Math.round(item.unit_price * item.quantity * 100) / 100) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 退货退款勾选 -->
          <div v-if="orderConfirm.order_type === 'RETURN'" class="mb-4 p-3 bg-warning-subtle border border-warning rounded-lg">
            <label class="flex items-center cursor-pointer">
              <input type="checkbox" v-model="orderConfirm.refunded" class="mr-2 w-4 h-4">
              <span class="font-medium text-sm">已退款给客户</span>
            </label>
            <div class="text-xs text-secondary mt-2">
              <div class="mb-1"><b>已勾选</b>：货款已经退还给客户，不产生在账资金</div>
              <div><b>未勾选</b>：货款未退还，将形成客户的在账资金（预付款），下次购货时可以抵扣</div>
            </div>
            <!-- 退款方式和金额（勾选已退款时显示） -->
            <div v-if="orderConfirm.refunded" class="mt-3 space-y-2 border-t border-warning/30 pt-3">
              <div>
                <label class="text-xs text-secondary" for="refund-method">退款方式</label>
                <select id="refund-method" v-model="orderConfirm.refund_method" class="input text-sm mt-0.5">
                  <option v-for="pm in paymentMethods" :key="pm.code" :value="pm.code">{{ pm.name }}</option>
                </select>
              </div>
              <div>
                <label class="text-xs text-secondary" for="refund-amount">退款金额</label>
                <input id="refund-amount" v-model.number="orderConfirm.refund_amount" type="number" step="0.01" min="0" class="input text-sm mt-0.5" />
                <div class="text-xs text-muted mt-0.5">默认为订单总金额，可调整实际退款金额</div>
              </div>
            </div>
          </div>

          <!-- 在账资金勾选 -->
          <div v-if="orderConfirm.order_type === 'CASH' && orderConfirm.available_credit > 0" class="mb-4 p-3 bg-info-subtle border border-primary rounded-lg">
            <label class="flex items-center cursor-pointer">
              <input type="checkbox" v-model="orderConfirm.use_credit" class="mr-2 w-4 h-4">
              <span class="font-medium text-sm">使用在账资金</span>
            </label>
            <div class="text-xs text-secondary mt-2">
              <div class="mb-1">该客户有 <b class="text-primary">&yen;{{ fmt(orderConfirm.available_credit) }}</b> 在账资金可用</div>
              <div>勾选后将自动抵扣，最多抵扣 &yen;{{ fmt(Math.min(orderConfirm.available_credit, orderConfirm.total)) }}</div>
            </div>
          </div>

          <!-- 返利使用区域 -->
          <div
            v-if="['CASH', 'CREDIT', 'CONSIGN_SETTLE'].includes(orderConfirm.order_type) && orderConfirm.rebate_balance > 0"
            class="mb-4 p-3 bg-success-subtle border border-success rounded-lg"
          >
            <label class="flex items-center cursor-pointer mb-2">
              <input
                type="checkbox"
                v-model="orderConfirm.use_rebate"
                class="mr-2 w-4 h-4"
                @change="!orderConfirm.use_rebate && orderConfirm.items.forEach(i => i.rebate_amount = 0)"
              >
              <span class="font-medium text-sm">使用返利</span>
              <span class="text-xs text-success ml-2">可用: &yen;{{ fmt(orderConfirm.rebate_balance) }}</span>
            </label>
            <div v-if="orderConfirm.use_rebate">
              <!-- 返利明细表 -->
              <div class="max-h-48 overflow-y-auto border rounded-lg bg-surface">
                <table class="w-full text-xs">
                  <thead class="bg-elevated sticky top-0">
                    <tr>
                      <th class="px-2 py-1 text-left">商品</th>
                      <th class="px-2 py-1 text-right">数量</th>
                      <th class="px-2 py-1 text-right">原单价</th>
                      <th class="px-2 py-1 text-right">返利金额</th>
                      <th class="px-2 py-1 text-right">实际小计</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y">
                    <tr v-for="(item, idx) in orderConfirm.items" :key="idx">
                      <td class="px-2 py-1">{{ item.name }}</td>
                      <td class="px-2 py-1 text-right">{{ item.quantity }}</td>
                      <td class="px-2 py-1 text-right">&yen;{{ fmt(item.unit_price) }}</td>
                      <td class="px-2 py-1 text-right">
                        <input
                          v-model.number="item.rebate_amount"
                          type="number"
                          step="0.01"
                          min="0"
                          :max="item.unit_price * item.quantity"
                          class="w-20 text-right border rounded px-1 py-0.5 text-xs"
                          placeholder="0"
                        >
                      </td>
                      <td class="px-2 py-1 text-right font-semibold">&yen;{{ fmt(item.unit_price * item.quantity - (item.rebate_amount || 0)) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <!-- 返利合计 -->
              <div class="flex justify-between mt-2 text-sm">
                <span class="text-success">返利总额: <b>&yen;{{ fmt(rebateTotal) }}</b></span>
                <span class="font-semibold">抵扣后总额: <b class="text-primary">&yen;{{ fmt(orderConfirm.total - rebateTotal) }}</b></span>
              </div>
              <div v-if="rebateTotal > orderConfirm.rebate_balance" class="text-xs text-error mt-1">返利总额超过可用余额!</div>
            </div>
          </div>

          <!-- 收款方式选择（仅现款） -->
          <div v-if="orderConfirm.order_type === 'CASH'" class="mb-4">
            <label class="label">收款方式 *</label>
            <select v-model="orderConfirm.payment_method" class="input text-sm">
              <option v-for="pm in paymentMethods" :key="pm.code" :value="pm.code">{{ pm.name }}</option>
            </select>
          </div>

          <!-- 财务账套（自动推断，只读展示） -->
          <div v-if="accountSetInfo.count > 0" class="mb-4">
            <label class="label">财务账套</label>
            <!-- 单账套：显示名称 -->
            <div v-if="accountSetInfo.count === 1" class="text-sm font-medium px-3 py-2 bg-elevated rounded-lg border">
              {{ accountSetInfo.name }}
            </div>
            <!-- 多账套：警告横幅 -->
            <div v-else class="p-3 bg-warning-subtle border border-warning rounded-lg">
              <div class="text-sm font-semibold text-warning mb-1">本单包含多个账套的商品</div>
              <div class="text-xs text-secondary">财务将按账套分别生成应收单，共涉及 {{ accountSetInfo.count }} 个账套：{{ accountSetInfo.names.join('、') }}</div>
            </div>
          </div>
          <div v-else-if="orderConfirm.items?.length" class="mb-4">
            <label class="label">财务账套</label>
            <div class="text-xs text-warning">商品所在仓库未关联账套，发货后将不会自动生成财务单据</div>
          </div>

          <!-- 订单备注 -->
          <div class="mb-4">
            <label class="label">订单备注（可选）</label>
            <textarea v-model="orderConfirm.remark" class="input text-sm" rows="3" placeholder="输入订单备注信息..."></textarea>
            <div class="text-xs text-muted mt-1">备注信息将保存在订单中，可在订单详情中查看</div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex gap-3 pt-3">
            <button type="button" @click="$emit('update:visible', false)" class="btn btn-secondary flex-1">取消</button>
            <button type="button" @click="$emit('confirm')" :disabled="submitting" class="btn btn-primary flex-1">
              {{ submitting ? '提交中...' : '确认提交' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 订单确认弹窗组件
 * 所有确认数据通过 orderConfirm prop 直接修改（reactive 对象）
 */
import { computed } from 'vue'
import { useFormat } from '../../../composables/useFormat'
import { orderTypeNames, orderTypeBadges } from '../../../utils/constants'

const props = defineProps({
  /** 是否显示弹窗 */
  visible: Boolean,
  /** 订单确认数据（reactive 对象，可直接修改） */
  orderConfirm: Object,
  /** 业务员列表 */
  employees: Array,
  /** 收款方式列表 */
  paymentMethods: Array,
  /** 是否正在提交 */
  submitting: Boolean
})

const emit = defineEmits(['update:visible', 'confirm'])

const { fmt } = useFormat()

/** 返利总额 */
const rebateTotal = computed(() =>
  props.orderConfirm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0)
)

/** 账套信息（从订单行的仓库数据推断） */
const accountSetInfo = computed(() => {
  const items = props.orderConfirm.items || []
  const setMap = new Map()
  for (const item of items) {
    if (item.account_set_id) {
      setMap.set(item.account_set_id, item.account_set_name || `账套${item.account_set_id}`)
    }
  }
  const names = [...setMap.values()]
  return {
    count: setMap.size,
    name: names[0] || '',
    names,
    ids: [...setMap.keys()]
  }
})
</script>
