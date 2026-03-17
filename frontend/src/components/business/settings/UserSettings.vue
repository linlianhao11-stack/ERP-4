<!--
  用户管理与系统维护组件
  功能：用户列表/新增/编辑/禁用启用、修改密码、数据库备份/恢复
  从 SettingsView.vue 常规设置标签页提取
-->
<template>
  <div class="contents">
    <!-- 用户管理卡片（仅管理员可见） -->
    <div v-if="hasPermission('admin')" class="card p-4">
      <h3 class="font-semibold mb-3 text-sm">用户管理</h3>
      <div class="space-y-2 mb-3">
        <div v-for="u in users" :key="u.id" class="flex justify-between items-center p-2 bg-elevated rounded text-sm">
          <span>{{ u.display_name }} <span class="text-muted text-xs">@{{ u.username }}</span></span>
          <div>
            <button @click="editUser(u)" class="text-primary text-xs mr-2">编辑</button>
            <button v-if="u.id !== authStore.user?.id" @click="handleToggleUser(u.id)" :class="u.is_active ? 'text-error' : 'text-success'" class="text-xs">{{ u.is_active ? '禁用' : '启用' }}</button>
          </div>
        </div>
      </div>
      <button @click="openUserForm()" class="btn btn-primary btn-sm">新增用户</button>
    </div>

    <!-- 修改密码卡片 -->
    <div class="card p-4">
      <h3 class="font-semibold mb-3 text-sm">修改密码</h3>
      <form @submit.prevent="handleChangePassword" class="space-y-3">
        <div><label class="label">旧密码</label><input v-model="pwdForm.old_password" type="password" class="input w-full text-sm" placeholder="请输入当前密码"></div>
        <div><label class="label">新密码</label><input v-model="pwdForm.new_password" type="password" class="input w-full text-sm" placeholder="请输入新密码"></div>
        <div><label class="label">确认新密码</label><input v-model="pwdForm.confirm_password" type="password" class="input w-full text-sm" placeholder="再次输入新密码"></div>
        <button type="submit" class="btn btn-primary btn-sm">修改密码</button>
      </form>
    </div>

    <!-- 数据库备份卡片（仅管理员可见） -->
    <div v-if="hasPermission('admin')" class="card p-4">
      <h3 class="font-semibold mb-3 text-sm">数据库备份</h3>
      <div class="flex gap-2 mb-3">
        <button @click="handleCreateBackup" class="btn btn-primary btn-sm" :disabled="backupLoading">{{ backupLoading ? '备份中...' : '立即备份' }}</button>
        <button @click="loadBackups" class="btn btn-secondary btn-sm">刷新列表</button>
        <button @click="showRestoreModal = true" class="btn btn-sm btn-success" :disabled="restoreLoading">备份恢复</button>
      </div>
      <!-- 备份列表 -->
      <div class="space-y-1.5 max-h-48 overflow-y-auto">
        <div v-for="b in backups" :key="b.filename" class="flex justify-between items-center p-2 bg-elevated rounded text-xs">
          <div>
            <div class="font-medium">{{ b.filename }}</div>
            <div class="text-muted">{{ b.size_mb }} MB · {{ fmtDate(b.created_at) }}</div>
          </div>
          <div class="flex gap-2">
            <button @click="handleDownloadBackup(b.filename)" class="text-primary">下载</button>
            <button @click="handleDeleteBackup(b.filename)" class="text-error">删除</button>
          </div>
        </div>
        <div v-if="!backups.length" class="text-muted text-center py-2">暂无备份</div>
      </div>
      <div class="text-xs text-muted mt-2">自动备份：每天凌晨3点 · 保留30天</div>
    </div>

    <!-- 用户编辑弹窗 -->
    <div v-if="showUserModal" class="modal-overlay active" @click.self="showUserModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">{{ userForm.id ? '编辑用户' : '新增用户' }}</h3>
          <button @click="showUserModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body"><div class="space-y-3">
          <div><label class="label">用户名 *</label><input v-model="userForm.username" class="input" required :disabled="!!userForm.id"></div>
          <div><label class="label">显示名称</label><input v-model="userForm.display_name" class="input"></div>
          <div><label class="label">密码 {{ userForm.id ? '(留空不修改)' : '*' }}</label><input v-model="userForm.password" type="password" class="input" :required="!userForm.id"></div>
          <div>
            <label class="label">角色</label>
            <select v-model="userForm.role" class="input">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <div v-if="userForm.role === 'user'">
            <label class="label">权限</label>
            <div class="bg-elevated rounded-lg p-3 text-sm text-secondary">
              <span v-if="userForm.permissions?.length">已配置 {{ userForm.permissions.length }} 项权限</span>
              <span v-else>暂未配置权限</span>
              <span class="mx-1">·</span>
              <button type="button" @click="goToPermissions"
                class="text-primary hover:underline">前往权限管理</button>
            </div>
          </div>
        </div></div>
        <div class="modal-footer">
          <button type="button" @click="showUserModal = false" class="btn btn-sm btn-secondary">取消</button>
          <button type="button" @click="saveUser()" class="btn btn-sm btn-primary">保存</button>
        </div>
      </div>
    </div>

    <!-- 备份恢复弹窗 -->
    <div v-if="showRestoreModal" class="modal-overlay active" @click.self="showRestoreModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">备份恢复</h3>
          <button @click="showRestoreModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body"><div class="space-y-4">
          <div class="text-sm text-secondary">上传 <span class="font-medium">.sql</span> 或 <span class="font-medium">.db</span> 备份文件来恢复数据库。恢复前会自动备份当前数据。</div>
          <div class="border-2 border-dashed border-line-strong rounded-lg p-6 text-center cursor-pointer hover:border-primary transition-colors" @click="$refs.restoreFileInput.click()" @dragover.prevent @drop.prevent="handleRestoreFileDrop">
            <div v-if="!restoreFile" class="text-muted text-sm">点击选择文件 或 拖拽文件到此处</div>
            <div v-else class="text-sm">
              <div class="font-medium text-secondary">{{ restoreFile.name }}</div>
              <div class="text-muted mt-1">{{ (restoreFile.size / 1024 / 1024).toFixed(2) }} MB</div>
            </div>
          </div>
          <input ref="restoreFileInput" type="file" accept=".sql,.db" class="hidden" @change="handleRestoreFileSelect">
          <div class="bg-warning-subtle border border-warning rounded p-3 text-xs text-warning">注意：恢复操作将覆盖当前数据库，请确认备份文件正确。恢复后页面将自动刷新。</div>
        </div></div>
        <div class="modal-footer">
          <button @click="showRestoreModal = false" class="btn btn-sm btn-secondary">取消</button>
          <button @click="handleUploadRestore" class="btn btn-sm btn-primary" :disabled="!restoreFile || restoreLoading" style="background:var(--success);color:#fff">{{ restoreLoading ? '恢复中...' : '确认恢复' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 用户管理 + 密码修改 + 数据库备份/恢复
 * 包含：用户CRUD、禁用/启用、密码修改、备份创建/下载/删除/恢复
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '../../../stores/auth'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import { changePassword } from '../../../api/auth'
import {
  createUser, updateUser, toggleUser as toggleUserApi,
  createBackup as createBackupApi, downloadBackup as downloadBackupApi,
  deleteBackup as deleteBackupApi, uploadRestoreBackup
} from '../../../api/settings'
import { downloadBlob } from '../../../composables/useDownload'

const emit = defineEmits(['data-changed', 'go-to-permissions'])

const authStore = useAuthStore()
const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { fmtDate } = useFormat()
const { hasPermission } = usePermission()
const users = computed(() => settingsStore.users)
const backups = computed(() => settingsStore.backups)

// 密码表单
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

// 用户相关状态
const showUserModal = ref(false)
const userForm = reactive({ id: null, username: '', display_name: '', role: 'user', permissions: [], password: '' })

// 备份相关状态
const backupLoading = ref(false)
const restoreLoading = ref(false)
const showRestoreModal = ref(false)
const restoreFile = ref(null)

// === 密码修改 ===
const handleChangePassword = async () => {
  if (!pwdForm.old_password || !pwdForm.new_password) {
    appStore.showToast('请填写完整', 'error')
    return
  }
  if (pwdForm.new_password.length < 6) {
    appStore.showToast('新密码长度不能少于6位', 'error')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    appStore.showToast('两次输入的新密码不一致', 'error')
    return
  }
  try {
    await changePassword({ old_password: pwdForm.old_password, new_password: pwdForm.new_password })
    appStore.showToast('密码修改成功')
    Object.assign(pwdForm, { old_password: '', new_password: '', confirm_password: '' })
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '密码修改失败', 'error')
  }
}

// === 用户管理 ===
const openUserForm = () => {
  Object.assign(userForm, { id: null, username: '', display_name: '', role: 'user', permissions: [], password: '' })
  showUserModal.value = true
}

const editUser = (u) => {
  Object.assign(userForm, {
    id: u.id, username: u.username, display_name: u.display_name,
    role: u.role, permissions: u.permissions || [], password: ''
  })
  showUserModal.value = true
}

const saveUser = async () => {
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    if (userForm.id) {
      await updateUser(userForm.id, userForm)
    } else {
      await createUser(userForm)
    }
    appStore.showToast('保存成功')
    showUserModal.value = false
    settingsStore.loadUsers()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleToggleUser = async (id) => {
  try {
    await toggleUserApi(id)
    settingsStore.loadUsers()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

// 跳转到权限管理（通知父组件切换标签页）
const goToPermissions = () => {
  showUserModal.value = false
  emit('go-to-permissions', userForm.id)
}

// === 备份管理 ===
const loadBackups = () => settingsStore.loadBackups()

const handleCreateBackup = async () => {
  backupLoading.value = true
  try {
    await createBackupApi()
    appStore.showToast('备份成功')
    loadBackups()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '备份失败', 'error')
  } finally {
    backupLoading.value = false
  }
}

const handleDownloadBackup = async (filename) => {
  try {
    const { data } = await downloadBackupApi(filename)
    downloadBlob(data, filename)
  } catch (e) {
    appStore.showToast('下载失败', 'error')
  }
}

const handleRestoreFileSelect = (e) => {
  restoreFile.value = e.target.files[0] || null
}

const handleRestoreFileDrop = (e) => {
  const file = e.dataTransfer.files[0]
  if (file) restoreFile.value = file
}

const handleUploadRestore = async () => {
  if (!restoreFile.value) return
  if (!await appStore.customConfirm('恢复确认', `确定使用 "${restoreFile.value.name}" 恢复数据库？此操作将覆盖当前数据，恢复前会自动备份。`)) return
  restoreLoading.value = true
  try {
    await uploadRestoreBackup(restoreFile.value)
    appStore.showToast('恢复成功，页面即将刷新')
    showRestoreModal.value = false
    setTimeout(() => location.reload(), 1000)
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '恢复失败', 'error')
  } finally {
    restoreLoading.value = false
  }
}

const handleDeleteBackup = async (filename) => {
  if (!await appStore.customConfirm('删除确认', '确定删除此备份？')) return
  try {
    await deleteBackupApi(filename)
    appStore.showToast('已删除')
    loadBackups()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// 组件挂载时加载数据
onMounted(() => {
  if (hasPermission('admin')) {
    settingsStore.loadUsers()
    settingsStore.loadBackups()
  }
})
</script>
