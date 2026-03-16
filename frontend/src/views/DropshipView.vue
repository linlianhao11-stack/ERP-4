<template>
  <div>
    <AppTabs v-model="activeTab" :tabs="tabs" container-class="mb-4" />

    <DropshipOrdersPanel
      v-if="activeTab === 'orders'"
      key="orders"
      ref="ordersPanel"
    />
    <DropshipPaymentPanel
      v-else-if="activeTab === 'payment'"
      key="payment"
    />
    <DropshipReportsPanel
      v-else-if="activeTab === 'reports'"
      key="reports"
    />
  </div>
</template>

<script setup>
/**
 * 代采代发主视图容器
 * 包含订单列表、付款工作台、报表统计三个 Tab
 */
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppTabs from '../components/common/AppTabs.vue'
import DropshipOrdersPanel from '../components/business/DropshipOrdersPanel.vue'

// 延迟加载不常用的面板
import { defineAsyncComponent } from 'vue'
const DropshipPaymentPanel = defineAsyncComponent(() =>
  import('../components/business/dropship/DropshipPaymentPanel.vue')
)
const DropshipReportsPanel = defineAsyncComponent(() =>
  import('../components/business/dropship/DropshipReportsPanel.vue')
)

const route = useRoute()
const router = useRouter()

const tabs = [
  { value: 'orders', label: '代采订单' },
  { value: 'payment', label: '付款工作台' },
  { value: 'reports', label: '报表统计' },
]

const validTabs = tabs.map(t => t.value)
const activeTab = ref(validTabs.includes(route.query.tab) ? route.query.tab : 'orders')
watch(activeTab, (val) =>
  router.replace({ query: { ...route.query, tab: val === 'orders' ? undefined : val } })
)

const ordersPanel = ref(null)
</script>
