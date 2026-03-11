<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="selectedAccountId" class="toolbar-select" @change="onAccountChange">
            <option :value="null" disabled>选择科目</option>
            <option v-for="a in leafAccounts" :key="a.id" :value="a.id">
              {{ a.code }} {{ a.name }}
            </option>
          </select>
          <input type="month" v-model="startPeriod" class="toolbar-select">
          <span class="text-[13px] text-muted">至</span>
          <input type="month" v-model="endPeriod" class="toolbar-select">
          <select v-if="showCustomerFilter" v-model="customerId" class="toolbar-select">
            <option :value="null">全部客户</option>
            <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select v-if="showSupplierFilter" v-model="supplierId" class="toolbar-select">
            <option :value="null">全部供应商</option>
            <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </template>
        <template #actions>
          <button @click="query" class="btn btn-primary btn-sm" :disabled="!selectedAccountId">查询</button>
          <button v-if="data" @click="handleExport" class="btn btn-secondary btn-sm">导出 Excel</button>
        </template>
      </PageToolbar>

      <div v-if="data" class="table-container">
        <div class="text-center text-[15px] font-semibold mb-2 mt-2">
          明细分类账 — {{ data.account_code }} {{ data.account_name }}
        </div>
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 w-24">日期</th>
              <th class="px-3 py-2 w-48">凭证号</th>
              <th class="px-3 py-2">摘要</th>
              <th v-if="data.aux_customer" class="px-3 py-2 w-28">客户</th>
              <th v-if="data.aux_supplier" class="px-3 py-2 w-28">供应商</th>
              <th class="px-3 py-2 w-28 text-right">借方</th>
              <th class="px-3 py-2 w-28 text-right">贷方</th>
              <th class="px-3 py-2 w-12 text-center">方向</th>
              <th class="px-3 py-2 w-28 text-right">余额</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr class="bg-canvas">
              <td class="px-3 py-2"></td><td class="px-3 py-2"></td>
              <td class="px-3 py-2 font-medium">期初余额</td>
              <td v-if="data.aux_customer" class="px-3 py-2"></td>
              <td v-if="data.aux_supplier" class="px-3 py-2"></td>
              <td class="px-3 py-2"></td><td class="px-3 py-2"></td>
              <td class="px-3 py-2 text-center">{{ data.opening_direction }}</td>
              <td class="px-3 py-2 text-right">{{ fmt(data.opening_balance) }}</td>
            </tr>
            <tr v-for="(e, idx) in data.entries" :key="idx" class="hover:bg-elevated">
              <td class="px-3 py-2">{{ e.date }}</td>
              <td class="px-3 py-2 text-blue-600 cursor-pointer hover:underline" @click="$emit('viewVoucher', e.voucher_id)">{{ e.voucher_no }}</td>
              <td class="px-3 py-2">{{ e.summary }}</td>
              <td v-if="data.aux_customer" class="px-3 py-2">{{ e.customer_name || '' }}</td>
              <td v-if="data.aux_supplier" class="px-3 py-2">{{ e.supplier_name || '' }}</td>
              <td class="px-3 py-2 text-right">{{ fmt(e.debit) }}</td>
              <td class="px-3 py-2 text-right">{{ fmt(e.credit) }}</td>
              <td class="px-3 py-2 text-center">{{ e.direction }}</td>
              <td class="px-3 py-2 text-right">{{ fmt(e.balance) }}</td>
            </tr>
            <tr class="bg-canvas font-semibold">
              <td class="px-3 py-2"></td><td class="px-3 py-2"></td>
              <td class="px-3 py-2">本期合计</td>
              <td v-if="data.aux_customer" class="px-3 py-2"></td>
              <td v-if="data.aux_supplier" class="px-3 py-2"></td>
              <td class="px-3 py-2 text-right">{{ fmt(data.period_debit_total) }}</td>
              <td class="px-3 py-2 text-right">{{ fmt(data.period_credit_total) }}</td>
              <td class="px-3 py-2"></td><td class="px-3 py-2"></td>
            </tr>
            <tr class="bg-canvas font-semibold">
              <td class="px-3 py-2"></td><td class="px-3 py-2"></td>
              <td class="px-3 py-2">期末余额</td>
              <td v-if="data.aux_customer" class="px-3 py-2"></td>
              <td v-if="data.aux_supplier" class="px-3 py-2"></td>
              <td class="px-3 py-2"></td><td class="px-3 py-2"></td>
              <td class="px-3 py-2 text-center">{{ data.closing_direction }}</td>
              <td class="px-3 py-2 text-right">{{ fmt(data.closing_balance) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="text-center text-muted py-12 text-[14px]">
        请选择科目和期间后点击查询
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PageToolbar from '../common/PageToolbar.vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { getDetailLedger, exportDetailLedger } from '../../api/accounting'
import api from '../../api/index'

defineEmits(['viewVoucher'])

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const selectedAccountId = ref(null)
const now = new Date()
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const startPeriod = ref(currentMonth)
const endPeriod = ref(currentMonth)
const customerId = ref(null)
const supplierId = ref(null)
const data = ref(null)
const customers = ref([])
const suppliers = ref([])

const leafAccounts = computed(() =>
  accountingStore.chartOfAccounts.filter(a => a.is_leaf)
)

const selectedAccount = computed(() =>
  leafAccounts.value.find(a => a.id === selectedAccountId.value)
)
const showCustomerFilter = computed(() => selectedAccount.value?.aux_customer)
const showSupplierFilter = computed(() => selectedAccount.value?.aux_supplier)

const fmt = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const onAccountChange = () => {
  customerId.value = null
  supplierId.value = null
  data.value = null
}

const query = async () => {
  if (!selectedAccountId.value || !accountingStore.currentAccountSetId) return
  try {
    const params = {
      account_set_id: accountingStore.currentAccountSetId,
      account_id: selectedAccountId.value,
      start_period: startPeriod.value,
      end_period: endPeriod.value,
    }
    if (customerId.value) params.customer_id = customerId.value
    if (supplierId.value) params.supplier_id = supplierId.value
    const { data: res } = await getDetailLedger(params)
    data.value = res
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  }
}

const handleExport = async () => {
  try {
    const params = {
      account_set_id: accountingStore.currentAccountSetId,
      account_id: selectedAccountId.value,
      start_period: startPeriod.value,
      end_period: endPeriod.value,
    }
    if (customerId.value) params.customer_id = customerId.value
    if (supplierId.value) params.supplier_id = supplierId.value
    const res = await exportDetailLedger(params)
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `明细分类账_${data.value.account_code}_${startPeriod.value}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}

onMounted(async () => {
  await accountingStore.loadChartOfAccounts()
  try {
    const [custRes, supRes] = await Promise.all([
      api.get('/customers'), api.get('/suppliers')
    ])
    customers.value = custRes.data?.items || custRes.data || []
    suppliers.value = supRes.data?.items || supRes.data || []
  } catch (e) { /* ignore */ }
})
</script>
