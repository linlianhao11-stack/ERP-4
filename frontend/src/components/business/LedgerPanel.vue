<template>
  <div>
    <div class="flex gap-2 mb-3 border-b pb-2">
      <span @click="sub = 'general'" :class="['tab', sub === 'general' ? 'active' : '']">总分类账</span>
      <span @click="sub = 'detail'" :class="['tab', sub === 'detail' ? 'active' : '']">明细分类账</span>
      <span @click="sub = 'trial'" :class="['tab', sub === 'trial' ? 'active' : '']">科目余额表</span>
    </div>
    <GeneralLedgerTab v-if="sub === 'general'" @viewVoucher="$emit('viewVoucher', $event)" />
    <DetailLedgerTab v-if="sub === 'detail'" @viewVoucher="$emit('viewVoucher', $event)" />
    <TrialBalanceTab v-if="sub === 'trial'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import GeneralLedgerTab from './GeneralLedgerTab.vue'
import DetailLedgerTab from './DetailLedgerTab.vue'
import TrialBalanceTab from './TrialBalanceTab.vue'

defineEmits(['viewVoucher'])
const sub = ref('general')
</script>
