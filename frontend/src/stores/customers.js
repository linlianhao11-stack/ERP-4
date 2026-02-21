import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCustomers } from '../api/customers'
import { fuzzyMatchAny } from '../utils/helpers'

export const useCustomersStore = defineStore('customers', () => {
  const customers = ref([])
  const customerSearch = ref('')
  const _loaded = ref(false)

  const filteredCustomers = computed(() => {
    const kw = customerSearch.value
    if (!kw) return customers.value
    return customers.value.filter(c => fuzzyMatchAny([c.name, c.phone], kw))
  })

  const loadCustomers = async () => {
    try {
      const { data } = await getCustomers()
      customers.value = data
      _loaded.value = true
    } catch (e) {
      console.error('加载客户失败', e)
    }
  }

  let _loadingPromise = null

  const ensureLoaded = async () => {
    if (_loaded.value) return
    if (_loadingPromise) return _loadingPromise
    _loadingPromise = loadCustomers().finally(() => { _loadingPromise = null })
    return _loadingPromise
  }

  return { customers, customerSearch, filteredCustomers, loadCustomers, ensureLoaded }
})
