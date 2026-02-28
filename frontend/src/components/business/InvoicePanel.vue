<template>
  <div>
    <div class="flex gap-2 mb-3 border-b pb-2">
      <span @click="sub = 'sales'" :class="['tab', sub === 'sales' ? 'active' : '']">销项发票</span>
      <span @click="sub = 'purchase'" :class="['tab', sub === 'purchase' ? 'active' : '']">进项发票</span>
    </div>
    <SalesInvoiceTab v-if="sub === 'sales'" />
    <PurchaseInvoiceTab v-if="sub === 'purchase'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import SalesInvoiceTab from './SalesInvoiceTab.vue'
import PurchaseInvoiceTab from './PurchaseInvoiceTab.vue'

const sub = ref('sales')
</script>
