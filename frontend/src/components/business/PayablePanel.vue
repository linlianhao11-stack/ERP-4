<template>
  <div>
    <div class="flex gap-2 mb-3 border-b pb-2">
      <span @click="sub = 'bills'" :class="['tab', sub === 'bills' ? 'active' : '']">应付单</span>
      <span @click="sub = 'disbursements'" :class="['tab', sub === 'disbursements' ? 'active' : '']">付款单</span>
      <span @click="sub = 'refunds'" :class="['tab', sub === 'refunds' ? 'active' : '']">付款退款</span>
    </div>
    <PayableBillsTab v-if="sub === 'bills'" />
    <DisbursementBillsTab v-if="sub === 'disbursements'" />
    <DisbursementRefundBillsTab v-if="sub === 'refunds'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import PayableBillsTab from './PayableBillsTab.vue'
import DisbursementBillsTab from './DisbursementBillsTab.vue'
import DisbursementRefundBillsTab from './DisbursementRefundBillsTab.vue'

const sub = ref('bills')
</script>
