import axios from 'axios'
import router from '../router'

const api = axios.create({ baseURL: '/api', timeout: 30000 })

// 全局回调（由 App.vue 注册，避免循环依赖）
let _onError = null
let _onUnauthorized = null
export function setApiErrorHandler(fn) {
  _onError = fn
}
export function setApiUnauthorizedHandler(fn) {
  _onUnauthorized = fn
}

// 防重复提交：同一 URL + method 的 POST/PUT/DELETE 请求去重
const _pendingRequests = new Map()

function getRequestKey(config) {
  if (['post', 'put', 'delete'].includes(config.method)) {
    return `${config.method}:${config.url}`
  }
  return null
}

api.interceptors.request.use(config => {
  const key = getRequestKey(config)
  if (key) {
    if (_pendingRequests.has(key)) {
      const controller = new AbortController()
      config.signal = controller.signal
      controller.abort('重复请求已取消')
      return config
    }
    _pendingRequests.set(key, true)
    config._dedupKey = key
  }
  return config
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('erp_token')
  if (token) config.headers.Authorization = 'Bearer ' + token
  return config
})

let _isRedirectingToLogin = false

api.interceptors.response.use(
  response => {
    if (response.config?._dedupKey) {
      _pendingRequests.delete(response.config._dedupKey)
    }
    return response
  },
  async error => {
    // Silently ignore deliberately canceled duplicate requests
    if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
      return Promise.reject(error)
    }
    const config = error.config
    // 自动重试：GET 请求遇到 5xx 错误时重试一次
    if (config && !config._retry && config.method === 'get' && error.response?.status >= 500) {
      config._retry = true
      await new Promise(r => setTimeout(r, 1000))
      return api(config)
    }
    // 清理防重复提交标记
    if (error.config?._dedupKey) {
      _pendingRequests.delete(error.config._dedupKey)
    }
    if (error.response?.status === 401) {
      localStorage.removeItem('erp_token')
      localStorage.removeItem('erp_last_active')
      // 跳过 logout 端点的 401，避免 logout→401→logout 无限循环
      if (_onUnauthorized && !config?.url?.includes('/auth/logout')) _onUnauthorized()
      // 防止多个并发 401 同时跳转
      if (!_isRedirectingToLogin) {
        _isRedirectingToLogin = true
        router.replace('/login').finally(() => {
          _isRedirectingToLogin = false
        })
      }
    } else if (error.response?.status === 422 && _onError) {
      const detail = error.response?.data?.detail
      if (Array.isArray(detail) && detail.length > 0) {
        const msgs = detail.map(e => {
          if (e.type === 'string_too_short') return `${e.loc?.[e.loc.length - 1] || '字段'}长度不能少于${e.ctx?.min_length}位`
          if (e.type === 'string_too_long') return `${e.loc?.[e.loc.length - 1] || '字段'}长度不能超过${e.ctx?.max_length}位`
          if (e.type === 'value_error') return e.msg
          return e.msg || '输入格式不正确'
        })
        _onError(msgs.join('；'), 'error')
      } else {
        _onError(typeof detail === 'string' ? detail : '输入数据格式不正确', 'error')
      }
    } else if (error.response?.status === 403 && _onError) {
      _onError(error.response?.data?.detail || '无权限执行此操作', 'error')
    } else if (error.response?.status === 404 && _onError) {
      _onError(error.response?.data?.detail || '请求的资源不存在', 'error')
    } else if (error.response?.status >= 500 && _onError) {
      _onError(error.response?.data?.detail || '服务器错误，请稍后重试', 'error')
    }
    return Promise.reject(error)
  }
)

// GET 请求去重：同一 URL + params 的并发 GET 共享同一个 Promise
const _pendingGets = new Map()
const _originalGet = api.get.bind(api)
api.get = function dedupGet(url, config = {}) {
  if (config.responseType) return _originalGet(url, config)
  const paramStr = config.params ? JSON.stringify(config.params) : ''
  const key = `${url}:${paramStr}`
  if (_pendingGets.has(key)) return _pendingGets.get(key)
  const promise = _originalGet(url, config).finally(() => _pendingGets.delete(key))
  _pendingGets.set(key, promise)
  return promise
}

export default api
