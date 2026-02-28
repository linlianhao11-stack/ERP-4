<template>
  <div>
    <!-- 账套切换器 -->
    <div v-if="accountingStore.accountSets.length > 0" class="flex items-center gap-3 mb-4">
      <span class="text-[13px] text-[#86868b]">当前账套</span>
      <div class="flex gap-2">
        <button
          v-for="s in accountingStore.accountSets"
          :key="s.id"
          @click="switchAccountSet(s.id)"
          :class="[
            'px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-200',
            s.id === accountingStore.currentAccountSetId
              ? 'bg-[#0071e3] text-white shadow-sm'
              : 'bg-[#f5f5f7] text-[#1d1d1f] hover:bg-[#e8e8ed]'
          ]"
        >
          {{ s.name }}
        </button>
      </div>
      <button v-if="isAdmin" @click="openAccountSetModal" class="text-[12px] text-[#86868b] hover:text-[#1d1d1f] flex items-center gap-0.5">
        <span>⚙</span> 管理
      </button>
      <span v-if="accountingStore.currentAccountSet" class="text-[12px] text-[#86868b] ml-auto">
        当前期间: {{ accountingStore.currentAccountSet.current_period }}
      </span>
    </div>

    <!-- Tab Navigation -->
    <div class="flex flex-wrap gap-2 mb-3 border-b pb-2">
      <span @click="tab = 'vouchers'" :class="['tab', tab === 'vouchers' ? 'active' : '']">凭证管理</span>
      <span @click="tab = 'accounts'" :class="['tab', tab === 'accounts' ? 'active' : '']">科目管理</span>
      <span @click="tab = 'periods'" :class="['tab', tab === 'periods' ? 'active' : '']">会计期间</span>
      <span @click="tab = 'ledgers'" :class="['tab', tab === 'ledgers' ? 'active' : '']">账簿查询</span>
      <span @click="tab = 'receivables'" :class="['tab', tab === 'receivables' ? 'active' : '']">应收管理</span>
      <span @click="tab = 'payables'" :class="['tab', tab === 'payables' ? 'active' : '']">应付管理</span>
      <span @click="tab = 'invoices'" :class="['tab', tab === 'invoices' ? 'active' : '']">发票管理</span>
    </div>

    <!-- 首次进入引导卡片（无账套） -->
    <div v-if="!accountingStore.currentAccountSetId && accountingStore.accountSets.length === 0" class="flex flex-col items-center justify-center py-20">
      <div class="text-center max-w-sm">
        <div class="text-4xl mb-4">📒</div>
        <h3 class="text-[17px] font-semibold text-[#1d1d1f] mb-2">尚未创建账套</h3>
        <p class="text-[13px] text-[#86868b] mb-6">账套是财务核算的基础单元，请先创建一个账套以开始使用财务模块。</p>
        <button v-if="isAdmin" @click="openCreateForm" class="btn btn-primary">创建第一个账套</button>
      </div>
    </div>

    <!-- No account set selected (has sets but none selected) -->
    <div v-else-if="!accountingStore.currentAccountSetId" class="text-center py-20 text-[#86868b]">
      <p class="text-[15px]">请先选择账套</p>
    </div>

    <!-- Panels -->
    <template v-else>
      <VoucherPanel v-if="tab === 'vouchers'" />
      <ChartOfAccountsPanel v-if="tab === 'accounts'" />
      <AccountingPeriodsPanel v-if="tab === 'periods'" />
      <LedgerPanel v-if="tab === 'ledgers'" />
      <ReceivablePanel v-if="tab === 'receivables'" />
      <PayablePanel v-if="tab === 'payables'" />
      <InvoicePanel v-if="tab === 'invoices'" />
    </template>

    <!-- 账套管理弹窗 -->
    <Transition name="fade">
      <div v-if="showAccountSetModal" class="modal-backdrop" @click.self="showAccountSetModal = false">
        <div class="modal" style="max-width: 560px">
          <div class="modal-header">
            <h3>{{ accountSetFormMode === 'create' ? '新建账套' : (accountSetFormMode === 'edit' ? '编辑账套' : '账套管理') }}</h3>
            <button @click="showAccountSetModal = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <!-- 列表态 -->
            <template v-if="!accountSetFormMode">
              <div class="space-y-2 mb-4">
                <div v-for="s in accountingStore.accountSets" :key="s.id" class="flex items-center justify-between p-3.5 bg-[#f5f5f7] rounded-xl hover:bg-[#ececf0] transition-colors">
                  <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-lg bg-[#0071e3]/10 flex items-center justify-center text-[#0071e3] text-sm font-bold shrink-0">{{ s.code?.charAt(0) || '#' }}</div>
                    <div>
                      <div class="text-[14px] font-medium text-[#1d1d1f]">{{ s.name }}</div>
                      <div class="text-[12px] text-[#86868b]">{{ s.code }}<span v-if="s.company_name"> · {{ s.company_name }}</span></div>
                    </div>
                  </div>
                  <button @click="openEditForm(s)" class="text-[12px] text-[#0071e3] hover:text-[#0077ED] font-medium px-2.5 py-1 rounded-lg hover:bg-[#0071e3]/8 transition-colors">编辑</button>
                </div>
                <div v-if="accountingStore.accountSets.length === 0" class="text-center py-10">
                  <div class="text-[#c7c7cc] text-3xl mb-2">📋</div>
                  <div class="text-[13px] text-[#86868b]">暂无账套，点击下方按钮创建</div>
                </div>
              </div>
              <div class="flex gap-3 pt-2 border-t border-[#e8e8ed]">
                <button @click="showAccountSetModal = false" class="btn btn-secondary flex-1">关闭</button>
                <button @click="accountSetFormMode = 'create'; resetForm()" class="btn btn-primary flex-1">新建账套</button>
              </div>
            </template>

            <!-- 表单态 -->
            <template v-else>
              <!-- 基本信息 -->
              <div class="text-[12px] font-semibold text-[#86868b] uppercase tracking-wider mb-2">基本信息</div>
              <div class="space-y-3 mb-5">
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="label">编码 <span class="text-[#ff3b30]">*</span></label>
                    <input v-model="accountSetForm.code" class="input text-sm" placeholder="如 QL01" :disabled="accountSetFormMode === 'edit'" :class="{ 'opacity-50 cursor-not-allowed': accountSetFormMode === 'edit' }">
                  </div>
                  <div>
                    <label class="label">名称 <span class="text-[#ff3b30]">*</span></label>
                    <input v-model="accountSetForm.name" class="input text-sm" placeholder="如 启领贸易">
                  </div>
                </div>
                <div v-if="accountSetFormMode === 'edit'" class="flex items-center gap-3 p-3 bg-[#f5f5f7] rounded-xl">
                  <span class="text-[13px] text-[#6e6e73]">启用状态</span>
                  <button @click="accountSetForm.is_active = !accountSetForm.is_active" :class="[
                    'relative inline-flex h-[22px] w-[40px] items-center rounded-full transition-colors duration-200',
                    accountSetForm.is_active ? 'bg-[#34c759]' : 'bg-[#c7c7cc]'
                  ]">
                    <span :class="[
                      'inline-block h-[18px] w-[18px] rounded-full bg-white shadow-sm transition-transform duration-200',
                      accountSetForm.is_active ? 'translate-x-[20px]' : 'translate-x-[2px]'
                    ]" />
                  </button>
                  <span class="text-[13px]" :class="accountSetForm.is_active ? 'text-[#34c759] font-medium' : 'text-[#86868b]'">{{ accountSetForm.is_active ? '已启用' : '已停用' }}</span>
                </div>
              </div>

              <!-- 企业信息 -->
              <div class="text-[12px] font-semibold text-[#86868b] uppercase tracking-wider mb-2">企业信息</div>
              <div class="space-y-3 mb-5">
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="label">公司名称</label>
                    <input v-model="accountSetForm.company_name" class="input text-sm" placeholder="全称">
                  </div>
                  <div>
                    <label class="label">税号</label>
                    <input v-model="accountSetForm.tax_id" class="input text-sm" placeholder="统一社会信用代码">
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="label">法人</label>
                    <input v-model="accountSetForm.legal_person" class="input text-sm" placeholder="法定代表人">
                  </div>
                  <div>
                    <label class="label">地址</label>
                    <input v-model="accountSetForm.address" class="input text-sm" placeholder="注册地址">
                  </div>
                </div>
              </div>

              <!-- 银行信息 -->
              <div class="text-[12px] font-semibold text-[#86868b] uppercase tracking-wider mb-2">银行信息</div>
              <div class="space-y-3 mb-5">
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="label">开户行</label>
                    <input v-model="accountSetForm.bank_name" class="input text-sm" placeholder="开户银行名称">
                  </div>
                  <div>
                    <label class="label">银行账号</label>
                    <input v-model="accountSetForm.bank_account" class="input text-sm" placeholder="对公账户">
                  </div>
                </div>
              </div>

              <!-- 启用设置（仅创建） -->
              <template v-if="accountSetFormMode === 'create'">
                <div class="text-[12px] font-semibold text-[#86868b] uppercase tracking-wider mb-2">启用设置</div>
                <div class="grid grid-cols-2 gap-3 mb-2">
                  <div>
                    <label class="label">启用年份 <span class="text-[#ff3b30]">*</span></label>
                    <input type="number" v-model.number="accountSetForm.start_year" class="input text-sm" min="2000" max="2099">
                  </div>
                  <div>
                    <label class="label">启用月份 <span class="text-[#ff3b30]">*</span></label>
                    <select v-model.number="accountSetForm.start_month" class="input text-sm">
                      <option v-for="m in 12" :key="m" :value="m">{{ m }} 月</option>
                    </select>
                  </div>
                </div>
                <div class="text-[12px] text-[#86868b] mb-2">系统将自动初始化该年度的会计期间和标准科目表</div>
              </template>

              <!-- 操作按钮 -->
              <div class="flex gap-3 pt-4 border-t border-[#e8e8ed]">
                <button @click="accountSetFormMode = null" class="btn btn-secondary flex-1">{{ hasMultipleSets ? '返回列表' : '取消' }}</button>
                <button @click="saveAccountSet" class="btn btn-primary flex-1" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAccountingStore } from '../stores/accounting'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'
import { createAccountSet, updateAccountSet, getAccountSet } from '../api/accounting'
import VoucherPanel from '../components/business/VoucherPanel.vue'
import ChartOfAccountsPanel from '../components/business/ChartOfAccountsPanel.vue'
import AccountingPeriodsPanel from '../components/business/AccountingPeriodsPanel.vue'
import LedgerPanel from '../components/business/LedgerPanel.vue'
import ReceivablePanel from '../components/business/ReceivablePanel.vue'
import PayablePanel from '../components/business/PayablePanel.vue'
import InvoicePanel from '../components/business/InvoicePanel.vue'

const accountingStore = useAccountingStore()
const authStore = useAuthStore()
const appStore = useAppStore()
const tab = ref('vouchers')

const isAdmin = computed(() => authStore.user?.role === 'admin')
const hasMultipleSets = computed(() => accountingStore.accountSets.length > 0)

// 账套管理弹窗 state
const showAccountSetModal = ref(false)
const accountSetFormMode = ref(null) // null=列表态, 'create', 'edit'
const editingAccountSetId = ref(null)
const saving = ref(false)
const accountSetForm = ref({
  code: '', name: '', company_name: '', tax_id: '',
  legal_person: '', address: '', bank_name: '', bank_account: '',
  start_year: new Date().getFullYear(), start_month: 1,
  is_active: true,
})

const switchAccountSet = (id) => {
  accountingStore.setCurrentAccountSet(id)
}

const openAccountSetModal = () => {
  accountSetFormMode.value = null
  showAccountSetModal.value = true
}

const resetForm = () => {
  editingAccountSetId.value = null
  accountSetForm.value = {
    code: '', name: '', company_name: '', tax_id: '',
    legal_person: '', address: '', bank_name: '', bank_account: '',
    start_year: new Date().getFullYear(), start_month: 1,
    is_active: true,
  }
}

const openCreateForm = () => {
  accountSetFormMode.value = 'create'
  resetForm()
  showAccountSetModal.value = true
}

const openEditForm = async (s) => {
  try {
    const { data } = await getAccountSet(s.id)
    accountSetFormMode.value = 'edit'
    editingAccountSetId.value = s.id
    accountSetForm.value = {
      code: data.code, name: data.name,
      company_name: data.company_name || '', tax_id: data.tax_id || '',
      legal_person: data.legal_person || '', address: data.address || '',
      bank_name: data.bank_name || '', bank_account: data.bank_account || '',
      is_active: data.is_active !== false,
    }
  } catch (e) {
    appStore.showToast('加载账套信息失败', 'error')
  }
}

const saveAccountSet = async () => {
  if (!accountSetForm.value.code || !accountSetForm.value.name) {
    appStore.showToast('请填写编码和名称', 'error')
    return
  }
  if (accountSetFormMode.value === 'create' && !accountSetForm.value.start_year) {
    appStore.showToast('请填写启用年份', 'error')
    return
  }
  saving.value = true
  try {
    if (accountSetFormMode.value === 'create') {
      const { data } = await createAccountSet(accountSetForm.value)
      appStore.showToast(`账套 ${data.name} 创建成功`, 'success')
      await accountingStore.loadAccountSets()
      accountingStore.setCurrentAccountSet(data.id)
    } else {
      const { code, start_year, start_month, ...updateData } = accountSetForm.value
      await updateAccountSet(editingAccountSetId.value, updateData)
      appStore.showToast('更新成功', 'success')
      await accountingStore.loadAccountSets()
    }
    accountSetFormMode.value = null
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

watch(showAccountSetModal, (v) => {
  if (v) {
    // 仅在通过 openAccountSetModal（管理入口）打开时重置为列表态
    // openCreateForm 已预设 accountSetFormMode = 'create'，此处不覆盖
    accountingStore.loadAccountSets()
  }
})

onMounted(() => {
  accountingStore.loadAccountSets()
})
</script>
