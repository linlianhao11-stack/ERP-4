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

  /** 当前页显示条数 */
  const pageItemCount = computed(() => {
    if (total.value <= 0) return 0
    return Math.min(pageSize, total.value - (page.value - 1) * pageSize)
  })

  /** 可见页码数组，包含数字和省略号标记 '…' */
  const visiblePages = computed(() => {
    const tp = totalPages.value
    const cur = page.value
    if (tp <= 5) return Array.from({ length: tp }, (_, i) => i + 1)
    if (cur <= 3) return [1, 2, 3, '…', tp]
    if (cur >= tp - 2) return [1, '…', tp - 2, tp - 1, tp]
    return [1, '…', cur - 1, cur, cur + 1, '…', tp]
  })

  const setTotal = (t) => { total.value = t }
  const resetPage = () => { page.value = 1 }
  const prevPage = () => { if (page.value > 1) page.value-- }
  const nextPage = () => { if (page.value < totalPages.value) page.value++ }
  /** 跳转到指定页 */
  const goToPage = (n) => { if (n >= 1 && n <= totalPages.value) page.value = n }

  return {
    page, pageSize, total, totalPages,
    hasPagination, paginationParams, visiblePages, pageItemCount,
    setTotal, resetPage, prevPage, nextPage, goToPage
  }
}
