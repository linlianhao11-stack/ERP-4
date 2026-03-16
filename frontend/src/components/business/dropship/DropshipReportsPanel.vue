<template>
  <div>
    <!-- 子 Tab 切换 -->
    <div class="flex items-center border-b mb-4 gap-0">
      <button type="button" v-for="t in subTabs" :key="t.value"
        :class="['tab', activeSubTab === t.value ? 'active' : '']"
        @click="activeSubTab = t.value">
        {{ t.label }}
      </button>
    </div>

    <!-- 月度汇总 -->
    <div v-if="activeSubTab === 'summary'">
      <div class="card">
        <div class="page-toolbar">
          <div class="page-toolbar-inner">
            <div class="page-toolbar-filters">
              <input type="month" v-model="summaryMonth" @change="loadSummary" class="toolbar-select" style="min-width:140px">
              <SegmentedControl
                v-model="summaryDimension"
                :options="[{value:'customer', label:'按客户'}, {value:'supplier', label:'按供应商'}]"
                @update:model-value="loadSummary"
              />
            </div>
          </div>
        </div>
        <div class="table-container">
          <table class="w-full text-sm">
            <thead class="bg-elevated">
              <tr>
                <th class="px-3 py-2 text-left">{{ summaryDimension === 'customer' ? '客户' : '供应商' }}</th>
                <th class="px-3 py-2 text-right">订单数</th>
                <th class="px-3 py-2 text-right">采购额</th>
                <th class="px-3 py-2 text-right">销售额</th>
                <th class="px-3 py-2 text-right">毛利</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr v-for="(row, i) in summaryData" :key="i" class="hover:bg-elevated">
                <td class="px-3 py-2">{{ row.name }}</td>
                <td class="px-3 py-2 text-right">{{ row.order_count }}</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(row.purchase_total) }}</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(row.sale_total) }}</td>
                <td class="px-3 py-2 text-right" :class="Number(row.gross_profit) >= 0 ? 'text-success' : 'text-error'">
                  ¥{{ fmtMoney(row.gross_profit) }}
                </td>
              </tr>
            </tbody>
            <tfoot v-if="summaryData.length" class="bg-elevated font-semibold text-sm">
              <tr>
                <td class="px-3 py-2">合计</td>
                <td class="px-3 py-2 text-right">{{ summaryTotals.order_count }}</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(summaryTotals.purchase_total) }}</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(summaryTotals.sale_total) }}</td>
                <td class="px-3 py-2 text-right" :class="summaryTotals.gross_profit >= 0 ? 'text-success' : 'text-error'">
                  ¥{{ fmtMoney(summaryTotals.gross_profit) }}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div v-if="summaryLoading" class="p-6 text-center text-muted text-sm">加载中...</div>
        <div v-else-if="!summaryData.length" class="p-6 text-center text-muted text-sm">暂无数据</div>
      </div>
    </div>

    <!-- 毛利分析 -->
    <div v-if="activeSubTab === 'profit'">
      <div class="card">
        <div class="page-toolbar">
          <div class="page-toolbar-inner">
            <div class="page-toolbar-filters">
              <label class="text-xs text-muted whitespace-nowrap">开始</label>
              <input type="date" v-model="profitStart" @change="loadProfit" class="toolbar-select">
              <label class="text-xs text-muted whitespace-nowrap">结束</label>
              <input type="date" v-model="profitEnd" @change="loadProfit" class="toolbar-select">
            </div>
          </div>
        </div>
        <div class="table-container">
          <table class="w-full text-sm">
            <thead class="bg-elevated">
              <tr>
                <th class="px-3 py-2 text-left">单号</th>
                <th class="px-3 py-2 text-left">商品</th>
                <th class="px-3 py-2 text-left">供应商</th>
                <th class="px-3 py-2 text-left">客户</th>
                <th class="px-3 py-2 text-right">采购额</th>
                <th class="px-3 py-2 text-right">销售额</th>
                <th class="px-3 py-2 text-right">毛利</th>
                <th class="px-3 py-2 text-right">毛利率</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr v-for="row in profitData" :key="row.id" class="hover:bg-elevated">
                <td class="px-3 py-2 font-mono text-xs">{{ row.ds_no }}</td>
                <td class="px-3 py-2">{{ row.product_name }}</td>
                <td class="px-3 py-2">{{ row.supplier_name }}</td>
                <td class="px-3 py-2">{{ row.customer_name }}</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(row.purchase_total) }}</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(row.sale_total) }}</td>
                <td class="px-3 py-2 text-right" :class="Number(row.gross_profit) >= 0 ? 'text-success' : 'text-error'">
                  ¥{{ fmtMoney(row.gross_profit) }}
                </td>
                <td class="px-3 py-2 text-right text-muted">
                  {{ row.gross_margin != null ? Number(row.gross_margin).toFixed(1) + '%' : '-' }}
                </td>
              </tr>
            </tbody>
            <tfoot v-if="profitData.length" class="bg-elevated font-semibold text-sm">
              <tr>
                <td class="px-3 py-2" colspan="4">汇总</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(profitTotals.purchase_total) }}</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(profitTotals.sale_total) }}</td>
                <td class="px-3 py-2 text-right" :class="profitTotals.gross_profit >= 0 ? 'text-success' : 'text-error'">
                  ¥{{ fmtMoney(profitTotals.gross_profit) }}
                </td>
                <td class="px-3 py-2 text-right text-muted">
                  {{ profitTotals.avg_margin }}%
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div v-if="profitLoading" class="p-6 text-center text-muted text-sm">加载中...</div>
        <div v-else-if="!profitData.length" class="p-6 text-center text-muted text-sm">暂无数据</div>
      </div>
    </div>

    <!-- 应收未收 -->
    <div v-if="activeSubTab === 'receivable'">
      <div class="card">
        <div class="table-container">
          <table class="w-full text-sm">
            <thead class="bg-elevated">
              <tr>
                <th class="px-3 py-2 text-left">单号</th>
                <th class="px-3 py-2 text-left">客户</th>
                <th class="px-3 py-2 text-left">平台单号</th>
                <th class="px-3 py-2 text-right">销售额</th>
                <th class="px-3 py-2 text-right">已收</th>
                <th class="px-3 py-2 text-right">未收</th>
                <th class="px-3 py-2 text-right">发货天数</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr v-for="row in receivableData" :key="row.id" class="hover:bg-elevated">
                <td class="px-3 py-2 font-mono text-xs">{{ row.ds_no }}</td>
                <td class="px-3 py-2">{{ row.customer_name }}</td>
                <td class="px-3 py-2 font-mono text-xs text-muted">{{ row.platform_order_no || '-' }}</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(row.sale_total) }}</td>
                <td class="px-3 py-2 text-right text-success">¥{{ fmtMoney(row.received) }}</td>
                <td class="px-3 py-2 text-right text-error font-semibold">¥{{ fmtMoney(row.unreceived) }}</td>
                <td class="px-3 py-2 text-right">
                  <span :class="getAgeClass(row.shipped_days || 0)">{{ row.shipped_days ?? '-' }}</span>
                </td>
              </tr>
            </tbody>
            <tfoot v-if="receivableData.length" class="bg-elevated font-semibold text-sm">
              <tr>
                <td class="px-3 py-2" colspan="3">合计 ({{ receivableData.length }} 笔)</td>
                <td class="px-3 py-2 text-right">¥{{ fmtMoney(receivableTotals.sale_total) }}</td>
                <td class="px-3 py-2 text-right text-success">¥{{ fmtMoney(receivableTotals.received) }}</td>
                <td class="px-3 py-2 text-right text-error">¥{{ fmtMoney(receivableTotals.unreceived) }}</td>
                <td class="px-3 py-2"></td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div v-if="receivableLoading" class="p-6 text-center text-muted text-sm">加载中...</div>
        <div v-else-if="!receivableData.length" class="p-6 text-center text-muted text-sm">暂无应收未收数据</div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 代采代发报表面板
 * 包含月度汇总、毛利分析、应收未收三个子 tab
 */
import { ref, computed, watch, onMounted } from 'vue'
import SegmentedControl from '../../common/SegmentedControl.vue'
import { useFormat } from '../../../composables/useFormat'
import { useAccountingStore } from '../../../stores/accounting'
import {
  getDropshipReportSummary,
  getDropshipReportProfit,
  getDropshipReportReceivable,
} from '../../../api/dropship'

const { fmtMoney, getAgeClass } = useFormat()
const accountingStore = useAccountingStore()

// 子 Tab
const subTabs = [
  { value: 'summary', label: '月度汇总' },
  { value: 'profit', label: '毛利分析' },
  { value: 'receivable', label: '应收未收' },
]
const activeSubTab = ref('summary')

// ---- 月度汇总 ----
const summaryMonth = ref(new Date().toISOString().slice(0, 7)) // YYYY-MM
const summaryDimension = ref('customer')
const summaryData = ref([])
const summaryLoading = ref(false)

const summaryTotals = computed(() => {
  const t = { order_count: 0, purchase_total: 0, sale_total: 0, gross_profit: 0 }
  for (const r of summaryData.value) {
    t.order_count += Number(r.order_count) || 0
    t.purchase_total += Number(r.purchase_total) || 0
    t.sale_total += Number(r.sale_total) || 0
    t.gross_profit += Number(r.gross_profit) || 0
  }
  return t
})

const loadSummary = async () => {
  summaryLoading.value = true
  try {
    const p = { month: summaryMonth.value }
    if (accountingStore.currentAccountSetId) p.account_set_id = accountingStore.currentAccountSetId
    const { data } = await getDropshipReportSummary(p)
    // 后端返回 by_customer / by_supplier，前端根据维度选择并做字段映射
    const dim = summaryDimension.value
    const raw = dim === 'customer' ? (data.by_customer || []) : (data.by_supplier || [])
    summaryData.value = raw.map(r => ({
      name: dim === 'customer' ? r.customer_name : r.supplier_name,
      order_count: r.count,
      purchase_total: r.purchase_total,
      sale_total: r.sale_total,
      gross_profit: r.profit,
    }))
  } catch (e) {
    console.error('加载月度汇总失败:', e)
    summaryData.value = []
  } finally {
    summaryLoading.value = false
  }
}

// ---- 毛利分析 ----
const profitStart = ref('')
const profitEnd = ref('')
const profitData = ref([])
const profitLoading = ref(false)

// 后端返回的汇总数据（含加权平均毛利率）
const profitSummary = ref(null)

const profitTotals = computed(() => {
  // 优先使用后端汇总
  if (profitSummary.value) {
    return {
      purchase_total: profitSummary.value.total_purchase ?? 0,
      sale_total: profitSummary.value.total_sale ?? 0,
      gross_profit: profitSummary.value.total_profit ?? 0,
      avg_margin: (profitSummary.value.avg_margin ?? 0).toFixed(1),
    }
  }
  // 兜底前端计算
  const t = { purchase_total: 0, sale_total: 0, gross_profit: 0 }
  for (const r of profitData.value) {
    t.purchase_total += Number(r.purchase_total) || 0
    t.sale_total += Number(r.sale_total) || 0
    t.gross_profit += Number(r.gross_profit) || 0
  }
  t.avg_margin = t.sale_total > 0
    ? (t.gross_profit / t.sale_total * 100).toFixed(1)
    : '0.0'
  return t
})

const loadProfit = async () => {
  profitLoading.value = true
  try {
    const params = {}
    if (accountingStore.currentAccountSetId) params.account_set_id = accountingStore.currentAccountSetId
    if (profitStart.value) params.start_date = profitStart.value
    if (profitEnd.value) params.end_date = profitEnd.value
    const { data } = await getDropshipReportProfit(params)
    profitData.value = data.items || data || []
    profitSummary.value = data.summary || null
  } catch (e) {
    console.error('加载毛利分析失败:', e)
    profitData.value = []
  } finally {
    profitLoading.value = false
  }
}

// ---- 应收未收 ----
const receivableData = ref([])
const receivableLoading = ref(false)

const receivableTotals = computed(() => {
  const t = { sale_total: 0, received: 0, unreceived: 0 }
  for (const r of receivableData.value) {
    t.sale_total += Number(r.sale_total) || 0
    t.received += Number(r.received) || 0
    t.unreceived += Number(r.unreceived) || 0
  }
  return t
})

const loadReceivable = async () => {
  receivableLoading.value = true
  try {
    const rp = {}
    if (accountingStore.currentAccountSetId) rp.account_set_id = accountingStore.currentAccountSetId
    const { data } = await getDropshipReportReceivable(rp)
    // 后端已按发货天数降序排列，做字段映射
    const items = data.items || data || []
    receivableData.value = items.map(r => ({
      ...r,
      received: r.received_amount ?? r.received ?? 0,
      unreceived: r.unreceived_amount ?? r.unreceived ?? 0,
    }))
  } catch (e) {
    console.error('加载应收未收失败:', e)
    receivableData.value = []
  } finally {
    receivableLoading.value = false
  }
}

// 切换子 tab 时加载对应数据
watch(activeSubTab, (tab) => {
  switch (tab) {
    case 'summary': loadSummary(); break
    case 'profit': loadProfit(); break
    case 'receivable': loadReceivable(); break
  }
})

onMounted(() => {
  loadSummary()
})
</script>
