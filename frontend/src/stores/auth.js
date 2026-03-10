import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMe, logoutApi } from '../api/auth'
import { IDLE_TIMEOUT } from '../utils/constants'
import { useAppStore } from './app'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref('')

  const hasPermission = (p) => {
    if (p === '_any') return !!user.value
    return user.value?.role === 'admin' || (user.value?.permissions || []).includes(p)
  }

  const setAuth = (t, u) => {
    token.value = t
    user.value = u
    localStorage.setItem('erp_token', t)
  }

  let _logoutPromise = null
  const logout = async () => {
    if (_logoutPromise) return _logoutPromise
    _logoutPromise = (async () => {
      try { await logoutApi() } catch (e) { /* ignore */ }
      token.value = ''
      user.value = null
      localStorage.removeItem('erp_token')
      localStorage.removeItem('erp_last_active')
      // Clear transient UI state (toasts, modals, confirm dialogs)
      try { useAppStore().resetTransientState() } catch (e) { /* app store may not be initialized */ }
    })()
    try { return await _logoutPromise } finally { _logoutPromise = null }
  }

  let _checkPromise = null

  const checkAuth = async () => {
    const t = localStorage.getItem('erp_token')
    if (!t) return false
    const last = parseInt(localStorage.getItem('erp_last_active') || '0')
    if (last && Date.now() - last > IDLE_TIMEOUT) {
      await logout()
      return false
    }
    if (_checkPromise) return _checkPromise
    // 先不设置 token.value，等验证通过再设置，避免状态不一致
    _checkPromise = (async () => {
      try {
        const { data } = await getMe()
        token.value = t
        user.value = data
        localStorage.setItem('erp_last_active', Date.now().toString())
        return true
      } catch (e) {
        // Only treat 401/403 as auth failures; other errors (500, network) should not log the user out
        const status = e?.response?.status
        if (status === 401 || status === 403) {
          logout()
          return false
        }
        // For server errors or network issues, keep existing auth state
        throw e
      }
    })().finally(() => { _checkPromise = null })
    return _checkPromise
  }

  return { user, token, hasPermission, setAuth, logout, checkAuth }
})
