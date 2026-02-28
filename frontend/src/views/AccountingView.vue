<template>
  <div>
    <!-- 账套切换器 -->
    <div class="flex items-center gap-3 mb-4">
      <span class="text-[13px] text-[#86868b]">当前账套</span>
      <div class="flex gap-2">
        <button
          v-for="s in accountingStore.accountSets"
          :key="s.id"
          @click="switchAccountSet(s.id)"
          :class="[
            'px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-200',
            s.id === accountingStore.currentAccountSetId
              ? 'bg-[#0071e3] text-white shadow-sm'
              : 'bg-[#f5f5f7] text-[#1d1d1f] hover:bg-[#e8e8ed]'
          ]"
        >
          {{ s.name }}
        </button>
      </div>
      <span v-if="accountingStore.currentAccountSet" class="text-[12px] text-[#86868b]">
        当前期间: {{ accountingStore.currentAccountSet.current_period }}
      </span>
    </div>

    <!-- Tab Navigation -->
    <div class="flex flex-wrap gap-2 mb-3 border-b pb-2">
      <span @click="tab = 'vouchers'" :class="['tab', tab === 'vouchers' ? 'active' : '']">凭证管理</span>
      <span @click="tab = 'accounts'" :class="['tab', tab === 'accounts' ? 'active' : '']">科目管理</span>
      <span @click="tab = 'periods'" :class="['tab', tab === 'periods' ? 'active' : '']">会计期间</span>
      <span @click="tab = 'receivables'" :class="['tab', tab === 'receivables' ? 'active' : '']">应收管理</span>
      <span @click="tab = 'payables'" :class="['tab', tab === 'payables' ? 'active' : '']">应付管理</span>
    </div>

    <!-- No account set selected -->
    <div v-if="!accountingStore.currentAccountSetId" class="text-center py-20 text-[#86868b]">
      <p class="text-[15px]">请先选择或创建账套</p>
    </div>

    <!-- Panels -->
    <template v-else>
      <VoucherPanel v-if="tab === 'vouchers'" />
      <ChartOfAccountsPanel v-if="tab === 'accounts'" />
      <AccountingPeriodsPanel v-if="tab === 'periods'" />
      <ReceivablePanel v-if="tab === 'receivables'" />
      <PayablePanel v-if="tab === 'payables'" />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAccountingStore } from '../stores/accounting'
import VoucherPanel from '../components/business/VoucherPanel.vue'
import ChartOfAccountsPanel from '../components/business/ChartOfAccountsPanel.vue'
import AccountingPeriodsPanel from '../components/business/AccountingPeriodsPanel.vue'
import ReceivablePanel from '../components/business/ReceivablePanel.vue'
import PayablePanel from '../components/business/PayablePanel.vue'

const accountingStore = useAccountingStore()
const tab = ref('vouchers')

const switchAccountSet = (id) => {
  accountingStore.setCurrentAccountSet(id)
}

onMounted(() => {
  accountingStore.loadAccountSets()
})
</script>
