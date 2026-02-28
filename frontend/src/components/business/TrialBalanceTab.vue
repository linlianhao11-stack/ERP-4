<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <input type="month" v-model="periodName" class="input input-sm w-36">
      <button @click="query" class="btn btn-primary btn-sm">查询</button>
      <button v-if="data" @click="handleExport" class="btn btn-secondary btn-sm">导出 Excel</button>
      <span v-if="data" :class="data.is_balanced ? 'text-green-600' : 'text-red-500'" class="text-[13px] font-medium ml-2">
        {{ data.is_balanced ? '试算平衡' : '试算不平衡！' }}
      </span>
    </div>

    <div v-if="data" class="table-container">
      <table class="w-full text-[13px]">
        <thead>
          <tr>
            <th rowspan="2" class="w-24">科目编码</th>
            <th rowspan="2">科目名称</th>
            <th colspan="2" class="text-center border-b-0">期初余额</th>
            <th colspan="2" class="text-center border-b-0">本期发生额</th>
            <th colspan="2" class="text-center border-b-0">期末余额</th>
          </tr>
          <tr>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in data.accounts" :key="a.code" :class="{ 'font-semibold bg-[#f9f9fb]': !a.is_leaf }">
            <td>{{ a.code }}</td>
            <td :style="{ paddingLeft: (a.level - 1) * 16 + 8 + 'px' }">{{ a.name }}</td>
            <td class="text-right">{{ fmt(a.opening_debit) }}</td>
            <td class="text-right">{{ fmt(a.opening_credit) }}</td>
            <td class="text-right">{{ fmt(a.period_debit) }}</td>
            <td class="text-right">{{ fmt(a.period_credit) }}</td>
            <td class="text-right">{{ fmt(a.closing_debit) }}</td>
            <td class="text-right">{{ fmt(a.closing_credit) }}</td>
          </tr>
          <tr v-if="data.accounts.length === 0">
            <td colspan="8" class="text-center text-[#86868b] py-8">暂无数据</td>
          </tr>
        </tbody>
        <tfoot v-if="data.accounts.length > 0">
          <tr class="font-bold bg-[#f5f5f7]">
            <td></td>
            <td>合  计</td>
            <td class="text-right">{{ fmt(data.totals.opening_debit) }}</td>
            <td class="text-right">{{ fmt(data.totals.opening_credit) }}</td>
            <td class="text-right">{{ fmt(data.totals.period_debit) }}</td>
            <td class="text-right">{{ fmt(data.totals.period_credit) }}</td>
            <td class="text-right">{{ fmt(data.totals.closing_debit) }}</td>
            <td class="text-right">{{ fmt(data.totals.closing_credit) }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
    <div v-else class="text-center text-[#86868b] py-12 text-[14px]">
      选择期间后点击查询
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { getTrialBalance, exportTrialBalance } from '../../api/accounting'

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const now = new Date()
const periodName = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const data = ref(null)

const fmt = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const query = async () => {
  if (!accountingStore.currentAccountSetId) return
  try {
    const { data: res } = await getTrialBalance({
      account_set_id: accountingStore.currentAccountSetId,
      period_name: periodName.value,
    })
    data.value = res
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  }
}

const handleExport = async () => {
  try {
    const res = await exportTrialBalance({
      account_set_id: accountingStore.currentAccountSetId,
      period_name: periodName.value,
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `科目余额表_${periodName.value}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}
</script>
