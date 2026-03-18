<!--
  归还弹窗
  显示借出信息 + 归还成色 + 备注
-->
<template>
  <AppModal :visible="visible" title="归还样机" width="480px" @close="$emit('close')">
    <div class="space-y-4">

      <!-- 借出信息 -->
      <div v-if="unit" class="card p-3 space-y-1 text-sm">
        <div class="flex justify-between">
          <span class="text-muted">样机编号</span>
          <span class="font-mono">{{ unit.code }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-muted">产品</span>
          <span>{{ unit.product_name }}</span>
        </div>
        <div v-if="unit.current_holder_name" class="flex justify-between">
          <span class="text-muted">当前持有人</span>
          <span>{{ unit.current_holder_name }}</span>
        </div>
        <div v-if="unit.current_loan_date" class="flex justify-between">
          <span class="text-muted">借出日期</span>
          <span>{{ unit.current_loan_date }}</span>
        </div>
        <div v-if="unit.days_borrowed != null" class="flex justify-between">
          <span class="text-muted">已借天数</span>
          <span :class="unit.is_overdue ? 'text-error font-semibold' : ''">{{ unit.days_borrowed }} 天</span>
        </div>
      </div>

      <!-- 归还成色 -->
      <div>
        <label class="label" for="return-condition">归还成色 *</label>
        <select id="return-condition" v-model="form.condition_on_return" class="input text-sm">
          <option value="new">全新</option>
          <option value="good">良好</option>
          <option value="fair">一般</option>
          <option value="poor">较差</option>
        </select>
      </div>

      <!-- 备注 -->
      <div>
        <label class="label" for="return-notes">归还备注</label>
        <textarea
          id="return-notes"
          v-model="form.notes"
          class="input text-sm"
          rows="2"
          placeholder="可选"
        ></textarea>
      </div>

    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-3">
        <button type="button" class="btn btn-secondary btn-sm" @click="$emit('close')">取消</button>
        <button type="button" class="btn btn-primary btn-sm" :disabled="appStore.submitting" @click="handleSubmit">
          {{ appStore.submitting ? '提交中...' : '确认归还' }}
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { reactive, watch } from 'vue'
import AppModal from '../../common/AppModal.vue'
import { useAppStore } from '../../../stores/app'
import { returnDemoLoan } from '../../../api/demo'

const props = defineProps({
  visible: Boolean,
  unit: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])
const appStore = useAppStore()

const form = reactive({
  condition_on_return: 'good',
  notes: '',
})

// 打开时重置
watch(() => props.visible, (val) => {
  if (val) {
    form.condition_on_return = props.unit?.condition || 'good'
    form.notes = ''
  }
})

const handleSubmit = async () => {
  if (!props.unit?.id && !props.unit?.current_loan_id) {
    appStore.showToast('缺少借出记录信息', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const loanId = props.unit.current_loan_id || props.unit.id
    await returnDemoLoan(loanId, {
      condition_on_return: form.condition_on_return,
      notes: form.notes || null,
    })
    appStore.showToast('归还成功')
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '归还失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
