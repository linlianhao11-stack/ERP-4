<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-[15px] font-semibold text-foreground">会计期间</h3>
      <div class="flex items-center gap-2">
        <select v-model="selectedYear" class="input input-sm w-28">
          <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}年</option>
        </select>
        <button v-if="hasPermission('period_end')" @click="handleInitYear" class="btn btn-secondary btn-sm" :disabled="submitting">初始化年度期间</button>
      </div>
    </div>

    <div class="table-container">
      <table class="w-full">
        <thead>
          <tr>
            <th>期间</th>
            <th>年</th>
            <th>月</th>
            <th>状态</th>
            <th>结账时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in periods" :key="p.id">
            <td class="font-medium">{{ p.period_name }}</td>
            <td>{{ p.year }}</td>
            <td>{{ p.month }}</td>
            <td>
              <span :class="p.is_closed ? 'badge badge-green' : 'badge badge-yellow'">
                {{ p.is_closed ? '已结账' : '未结账' }}
              </span>
            </td>
            <td>{{ p.closed_at ? new Date(p.closed_at).toLocaleString() : '-' }}</td>
          </tr>
          <tr v-if="periods.length === 0">
            <td colspan="5" class="text-center text-muted py-8">
              该年度暂无会计期间，请点击"初始化年度期间"创建
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import { initYearPeriods } from '../../api/accounting'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()

const currentYear = new Date().getFullYear()
const selectedYear = ref(currentYear)
const submitting = ref(false)
const periods = ref([])

const yearOptions = computed(() => {
  const years = []
  for (let y = currentYear - 2; y <= currentYear + 2; y++) years.push(y)
  return years
})

const loadPeriods = async () => {
  if (!accountingStore.currentAccountSetId) return
  await accountingStore.loadPeriods(selectedYear.value)
  periods.value = accountingStore.periods
}

const handleInitYear = async () => {
  submitting.value = true
  try {
    const { data } = await initYearPeriods(accountingStore.currentAccountSetId, selectedYear.value)
    appStore.showToast(data.message, 'success')
    await loadPeriods()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '初始化失败', 'error')
  } finally {
    submitting.value = false
  }
}

watch(selectedYear, loadPeriods)
watch(() => accountingStore.currentAccountSetId, loadPeriods)
onMounted(loadPeriods)
</script>
