<!--
  银行账户管理组件
  功能：按账套 Tab 切换，银行账户的增删改
-->
<template>
  <div class="grid md:grid-cols-2 gap-5 mt-5">
    <div class="card p-4">
      <h3 class="font-semibold mb-3 text-sm">银行账户管理</h3>
      <div class="text-xs text-muted mb-3">管理企业银行账户，用于凭证分录的银行辅助核算</div>
      <div class="space-y-2 mb-3">
        <div v-for="b in bankAccounts" :key="b.id" class="flex justify-between items-center p-2 bg-elevated rounded text-sm">
          <!-- 编辑模式 -->
          <div v-if="editingId === b.id" class="flex items-center gap-2 flex-1">
            <input v-model="editForm.bank_name" class="input text-sm flex-1" placeholder="银行名称" @keyup.escape="cancelEdit">
            <input v-model="editForm.account_number" class="input text-sm flex-1" placeholder="账号" @keyup.escape="cancelEdit">
            <input v-model="editForm.short_name" class="input text-sm w-20" placeholder="简称" @keyup.escape="cancelEdit">
            <button @click="saveEdit" class="text-success-emphasis text-xs font-medium">保存</button>
            <button @click="cancelEdit" class="text-muted text-xs">取消</button>
          </div>
          <!-- 展示模式 -->
          <template v-else>
            <div>
              <span class="font-medium">{{ b.short_name || b.bank_name }}</span>
              <span class="text-xs text-muted ml-1">{{ b.account_number }}</span>
            </div>
            <div>
              <button @click="startEdit(b)" class="text-primary text-xs mr-2">编辑</button>
              <button @click="handleDelete(b.id)" class="text-error text-xs">删除</button>
            </div>
          </template>
        </div>
        <div v-if="!bankAccounts.length" class="text-muted text-center py-2 text-sm">暂无银行账户</div>
      </div>
      <!-- 新增银行账户 -->
      <form @submit.prevent="handleCreate" class="flex gap-2">
        <input v-model="newForm.bank_name" class="input flex-1 text-sm" placeholder="银行名称">
        <input v-model="newForm.account_number" class="input flex-1 text-sm" placeholder="账号">
        <input v-model="newForm.short_name" class="input w-20 text-sm" placeholder="简称">
        <button type="submit" class="btn btn-primary btn-sm">添加</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useAccountingStore } from '../../../stores/accounting'
import { getBankAccounts, createBankAccount, updateBankAccount, deleteBankAccount } from '../../../api/accounting'

const emit = defineEmits(['data-changed'])

const appStore = useAppStore()
const accountingStore = useAccountingStore()

const bankAccounts = ref([])
const editingId = ref(null)
const editForm = ref({ bank_name: '', account_number: '', short_name: '' })
const newForm = ref({ bank_name: '', account_number: '', short_name: '' })

const loadBankAccounts = async () => {
  const setId = accountingStore.currentAccountSetId
  if (!setId) return
  try {
    const { data } = await getBankAccounts({ account_set_id: setId })
    bankAccounts.value = data
  } catch (e) {
    bankAccounts.value = []
  }
}

const startEdit = (b) => {
  editingId.value = b.id
  editForm.value = { bank_name: b.bank_name, account_number: b.account_number, short_name: b.short_name || '' }
}

const cancelEdit = () => {
  editingId.value = null
  editForm.value = { bank_name: '', account_number: '', short_name: '' }
}

const saveEdit = async () => {
  if (!editForm.value.bank_name.trim() || !editForm.value.account_number.trim()) {
    appStore.showToast('银行名称和账号不能为空', 'error')
    return
  }
  try {
    await updateBankAccount(editingId.value, editForm.value)
    appStore.showToast('修改成功')
    cancelEdit()
    await loadBankAccounts()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '修改失败', 'error')
  }
}

const handleCreate = async () => {
  if (!newForm.value.bank_name.trim() || !newForm.value.account_number.trim()) {
    appStore.showToast('请填写银行名称和账号', 'error')
    return
  }
  try {
    await createBankAccount({
      ...newForm.value,
      account_set_id: accountingStore.currentAccountSetId,
    })
    appStore.showToast('添加成功')
    newForm.value = { bank_name: '', account_number: '', short_name: '' }
    await loadBankAccounts()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '添加失败', 'error')
  }
}

const handleDelete = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该银行账户？')) return
  try {
    await deleteBankAccount(id)
    appStore.showToast('已删除')
    await loadBankAccounts()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => {
  cancelEdit()
  loadBankAccounts()
})

onMounted(() => { loadBankAccounts() })
</script>
