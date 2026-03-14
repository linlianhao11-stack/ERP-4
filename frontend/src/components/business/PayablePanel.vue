<template>
  <div>
    <div class="flex items-center gap-2 mb-3 border-b pb-2">
      <AppTabs v-model="sub" :tabs="[
        { value: 'bills', label: '应付单' },
        { value: 'disbursements', label: '付款单' },
        { value: 'refunds', label: '付款退款' },
        { value: 'receipt', label: '入库单' },
        { value: 'returns', label: '采购退货' },
      ]" container-class="" />
      <button @click="showPeriodPicker = true" :disabled="generating" class="ml-auto px-3 py-1.5 text-[12px] font-medium rounded-lg bg-purple-subtle text-purple-emphasis hover:bg-purple-subtle transition-colors shrink-0">
        {{ generating ? '生成中...' : '批量生成凭证' }}
      </button>
    </div>
    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <PayableBillsTab v-if="sub === 'bills'" key="bills" />
      <DisbursementBillsTab v-else-if="sub === 'disbursements'" key="disbursements" />
      <DisbursementRefundBillsTab v-else-if="sub === 'refunds'" key="refunds" />
      <PurchaseReceiptTab v-else-if="sub === 'receipt'" key="receipt" />
      <PurchaseReturnTab v-else-if="sub === 'returns'" key="returns" />
    </Transition>

    <!-- 月份多选弹窗 -->
    <Transition name="fade">
      <div v-if="showPeriodPicker" class="modal-backdrop" @click.self="showPeriodPicker = false">
        <div class="modal max-w-sm">
          <div class="modal-header">
            <h3>选择生成凭证的月份</h3>
            <button @click="showPeriodPicker = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="space-y-1.5 max-h-64 overflow-y-auto">
              <label v-for="p in availablePeriods" :key="p.period_name"
                class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-elevated cursor-pointer text-sm"
                :class="{ 'opacity-50': p.is_closed }"
                :for="'ap-period-' + p.period_name">
                <input :id="'ap-period-' + p.period_name" type="checkbox" v-model="selectedPeriods" :value="p.period_name" :disabled="p.is_closed" class="rounded" />
                <span>{{ p.period_name }}</span>
                <span v-if="p.is_closed" class="text-xs text-muted ml-auto">已结账</span>
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showPeriodPicker = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handleGenerateVouchers" :disabled="!selectedPeriods.length || generating" class="btn btn-primary btn-sm">
              生成（{{ selectedPeriods.length }} 个月）
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import AppTabs from '../common/AppTabs.vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { generateApVouchers, getAccountingPeriods } from '../../api/accounting'
import PayableBillsTab from './PayableBillsTab.vue'
import DisbursementBillsTab from './DisbursementBillsTab.vue'
import DisbursementRefundBillsTab from './DisbursementRefundBillsTab.vue'
import PurchaseReceiptTab from './PurchaseReceiptTab.vue'
import PurchaseReturnTab from './PurchaseReturnTab.vue'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const sub = ref('bills')
const generating = ref(false)
const showPeriodPicker = ref(false)
const availablePeriods = ref([])
const selectedPeriods = ref([])

const loadPeriods = async () => {
  const setId = accountingStore.currentAccountSetId
  if (!setId) return
  const year = new Date().getFullYear()
  try {
    const [res1, res2] = await Promise.all([
      getAccountingPeriods(setId, year),
      getAccountingPeriods(setId, year - 1),
    ])
    availablePeriods.value = [...(res2.data || []), ...(res1.data || [])]
    const current = accountingStore.currentAccountSet?.current_period
    if (current && !selectedPeriods.value.length) {
      selectedPeriods.value = [current]
    }
  } catch { /* ignore */ }
}

const handleGenerateVouchers = async () => {
  const setId = accountingStore.currentAccountSetId
  if (!setId || !selectedPeriods.value.length) return
  const label = selectedPeriods.value.join(', ')
  if (!await appStore.customConfirm('确认操作', `确认为 ${label} 批量生成应付凭证？`)) return
  showPeriodPicker.value = false
  generating.value = true
  try {
    const { data } = await generateApVouchers(setId, selectedPeriods.value)
    const total = data.vouchers?.length || 0
    if (total === 0) {
      appStore.showToast('无需生成凭证（已确认单据均已生成凭证）', 'info')
    } else {
      const parts = Object.entries(data.summary || {})
        .filter(([, v]) => v.count > 0)
        .map(([k, v]) => `${k}: ${v.count} 张`)
      appStore.showToast(`成功生成 ${total} 张凭证（${parts.join('，')}）`, 'success')
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '生成凭证失败', 'error')
  } finally {
    generating.value = false
  }
}

watch(() => accountingStore.currentAccountSetId, () => loadPeriods())
watch(showPeriodPicker, (v) => { if (v) loadPeriods() })
</script>
