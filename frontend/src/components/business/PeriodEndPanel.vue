<template>
  <div>
    <!-- 期间选择 + 状态卡片 -->
    <div class="flex flex-wrap items-start gap-4 mb-5">
      <!-- 期间选择器 -->
      <div class="flex items-center gap-2">
        <label class="label mb-0">选择期间</label>
        <select v-model="selectedPeriod" class="toolbar-select" @change="onPeriodChange">
          <option value="">请选择</option>
          <option v-for="p in periodOptions" :key="p.period_name" :value="p.period_name">{{ p.period_name }}</option>
        </select>
      </div>

      <!-- 当前期间状态卡片 -->
      <div v-if="selectedPeriodObj" class="flex-1 bg-elevated rounded-xl p-4 flex items-center justify-between min-w-[280px]">
        <div>
          <div class="text-[15px] font-semibold text-foreground">{{ selectedPeriodObj.period_name }}</div>
          <div class="text-[12px] text-muted mt-0.5">
            {{ selectedPeriodObj.year }}年第{{ selectedPeriodObj.month }}期
          </div>
        </div>
        <span :class="selectedPeriodObj.is_closed ? 'badge badge-red' : 'badge badge-green'">
          {{ selectedPeriodObj.is_closed ? '已结账' : '未结账' }}
        </span>
      </div>
    </div>

    <template v-if="selectedPeriod">
      <!-- 1. 损益结转区域 -->
      <div class="bg-elevated rounded-xl p-5 mb-4">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-[15px] font-semibold text-foreground">损益结转</h4>
          <div class="flex gap-2">
            <button @click="handlePreview" class="btn btn-secondary btn-sm" :disabled="loading.preview">
              {{ loading.preview ? '预览中...' : '预览结转' }}
            </button>
            <button
              v-if="hasPermission('period_end') && previewData && previewData.entries && previewData.entries.length > 0 && !previewData.already_exists"
              @click="handleExecute"
              class="btn btn-primary btn-sm"
              :disabled="loading.execute"
            >
              {{ loading.execute ? '执行中...' : '确认执行' }}
            </button>
          </div>
        </div>

        <!-- 已存在提示 -->
        <div v-if="previewData && previewData.already_exists" class="p-3 bg-orange-subtle rounded-lg text-[13px] text-orange-emphasis">
          该期间已存在损益结转凭证，凭证号：<span class="font-semibold">{{ previewData.voucher_no }}</span>
        </div>

        <!-- 执行结果 -->
        <div v-if="carryForwardResult" class="p-3 bg-success-subtle rounded-lg text-[13px] text-success-emphasis mb-3">
          <template v-if="carryForwardResult.already_existed">
            结转凭证已存在，凭证号：<span class="font-semibold">{{ carryForwardResult.voucher_no }}</span>
          </template>
          <template v-else>
            结转成功！凭证号：<span class="font-semibold">{{ carryForwardResult.voucher_no }}</span>，
            本期利润：<span class="font-semibold">{{ carryForwardResult.total_profit }}</span>
          </template>
        </div>

        <!-- 预览表格 -->
        <div v-if="previewData && previewData.entries && previewData.entries.length > 0 && !previewData.already_exists" class="table-container mt-3">
          <table class="w-full text-sm">
            <thead>
              <tr>
                <th>科目编码</th>
                <th>科目名称</th>
                <th class="text-right">借方金额</th>
                <th class="text-right">贷方金额</th>
                <th>摘要</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(e, idx) in previewData.entries" :key="idx">
                <td>{{ e.account_code }}</td>
                <td>{{ e.account_name }}</td>
                <td class="text-right">{{ formatAmt(e.debit_amount) }}</td>
                <td class="text-right">{{ formatAmt(e.credit_amount) }}</td>
                <td>{{ e.summary }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="font-semibold">
                <td colspan="2" class="text-right">本期利润（贷方净额）</td>
                <td colspan="3">{{ previewData.total_profit }}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        <!-- 无结转分录 -->
        <div v-if="previewData && !previewData.already_exists && previewData.entries && previewData.entries.length === 0" class="text-center py-4 text-[13px] text-muted">
          本期无损益类科目发生额，无需结转
        </div>
      </div>

      <!-- 2. 结账检查区域 -->
      <div class="bg-elevated rounded-xl p-5 mb-4">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-[15px] font-semibold text-foreground">结账检查</h4>
          <div class="flex gap-2">
            <button @click="handleCloseCheck" class="btn btn-secondary btn-sm" :disabled="loading.check">
              {{ loading.check ? '检查中...' : '执行检查' }}
            </button>
            <button
              v-if="hasPermission('period_end') && allChecksPassed && !selectedPeriodObj?.is_closed"
              @click="handleClosePeriod"
              class="btn btn-primary btn-sm"
              :disabled="loading.close"
            >
              {{ loading.close ? '结账中...' : '结账' }}
            </button>
          </div>
        </div>

        <!-- 检查结果清单 -->
        <div v-if="checkItems.length > 0" class="space-y-2">
          <div
            v-for="(item, idx) in checkItems"
            :key="idx"
            :class="[
              'flex items-start gap-3 p-3 rounded-lg text-[13px]',
              item.passed ? 'bg-success-subtle' : 'bg-error-subtle'
            ]"
          >
            <span :class="item.passed ? 'text-success-emphasis' : 'text-error-emphasis'" class="text-[16px] font-bold shrink-0 mt-px">
              {{ item.passed ? '\u2713' : '\u2717' }}
            </span>
            <div>
              <div :class="item.passed ? 'text-success-emphasis' : 'text-error-emphasis'" class="font-medium">{{ item.label }}</div>
              <div class="text-[12px] mt-0.5" :class="item.passed ? 'text-success-emphasis/70' : 'text-error-emphasis/70'">{{ item.detail }}</div>
            </div>
          </div>
        </div>

        <!-- 结账成功提示 -->
        <div v-if="closeResult" class="p-3 bg-success-subtle rounded-lg text-[13px] text-success-emphasis mt-3">
          {{ closeResult.already_closed ? '该期间已结账' : `期间 ${closeResult.period_name} 结账成功` }}
        </div>
      </div>

      <!-- 3. 年度结转区域（仅12月） -->
      <div v-if="selectedMonth === 12" class="bg-elevated rounded-xl p-5 mb-4">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-[15px] font-semibold text-foreground">年度结转</h4>
          <button v-if="hasPermission('period_end')" @click="handleYearClose" class="btn btn-primary btn-sm" :disabled="loading.yearClose">
            {{ loading.yearClose ? '结转中...' : '年度结转' }}
          </button>
        </div>
        <p class="text-[13px] text-muted mb-2">
          将本年利润（4103）结转至利润分配-未分配利润（4104），并初始化下一年度会计期间。
        </p>

        <div v-if="yearCloseResult" class="p-3 bg-success-subtle rounded-lg text-[13px] text-success-emphasis">
          <template v-if="yearCloseResult.already_existed">
            年度结转凭证已存在，凭证号：<span class="font-semibold">{{ yearCloseResult.voucher_no }}</span>
          </template>
          <template v-else-if="yearCloseResult.voucher_no">
            年度结转成功！凭证号：<span class="font-semibold">{{ yearCloseResult.voucher_no }}</span>，
            净利润：<span class="font-semibold">{{ yearCloseResult.net_profit }}</span>
            <span v-if="yearCloseResult.next_year_periods_created > 0">，
              已初始化 {{ yearCloseResult.next_year_periods_created }} 个下年度会计期间
            </span>
          </template>
          <template v-else>
            {{ yearCloseResult.message || '年度结转完成' }}
          </template>
        </div>
      </div>

      <!-- 4. 反结账按钮（admin + 已结账） -->
      <div v-if="hasPermission('period_end') && selectedPeriodObj?.is_closed" class="bg-elevated rounded-xl p-5 mb-4">
        <div class="flex items-center justify-between">
          <div>
            <h4 class="text-[15px] font-semibold text-foreground">反结账</h4>
            <p class="text-[13px] text-muted mt-1">解锁已结账期间，允许继续录入和修改凭证。</p>
          </div>
          <button @click="handleReopen" class="btn btn-sm px-3 py-1.5 rounded-lg text-[13px] font-medium bg-error-subtle text-error-emphasis hover:bg-error-subtle transition-colors" :disabled="loading.reopen">
            {{ loading.reopen ? '处理中...' : '反结账' }}
          </button>
        </div>
        <div v-if="reopenResult" class="p-3 bg-success-subtle rounded-lg text-[13px] text-success-emphasis mt-3">
          期间 {{ reopenResult.period_name }} 已成功反结账
        </div>
      </div>
    </template>

    <!-- 5. 期间历史列表 -->
    <div class="mt-5">
      <div class="flex items-center justify-between mb-3">
        <h4 class="text-[15px] font-semibold text-foreground">期间列表</h4>
        <div class="flex items-center gap-2">
          <label class="label mb-0 text-[12px]">年度</label>
          <select v-model.number="listYear" class="toolbar-select" @change="loadPeriodList">
            <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
          </select>
        </div>
      </div>
      <div class="card" style="overflow: visible">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-2 py-2">期间</th>
              <th class="px-2 py-2">年</th>
              <th class="px-2 py-2">月</th>
              <th class="px-2 py-2">状态</th>
              <th class="px-2 py-2">结账时间</th>
              <th class="px-2 py-2">结账人</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="p in periodList" :key="p.period_name">
              <td class="px-2 py-2 font-medium">{{ p.period_name }}</td>
              <td class="px-2 py-2">{{ p.year }}</td>
              <td class="px-2 py-2">{{ p.month }}</td>
              <td class="px-2 py-2">
                <span :class="p.is_closed ? 'badge badge-red' : 'badge badge-green'">
                  {{ p.is_closed ? '已结账' : '未结账' }}
                </span>
              </td>
              <td class="px-2 py-2">{{ p.closed_at ? formatDate(p.closed_at) : '-' }}</td>
              <td class="px-2 py-2">{{ p.closed_by || '-' }}</td>
            </tr>
            <tr v-if="periodList.length === 0">
              <td colspan="6" class="px-2 py-2 text-center text-muted py-8">暂无期间数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAuthStore } from '../../stores/auth'
import { useAppStore } from '../../stores/app'
import { usePermission } from '../../composables/usePermission'
import {
  getAccountingPeriods,
  previewCarryForward,
  executeCarryForward,
  closeCheck,
  closePeriod,
  reopenPeriod,
  yearClose,
} from '../../api/accounting'

const accountingStore = useAccountingStore()
const authStore = useAuthStore()
const appStore = useAppStore()

const { hasPermission } = usePermission()

// --- 期间选择 ---
const selectedPeriod = ref('')
const periodOptions = ref([])
const periodList = ref([])
const listYear = ref(new Date().getFullYear())

const yearOptions = computed(() => {
  const cur = new Date().getFullYear()
  return Array.from({ length: 5 }, (_, i) => cur - 2 + i)
})

const selectedPeriodObj = computed(() =>
  periodOptions.value.find(p => p.period_name === selectedPeriod.value)
)

const selectedMonth = computed(() => {
  if (!selectedPeriod.value) return 0
  const parts = selectedPeriod.value.split('-')
  return parseInt(parts[1])
})

// --- 加载期间 ---
async function loadPeriodOptions() {
  if (!accountingStore.currentAccountSetId) return
  try {
    const { data } = await getAccountingPeriods(accountingStore.currentAccountSetId)
    periodOptions.value = data.items || data || []
    // 默认选当前期间
    if (!selectedPeriod.value && accountingStore.currentAccountSet?.current_period) {
      selectedPeriod.value = accountingStore.currentAccountSet.current_period
    }
  } catch (e) { /* ignore */ }
}

async function loadPeriodList() {
  if (!accountingStore.currentAccountSetId) return
  try {
    const { data } = await getAccountingPeriods(accountingStore.currentAccountSetId, listYear.value)
    periodList.value = data.items || data || []
  } catch (e) { /* ignore */ }
}

function onPeriodChange() {
  // 重置状态
  previewData.value = null
  carryForwardResult.value = null
  checkItems.value = []
  closeResult.value = null
  yearCloseResult.value = null
  reopenResult.value = null
}

// --- 损益结转 ---
const previewData = ref(null)
const carryForwardResult = ref(null)

const loading = ref({
  preview: false,
  execute: false,
  check: false,
  close: false,
  yearClose: false,
  reopen: false,
})

async function handlePreview() {
  if (!selectedPeriod.value) return
  loading.value.preview = true
  carryForwardResult.value = null
  try {
    const { data } = await previewCarryForward(accountingStore.currentAccountSetId, selectedPeriod.value)
    previewData.value = data
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '预览失败', 'error')
  } finally {
    loading.value.preview = false
  }
}

async function handleExecute() {
  if (!selectedPeriod.value) return
  loading.value.execute = true
  try {
    const { data } = await executeCarryForward(accountingStore.currentAccountSetId, selectedPeriod.value)
    carryForwardResult.value = data
    previewData.value = null
    appStore.showToast('损益结转成功', 'success')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '执行失败', 'error')
  } finally {
    loading.value.execute = false
  }
}

// --- 结账检查 ---
const checkItems = ref([])
const closeResult = ref(null)

const allChecksPassed = computed(() =>
  checkItems.value.length > 0 && checkItems.value.every(i => i.passed)
)

async function handleCloseCheck() {
  if (!selectedPeriod.value) return
  loading.value.check = true
  closeResult.value = null
  try {
    const { data } = await closeCheck(accountingStore.currentAccountSetId, selectedPeriod.value)
    checkItems.value = data.checks || []
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '检查失败', 'error')
  } finally {
    loading.value.check = false
  }
}

async function handleClosePeriod() {
  if (!selectedPeriod.value) return
  const ok = await appStore.customConfirm('确认结账？', `将锁定期间 ${selectedPeriod.value}，结账后不可在该期间录入或修改凭证。`)
  if (!ok) return
  loading.value.close = true
  try {
    const { data } = await closePeriod(accountingStore.currentAccountSetId, selectedPeriod.value)
    closeResult.value = data
    appStore.showToast('结账成功', 'success')
    await loadPeriodOptions()
    await loadPeriodList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '结账失败', 'error')
  } finally {
    loading.value.close = false
  }
}

// --- 年度结转 ---
const yearCloseResult = ref(null)

async function handleYearClose() {
  if (!selectedPeriod.value) return
  const year = parseInt(selectedPeriod.value.split('-')[0])
  const ok = await appStore.customConfirm('确认年度结转？', `将结转 ${year} 年度本年利润至利润分配，并初始化 ${year + 1} 年度会计期间。`)
  if (!ok) return
  loading.value.yearClose = true
  try {
    const { data } = await yearClose(accountingStore.currentAccountSetId, year)
    yearCloseResult.value = data
    appStore.showToast('年度结转成功', 'success')
    await loadPeriodOptions()
    await loadPeriodList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '年度结转失败', 'error')
  } finally {
    loading.value.yearClose = false
  }
}

// --- 反结账 ---
const reopenResult = ref(null)

async function handleReopen() {
  if (!selectedPeriod.value) return
  const ok = await appStore.customConfirm('确认反结账？', `将解锁期间 ${selectedPeriod.value}，允许继续录入和修改凭证。`)
  if (!ok) return
  loading.value.reopen = true
  try {
    const { data } = await reopenPeriod(accountingStore.currentAccountSetId, selectedPeriod.value)
    reopenResult.value = data
    appStore.showToast('反结账成功', 'success')
    await loadPeriodOptions()
    await loadPeriodList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '反结账失败', 'error')
  } finally {
    loading.value.reopen = false
  }
}

// --- 工具函数 ---
function formatAmt(val) {
  if (!val || val === '0') return '-'
  const n = parseFloat(val)
  return isNaN(n) ? val : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(dt) {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN')
}

// --- 生命周期 ---
watch(() => accountingStore.currentAccountSetId, () => {
  selectedPeriod.value = ''
  onPeriodChange()
  loadPeriodOptions()
  loadPeriodList()
})

onMounted(() => {
  loadPeriodOptions()
  loadPeriodList()
})
</script>
