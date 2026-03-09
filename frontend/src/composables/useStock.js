/**
 * 库存列表 composable
 * 提供库存页面的筛选、排序、搜索、导出等核心逻辑
 */
import { ref, reactive, computed } from 'vue'
import { useAppStore } from '../stores/app'
import { useProductsStore } from '../stores/products'
import { useWarehousesStore } from '../stores/warehouses'
import { exportStock as apiExportStock } from '../api/stock'
import { getWarehouses } from '../api/warehouses'
import { fuzzyMatchAny } from '../utils/helpers'

export function useStock() {
  const appStore = useAppStore()
  const productsStore = useProductsStore()
  const warehousesStore = useWarehousesStore()

  // 从 store 获取数据
  const products = computed(() => productsStore.products)
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

  /** 按关键词过滤后的商品列表 */
  const filteredProducts = computed(() => {
    const kw = productSearch.value
    if (!kw) return products.value
    return products.value.filter(p => fuzzyMatchAny([p.sku, p.name, p.brand, p.category], kw))
  })

  /** 展平并排序后的库存行（商品+库存位置） */
  const sortedStockRows = computed(() => {
    const rows = []
    filteredProducts.value.forEach(p => {
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
    filteredProducts.value.some(p => p.stocks && p.stocks.some(s => showVirtualStock.value || !s.is_virtual))
  )

  /** 加载商品列表（可按仓库筛选） */
  const loadProductsData = () => {
    productsStore.loadProducts(stockWarehouseFilter.value || undefined)
  }

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
    products,
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
    filteredProducts,
    sortedStockRows,
    hasStockProducts,
    // 方法
    loadProductsData,
    loadVirtualWarehouses,
    onToggleVirtualStock,
    handleExportStock,
  }
}
