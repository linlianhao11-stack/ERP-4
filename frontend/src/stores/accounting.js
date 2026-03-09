import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAccountSets, getChartOfAccounts, getAccountingPeriods } from '../api/accounting'

export const useAccountingStore = defineStore('accounting', () => {
  const accountSets = ref([])
  const currentAccountSetId = ref(null)
  const chartOfAccounts = ref([])
  const periods = ref([])
  const loading = ref(false)

  const currentAccountSet = computed(() =>
    accountSets.value.find(s => s.id === currentAccountSetId.value)
  )

  async function loadAccountSets() {
    try {
      const { data } = await getAccountSets()
      accountSets.value = data
      if (!currentAccountSetId.value && data.length > 0) {
        currentAccountSetId.value = data[0].id
      }
    } catch (e) { console.error('加载失败', e) }
  }

  function setCurrentAccountSet(id) {
    currentAccountSetId.value = id
    chartOfAccounts.value = []
    periods.value = []
  }

  async function loadChartOfAccounts() {
    if (!currentAccountSetId.value) return
    try {
      const { data } = await getChartOfAccounts(currentAccountSetId.value)
      chartOfAccounts.value = data
    } catch (e) { console.error('加载失败', e) }
  }

  async function loadPeriods(year) {
    if (!currentAccountSetId.value) return
    try {
      const { data } = await getAccountingPeriods(currentAccountSetId.value, year)
      periods.value = data
    } catch (e) { console.error('加载失败', e) }
  }

  return {
    accountSets, currentAccountSetId, currentAccountSet,
    chartOfAccounts, periods, loading,
    loadAccountSets, setCurrentAccountSet,
    loadChartOfAccounts, loadPeriods,
  }
})
