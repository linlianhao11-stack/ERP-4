<template>
  <div>
    <div class="flex items-center gap-2 mb-3 border-b pb-2">
      <AppTabs v-model="sub" :tabs="[
        { value: 'bills', label: '应付单' },
        { value: 'disbursements', label: '付款单' },
        { value: 'refunds', label: '付款退款' },
        { value: 'receipt', label: '入库单' },
        { value: 'returns', label: '采购退货' },
      ]" container-class="" />
      <button @click="showVoucherModal = true" class="ml-auto px-3 py-1.5 text-[12px] font-medium rounded-lg bg-purple-subtle text-purple-emphasis hover:bg-purple-subtle transition-colors shrink-0">
        批量生成凭证
      </button>
    </div>
    <PayableBillsTab v-if="sub === 'bills'" key="bills" :refresh-key="payableRefreshKey" />
    <DisbursementBillsTab v-else-if="sub === 'disbursements'" key="disbursements" @data-changed="onSubTabDataChanged" />
    <DisbursementRefundBillsTab v-else-if="sub === 'refunds'" key="refunds" @data-changed="onSubTabDataChanged" />
    <PurchaseReceiptTab v-else-if="sub === 'receipt'" key="receipt" />
    <PurchaseReturnTab v-else-if="sub === 'returns'" key="returns" />

    <VoucherGenerateModal
      :visible="showVoucherModal"
      @update:visible="showVoucherModal = $event"
      mode="ap"
      :account-set-id="accountingStore.currentAccountSetId"
      @generated="onSubTabDataChanged"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppTabs from '../common/AppTabs.vue'
import { useAccountingStore } from '../../stores/accounting'
import PayableBillsTab from './PayableBillsTab.vue'
import DisbursementBillsTab from './DisbursementBillsTab.vue'
import DisbursementRefundBillsTab from './DisbursementRefundBillsTab.vue'
import PurchaseReceiptTab from './PurchaseReceiptTab.vue'
import PurchaseReturnTab from './PurchaseReturnTab.vue'
import VoucherGenerateModal from './VoucherGenerateModal.vue'

const accountingStore = useAccountingStore()
const sub = ref('bills')
const payableRefreshKey = ref(0)
const showVoucherModal = ref(false)

function onSubTabDataChanged() { payableRefreshKey.value++ }
</script>
