<template>
  <div>
    <div class="flex items-center gap-2 mb-3 border-b pb-2">
      <span @click="sub = 'bills'" :class="['tab', sub === 'bills' ? 'active' : '']">应收单</span>
      <span @click="sub = 'receipts'" :class="['tab', sub === 'receipts' ? 'active' : '']">收款单</span>
      <span @click="sub = 'refunds'" :class="['tab', sub === 'refunds' ? 'active' : '']">收款退款</span>
      <span @click="sub = 'writeoffs'" :class="['tab', sub === 'writeoffs' ? 'active' : '']">应收核销</span>
      <span @click="sub = 'delivery'" :class="['tab', sub === 'delivery' ? 'active' : '']">出库单</span>
      <button @click="handleGenerateVouchers" :disabled="generating" class="ml-auto px-3 py-1.5 text-[12px] font-medium rounded-lg bg-[#f0e6fa] text-[#7d2ae8] hover:bg-[#e8d5f5] transition-colors">
        {{ generating ? '生成中...' : '批量生成凭证' }}
      </button>
    </div>
    <ReceivableBillsTab v-if="sub === 'bills'" />
    <ReceiptBillsTab v-if="sub === 'receipts'" />
    <ReceiptRefundBillsTab v-if="sub === 'refunds'" />
    <WriteOffBillsTab v-if="sub === 'writeoffs'" />
    <SalesDeliveryTab v-if="sub === 'delivery'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
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
  if (!confirm(`确认为当前期间 ${period} 批量生成应收凭证？`)) return
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
