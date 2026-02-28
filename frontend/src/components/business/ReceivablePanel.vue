<template>
  <div>
    <div class="flex gap-2 mb-3 border-b pb-2">
      <span @click="sub = 'bills'" :class="['tab', sub === 'bills' ? 'active' : '']">应收单</span>
      <span @click="sub = 'receipts'" :class="['tab', sub === 'receipts' ? 'active' : '']">收款单</span>
      <span @click="sub = 'refunds'" :class="['tab', sub === 'refunds' ? 'active' : '']">收款退款</span>
      <span @click="sub = 'writeoffs'" :class="['tab', sub === 'writeoffs' ? 'active' : '']">应收核销</span>
    </div>
    <ReceivableBillsTab v-if="sub === 'bills'" />
    <ReceiptBillsTab v-if="sub === 'receipts'" />
    <ReceiptRefundBillsTab v-if="sub === 'refunds'" />
    <WriteOffBillsTab v-if="sub === 'writeoffs'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ReceivableBillsTab from './ReceivableBillsTab.vue'
import ReceiptBillsTab from './ReceiptBillsTab.vue'
import ReceiptRefundBillsTab from './ReceiptRefundBillsTab.vue'
import WriteOffBillsTab from './WriteOffBillsTab.vue'

const sub = ref('bills')
</script>
