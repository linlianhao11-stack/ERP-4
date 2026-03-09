<!--
  系统日志组件
  功能：操作日志列表展示、按操作类型筛选、刷新
  从 SettingsView.vue 系统日志标签页提取
-->
<template>
  <div class="card p-4">
    <!-- 筛选栏 -->
    <div class="flex gap-2 mb-3 flex-wrap">
      <select v-model="opLogFilter" @change="loadOpLogs" class="input w-auto text-sm">
        <option value="">全部操作</option>
        <option value="ORDER_CREATE">创建订单</option>
        <option value="PAYMENT_CREATE">账期收款</option>
        <option value="PAYMENT_CONFIRM">确认收款</option>
        <option value="STOCK_RESTOCK">入库</option>
        <option value="PURCHASE_CREATE">采购下单</option>
        <option value="PURCHASE_PAY">采购付款</option>
        <option value="PURCHASE_RECEIVE">采购收货</option>
        <option value="STOCK_TRANSFER">库存调拨</option>
        <option value="STOCK_ADJUST">库存调整</option>
        <option value="USER_CREATE">创建用户</option>
        <option value="USER_TOGGLE">禁用/启用用户</option>
      </select>
      <button @click="loadOpLogs" class="btn btn-secondary btn-sm">刷新</button>
    </div>
    <!-- 日志列表 -->
    <div class="space-y-1 max-h-[70vh] overflow-y-auto">
      <div v-for="log in opLogs" :key="log.id" class="flex justify-between items-start p-2 bg-[#f5f5f7] rounded text-xs">
        <div>
          <span class="font-medium text-[#0071e3]">{{ log.operator_name }}</span>
          <span class="mx-1 text-[#86868b]">·</span>
          <span>{{ log.detail }}</span>
        </div>
        <div class="text-[#86868b] whitespace-nowrap ml-2">{{ fmtDate(log.created_at) }}</div>
      </div>
      <div v-if="!opLogs.length" class="text-[#86868b] text-center py-4">暂无操作日志</div>
    </div>
  </div>
</template>

<script setup>
/**
 * 系统操作日志
 * 包含：日志列表、按操作类型筛选、日期格式化
 */
import { ref, computed, onMounted } from 'vue'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'

const settingsStore = useSettingsStore()
const { fmtDate } = useFormat()
const opLogs = computed(() => settingsStore.opLogs)

// 日志筛选条件
const opLogFilter = ref('')

// 加载操作日志
const loadOpLogs = () => {
  const params = {}
  if (opLogFilter.value) params.action = opLogFilter.value
  settingsStore.loadOpLogs(params)
}

// 组件挂载时自动加载日志
onMounted(() => {
  loadOpLogs()
})
</script>
