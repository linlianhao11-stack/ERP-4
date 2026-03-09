<template>
  <div>
    <!-- 查询栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <label class="label mb-0">期间</label>
      <select v-model.number="queryYear" class="input input-sm w-24">
        <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
      </select>
      <span class="text-[13px] text-muted">年</span>
      <select v-model.number="queryMonth" class="input input-sm w-20">
        <option v-for="m in 12" :key="m" :value="m">{{ m }}</option>
      </select>
      <span class="text-[13px] text-muted">月</span>
      <button @click="handleQuery" class="btn btn-primary btn-sm" :disabled="loading">
        {{ loading ? '查询中...' : '查询' }}
      </button>
    </div>

    <!-- 子Tab -->
    <div class="flex gap-2 mb-3 border-b pb-2">
      <span @click="sub = 'balance-sheet'" :class="['tab', sub === 'balance-sheet' ? 'active' : '']">资产负债表</span>
      <span @click="sub = 'income'" :class="['tab', sub === 'income' ? 'active' : '']">利润表</span>
      <span @click="sub = 'cash-flow'" :class="['tab', sub === 'cash-flow' ? 'active' : '']">现金流量表</span>

      <!-- 导出按钮 -->
      <div class="ml-auto relative" v-if="hasData">
        <button @click="showExportMenu = !showExportMenu" class="btn btn-secondary btn-sm flex items-center gap-1">
          导出 <span class="text-[10px]">&#9660;</span>
        </button>
        <div v-if="showExportMenu" class="absolute right-0 top-full mt-1 bg-surface rounded-lg shadow-lg border border-line py-1 z-10 min-w-[120px]">
          <button @click="handleExport('excel')" class="w-full text-left px-3 py-1.5 text-[13px] hover:bg-elevated transition-colors">导出 Excel</button>
          <button @click="handleExport('pdf')" class="w-full text-left px-3 py-1.5 text-[13px] hover:bg-elevated transition-colors">导出 PDF</button>
        </div>
      </div>
    </div>

    <!-- 报表内容 -->
    <BalanceSheetTab v-if="sub === 'balance-sheet'" :data="balanceSheetData" />
    <IncomeStatementTab v-if="sub === 'income'" :data="incomeData" />
    <CashFlowTab v-if="sub === 'cash-flow'" :data="cashFlowData" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import {
  getBalanceSheet,
  getIncomeStatement,
  getCashFlow,
  exportBalanceSheet,
  exportIncomeStatement,
  exportCashFlow,
} from '../../api/accounting'
import BalanceSheetTab from './BalanceSheetTab.vue'
import IncomeStatementTab from './IncomeStatementTab.vue'
import CashFlowTab from './CashFlowTab.vue'

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const sub = ref('balance-sheet')
const loading = ref(false)

const now = new Date()
const queryYear = ref(now.getFullYear())
const queryMonth = ref(now.getMonth() + 1)

const balanceSheetData = ref(null)
const incomeData = ref(null)
const cashFlowData = ref(null)

const showExportMenu = ref(false)

const yearOptions = computed(() => {
  const cur = new Date().getFullYear()
  return Array.from({ length: 5 }, (_, i) => cur - 2 + i)
})

const periodName = computed(() => `${queryYear.value}-${String(queryMonth.value).padStart(2, '0')}`)

const hasData = computed(() => {
  if (sub.value === 'balance-sheet') return !!balanceSheetData.value
  if (sub.value === 'income') return !!incomeData.value
  if (sub.value === 'cash-flow') return !!cashFlowData.value
  return false
})

async function handleQuery() {
  if (!accountingStore.currentAccountSetId) return
  loading.value = true
  const params = {
    account_set_id: accountingStore.currentAccountSetId,
    period_name: periodName.value,
  }
  try {
    const [bs, is, cf] = await Promise.all([
      getBalanceSheet(params),
      getIncomeStatement(params),
      getCashFlow(params),
    ])
    balanceSheetData.value = bs.data
    incomeData.value = is.data
    cashFlowData.value = cf.data
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  } finally {
    loading.value = false
  }
}

async function handleExport(format) {
  showExportMenu.value = false
  if (!accountingStore.currentAccountSetId) return

  const params = {
    account_set_id: accountingStore.currentAccountSetId,
    period_name: periodName.value,
    format,
  }

  const exportMap = {
    'balance-sheet': { fn: exportBalanceSheet, name: '资产负债表' },
    'income': { fn: exportIncomeStatement, name: '利润表' },
    'cash-flow': { fn: exportCashFlow, name: '现金流量表' },
  }

  const cfg = exportMap[sub.value]
  if (!cfg) return

  try {
    const resp = await cfg.fn(params)
    const ext = format === 'pdf' ? 'pdf' : 'xlsx'
    const blob = new Blob([resp.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${cfg.name}_${periodName.value}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
    appStore.showToast(`${cfg.name}导出成功`, 'success')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '导出失败', 'error')
  }
}

// 点击外部关闭导出菜单
function handleClickOutside(e) {
  if (showExportMenu.value) {
    showExportMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside, true)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside, true)
})
</script>
