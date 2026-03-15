import { ref, onBeforeUnmount } from 'vue'

/**
 * 通用搜索 debounce composable
 * @param {Function} loadFn - 加载数据的函数
 * @param {import('vue').Ref<number>} pageRef - 页码 ref（重置为 1）
 * @param {number} delay - 防抖延迟（默认 300ms）
 */
export function useSearch(loadFn, pageRef, delay = 300) {
  const searchQuery = ref('')
  let _timer

  function debouncedSearch() {
    clearTimeout(_timer)
    _timer = setTimeout(() => {
      if (pageRef) pageRef.value = 1
      loadFn()
    }, delay)
  }

  onBeforeUnmount(() => clearTimeout(_timer))

  return { searchQuery, debouncedSearch }
}
