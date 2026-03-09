<template>
  <div>
    <div class="flex gap-2 mb-3 border-b pb-2">
      <button role="tab" :aria-selected="sub === 'sales'" @click="sub = 'sales'" :class="['tab', sub === 'sales' ? 'active' : '']">销项发票</button>
      <button role="tab" :aria-selected="sub === 'purchase'" @click="sub = 'purchase'" :class="['tab', sub === 'purchase' ? 'active' : '']">进项发票</button>
    </div>
    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <SalesInvoiceTab v-if="sub === 'sales'" key="sales" />
      <PurchaseInvoiceTab v-else-if="sub === 'purchase'" key="purchase" />
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import SalesInvoiceTab from './SalesInvoiceTab.vue'
import PurchaseInvoiceTab from './PurchaseInvoiceTab.vue'

const sub = ref('sales')
</script>
