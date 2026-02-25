import { useAuthStore } from '../stores/auth'

export function usePermission() {
  const authStore = useAuthStore()
  const hasPermission = (p) => authStore.hasPermission(p)
  return { hasPermission }
}
