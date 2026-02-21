import { onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { IDLE_TIMEOUT } from '../utils/constants'

export function useIdleTimeout(onTimeout) {
  const authStore = useAuthStore()

  const isLoggedIn = () => !!authStore.token

  const updateLastActive = () => {
    localStorage.setItem('erp_last_active', Date.now().toString())
  }

  const checkIdleTimeout = () => {
    if (!isLoggedIn()) return
    const last = parseInt(localStorage.getItem('erp_last_active') || '0')
    if (last && Date.now() - last > IDLE_TIMEOUT) {
      if (typeof onTimeout === 'function') {
        onTimeout()
      } else {
        authStore.logout()
      }
    }
  }

  let intervalId = null
  let lastHandlerCall = 0
  const events = ['click', 'keydown', 'mousemove', 'touchstart', 'scroll']
  const handler = () => {
    const now = Date.now()
    // 节流：至少间隔 5 秒才写入 localStorage
    if (now - lastHandlerCall < 5000) return
    lastHandlerCall = now
    if (isLoggedIn()) updateLastActive()
  }

  onMounted(() => {
    events.forEach(evt => document.addEventListener(evt, handler, { passive: true }))
    intervalId = setInterval(checkIdleTimeout, 60000)
  })

  onUnmounted(() => {
    events.forEach(evt => document.removeEventListener(evt, handler))
    if (intervalId) clearInterval(intervalId)
  })

  return { updateLastActive, checkIdleTimeout }
}
