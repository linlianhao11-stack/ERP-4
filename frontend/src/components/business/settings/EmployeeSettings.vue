<!--
  员工管理组件
  功能：员工列表显示、新增/编辑/删除员工
  支持部门归属、业务员标记
  从 SettingsView.vue 常规设置标签页使用
-->
<template>
  <div class="contents">
    <!-- 员工管理卡片 -->
    <div class="card p-4">
      <h3 class="font-semibold mb-3 text-sm">员工管理</h3>
      <!-- 员工列表 -->
      <div class="space-y-2 mb-3 max-h-64 overflow-y-auto">
        <div v-for="e in employees" :key="e.id" class="flex justify-between items-center p-2 bg-elevated rounded text-sm">
          <div class="flex-1 min-w-0">
            <span class="font-mono text-xs text-muted mr-1">{{ e.code }}</span>
            <span>{{ e.name }}</span>
            <span v-if="e.phone" class="text-xs text-muted ml-1">{{ e.phone }}</span>
            <span v-if="e.department_name" class="text-xs text-secondary ml-1">/ {{ e.department_name }}</span>
            <span v-if="e.is_salesperson" class="text-xs bg-info-subtle text-primary px-1.5 py-0.5 rounded ml-1">业务员</span>
          </div>
          <div class="flex-shrink-0 ml-2">
            <button @click="editEmployee(e)" class="text-primary text-xs mr-2">编辑</button>
            <button @click="handleDeleteEmployee(e.id)" class="text-error text-xs">删除</button>
          </div>
        </div>
        <div v-if="!employees.length" class="text-muted text-center py-2 text-sm">暂无员工</div>
      </div>
      <!-- 新增员工表单 -->
      <form @submit.prevent="handleCreateEmployee" class="space-y-2">
        <div class="flex gap-2">
          <input v-model="newEmpCode" class="input flex-1 text-sm" placeholder="编码">
          <input v-model="newEmpName" class="input flex-1 text-sm" placeholder="姓名">
          <input v-model="newEmpPhone" class="input flex-1 text-sm" placeholder="电话(可选)">
        </div>
        <div class="flex gap-2 items-center">
          <select v-model="newEmpDeptId" class="input flex-1 text-sm">
            <option value="">部门(可选)</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
          <label class="flex items-center gap-1 text-sm cursor-pointer whitespace-nowrap" for="new-emp-salesperson">
            <input id="new-emp-salesperson" type="checkbox" v-model="newEmpIsSalesperson" class="w-4 h-4">
            业务员
          </label>
          <button type="submit" class="btn btn-primary btn-sm">添加</button>
        </div>
      </form>
    </div>

    <!-- 员工编辑弹窗 -->
    <div v-if="showEmpModal" class="modal-overlay active" @click.self="showEmpModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">{{ empForm.id ? '编辑员工 - ' + empForm.name : '新建员工' }}</h3>
          <button @click="showEmpModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body"><div class="space-y-3">
          <div><label class="label" for="emp-code">编码 *</label><input id="emp-code" v-model="empForm.code" class="input" required placeholder="员工编码"></div>
          <div><label class="label" for="emp-name">姓名 *</label><input id="emp-name" v-model="empForm.name" class="input" required placeholder="员工姓名"></div>
          <div><label class="label" for="emp-phone">电话</label><input id="emp-phone" v-model="empForm.phone" class="input" placeholder="可选"></div>
          <div>
            <label class="label" for="emp-dept">部门</label>
            <select id="emp-dept" v-model="empForm.department_id" class="input">
              <option :value="null">无部门</option>
              <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
          </div>
          <div>
            <label class="flex items-center gap-2 cursor-pointer" for="emp-salesperson">
              <input id="emp-salesperson" type="checkbox" v-model="empForm.is_salesperson" class="w-4 h-4">
              <span class="text-sm">标记为业务员</span>
            </label>
          </div>
        </div></div>
        <div class="modal-footer">
          <button type="button" @click="showEmpModal = false" class="btn btn-sm btn-secondary">取消</button>
          <button type="button" @click="saveEmployee()" class="btn btn-sm btn-primary">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 员工管理
 * 包含：员工列表、新增、编辑、删除
 * 支持部门归属和业务员标记
 */
import { ref, reactive, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { getDepartments, getEmployees, createEmployee, updateEmployee, deleteEmployee as deleteEmployeeApi } from '../../../api/employees'

const emit = defineEmits(['data-changed'])

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const employees = ref([])
const departments = ref([])

// 新增员工相关状态
const newEmpCode = ref('')
const newEmpName = ref('')
const newEmpPhone = ref('')
const newEmpDeptId = ref('')
const newEmpIsSalesperson = ref(false)
const showEmpModal = ref(false)
const empForm = reactive({ id: null, code: '', name: '', phone: '', department_id: null, is_salesperson: false })

// 加载数据
const loadDepartments = async () => {
  try {
    const { data } = await getDepartments()
    departments.value = data.items || data
  } catch (e) {
    console.error('加载部门列表失败:', e)
  }
}

const loadEmployees = async () => {
  try {
    const { data } = await getEmployees()
    employees.value = data.items || data
  } catch (e) {
    console.error('加载员工列表失败:', e)
  }
}

// === 员工操作 ===
const editEmployee = (e) => {
  Object.assign(empForm, {
    id: e.id,
    code: e.code,
    name: e.name,
    phone: e.phone || '',
    department_id: e.department_id || null,
    is_salesperson: e.is_salesperson || false
  })
  showEmpModal.value = true
}

const saveEmployee = async () => {
  if (!empForm.code || !empForm.code.trim() || !empForm.name || !empForm.name.trim()) {
    appStore.showToast('请输入员工编码和姓名', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await updateEmployee(empForm.id, {
      code: empForm.code.trim(),
      name: empForm.name.trim(),
      phone: empForm.phone || null,
      department_id: empForm.department_id || null,
      is_salesperson: empForm.is_salesperson
    })
    appStore.showToast('保存成功')
    showEmpModal.value = false
    loadEmployees()
    settingsStore.loadEmployees()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleCreateEmployee = async () => {
  if (!newEmpCode.value || !newEmpCode.value.trim() || !newEmpName.value || !newEmpName.value.trim()) return
  try {
    await createEmployee({
      code: newEmpCode.value.trim(),
      name: newEmpName.value.trim(),
      phone: newEmpPhone.value.trim() || null,
      department_id: newEmpDeptId.value || null,
      is_salesperson: newEmpIsSalesperson.value
    })
    appStore.showToast('创建成功')
    newEmpCode.value = ''
    newEmpName.value = ''
    newEmpPhone.value = ''
    newEmpDeptId.value = ''
    newEmpIsSalesperson.value = false
    loadEmployees()
    settingsStore.loadEmployees()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  }
}

const handleDeleteEmployee = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该员工？')) return
  try {
    await deleteEmployeeApi(id)
    appStore.showToast('已删除')
    loadEmployees()
    settingsStore.loadEmployees()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// 组件挂载时加载数据
onMounted(() => {
  loadDepartments()
  loadEmployees()
})
</script>
