/**
 * useShipment — 物流列表数据加载、筛选、排序 composable
 * 从 LogisticsView 提取，提供物流列表页所需的核心数据和操作
 */
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useSort } from './useSort'
import { usePagination } from './usePagination'
import { useColumnConfig } from './useColumnConfig'
import { getShipments, getCarriers } from '../api/logistics'

export function useShipment() {
  // ---- 排序 ----
  const { sortState: shipmentSort, toggleSort, genericSort } = useSort()
  const { page, pageSize, total, totalPages, hasPagination, paginationParams, visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage, saveNextCursor } = usePagination(20)

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
      saveNextCursor(data.next_cursor)
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
      status: s => s.status || '',
      order_amount: s => Number(s.total_amount) || 0,
      employee: s => s.employee_name || ''
    })
  })

  // ---- 列可见性配置（useColumnConfig 管理，localStorage 持久化）----
  // Task 2 仅迁移现有列定义；新列在 Task 11 添加（需后端 + 模板支持）
  const shipmentColumnDefs = {
    order_no: { label: '订单号', defaultVisible: true },
    order_type: { label: '类型', defaultVisible: true },
    customer: { label: '客户', defaultVisible: true },
    shipping_status: { label: '发货状态', defaultVisible: true },
    carrier: { label: '快递公司', defaultVisible: true },
    tracking_no: { label: '快递单号', defaultVisible: true },
    sn: { label: 'SN码', defaultVisible: false },
    shipped_at: { label: '发货时间', defaultVisible: false },
    status: { label: '物流状态', defaultVisible: true },
    last_info: { label: '物流信息', defaultVisible: false },
    // 新增列（Task 11 添加，与后端 Task 5 和模板同步）
    order_amount: { label: '订单金额', defaultVisible: true, align: 'right' },
    remark: { label: '备注', defaultVisible: true },
    employee: { label: '业务员', defaultVisible: false },
    phone: { label: '收件电话', defaultVisible: false },
    order_created_at: { label: '创建时间', defaultVisible: false },
    actions: { label: '操作', defaultVisible: true }
  }

  const {
    columnLabels, visibleColumns, showColumnMenu,
    toggleColumn, isColumnVisible, resetColumns, menuAttr
  } = useColumnConfig('logistics_columns', shipmentColumnDefs)

  // ---- 生命周期 ----
  onMounted(() => {
    loadShipments()
    loadCarriers()
  })

  onUnmounted(() => {
    clearTimeout(_searchTimer)
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
    resetColumns,
    menuAttr,
    // 排序
    toggleSort,
    // 分页
    page, total, totalPages, hasPagination, visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage,
    // 数据加载
    loadShipments,
    debouncedLoadShipments,
    loadCarriers
  }
}
