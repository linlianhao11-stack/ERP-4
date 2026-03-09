/**
 * useShipment — 物流列表数据加载、筛选、排序 composable
 * 从 LogisticsView 提取，提供物流列表页所需的核心数据和操作
 */
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useSort } from './useSort'
import { usePagination } from './usePagination'
import { getShipments, getCarriers } from '../api/logistics'

export function useShipment() {
  // ---- 排序 ----
  const { sortState: shipmentSort, toggleSort, genericSort } = useSort()
  const { page, pageSize, total, totalPages, hasPagination, paginationParams, resetPage, prevPage, nextPage } = usePagination(50)

  // ---- 列表数据 ----
  const shipments = ref([])
  /** 筛选条件：status 物流状态，search 搜索关键词 */
  const shipmentFilter = reactive({ status: '', search: '' })
  /** 快递公司列表 */
  const carriers = ref([])

  // ---- 搜索防抖定时器 ----
  let _searchTimer = null
  /** 带 300ms 防抖的列表加载 */
  const debouncedLoadShipments = () => {
    clearTimeout(_searchTimer)
    resetPage()
    _searchTimer = setTimeout(loadShipments, 300)
  }

  /** 加载物流列表 */
  const loadShipments = async () => {
    try {
      const params = { ...paginationParams.value }
      if (shipmentFilter.status) params.status = shipmentFilter.status
      if (shipmentFilter.search) params.search = shipmentFilter.search
      const { data } = await getShipments(params)
      shipments.value = data.items || data
      total.value = data.total ?? 0
    } catch (e) {
      console.error(e)
    }
  }

  /** 加载快递公司列表 */
  const loadCarriers = async () => {
    try {
      const { data } = await getCarriers()
      carriers.value = data
    } catch (e) {
      console.error(e)
    }
  }

  /** 排序后的物流列表 */
  const sortedShipments = computed(() => {
    return genericSort(shipments.value, {
      order_no: s => s.order_no || '',
      order_type: s => s.order_type || '',
      customer: s => s.customer_name || '',
      carrier: s => s.carrier_name || '',
      shipped_at: s => s.created_at || '',
      status: s => s.status || ''
    })
  })

  // ---- 列可见性配置（localStorage 持久化）----
  const defaultColumns = {
    order_no: true,
    order_type: true,
    customer: true,
    shipping_status: true,
    carrier: true,
    tracking_no: true,
    sn: false,
    shipped_at: false,
    status: true,
    last_info: false,
    actions: true
  }

  /** 列名中文标签 */
  const columnLabels = {
    order_no: '订单号',
    order_type: '类型',
    customer: '客户',
    shipping_status: '发货状态',
    carrier: '快递公司',
    tracking_no: '快递单号',
    sn: 'SN码',
    shipped_at: '发货时间',
    status: '物流状态',
    last_info: '物流信息',
    actions: '操作'
  }

  // 从 localStorage 恢复列可见性
  let _savedColumns = null
  try { _savedColumns = JSON.parse(localStorage.getItem('logistics_columns')) } catch (e) { /* 忽略损坏数据 */ }
  const visibleColumns = reactive({ ...defaultColumns, ...(_savedColumns || {}) })

  /** 列设置菜单是否展开 */
  const showColumnMenu = ref(false)

  /** 切换某列的可见性 */
  const toggleColumn = (key) => {
    visibleColumns[key] = !visibleColumns[key]
    localStorage.setItem('logistics_columns', JSON.stringify(visibleColumns))
  }

  /** 判断某列是否可见 */
  const isColumnVisible = (key) => visibleColumns[key]

  // ---- 点击外部关闭列菜单 ----
  const handleDocClick = (e) => {
    if (showColumnMenu.value && !e.target.closest('[data-column-menu]')) {
      showColumnMenu.value = false
    }
  }

  // ---- 生命周期 ----
  onMounted(() => {
    loadShipments()
    loadCarriers()
    document.addEventListener('click', handleDocClick)
  })

  onUnmounted(() => {
    clearTimeout(_searchTimer)
    document.removeEventListener('click', handleDocClick)
  })

  return {
    // 数据
    shipments,
    shipmentFilter,
    carriers,
    shipmentSort,
    sortedShipments,
    // 列可见性
    columnLabels,
    visibleColumns,
    showColumnMenu,
    toggleColumn,
    isColumnVisible,
    // 排序
    toggleSort,
    // 分页
    page, totalPages, hasPagination, resetPage, prevPage, nextPage,
    // 数据加载
    loadShipments,
    debouncedLoadShipments,
    loadCarriers
  }
}
