<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h2 class="text-[20px] font-semibold text-[#1d1d1f] tracking-tight">数据概览</h2>
      <p class="text-[13px] text-[#86868b] mt-0.5">{{ settingsStore.companyName || 'ERP System' }}</p>
    </div>

    <!-- KPI Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="card p-5">
        <div class="flex items-center gap-2.5 mb-3">
          <div class="w-8 h-8 rounded-[10px] bg-[#e8f4fd] flex items-center justify-center">
            <TrendingUp :size="16" :stroke-width="1.5" class="text-[#0071e3]" />
          </div>
          <span class="text-[12px] font-medium text-[#86868b]">今日销售</span>
        </div>
        <div class="text-[22px] font-semibold text-[#1d1d1f] tracking-tight">¥{{ fmt(dashboard.today_sales) }}</div>
      </div>

      <div v-if="hasPermission('finance')" class="card p-5">
        <div class="flex items-center gap-2.5 mb-3">
          <div class="w-8 h-8 rounded-[10px] bg-[#e8f8ee] flex items-center justify-center">
            <CircleDollarSign :size="16" :stroke-width="1.5" class="text-[#34c759]" />
          </div>
          <span class="text-[12px] font-medium text-[#86868b]">今日毛利</span>
        </div>
        <div class="text-[22px] font-semibold text-[#1d1d1f] tracking-tight">¥{{ fmt(dashboard.today_profit) }}</div>
      </div>

      <div v-if="hasPermission('finance')" class="card p-5">
        <div class="flex items-center gap-2.5 mb-3">
          <div class="w-8 h-8 rounded-[10px] bg-[#f3eef8] flex items-center justify-center">
            <Package :size="16" :stroke-width="1.5" class="text-[#af52de]" />
          </div>
          <span class="text-[12px] font-medium text-[#86868b]">库存总值</span>
        </div>
        <div class="text-[22px] font-semibold text-[#1d1d1f] tracking-tight">¥{{ fmt(dashboard.stock_value) }}</div>
      </div>

      <div class="card p-5">
        <div class="flex items-center gap-2.5 mb-3">
          <div class="w-8 h-8 rounded-[10px] bg-[#fff3e0] flex items-center justify-center">
            <Receipt :size="16" :stroke-width="1.5" class="text-[#ff9f0a]" />
          </div>
          <span class="text-[12px] font-medium text-[#86868b]">应收账款</span>
        </div>
        <div class="text-[22px] font-semibold text-[#1d1d1f] tracking-tight">¥{{ fmt(dashboard.total_receivable) }}</div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="card p-5 mb-6">
      <h3 class="text-[14px] font-semibold text-[#1d1d1f] mb-4">快捷操作</h3>
      <div class="flex flex-wrap gap-2.5">
        <button class="btn btn-primary btn-sm" @click="router.push('/sales')">
          <ShoppingCart :size="14" :stroke-width="1.5" /><span>新建销售</span>
        </button>
        <button class="btn btn-secondary btn-sm" @click="router.push('/stock')">
          <Package :size="14" :stroke-width="1.5" /><span>入库补货</span>
        </button>
        <button class="btn btn-secondary btn-sm" @click="router.push('/purchase')">
          <ShoppingBag :size="14" :stroke-width="1.5" /><span>采购下单</span>
        </button>
        <button class="btn btn-secondary btn-sm" @click="router.push('/consignment')">
          <ArrowLeftRight :size="14" :stroke-width="1.5" /><span>寄售管理</span>
        </button>
        <button class="btn btn-secondary btn-sm" @click="router.push('/logistics')">
          <Truck :size="14" :stroke-width="1.5" /><span>物流查询</span>
        </button>
        <button class="btn btn-secondary btn-sm" @click="router.push('/finance')">
          <Wallet :size="14" :stroke-width="1.5" /><span>财务管理</span>
        </button>
      </div>
    </div>

    <!-- Inventory Age + Top Products -->
    <div class="grid md:grid-cols-2 gap-5">
      <div class="card p-5">
        <h3 class="text-[14px] font-semibold text-[#1d1d1f] mb-5">库龄分布</h3>
        <div class="flex justify-around text-center">
          <div>
            <div class="text-[28px] font-semibold text-[#34c759] tracking-tight">{{ dashboard.inventory_age?.normal || 0 }}</div>
            <div class="text-[12px] text-[#86868b] mt-1">正常</div>
          </div>
          <div class="w-px bg-[#e8e8ed]"></div>
          <div>
            <div class="text-[28px] font-semibold text-[#ff9f0a] tracking-tight">{{ dashboard.inventory_age?.slow || 0 }}</div>
            <div class="text-[12px] text-[#86868b] mt-1">滞销</div>
          </div>
          <div class="w-px bg-[#e8e8ed]"></div>
          <div>
            <div class="text-[28px] font-semibold text-[#ff3b30] tracking-tight">{{ dashboard.inventory_age?.dead || 0 }}</div>
            <div class="text-[12px] text-[#86868b] mt-1">呆滞</div>
          </div>
        </div>
      </div>

      <div class="card p-5">
        <h3 class="text-[14px] font-semibold text-[#1d1d1f] mb-4">畅销 TOP 10</h3>
        <div class="space-y-0 max-h-52 overflow-y-auto">
          <div
            v-for="(p, i) in dashboard.top_products"
            :key="i"
            class="flex items-center justify-between py-2.5 border-b border-[#f5f5f7] last:border-0"
          >
            <div class="flex items-center gap-2.5 min-w-0">
              <span class="w-5 h-5 rounded-md bg-[#f5f5f7] flex items-center justify-center text-[11px] font-medium text-[#86868b] shrink-0">{{ i + 1 }}</span>
              <span class="text-[13px] text-[#1d1d1f] truncate">{{ p.name }}</span>
            </div>
            <span class="text-[13px] text-[#86868b] ml-3 shrink-0">{{ p.quantity }}件</span>
          </div>
          <div v-if="!dashboard.top_products?.length" class="text-[13px] text-[#86868b] text-center py-8">暂无数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { useSettingsStore } from '../stores/settings'
import { getDashboard } from '../api/dashboard'
import { useFormat } from '../composables/useFormat'
import { usePermission } from '../composables/usePermission'
import {
  TrendingUp, CircleDollarSign, Package, Receipt,
  ShoppingCart, ShoppingBag, ArrowLeftRight, Truck, Wallet
} from 'lucide-vue-next'

const router = useRouter()
const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { fmt } = useFormat()
const { hasPermission } = usePermission()

const dashboard = ref({
  today_sales: 0,
  today_profit: 0,
  stock_value: 0,
  total_receivable: 0,
  inventory_age: {},
  top_products: []
})

const loadDashboard = async () => {
  try {
    const { data } = await getDashboard()
    dashboard.value = data
  } catch (e) {
    appStore.showToast('加载仪表盘数据失败', 'error')
  }
}

onMounted(() => {
  loadDashboard()
})
</script>
