import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  { path: '/dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { perm: 'dashboard' } },
  { path: '/sales', name: 'sales', component: () => import('../views/SalesView.vue'), meta: { perm: 'sales' } },
  { path: '/stock', name: 'stock', component: () => import('../views/StockView.vue'), meta: { perm: 'stock_view' } },
  { path: '/purchase', name: 'purchase', component: () => import('../views/PurchaseView.vue'), meta: { perm: 'purchase' } },
  { path: '/consignment', name: 'consignment', component: () => import('../views/ConsignmentView.vue'), meta: { perm: 'consignment' } },
  { path: '/logistics', name: 'logistics', component: () => import('../views/LogisticsView.vue'), meta: { perm: 'logistics' } },
  { path: '/finance', name: 'finance', component: () => import('../views/FinanceView.vue'), meta: { perm: 'finance' } },
  { path: '/customers', name: 'customers', component: () => import('../views/CustomersView.vue'), meta: { perm: 'customer' } },
  { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { perm: '_any' } },
  { path: '/guide', name: 'guide', component: () => import('../views/GuideView.vue') },
  { path: '/:pathMatch(.*)*', name: 'not-found', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Helper: check permission and redirect to dashboard if denied
const checkPermAndNext = (authStore, perm, next) => {
  if (perm && !authStore.hasPermission(perm)) {
    return next({ name: 'dashboard' })
  }
  return next()
}

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('erp_token')
  if (to.name !== 'login' && !token) {
    return next({ name: 'login' })
  } else if (to.name === 'login' && token) {
    return next({ name: 'dashboard' })
  } else if (to.meta.perm) {
    const authStore = useAuthStore()
    if (!authStore.user) {
      // Try to load user first
      try {
        await authStore.checkAuth()
      } catch (e) {}

      // After checking, if still no user, redirect to login
      if (!authStore.user) {
        return next({ name: 'login' })
      }
    }
    // Check permissions (applies whether user was just loaded or already present)
    return checkPermAndNext(authStore, to.meta.perm, next)
  } else {
    return next()
  }
})

export default router
