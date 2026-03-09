<template>
  <div>
    <div class="flex gap-2 mb-3 border-b pb-2">
      <button role="tab" :aria-selected="sub === 'general'" @click="sub = 'general'" :class="['tab', sub === 'general' ? 'active' : '']">总分类账</button>
      <button role="tab" :aria-selected="sub === 'detail'" @click="sub = 'detail'" :class="['tab', sub === 'detail' ? 'active' : '']">明细分类账</button>
      <button role="tab" :aria-selected="sub === 'trial'" @click="sub = 'trial'" :class="['tab', sub === 'trial' ? 'active' : '']">科目余额表</button>
    </div>
    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <GeneralLedgerTab v-if="sub === 'general'" key="general" @viewVoucher="$emit('viewVoucher', $event)" />
      <DetailLedgerTab v-else-if="sub === 'detail'" key="detail" @viewVoucher="$emit('viewVoucher', $event)" />
      <TrialBalanceTab v-else-if="sub === 'trial'" key="trial" />
    </Transition>
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
