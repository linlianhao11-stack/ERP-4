/**
 * 采购订单列表 composable
 * 管理采购单的加载、筛选、搜索、导出等列表级操作
 */
import { ref, onUnmounted } from 'vue'
import { getPurchaseOrders, exportPurchaseOrders as exportPurchaseOrdersApi } from '../api/purchase'
import { useAppStore } from '../stores/app'

export function usePurchaseOrder() {
  const appStore = useAppStore()

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
    _poSearchTimer = setTimeout(loadPurchaseOrders, 300)
  }

  /** 根据当前筛选条件加载采购订单列表 */
  const loadPurchaseOrders = async () => {
    try {
      const params = {}
      if (purchaseStatusFilter.value) params.status = purchaseStatusFilter.value
      if (purchaseDateStart.value) params.start_date = purchaseDateStart.value
      if (purchaseDateEnd.value) params.end_date = purchaseDateEnd.value
      if (purchaseSearch.value) params.search = purchaseSearch.value
      if (purchaseAccountSetFilter.value) params.account_set_id = purchaseAccountSetFilter.value
      const { data } = await getPurchaseOrders(params)
      purchaseOrders.value = data.items || data
    } catch (e) {
      console.error(e)
    }
  }

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
    purchaseStatusFilter,
    purchaseAccountSetFilter,
    purchaseDateStart,
    purchaseDateEnd,
    purchaseSearch,
    loadPurchaseOrders,
    debouncedLoad,
    handleExport
  }
}
