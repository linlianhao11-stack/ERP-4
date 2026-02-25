import { onUnmounted } from 'vue'
import api from '../api'

/**
 * 可取消的 API 请求 composable
 * 组件 unmount 时自动取消所有进行中的请求
 */
export function useApi() {
  const controllers = new Set()

  const get = (url, config = {}) => {
    const controller = new AbortController()
    controllers.add(controller)
    return api.get(url, { ...config, signal: controller.signal })
      .finally(() => controllers.delete(controller))
  }

  const post = (url, data, config = {}) => {
    const controller = new AbortController()
    controllers.add(controller)
    return api.post(url, data, { ...config, signal: controller.signal })
      .finally(() => controllers.delete(controller))
  }

  const put = (url, data, config = {}) => {
    const controller = new AbortController()
    controllers.add(controller)
    return api.put(url, data, { ...config, signal: controller.signal })
      .finally(() => controllers.delete(controller))
  }

  const del = (url, config = {}) => {
    const controller = new AbortController()
    controllers.add(controller)
    return api.delete(url, { ...config, signal: controller.signal })
      .finally(() => controllers.delete(controller))
  }

  const cancelAll = () => {
    controllers.forEach(c => c.abort())
    controllers.clear()
  }

  onUnmounted(cancelAll)

  return { get, post, put, del, cancelAll }
}
