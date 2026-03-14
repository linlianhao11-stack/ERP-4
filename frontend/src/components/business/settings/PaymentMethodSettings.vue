<!--
  收款方式与付款方式管理组件
  功能：按账套 Tab 切换，收款方式（PaymentMethod）的增删改、付款方式（DisbursementMethod）的增删改
  从 SettingsView.vue 财务设置标签页提取
-->
<template>
  <div>
    <!-- 账套 Tab 切换 -->
    <div v-if="accountSets.length > 1" class="flex gap-2 mb-4 border-b border-border pb-2">
      <button
        v-for="as in accountSets" :key="as.id"
        @click="switchAccountSet(as.id)"
        :class="['text-sm px-3 py-1.5 rounded-t transition-colors',
          currentAccountSetId === as.id
            ? 'bg-primary text-white font-medium'
            : 'text-secondary hover:text-foreground hover:bg-elevated']"
      >
        {{ as.name }}
      </button>
    </div>

    <!-- 收款方式管理 -->
    <div class="grid md:grid-cols-2 gap-5">
      <div class="card p-4">
        <h3 class="font-semibold mb-3 text-sm">收款方式管理</h3>
        <div class="text-xs text-muted mb-3">管理收款时可选的付款方式，修改后全局生效</div>
        <div class="space-y-2 mb-3">
          <div v-for="m in paymentMethods" :key="m.id" class="flex justify-between items-center p-2 bg-elevated rounded text-sm">
            <!-- 编辑模式 -->
            <div v-if="editingPayMethodId === m.id" class="flex items-center gap-2 flex-1">
              <input v-model="editingPayMethodName" class="input text-sm flex-1" @keyup.enter="saveEditPaymentMethod" @keyup.escape="cancelEditPaymentMethod">
              <button @click="saveEditPaymentMethod" class="text-success-emphasis text-xs font-medium">保存</button>
              <button @click="cancelEditPaymentMethod" class="text-muted text-xs">取消</button>
            </div>
            <!-- 展示模式 -->
            <template v-else>
              <div>
                <span class="font-medium">{{ m.name }}</span>
                <span class="text-xs text-muted ml-1">({{ m.code }})</span>
              </div>
              <div>
                <button @click="editPaymentMethod(m)" class="text-primary text-xs mr-2">编辑</button>
                <button @click="handleDeletePaymentMethod(m.id)" class="text-error text-xs">删除</button>
              </div>
            </template>
          </div>
          <div v-if="!paymentMethods.length" class="text-muted text-center py-2 text-sm">暂无收款方式</div>
        </div>
        <!-- 新增收款方式 -->
        <form @submit.prevent="handleCreatePaymentMethod" class="flex gap-2">
          <input v-model="newPayMethodCode" class="input flex-1 text-sm" placeholder="编码(如 bank_abc)">
          <input v-model="newPayMethodName" class="input flex-1 text-sm" placeholder="显示名称">
          <button type="submit" class="btn btn-primary btn-sm">添加</button>
        </form>
      </div>
    </div>

    <!-- 付款方式管理 -->
    <div class="grid md:grid-cols-2 gap-5 mt-5">
      <div class="card p-4">
        <h3 class="font-semibold mb-3 text-sm">付款方式管理</h3>
        <div class="text-xs text-muted mb-3">管理向供应商付款时可选的付款方式，修改后全局生效</div>
        <div class="space-y-2 mb-3">
          <div v-for="m in disbursementMethods" :key="m.id" class="flex justify-between items-center p-2 bg-elevated rounded text-sm">
            <!-- 编辑模式 -->
            <div v-if="editingDisbMethodId === m.id" class="flex items-center gap-2 flex-1">
              <input v-model="editingDisbMethodName" class="input text-sm flex-1" @keyup.enter="saveEditDisbursementMethod" @keyup.escape="cancelEditDisbursementMethod">
              <button @click="saveEditDisbursementMethod" class="text-success-emphasis text-xs font-medium">保存</button>
              <button @click="cancelEditDisbursementMethod" class="text-muted text-xs">取消</button>
            </div>
            <!-- 展示模式 -->
            <template v-else>
              <div>
                <span class="font-medium">{{ m.name }}</span>
                <span class="text-xs text-muted ml-1">({{ m.code }})</span>
              </div>
              <div>
                <button @click="editDisbursementMethod(m)" class="text-primary text-xs mr-2">编辑</button>
                <button @click="handleDeleteDisbursementMethod(m.id)" class="text-error text-xs">删除</button>
              </div>
            </template>
          </div>
          <div v-if="!disbursementMethods.length" class="text-muted text-center py-2 text-sm">暂无付款方式</div>
        </div>
        <!-- 新增付款方式 -->
        <form @submit.prevent="handleCreateDisbursementMethod" class="flex gap-2">
          <input v-model="newDisbMethodCode" class="input flex-1 text-sm" placeholder="编码(如 bank_abc)">
          <input v-model="newDisbMethodName" class="input flex-1 text-sm" placeholder="显示名称">
          <button type="submit" class="btn btn-primary btn-sm">添加</button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 收款方式与付款方式管理
 * 包含：账套 Tab 切换、收款方式CRUD、付款方式(付供应商)CRUD
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { useAccountingStore } from '../../../stores/accounting'
import {
  createPaymentMethod, updatePaymentMethod, deletePaymentMethod as deletePaymentMethodApi,
  createDisbursementMethod, updateDisbursementMethod, deleteDisbursementMethod as deleteDisbursementMethodApi
} from '../../../api/settings'

const emit = defineEmits(['data-changed'])

const appStore = useAppStore()
const settingsStore = useSettingsStore()
const accountingStore = useAccountingStore()

// 账套相关
const accountSets = computed(() => accountingStore.accountSets)
const currentAccountSetId = ref(null)

const paymentMethods = computed(() => settingsStore.paymentMethods)
const disbursementMethods = computed(() => settingsStore.disbursementMethods)

// === 收款方式状态 ===
const newPayMethodCode = ref('')
const newPayMethodName = ref('')
const editingPayMethodId = ref(null)
const editingPayMethodName = ref('')

// === 付款方式状态 ===
const newDisbMethodCode = ref('')
const newDisbMethodName = ref('')
const editingDisbMethodId = ref(null)
const editingDisbMethodName = ref('')

/** 切换账套 */
function switchAccountSet(id) {
  currentAccountSetId.value = id
}

/** 按当前账套重新加载收付款方式 */
function reloadMethods() {
  settingsStore.loadPaymentMethods(currentAccountSetId.value)
  settingsStore.loadDisbursementMethods(currentAccountSetId.value)
}

// 监听账套切换
watch(currentAccountSetId, () => {
  // 切换时清除编辑状态
  cancelEditPaymentMethod()
  cancelEditDisbursementMethod()
  reloadMethods()
})

// === 收款方式操作 ===
const editPaymentMethod = (m) => {
  editingPayMethodId.value = m.id
  editingPayMethodName.value = m.name
}

const saveEditPaymentMethod = async () => {
  if (!editingPayMethodName.value.trim()) {
    appStore.showToast('名称不能为空', 'error')
    return
  }
  try {
    await updatePaymentMethod(editingPayMethodId.value, { name: editingPayMethodName.value.trim() })
    appStore.showToast('修改成功')
    editingPayMethodId.value = null
    editingPayMethodName.value = ''
    reloadMethods()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '修改失败', 'error')
  }
}

const cancelEditPaymentMethod = () => {
  editingPayMethodId.value = null
  editingPayMethodName.value = ''
}

const handleCreatePaymentMethod = async () => {
  if (!newPayMethodCode.value.trim() || !newPayMethodName.value.trim()) {
    appStore.showToast('请填写编码和名称', 'error')
    return
  }
  try {
    await createPaymentMethod({
      code: newPayMethodCode.value.trim(),
      name: newPayMethodName.value.trim(),
      account_set_id: currentAccountSetId.value
    })
    appStore.showToast('创建成功')
    newPayMethodCode.value = ''
    newPayMethodName.value = ''
    reloadMethods()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  }
}

const handleDeletePaymentMethod = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该收款方式？')) return
  try {
    await deletePaymentMethodApi(id)
    appStore.showToast('已删除')
    reloadMethods()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// === 付款方式操作 ===
const editDisbursementMethod = (m) => {
  editingDisbMethodId.value = m.id
  editingDisbMethodName.value = m.name
}

const saveEditDisbursementMethod = async () => {
  if (!editingDisbMethodName.value.trim()) {
    appStore.showToast('名称不能为空', 'error')
    return
  }
  try {
    await updateDisbursementMethod(editingDisbMethodId.value, { name: editingDisbMethodName.value.trim() })
    appStore.showToast('修改成功')
    editingDisbMethodId.value = null
    editingDisbMethodName.value = ''
    reloadMethods()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '修改失败', 'error')
  }
}

const cancelEditDisbursementMethod = () => {
  editingDisbMethodId.value = null
  editingDisbMethodName.value = ''
}

const handleCreateDisbursementMethod = async () => {
  if (!newDisbMethodCode.value.trim() || !newDisbMethodName.value.trim()) {
    appStore.showToast('编码和名称不能为空', 'error')
    return
  }
  try {
    await createDisbursementMethod({
      code: newDisbMethodCode.value.trim(),
      name: newDisbMethodName.value.trim(),
      account_set_id: currentAccountSetId.value
    })
    appStore.showToast('添加成功')
    newDisbMethodCode.value = ''
    newDisbMethodName.value = ''
    reloadMethods()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '添加失败', 'error')
  }
}

const handleDeleteDisbursementMethod = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该付款方式？')) return
  try {
    await deleteDisbursementMethodApi(id)
    appStore.showToast('已删除')
    reloadMethods()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// 组件挂载时加载数据
onMounted(async () => {
  // 加载账套列表
  if (!accountSets.value.length) {
    await accountingStore.loadAccountSets()
  }
  // 默认选中第一个账套
  if (accountSets.value.length && !currentAccountSetId.value) {
    currentAccountSetId.value = accountSets.value[0].id
  }
  // 如果没有账套，直接加载全部收付款方式
  if (!currentAccountSetId.value) {
    settingsStore.loadPaymentMethods()
    settingsStore.loadDisbursementMethods()
  }
})
</script>
