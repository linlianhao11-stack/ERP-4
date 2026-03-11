/**
 * 库存列表 composable
 * 提供库存页面的筛选、排序、搜索、导出等核心逻辑
 * 使用服务端分页 + 搜索，不再全量加载商品
 */
import { ref, reactive, computed, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'
import { useWarehousesStore } from '../stores/warehouses'
import { getProducts } from '../api/products'
import { exportStock as apiExportStock } from '../api/stock'
import { getWarehouses } from '../api/warehouses'
import { usePagination } from './usePagination'
import { useColumnConfig } from './useColumnConfig'

const stockColumnDefs = {
  brand: { label: '品牌', defaultVisible: true },
  name: { label: '商品名称', defaultVisible: true },
  warehouse: { label: '仓位', defaultVisible: true },
  retail_price: { label: '零售价', defaultVisible: true, align: 'right' },
  cost_price: { label: '成本', defaultVisible: true, align: 'right' },
  quantity: { label: '库存', defaultVisible: true, align: 'right' },
  reserved_qty: { label: '预留', defaultVisible: true, align: 'right' },
  available_qty: { label: '可用', defaultVisible: true, align: 'right' },
  age_days: { label: '库龄', defaultVisible: true, align: 'center' },
  actions: { label: '操作', defaultVisible: true, align: 'center' },
}

export function useStock() {
  const appStore = useAppStore()
  const warehousesStore = useWarehousesStore()
  const { page, pageSize, total, totalPages, hasPagination, paginationParams, resetPage, prevPage, nextPage } = usePagination(50)

  const {
    columnLabels, visibleColumns, showColumnMenu, menuAttr,
    toggleColumn, isColumnVisible, resetColumns,
  } = useColumnConfig('stock_columns', stockColumnDefs)

  // 本地商品数据（分页加载，非全量）
  const stockProducts = ref([])
  const warehouses = computed(() => warehousesStore.warehouses)
  const locations = computed(() => warehousesStore.locations)

  // 本地筛选状态
  const stockWarehouseFilter = ref('')
  const showVirtualStock = ref(false)
  const virtualWarehouses = ref([])
  const productSearch = ref('')

  // 排序状态
  const stockSort = reactive({ key: '', order: '' })

  /** 切换排序字段/方向 */
  const toggleStockSort = (key) => {
    if (stockSort.key === key) {
      if (stockSort.order === 'asc') stockSort.order = 'desc'
      else { stockSort.key = ''; stockSort.order = '' }
    } else {
      stockSort.key = key
      stockSort.order = 'asc'
    }
  }

  /** 展平并排序后的库存行（商品+库存位置） */
  const sortedStockRows = computed(() => {
    const rows = []
    stockProducts.value.forEach(p => {
      if (!p.stocks || !p.stocks.length) return
      const stocks = showVirtualStock.value ? p.stocks : p.stocks.filter(x => !x.is_virtual)
      stocks.forEach(s => { rows.push({ p, s }) })
    })
    if (!stockSort.key) return rows
    const k = stockSort.key
    const asc = stockSort.order === 'asc'
    rows.sort((a, b) => {
      let va, vb
      if (k === 'brand') { va = (a.p.brand || '').toLowerCase(); vb = (b.p.brand || '').toLowerCase() }
      else if (k === 'name') { va = (a.p.name || '').toLowerCase(); vb = (b.p.name || '').toLowerCase() }
      else if (k === 'warehouse') { va = (a.s.warehouse_name || '') + (a.s.location_code || ''); vb = (b.s.warehouse_name || '') + (b.s.location_code || '') }
      else if (k === 'retail_price') { va = Number(a.p.retail_price) || 0; vb = Number(b.p.retail_price) || 0 }
      else if (k === 'cost_price') { va = Number(a.p.cost_price) || 0; vb = Number(b.p.cost_price) || 0 }
      else if (k === 'quantity') { va = a.s.quantity || 0; vb = b.s.quantity || 0 }
      else if (k === 'age') { va = a.p.age_days || 0; vb = b.p.age_days || 0 }
      else return 0
      if (va < vb) return asc ? -1 : 1
      if (va > vb) return asc ? 1 : -1
      return 0
    })
    return rows
  })

  /** 是否存在有库存的商品（控制空状态展示） */
  const hasStockProducts = computed(() =>
    stockProducts.value.some(p => p.stocks && p.stocks.some(s => showVirtualStock.value || !s.is_virtual))
  )

  /** 加载商品列表（服务端分页 + 搜索） */
  const loadProductsData = async () => {
    try {
      const params = { ...paginationParams.value }
      if (stockWarehouseFilter.value) params.warehouse_id = stockWarehouseFilter.value
      if (productSearch.value) params.keyword = productSearch.value
      const { data } = await getProducts(params)
      stockProducts.value = data.items || data
      total.value = data.total ?? 0
    } catch (e) {
      console.error(e)
    }
  }

  // 搜索防抖
  let _searchTimer = null
  const debouncedSearch = () => {
    clearTimeout(_searchTimer)
    resetPage()
    _searchTimer = setTimeout(loadProductsData, 300)
  }
  onUnmounted(() => clearTimeout(_searchTimer))

  /** 加载寄售（虚拟）仓库列表 */
  const loadVirtualWarehouses = async () => {
    try {
      const { data } = await getWarehouses({ include_virtual: true })
      virtualWarehouses.value = data.filter(w => w.is_virtual)
    } catch (e) {
      console.error(e)
      appStore.showToast(e.response?.data?.detail || '加载数据失败', 'error')
    }
  }

  /** 切换寄售显示时，懒加载虚拟仓库 */
  const onToggleVirtualStock = async () => {
    if (showVirtualStock.value && !virtualWarehouses.value.length) await loadVirtualWarehouses()
  }

  /** 导出库存为 CSV */
  const handleExportStock = async () => {
    if (appStore.submitting) return
    appStore.submitting = true
    try {
      const params = {}
      if (stockWarehouseFilter.value) params.warehouse_id = stockWarehouseFilter.value
      const response = await apiExportStock(params)
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', '库存表_' + new Date().toISOString().slice(0, 19).replace(/:/g, '') + '.csv')
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      appStore.showToast('导出成功')
    } catch (e) {
      appStore.showToast('导出失败', 'error')
    } finally {
      appStore.submitting = false
    }
  }

  return {
    // 数据
    stockProducts,
    warehouses,
    locations,
    // 筛选
    stockWarehouseFilter,
    showVirtualStock,
    virtualWarehouses,
    productSearch,
    // 排序
    stockSort,
    toggleStockSort,
    // 计算属性
    sortedStockRows,
    hasStockProducts,
    // 分页
    page, totalPages, hasPagination, resetPage, prevPage, nextPage,
    // 方法
    loadProductsData,
    debouncedSearch,
    loadVirtualWarehouses,
    onToggleVirtualStock,
    handleExportStock,
    // 列配置
    columnLabels, visibleColumns, showColumnMenu, menuAttr,
    toggleColumn, isColumnVisible, resetColumns,
  }
}
