<template>
  <div>
    <!-- Tab Navigation -->
    <div class="flex flex-wrap gap-2 mb-3 border-b pb-2">
      <span @click="financeTab = 'orders'" :class="['tab', financeTab === 'orders' ? 'active' : '']">订单明细</span>
      <span @click="financeTab = 'unpaid'" :class="['tab', financeTab === 'unpaid' ? 'active' : '']">欠款明细</span>
      <span @click="financeTab = 'payments'" :class="['tab', financeTab === 'payments' ? 'active' : '']">收款管理</span>
      <span v-if="hasPermission('purchase_pay') || hasPermission('finance_pay')" @click="financeTab = 'payables'" :class="['tab', financeTab === 'payables' ? 'active' : '']">付款管理</span>
      <span @click="financeTab = 'logs'" :class="['tab', financeTab === 'logs' ? 'active' : '']">出入库日志</span>
      <span @click="financeTab = 'rebates'" :class="['tab', financeTab === 'rebates' ? 'active' : '']">返利管理</span>
    </div>

    <!-- Panels -->
    <FinanceOrdersPanel
      v-show="financeTab === 'orders' || financeTab === 'unpaid'"
      :tab="financeTab"
      ref="ordersPanel"
      @data-changed="onOrdersDataChanged"
    />
    <FinancePaymentsPanel
      v-if="financeTab === 'payments'"
      ref="paymentsPanel"
      @view-order="handleViewOrder"
    />
    <FinancePayablesPanel
      v-if="financeTab === 'payables'"
    />
    <FinanceLogsPanel
      v-if="financeTab === 'logs'"
    />
    <FinanceRebatesPanel
      v-if="financeTab === 'rebates'"
      :accountSets="accountingStore.accountSets"
    />
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useCustomersStore } from '../stores/customers'
import { useSettingsStore } from '../stores/settings'
import { useAccountingStore } from '../stores/accounting'
import { usePermission } from '../composables/usePermission'
import FinanceOrdersPanel from '../components/business/FinanceOrdersPanel.vue'
import FinancePaymentsPanel from '../components/business/FinancePaymentsPanel.vue'
import FinancePayablesPanel from '../components/business/FinancePayablesPanel.vue'
import FinanceLogsPanel from '../components/business/FinanceLogsPanel.vue'
import FinanceRebatesPanel from '../components/business/FinanceRebatesPanel.vue'

const route = useRoute()
const customersStore = useCustomersStore()
const settingsStore = useSettingsStore()
const accountingStore = useAccountingStore()
const { hasPermission } = usePermission()

const financeTab = ref('orders')
const ordersPanel = ref(null)
const paymentsPanel = ref(null)

const handleViewOrder = async (orderId) => {
  financeTab.value = 'orders'
  await nextTick()
  ordersPanel.value?.viewOrder(orderId)
}

const needsRefresh = ref({})

const onOrdersDataChanged = () => {
  needsRefresh.value.payments = true
}

watch(financeTab, (newTab) => {
  if (needsRefresh.value[newTab]) {
    nextTick(() => {
      if (newTab === 'payments') paymentsPanel.value?.refresh()
      delete needsRefresh.value[newTab]
    })
  }
})

onMounted(async () => {
  customersStore.loadCustomers()
  settingsStore.loadPaymentMethods()
  settingsStore.loadDisbursementMethods()
  accountingStore.loadAccountSets()

  // 支持从仪表盘等页面通过 ?orderId=X 穿透查看订单详情
  const orderId = route.query.orderId
  if (orderId) {
    financeTab.value = 'orders'
    await nextTick()
    ordersPanel.value?.viewOrder(Number(orderId))
  }
})
</script>
