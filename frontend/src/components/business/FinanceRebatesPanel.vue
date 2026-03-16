<template>
  <div class="card">
    <div class="p-3 border-b flex items-center gap-2 flex-wrap">
      <span @click="rebateTab = 'customer'; loadRebateSummaryData('customer')" :class="['tab', rebateTab === 'customer' ? 'active' : '']">客户返利</span>
      <span @click="rebateTab = 'supplier'; loadRebateSummaryData('supplier')" :class="['tab', rebateTab === 'supplier' ? 'active' : '']">供应商返利</span>
      <!-- 账套选择器 -->
      <select v-if="accountSets.length" v-model="selectedAccountSetId" class="input text-sm w-40 ml-2" @change="loadRebateSummaryData()">
        <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <div class="flex-1"></div>
      <button v-if="hasPermission('finance_rebate')" @click="openRebateChargeNew()" class="btn btn-primary btn-sm text-xs">新增充值</button>
    </div>
    <!-- Desktop table -->
    <div class="hidden md:block overflow-x-auto table-container">
      <table class="w-full text-sm">
        <thead class="bg-elevated">
          <tr>
            <th class="px-2 py-2 text-left">{{ rebateTab === 'customer' ? '客户' : '供应商' }}名称</th>
            <th class="px-2 py-2 text-right">返利余额</th>
            <th v-if="rebateTab === 'supplier'" class="px-2 py-2 text-right">在账资金</th>
            <th class="px-2 py-2 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr v-for="item in rebateSummary" :key="item.id">
            <td class="px-2 py-2 font-medium">{{ item.name }}</td>
            <td class="px-2 py-2 text-right"><span :class="item.rebate_balance > 0 ? 'text-success font-semibold' : 'text-muted'">¥{{ fmt(item.rebate_balance) }}</span></td>
            <td v-if="rebateTab === 'supplier'" class="px-2 py-2 text-right"><span :class="(item.credit_balance || 0) > 0 ? 'text-primary font-semibold' : 'text-muted'">¥{{ fmt(item.credit_balance || 0) }}</span></td>
            <td class="px-2 py-2 text-center">
              <button v-if="hasPermission('finance_rebate')" @click="openRebateCharge(rebateTab, item.id, item.name)" class="text-xs text-primary hover:underline mr-3">充值</button>
              <button @click="viewRebateDetail(rebateTab, item.id, item.name)" class="text-xs text-primary hover:underline">明细</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!rebateSummary.length" class="p-8 text-center text-muted text-sm">暂无数据</div>
    </div>
    <!-- Mobile cards -->
    <div class="md:hidden p-3 space-y-2">
      <div v-for="item in rebateSummary" :key="item.id" class="p-3 bg-elevated rounded-lg">
        <div class="flex justify-between items-center mb-2">
          <span class="font-medium">{{ item.name }}</span>
          <div class="text-right">
            <div :class="item.rebate_balance > 0 ? 'text-success font-semibold' : 'text-muted'">¥{{ fmt(item.rebate_balance) }}</div>
            <div v-if="rebateTab === 'supplier' && (item.credit_balance || 0) > 0" class="text-xs text-primary">在账: ¥{{ fmt(item.credit_balance) }}</div>
          </div>
        </div>
        <div class="flex gap-2">
          <button v-if="hasPermission('finance_rebate')" @click="openRebateCharge(rebateTab, item.id, item.name)" class="btn btn-sm btn-primary text-xs flex-1">充值</button>
          <button @click="viewRebateDetail(rebateTab, item.id, item.name)" class="btn btn-sm btn-secondary text-xs flex-1">明细</button>
        </div>
      </div>
      <div v-if="!rebateSummary.length" class="p-8 text-center text-muted text-sm">暂无数据</div>
    </div>

    <!-- Modal: Rebate Charge -->
    <div v-if="showRebateChargeModal" class="modal-overlay" @click.self="showRebateChargeModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="font-semibold">{{ rebateChargeForm.target_id ? '返利充值' : (rebateChargeForm.target_type === 'customer' ? '客户返利充值' : '供应商返利充值') }}</h3>
          <button @click="showRebateChargeModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body space-y-4">
          <!-- 弹窗内账套选择 -->
          <div v-if="accountSets.length">
            <label class="label">充值账套 *</label>
            <select v-model="chargeAccountSetId" class="input" @change="onChargeAccountSetChange">
              <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div v-if="rebateChargeForm.target_id" class="p-3 bg-info-subtle rounded-lg text-sm">
            <div class="font-semibold text-primary mb-1">{{ rebateChargeForm.target_name }}</div>
            <div class="text-primary">当前返利余额: <b>¥{{ fmt(rebateChargeForm.current_balance) }}</b></div>
          </div>
          <div v-else>
            <label class="label">选择{{ rebateChargeForm.target_type === 'customer' ? '客户' : '供应商' }} *</label>
            <select v-model="rebateChargeForm.target_id" class="input" @change="onRebateChargeTargetChange">
              <option :value="null">请选择</option>
              <option v-for="item in chargeTargetList" :key="item.id" :value="item.id">{{ item.name }}（余额: ¥{{ fmt(item.rebate_balance) }}）</option>
            </select>
          </div>
          <div>
            <label class="label">充值金额 *</label>
            <input v-model.number="rebateChargeForm.amount" type="number" step="0.01" min="0.01" class="input" placeholder="输入充值金额">
          </div>
          <div>
            <label class="label">备注</label>
            <input v-model="rebateChargeForm.remark" class="input" placeholder="充值原因说明（可选）">
          </div>
          <div class="flex gap-3 pt-2">
            <button @click="showRebateChargeModal = false" class="btn btn-secondary flex-1">取消</button>
            <button @click="handleChargeRebate" :disabled="submitting || !rebateChargeForm.target_id" class="btn btn-primary flex-1">{{ submitting ? '处理中...' : '确认充值' }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal: Rebate Detail -->
    <div v-if="showRebateDetailModal" class="modal-overlay" @click.self="showRebateDetailModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="font-semibold">返利明细 - {{ rebateDetailTarget?.name }}</h3>
          <button @click="showRebateDetailModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body space-y-4">
          <div class="p-3 bg-elevated rounded-lg text-sm">
            <div class="font-semibold">{{ rebateDetailTarget?.name }}</div>
            <div>当前余额: <b class="text-success">¥{{ fmt(rebateDetailTarget?.balance || 0) }}</b></div>
          </div>
          <div class="max-h-96 overflow-y-auto">
            <table class="w-full text-sm">
              <thead class="bg-elevated sticky top-0">
                <tr>
                  <th class="px-2 py-1 text-left">时间</th>
                  <th class="px-2 py-1 text-center">类型</th>
                  <th class="px-2 py-1 text-right">金额</th>
                  <th class="px-2 py-1 text-right">余额</th>
                  <th class="px-2 py-1 text-left">备注</th>
                </tr>
              </thead>
              <tbody class="divide-y">
                <tr v-for="log in rebateLogs" :key="log.id">
                  <td class="px-2 py-1 text-xs text-muted">{{ fmtDate(log.created_at) }}</td>
                  <td class="px-2 py-1 text-center"><span :class="log.type === 'charge' || log.type === 'refund' ? 'text-success' : 'text-error'" class="text-xs font-semibold">{{ rebateTypeLabel(log.type) }}</span></td>
                  <td class="px-2 py-1 text-right font-semibold" :class="log.type === 'charge' || log.type === 'refund' ? 'text-success' : 'text-error'">{{ log.type === 'charge' || log.type === 'refund' ? '+' : '-' }}¥{{ fmt(Math.abs(log.amount)) }}</td>
                  <td class="px-2 py-1 text-right">¥{{ fmt(log.balance_after) }}</td>
                  <td class="px-2 py-1 text-xs text-muted">{{ log.remark || '-' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!rebateLogs.length" class="p-6 text-center text-muted text-sm">暂无流水记录</div>
          </div>
          <div class="flex gap-3 pt-2">
            <button @click="showRebateDetailModal = false" class="btn btn-secondary flex-1">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useAppStore } from '../../stores/app'
import { useCustomersStore } from '../../stores/customers'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { getRebateSummary, chargeRebate, getRebateLogs } from '../../api/rebates'

const { hasPermission } = usePermission()

const props = defineProps({
  accountSets: { type: Array, default: () => [] }
})

const appStore = useAppStore()
const customersStore = useCustomersStore()
const { fmt, fmtDate } = useFormat()

const rebateTab = ref('customer')
const submitting = ref(false)
const rebateSummary = ref([])
const rebateLogs = ref([])
const selectedAccountSetId = ref(null)
const chargeAccountSetId = ref(null)
const chargeTargetList = ref([])

const showRebateChargeModal = ref(false)
const showRebateDetailModal = ref(false)
const rebateDetailTarget = ref(null)

const rebateChargeForm = reactive({
  target_type: 'customer',
  target_id: null,
  target_name: '',
  current_balance: 0,
  amount: null,
  remark: ''
})

const rebateTypeLabel = (type) => {
  const map = { charge: '充值', refund: '退回', use: '使用', credit_charge: '退货转入', credit_use: '在账抵扣', credit_refund: '在账退款' }
  return map[type] || type || '未知'
}

// 初始化默认账套
watch(() => props.accountSets, (sets) => {
  if (sets.length && !selectedAccountSetId.value) {
    selectedAccountSetId.value = sets[0].id
  }
}, { immediate: true })

const loadRebateSummaryData = async (targetType) => {
  try {
    const params = { target_type: targetType || rebateTab.value }
    if (selectedAccountSetId.value) {
      params.account_set_id = selectedAccountSetId.value
    }
    const { data } = await getRebateSummary(params)
    rebateSummary.value = data
  } catch (e) {
    console.error(e)
    appStore.showToast(e.response?.data?.detail || '加载返利数据失败', 'error')
  }
}

const openRebateCharge = (targetType, targetId, name) => {
  const item = rebateSummary.value.find(x => x.id === targetId)
  rebateChargeForm.target_type = targetType
  rebateChargeForm.target_id = targetId
  rebateChargeForm.target_name = name
  rebateChargeForm.current_balance = item?.rebate_balance || 0
  rebateChargeForm.amount = null
  rebateChargeForm.remark = ''
  chargeAccountSetId.value = selectedAccountSetId.value
  chargeTargetList.value = [...rebateSummary.value]
  showRebateChargeModal.value = true
}

const openRebateChargeNew = () => {
  rebateChargeForm.target_type = rebateTab.value
  rebateChargeForm.target_id = null
  rebateChargeForm.target_name = ''
  rebateChargeForm.current_balance = 0
  rebateChargeForm.amount = null
  rebateChargeForm.remark = ''
  chargeAccountSetId.value = selectedAccountSetId.value
  chargeTargetList.value = [...rebateSummary.value]
  showRebateChargeModal.value = true
}

const onRebateChargeTargetChange = () => {
  const item = chargeTargetList.value.find(x => x.id === rebateChargeForm.target_id)
  if (item) {
    rebateChargeForm.target_name = item.name
    rebateChargeForm.current_balance = item.rebate_balance || 0
  } else {
    rebateChargeForm.target_name = ''
    rebateChargeForm.current_balance = 0
  }
}

const onChargeAccountSetChange = async () => {
  try {
    const params = {
      target_type: rebateChargeForm.target_type,
      account_set_id: chargeAccountSetId.value
    }
    const { data } = await getRebateSummary(params)
    chargeTargetList.value = data
    if (rebateChargeForm.target_id) {
      const item = data.find(x => x.id === rebateChargeForm.target_id)
      rebateChargeForm.current_balance = item?.rebate_balance || 0
    }
  } catch (e) {
    console.error(e)
  }
}

const handleChargeRebate = async () => {
  if (!rebateChargeForm.amount || rebateChargeForm.amount <= 0) {
    appStore.showToast('请输入充值金额', 'error')
    return
  }
  if (!chargeAccountSetId.value) {
    appStore.showToast('请选择充值账套', 'error')
    return
  }
  if (submitting.value) return
  submitting.value = true
  try {
    const payload = {
      target_type: rebateChargeForm.target_type,
      target_id: rebateChargeForm.target_id,
      amount: rebateChargeForm.amount,
      remark: rebateChargeForm.remark || null,
      account_set_id: chargeAccountSetId.value
    }
    await chargeRebate(payload)
    appStore.showToast('充值成功')
    showRebateChargeModal.value = false
    loadRebateSummaryData(rebateChargeForm.target_type)
    customersStore.loadCustomers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '充值失败', 'error')
  } finally {
    submitting.value = false
  }
}

const viewRebateDetail = async (targetType, targetId, name) => {
  try {
    const item = rebateSummary.value.find(x => x.id === targetId)
    rebateDetailTarget.value = { name: name, balance: item?.rebate_balance || 0 }
    const params = { target_type: targetType, target_id: targetId }
    if (selectedAccountSetId.value) {
      params.account_set_id = selectedAccountSetId.value
    }
    const { data } = await getRebateLogs(params)
    rebateLogs.value = data
    showRebateDetailModal.value = true
  } catch (e) {
    appStore.showToast('加载失败', 'error')
  }
}

defineExpose({ refresh: () => loadRebateSummaryData(rebateTab.value) })

onMounted(() => { loadRebateSummaryData(rebateTab.value) })
</script>
