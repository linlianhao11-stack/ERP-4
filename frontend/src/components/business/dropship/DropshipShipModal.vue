<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('update:visible', false)">
    <div class="modal-content" style="max-width:520px">
      <div class="modal-header">
        <h3 class="modal-title">确认发货</h3>
        <button @click="$emit('update:visible', false)" class="modal-close">&times;</button>
      </div>
      <div class="modal-body">
        <div class="space-y-4">
          <!-- 订单摘要 -->
          <div class="bg-elevated rounded-lg p-3 text-sm">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-mono font-semibold">{{ order?.ds_no }}</span>
            </div>
            <div class="text-muted">{{ order?.product_name }}</div>
            <div class="text-muted text-xs mt-1">
              {{ order?.supplier_name }} → {{ order?.customer_name }}
            </div>
          </div>
          <!-- 快递公司 -->
          <div>
            <label class="label" for="ship-carrier">快递公司 *</label>
            <select id="ship-carrier" v-model="form.carrier_code" class="input">
              <option value="" disabled>请选择快递公司</option>
              <option v-for="c in CARRIERS" :key="c.code" :value="c.code">{{ c.name }}</option>
            </select>
          </div>
          <!-- 快递单号 -->
          <div>
            <label class="label" for="ship-tracking">快递单号 *</label>
            <input id="ship-tracking" v-model="form.tracking_no" class="input" placeholder="输入快递单号">
          </div>
          <!-- 手机号（顺丰/中通需要） -->
          <div v-if="needPhone">
            <label class="label" for="ship-phone">手机号后四位</label>
            <input id="ship-phone" v-model="form.phone" class="input" placeholder="收/寄件人手机号后四位（用于物流查询）" maxlength="4">
            <p class="text-xs text-muted mt-1">{{ carrierName }}查询物流需要手机号后四位</p>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" @click="$emit('update:visible', false)" class="btn btn-sm btn-secondary">取消</button>
        <button type="button" @click="handleShip" class="btn btn-sm btn-primary"
          :disabled="submitting || !form.carrier_code || !form.tracking_no.trim()">
          {{ submitting ? '发货中...' : '确认发货' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, computed, watch } from 'vue'
import { CARRIERS, PHONE_REQUIRED_CARRIERS } from '../../../constants/carriers'
import { shipDropshipOrder } from '../../../api/dropship'
import { useAppStore } from '../../../stores/app'

const props = defineProps({
  visible: Boolean,
  order: Object,
})
const emit = defineEmits(['update:visible', 'shipped'])

const appStore = useAppStore()
const submitting = computed(() => appStore.submitting)

const form = reactive({
  carrier_code: '',
  tracking_no: '',
  phone: '',
})

const needPhone = computed(() => PHONE_REQUIRED_CARRIERS.has(form.carrier_code))
const carrierName = computed(() => CARRIERS.find(c => c.code === form.carrier_code)?.name || '')

// 弹窗打开时重置表单
watch(() => props.visible, (v) => {
  if (v) {
    form.carrier_code = ''
    form.tracking_no = ''
    form.phone = ''
  }
})

const handleShip = async () => {
  if (!form.carrier_code || !form.tracking_no.trim()) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const selectedCarrier = CARRIERS.find(c => c.code === form.carrier_code)
    await shipDropshipOrder(props.order.id, {
      carrier_code: form.carrier_code,
      carrier_name: selectedCarrier?.name || '',
      tracking_no: form.tracking_no.trim(),
      phone: form.phone.trim() || null,
    })
    appStore.showToast('发货成功')
    emit('update:visible', false)
    emit('shipped')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '发货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
