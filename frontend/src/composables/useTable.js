import { ref, reactive, onUnmounted } from 'vue'

/**
 * 表格数据加载 + 搜索防抖 + loading 状态
 * @param {Function} fetchFn - 异步数据获取函数，接受 params 参数，返回 { data }
 * @param {Object} options - 可选配置
 * @param {number} options.debounce - 搜索防抖毫秒数，默认 300
 * @returns {Object} items, loading, search, filters, loadData, debouncedLoad
 *
 * 用法：
 *   const { items, loading, search, filters, loadData, debouncedLoad } = useTable(getAllOrders)
 *   filters.type = 'CASH'
 *   loadData()                   // 立即加载
 *   search.value = 'keyword'     // 设置搜索词
 *   debouncedLoad()              // 防抖加载
 */
export function useTable(fetchFn, options = {}) {
  const { debounce = 300 } = options

  const items = ref([])
  const loading = ref(false)
  const search = ref('')
  const filters = reactive({})

  let _timer = null

  const loadData = async (extraParams = {}) => {
    loading.value = true
    try {
      const params = { ...filters, ...extraParams }
      if (search.value) params.search = search.value
      const { data } = await fetchFn(params)
      items.value = Array.isArray(data) ? data : (data.items || [])
    } catch (e) {
      console.error('加载数据失败:', e)
    } finally {
      loading.value = false
    }
  }

  const debouncedLoad = (extraParams) => {
    clearTimeout(_timer)
    _timer = setTimeout(() => loadData(extraParams), debounce)
  }

  onUnmounted(() => {
    if (_timer) {
      clearTimeout(_timer)
      _timer = null
    }
  })

  return { items, loading, search, filters, loadData, debouncedLoad }
}
