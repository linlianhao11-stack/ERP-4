<template>
  <Transition name="fade">
    <div v-if="visible" class="modal-backdrop" @click.self="$emit('close')">
      <div class="modal max-w-2xl">
        <div class="modal-header">
          <h3>{{ mode === 'sales' ? '推送销项发票' : '推送进项发票' }}</h3>
          <button @click="$emit('close')" class="modal-close">&times;</button>
        </div>
        <div class="modal-body">
          <!-- 已选单据摘要 -->
          <div class="mb-4">
            <div class="text-xs font-semibold text-secondary mb-2">
              已选 {{ bills.length }} 张{{ mode === 'sales' ? '应收' : '应付' }}单
            </div>
            <div class="border border-line rounded-xl overflow-hidden">
              <table class="w-full text-[13px]">
                <thead class="bg-elevated">
                  <tr>
                    <th class="px-3 py-1.5 text-left">单号</th>
                    <th class="px-3 py-1.5 text-right">金额</th>
                    <th class="px-3 py-1.5 text-left">状态</th>
                  </tr>
                </thead>
                <tbody class="divide-y">
                  <tr v-for="b in bills" :key="b.id">
                    <td class="px-3 py-1.5 font-mono text-[12px]">{{ b.bill_no }}</td>
                    <td class="px-3 py-1.5 text-right">{{ fmtMoney(b.total_amount) }}</td>
                    <td class="px-3 py-1.5">
                      <span :class="b.status === 'completed' ? 'badge badge-green' : 'badge badge-yellow'">
                        {{ statusLabel(b.status) }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 开票信息 -->
          <div v-if="partnerName" class="border border-line rounded-xl p-3 mb-4">
            <div class="text-xs font-semibold text-secondary mb-2">
              {{ mode === 'sales' ? '购方' : '销方' }}开票信息
            </div>
            <div class="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[13px]">
              <div class="col-span-2">
                <span class="text-muted">名称：</span>{{ partnerName }}
              </div>
              <div class="col-span-2">
                <span class="text-muted">纳税人识别号：</span>
                <span class="font-mono">{{ partnerInfo.tax_id || '未填写' }}</span>
              </div>
              <div class="col-span-2">
                <span class="text-muted">地址电话：</span>
                {{ [partnerInfo.address, partnerInfo.phone].filter(Boolean).join(' ') || '未填写' }}
              </div>
              <div class="col-span-2">
                <span class="text-muted">开户行及账号：</span>
                {{ [partnerInfo.bank_name, partnerInfo.bank_account].filter(Boolean).join(' ') || '未填写' }}
              </div>
            </div>
          </div>

          <!-- 发票参数 -->
          <div class="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label for="ipm-invoice-type" class="label">发票类型</label>
              <select id="ipm-invoice-type" v-model="form.invoice_type" class="input text-sm">
                <option value="special">增值税专用发票</option>
                <option value="normal">增值税普通发票</option>
              </select>
            </div>
            <div>
              <label for="ipm-invoice-date" class="label">发票日期</label>
              <input id="ipm-invoice-date" v-model="form.invoice_date" type="date" class="input text-sm" />
            </div>
            <div>
              <label for="ipm-tax-rate" class="label">税率 (%)</label>
              <input id="ipm-tax-rate" v-model.number="form.tax_rate" type="number" step="0.01" min="0" max="100" class="input text-sm" />
            </div>
            <div>
              <label for="ipm-remark" class="label">备注</label>
              <input id="ipm-remark" v-model="form.remark" class="input text-sm" />
            </div>
          </div>

          <!-- 金额预览 -->
          <div class="bg-elevated rounded-xl p-3">
            <div class="text-[12px] font-semibold text-muted mb-2">发票金额预览</div>
            <div class="grid grid-cols-3 gap-2 text-[13px]">
              <div>不含税金额：<span class="font-medium">{{ fmtMoney(previewWithoutTax) }}</span></div>
              <div>税额：<span class="font-medium">{{ fmtMoney(previewTax) }}</span></div>
              <div>价税合计：<span class="font-medium">{{ fmtMoney(totalAmount) }}</span></div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="$emit('close')" class="btn btn-secondary btn-sm">取消</button>
          <button @click="handleSubmit" :disabled="submitting" class="btn btn-primary btn-sm">
            {{ submitting ? '推送中...' : '确认推送' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useFormat } from '../../composables/useFormat'
import { useAppStore } from '../../stores/app'

const props = defineProps({
  visible: { type: Boolean, default: false },
  mode: { type: String, default: 'sales' },       // 'sales' | 'purchase'
  bills: { type: Array, default: () => [] },       // 已选单据列表
  partnerName: { type: String, default: '' },      // 客户/供应商名称
  partnerInfo: { type: Object, default: () => ({}) }, // { tax_id, address, phone, bank_name, bank_account }
  pushFn: { type: Function, required: true },      // 实际推送的 API 函数
})

const emit = defineEmits(['close', 'success'])
const appStore = useAppStore()
const { fmtMoney } = useFormat()

const submitting = ref(false)
const form = ref({
  invoice_type: 'special',
  invoice_date: new Date().toISOString().slice(0, 10),
  tax_rate: 13,
  remark: '',
})

// 打开时重置表单
watch(() => props.visible, (val) => {
  if (val) {
    form.value = {
      invoice_type: 'special',
      invoice_date: new Date().toISOString().slice(0, 10),
      tax_rate: 13,
      remark: '',
    }
  }
})

const totalAmount = computed(() => {
  return props.bills.reduce((sum, b) => sum + (parseFloat(b.total_amount) || 0), 0)
})

const previewWithoutTax = computed(() => {
  const rate = form.value.tax_rate / 100
  return (totalAmount.value / (1 + rate)).toFixed(2)
})

const previewTax = computed(() => {
  return (totalAmount.value - parseFloat(previewWithoutTax.value)).toFixed(2)
})

function statusLabel(s) {
  if (props.mode === 'sales') {
    return { pending: '待收款', partial: '部分收款', completed: '已收齐', cancelled: '已取消' }[s] || s
  }
  return { pending: '待付款', partial: '部分付款', completed: '已付清', cancelled: '已取消' }[s] || s
}

async function handleSubmit() {
  if (submitting.value) return
  submitting.value = true
  try {
    await props.pushFn(form.value)
    appStore.showToast('发票推送成功', 'success')
    emit('success')
    emit('close')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '推送失败', 'error')
  } finally {
    submitting.value = false
  }
}
</script>
