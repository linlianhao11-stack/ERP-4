<template>
  <div class="card" style="overflow: visible">
    <PageToolbar>
      <template #filters>
        <input type="month" v-model="periodName" class="toolbar-select w-36">
        <button @click="query" class="btn btn-primary btn-sm">查询</button>
        <button v-if="data" @click="handleExport" class="btn btn-secondary btn-sm">导出 Excel</button>
        <span v-if="data" :class="data.is_balanced ? 'text-success' : 'text-error'" class="text-[13px] font-medium ml-2">
          {{ data.is_balanced ? '试算平衡' : '试算不平衡！' }}
        </span>
      </template>
    </PageToolbar>

    <div v-if="data" class="table-container">
      <table class="w-full text-sm">
        <thead class="bg-elevated">
          <tr>
            <th rowspan="2" class="px-2 py-2 w-24">科目编码</th>
            <th rowspan="2" class="px-2 py-2">科目名称</th>
            <th colspan="2" class="px-2 py-2 text-center border-b-0">期初余额</th>
            <th colspan="2" class="px-2 py-2 text-center border-b-0">本期发生额</th>
            <th colspan="2" class="px-2 py-2 text-center border-b-0">期末余额</th>
          </tr>
          <tr>
            <th class="px-2 py-2 w-28 text-right">借方</th>
            <th class="px-2 py-2 w-28 text-right">贷方</th>
            <th class="px-2 py-2 w-28 text-right">借方</th>
            <th class="px-2 py-2 w-28 text-right">贷方</th>
            <th class="px-2 py-2 w-28 text-right">借方</th>
            <th class="px-2 py-2 w-28 text-right">贷方</th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr v-for="a in data.accounts" :key="a.code" :class="{ 'font-semibold bg-canvas': !a.is_leaf }">
            <td class="px-2 py-2">{{ a.code }}</td>
            <td class="px-2 py-2" :style="{ paddingLeft: (a.level - 1) * 16 + 8 + 'px' }">{{ a.name }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(a.opening_debit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(a.opening_credit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(a.period_debit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(a.period_credit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(a.closing_debit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(a.closing_credit) }}</td>
          </tr>
          <tr v-if="data.accounts.length === 0">
            <td colspan="8" class="px-2 py-2 text-center text-muted py-8">暂无数据</td>
          </tr>
        </tbody>
        <tfoot v-if="data.accounts.length > 0">
          <tr class="font-bold bg-elevated">
            <td class="px-2 py-2"></td>
            <td class="px-2 py-2">合  计</td>
            <td class="px-2 py-2 text-right">{{ fmt(data.totals.opening_debit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(data.totals.opening_credit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(data.totals.period_debit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(data.totals.period_credit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(data.totals.closing_debit) }}</td>
            <td class="px-2 py-2 text-right">{{ fmt(data.totals.closing_credit) }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
    <div v-else class="text-center text-muted py-12 text-[14px]">
      选择期间后点击查询
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import PageToolbar from '../common/PageToolbar.vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { getTrialBalance, exportTrialBalance } from '../../api/accounting'
import { downloadBlob } from '../../composables/useDownload'

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
    downloadBlob(res.data, `科目余额表_${periodName.value}.xlsx`)
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}
</script>
