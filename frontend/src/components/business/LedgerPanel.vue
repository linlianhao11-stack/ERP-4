<template>
  <div>
    <AppTabs v-model="sub" :tabs="[
      { value: 'general', label: '总分类账' },
      { value: 'detail', label: '明细分类账' },
      { value: 'trial', label: '科目余额表' },
    ]" container-class="mb-4" />
    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <GeneralLedgerTab v-if="sub === 'general'" key="general" @viewVoucher="$emit('viewVoucher', $event)" />
      <DetailLedgerTab v-else-if="sub === 'detail'" key="detail" @viewVoucher="$emit('viewVoucher', $event)" />
      <TrialBalanceTab v-else-if="sub === 'trial'" key="trial" />
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppTabs from '../common/AppTabs.vue'
import GeneralLedgerTab from './GeneralLedgerTab.vue'
import DetailLedgerTab from './DetailLedgerTab.vue'
import TrialBalanceTab from './TrialBalanceTab.vue'

defineEmits(['viewVoucher'])
const sub = ref('general')
</script>
