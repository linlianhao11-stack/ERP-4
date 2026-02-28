<template>
  <div>
    <div class="flex items-center gap-2 mb-3 border-b pb-2">
      <span @click="sub = 'bills'" :class="['tab', sub === 'bills' ? 'active' : '']">应付单</span>
      <span @click="sub = 'disbursements'" :class="['tab', sub === 'disbursements' ? 'active' : '']">付款单</span>
      <span @click="sub = 'refunds'" :class="['tab', sub === 'refunds' ? 'active' : '']">付款退款</span>
      <span @click="sub = 'receipt'" :class="['tab', sub === 'receipt' ? 'active' : '']">入库单</span>
      <button @click="handleGenerateVouchers" :disabled="generating" class="ml-auto px-3 py-1.5 text-[12px] font-medium rounded-lg bg-[#f0e6fa] text-[#7d2ae8] hover:bg-[#e8d5f5] transition-colors">
        {{ generating ? '生成中...' : '批量生成凭证' }}
      </button>
    </div>
    <PayableBillsTab v-if="sub === 'bills'" />
    <DisbursementBillsTab v-if="sub === 'disbursements'" />
    <DisbursementRefundBillsTab v-if="sub === 'refunds'" />
    <PurchaseReceiptTab v-if="sub === 'receipt'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { generateApVouchers } from '../../api/accounting'
import PayableBillsTab from './PayableBillsTab.vue'
import DisbursementBillsTab from './DisbursementBillsTab.vue'
import DisbursementRefundBillsTab from './DisbursementRefundBillsTab.vue'
import PurchaseReceiptTab from './PurchaseReceiptTab.vue'

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
  if (!confirm(`确认为当前期间 ${period} 批量生成应付凭证？`)) return
  generating.value = true
  try {
    const { data } = await generateApVouchers(setId, period)
    if (data.length === 0) {
      appStore.showToast('无需生成凭证（已确认单据均已生成凭证）', 'info')
    } else {
      appStore.showToast(`成功生成 ${data.length} 张应付凭证`, 'success')
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '生成凭证失败', 'error')
  } finally {
    generating.value = false
  }
}
</script>
