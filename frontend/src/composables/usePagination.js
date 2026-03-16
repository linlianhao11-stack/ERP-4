/**
 * 分页 composable
 * 支持传统 offset/limit 和游标分页（cursor-based pagination）
 * 当后端返回 next_cursor 时自动启用游标模式，顺序翻页性能 O(1)
 * 跳转到未缓存的页码时自动退化为 offset 模式
 * @param {number} size - 每页条数，默认 20
 */
import { ref, computed } from 'vue'

export function usePagination(size = 20) {
  const page = ref(1)
  const pageSize = size
  const total = ref(0)

  // 游标缓存：page -> cursor 映射
  const pageCursors = ref({})

  const totalPages = computed(() => Math.ceil(total.value / pageSize))
  const hasPagination = computed(() => total.value > pageSize)

  /** 构建分页参数：优先使用 cursor，否则退化为 offset */
  const paginationParams = computed(() => {
    const c = pageCursors.value[page.value]
    if (c) {
      return { cursor: c, limit: pageSize }
    }
    return {
      offset: (page.value - 1) * pageSize,
      limit: pageSize
    }
  })

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
  const resetPage = () => {
    page.value = 1
    pageCursors.value = {}  // 重置时清空所有游标
  }
  const prevPage = () => { if (page.value > 1) page.value-- }
  const nextPage = () => { if (page.value < totalPages.value) page.value++ }
  /** 跳转到指定页 */
  const goToPage = (n) => { if (n >= 1 && n <= totalPages.value) page.value = n }

  /** 存储后端返回的 next_cursor，关联到下一页 */
  const saveNextCursor = (nextCursor) => {
    if (nextCursor) {
      pageCursors.value[page.value + 1] = nextCursor
    }
  }

  return {
    page, pageSize, total, totalPages,
    hasPagination, paginationParams, visiblePages, pageItemCount,
    setTotal, resetPage, prevPage, nextPage, goToPage,
    saveNextCursor
  }
}
