import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getProducts } from '../api/products'
import { createLazyLoader } from '../utils/createLazyLoader'

export const useProductsStore = defineStore('products', () => {
  const products = ref([])
  const error = ref(null)

  const loadProducts = async (warehouseId) => {
    error.value = null
    try {
      // 全量加载商品列表，使用足够大的 limit 避免数据截断
      const params = warehouseId ? { warehouse_id: warehouseId } : { limit: 99999 }
      const { data } = await getProducts(params)
      if (!warehouseId) {
        products.value = data.items ?? data
      }
      return data
    } catch (e) {
      error.value = '商品数据加载失败'
      console.error(e)
    }
  }

  const { ensureLoaded } = createLazyLoader(() => loadProducts())

  return { products, error, loadProducts, ensureLoaded }
})
