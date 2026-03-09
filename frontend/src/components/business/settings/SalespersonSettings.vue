<!--
  销售员管理组件
  功能：销售员列表显示、新增/编辑/删除销售员
  从 SettingsView.vue 常规设置标签页提取
-->
<template>
  <div class="contents">
    <!-- 销售员管理卡片 -->
    <div class="card p-4">
      <h3 class="font-semibold mb-3 text-sm">销售员管理</h3>
      <!-- 销售员列表 -->
      <div class="space-y-2 mb-3 max-h-48 overflow-y-auto">
        <div v-for="s in salespersons" :key="s.id" class="flex justify-between items-center p-2 bg-[#f5f5f7] rounded text-sm">
          <span>{{ s.name }} <span v-if="s.phone" class="text-xs text-[#86868b]">{{ s.phone }}</span></span>
          <div>
            <button @click="editSalesperson(s)" class="text-[#0071e3] text-xs mr-2">编辑</button>
            <button @click="handleDeleteSalesperson(s.id)" class="text-[#ff3b30] text-xs">删除</button>
          </div>
        </div>
        <div v-if="!salespersons.length" class="text-[#86868b] text-center py-2 text-sm">暂无销售员</div>
      </div>
      <!-- 新增销售员表单 -->
      <form @submit.prevent="handleCreateSalesperson" class="flex gap-2">
        <input v-model="newSalespersonName" class="input flex-1 text-sm" placeholder="姓名">
        <input v-model="newSalespersonPhone" class="input flex-1 text-sm" placeholder="电话(可选)">
        <button type="submit" class="btn btn-primary btn-sm">添加</button>
      </form>
    </div>

    <!-- 销售员编辑弹窗 -->
    <div v-if="showSalespersonModal" class="modal-overlay active" @click.self="showSalespersonModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">{{ salespersonForm.id ? '编辑销售员 - ' + salespersonForm.name : '新建销售员' }}</h3>
          <button @click="showSalespersonModal = false" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveSalesperson" class="space-y-3 p-4">
          <div><label class="label">姓名 *</label><input v-model="salespersonForm.name" class="input" required placeholder="销售员姓名"></div>
          <div><label class="label">电话</label><input v-model="salespersonForm.phone" class="input" placeholder="可选"></div>
          <div class="flex gap-3 pt-3">
            <button type="button" @click="showSalespersonModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1">保存</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 销售员管理
 * 包含：销售员列表、新增、编辑、删除
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { createSalesperson, updateSalesperson, deleteSalesperson as deleteSalespersonApi } from '../../../api/salespersons'

const emit = defineEmits(['data-changed'])

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const salespersons = computed(() => settingsStore.salespersons)

// 销售员相关状态
const newSalespersonName = ref('')
const newSalespersonPhone = ref('')
const showSalespersonModal = ref(false)
const salespersonForm = reactive({ id: null, name: '', phone: '' })

// === 销售员操作 ===
const editSalesperson = (s) => {
  Object.assign(salespersonForm, { id: s.id, name: s.name, phone: s.phone })
  showSalespersonModal.value = true
}

const saveSalesperson = async () => {
  if (!salespersonForm.name || !salespersonForm.name.trim()) {
    appStore.showToast('请输入销售员姓名', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await updateSalesperson(salespersonForm.id, { name: salespersonForm.name.trim(), phone: salespersonForm.phone || null })
    appStore.showToast('保存成功')
    showSalespersonModal.value = false
    settingsStore.loadSalespersons()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleCreateSalesperson = async () => {
  if (!newSalespersonName.value || !newSalespersonName.value.trim()) return
  try {
    await createSalesperson({ name: newSalespersonName.value.trim(), phone: newSalespersonPhone.value.trim() || null })
    appStore.showToast('创建成功')
    newSalespersonName.value = ''
    newSalespersonPhone.value = ''
    settingsStore.loadSalespersons()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  }
}

const handleDeleteSalesperson = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该销售员？')) return
  try {
    await deleteSalespersonApi(id)
    appStore.showToast('已删除')
    settingsStore.loadSalespersons()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// 组件挂载时加载销售员数据
onMounted(() => {
  settingsStore.loadSalespersons()
})
</script>
