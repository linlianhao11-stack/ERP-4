<!--
  部门管理组件
  功能：部门列表显示、新增/编辑/删除部门
  从 SettingsView.vue 常规设置标签页使用
-->
<template>
  <div class="contents">
    <!-- 部门管理卡片 -->
    <div class="card p-4">
      <h3 class="font-semibold mb-3 text-sm">部门管理</h3>
      <!-- 部门列表 -->
      <div class="space-y-2 mb-3 max-h-48 overflow-y-auto">
        <div v-for="d in departments" :key="d.id" class="flex justify-between items-center p-2 bg-elevated rounded text-sm">
          <span>
            <span class="font-mono text-xs text-muted mr-1">{{ d.code }}</span>
            {{ d.name }}
          </span>
          <div>
            <button @click="editDepartment(d)" class="text-primary text-xs mr-2">编辑</button>
            <button @click="handleDeleteDepartment(d.id)" class="text-error text-xs">删除</button>
          </div>
        </div>
        <div v-if="!departments.length" class="text-muted text-center py-2 text-sm">暂无部门</div>
      </div>
      <!-- 新增部门表单 -->
      <form @submit.prevent="handleCreateDepartment" class="flex gap-2">
        <input v-model="newDeptCode" class="input flex-1 text-sm" placeholder="编码">
        <input v-model="newDeptName" class="input flex-1 text-sm" placeholder="名称">
        <button type="submit" class="btn btn-primary btn-sm">添加</button>
      </form>
    </div>

    <!-- 部门编辑弹窗 -->
    <div v-if="showDeptModal" class="modal-overlay active" @click.self="showDeptModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">{{ deptForm.id ? '编辑部门 - ' + deptForm.name : '新建部门' }}</h3>
          <button @click="showDeptModal = false" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveDepartment" class="space-y-3 p-4">
          <div><label class="label" for="dept-code">编码 *</label><input id="dept-code" v-model="deptForm.code" class="input" required placeholder="部门编码"></div>
          <div><label class="label" for="dept-name">名称 *</label><input id="dept-name" v-model="deptForm.name" class="input" required placeholder="部门名称"></div>
          <div class="flex gap-3 pt-3">
            <button type="button" @click="showDeptModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1">保存</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 部门管理
 * 包含：部门列表、新增、编辑、删除
 */
import { ref, reactive, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { getDepartments, createDepartment, updateDepartment, deleteDepartment as deleteDepartmentApi } from '../../../api/employees'

const emit = defineEmits(['data-changed'])

const appStore = useAppStore()
const departments = ref([])

// 部门相关状态
const newDeptCode = ref('')
const newDeptName = ref('')
const showDeptModal = ref(false)
const deptForm = reactive({ id: null, code: '', name: '' })

// 加载部门列表
const loadDepartments = async () => {
  try {
    const { data } = await getDepartments()
    departments.value = data
  } catch (e) {
    console.error('加载部门列表失败:', e)
  }
}

// === 部门操作 ===
const editDepartment = (d) => {
  Object.assign(deptForm, { id: d.id, code: d.code, name: d.name })
  showDeptModal.value = true
}

const saveDepartment = async () => {
  if (!deptForm.code || !deptForm.code.trim() || !deptForm.name || !deptForm.name.trim()) {
    appStore.showToast('请输入部门编码和名称', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await updateDepartment(deptForm.id, { code: deptForm.code.trim(), name: deptForm.name.trim() })
    appStore.showToast('保存成功')
    showDeptModal.value = false
    loadDepartments()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleCreateDepartment = async () => {
  if (!newDeptCode.value || !newDeptCode.value.trim() || !newDeptName.value || !newDeptName.value.trim()) return
  try {
    await createDepartment({ code: newDeptCode.value.trim(), name: newDeptName.value.trim() })
    appStore.showToast('创建成功')
    newDeptCode.value = ''
    newDeptName.value = ''
    loadDepartments()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  }
}

const handleDeleteDepartment = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该部门？删除前请确保该部门下无员工。')) return
  try {
    await deleteDepartmentApi(id)
    appStore.showToast('已删除')
    loadDepartments()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// 组件挂载时加载部门数据
onMounted(() => {
  loadDepartments()
})
</script>
