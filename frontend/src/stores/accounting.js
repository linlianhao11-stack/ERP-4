import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAccountSets, getChartOfAccounts, getAccountingPeriods } from '../api/accounting'
import { useAppStore } from './app'

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
      const items = data.items || data
      accountSets.value = items
      if (!currentAccountSetId.value && items.length > 0) {
        currentAccountSetId.value = items[0].id
      }
    } catch (e) {
      console.error('加载账套失败', e)
      useAppStore().showToast('加载账套失败', 'error')
    }
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
      chartOfAccounts.value = data.items || data
    } catch (e) {
      console.error('加载科目表失败', e)
      useAppStore().showToast('加载科目表失败', 'error')
    }
  }

  async function loadPeriods(year) {
    if (!currentAccountSetId.value) return
    try {
      const { data } = await getAccountingPeriods(currentAccountSetId.value, year)
      periods.value = data.items || data
    } catch (e) {
      console.error('加载会计期间失败', e)
      useAppStore().showToast('加载会计期间失败', 'error')
    }
  }

  return {
    accountSets, currentAccountSetId, currentAccountSet,
    chartOfAccounts, periods, loading,
    loadAccountSets, setCurrentAccountSet,
    loadChartOfAccounts, loadPeriods,
  }
})
