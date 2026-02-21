<template>
  <div class="card">
    <div class="p-3 border-b flex items-center gap-2">
      <span @click="rebateTab = 'customer'; loadRebateSummaryData('customer')" :class="['tab', rebateTab === 'customer' ? 'active' : '']">客户返利</span>
      <span @click="rebateTab = 'supplier'; loadRebateSummaryData('supplier')" :class="['tab', rebateTab === 'supplier' ? 'active' : '']">供应商返利</span>
      <div class="flex-1"></div>
      <button v-if="hasPermission('finance')" @click="openRebateChargeNew()" class="btn btn-primary btn-sm text-xs">新增充值</button>
    </div>
    <!-- Desktop table -->
    <div class="hidden md:block overflow-x-auto table-container">
      <table class="w-full text-sm">
        <thead class="bg-[#f5f5f7]">
          <tr>
            <th class="px-3 py-2 text-left">{{ rebateTab === 'customer' ? '客户' : '供应商' }}名称</th>
            <th class="px-3 py-2 text-right">返利余额</th>
            <th class="px-3 py-2 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr v-for="item in rebateSummary" :key="item.id">
            <td class="px-3 py-2 font-medium">{{ item.name }}</td>
            <td class="px-3 py-2 text-right"><span :class="item.rebate_balance > 0 ? 'text-[#34c759] font-semibold' : 'text-[#86868b]'">¥{{ fmt(item.rebate_balance) }}</span></td>
            <td class="px-3 py-2 text-center">
              <button v-if="hasPermission('finance')" @click="openRebateCharge(rebateTab, item.id, item.name)" class="text-xs text-[#0071e3] hover:underline mr-3">充值</button>
              <button @click="viewRebateDetail(rebateTab, item.id, item.name)" class="text-xs text-[#0071e3] hover:underline">明细</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!rebateSummary.length" class="p-8 text-center text-[#86868b] text-sm">暂无数据</div>
    </div>
    <!-- Mobile cards -->
    <div class="md:hidden p-3 space-y-2">
      <div v-for="item in rebateSummary" :key="item.id" class="p-3 bg-[#f5f5f7] rounded-lg">
        <div class="flex justify-between items-center mb-2">
          <span class="font-medium">{{ item.name }}</span>
          <span :class="item.rebate_balance > 0 ? 'text-[#34c759] font-semibold' : 'text-[#86868b]'">¥{{ fmt(item.rebate_balance) }}</span>
        </div>
        <div class="flex gap-2">
          <button v-if="hasPermission('finance')" @click="openRebateCharge(rebateTab, item.id, item.name)" class="btn btn-sm btn-primary text-xs flex-1">充值</button>
          <button @click="viewRebateDetail(rebateTab, item.id, item.name)" class="btn btn-sm btn-secondary text-xs flex-1">明细</button>
        </div>
      </div>
      <div v-if="!rebateSummary.length" class="p-8 text-center text-[#86868b] text-sm">暂无数据</div>
    </div>

    <!-- Modal: Rebate Charge -->
    <div v-if="showRebateChargeModal" class="modal-overlay" @click.self="showRebateChargeModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="font-semibold">{{ rebateChargeForm.target_id ? '返利充值' : (rebateChargeForm.target_type === 'customer' ? '客户返利充值' : '供应商返利充值') }}</h3>
          <button @click="showRebateChargeModal = false" class="text-[#86868b] hover:text-[#6e6e73] text-xl">&times;</button>
        </div>
        <div class="modal-body space-y-4">
          <div v-if="rebateChargeForm.target_id" class="p-3 bg-[#e8f4fd] rounded-lg text-sm">
            <div class="font-semibold text-[#0071e3] mb-1">{{ rebateChargeForm.target_name }}</div>
            <div class="text-[#0071e3]">当前返利余额: <b>¥{{ fmt(rebateChargeForm.current_balance) }}</b></div>
          </div>
          <div v-else>
            <label class="label">选择{{ rebateChargeForm.target_type === 'customer' ? '客户' : '供应商' }} *</label>
            <select v-model="rebateChargeForm.target_id" class="input" @change="onRebateChargeTargetChange">
              <option :value="null">请选择</option>
              <option v-for="item in rebateSummary" :key="item.id" :value="item.id">{{ item.name }}（余额: ¥{{ fmt(item.rebate_balance) }}）</option>
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
          <button @click="showRebateDetailModal = false" class="text-[#86868b] hover:text-[#6e6e73] text-xl">&times;</button>
        </div>
        <div class="modal-body space-y-4">
          <div class="p-3 bg-[#f5f5f7] rounded-lg text-sm">
            <div class="font-semibold">{{ rebateDetailTarget?.name }}</div>
            <div>当前余额: <b class="text-[#34c759]">¥{{ fmt(rebateDetailTarget?.balance || 0) }}</b></div>
          </div>
          <div class="max-h-96 overflow-y-auto">
            <table class="w-full text-sm">
              <thead class="bg-[#f5f5f7] sticky top-0">
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
                  <td class="px-2 py-1 text-xs text-[#86868b]">{{ fmtDate(log.created_at) }}</td>
                  <td class="px-2 py-1 text-center"><span :class="log.type === 'charge' || log.type === 'refund' ? 'text-[#34c759]' : 'text-[#ff3b30]'" class="text-xs font-semibold">{{ log.type === 'charge' ? '充值' : log.type === 'refund' ? '退回' : log.type === 'use' ? '使用' : (log.type || '未知') }}</span></td>
                  <td class="px-2 py-1 text-right font-semibold" :class="log.type === 'charge' || log.type === 'refund' ? 'text-[#34c759]' : 'text-[#ff3b30]'">{{ log.type === 'charge' || log.type === 'refund' ? '+' : '-' }}¥{{ fmt(log.amount) }}</td>
                  <td class="px-2 py-1 text-right">¥{{ fmt(log.balance_after) }}</td>
                  <td class="px-2 py-1 text-xs text-[#86868b]">{{ log.remark || '-' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!rebateLogs.length" class="p-6 text-center text-[#86868b] text-sm">暂无流水记录</div>
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
import { ref, reactive, onMounted } from 'vue'
import { useAppStore } from '../../stores/app'
import { useCustomersStore } from '../../stores/customers'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { getRebateSummary, chargeRebate, getRebateLogs } from '../../api/rebates'

const { hasPermission } = usePermission()

const appStore = useAppStore()
const customersStore = useCustomersStore()
const { fmt, fmtDate } = useFormat()

const rebateTab = ref('customer')
const submitting = ref(false)
const rebateSummary = ref([])
const rebateLogs = ref([])

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

const loadRebateSummaryData = async (targetType) => {
  try {
    const { data } = await getRebateSummary({ target_type: targetType || rebateTab.value })
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
  showRebateChargeModal.value = true
}

const openRebateChargeNew = () => {
  rebateChargeForm.target_type = rebateTab.value
  rebateChargeForm.target_id = null
  rebateChargeForm.target_name = ''
  rebateChargeForm.current_balance = 0
  rebateChargeForm.amount = null
  rebateChargeForm.remark = ''
  showRebateChargeModal.value = true
}

const onRebateChargeTargetChange = () => {
  const item = rebateSummary.value.find(x => x.id === rebateChargeForm.target_id)
  if (item) {
    rebateChargeForm.target_name = item.name
    rebateChargeForm.current_balance = item.rebate_balance || 0
  } else {
    rebateChargeForm.target_name = ''
    rebateChargeForm.current_balance = 0
  }
}

const handleChargeRebate = async () => {
  if (!rebateChargeForm.amount || rebateChargeForm.amount <= 0) {
    appStore.showToast('请输入充值金额', 'error')
    return
  }
  if (submitting.value) return
  submitting.value = true
  try {
    await chargeRebate({
      target_type: rebateChargeForm.target_type,
      target_id: rebateChargeForm.target_id,
      amount: rebateChargeForm.amount,
      remark: rebateChargeForm.remark || null
    })
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
    const { data } = await getRebateLogs({ target_type: targetType, target_id: targetId })
    rebateLogs.value = data
    showRebateDetailModal.value = true
  } catch (e) {
    appStore.showToast('加载失败', 'error')
  }
}

defineExpose({ refresh: () => loadRebateSummaryData(rebateTab.value) })

onMounted(() => { loadRebateSummaryData(rebateTab.value) })
</script>
