<!--
  新增样机弹窗
  支持两种来源：从库存转入 / 新采购入库
  仓库-仓位联动选择 + 可用库存展示
-->
<template>
  <AppModal :visible="visible" title="新增样机" width="640px" @close="$emit('close')">
    <div class="space-y-4">

      <!-- 来源选择 -->
      <div>
        <label class="label">来源方式</label>
        <div class="flex items-center gap-4 mt-1">
          <label class="flex items-center gap-1.5 cursor-pointer text-sm">
            <input type="radio" v-model="form.source" value="stock_transfer" class="w-4 h-4"> 从库存转入
          </label>
          <label class="flex items-center gap-1.5 cursor-pointer text-sm">
            <input type="radio" v-model="form.source" value="new_purchase" class="w-4 h-4"> 新采购入库
          </label>
        </div>
      </div>

      <!-- 产品选择 -->
      <div class="relative">
        <label class="label" for="demo-product-search">产品 *</label>
        <input
          id="demo-product-search"
          v-model="productSearch"
          @input="productDropdown = true"
          @focus="productDropdown = true"
          @blur="hideProductDropdown"
          class="input text-sm"
          placeholder="输入产品名称搜索..."
          autocomplete="off"
        >
        <div v-if="productDropdown && filteredProducts.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
          <div
            v-for="p in filteredProducts"
            :key="p.id"
            @mousedown.prevent="selectProduct(p)"
            class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm"
          >
            {{ p.name }}
            <span v-if="p.sku" class="text-muted text-xs ml-1">({{ p.sku }})</span>
          </div>
        </div>
      </div>

      <!-- 源仓库 + 仓位（仅库存转入） -->
      <template v-if="form.source === 'stock_transfer'">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="label" for="demo-source-wh">源仓库 *</label>
            <select id="demo-source-wh" v-model="form.source_warehouse_id" class="input text-sm">
              <option :value="null">请选择源仓库</option>
              <option v-for="w in sourceWarehouseOptions" :key="w.id" :value="w.id">
                {{ w.label }}
              </option>
            </select>
          </div>
          <div>
            <label class="label" for="demo-source-loc">源仓位</label>
            <select
              id="demo-source-loc"
              v-model="form.source_location_id"
              class="input text-sm"
              :disabled="!form.source_warehouse_id"
            >
              <option :value="null">{{ form.source_warehouse_id ? '默认仓位' : '请先选仓库' }}</option>
              <option v-for="loc in sourceLocationOptions" :key="loc.id" :value="loc.id">
                {{ loc.label }}
              </option>
            </select>
          </div>
        </div>
      </template>

      <!-- SN码 -->
      <div>
        <label class="label" for="demo-sn">SN码 *</label>
        <input
          id="demo-sn"
          v-model="form.sn_code"
          class="input text-sm"
          placeholder="输入SN码"
        >
      </div>

      <!-- 目标样机仓库 + 仓位 -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="label" for="demo-target-wh">样机仓库 *</label>
          <select id="demo-target-wh" v-model="form.warehouse_id" class="input text-sm">
            <option :value="null">请选择样机仓库</option>
            <option v-for="w in warehouses" :key="w.id" :value="w.id">{{ w.name }}</option>
          </select>
        </div>
        <div>
          <label class="label" for="demo-target-loc">样机仓位</label>
          <select
            id="demo-target-loc"
            v-model="form.location_id"
            class="input text-sm"
            :disabled="!form.warehouse_id"
          >
            <option :value="null">{{ form.warehouse_id ? '默认仓位' : '请先选仓库' }}</option>
            <option v-for="loc in targetLocations" :key="loc.id" :value="loc.id">
              {{ loc.code }}{{ loc.name ? ' - ' + loc.name : '' }}
            </option>
          </select>
        </div>
      </div>

      <!-- 成色 -->
      <div>
        <label class="label" for="demo-condition">成色 *</label>
        <select id="demo-condition" v-model="form.condition" class="input text-sm">
          <option value="new">全新</option>
          <option value="good">良好</option>
          <option value="fair">一般</option>
          <option value="poor">较差</option>
        </select>
      </div>

      <!-- 成本价（仅新采购） -->
      <div v-if="form.source === 'new_purchase'">
        <label class="label" for="demo-cost">成本价</label>
        <input
          id="demo-cost"
          v-model.number="form.cost_price"
          type="number"
          step="0.01"
          min="0"
          class="input text-sm"
          placeholder="0.00"
        >
      </div>

      <!-- 备注 -->
      <div>
        <label class="label" for="demo-notes">备注</label>
        <textarea
          id="demo-notes"
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
          {{ appStore.submitting ? '提交中...' : '确认' }}
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import AppModal from '../../common/AppModal.vue'
import { useAppStore } from '../../../stores/app'
import { useWarehousesStore } from '../../../stores/warehouses'
import { createDemoUnit } from '../../../api/demo'
import { getProducts } from '../../../api/products'

const props = defineProps({
  visible: Boolean,
})
const emit = defineEmits(['close', 'saved'])
const appStore = useAppStore()
const warehousesStore = useWarehousesStore()

// 产品列表（带库存信息）
const products = ref([])
const productSearch = ref('')
const productDropdown = ref(false)
let _blurTimer = null
const hideProductDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { productDropdown.value = false }, 200)
}
onUnmounted(() => clearTimeout(_blurTimer))

// 从 store 获取仓库列表
const warehouses = computed(() => warehousesStore.warehouses)

// 表单
const form = reactive({
  source: 'stock_transfer',
  product_id: null,
  sn_code: '',
  source_warehouse_id: null,
  source_location_id: null,
  warehouse_id: null,
  location_id: null,
  condition: 'new',
  cost_price: null,
  notes: '',
})

// ── 仓位联动 ──

const sourceLocations = computed(() =>
  warehousesStore.getLocationsByWarehouse(form.source_warehouse_id)
)

const targetLocations = computed(() =>
  warehousesStore.getLocationsByWarehouse(form.warehouse_id)
)

// 切换源仓库时重置仓位
watch(() => form.source_warehouse_id, () => {
  form.source_location_id = null
})

// 切换目标仓库时重置仓位
watch(() => form.warehouse_id, () => {
  form.location_id = null
})

// ── 库存计算（内聚到下拉选项） ──

const selectedProduct = computed(() =>
  products.value.find(p => p.id === form.product_id)
)

/** 计算某仓库对当前产品的可用库存合计 */
const getWarehouseQty = (warehouseId) => {
  const stocks = selectedProduct.value?.stocks
  if (!stocks) return 0
  return stocks
    .filter(s => s.warehouse_id === warehouseId)
    .reduce((sum, s) => sum + (s.available_qty ?? s.quantity ?? 0), 0)
}

/** 计算某仓位对当前产品的可用库存 */
const getLocationQty = (warehouseId, locationId) => {
  const stocks = selectedProduct.value?.stocks
  if (!stocks) return 0
  const s = stocks.find(s => s.warehouse_id === warehouseId && s.location_id === locationId)
  return s ? (s.available_qty ?? s.quantity ?? 0) : 0
}

/** 源仓库下拉选项：仓库名 + 可用库存 */
const sourceWarehouseOptions = computed(() =>
  warehouses.value.map(w => {
    const qty = form.product_id ? getWarehouseQty(w.id) : null
    const suffix = qty !== null ? `，可用库存：${qty}台` : ''
    return { id: w.id, label: `${w.name}${suffix}` }
  })
)

/** 源仓位下拉选项：仓位编码 + 可用库存 */
const sourceLocationOptions = computed(() =>
  sourceLocations.value.map(loc => {
    const qty = form.product_id ? getLocationQty(form.source_warehouse_id, loc.id) : null
    const name = loc.code + (loc.name ? ' - ' + loc.name : '')
    const suffix = qty !== null ? `，可用库存：${qty}台` : ''
    return { id: loc.id, label: `${name}${suffix}` }
  })
)

/** 当前选中的源仓库可用库存（用于校验） */
const sourceAvailableQty = computed(() => {
  if (!form.product_id || !form.source_warehouse_id) return 0
  if (form.source_location_id) {
    return getLocationQty(form.source_warehouse_id, form.source_location_id)
  }
  return getWarehouseQty(form.source_warehouse_id)
})

// ── 产品搜索 ──

const filteredProducts = computed(() => {
  const q = productSearch.value.trim().toLowerCase()
  if (!q) return products.value.slice(0, 20)
  return products.value.filter(p =>
    p.name.toLowerCase().includes(q) ||
    (p.sku && p.sku.toLowerCase().includes(q))
  ).slice(0, 20)
})

const selectProduct = (p) => {
  form.product_id = p.id
  productSearch.value = p.name
  productDropdown.value = false
}

// ── 加载数据 ──

const loadProducts = async () => {
  try {
    // has_stock=false 获取全部产品（含库存信息）
    const { data } = await getProducts({ page_size: 500 })
    products.value = data.items || data || []
  } catch (e) {
    console.error('加载产品失败:', e)
  }
}

// ── 重置表单 ──

const resetForm = () => {
  Object.assign(form, {
    source: 'stock_transfer',
    product_id: null,
    sn_code: '',
    source_warehouse_id: null,
    source_location_id: null,
    warehouse_id: null,
    location_id: null,
    condition: 'new',
    cost_price: null,
    notes: '',
  })
  productSearch.value = ''
}

// 打开弹窗时重置
watch(() => props.visible, (val) => {
  if (val) {
    resetForm()
  }
})

// ── 校验 ──

const validate = () => {
  if (!form.product_id) {
    appStore.showToast('请选择产品', 'error')
    return false
  }
  if (!form.sn_code?.trim()) {
    appStore.showToast('请输入SN码', 'error')
    return false
  }
  if (!form.warehouse_id) {
    appStore.showToast('请选择样机仓库', 'error')
    return false
  }
  if (form.source === 'stock_transfer' && !form.source_warehouse_id) {
    appStore.showToast('请选择源仓库', 'error')
    return false
  }
  if (form.source === 'stock_transfer' && sourceAvailableQty.value < 1) {
    appStore.showToast('源仓库可用库存不足', 'error')
    return false
  }
  return true
}

// ── 提交 ──

const handleSubmit = async () => {
  if (!validate()) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const payload = {
      source: form.source,
      product_id: form.product_id,
      sn_code: form.sn_code.trim(),
      warehouse_id: form.warehouse_id,
      location_id: form.location_id || null,
      condition: form.condition,
      notes: form.notes || null,
    }
    if (form.source === 'stock_transfer') {
      payload.source_warehouse_id = form.source_warehouse_id
      payload.source_location_id = form.source_location_id || null
    }
    if (form.source === 'new_purchase' && form.cost_price) {
      payload.cost_price = form.cost_price
    }
    await createDemoUnit(payload)
    appStore.showToast('样机创建成功')
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

onMounted(async () => {
  await warehousesStore.ensureLoaded()
  loadProducts()
})
</script>
