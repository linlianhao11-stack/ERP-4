/**
 * 代采代发订单列表 composable
 * 管理代采代发单的加载、筛选、搜索、排序、列配置等列表级操作
 */
import { ref, computed, onUnmounted } from 'vue'
import { getDropshipOrders } from '../api/dropship'
import { usePagination } from './usePagination'
import { useSort } from './useSort'
import { useColumnConfig } from './useColumnConfig'

// 代采代发订单列定义（模块级常量，所有实例共享同一结构）
const dropshipColumnDefs = {
  ds_no: { label: '单号', defaultVisible: true },
  status: { label: '状态', defaultVisible: true },
  supplier_name: { label: '供应商', defaultVisible: true },
  product_name: { label: '商品', defaultVisible: true },
  quantity: { label: '数量', defaultVisible: true, align: 'right' },
  purchase_total: { label: '采购额', defaultVisible: true, align: 'right' },
  sale_total: { label: '销售额', defaultVisible: true, align: 'right' },
  gross_profit: { label: '毛利', defaultVisible: true, align: 'right' },
  gross_margin: { label: '毛利率', defaultVisible: false, align: 'right' },
  customer_name: { label: '客户', defaultVisible: true },
  platform_order_no: { label: '平台单号', defaultVisible: false },
  tracking_no: { label: '快递单号', defaultVisible: false },
  settlement_type: { label: '结算方式', defaultVisible: false },
  creator_name: { label: '创建人', defaultVisible: false },
  created_at: { label: '创建时间', defaultVisible: true },
}

export function useDropshipOrder() {
  const { page, pageSize, total, totalPages, hasPagination, paginationParams,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage, saveNextCursor }
    = usePagination(20)

  // 排序
  const { sortState, toggleSort, genericSort } = useSort()

  // 列配置
  const {
    columnLabels, visibleColumns, toggleColumn, isColumnVisible, resetColumns,
  } = useColumnConfig('dropship_columns', dropshipColumnDefs)

  // 列表数据
  const items = ref([])

  // 筛选条件
  const statusFilter = ref('')
  const search = ref('')
  const dateStart = ref('')
  const dateEnd = ref('')

  // 防抖定时器
  let _searchTimer = null

  /** 防抖加载（用于搜索输入） */
  const debouncedLoad = () => {
    clearTimeout(_searchTimer)
    resetPage()
    _searchTimer = setTimeout(loadData, 300)
  }

  /** 根据当前筛选条件加载代采代发订单列表 */
  const loadData = async () => {
    try {
      const params = { ...paginationParams.value }
      if (statusFilter.value) params.status = statusFilter.value
      if (search.value) params.search = search.value
      if (dateStart.value) params.start_date = dateStart.value
      if (dateEnd.value) params.end_date = dateEnd.value

      const { data } = await getDropshipOrders(params)
      items.value = data.items || data
      total.value = data.total ?? 0
      saveNextCursor(data.next_cursor)
    } catch (e) {
      console.error('加载代采代发列表失败:', e)
    }
  }

  // 排序后的列表
  const sortedItems = computed(() => {
    return genericSort(items.value, {
      ds_no: item => item.ds_no || '',
      status: item => item.status || '',
      supplier_name: item => item.supplier_name || '',
      product_name: item => item.product_name || '',
      quantity: item => Number(item.quantity) || 0,
      purchase_total: item => Number(item.purchase_total) || 0,
      sale_total: item => Number(item.sale_total) || 0,
      gross_profit: item => Number(item.gross_profit) || 0,
      gross_margin: item => Number(item.gross_margin) || 0,
      customer_name: item => item.customer_name || '',
      created_at: item => item.created_at || '',
    })
  })

  // 组件卸载时清除定时器
  onUnmounted(() => clearTimeout(_searchTimer))

  return {
    items,
    // 分页
    page, pageSize, total, totalPages, hasPagination, visiblePages, pageItemCount,
    resetPage, prevPage, nextPage, goToPage,
    // 筛选
    statusFilter, search, dateStart, dateEnd,
    loadData, debouncedLoad,
    // 排序
    sortState, toggleSort, sortedItems,
    // 列配置
    columnLabels, visibleColumns, toggleColumn, isColumnVisible, resetColumns,
  }
}
