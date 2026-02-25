import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCustomers } from '../api/customers'
import { fuzzyMatchAny } from '../utils/helpers'

export const useCustomersStore = defineStore('customers', () => {
  const customers = ref([])
  const customerSearch = ref('')
  const error = ref(null)
  const _loaded = ref(false)

  const filteredCustomers = computed(() => {
    const kw = customerSearch.value
    if (!kw) return customers.value
    return customers.value.filter(c => fuzzyMatchAny([c.name, c.phone], kw))
  })

  const loadCustomers = async () => {
    error.value = null
    try {
      const { data } = await getCustomers()
      customers.value = data
      _loaded.value = true
    } catch (e) {
      error.value = '客户数据加载失败'
      console.error('loadCustomers error:', e)
    }
  }

  let _loadingPromise = null

  const ensureLoaded = async () => {
    if (_loaded.value) return
    if (_loadingPromise) return _loadingPromise
    _loadingPromise = loadCustomers().finally(() => { _loadingPromise = null })
    return _loadingPromise
  }

  return { customers, customerSearch, error, filteredCustomers, loadCustomers, ensureLoaded }
})
