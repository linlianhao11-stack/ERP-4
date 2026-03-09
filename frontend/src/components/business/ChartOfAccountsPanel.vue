<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-[15px] font-semibold text-foreground">会计科目</h3>
      <button v-if="hasPermission('accounting_edit')" @click="openAddForm" class="btn btn-primary btn-sm">新增子科目</button>
    </div>

    <div class="table-container">
      <table class="w-full">
        <thead>
          <tr>
            <th>科目编码</th>
            <th>科目名称</th>
            <th>类别</th>
            <th>方向</th>
            <th>末级</th>
            <th>辅助核算</th>
            <th v-if="hasPermission('accounting_edit')">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in accounts" :key="a.id">
            <td>{{ a.code }}</td>
            <td>{{ a.name }}</td>
            <td><span :class="categoryBadge(a.category)">{{ categoryName(a.category) }}</span></td>
            <td>{{ a.direction === 'debit' ? '借' : '贷' }}</td>
            <td>{{ a.is_leaf ? '是' : '否' }}</td>
            <td>
              <span v-if="a.aux_customer" class="badge badge-blue">客户</span>
              <span v-if="a.aux_supplier" class="badge badge-orange">供应商</span>
            </td>
            <td v-if="hasPermission('accounting_edit')">
              <div class="flex gap-1">
                <button @click="openEditAccount(a)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-info-subtle text-info-emphasis hover:bg-info-subtle transition-colors">编辑</button>
                <button v-if="a.is_leaf" @click="deactivateAccount(a)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-error-subtle text-error-emphasis hover:bg-error-subtle transition-colors">停用</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增/编辑科目弹窗 -->
    <Transition name="fade">
      <div v-if="showAddForm" class="modal-backdrop" @click.self="showAddForm = false">
        <div class="modal" style="max-width: 480px">
          <div class="modal-header">
            <h3>{{ isEditMode ? '编辑科目' : '新增子科目' }}</h3>
            <button @click="showAddForm = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body space-y-3">
            <div>
              <label class="label">上级科目编码</label>
              <input v-model="form.parent_code" class="input text-sm" placeholder="如 1002" :disabled="isEditMode" :class="{ 'bg-elevated opacity-60 cursor-not-allowed': isEditMode }">
            </div>
            <div>
              <label class="label">科目编码</label>
              <input v-model="form.code" class="input text-sm" placeholder="如 100201" :disabled="isEditMode" :class="{ 'bg-elevated opacity-60 cursor-not-allowed': isEditMode }">
            </div>
            <div>
              <label class="label">科目名称</label>
              <input v-model="form.name" class="input text-sm" placeholder="如 工商银行">
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="label">类别</label>
                <select v-model="form.category" class="input text-sm" :disabled="isEditMode" :class="{ 'bg-elevated opacity-60 cursor-not-allowed': isEditMode }">
                  <option value="asset">资产</option>
                  <option value="liability">负债</option>
                  <option value="equity">权益</option>
                  <option value="cost">成本</option>
                  <option value="profit_loss">损益</option>
                </select>
              </div>
              <div>
                <label class="label">余额方向</label>
                <select v-model="form.direction" class="input text-sm" :disabled="isEditMode" :class="{ 'bg-elevated opacity-60 cursor-not-allowed': isEditMode }">
                  <option value="debit">借</option>
                  <option value="credit">贷</option>
                </select>
              </div>
            </div>
            <div class="flex gap-4">
              <label class="flex items-center gap-1.5 text-[13px]">
                <input type="checkbox" v-model="form.aux_customer"> 辅助核算-客户
              </label>
              <label class="flex items-center gap-1.5 text-[13px]">
                <input type="checkbox" v-model="form.aux_supplier"> 辅助核算-供应商
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showAddForm = false" class="btn btn-secondary">取消</button>
            <button @click="isEditMode ? handleEdit() : handleAdd()" class="btn btn-primary" :disabled="submitting">确定</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import { createChartOfAccount, updateChartOfAccount, deleteChartOfAccount } from '../../api/accounting'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()

const accounts = ref([])
const showAddForm = ref(false)
const submitting = ref(false)
const isEditMode = ref(false)
const editingAccountId = ref(null)
const form = ref({
  parent_code: '', code: '', name: '',
  category: 'asset', direction: 'debit',
  aux_customer: false, aux_supplier: false,
})

const categoryNames = { asset: '资产', liability: '负债', equity: '权益', cost: '成本', profit_loss: '损益' }
const categoryBadges = { asset: 'badge badge-blue', liability: 'badge badge-red', equity: 'badge badge-green', cost: 'badge badge-orange', profit_loss: 'badge badge-purple' }
const categoryName = (c) => categoryNames[c] || c
const categoryBadge = (c) => categoryBadges[c] || 'badge'

const loadAccounts = async () => {
  await accountingStore.loadChartOfAccounts()
  accounts.value = accountingStore.chartOfAccounts
}

const openAddForm = () => {
  isEditMode.value = false
  editingAccountId.value = null
  form.value = { parent_code: '', code: '', name: '', category: 'asset', direction: 'debit', aux_customer: false, aux_supplier: false }
  showAddForm.value = true
}

const openEditAccount = (a) => {
  isEditMode.value = true
  editingAccountId.value = a.id
  form.value = {
    parent_code: a.parent_code || '',
    code: a.code,
    name: a.name,
    category: a.category,
    direction: a.direction,
    aux_customer: a.aux_customer || false,
    aux_supplier: a.aux_supplier || false,
  }
  showAddForm.value = true
}

const handleEdit = async () => {
  if (!form.value.name) {
    appStore.showToast('请填写科目名称', 'error')
    return
  }
  submitting.value = true
  try {
    await updateChartOfAccount(editingAccountId.value, {
      name: form.value.name,
      aux_customer: form.value.aux_customer,
      aux_supplier: form.value.aux_supplier,
    })
    appStore.showToast('更新成功', 'success')
    showAddForm.value = false
    await loadAccounts()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '更新失败', 'error')
  } finally {
    submitting.value = false
  }
}

const handleAdd = async () => {
  if (!form.value.code || !form.value.name) {
    appStore.showToast('请填写科目编码和名称', 'error')
    return
  }
  submitting.value = true
  try {
    await createChartOfAccount(accountingStore.currentAccountSetId, form.value)
    appStore.showToast('创建成功', 'success')
    showAddForm.value = false
    form.value = { parent_code: '', code: '', name: '', category: 'asset', direction: 'debit', aux_customer: false, aux_supplier: false }
    await loadAccounts()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    submitting.value = false
  }
}

const deactivateAccount = async (account) => {
  if (!await appStore.customConfirm('停用确认', `确定停用科目 ${account.code} ${account.name}？`)) return
  try {
    await deleteChartOfAccount(account.id)
    appStore.showToast('已停用', 'success')
    await loadAccounts()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '停用失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => {
  if (accountingStore.currentAccountSetId) loadAccounts()
})
onMounted(() => { if (accountingStore.currentAccountSetId) loadAccounts() })
</script>
