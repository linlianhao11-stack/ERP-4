<template>
  <div>
    <!-- 订单明细 / 欠款明细共用同一个组件 -->
    <FinanceOrdersTab
      :active="tab === 'orders' || tab === 'unpaid'"
      :tab="tab"
      ref="ordersTab"
      @data-changed="emit('data-changed')"
      @open-payment="openPayment"
    />
    <!-- 收款弹窗（保留在 UnpaidTab 中） -->
    <FinanceUnpaidTab
      v-show="false"
      ref="unpaidTab"
      @data-changed="emit('data-changed')"
    />
  </div>
</template>

<script setup>
/**
 * 财务订单面板 — 瘦容器
 * 订单明细和欠款明细共用 FinanceOrdersTab（通过 tab prop 区分）
 * FinanceUnpaidTab 仅保留收款弹窗功能
 */
import { ref } from 'vue'
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

// --- 转发方法 ---
/** 查看订单详情 */
const viewOrder = (id) => {
  ordersTab.value?.viewOrder(id)
}

/** 打开收款弹窗（转发到 UnpaidTab） */
const openPayment = () => {
  unpaidTab.value?.openPaymentModal()
}

/** 刷新 */
const refresh = () => {
  ordersTab.value?.refresh()
}

defineExpose({ refresh, viewOrder })
</script>
