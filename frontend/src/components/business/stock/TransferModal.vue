<!--
  库存调拨弹窗
  展示调出源信息，选择调入目标仓库/仓位，填写调拨数量
-->
<template>
  <teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal">
        <!-- 标题栏 -->
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">调拨 - {{ product?.sku }}</h3>
          <button @click="close" class="modal-close">&times;</button>
        </div>
        <!-- 表单 -->
        <div class="p-4">
          <form @submit.prevent="handleSave" class="space-y-4">
            <!-- 商品信息 -->
            <div class="p-4 bg-info-subtle border border-primary rounded-lg">
              <div class="text-xs text-primary font-semibold mb-1">调拨商品</div>
              <div class="font-medium text-foreground">{{ productLabel }}</div>
            </div>
            <div class="grid form-grid grid-cols-2 gap-4">
              <!-- 调出信息（只读） -->
              <div class="p-4 bg-error-subtle border-2 border-error rounded-lg">
                <div class="text-sm text-error font-bold mb-3 flex items-center">
                  <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v3.586L7.707 9.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 10.586V7z" clip-rule="evenodd"/></svg>
                  调出
                </div>
                <div class="space-y-2 text-sm">
                  <div><span class="text-muted">仓库：</span><span class="font-medium text-foreground">{{ fromWarehouseName }}</span></div>
                  <div><span class="text-muted">仓位：</span><span class="font-medium text-foreground">{{ fromLocationCode }}</span></div>
                  <div class="pt-2 border-t border-error"><span class="text-muted">可用库存：</span><span class="text-lg font-bold text-error">{{ sourceQty }}</span></div>
                </div>
              </div>
              <!-- 调入信息（可编辑） -->
              <div class="p-4 bg-success-subtle border-2 border-success rounded-lg">
                <div class="text-sm text-success font-bold mb-3 flex items-center">
                  <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v3.586L7.707 9.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 10.586V7z" clip-rule="evenodd"/></svg>
                  调入
                </div>
                <div class="space-y-2">
                  <div>
                    <label class="block text-xs text-secondary mb-1">目标仓库 *</label>
                    <select v-model="form.to_warehouse_id" class="input" required>
                      <option value="">请选择</option>
                      <option
                        v-for="w in warehouses.filter(x => !x.is_virtual)"
                        :key="w.id"
                        :value="w.id"
                      >{{ w.name }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-xs text-secondary mb-1">目标仓位 *</label>
                    <select v-model="form.to_location_id" class="input" required :disabled="!form.to_warehouse_id">
                      <option value="">{{ form.to_warehouse_id ? '请选择' : '请先选择仓库' }}</option>
                      <option v-for="loc in transferToLocations" :key="loc.id" :value="loc.id">{{ loc.code }}</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
            <!-- 调拨数量 -->
            <div>
              <label class="label">调拨数量 *</label>
              <input
                v-model.number="form.quantity"
                type="number"
                class="input text-lg font-semibold"
                required min="1"
                :max="sourceQty || 999999"
                placeholder="输入数量"
              >
            </div>
            <!-- 备注 -->
            <div>
              <label class="label">备注</label>
              <input v-model="form.remark" class="input" placeholder="选填，可备注调拨原因">
            </div>
            <!-- 按钮 -->
            <div class="flex gap-3 pt-2">
              <button type="button" @click="close" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-primary flex-1 font-semibold">确认调拨</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 库存调拨弹窗组件
 * 通过 props 接收要调拨的商品和源库存信息
 * 内部管理目标仓库/仓位选择和调拨数量
 */
import { reactive, computed, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useWarehousesStore } from '../../../stores/warehouses'
import { transfer as apiTransfer } from '../../../api/stock'

const props = defineProps({
  /** 是否显示弹窗 */
  visible: Boolean,
  /** 要调拨的商品对象 */
  product: { type: Object, default: null },
  /** 源库存信息（包含 warehouse_id, location_id, quantity, reserved_qty, available_qty） */
  fromStock: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'saved'])

const appStore = useAppStore()
const warehousesStore = useWarehousesStore()

const warehouses = computed(() => warehousesStore.warehouses)
const locations = computed(() => warehousesStore.locations)

// 调拨表单（仅目标端可编辑）
const form = reactive({
  to_warehouse_id: '', to_location_id: '',
  quantity: 1, remark: '',
})

/** 商品显示标签 */
const productLabel = computed(() =>
  props.product ? `${props.product.sku} - ${props.product.name}` : ''
)

/** 源仓库名称 */
const fromWarehouseName = computed(() => {
  if (!props.fromStock) return ''
  return warehouses.value.find(w => w.id === props.fromStock.warehouse_id)?.name || ''
})

/** 源仓位编码 */
const fromLocationCode = computed(() => {
  if (!props.fromStock) return ''
  return locations.value.find(l => l.id === props.fromStock.location_id)?.code || ''
})

/** 源可用库存 */
const sourceQty = computed(() => {
  if (!props.fromStock) return 0
  return props.fromStock.available_qty ?? (props.fromStock.quantity - (props.fromStock.reserved_qty || 0))
})

/** 目标仓库下的仓位列表 */
const transferToLocations = computed(() => {
  if (!form.to_warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(form.to_warehouse_id)
})

/** 目标仓库变更时重置仓位 */
watch(() => form.to_warehouse_id, () => { form.to_location_id = '' })

/** 弹窗打开时重置目标表单 */
watch(() => props.visible, (val) => {
  if (!val) return
  Object.assign(form, {
    to_warehouse_id: '', to_location_id: '',
    quantity: 1, remark: '',
  })
})

/** 关闭弹窗 */
const close = () => emit('update:visible', false)

/** 提交调拨 */
const handleSave = async () => {
  if (!props.product || !props.fromStock) return
  if (!form.to_warehouse_id || !form.to_location_id || !form.quantity) {
    appStore.showToast('请填写完整信息', 'error'); return
  }
  if (props.fromStock.warehouse_id === parseInt(form.to_warehouse_id) &&
      props.fromStock.location_id === parseInt(form.to_location_id)) {
    appStore.showToast('源和目标位置不能相同', 'error'); return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await apiTransfer({
      product_id: parseInt(props.product.id),
      from_warehouse_id: parseInt(props.fromStock.warehouse_id),
      from_location_id: parseInt(props.fromStock.location_id),
      to_warehouse_id: parseInt(form.to_warehouse_id),
      to_location_id: parseInt(form.to_location_id),
      quantity: parseInt(form.quantity),
      remark: form.remark || null,
    })
    appStore.showToast('调拨成功')
    close()
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '调拨失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
