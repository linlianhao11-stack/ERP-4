<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="selectedYear" class="toolbar-select">
            <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}年</option>
          </select>
        </template>
        <template #actions>
          <button v-if="hasPermission('period_end')" @click="handleInitYear" class="btn btn-secondary btn-sm" :disabled="submitting">初始化年度期间</button>
        </template>
      </PageToolbar>

      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-2 py-2">期间</th>
              <th class="px-2 py-2">年</th>
              <th class="px-2 py-2">月</th>
              <th class="px-2 py-2">状态</th>
              <th class="px-2 py-2">结账时间</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="p in periods" :key="p.id" class="hover:bg-elevated">
              <td class="px-2 py-2 font-medium">{{ p.period_name }}</td>
              <td class="px-2 py-2">{{ p.year }}</td>
              <td class="px-2 py-2">{{ p.month }}</td>
              <td class="px-2 py-2">
                <span :class="p.is_closed ? 'badge badge-green' : 'badge badge-yellow'">
                  {{ p.is_closed ? '已结账' : '未结账' }}
                </span>
              </td>
              <td class="px-2 py-2">{{ p.closed_at ? new Date(p.closed_at).toLocaleString() : '-' }}</td>
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
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import { initYearPeriods } from '../../api/accounting'
import PageToolbar from '../common/PageToolbar.vue'

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
