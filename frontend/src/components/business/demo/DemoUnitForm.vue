<!--
  新增样机弹窗
  支持两种来源：从库存转入 / 新采购入库
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

      <!-- SN码 -->
      <div>
        <label class="label" for="demo-sn">SN码</label>
        <input
          id="demo-sn"
          v-model="form.sn_code"
          class="input text-sm"
          placeholder="输入SN码（可选）"
        >
      </div>

      <!-- 源仓库（仅库存转入） -->
      <div v-if="form.source === 'stock_transfer'">
        <label class="label" for="demo-source-wh">源仓库 *</label>
        <select id="demo-source-wh" v-model="form.source_warehouse_id" class="input text-sm">
          <option :value="null">请选择源仓库</option>
          <option v-for="w in warehouses" :key="w.id" :value="w.id">{{ w.name }}</option>
        </select>
      </div>

      <!-- 目标样机仓库 -->
      <div>
        <label class="label" for="demo-target-wh">样机仓库 *</label>
        <select id="demo-target-wh" v-model="form.target_warehouse_id" class="input text-sm">
          <option :value="null">请选择样机仓库</option>
          <option v-for="w in warehouses" :key="w.id" :value="w.id">{{ w.name }}</option>
        </select>
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
import { createDemoUnit } from '../../../api/demo'
import { getProducts } from '../../../api/products'
import { getWarehouses } from '../../../api/warehouses'

const props = defineProps({
  visible: Boolean,
})
const emit = defineEmits(['close', 'saved'])
const appStore = useAppStore()

// 产品列表
const products = ref([])
const productSearch = ref('')
const productDropdown = ref(false)
let _blurTimer = null
const hideProductDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { productDropdown.value = false }, 200)
}
onUnmounted(() => clearTimeout(_blurTimer))

// 仓库列表
const warehouses = ref([])

// 表单
const form = reactive({
  source: 'stock_transfer',
  product_id: null,
  sn_code: '',
  source_warehouse_id: null,
  target_warehouse_id: null,
  condition: 'new',
  cost_price: null,
  notes: '',
})

// 产品搜索过滤
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

// 加载数据
const loadProducts = async () => {
  try {
    const { data } = await getProducts({ page_size: 500 })
    products.value = data.items || data || []
  } catch (e) {
    console.error('加载产品失败:', e)
  }
}

const loadWarehouses = async () => {
  try {
    const { data } = await getWarehouses()
    warehouses.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载仓库失败:', e)
  }
}

// 重置表单
const resetForm = () => {
  Object.assign(form, {
    source: 'stock_transfer',
    product_id: null,
    sn_code: '',
    source_warehouse_id: null,
    target_warehouse_id: null,
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

// 校验
const validate = () => {
  if (!form.product_id) {
    appStore.showToast('请选择产品', 'error')
    return false
  }
  if (!form.target_warehouse_id) {
    appStore.showToast('请选择样机仓库', 'error')
    return false
  }
  if (form.source === 'stock_transfer' && !form.source_warehouse_id) {
    appStore.showToast('请选择源仓库', 'error')
    return false
  }
  return true
}

// 提交
const handleSubmit = async () => {
  if (!validate()) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const payload = {
      source: form.source,
      product_id: form.product_id,
      sn_code: form.sn_code || null,
      target_warehouse_id: form.target_warehouse_id,
      condition: form.condition,
      notes: form.notes || null,
    }
    if (form.source === 'stock_transfer') {
      payload.source_warehouse_id = form.source_warehouse_id
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

onMounted(() => {
  loadProducts()
  loadWarehouses()
})
</script>
