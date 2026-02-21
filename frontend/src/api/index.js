import axios from 'axios'
import router from '../router'

const api = axios.create({ baseURL: '/api' })

// 全局回调（由 App.vue 注册，避免循环依赖）
let _onError = null
let _onUnauthorized = null
export function setApiErrorHandler(fn) {
  _onError = fn
}
export function setApiUnauthorizedHandler(fn) {
  _onUnauthorized = fn
}

api.interceptors.request.use(config => {
  const token = localStorage.getItem('erp_token')
  if (token) config.headers.Authorization = 'Bearer ' + token
  return config
})

let _isRedirectingToLogin = false

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('erp_token')
      localStorage.removeItem('erp_last_active')
      if (_onUnauthorized) _onUnauthorized()
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

export default api
