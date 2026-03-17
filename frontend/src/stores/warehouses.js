import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getWarehouses, getLocations } from '../api/warehouses'
import { createLazyLoader } from '../utils/createLazyLoader'

export const useWarehousesStore = defineStore('warehouses', () => {
  const warehouses = ref([])
  const locations = ref([])
  const loading = ref(false)
  const error = ref(null)

  const loadWarehouses = async () => {
    loading.value = true
    try {
      const { data } = await getWarehouses()
      warehouses.value = data.items || data
    } catch (e) {
      error.value = '加载仓库失败'
      console.error('加载仓库失败', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  const loadLocations = async (warehouseId) => {
    loading.value = true
    try {
      const params = warehouseId ? { warehouse_id: warehouseId } : {}
      const { data } = await getLocations(params)
      locations.value = data.items || data
    } catch (e) {
      error.value = '加载仓位失败'
      console.error('加载仓位失败', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  const { ensureLoaded } = createLazyLoader(
    () => Promise.all([loadWarehouses(), loadLocations()])
  )

  const getLocationsByWarehouse = (warehouseId) => {
    if (!warehouseId) return []
    // First try from warehouses data (which includes locations)
    const wh = warehouses.value.find(w => w.id === parseInt(warehouseId))
    if (wh && wh.locations) return wh.locations
    // Fallback: filter from global locations
    return locations.value.filter(l => l.warehouse_id === parseInt(warehouseId))
  }

  return { warehouses, locations, loading, error, loadWarehouses, loadLocations, getLocationsByWarehouse, ensureLoaded }
})
