<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('update:visible', false)">
    <div class="modal-content" style="max-width:640px">
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
            <label class="label">快递公司 *</label>
            <SearchableSelect
              v-model="form.carrier_code"
              :options="carrierOptions"
              placeholder="请选择快递公司"
              search-placeholder="搜索快递公司..."
            />
          </div>
          <!-- 无物流提示 -->
          <div v-if="isNoLogistics" class="text-sm text-success font-semibold">
            {{ noLogisticsHint }}
          </div>
          <!-- 快递单号（非自提/自配送时显示） -->
          <div v-if="!isNoLogistics">
            <label class="label">快递单号 *</label>
            <input v-model="form.tracking_no" class="input" placeholder="输入快递单号">
          </div>
          <!-- 手机号（顺丰/中通需要） -->
          <div v-if="!isNoLogistics && needPhone">
            <label class="label">
              手机号后四位
              <span class="text-warning font-normal">（{{ carrierName }}必填）</span>
            </label>
            <input v-model="form.phone" class="input" placeholder="收/寄件人手机号后四位（用于物流查询）" maxlength="11">
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" @click="$emit('update:visible', false)" class="btn btn-sm btn-secondary">取消</button>
        <button type="button" @click="handleShip" class="btn btn-sm btn-primary"
          :disabled="submitting || !form.carrier_code || (!isNoLogistics && !form.tracking_no.trim())">
          {{ submitting ? '发货中...' : shipBtnText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { PHONE_REQUIRED_CARRIERS, isNoLogisticsCode, noLogisticsHint as getNoLogisticsHint, shipActionText } from '../../../constants/carriers'
import { getCarriers } from '../../../api/logistics'
import { shipDropshipOrder } from '../../../api/dropship'
import { useAppStore } from '../../../stores/app'
import SearchableSelect from '../../common/SearchableSelect.vue'

const props = defineProps({
  visible: Boolean,
  order: Object,
})
const emit = defineEmits(['update:visible', 'shipped'])

const appStore = useAppStore()
const submitting = computed(() => appStore.submitting)

const carriers = ref([])
const form = reactive({
  carrier_code: '',
  tracking_no: '',
  phone: '',
})

/** 快递公司列表转 SearchableSelect 格式 */
const carrierOptions = computed(() =>
  carriers.value.map(c => ({ id: c.code, label: c.name }))
)

const isNoLogistics = computed(() => isNoLogisticsCode(form.carrier_code))
const needPhone = computed(() => PHONE_REQUIRED_CARRIERS.has(form.carrier_code))
const carrierName = computed(() => carriers.value.find(c => c.code === form.carrier_code)?.name || '')
const noLogisticsHint = computed(() => getNoLogisticsHint(form.carrier_code))
const shipBtnText = computed(() => shipActionText(form.carrier_code))

/** 加载快递公司列表 */
const loadCarriers = async () => {
  try {
    const { data } = await getCarriers()
    carriers.value = data
  } catch (e) {
    console.error(e)
  }
}

// 弹窗打开时重置表单 + 加载快递公司
watch(() => props.visible, (v) => {
  if (v) {
    form.carrier_code = ''
    form.tracking_no = ''
    form.phone = ''
    if (!carriers.value.length) loadCarriers()
  }
})

const handleShip = async () => {
  if (!form.carrier_code) return
  if (!isNoLogistics.value && !form.tracking_no.trim()) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const selectedCarrier = carriers.value.find(c => c.code === form.carrier_code)
    await shipDropshipOrder(props.order.id, {
      carrier_code: form.carrier_code,
      carrier_name: selectedCarrier?.name || '',
      tracking_no: isNoLogistics.value ? null : form.tracking_no.trim(),
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
