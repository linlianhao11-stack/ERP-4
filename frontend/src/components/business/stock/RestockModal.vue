<!--
  入库弹窗
  支持选择仓库/仓位/商品、填写数量/成本、SN码管理
-->
<template>
  <teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal">
        <!-- 标题栏 -->
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">入库</h3>
          <button @click="close" class="modal-close">&times;</button>
        </div>
        <!-- 表单 -->
        <div class="p-4">
          <form @submit.prevent="handleSave" class="space-y-3">
            <!-- 仓库选择 -->
            <div>
              <label class="label">仓库 *</label>
              <select v-model="form.warehouse_id" @change="checkSnRequired" class="input" required>
                <option value="">选择仓库</option>
                <option
                  v-for="w in warehouses.filter(x => !x.is_virtual)"
                  :key="w.id"
                  :value="w.id"
                >{{ w.name }}</option>
              </select>
            </div>
            <!-- 仓位选择 -->
            <div>
              <label class="label">仓位 *</label>
              <select v-model="form.location_id" class="input" required :disabled="!form.warehouse_id">
                <option value="">{{ form.warehouse_id ? '选择仓位' : '请先选择仓库' }}</option>
                <option v-for="loc in restockLocations" :key="loc.id" :value="loc.id">
                  {{ loc.code }}{{ loc.name ? ' - ' + loc.name : '' }}
                </option>
              </select>
            </div>
            <!-- 商品选择 -->
            <div>
              <label class="label">商品 *</label>
              <select v-model="form.product_id" @change="checkSnRequired" class="input" required>
                <option value="">选择商品</option>
                <option v-for="p in products" :key="p.id" :value="p.id">{{ p.sku }} - {{ p.name }}</option>
              </select>
            </div>
            <!-- 数量和成本 -->
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">数量 *</label>
                <input v-model.number="form.quantity" type="number" class="input" required min="1">
              </div>
              <div>
                <label class="label">入库成本(本批次)</label>
                <input v-model.number="form.cost_price" type="number" step="0.01" class="input" placeholder="不填则用上次成本">
              </div>
            </div>
            <!-- 备注 -->
            <div>
              <label class="label">备注</label>
              <input v-model="form.remark" class="input">
            </div>
            <!-- SN码区域 -->
            <div v-if="form.sn_required" class="bg-warning-subtle border border-warning rounded-lg p-3">
              <label class="label">
                SN码 *
                <span
                  class="font-normal text-xs"
                  :class="parsedSnCount === parseInt(form.quantity || 0) ? 'text-success' : 'text-error'"
                >
                  (已输入 {{ parsedSnCount }} / 需要 {{ form.quantity || 0 }})
                </span>
              </label>
              <textarea
                v-model="form.sn_input"
                class="input text-sm"
                rows="3"
                placeholder="每行一个SN码，或用逗号/空格分隔"
              ></textarea>
            </div>
            <!-- 按钮 -->
            <div class="flex gap-3 pt-3">
              <button type="button" @click="close" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-primary flex-1">确认入库</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 入库弹窗组件
 * 内部管理表单状态，从 store 获取仓库/商品数据
 * 支持 SN码 检查与解析
 */
import { reactive, computed, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useProductsStore } from '../../../stores/products'
import { useWarehousesStore } from '../../../stores/warehouses'
import { restock as apiRestock } from '../../../api/stock'
import { checkSnRequired as apiCheckSnRequired } from '../../../api/sn'
import { parseSnCodes } from '../../../utils/helpers'

const props = defineProps({
  /** 是否显示弹窗 */
  visible: Boolean,
})

const emit = defineEmits(['update:visible', 'saved'])

const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()

// 从 store 获取数据
const products = computed(() => productsStore.products)
const warehouses = computed(() => warehousesStore.warehouses)

// 表单数据
const form = reactive({
  warehouse_id: '', location_id: '', product_id: '',
  quantity: 1, cost_price: null, remark: '',
  sn_required: false, sn_input: '',
})

/** 当前仓库下的仓位列表 */
const restockLocations = computed(() => {
  if (!form.warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(form.warehouse_id)
})

/** 已解析的SN码数量 */
const parsedSnCount = computed(() => parseSnCodes(form.sn_input).length)

/** 仓库变更时重置仓位 */
watch(() => form.warehouse_id, () => { form.location_id = '' })

/** 弹窗打开时重置表单 */
watch(() => props.visible, (val) => {
  if (!val) return
  Object.assign(form, {
    warehouse_id: '', location_id: '', product_id: '',
    quantity: 1, cost_price: null, remark: '',
    sn_required: false, sn_input: '',
  })
})

/** 关闭弹窗 */
const close = () => emit('update:visible', false)

/** 检查是否需要SN码（仓库+商品选定后触发） */
const checkSnRequired = async () => {
  if (!form.warehouse_id || !form.product_id) {
    form.sn_required = false
    form.sn_input = ''
    return
  }
  try {
    const { data } = await apiCheckSnRequired({
      warehouse_id: form.warehouse_id,
      product_id: form.product_id,
    })
    form.sn_required = data.required
    if (!data.required) form.sn_input = ''
  } catch (e) {
    form.sn_required = false
  }
}

/** 提交入库 */
const handleSave = async () => {
  if (!form.warehouse_id || !form.location_id || !form.product_id || !form.quantity) {
    appStore.showToast('请填写完整信息', 'error'); return
  }
  if (parseInt(form.quantity) <= 0) {
    appStore.showToast('入库数量必须大于0', 'error'); return
  }
  if (form.cost_price != null && form.cost_price !== '' && Number(form.cost_price) < 0) {
    appStore.showToast('成本价不能为负数', 'error'); return
  }
  if (appStore.submitting) return

  // SN码校验
  const snList = form.sn_required ? parseSnCodes(form.sn_input) : null
  if (form.sn_required) {
    if (!snList || snList.length === 0) {
      appStore.showToast('该仓库+品牌已启用SN管理，请填写SN码', 'error'); return
    }
    if (snList.length !== parseInt(form.quantity)) {
      appStore.showToast(`SN码数量(${snList.length})与入库数量(${form.quantity})不匹配`, 'error'); return
    }
  }

  appStore.submitting = true
  try {
    await apiRestock({
      warehouse_id: parseInt(form.warehouse_id),
      location_id: parseInt(form.location_id),
      product_id: parseInt(form.product_id),
      quantity: parseInt(form.quantity),
      cost_price: form.cost_price || null,
      remark: form.remark || null,
      sn_codes: snList || null,
    })
    appStore.showToast('入库成功')
    close()
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '入库失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
