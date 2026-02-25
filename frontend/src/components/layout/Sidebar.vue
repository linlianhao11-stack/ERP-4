<template>
  <aside class="sidebar" :class="{ collapsed: collapsed }">
    <div class="sidebar-header">
      <template v-if="!collapsed">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-[#1d1d1f] rounded-[10px] flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 13L2 9z"/></svg>
          </div>
          <div>
            <div class="text-[14px] font-semibold text-[#1d1d1f] tracking-tight">ERP System</div>
            <div class="text-[11px] text-[#86868b]">{{ authStore.user?.display_name }}</div>
          </div>
        </div>
      </template>
      <button @click="$emit('toggle')" class="sidebar-toggle">
        <component :is="collapsed ? PanelLeftOpen : PanelLeftClose" :size="18" :stroke-width="1.5" />
      </button>
    </div>
    <nav class="sidebar-nav">
      <router-link
        v-for="item in visibleItems"
        :key="item.key"
        :to="'/' + item.key"
        class="sidebar-item"
        :class="{ active: $route.name === item.key }"
      >
        <span class="sidebar-icon">
          <component :is="iconMap[item.key]" :size="20" :stroke-width="1.5" />
        </span>
        <span v-if="!collapsed" class="sidebar-label">{{ item.name }}</span>
      </router-link>
    </nav>
    <div class="sidebar-footer" v-if="!collapsed">
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
import { menuItems, iconMap } from '../../utils/constants'
import { BookOpen, LogOut, PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'

const props = defineProps({ collapsed: Boolean })
defineEmits(['toggle'])

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const visibleItems = computed(() =>
  menuItems.filter(item => authStore.hasPermission(item.perm))
)

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>
