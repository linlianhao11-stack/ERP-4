<template>
  <div>
    <AppTabs v-model="sub" :tabs="[
      { value: 'sales', label: '销项发票' },
      { value: 'purchase', label: '进项发票' },
    ]" container-class="mb-4" />
    <SalesInvoiceTab v-if="sub === 'sales'" key="sales" />
    <PurchaseInvoiceTab v-else-if="sub === 'purchase'" key="purchase" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppTabs from '../common/AppTabs.vue'
import SalesInvoiceTab from './SalesInvoiceTab.vue'
import PurchaseInvoiceTab from './PurchaseInvoiceTab.vue'

const sub = ref('sales')
</script>
