<template>
  <nav class="bottom-nav">
    <router-link
      v-for="item in visibleItems"
      :key="item.key"
      :to="'/' + item.key"
      class="bottom-nav-item"
      :class="{ active: $route.name === item.key }"
    >
      <span class="bottom-nav-icon">
        <component :is="iconMap[item.key]" :size="20" :stroke-width="1.5" />
      </span>
      <span class="bottom-nav-label">{{ item.name }}</span>
    </router-link>
    <button class="bottom-nav-item" @click="$emit('more')">
      <span class="bottom-nav-icon">
        <MoreHorizontal :size="20" :stroke-width="1.5" />
      </span>
      <span class="bottom-nav-label">更多</span>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { bottomNavItems, iconMap } from '../../utils/constants'
import { MoreHorizontal } from 'lucide-vue-next'

defineEmits(['more'])

const route = useRoute()
const authStore = useAuthStore()

const visibleItems = computed(() =>
  bottomNavItems.filter(item => authStore.hasPermission(item.perm)).slice(0, 4)
)
</script>
