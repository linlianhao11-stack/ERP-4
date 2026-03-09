<template>
  <div>
    <!-- Tabs -->
    <AppTabs v-model="purchaseTab" :tabs="[
      { value: 'orders', label: '采购订单' },
      { value: 'suppliers', label: '供应商管理' }
    ]" container-class="mb-4" />

    <!-- Panels -->
    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <PurchaseOrdersPanel
        v-if="purchaseTab === 'orders'"
        key="orders"
        ref="ordersPanel"
        @data-changed="onOrdersDataChanged"
      />
      <PurchaseSuppliersPanel
        v-else-if="purchaseTab === 'suppliers'"
        key="suppliers"
        ref="suppliersPanel"
        @view-order="handleViewOrder"
        @data-changed="onSuppliersDataChanged"
      />
    </Transition>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppTabs from '../components/common/AppTabs.vue'
import PurchaseOrdersPanel from '../components/business/PurchaseOrdersPanel.vue'
import PurchaseSuppliersPanel from '../components/business/PurchaseSuppliersPanel.vue'

const route = useRoute()
const router = useRouter()

const purchaseTab = ref('orders')
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
