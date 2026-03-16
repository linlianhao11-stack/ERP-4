<template>
  <div>
    <div class="flex items-center gap-2 mb-3 border-b pb-2">
      <AppTabs v-model="sub" :tabs="[
        { value: 'bills', label: '应收单' },
        { value: 'receipts', label: '收款单' },
        { value: 'refunds', label: '收款退款' },
        { value: 'writeoffs', label: '应收核销' },
        { value: 'delivery', label: '出库单' },
        { value: 'returns', label: '销售退货' },
      ]" container-class="" />
      <button @click="showVoucherModal = true" class="ml-auto px-3 py-1.5 text-[12px] font-medium rounded-lg bg-purple-subtle text-purple-emphasis hover:bg-purple-subtle transition-colors shrink-0">
        批量生成凭证
      </button>
    </div>
    <ReceivableBillsTab v-if="sub === 'bills'" key="bills" :refresh-key="receivableRefreshKey" />
    <ReceiptBillsTab v-else-if="sub === 'receipts'" key="receipts" @data-changed="onSubTabDataChanged" />
    <ReceiptRefundBillsTab v-else-if="sub === 'refunds'" key="refunds" @data-changed="onSubTabDataChanged" />
    <WriteOffBillsTab v-else-if="sub === 'writeoffs'" key="writeoffs" @data-changed="onSubTabDataChanged" />
    <SalesDeliveryTab v-else-if="sub === 'delivery'" key="delivery" />
    <SalesReturnTab v-else-if="sub === 'returns'" key="returns" />

    <VoucherGenerateModal
      :visible="showVoucherModal"
      @update:visible="showVoucherModal = $event"
      mode="ar"
      :account-set-id="accountingStore.currentAccountSetId"
      @generated="onSubTabDataChanged"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppTabs from '../common/AppTabs.vue'
import { useAccountingStore } from '../../stores/accounting'
import ReceivableBillsTab from './ReceivableBillsTab.vue'
import ReceiptBillsTab from './ReceiptBillsTab.vue'
import ReceiptRefundBillsTab from './ReceiptRefundBillsTab.vue'
import WriteOffBillsTab from './WriteOffBillsTab.vue'
import SalesDeliveryTab from './SalesDeliveryTab.vue'
import SalesReturnTab from './SalesReturnTab.vue'
import VoucherGenerateModal from './VoucherGenerateModal.vue'

const accountingStore = useAccountingStore()
const sub = ref('bills')
const receivableRefreshKey = ref(0)
const showVoucherModal = ref(false)

function onSubTabDataChanged() {
  receivableRefreshKey.value++
}
</script>
