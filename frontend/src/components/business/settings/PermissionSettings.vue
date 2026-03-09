<!--
  权限管理组件
  功能：左侧用户列表选择、右侧权限矩阵（开关切换）、保存用户权限
  从 SettingsView.vue 权限管理标签页提取
-->
<template>
  <div class="flex gap-5" style="min-height: 60vh">
    <!-- 左侧：用户列表 -->
    <div class="w-56 shrink-0">
      <div class="card p-3">
        <h3 class="font-semibold mb-3 text-sm">选择用户</h3>
        <div class="space-y-1 max-h-[60vh] overflow-y-auto">
          <div v-for="u in users" :key="u.id"
            @click="selectPermUser(u)"
            :class="['flex items-center justify-between p-2.5 rounded-lg cursor-pointer text-sm transition-colors',
              permSelectedUser?.id === u.id ? 'bg-primary text-white' : 'hover:bg-elevated']">
            <div>
              <div class="font-medium">{{ u.display_name || u.username }}</div>
              <div :class="['text-xs', permSelectedUser?.id === u.id ? 'text-white/70' : 'text-muted']">@{{ u.username }}</div>
            </div>
            <span v-if="u.role === 'admin'"
              :class="['text-xs px-1.5 py-0.5 rounded',
                permSelectedUser?.id === u.id ? 'bg-surface/20 text-white' : 'bg-info-subtle text-primary']">管理员</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧：权限配置卡片 -->
    <div class="flex-1 min-w-0">
      <!-- 未选择用户提示 -->
      <div v-if="!permSelectedUser" class="card p-12 text-center text-muted text-sm">
        <div class="text-3xl mb-3 opacity-30">🔐</div>
        请从左侧选择一个用户来管理权限
      </div>

      <!-- 管理员提示（无需配置） -->
      <div v-else-if="permSelectedUser.role === 'admin'" class="card p-12 text-center">
        <div class="text-3xl mb-3 opacity-30">👑</div>
        <div class="text-primary font-semibold mb-1">{{ permSelectedUser.display_name || permSelectedUser.username }}</div>
        <div class="text-muted text-sm">管理员拥有全部权限，无需单独配置</div>
      </div>

      <!-- 权限矩阵 -->
      <div v-else>
        <div class="flex items-center justify-between mb-3">
          <div class="text-sm text-muted">
            正在编辑 <span class="font-semibold text-foreground">{{ permSelectedUser.display_name || permSelectedUser.username }}</span> 的权限
          </div>
          <button @click="savePermissions" class="btn btn-primary btn-sm">保存权限</button>
        </div>
        <!-- 权限分组卡片网格 -->
        <div class="grid md:grid-cols-2 gap-3">
          <div v-for="group in permissionGroups" :key="group.main" class="card p-3">
            <!-- 主权限开关 -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <component :is="iconMap[group.icon]" class="w-4 h-4 text-primary" />
                <span class="font-semibold text-sm">{{ group.label }}</span>
              </div>
              <button type="button" @click="toggleMainPerm(group)"
                :class="['w-10 h-[22px] rounded-full transition-colors relative shrink-0',
                  permUserPerms.includes(group.main) ? 'bg-success' : 'bg-line-strong']">
                <span :class="['absolute top-[3px] left-[3px] w-4 h-4 bg-surface rounded-full shadow-sm transition-transform',
                  permUserPerms.includes(group.main) ? 'translate-x-[18px]' : '']"></span>
              </button>
            </div>
            <!-- 子权限开关（主权限开启后显示） -->
            <div v-if="group.children.length && permUserPerms.includes(group.main)" class="space-y-2 mt-3 pt-3 border-t border-line">
              <div v-for="child in group.children" :key="child.key" class="flex items-center justify-between pl-6">
                <span class="text-sm text-secondary">{{ child.name }}</span>
                <button type="button" @click="toggleChildPerm(child.key)"
                  :class="['w-9 h-5 rounded-full transition-colors relative shrink-0',
                    permUserPerms.includes(child.key) ? 'bg-success' : 'bg-line-strong']">
                  <span :class="['absolute top-[2px] left-[2px] w-4 h-4 bg-surface rounded-full shadow-sm transition-transform',
                    permUserPerms.includes(child.key) ? 'translate-x-4' : '']"></span>
                </button>
              </div>
            </div>
            <!-- 子权限提示（主权限关闭时） -->
            <div v-else-if="group.children.length" class="text-xs text-muted mt-3 pt-3 border-t border-line">
              开启主开关后可配置子权限
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 权限管理
 * 包含：用户选择、权限分组矩阵、主/子权限开关切换、保存权限
 */
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { updateUser } from '../../../api/settings'
import { permissionGroups, iconMap } from '../../../utils/constants'

const props = defineProps({
  /** 初始选中的用户ID（从用户管理跳转过来时使用） */
  initialUserId: { type: Number, default: null }
})

const emit = defineEmits(['data-changed'])

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const users = computed(() => settingsStore.users)

// 权限管理状态
const permSelectedUser = ref(null)
const permUserPerms = ref([])

// === 用户选择 ===
const selectPermUser = (u) => {
  if (!u) return
  permSelectedUser.value = u
  permUserPerms.value = [...(u.permissions || [])]
}

// 暴露方法供父组件调用（从用户管理跳转时选中用户）
defineExpose({ selectPermUser })

// === 权限开关操作 ===
const toggleMainPerm = (group) => {
  const idx = permUserPerms.value.indexOf(group.main)
  if (idx >= 0) {
    // 关闭主权限 → 同时移除主权限和所有子权限
    permUserPerms.value.splice(idx, 1)
    for (const child of group.children) {
      const ci = permUserPerms.value.indexOf(child.key)
      if (ci >= 0) permUserPerms.value.splice(ci, 1)
    }
  } else {
    permUserPerms.value.push(group.main)
  }
}

const toggleChildPerm = (key) => {
  const idx = permUserPerms.value.indexOf(key)
  if (idx >= 0) {
    permUserPerms.value.splice(idx, 1)
  } else {
    permUserPerms.value.push(key)
  }
}

// === 保存权限 ===
const savePermissions = async () => {
  if (!permSelectedUser.value || appStore.submitting) return
  appStore.submitting = true
  try {
    await updateUser(permSelectedUser.value.id, { permissions: permUserPerms.value })
    appStore.showToast('权限已保存')
    await settingsStore.loadUsers()
    // 刷新选中用户的数据
    const updated = users.value.find(u => u.id === permSelectedUser.value.id)
    if (updated) permSelectedUser.value = updated
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// 组件挂载时，如果有初始用户ID则自动选中
onMounted(() => {
  settingsStore.loadUsers()
  if (props.initialUserId) {
    const u = users.value.find(u => u.id === props.initialUserId)
    if (u) selectPermUser(u)
  }
})
</script>
