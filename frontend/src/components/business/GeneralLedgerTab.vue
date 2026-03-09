<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="selectedAccountId" class="input input-sm w-64" @change="query">
        <option :value="null" disabled>选择科目</option>
        <option v-for="a in leafAccounts" :key="a.id" :value="a.id">
          {{ a.code }} {{ a.name }}
        </option>
      </select>
      <input type="month" v-model="startPeriod" class="input input-sm w-36" @change="query">
      <span class="text-[13px] text-muted">至</span>
      <input type="month" v-model="endPeriod" class="input input-sm w-36" @change="query">
      <button @click="query" class="btn btn-primary btn-sm" :disabled="!selectedAccountId">查询</button>
      <button v-if="data" @click="handleExport" class="btn btn-secondary btn-sm">导出 Excel</button>
    </div>

    <div v-if="data" class="table-container">
      <div class="text-center text-[15px] font-semibold mb-2">
        总分类账 — {{ data.account_code }} {{ data.account_name }}
      </div>
      <table class="w-full text-[13px]">
        <thead>
          <tr>
            <th class="w-24">日期</th>
            <th class="w-48">凭证号</th>
            <th>摘要</th>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
            <th class="w-12 text-center">方向</th>
            <th class="w-28 text-right">余额</th>
          </tr>
        </thead>
        <tbody>
          <tr class="bg-canvas">
            <td></td><td></td>
            <td class="font-medium">期初余额</td>
            <td></td><td></td>
            <td class="text-center">{{ data.opening_direction }}</td>
            <td class="text-right">{{ fmt(data.opening_balance) }}</td>
          </tr>
          <tr v-for="(e, idx) in data.entries" :key="idx">
            <td>{{ e.date }}</td>
            <td class="text-blue-600 cursor-pointer hover:underline" @click="$emit('viewVoucher', e.voucher_id)">{{ e.voucher_no }}</td>
            <td>{{ e.summary }}</td>
            <td class="text-right">{{ fmt(e.debit) }}</td>
            <td class="text-right">{{ fmt(e.credit) }}</td>
            <td class="text-center">{{ e.direction }}</td>
            <td class="text-right">{{ fmt(e.balance) }}</td>
          </tr>
          <tr class="bg-canvas font-semibold">
            <td></td><td></td>
            <td>本期合计</td>
            <td class="text-right">{{ fmt(data.period_debit_total) }}</td>
            <td class="text-right">{{ fmt(data.period_credit_total) }}</td>
            <td></td><td></td>
          </tr>
          <tr class="bg-canvas font-semibold">
            <td></td><td></td>
            <td>期末余额</td>
            <td></td><td></td>
            <td class="text-center">{{ data.closing_direction }}</td>
            <td class="text-right">{{ fmt(data.closing_balance) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="data.entries.length === 0" class="text-center text-muted py-4 text-[13px]">
        本期无发生额
      </div>
    </div>
    <div v-else class="text-center text-muted py-12 text-[14px]">
      请选择科目和期间后点击查询
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { getGeneralLedger, exportGeneralLedger } from '../../api/accounting'

defineEmits(['viewVoucher'])

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const selectedAccountId = ref(null)
const now = new Date()
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const startPeriod = ref(currentMonth)
const endPeriod = ref(currentMonth)
const data = ref(null)

const leafAccounts = computed(() =>
  accountingStore.chartOfAccounts.filter(a => a.is_leaf)
)

const fmt = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const query = async () => {
  if (!selectedAccountId.value || !accountingStore.currentAccountSetId) return
  try {
    const { data: res } = await getGeneralLedger({
      account_set_id: accountingStore.currentAccountSetId,
      account_id: selectedAccountId.value,
      start_period: startPeriod.value,
      end_period: endPeriod.value,
    })
    data.value = res
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  }
}

const handleExport = async () => {
  try {
    const res = await exportGeneralLedger({
      account_set_id: accountingStore.currentAccountSetId,
      account_id: selectedAccountId.value,
      start_period: startPeriod.value,
      end_period: endPeriod.value,
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `总分类账_${data.value.account_code}_${startPeriod.value}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}

onMounted(() => accountingStore.loadChartOfAccounts())
</script>
