import { useAuthStore } from '../stores/auth'

export function usePermission() {
  const authStore = useAuthStore()

  const hasPermission = (p) => {
    if (p === '_any') return !!authStore.user
    return authStore.user?.role === 'admin' || (authStore.user?.permissions || []).includes(p)
  }

  return { hasPermission }
}
