/**
 * 创建延迟加载器 — 消除 Store 中重复的 ensureLoaded 模式
 * @param {Function} loadFn - 异步加载函数
 * @returns {{ ensureLoaded: Function, reset: Function, _loaded: import('vue').Ref<boolean> }}
 */
import { ref } from 'vue'

export function createLazyLoader(loadFn) {
  const _loaded = ref(false)
  let _promise = null

  const ensureLoaded = async () => {
    if (_loaded.value) return
    if (_promise) return _promise
    _promise = loadFn()
      .then(() => { _loaded.value = true })
      .catch(() => {})  // 吞掉异常防止 unhandled rejection，调用者可自行 try/catch
      .finally(() => { _promise = null })
    return _promise
  }

  const reset = () => {
    _loaded.value = false
    _promise = null
  }

  return { ensureLoaded, reset, _loaded }
}
