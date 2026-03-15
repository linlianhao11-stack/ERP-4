/**
 * 采购订单列表 composable
 * 管理采购单的加载、筛选、搜索、导出、排序、列配置等列表级操作
 */
import { ref, computed, onUnmounted } from 'vue'
import { getPurchaseOrders, exportPurchaseOrders as exportPurchaseOrdersApi } from '../api/purchase'
import { useAppStore } from '../stores/app'
import { usePagination } from './usePagination'
import { useSort } from './useSort'
import { useColumnConfig } from './useColumnConfig'

// 采购订单列定义（模块级常量，所有实例共享同一结构）
const purchaseColumnDefs = {
  po_no: { label: '采购单号', defaultVisible: true },
  supplier: { label: '供应商', defaultVisible: true },
  date: { label: '采购日期', defaultVisible: true },
  total_amount: { label: '总金额', defaultVisible: true, align: 'right' },
  tax_amount: { label: '含税金额', defaultVisible: true, align: 'right' },
  item_count: { label: '品项数', defaultVisible: true, align: 'center' },
  status: { label: '状态', defaultVisible: true, align: 'center' },
  remark: { label: '备注', defaultVisible: true },
  creator: { label: '创建人', defaultVisible: true },
  account_set: { label: '账套', defaultVisible: true },
  return_amount: { label: '退货金额', defaultVisible: false, align: 'right' },
  target_warehouse: { label: '目标仓库', defaultVisible: false },
  target_location: { label: '目标仓位', defaultVisible: false },
  rebate_used: { label: '返利已用', defaultVisible: false, align: 'right' },
  credit_used: { label: '在账资金已用', defaultVisible: false, align: 'right' },
  reviewer: { label: '审核人', defaultVisible: false },
  reviewed_at: { label: '审核时间', defaultVisible: false },
  payment_method: { label: '付款方式', defaultVisible: false },
}

export function usePurchaseOrder() {
  const appStore = useAppStore()
  const { page, pageSize, total, totalPages, hasPagination, paginationParams, resetPage, prevPage, nextPage } = usePagination(20)

  // 排序
  const { sortState: purchaseSort, toggleSort: togglePurchaseSort, genericSort } = useSort()

  // 列配置
  const {
    columnLabels, visibleColumns, showColumnMenu, activeColumns, menuAttr,
    toggleColumn, isColumnVisible, resetColumns,
    viewMode, setViewMode,
  } = useColumnConfig('purchase_columns', purchaseColumnDefs, { supportViewMode: true })

  // 列表数据
  const purchaseOrders = ref([])

  // 筛选条件
  const purchaseStatusFilter = ref('')
  const purchaseAccountSetFilter = ref('')
  const purchaseDateStart = ref('')
  const purchaseDateEnd = ref('')
  const purchaseSearch = ref('')

  // 防抖定时器
  let _poSearchTimer = null

  /** 防抖加载采购订单（用于搜索输入） */
  const debouncedLoad = () => {
    clearTimeout(_poSearchTimer)
    resetPage()
    _poSearchTimer = setTimeout(loadPurchaseOrders, 300)
  }

  /** 根据当前筛选条件加载采购订单列表 */
  const loadPurchaseOrders = async () => {
    try {
      const params = { ...paginationParams.value }
      if (purchaseStatusFilter.value) params.status = purchaseStatusFilter.value
      if (purchaseDateStart.value) params.start_date = purchaseDateStart.value
      if (purchaseDateEnd.value) params.end_date = purchaseDateEnd.value
      if (purchaseSearch.value) params.search = purchaseSearch.value
      if (purchaseAccountSetFilter.value) params.account_set_id = purchaseAccountSetFilter.value
      const { data } = await getPurchaseOrders(params)
      purchaseOrders.value = data.items || data
      total.value = data.total ?? 0
    } catch (e) {
      console.error(e)
    }
  }

  // 排序后的列表
  const sortedPurchaseOrders = computed(() => {
    return genericSort(purchaseOrders.value, {
      po_no: o => o.po_no || '',
      supplier: o => o.supplier_name || '',
      date: o => o.created_at || '',
      total_amount: o => Number(o.total_amount) || 0,
      tax_amount: o => Number(o.tax_amount) || 0,
      status: o => o.status || '',
      creator: o => o.creator_name || '',
    })
  })

  /** 导出采购订单为 CSV 文件 */
  const handleExport = async () => {
    try {
      const params = {}
      if (purchaseStatusFilter.value) params.status = purchaseStatusFilter.value
      if (purchaseDateStart.value) params.start_date = purchaseDateStart.value
      if (purchaseDateEnd.value) params.end_date = purchaseDateEnd.value
      if (purchaseSearch.value) params.search = purchaseSearch.value
      if (purchaseAccountSetFilter.value) params.account_set_id = purchaseAccountSetFilter.value
      const response = await exportPurchaseOrdersApi(params)
      // 创建下载链接并触发下载
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', '采购订单_' + new Date().toISOString().slice(0, 19).replace(/:/g, '') + '.csv')
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      appStore.showToast('导出成功')
    } catch (e) {
      appStore.showToast('导出失败', 'error')
    }
  }

  // 组件卸载时清除定时器
  onUnmounted(() => clearTimeout(_poSearchTimer))

  return {
    purchaseOrders,
    // 分页
    page, pageSize, total, totalPages, hasPagination, resetPage, prevPage, nextPage,
    purchaseStatusFilter,
    purchaseAccountSetFilter,
    purchaseDateStart,
    purchaseDateEnd,
    purchaseSearch,
    loadPurchaseOrders,
    debouncedLoad,
    handleExport,
    // 排序
    purchaseSort, togglePurchaseSort, sortedPurchaseOrders,
    // 列配置
    columnLabels, visibleColumns, showColumnMenu, activeColumns, menuAttr,
    toggleColumn, isColumnVisible, resetColumns,
    viewMode, setViewMode,
  }
}
