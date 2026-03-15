/**
 * 分页 composable
 * 提供分页状态管理，与后端 offset/limit 接口配合使用
 * @param {number} size - 每页条数，默认 20
 */
import { ref, computed } from 'vue'

export function usePagination(size = 20) {
  const page = ref(1)
  const pageSize = size
  const total = ref(0)

  const totalPages = computed(() => Math.ceil(total.value / pageSize))
  const hasPagination = computed(() => total.value > pageSize)

  /** 构建 offset/limit 参数供 API 调用 */
  const paginationParams = computed(() => ({
    offset: (page.value - 1) * pageSize,
    limit: pageSize
  }))

  const setTotal = (t) => { total.value = t }
  const resetPage = () => { page.value = 1 }
  const prevPage = () => { if (page.value > 1) page.value-- }
  const nextPage = () => { if (page.value < totalPages.value) page.value++ }

  return {
    page, pageSize, total, totalPages,
    hasPagination, paginationParams,
    setTotal, resetPage, prevPage, nextPage
  }
}
