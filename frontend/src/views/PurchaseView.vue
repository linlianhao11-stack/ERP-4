<template>
  <div>
    <!-- Tabs -->
    <AppTabs v-model="purchaseTab" :tabs="[
      { value: 'orders', label: '采购订单' },
      { value: 'returns', label: '退货单' },
      { value: 'suppliers', label: '供应商管理' },
      { value: 'materials', label: '物料管理' }
    ]" container-class="mb-4" />

    <!-- Panels -->
    <PurchaseOrdersPanel
      v-if="purchaseTab === 'orders'"
      key="orders"
      ref="ordersPanel"
      @data-changed="onOrdersDataChanged"
    />
    <PurchaseReturnTab
      v-else-if="purchaseTab === 'returns'"
      key="returns"
    />
    <PurchaseSuppliersPanel
      v-else-if="purchaseTab === 'suppliers'"
      key="suppliers"
      ref="suppliersPanel"
      @view-order="handleViewOrder"
      @data-changed="onSuppliersDataChanged"
    />
    <MaterialsTab
      v-else-if="purchaseTab === 'materials'"
      key="materials"
    />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppTabs from '../components/common/AppTabs.vue'
import PurchaseOrdersPanel from '../components/business/PurchaseOrdersPanel.vue'
import PurchaseSuppliersPanel from '../components/business/PurchaseSuppliersPanel.vue'
const PurchaseReturnTab = defineAsyncComponent(() => import('../components/business/purchase/PurchaseReturnTab.vue'))
const MaterialsTab = defineAsyncComponent(() => import('../components/business/purchase/MaterialsTab.vue'))

const route = useRoute()
const router = useRouter()

const validTabs = ['orders', 'returns', 'suppliers', 'materials']
const purchaseTab = ref(validTabs.includes(route.query.tab) ? route.query.tab : 'orders')
watch(purchaseTab, (val) => router.replace({ query: { ...route.query, tab: val === 'orders' ? undefined : val } }))
const ordersPanel = ref(null)
const suppliersPanel = ref(null)

const handleViewOrder = async (orderId) => {
  purchaseTab.value = 'orders'
  await nextTick()
  ordersPanel.value?.viewPurchaseOrder(orderId)
}

const onOrdersDataChanged = () => {
  suppliersPanel.value?.refresh()
}

const onSuppliersDataChanged = () => {
  ordersPanel.value?.refresh()
}

onMounted(async () => {
  if (route.query.action === 'receive') {
    await nextTick()
    ordersPanel.value?.openPurchaseReceive()
    router.replace({ path: '/purchase' })
  }
})
</script>
