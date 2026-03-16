<template>
  <div>
    <!-- Header -->
    <div class="mb-7">
      <h2 class="text-[22px] font-bold text-foreground tracking-tight">数据概览</h2>
      <p class="text-[13px] text-muted mt-0.5">{{ settingsStore.companyName || 'ERP System' }}</p>
    </div>

    <!-- Asymmetric KPI Grid -->
    <div class="kpi-grid mb-6">
      <!-- Hero KPI: 今日销售 -->
      <div class="card kpi-hero">
        <div>
          <div class="flex items-center gap-2 text-[13px] font-medium text-secondary">
            <TrendingUp :size="16" :stroke-width="1.5" class="text-primary" />
            今日销售额
          </div>
          <div class="text-[36px] font-bold text-foreground tracking-tighter font-mono mt-3">¥{{ fmt(dashboard.today_sales) }}</div>
        </div>
      </div>

      <!-- Secondary KPIs -->
      <div v-if="hasPermission('finance')" class="card kpi-secondary">
        <div class="text-[12px] font-medium text-muted mb-2">今日毛利</div>
        <div class="text-[20px] font-semibold text-success-emphasis tracking-tight font-mono">¥{{ fmt(dashboard.today_profit) }}</div>
      </div>
      <div class="card kpi-secondary">
        <div class="text-[12px] font-medium text-muted mb-2">应收账款</div>
        <div class="text-[20px] font-semibold text-warning-emphasis tracking-tight font-mono">¥{{ fmt(dashboard.total_receivable) }}</div>
      </div>
      <div class="card kpi-secondary">
        <div class="text-[12px] font-medium text-muted mb-2">今日发货</div>
        <div class="text-[20px] font-semibold text-info tracking-tight font-mono">{{ dashboard.today_shipments }} <span class="text-[13px] font-normal text-muted">单</span></div>
      </div>
      <div v-if="hasPermission('finance')" class="card kpi-secondary">
        <div class="text-[12px] font-medium text-muted mb-2">库存总值</div>
        <div class="text-[20px] font-semibold text-foreground tracking-tight font-mono">¥{{ fmt(dashboard.stock_value) }}</div>
      </div>
    </div>

    <!-- Sales Trend + Todo Panel -->
    <div class="grid md:grid-cols-[1fr_340px] gap-5 mb-5">
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
        <div class="flex-1 overflow-y-auto max-h-[270px]">
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
            <span class="text-[14px] font-medium mb-1">全部处理完毕</span>
            <span class="text-[12px]">新的待办事项会自动出现在这里</span>
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

    <!-- 订单详情弹窗 -->
    <teleport to="body">
      <div v-if="showOrderDetail" class="modal-overlay" @click.self="closeOrderDetail">
        <div class="modal-content" style="max-width:920px">
          <div class="modal-header">
            <h3 class="font-semibold">订单详情</h3>
            <button @click="closeOrderDetail" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <!-- 加载中 -->
            <div v-if="orderDetailLoading" class="flex items-center justify-center py-16 text-muted">
              <span class="text-sm">加载中...</span>
            </div>
            <template v-else-if="orderDetail.order_no">
              <!-- 订单基本信息 -->
              <div class="mb-5 p-4 bg-elevated rounded-xl">
                <div class="flex justify-between items-start mb-2">
                  <div>
                    <div class="text-[15px] font-bold font-mono">{{ orderDetail.order_no }}</div>
                    <div class="text-xs text-muted mt-0.5">
                      <span v-if="orderDetail.employee_name">销售员: {{ orderDetail.employee_name }} · </span>
                      {{ orderDetail.creator_name }} · {{ fmtDate(orderDetail.created_at) }}
                    </div>
                  </div>
                  <StatusBadge type="orderType" :status="orderDetail.order_type" />
                </div>
                <div class="grid grid-cols-2 gap-1.5 gap-x-4 text-[13px]">
                  <div><span class="text-muted">客户:</span> {{ orderDetail.customer?.name || '-' }}</div>
                  <div><span class="text-muted">仓库:</span> {{ orderDetail.warehouse?.name || '-' }}</div>
                  <div><span class="text-muted">金额:</span> <span class="font-semibold">¥{{ fmt(orderDetail.total_amount) }}</span></div>
                  <div v-if="hasPermission('finance')"><span class="text-muted">毛利:</span> <span :class="orderDetail.total_profit >= 0 ? 'text-success' : 'text-error'">¥{{ fmt(orderDetail.total_profit) }}</span></div>
                  <div><span class="text-muted">已付:</span> ¥{{ fmt(orderDetail.paid_amount) }}</div>
                  <div><span class="text-muted">状态:</span> <span :class="orderDetail.is_cleared ? 'text-success' : 'text-error'">{{ orderDetail.is_cleared ? '已结清' : '未结清' }}</span></div>
                  <div v-if="orderDetail.shipping_status"><span class="text-muted">发货:</span> <StatusBadge type="shippingStatus" :status="orderDetail.shipping_status" /></div>
                  <div v-if="orderDetail.remark" class="col-span-2 pt-2 border-t border-line"><span class="text-muted">备注:</span> <span class="text-secondary">{{ orderDetail.remark }}</span></div>
                </div>
              </div>

              <!-- 商品明细 -->
              <div v-if="orderDetail.items?.length" class="mb-5">
                <div class="flex items-center gap-2 mb-2.5">
                  <span class="text-[13px] font-semibold text-secondary">商品明细</span>
                  <span class="text-[11px] text-muted bg-elevated px-2 py-0.5 rounded-full">{{ orderDetail.items.length }} 件商品</span>
                </div>
                <div class="overflow-x-auto">
                  <table class="w-full text-sm">
                    <thead class="bg-elevated">
                      <tr>
                        <th class="px-2 py-2 text-left text-xs font-semibold text-secondary">商品</th>
                        <th class="px-2 py-2 text-right text-xs font-semibold text-secondary">单价</th>
                        <th class="px-2 py-2 text-right text-xs font-semibold text-secondary">数量</th>
                        <th class="px-2 py-2 text-right text-xs font-semibold text-secondary">金额</th>
                        <th v-if="hasPermission('finance')" class="px-2 py-2 text-right text-xs font-semibold text-secondary">毛利</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-line">
                      <tr v-for="item in orderDetail.items" :key="item.id || item.product_id">
                        <td class="px-2 py-2.5">
                          <div class="font-medium">{{ item.product_name }}</div>
                          <div class="text-[11px] text-muted font-mono">{{ item.product_sku }}</div>
                        </td>
                        <td class="px-2 py-2.5 text-right">{{ fmt(item.unit_price) }}</td>
                        <td class="px-2 py-2.5 text-right">{{ item.quantity }}</td>
                        <td class="px-2 py-2.5 text-right font-semibold">{{ fmt(item.amount) }}</td>
                        <td v-if="hasPermission('finance')" class="px-2 py-2.5 text-right" :class="item.profit >= 0 ? 'text-success' : 'text-error'">{{ fmt(item.profit) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- 物流信息 -->
              <div v-if="orderDetail.shipments?.length" class="mb-2">
                <div class="flex items-center gap-2 mb-2.5">
                  <span class="text-[13px] font-semibold text-secondary">物流信息</span>
                  <span class="text-[11px] text-muted bg-elevated px-2 py-0.5 rounded-full">{{ orderDetail.shipments.length }} 个物流单</span>
                </div>
                <div v-for="sh in orderDetail.shipments" :key="sh.id" class="border border-line rounded-[10px] overflow-hidden mb-2.5 last:mb-0">
                  <div class="flex justify-between items-center px-3.5 py-2.5 bg-elevated">
                    <div class="flex items-center gap-1.5">
                      <span class="text-xs text-muted">{{ sh.carrier_name || '未填写承运商' }}</span>
                    </div>
                    <StatusBadge type="shipmentStatus" :status="sh.status" />
                  </div>
                  <div v-if="sh.tracking_no" class="flex items-center gap-1.5 px-3.5 py-2 border-b border-line">
                    <span class="text-[11px] text-muted">运单号:</span>
                    <span class="text-xs font-mono font-medium text-primary">{{ sh.tracking_no }}</span>
                  </div>
                </div>
              </div>
            </template>
          </div>
          <div class="modal-footer">
            <button type="button" @click="closeOrderDetail" class="btn btn-secondary btn-sm">关闭</button>
            <button type="button" @click="closeOrderDetail(); router.push({ path: '/finance', query: { orderId: orderDetail.id } })" class="btn btn-primary btn-sm">查看完整详情</button>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { useSettingsStore } from '../stores/settings'
import { getDashboard, getSalesTrend, getRecentOrders } from '../api/dashboard'
import { getOrder } from '../api/orders'
import { useFormat } from '../composables/useFormat'
import { usePermission } from '../composables/usePermission'
import {
  TrendingUp, CircleDollarSign, Package, Receipt,
  Truck, ClipboardCheck, PackageSearch, CreditCard, AlertTriangle, FileText,
  Wallet, ChevronRight, CheckCircle
} from 'lucide-vue-next'
import StatusBadge from '../components/common/StatusBadge.vue'
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip } from 'chart.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip)

const router = useRouter()
const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()

const dashboard = ref({
  today_sales: 0, today_profit: 0, stock_value: 0,
  total_receivable: 0, today_shipments: 0, inventory_age: {}, top_products: []
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
  { key: 'pending_payment', label: '待付款采购', route: '/finance', perm: 'finance', icon: Wallet, iconBg: 'bg-error-subtle', iconColor: 'text-error' },
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

// --- Chart (dark-mode aware) ---
const getChartColors = () => {
  const style = getComputedStyle(document.documentElement)
  const primary = style.getPropertyValue('--primary').trim() || '#4878c8'
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
  return {
    primary,
    tickColor: isDark ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.35)',
    gridColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
    tooltipBg: isDark ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.8)',
    tooltipText: isDark ? '#111' : '#fff',
    fillColor: isDark ? 'rgba(100,160,240,0.10)' : 'rgba(72,120,200,0.08)',
  }
}

const renderChart = () => {
  if (!chartCanvas.value) return
  if (chartInstance) chartInstance.destroy()

  const colors = getChartColors()
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
        borderColor: colors.primary,
        backgroundColor: colors.fillColor,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: colors.primary,
        pointHoverBorderColor: colors.tooltipText,
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
          backgroundColor: colors.tooltipBg,
          titleColor: colors.tooltipText,
          bodyColor: colors.tooltipText,
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
          ticks: { font: { size: 11 }, color: colors.tickColor, maxRotation: 0, autoSkipPadding: 20 },
          border: { display: false }
        },
        y: {
          grid: { color: colors.gridColor },
          ticks: {
            font: { size: 11 }, color: colors.tickColor,
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

// --- 订单详情弹窗 ---
const showOrderDetail = ref(false)
const orderDetail = reactive({})
const orderDetailLoading = ref(false)

const lockScroll = (lock) => {
  const el = document.querySelector('.app-content')
  if (el) el.style.overflow = lock ? 'hidden' : ''
}

const goToOrder = async (id) => {
  orderDetailLoading.value = true
  showOrderDetail.value = true
  lockScroll(true)
  try {
    const { data } = await getOrder(id)
    Object.keys(orderDetail).forEach(k => delete orderDetail[k])
    Object.assign(orderDetail, data)
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
    showOrderDetail.value = false
    lockScroll(false)
  } finally {
    orderDetailLoading.value = false
  }
}

const closeOrderDetail = () => {
  showOrderDetail.value = false
  lockScroll(false)
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

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (min-width: 768px) {
  .kpi-grid {
    grid-template-columns: 1fr 1fr 1fr;
    grid-template-rows: auto auto;
  }
}
.kpi-hero {
  padding: 28px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  grid-column: 1 / -1;
}
@media (min-width: 768px) {
  .kpi-hero {
    grid-row: 1 / 3;
    grid-column: 1;
    min-height: 180px;
  }
}
.kpi-secondary {
  padding: 20px;
}
</style>
