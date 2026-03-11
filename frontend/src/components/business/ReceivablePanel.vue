<template>
  <div>
    <div class="flex items-center gap-2 mb-3 border-b pb-2">
      <AppTabs v-model="sub" :tabs="[
        { value: 'bills', label: '应收单' },
        { value: 'receipts', label: '收款单' },
        { value: 'refunds', label: '收款退款' },
        { value: 'writeoffs', label: '应收核销' },
        { value: 'delivery', label: '出库单' },
      ]" container-class="" />
      <button @click="handleGenerateVouchers" :disabled="generating" class="ml-auto px-3 py-1.5 text-[12px] font-medium rounded-lg bg-purple-subtle text-purple-emphasis hover:bg-purple-subtle transition-colors shrink-0">
        {{ generating ? '生成中...' : '批量生成凭证' }}
      </button>
    </div>
    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <ReceivableBillsTab v-if="sub === 'bills'" key="bills" />
      <ReceiptBillsTab v-else-if="sub === 'receipts'" key="receipts" />
      <ReceiptRefundBillsTab v-else-if="sub === 'refunds'" key="refunds" />
      <WriteOffBillsTab v-else-if="sub === 'writeoffs'" key="writeoffs" />
      <SalesDeliveryTab v-else-if="sub === 'delivery'" key="delivery" />
    </Transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppTabs from '../common/AppTabs.vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { generateArVouchers } from '../../api/accounting'
import ReceivableBillsTab from './ReceivableBillsTab.vue'
import ReceiptBillsTab from './ReceiptBillsTab.vue'
import ReceiptRefundBillsTab from './ReceiptRefundBillsTab.vue'
import WriteOffBillsTab from './WriteOffBillsTab.vue'
import SalesDeliveryTab from './SalesDeliveryTab.vue'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const sub = ref('bills')
const generating = ref(false)

const handleGenerateVouchers = async () => {
  const setId = accountingStore.currentAccountSetId
  const period = accountingStore.currentAccountSet?.current_period
  if (!setId || !period) {
    appStore.showToast('请先选择账套和期间', 'error')
    return
  }
  if (!await appStore.customConfirm('确认操作', `确认为当前期间 ${period} 批量生成应收凭证？`)) return
  generating.value = true
  try {
    const { data } = await generateArVouchers(setId, period)
    if (data.length === 0) {
      appStore.showToast('无需生成凭证（已确认单据均已生成凭证）', 'info')
    } else {
      appStore.showToast(`成功生成 ${data.length} 张应收凭证`, 'success')
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '生成凭证失败', 'error')
  } finally {
    generating.value = false
  }
}
</script>
