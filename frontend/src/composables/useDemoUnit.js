/**
 * 样机管理 composables
 */
import { ref, computed, onUnmounted } from 'vue'
import { getDemoUnits, getDemoLoans, getDemoStats } from '../api/demo'
import { usePagination } from './usePagination'
import { useSort } from './useSort'

/**
 * 样机台账列表管理
 */
export function useDemoUnit() {
  const { page, pageSize, total, totalPages, hasPagination, paginationParams,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage } = usePagination(50)
  const { sortState, toggleSort, genericSort } = useSort()

  const units = ref([])
  const loading = ref(false)
  const statusFilter = ref('')
  const warehouseFilter = ref('')
  const search = ref('')

  let _timer = null
  const debouncedLoad = () => {
    clearTimeout(_timer)
    resetPage()
    _timer = setTimeout(loadUnits, 300)
  }

  const loadUnits = async () => {
    loading.value = true
    try {
      const params = { ...paginationParams.value }
      if (statusFilter.value) params.status = statusFilter.value
      if (warehouseFilter.value) params.warehouse_id = warehouseFilter.value
      if (search.value) params.search = search.value
      const { data } = await getDemoUnits(params)
      units.value = data.items || []
      total.value = data.total ?? 0
    } catch (e) {
      console.error('加载样机列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  const sortedUnits = computed(() =>
    genericSort(units.value, {
      code: i => i.code,
      product_name: i => i.product_name || '',
      status: i => i.status || '',
      cost_price: i => Number(i.cost_price) || 0,
      total_loan_count: i => i.total_loan_count || 0,
    })
  )

  onUnmounted(() => clearTimeout(_timer))

  return {
    units, loading, statusFilter, warehouseFilter, search,
    loadUnits, debouncedLoad, sortedUnits,
    sortState, toggleSort,
    page, pageSize, total, totalPages, hasPagination,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage,
  }
}

/**
 * 借还记录列表管理
 */
export function useDemoLoan() {
  const { page, pageSize, total, totalPages, hasPagination, paginationParams,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage } = usePagination(50)

  const loans = ref([])
  const loading = ref(false)
  const statusFilter = ref('')
  const search = ref('')
  const dateStart = ref('')
  const dateEnd = ref('')

  let _timer = null
  const debouncedLoad = () => {
    clearTimeout(_timer)
    resetPage()
    _timer = setTimeout(loadLoans, 300)
  }

  const loadLoans = async () => {
    loading.value = true
    try {
      const params = { ...paginationParams.value }
      if (statusFilter.value) params.status = statusFilter.value
      if (search.value) params.search = search.value
      if (dateStart.value) params.start_date = dateStart.value
      if (dateEnd.value) params.end_date = dateEnd.value
      const { data } = await getDemoLoans(params)
      loans.value = data.items || []
      total.value = data.total ?? 0
    } catch (e) {
      console.error('加载借还记录失败:', e)
    } finally {
      loading.value = false
    }
  }

  onUnmounted(() => clearTimeout(_timer))

  return {
    loans, loading, statusFilter, search, dateStart, dateEnd,
    loadLoans, debouncedLoad,
    page, pageSize, total, totalPages, hasPagination,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage,
  }
}

/**
 * 样机统计数据
 */
export function useDemoStats() {
  const stats = ref({ total: 0, in_stock: 0, lent_out: 0, overdue: 0, total_value: 0 })

  const loadStats = async (warehouseId) => {
    try {
      const params = {}
      if (warehouseId) params.warehouse_id = warehouseId
      const { data } = await getDemoStats(params)
      stats.value = data
    } catch (e) {
      console.error('加载统计失败:', e)
    }
  }

  return { stats, loadStats }
}
