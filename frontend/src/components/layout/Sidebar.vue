<template>
  <aside class="sidebar" :class="{ collapsed: collapsed }">
    <div class="sidebar-header">
      <template v-if="!collapsed">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-foreground rounded-[10px] flex items-center justify-center text-canvas">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 13L2 9z"/></svg>
          </div>
          <div>
            <div class="text-[14px] font-semibold text-foreground tracking-tight">ERP System</div>
            <div class="text-[11px] text-muted">{{ authStore.user?.display_name }}</div>
          </div>
        </div>
      </template>
      <button @click="$emit('toggle')" class="sidebar-toggle">
        <component :is="collapsed ? PanelLeftOpen : PanelLeftClose" :size="18" :stroke-width="1.5" />
      </button>
    </div>
    <nav class="sidebar-nav">
      <template v-for="(group, gIdx) in groupedItems" :key="group.label">
        <div v-if="!collapsed && group.items.length" class="sidebar-group">{{ group.label }}</div>
        <router-link
          v-for="item in group.items"
          :key="item.key"
          :to="'/' + item.key"
          class="sidebar-item"
          :class="{ active: $route.name === item.key }"
        >
          <span class="sidebar-icon">
            <component :is="iconMap[item.key]" :size="20" :stroke-width="1.5" />
          </span>
          <span v-if="!collapsed" class="sidebar-label">{{ item.name }}</span>
          <span v-if="!collapsed && getBadgeCount(item.key)" class="sidebar-badge">{{ getBadgeCount(item.key) > 99 ? '99+' : getBadgeCount(item.key) }}</span>
        </router-link>
      </template>
    </nav>
    <div class="sidebar-footer" v-if="!collapsed">
      <button @click="appStore.toggleTheme()" class="sidebar-footer-btn">
        <component :is="appStore.theme === 'dark' ? Sun : Moon" :size="16" :stroke-width="1.5" />
        <span>{{ appStore.theme === 'dark' ? '浅色模式' : '深色模式' }}</span>
      </button>
      <router-link to="/guide" class="sidebar-footer-btn">
        <BookOpen :size="16" :stroke-width="1.5" /><span>使用说明</span>
      </router-link>
      <button @click="handleLogout" class="sidebar-footer-btn">
        <LogOut :size="16" :stroke-width="1.5" /><span>退出登录</span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useAppStore } from '../../stores/app'
import { menuItems, iconMap } from '../../utils/constants'
import { BookOpen, LogOut, PanelLeftClose, PanelLeftOpen, Sun, Moon } from 'lucide-vue-next'

const props = defineProps({ collapsed: Boolean })
defineEmits(['toggle'])

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const visibleItems = computed(() =>
  menuItems.filter(item => authStore.hasPermission(item.perm))
)

const groupedItems = computed(() => {
  const groups = []
  const groupMap = {}
  visibleItems.value.forEach(item => {
    const g = item.group || '其他'
    if (!groupMap[g]) {
      groupMap[g] = { label: g, items: [] }
      groups.push(groupMap[g])
    }
    groupMap[g].items.push(item)
  })
  return groups
})

const badgeMap = {
  logistics: ['pending_shipment'],
  purchase: ['pending_review', 'in_transit'],
  finance: ['pending_collection'],
  stock: ['low_stock'],
  accounting: ['pending_receivable']
}

const getBadgeCount = (key) => {
  const fields = badgeMap[key]
  if (!fields) return 0
  return fields.reduce((sum, f) => sum + (appStore.todoCounts[f] || 0), 0)
}

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>
