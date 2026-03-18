<!--
  样机管理面板 — 顶层容器
  包含统计卡片 + 二级 Tab（样机台账 / 借还记录）
-->
<template>
  <div>
    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold font-mono">{{ stats.total }}</div>
        <div class="text-xs text-muted mt-1">样机总数</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold font-mono text-success">{{ stats.in_stock }}</div>
        <div class="text-xs text-muted mt-1">在库可借</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold font-mono text-primary">{{ stats.lent_out }}</div>
        <div class="text-xs text-muted mt-1">借出中</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold font-mono" :class="stats.overdue > 0 ? 'text-error' : ''">{{ stats.overdue }}</div>
        <div class="text-xs text-muted mt-1">超期未还</div>
      </div>
    </div>

    <!-- 二级 Tab -->
    <AppTabs
      v-model="subTab"
      :tabs="[
        { value: 'units', label: '样机台账' },
        { value: 'loans', label: '借还记录' },
      ]"
    />

    <DemoUnitList v-if="subTab === 'units'" @refresh="refreshAll" />
    <DemoLoanList v-else-if="subTab === 'loans'" @refresh="refreshAll" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AppTabs from '../../common/AppTabs.vue'
import DemoUnitList from './DemoUnitList.vue'
import DemoLoanList from './DemoLoanList.vue'
import { useDemoStats } from '../../../composables/useDemoUnit'

const subTab = ref('units')
const { stats, loadStats } = useDemoStats()

const refreshAll = () => {
  loadStats()
}

onMounted(() => loadStats())
</script>
