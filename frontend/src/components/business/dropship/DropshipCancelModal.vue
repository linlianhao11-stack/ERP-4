<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('update:visible', false)">
    <div class="modal-content" style="max-width:480px">
      <div class="modal-header">
        <h3 class="modal-title">取消订单</h3>
        <button @click="$emit('update:visible', false)" class="modal-close">&times;</button>
      </div>
      <div class="modal-body">
        <div class="space-y-4">
          <div class="bg-elevated rounded-lg p-3 text-sm">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-mono font-semibold">{{ order?.ds_no }}</span>
              <StatusBadge type="dropshipStatus" :status="order?.status" />
            </div>
            <div class="text-muted">{{ order?.product_name }}</div>
            <div class="text-muted text-xs mt-1">
              {{ order?.supplier_name }} → {{ order?.customer_name }}
            </div>
          </div>
          <div>
            <label class="label" for="cancel-reason">取消原因（可选）</label>
            <textarea id="cancel-reason" v-model="reason" class="input" rows="3" placeholder="请输入取消原因..."></textarea>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" @click="$emit('update:visible', false)" class="btn btn-sm btn-secondary">返回</button>
        <button type="button" @click="handleCancel" class="btn btn-sm btn-danger" :disabled="submitting">
          {{ submitting ? '取消中...' : '确认取消' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import StatusBadge from '../../common/StatusBadge.vue'
import { cancelDropshipOrder } from '../../../api/dropship'
import { useAppStore } from '../../../stores/app'

const props = defineProps({
  visible: Boolean,
  order: Object,
})
const emit = defineEmits(['update:visible', 'cancelled'])

const appStore = useAppStore()
const submitting = computed(() => appStore.submitting)
const reason = ref('')

watch(() => props.visible, (v) => {
  if (v) reason.value = ''
})

const handleCancel = async () => {
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await cancelDropshipOrder(props.order.id, {
      reason: reason.value.trim() || null,
    })
    appStore.showToast('订单已取消')
    emit('update:visible', false)
    emit('cancelled')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '取消失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
