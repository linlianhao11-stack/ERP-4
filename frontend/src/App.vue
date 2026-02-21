<template>
  <div v-if="!ready" class="flex items-center justify-center min-h-screen">
    <div class="text-[#86868b] text-[15px]">加载中...</div>
  </div>
  <template v-else>
    <div v-if="authStore.user" class="app-layout">
      <!-- Sidebar (desktop) -->
      <Sidebar :collapsed="sidebarCollapsed" @toggle="sidebarCollapsed = !sidebarCollapsed" class="hidden md:flex" />

      <!-- Main content -->
      <div class="app-main" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
        <div class="app-content">
          <router-view />
        </div>
      </div>

      <!-- Bottom nav (mobile) -->
      <BottomNav class="md:hidden" @more="showMoreMenu = !showMoreMenu" />

      <!-- More menu overlay (mobile) -->
      <Transition name="fade">
        <div v-if="showMoreMenu" class="fixed inset-0 bg-black/20 backdrop-blur-sm z-40" @click="showMoreMenu = false">
          <div class="fixed bottom-16 left-0 right-0 bg-white/95 backdrop-blur-xl rounded-t-[20px] p-5 pb-6 z-50 shadow-2xl border-t border-[#e8e8ed]" @click.stop>
            <div class="w-9 h-1 bg-[#d2d2d7] rounded-full mx-auto mb-4"></div>
            <div class="grid grid-cols-4 gap-2">
              <router-link
                v-for="item in moreMenuItems"
                :key="item.key"
                :to="'/' + item.key"
                class="flex flex-col items-center gap-1.5 p-3 rounded-2xl hover:bg-[#f5f5f7] transition-colors duration-200 cursor-pointer"
                @click="showMoreMenu = false"
              >
                <div class="w-10 h-10 rounded-xl bg-[#f5f5f7] flex items-center justify-center text-[#1d1d1f]">
                  <component :is="iconMap[item.key]" :size="20" :stroke-width="1.5" />
                </div>
                <span class="text-[11px] font-medium text-[#1d1d1f]">{{ item.name }}</span>
              </router-link>
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <router-view v-else />
  </template>

  <!-- Toast -->
  <Transition name="toast">
    <div v-if="appStore.toast.show" class="toast" :class="appStore.toast.type">
      {{ appStore.toast.msg }}
    </div>
  </Transition>

  <!-- Confirm Dialog -->
  <Transition name="fade">
    <div v-if="appStore.confirmDialog.show" class="modal-backdrop" @click.self="appStore.confirmDialogNo" style="z-index:9998">
      <div class="modal" style="max-width: 380px">
        <div class="p-7 text-center">
          <div class="w-12 h-12 bg-[#fff3cd] rounded-full mx-auto mb-5 flex items-center justify-center">
            <AlertTriangle :size="22" :stroke-width="1.5" class="text-[#ff9f0a]" />
          </div>
          <div class="text-[16px] font-semibold text-[#1d1d1f] mb-1.5 leading-snug">{{ appStore.confirmDialog.message }}</div>
          <div v-if="appStore.confirmDialog.detail" class="text-[13px] text-[#86868b] mb-1 leading-relaxed">{{ appStore.confirmDialog.detail }}</div>
          <div class="flex gap-3 mt-6">
            <button @click="appStore.confirmDialogNo" class="btn btn-secondary flex-1">取消</button>
            <button @click="appStore.confirmDialogYes" class="btn btn-warning flex-1">确认</button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useAppStore } from './stores/app'
import { useProductsStore } from './stores/products'
import { useWarehousesStore } from './stores/warehouses'
import { useCustomersStore } from './stores/customers'
import { useFinanceStore } from './stores/finance'
import { useSettingsStore } from './stores/settings'
import { useIdleTimeout } from './composables/useIdleTimeout'
import { setApiErrorHandler, setApiUnauthorizedHandler } from './api/index'
import { menuItems, iconMap } from './utils/constants'
import Sidebar from './components/layout/Sidebar.vue'
import BottomNav from './components/layout/BottomNav.vue'
import { AlertTriangle } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const customersStore = useCustomersStore()
const financeStore = useFinanceStore()
const settingsStore = useSettingsStore()

const ready = ref(false)
const sidebarCollapsed = ref(false)
const showMoreMenu = ref(false)

const moreMenuItems = computed(() =>
  menuItems.filter(item => authStore.hasPermission(item.perm))
)

// 注册 API 全局错误处理（500+ 错误自动 toast）
setApiErrorHandler((msg, type) => appStore.showToast(msg, type))
setApiUnauthorizedHandler(() => authStore.logout())

// 仅加载全局必需的轻量数据
const loadEssentials = () => {
  settingsStore.loadSalespersons()
  settingsStore.loadPaymentMethods()
  settingsStore.loadCompanyName()
}

// 按路由按需加载数据
const loadForRoute = (routeName) => {
  if (!authStore.user) return
  if (['sales', 'purchase', 'stock'].includes(routeName)) {
    productsStore.ensureLoaded()
    warehousesStore.ensureLoaded()
  }
  if (['sales', 'customers', 'finance'].includes(routeName)) {
    customersStore.ensureLoaded()
  }
  if (routeName === 'finance') {
    financeStore.ensureLoaded()
  }
  if (['consignment', 'settings'].includes(routeName)) {
    warehousesStore.ensureLoaded()
  }
  if (routeName === 'settings') {
    settingsStore.loadUsers()
    if (authStore.hasPermission('admin')) {
      settingsStore.loadBackups()
      settingsStore.loadOpLogs()
    }
  }
}

// 路由切换时按需加载（含登录后首次加载 essentials）
router.afterEach((to, from) => {
  if (authStore.user && from.name === 'login') {
    loadEssentials()
  }
  loadForRoute(to.name)
})

useIdleTimeout(() => {
  authStore.logout()
  router.push('/login')
  appStore.showToast('由于长时间未操作，已自动退出登录', 'warning')
})

onMounted(async () => {
  const ok = await authStore.checkAuth()
  if (ok) {
    loadEssentials()
    loadForRoute(router.currentRoute.value.name)
  } else if (router.currentRoute.value.name !== 'login') {
    await router.replace('/login')
  }
  ready.value = true
})
</script>
