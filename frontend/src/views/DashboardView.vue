<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h2 class="text-[20px] font-semibold text-foreground tracking-tight">数据概览</h2>
      <p class="text-[13px] text-muted mt-0.5">{{ settingsStore.companyName || 'ERP System' }}</p>
    </div>

    <!-- KPI Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="card p-5">
        <div class="flex items-center gap-2.5 mb-3">
          <div class="w-8 h-8 rounded-[10px] bg-info-subtle flex items-center justify-center">
            <TrendingUp :size="16" :stroke-width="1.5" class="text-primary" />
          </div>
          <span class="text-[12px] font-medium text-muted">今日销售</span>
        </div>
        <div class="text-[22px] font-semibold text-foreground tracking-tight">¥{{ fmt(dashboard.today_sales) }}</div>
      </div>

      <div v-if="hasPermission('finance')" class="card p-5">
        <div class="flex items-center gap-2.5 mb-3">
          <div class="w-8 h-8 rounded-[10px] bg-success-subtle flex items-center justify-center">
            <CircleDollarSign :size="16" :stroke-width="1.5" class="text-success" />
          </div>
          <span class="text-[12px] font-medium text-muted">今日毛利</span>
        </div>
        <div class="text-[22px] font-semibold text-foreground tracking-tight">¥{{ fmt(dashboard.today_profit) }}</div>
      </div>

      <div v-if="hasPermission('finance')" class="card p-5">
        <div class="flex items-center gap-2.5 mb-3">
          <div class="w-8 h-8 rounded-[10px] bg-purple-subtle flex items-center justify-center">
            <Package :size="16" :stroke-width="1.5" class="text-purple-emphasis" />
          </div>
          <span class="text-[12px] font-medium text-muted">库存总值</span>
        </div>
        <div class="text-[22px] font-semibold text-foreground tracking-tight">¥{{ fmt(dashboard.stock_value) }}</div>
      </div>

      <div class="card p-5">
        <div class="flex items-center gap-2.5 mb-3">
          <div class="w-8 h-8 rounded-[10px] bg-orange-subtle flex items-center justify-center">
            <Receipt :size="16" :stroke-width="1.5" class="text-warning" />
          </div>
          <span class="text-[12px] font-medium text-muted">应收账款</span>
        </div>
        <div class="text-[22px] font-semibold text-foreground tracking-tight">¥{{ fmt(dashboard.total_receivable) }}</div>
      </div>
    </div>

    <!-- Sales Trend + Todo Panel -->
    <div class="grid md:grid-cols-[1fr_320px] gap-5 mb-5">
      <!-- 销售趋势 -->
      <div class="card overflow-hidden">
        <div class="flex items-center justify-between px-5 py-3.5 border-b border-line">
          <span class="text-[14px] font-semibold text-foreground">销售趋势</span>
          <div class="flex gap-1">
            <button v-for="d in [7, 30]" :key="d"
              @click="trendDays = d; loadSalesTrend()"
              class="px-2.5 py-1 rounded-md text-[12px] font-medium transition-colors"
              :class="trendDays === d ? 'bg-primary-muted text-primary' : 'text-muted hover:text-secondary'"
            >{{ d }}天</button>
          </div>
        </div>
        <div class="px-5 pt-4 pb-2" style="height: 240px;">
          <canvas ref="chartCanvas"></canvas>
        </div>
      </div>

      <!-- 待办事项 -->
      <div class="card overflow-hidden flex flex-col">
        <div class="flex items-center justify-between px-5 py-3.5 border-b border-line">
          <span class="text-[14px] font-semibold text-foreground">待办事项</span>
          <span v-if="todoItems.length" class="badge badge-gray text-[11px]">{{ todoItems.length }} 项</span>
        </div>
        <div class="flex-1 overflow-y-auto">
          <router-link
            v-for="item in todoItems"
            :key="item.key"
            :to="item.route"
            class="flex items-center gap-3 px-5 py-3 hover:bg-elevated transition-colors"
          >
            <div class="w-[30px] h-[30px] rounded-lg flex items-center justify-center flex-shrink-0" :class="item.iconBg">
              <component :is="item.icon" :size="15" :stroke-width="1.5" :class="item.iconColor" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-[13px] font-[450] text-foreground">{{ item.label }}</div>
            </div>
            <span class="text-[16px] font-bold font-mono tabular-nums text-foreground min-w-[28px] text-right">{{ item.count }}</span>
            <ChevronRight :size="14" :stroke-width="1.5" class="text-muted flex-shrink-0" />
          </router-link>
          <div v-if="!todoItems.length" class="flex flex-col items-center justify-center py-12 text-muted">
            <CheckCircle :size="32" :stroke-width="1" class="mb-2 opacity-40" />
            <span class="text-[13px]">暂无待办</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Orders -->
    <div class="card overflow-hidden">
      <div class="flex items-center justify-between px-5 py-3.5 border-b border-line">
        <span class="text-[14px] font-semibold text-foreground">最近订单</span>
        <router-link to="/finance" class="text-[12px] text-primary font-medium hover:underline">查看全部</router-link>
      </div>
      <!-- 移动端卡片 -->
      <div class="md:hidden divide-y divide-line">
        <div v-for="o in recentOrders" :key="o.id" class="px-4 py-3 cursor-pointer active:bg-elevated" @click="goToOrder(o.id)">
          <div class="flex justify-between items-start mb-1">
            <span class="text-[12px] font-mono font-semibold text-primary">{{ o.order_no }}</span>
            <span class="text-[13px] font-mono font-semibold">¥{{ fmt(o.total_amount) }}</span>
          </div>
          <div class="flex justify-between items-center text-[12px]">
            <span class="text-muted">{{ o.customer_name }}</span>
            <StatusBadge type="orderType" :status="o.order_type" />
          </div>
          <div class="text-[11px] text-muted mt-0.5">{{ o.created_at }}</div>
        </div>
        <div v-if="!recentOrders.length" class="p-8 text-center text-muted text-sm">暂无订单</div>
      </div>
      <!-- 桌面端表格 -->
      <div class="hidden md:block table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-4 py-2.5 text-left">订单号</th>
              <th class="px-4 py-2.5 text-left">客户</th>
              <th class="px-4 py-2.5 text-right">金额</th>
              <th class="px-4 py-2.5 text-center">类型</th>
              <th class="px-4 py-2.5 text-center">状态</th>
              <th class="px-4 py-2.5 text-left">时间</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="o in recentOrders" :key="o.id" class="hover:bg-elevated cursor-pointer" @click="goToOrder(o.id)">
              <td class="px-4 py-2.5 font-mono text-[12px] font-semibold text-primary">{{ o.order_no }}</td>
              <td class="px-4 py-2.5">{{ o.customer_name }}</td>
              <td class="px-4 py-2.5 text-right font-mono">¥{{ fmt(o.total_amount) }}</td>
              <td class="px-4 py-2.5 text-center"><StatusBadge type="orderType" :status="o.order_type" /></td>
              <td class="px-4 py-2.5 text-center"><StatusBadge type="shippingStatus" :status="o.shipping_status" /></td>
              <td class="px-4 py-2.5 text-muted text-xs">{{ o.created_at }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!recentOrders.length" class="p-8 text-center text-muted text-sm">暂无订单</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { useSettingsStore } from '../stores/settings'
import { getDashboard, getSalesTrend, getRecentOrders } from '../api/dashboard'
import { useFormat } from '../composables/useFormat'
import { usePermission } from '../composables/usePermission'
import {
  TrendingUp, CircleDollarSign, Package, Receipt,
  Truck, ClipboardCheck, PackageSearch, CreditCard, AlertTriangle, FileText,
  ChevronRight, CheckCircle
} from 'lucide-vue-next'
import StatusBadge from '../components/common/StatusBadge.vue'
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip } from 'chart.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip)

const router = useRouter()
const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { fmt } = useFormat()
const { hasPermission } = usePermission()

const dashboard = ref({
  today_sales: 0, today_profit: 0, stock_value: 0,
  total_receivable: 0, inventory_age: {}, top_products: []
})
const recentOrders = ref([])
const trendDays = ref(30)
const trendData = ref([])
const chartCanvas = ref(null)
let chartInstance = null

// --- Todo items ---
const todoItemDefs = [
  { key: 'pending_shipment', label: '待发货订单', route: '/logistics', perm: 'logistics', icon: Truck, iconBg: 'bg-info-subtle', iconColor: 'text-info' },
  { key: 'pending_review', label: '待审核采购', route: '/purchase', perm: 'purchase', icon: ClipboardCheck, iconBg: 'bg-purple-subtle', iconColor: 'text-purple-emphasis' },
  { key: 'in_transit', label: '在途采购', route: '/purchase', perm: 'purchase', icon: PackageSearch, iconBg: 'bg-info-subtle', iconColor: 'text-info' },
  { key: 'pending_collection', label: '待收款客户', route: '/finance', perm: 'finance', icon: CreditCard, iconBg: 'bg-warning-subtle', iconColor: 'text-warning' },
  { key: 'low_stock', label: '低库存预警', route: '/stock', perm: 'stock_view', icon: AlertTriangle, iconBg: 'bg-error-subtle', iconColor: 'text-error' },
  { key: 'pending_receivable', label: '待处理应收', route: '/accounting', perm: 'accounting_view', icon: FileText, iconBg: 'bg-orange-subtle', iconColor: 'text-orange-emphasis' },
]

const todoItems = computed(() => {
  const counts = appStore.todoCounts
  return todoItemDefs
    .filter(d => hasPermission(d.perm) && (counts[d.key] || 0) > 0)
    .map(d => ({ ...d, count: counts[d.key] }))
})

// --- Data loading ---
const loadDashboard = async () => {
  try {
    const { data } = await getDashboard()
    dashboard.value = data
  } catch (e) { /* silent */ }
}

const loadSalesTrend = async () => {
  try {
    const { data } = await getSalesTrend(trendDays.value)
    trendData.value = data
    await nextTick()
    renderChart()
  } catch (e) { /* silent */ }
}

const loadRecentOrders = async () => {
  try {
    const { data } = await getRecentOrders(10)
    recentOrders.value = data
  } catch (e) { /* silent */ }
}

// --- Chart ---
const getChartColors = () => {
  const style = getComputedStyle(document.documentElement)
  const primary = style.getPropertyValue('--primary').trim() || '#4878c8'
  return { primary }
}

const renderChart = () => {
  if (!chartCanvas.value) return
  if (chartInstance) chartInstance.destroy()

  const { primary } = getChartColors()
  const labels = trendData.value.map(d => {
    const parts = d.date.split('-')
    return `${parts[1]}/${parts[2]}`
  })
  const values = trendData.value.map(d => d.amount)

  chartInstance = new Chart(chartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: values,
        borderColor: primary,
        backgroundColor: primary.includes('oklch') ? 'rgba(72, 120, 200, 0.08)' : primary + '14',
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: primary,
        pointHoverBorderColor: '#fff',
        pointHoverBorderWidth: 2,
        tension: 0.35,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(0,0,0,0.8)',
          titleFont: { size: 12 },
          bodyFont: { size: 13, weight: 600 },
          padding: { x: 10, y: 6 },
          cornerRadius: 8,
          callbacks: {
            label: (ctx) => `¥${ctx.parsed.y.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 }, color: '#999', maxRotation: 0, autoSkipPadding: 20 },
          border: { display: false }
        },
        y: {
          grid: { color: 'rgba(0,0,0,0.04)' },
          ticks: {
            font: { size: 11 }, color: '#999',
            callback: (v) => v >= 10000 ? (v / 10000).toFixed(0) + 'w' : v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v
          },
          border: { display: false },
          beginAtZero: true
        }
      }
    }
  })
}

// Re-render chart when theme changes
watch(() => appStore.theme, () => {
  if (trendData.value.length) {
    nextTick(() => renderChart())
  }
})

const goToOrder = (id) => {
  router.push({ path: '/finance', query: { orderId: id } })
}

onMounted(() => {
  loadDashboard()
  appStore.loadTodoCounts()
  loadSalesTrend()
  loadRecentOrders()
})

onUnmounted(() => {
  if (chartInstance) chartInstance.destroy()
})
</script>
