<template>
  <div>
    <!-- 订单明细 Tab -->
    <FinanceOrdersTab
      v-show="tab === 'orders'"
      :active="tab === 'orders'"
      ref="ordersTab"
      @data-changed="emit('data-changed')"
      @open-payment="openPayment"
    />
    <!-- 欠款明细 Tab -->
    <FinanceUnpaidTab
      v-show="tab === 'unpaid'"
      :active="tab === 'unpaid'"
      ref="unpaidTab"
      @data-changed="emit('data-changed')"
      @view-order="viewOrder"
    />
  </div>
</template>

<script setup>
/**
 * 财务订单面板 — 瘦容器
 * 负责在"订单明细"和"欠款明细"两个 Tab 之间切换，
 * 并将 FinanceView 的调用链转发到对应子组件。
 */
import { ref, watch } from 'vue'
import FinanceOrdersTab from './finance/FinanceOrdersTab.vue'
import FinanceUnpaidTab from './finance/FinanceUnpaidTab.vue'

const props = defineProps({
  /** 当前激活的 Tab 名称：'orders' | 'unpaid' */
  tab: { type: String, default: 'orders' }
})

const emit = defineEmits(['data-changed'])

// 子组件引用
const ordersTab = ref(null)
const unpaidTab = ref(null)

// --- Tab 切换时刷新对应子组件 ---
watch(() => props.tab, (val) => {
  if (val === 'orders') ordersTab.value?.refresh()
  else if (val === 'unpaid') unpaidTab.value?.refresh()
})

// --- 转发方法 ---
/** 查看订单详情（转发到订单 Tab） */
const viewOrder = (id) => {
  ordersTab.value?.viewOrder(id)
}

/** 打开收款弹窗（转发到欠款 Tab） */
const openPayment = () => {
  unpaidTab.value?.openPaymentModal()
}

/** 刷新指定或全部 Tab */
const refresh = (tabName) => {
  if (tabName === 'orders') ordersTab.value?.refresh()
  else if (tabName === 'unpaid') unpaidTab.value?.refresh()
  else {
    ordersTab.value?.refresh()
    unpaidTab.value?.refresh()
  }
}

defineExpose({ refresh, viewOrder })
</script>
