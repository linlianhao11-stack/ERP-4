import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { getAllOrders, getUnpaidOrders, getPayments, getStockLogs } from '../api/finance'
import { useAppStore } from './app'

export const useFinanceStore = defineStore('finance', () => {
  const allOrders = ref([])
  const unpaidOrders = ref([])
  const payments = ref([])
  const stockLogs = ref([])
  const financeTab = ref('orders')
  const financeCustomerId = ref('')
  const orderFilter = reactive({ type: '', start: '', end: '', search: '' })
  const logFilter = reactive({ type: '' })

  const loadAllOrders = async () => {
    try {
      const params = {}
      if (orderFilter.type) params.order_type = orderFilter.type
      if (orderFilter.start) params.start_date = orderFilter.start
      if (orderFilter.end) params.end_date = orderFilter.end
      if (orderFilter.search) params.search = orderFilter.search
      const { data } = await getAllOrders(params)
      allOrders.value = data.items || data
    } catch (e) {
      console.error('加载订单失败', e)
      useAppStore().showToast('加载订单失败', 'error')
    }
  }

  const _loaded = ref(false)

  const loadUnpaidOrders = async () => {
    try {
      const p = financeCustomerId.value ? { customer_id: financeCustomerId.value } : {}
      const { data } = await getUnpaidOrders(p)
      unpaidOrders.value = data.items || data
    } catch (e) {
      console.error('加载未付订单失败', e)
      useAppStore().showToast('加载未付订单失败', 'error')
      throw e
    }
  }

  const loadPayments = async () => {
    try {
      const { data } = await getPayments()
      payments.value = data.items || data
    } catch (e) {
      console.error('加载收款记录失败', e)
      useAppStore().showToast('加载收款记录失败', 'error')
      throw e
    }
  }

  let _loadingPromise = null

  const ensureLoaded = async () => {
    if (_loaded.value) return
    if (_loadingPromise) return _loadingPromise
    _loadingPromise = Promise.all([loadUnpaidOrders(), loadPayments()])
      .then(() => { _loaded.value = true })
      .catch(e => {
        console.error('加载财务数据失败', e)
        useAppStore().showToast('加载财务数据失败', 'error')
      })
      .finally(() => { _loadingPromise = null })
    return _loadingPromise
  }

  const loadStockLogs = async () => {
    try {
      const params = {}
      if (logFilter.type) params.change_type = logFilter.type
      const { data } = await getStockLogs(params)
      stockLogs.value = data.items || data
    } catch (e) {
      console.error('加载库存日志失败', e)
      useAppStore().showToast('加载库存日志失败', 'error')
    }
  }

  return {
    allOrders, unpaidOrders, payments, stockLogs,
    financeTab, financeCustomerId, orderFilter, logFilter,
    loadAllOrders, loadUnpaidOrders, loadPayments, loadStockLogs, ensureLoaded
  }
})
