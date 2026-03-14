<!--
  系统设置页面 — 薄容器组件
  职责：标签页导航、权限判断、组装子组件
  实际业务逻辑已拆分到 components/business/settings/ 下的 6 个子组件
-->
<template>
  <div>
    <h2 class="text-lg font-bold mb-4">系统设置</h2>

    <!-- 标签页导航 -->
    <div class="flex flex-wrap gap-2 mb-3 border-b pb-2">
      <button @click="settingsTab = 'general'" :class="['tab', settingsTab === 'general' ? 'active' : '']">常规设置</button>
      <button v-if="hasPermission('finance')" @click="settingsTab = 'finance'" :class="['tab', settingsTab === 'finance' ? 'active' : '']">财务设置</button>
      <button v-if="hasPermission('admin')" @click="settingsTab = 'logs'" :class="['tab', settingsTab === 'logs' ? 'active' : '']">系统日志</button>
      <button v-if="hasPermission('admin')" @click="settingsTab = 'permissions'" :class="['tab', settingsTab === 'permissions' ? 'active' : '']">权限管理</button>
      <button v-if="hasPermission('admin')" @click="settingsTab = 'ai'" :class="['tab', settingsTab === 'ai' ? 'active' : '']">AI 助手配置</button>
    </div>

    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <!-- 常规设置标签页 -->
      <div v-if="settingsTab === 'general'" key="general" class="grid md:grid-cols-2 gap-5">
        <WarehouseSettings
          v-if="hasPermission('settings') || hasPermission('stock_edit')"
          @data-changed="onDataChanged" />
        <DepartmentSettings
          v-if="hasPermission('settings') || hasPermission('sales')"
          @data-changed="onDataChanged" />
        <EmployeeSettings
          v-if="hasPermission('settings') || hasPermission('sales')"
          @data-changed="onDataChanged" />
        <UserSettings
          @data-changed="onDataChanged"
          @go-to-permissions="handleGoToPermissions" />
      </div>

      <!-- 财务设置标签页 -->
      <div v-else-if="settingsTab === 'finance'" key="finance">
        <PaymentMethodSettings @data-changed="onDataChanged" />
      </div>

      <!-- 系统日志标签页 -->
      <div v-else-if="settingsTab === 'logs'" key="logs">
        <LogsSettings />
      </div>

      <!-- 权限管理标签页 -->
      <div v-else-if="settingsTab === 'permissions'" key="permissions">
        <PermissionSettings
          ref="permissionSettingsRef"
          :initial-user-id="permInitialUserId"
          @data-changed="onDataChanged" />
      </div>

      <!-- AI 助手配置标签页 -->
      <div v-else-if="settingsTab === 'ai'" key="ai">
        <ApiKeysPanel />
      </div>
    </Transition>
  </div>
</template>

<script setup>
/**
 * 系统设置页面 — 标签页容器
 * 子组件：WarehouseSettings、DepartmentSettings、EmployeeSettings、UserSettings、
 *         PaymentMethodSettings、LogsSettings、PermissionSettings、ApiKeysPanel
 */
import { ref, nextTick } from 'vue'
import { usePermission } from '../composables/usePermission'
import { useSettingsStore } from '../stores/settings'

// 子组件导入
import WarehouseSettings from '../components/business/settings/WarehouseSettings.vue'
import DepartmentSettings from '../components/business/settings/DepartmentSettings.vue'
import EmployeeSettings from '../components/business/settings/EmployeeSettings.vue'
import UserSettings from '../components/business/settings/UserSettings.vue'
import PaymentMethodSettings from '../components/business/settings/PaymentMethodSettings.vue'
import LogsSettings from '../components/business/settings/LogsSettings.vue'
import PermissionSettings from '../components/business/settings/PermissionSettings.vue'
import ApiKeysPanel from '../components/business/settings/ApiKeysPanel.vue'

const { hasPermission } = usePermission()
const settingsStore = useSettingsStore()

// 当前标签页
const settingsTab = ref('general')

// 权限管理组件引用及初始用户ID（用于从用户管理跳转）
const permissionSettingsRef = ref(null)
const permInitialUserId = ref(null)

// 子组件数据变更回调（预留扩展点）
const onDataChanged = () => {
  // 子组件已自行刷新各自的 store 数据，此处可添加跨组件联动逻辑
}

// 从用户管理弹窗跳转到权限管理标签页
const handleGoToPermissions = async (userId) => {
  permInitialUserId.value = userId
  settingsTab.value = 'permissions'
  await nextTick()
  // 通过 ref 调用子组件方法选中对应用户
  const users = settingsStore.users
  const user = users.find(u => u.id === userId)
  if (user && permissionSettingsRef.value) {
    permissionSettingsRef.value.selectPermUser(user)
  }
}
</script>
