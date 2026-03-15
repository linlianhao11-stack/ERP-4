<template>
  <Transition name="fade">
    <div v-if="visible" class="modal-backdrop" @click.self="close">
      <div class="modal" style="max-width: 800px">
        <div class="modal-header">
          <h3>批量生成{{ mode === 'ar' ? '应收' : '应付' }}凭证</h3>
          <button @click="close" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <!-- 月份选择 -->
          <div class="flex items-center gap-3 mb-4">
            <label class="text-sm text-secondary">选择月份</label>
            <select v-model="selectedPeriod" class="toolbar-select">
              <option v-for="p in periods" :key="p.period_name" :value="p.period_name" :disabled="p.is_closed">
                {{ p.period_name }} {{ p.is_closed ? '(已结账)' : '' }}
              </option>
            </select>
          </div>

          <!-- 单据表格 -->
          <div v-if="bills.length" class="card overflow-hidden">
            <table class="w-full text-sm">
              <thead class="bg-elevated">
                <tr>
                  <th class="px-3 py-2 text-left w-10">
                    <input type="checkbox" v-model="allChecked" class="rounded" />
                  </th>
                  <th class="px-3 py-2 text-left">单据号</th>
                  <th class="px-3 py-2 text-left">类型</th>
                  <th class="px-3 py-2 text-left">{{ mode === 'ar' ? '客户' : '供应商' }}</th>
                  <th class="px-3 py-2 text-right">金额</th>
                  <th class="px-3 py-2 text-left">日期</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="bill in bills" :key="bill.type + '-' + bill.id" class="border-t border-border-light">
                  <td class="px-3 py-2">
                    <input type="checkbox" v-model="checkedBills" :value="bill" class="rounded" />
                  </td>
                  <td class="px-3 py-2 font-mono text-xs">{{ bill.bill_no }}</td>
                  <td class="px-3 py-2">{{ bill.type_label }}</td>
                  <td class="px-3 py-2">{{ bill.partner_name }}</td>
                  <td class="px-3 py-2 text-right font-mono">{{ formatMoney(bill.amount) }}</td>
                  <td class="px-3 py-2 text-secondary">{{ bill.date }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 无数据提示 -->
          <div v-else-if="!loading" class="text-center py-8 text-muted">
            {{ selectedPeriod ? '该月份无待处理单据' : '请选择月份' }}
          </div>

          <!-- 加载中 -->
          <div v-if="loading" class="text-center py-8 text-muted">加载中...</div>

          <!-- 底部信息栏 -->
          <div v-if="bills.length" class="mt-4 flex items-center justify-between text-sm">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="mergeByPartner" class="rounded" />
              <span>合并同{{ mode === 'ar' ? '客户' : '供应商' }}</span>
            </label>
            <span class="text-secondary">
              已选 {{ checkedBills.length }} 张，将生成约 {{ estimatedVoucherCount }} 张凭证
            </span>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="close" class="btn btn-secondary btn-sm">取消</button>
          <button @click="handleGenerate" :disabled="!checkedBills.length || generating" class="btn btn-primary btn-sm">
            {{ generating ? '生成中...' : '确认生成' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useAccountingStore } from '@/stores/accounting'
import { useAppStore } from '@/stores/app'
import {
  getAccountingPeriods,
  getPendingArBills,
  getPendingApBills,
  generateArVouchers,
  generateApVouchers,
} from '@/api/accounting'

const props = defineProps({
  visible: Boolean,
  mode: String, // "ar" | "ap"
  accountSetId: Number,
})
const emit = defineEmits(['update:visible', 'generated'])

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const periods = ref([])
const selectedPeriod = ref('')
const bills = ref([])
const checkedBills = ref([])
const mergeByPartner = ref(false)
const loading = ref(false)
const generating = ref(false)

// 全选 computed
const allChecked = computed({
  get: () => bills.value.length > 0 && checkedBills.value.length === bills.value.length,
  set: (val) => {
    checkedBills.value = val ? [...bills.value] : []
  },
})

// 预估凭证数
const estimatedVoucherCount = computed(() => {
  if (!checkedBills.value.length) return 0
  if (!mergeByPartner.value) return checkedBills.value.length
  const partnerIds = new Set(checkedBills.value.map((b) => b.partner_id))
  return partnerIds.size
})

// 金额格式化
const formatMoney = (v) => {
  const n = Number(v)
  return isNaN(n) ? '0.00' : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 加载会计期间
const loadPeriods = async () => {
  if (!props.accountSetId) return
  const year = new Date().getFullYear()
  try {
    const [r1, r2] = await Promise.all([
      getAccountingPeriods(props.accountSetId, year),
      getAccountingPeriods(props.accountSetId, year - 1),
    ])
    periods.value = [...(r2.data || []), ...(r1.data || [])]
    const current = accountingStore.currentAccountSet?.current_period
    if (current) selectedPeriod.value = current
  } catch {
    /* 忽略加载错误 */
  }
}

// 加载待处理单据
const loadBills = async () => {
  if (!selectedPeriod.value || !props.accountSetId) {
    bills.value = []
    return
  }
  loading.value = true
  try {
    const fn = props.mode === 'ar' ? getPendingArBills : getPendingApBills
    const { data } = await fn({
      account_set_id: props.accountSetId,
      period: selectedPeriod.value,
    })
    bills.value = data.items || []
    checkedBills.value = [...bills.value] // 默认全选
  } catch {
    bills.value = []
  } finally {
    loading.value = false
  }
}

// 生成凭证
const handleGenerate = async () => {
  if (!checkedBills.value.length) return
  generating.value = true
  try {
    const fn = props.mode === 'ar' ? generateArVouchers : generateApVouchers
    const payload = {
      bills: checkedBills.value.map((b) => ({ id: b.id, type: b.type })),
      merge_by_partner: mergeByPartner.value,
    }
    const { data } = await fn(props.accountSetId, payload)
    const total = data.vouchers?.length || 0
    if (total === 0) {
      appStore.showToast('无需生成凭证', 'info')
    } else {
      appStore.showToast(`成功生成 ${total} 张凭证`, 'success')
    }
    emit('generated')
    close()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '生成凭证失败', 'error')
  } finally {
    generating.value = false
  }
}

// 关闭弹窗
const close = () => {
  emit('update:visible', false)
}

// 弹窗打开时加载期间，重置状态
watch(
  () => props.visible,
  (v) => {
    if (v) {
      loadPeriods()
      bills.value = []
      checkedBills.value = []
    }
  }
)

// 切换月份时加载单据
watch(selectedPeriod, () => loadBills())
</script>
