import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getWarehouses, getLocations } from '../api/warehouses'

export const useWarehousesStore = defineStore('warehouses', () => {
  const warehouses = ref([])
  const locations = ref([])
  const _loaded = ref(false)

  const loadWarehouses = async () => {
    try {
      const { data } = await getWarehouses()
      warehouses.value = data
    } catch (e) {
      console.error('加载仓库失败', e)
    }
  }

  const loadLocations = async (warehouseId) => {
    try {
      const params = warehouseId ? { warehouse_id: warehouseId } : {}
      const { data } = await getLocations(params)
      locations.value = data
    } catch (e) {
      console.error('加载仓位失败', e)
    }
  }

  let _loadingPromise = null

  const ensureLoaded = async () => {
    if (_loaded.value) return
    if (_loadingPromise) return _loadingPromise
    _loadingPromise = loadWarehouses()
      .then(() => loadLocations())
      .then(() => { _loaded.value = true })
      .catch(e => { console.error('加载仓库/库位失败', e) })
      .finally(() => { _loadingPromise = null })
    return _loadingPromise
  }

  const getLocationsByWarehouse = (warehouseId) => {
    if (!warehouseId) return []
    // First try from warehouses data (which includes locations)
    const wh = warehouses.value.find(w => w.id === parseInt(warehouseId))
    if (wh && wh.locations) return wh.locations
    // Fallback: filter from global locations
    return locations.value.filter(l => l.warehouse_id === parseInt(warehouseId))
  }

  return { warehouses, locations, loadWarehouses, loadLocations, getLocationsByWarehouse, ensureLoaded }
})
