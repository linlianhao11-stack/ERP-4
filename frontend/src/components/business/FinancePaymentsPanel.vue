<template>
  <div>
    <!-- Mobile cards -->
    <div class="md:hidden space-y-2">
      <div v-for="p in payments" :key="p.id" class="card p-3 cursor-pointer" @click="p.order_nos && p.order_nos.length ? $emit('view-order', p.order_nos[0].id) : null">
        <div class="flex justify-between items-start mb-2">
          <div class="min-w-0 flex-1 mr-3">
            <div class="font-medium flex items-center gap-2 truncate">{{ p.customer_name }} <span class="flex-shrink-0" :class="p.source === 'CASH' ? 'badge badge-blue' : 'badge badge-purple'" style="font-size:11px">{{ p.source === 'CASH' ? '现款' : '账期' }}</span></div>
            <div class="text-xs text-muted truncate">{{ p.payment_no }} · {{ getPaymentMethodName(p.payment_method) }} · {{ p.creator_name }}</div>
            <div v-if="p.order_nos && p.order_nos.length" class="text-xs text-muted mt-1">关联订单：<span v-for="(on, idx) in p.order_nos" :key="on.id"><span class="text-primary font-mono">{{ on.order_no }}</span><span v-if="idx < p.order_nos.length - 1">、</span></span></div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="text-lg font-bold text-success">+¥{{ fmt(p.amount) }}</div>
            <div class="text-xs text-muted">{{ fmtDate(p.created_at) }}</div>
          </div>
        </div>
        <div class="flex justify-end">
          <div v-if="p.is_confirmed" class="text-xs text-success whitespace-nowrap">已确认 · <span class="text-muted">{{ p.confirmed_by_name }}</span></div>
          <button v-else-if="hasPermission('finance_confirm')" @click.stop="confirmPaymentRecord(p.id, p.amount)" class="btn btn-warning btn-sm whitespace-nowrap">确认到账</button>
        </div>
      </div>
      <div v-if="!payments.length" class="p-8 text-center text-muted text-sm">暂无记录</div>
    </div>
    <!-- Desktop table -->
    <div class="card hidden md:block">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 text-left">收款单号</th>
              <th class="px-3 py-2 text-left">客户</th>
              <th class="px-3 py-2 text-center">类型</th>
              <th class="px-3 py-2 text-left">付款方式</th>
              <th class="px-3 py-2 text-right">金额</th>
              <th class="px-3 py-2 text-left">关联订单</th>
              <th class="px-3 py-2 text-center">状态</th>
              <th class="px-3 py-2 text-left">时间</th>
              <th class="px-3 py-2 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="p in payments" :key="p.id" class="hover:bg-elevated cursor-pointer" @click="p.order_nos && p.order_nos.length ? $emit('view-order', p.order_nos[0].id) : null">
              <td class="px-3 py-2 font-mono text-sm">{{ p.payment_no }}</td>
              <td class="px-3 py-2">{{ p.customer_name }}</td>
              <td class="px-3 py-2 text-center"><span :class="p.source === 'CASH' ? 'badge badge-blue' : 'badge badge-purple'" style="font-size:11px">{{ p.source === 'CASH' ? '现款' : '账期' }}</span></td>
              <td class="px-3 py-2">{{ getPaymentMethodName(p.payment_method) }}</td>
              <td class="px-3 py-2 text-right font-semibold text-success">+¥{{ fmt(p.amount) }}</td>
              <td class="px-3 py-2">
                <span v-if="p.order_nos && p.order_nos.length">
                  <span v-for="(on, idx) in p.order_nos" :key="on.id"><span class="text-primary font-mono text-xs">{{ on.order_no }}</span><span v-if="idx < p.order_nos.length - 1">、</span></span>
                </span>
                <span v-else class="text-muted text-xs">-</span>
              </td>
              <td class="px-3 py-2 text-center">
                <span v-if="p.is_confirmed" class="text-xs text-success">已确认</span>
                <span v-else class="text-xs text-warning">待确认</span>
              </td>
              <td class="px-3 py-2 text-muted text-xs">{{ fmtDate(p.created_at) }}</td>
              <td class="px-3 py-2 text-center">
                <span v-if="p.is_confirmed" class="text-xs text-muted">{{ p.confirmed_by_name }}</span>
                <button v-else-if="hasPermission('finance_confirm')" @click.stop="confirmPaymentRecord(p.id, p.amount)" class="btn btn-warning btn-sm text-xs">确认到账</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!payments.length" class="p-8 text-center text-muted text-sm">暂无记录</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../../stores/app'
import { useSettingsStore } from '../../stores/settings'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { getPayments, confirmPayment } from '../../api/finance'

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()

const paymentMethods = computed(() => settingsStore.paymentMethods)
const payments = ref([])

const emit = defineEmits(['view-order'])

const getPaymentMethodName = (m) => {
  const found = paymentMethods.value.find(p => p.code === m)
  if (found) return found.name
  return { cash: '现金', bank: '银行转账', bank_public: '对公转账', bank_private: '对私转账', wechat: '微信', alipay: '支付宝' }[m] || m
}

const loadPaymentsData = async () => {
  try {
    const { data } = await getPayments()
    payments.value = data
  } catch (e) {
    console.error(e)
    appStore.showToast(e.response?.data?.detail || '加载收款记录失败', 'error')
  }
}

const confirmPaymentRecord = async (id, amount) => {
  const confirmed = await appStore.customConfirm('确认到账', `确认该笔 ¥${Number(amount).toFixed(2)} 已到账？`)
  if (!confirmed) return
  try {
    await confirmPayment(id)
    appStore.showToast('确认成功')
    loadPaymentsData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}

defineExpose({ refresh: loadPaymentsData })

onMounted(() => { loadPaymentsData() })
</script>
