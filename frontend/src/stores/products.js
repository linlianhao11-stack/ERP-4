import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getProducts } from '../api/products'

export const useProductsStore = defineStore('products', () => {
  const products = ref([])
  const _loaded = ref(false)

  const loadProducts = async (warehouseId) => {
    try {
      const params = {}
      if (warehouseId) params.warehouse_id = warehouseId
      const { data } = await getProducts(params)
      products.value = data
      if (!warehouseId) {
        _loaded.value = true
      }
    } catch (e) {
      console.error('加载商品失败', e)
    }
  }

  let _loadingPromise = null

  const ensureLoaded = async () => {
    if (_loaded.value) return
    if (_loadingPromise) return _loadingPromise
    _loadingPromise = loadProducts().finally(() => { _loadingPromise = null })
    return _loadingPromise
  }

  return { products, loadProducts, ensureLoaded }
})
