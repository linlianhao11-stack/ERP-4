<template>
  <!-- 新建采购订单弹窗 -->
  <div v-if="visible" class="modal-overlay active" @click.self="close">
    <div class="modal-content" style="max-width:700px">
      <div class="modal-header">
        <h3 class="modal-title">新建采购订单</h3>
        <button @click="close" class="modal-close">&times;</button>
      </div>
      <div class="space-y-4 p-4">
        <div class="grid form-grid grid-cols-2 gap-3">
          <!-- 供应商搜索 -->
          <div class="relative">
            <label class="label">供应商 *</label>
            <input
              v-model="poSupplierSearch"
              @input="poSupplierDropdown = true"
              @focus="poSupplierDropdown = true"
              @blur="setTimeout(() => poSupplierDropdown = false, 200)"
              class="input"
              placeholder="输入供应商名称搜索..."
              autocomplete="off"
            >
            <div v-if="poSupplierDropdown && filteredPoSuppliers.length" class="absolute z-50 left-0 right-0 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
              <div v-for="s in filteredPoSuppliers" :key="s.id" @mousedown.prevent="selectPoSupplier(s)" class="px-3 py-2 hover:bg-[#e8f4fd] cursor-pointer text-sm">
                {{ s.name }}
                <span v-if="s.contact_person" class="text-[#86868b] text-xs ml-1">({{ s.contact_person }})</span>
              </div>
            </div>
          </div>
          <!-- 目标仓库 -->
          <div>
            <label class="label">目标仓库 *</label>
            <select v-model="poForm.target_warehouse_id" class="input" required>
              <option value="">选择仓库</option>
              <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
            </select>
          </div>
        </div>
        <!-- 目标仓位 -->
        <div>
          <label class="label">目标仓位</label>
          <select v-model="poForm.target_location_id" class="input" :disabled="!poForm.target_warehouse_id">
            <option value="">{{ poForm.target_warehouse_id ? '选择仓位（可选）' : '请先选择仓库' }}</option>
            <option v-for="loc in poTargetLocations" :key="loc.id" :value="loc.id">{{ loc.code }}{{ loc.name ? ' - ' + loc.name : '' }}</option>
          </select>
        </div>
        <!-- 财务账套 -->
        <div v-if="accountSets.length">
          <label class="label">财务账套</label>
          <select v-model="poForm.account_set_id" class="input">
            <option :value="null">不指定</option>
            <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
          <div v-if="poForm.account_set_id" class="text-xs text-[#86868b] mt-1">选择仓库后将自动带入关联账套，也可手动修改</div>
          <div v-else class="text-xs text-[#ff9500] mt-1">未选择财务账套，收货后将不会自动生成财务单据（应付单/入库单）</div>
        </div>

        <!-- 商品明细 -->
        <div class="border-t pt-3">
          <div class="flex justify-between items-center mb-2">
            <span class="font-semibold text-sm">商品明细</span>
            <button type="button" @click="poAddItem" class="btn btn-secondary btn-sm text-xs">+ 添加商品</button>
          </div>
          <div v-for="(item, idx) in poForm.items" :key="idx" class="p-3 bg-[#f5f5f7] rounded-lg mb-2">
            <div class="flex justify-between items-center mb-2">
              <span class="text-xs font-semibold text-[#86868b]">#{{ idx + 1 }}</span>
              <button type="button" @click="poRemoveItem(idx)" class="text-[#ff3b30] text-xs" v-if="poForm.items.length > 1">删除</button>
            </div>
            <!-- 商品搜索下拉 -->
            <div class="mb-2 relative">
              <label class="label text-xs">商品</label>
              <input
                v-model="item._search"
                @input="item._dropdownOpen = true"
                @focus="item._dropdownOpen = true"
                @blur="setTimeout(() => item._dropdownOpen = false, 200)"
                class="input text-sm"
                placeholder="输入SKU或商品名搜索..."
                autocomplete="off"
              >
              <div v-if="item._dropdownOpen && poFilteredProducts(item._search).length" class="absolute z-50 left-0 right-0 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
                <div v-for="p in poFilteredProducts(item._search)" :key="p.id" @mousedown.prevent="poPickProduct(item, p)" class="px-3 py-2 hover:bg-[#e8f4fd] cursor-pointer text-sm">
                  <span class="font-mono text-[#86868b]">{{ p.sku }}</span> <span>{{ p.name }}</span>
                  <span v-if="p.brand" class="text-[#86868b] text-xs ml-1">[{{ p.brand }}]</span>
                </div>
              </div>
            </div>
            <!-- 价格/税率/数量 -->
            <div class="grid grid-cols-3 gap-2 mb-2">
              <div>
                <label class="label text-xs">含税单价</label>
                <input v-model.number="item.tax_inclusive_price" type="number" step="0.01" class="input text-sm" @input="poCalcItem(item)">
              </div>
              <div>
                <label class="label text-xs">税率</label>
                <select v-model.number="item.tax_rate" class="input text-sm" @change="poCalcItem(item)">
                  <option :value="0.13">13%</option>
                  <option :value="0.09">9%</option>
                  <option :value="0.06">6%</option>
                  <option :value="0.03">3%</option>
                  <option :value="0">0%</option>
                </select>
              </div>
              <div>
                <label class="label text-xs">数量</label>
                <input v-model.number="item.quantity" type="number" min="1" class="input text-sm" @input="poCalcItem(item)">
              </div>
            </div>
            <!-- 小计信息 -->
            <div class="flex justify-between text-xs text-[#86868b]">
              <span>未税单价: ¥{{ item.tax_exclusive_price.toFixed(2) }}</span>
              <span v-if="item.rebate_amount > 0" class="text-[#34c759]">返利: -¥{{ item.rebate_amount.toFixed(2) }}</span>
              <span class="font-semibold text-[#1d1d1f]">小计: ¥{{ (item.amount - (item.rebate_amount || 0)).toFixed(2) }}</span>
            </div>
          </div>
        </div>

        <!-- 返利抵扣 -->
        <div v-if="poForm.supplier_rebate_balance > 0" class="border-t pt-3">
          <label class="flex items-center cursor-pointer mb-2">
            <input type="checkbox" v-model="poForm.use_rebate" class="mr-2 w-4 h-4" @change="!poForm.use_rebate && poForm.items.forEach(i => i.rebate_amount = 0)">
            <span class="font-medium text-sm">使用返利</span>
            <span class="text-xs text-[#34c759] ml-2">可用: ¥{{ fmt(poForm.supplier_rebate_balance) }}</span>
          </label>
          <div v-if="poForm.use_rebate" class="space-y-2">
            <div v-for="(item, idx) in poForm.items.filter(i => i.product_id)" :key="idx" class="flex items-center gap-2 text-sm bg-[#f5f5f7] rounded p-2">
              <span class="flex-1 truncate">{{ item._search || '商品' + (idx + 1) }}</span>
              <span class="text-[#86868b]">¥{{ item.amount.toFixed(2) }}</span>
              <input v-model.number="item.rebate_amount" type="number" step="0.01" min="0" :max="item.amount" class="w-24 text-right border rounded px-2 py-1 text-sm" placeholder="返利">
            </div>
            <div class="flex justify-between text-sm mt-1">
              <span class="text-[#34c759]">返利总额: <b>¥{{ fmt(poForm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0)) }}</b></span>
              <span v-if="poForm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) > poForm.supplier_rebate_balance" class="text-[#ff3b30] text-xs">超过可用余额!</span>
            </div>
          </div>
        </div>

        <!-- 在账资金抵扣 -->
        <div v-if="poForm.supplier_credit_balance > 0" class="border-t pt-3">
          <label class="flex items-center cursor-pointer mb-2">
            <input type="checkbox" v-model="poForm.use_credit" class="mr-2 w-4 h-4">
            <span class="font-medium text-sm">使用在账资金</span>
            <span class="text-xs text-[#0071e3] ml-2">可用: ¥{{ fmt(poForm.supplier_credit_balance) }}</span>
          </label>
          <div v-if="poForm.use_credit" class="flex items-center gap-2">
            <label class="text-sm text-[#6e6e73]">抵扣金额:</label>
            <input v-model.number="poForm.credit_amount" type="number" step="0.01" min="0"
              :max="poForm.supplier_credit_balance" class="input text-sm w-40" placeholder="输入抵扣金额">
            <span v-if="poForm.credit_amount > poForm.supplier_credit_balance" class="text-[#ff3b30] text-xs">超过可用余额!</span>
          </div>
        </div>

        <!-- 含税总额 -->
        <div class="border-t pt-3 flex justify-between items-center">
          <div class="text-sm">
            含税总额: <span class="text-xl font-bold text-[#0071e3]">¥{{ poFinalAmount.toFixed(2) }}</span>
            <span v-if="(poForm.use_rebate && poRebateTotal > 0) || (poForm.use_credit && poForm.credit_amount > 0)" class="text-xs text-[#86868b] ml-2">
              (原价 ¥{{ poTotal.toFixed(2) }}
              <template v-if="poForm.use_rebate && poRebateTotal > 0"> - 返利 ¥{{ poRebateTotal.toFixed(2) }}</template>
              <template v-if="poForm.use_credit && poForm.credit_amount > 0"> - 在账 ¥{{ poForm.credit_amount.toFixed(2) }}</template>)
            </span>
          </div>
        </div>
        <!-- 备注 -->
        <div>
          <label class="label">备注</label>
          <input v-model="poForm.remark" class="input" placeholder="可选">
        </div>
        <!-- 操作按钮 -->
        <div class="flex gap-3 pt-2">
          <button type="button" @click="close" class="btn btn-secondary flex-1">取消</button>
          <button type="button" @click="savePurchaseOrder" class="btn btn-primary flex-1" :disabled="appStore.submitting">{{ appStore.submitting ? '提交中...' : '确认提交' }}</button>
        </div>
      </div>
    </div>
  </div>

  <!-- 快速新建商品弹窗 -->
  <div v-if="showProductModal" class="modal-overlay active" @click.self="showProductModal = false">
    <div class="modal-content">
      <div class="modal-header">
        <h3 class="modal-title">新建商品</h3>
        <button @click="showProductModal = false" class="modal-close">&times;</button>
      </div>
      <form @submit.prevent="saveProduct" class="space-y-3 p-4">
        <div><label class="label">SKU *</label><input v-model="productForm.sku" class="input" required placeholder="商品SKU"></div>
        <div><label class="label">名称 *</label><input v-model="productForm.name" class="input" required placeholder="商品名称"></div>
        <div class="grid form-grid grid-cols-2 gap-3">
          <div><label class="label">品牌</label><input v-model="productForm.brand" class="input" placeholder="品牌"></div>
          <div><label class="label">分类</label><input v-model="productForm.category" class="input" placeholder="分类"></div>
        </div>
        <div class="grid form-grid grid-cols-2 gap-3">
          <div><label class="label">零售价</label><input v-model.number="productForm.retail_price" type="number" step="0.01" class="input"></div>
          <div><label class="label">成本价</label><input v-model.number="productForm.cost_price" type="number" step="0.01" class="input"></div>
        </div>
        <div class="flex gap-3 pt-3">
          <button type="button" @click="showProductModal = false" class="btn btn-secondary flex-1">取消</button>
          <button type="submit" class="btn btn-primary flex-1">保存</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
/**
 * 新建采购订单表单弹窗
 * 包含供应商搜索、商品明细编辑、返利/在账资金抵扣、账套选择
 * 内嵌快速新建商品弹窗
 */
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useProductsStore } from '../../../stores/products'
import { useWarehousesStore } from '../../../stores/warehouses'
import { useFormat } from '../../../composables/useFormat'
import { getSuppliers, createPurchaseOrder } from '../../../api/purchase'
import api from '../../../api/index'

const props = defineProps({
  /** 弹窗是否可见 */
  visible: Boolean,
  /** 财务账套列表 */
  accountSets: Array
})

const emit = defineEmits(['update:visible', 'saved'])

const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const { fmt } = useFormat()
const products = computed(() => productsStore.products)
const warehouses = computed(() => warehousesStore.warehouses)

// 供应商列表
const suppliers = ref([])

// 供应商搜索状态
const poSupplierSearch = ref('')
const poSupplierDropdown = ref(false)

// 新建商品弹窗
const showProductModal = ref(false)
const productForm = reactive({
  sku: '', name: '', brand: '', category: '', retail_price: null, cost_price: null
})

// 采购单表单
const poForm = reactive({
  supplier_id: '', target_warehouse_id: '', target_location_id: '',
  remark: '', items: [], use_rebate: false, supplier_rebate_balance: 0,
  use_credit: false, supplier_credit_balance: 0, credit_amount: 0,
  account_set_id: null
})

/** 关闭弹窗 */
const close = () => {
  emit('update:visible', false)
}

// ---- 计算属性 ----

/** 供应商模糊搜索过滤 */
const filteredPoSuppliers = computed(() => {
  const q = poSupplierSearch.value.trim().toLowerCase()
  if (!q) return suppliers.value
  return suppliers.value.filter(s =>
    s.name.toLowerCase().includes(q) ||
    (s.contact_person && s.contact_person.toLowerCase().includes(q))
  )
})

/** 商品含税总价 */
const poTotal = computed(() => Math.round(poForm.items.reduce((s, i) => s + i.amount, 0) * 100) / 100)
/** 返利总额 */
const poRebateTotal = computed(() => Math.round(poForm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) * 100) / 100)
/** 扣除返利和在账资金后的最终金额 */
const poFinalAmount = computed(() => {
  let amount = poTotal.value
  if (poForm.use_rebate) amount -= poRebateTotal.value
  if (poForm.use_credit && poForm.credit_amount > 0) amount -= poForm.credit_amount
  return Math.max(0, amount)
})

/** 当前仓库下的仓位列表 */
const poTargetLocations = computed(() => {
  if (!poForm.target_warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(poForm.target_warehouse_id)
})

// 账套变更时重新加载供应商余额
watch(() => poForm.account_set_id, () => {
  loadSuppliers()
  if (poForm.supplier_id) {
    // 延迟更新余额，等供应商列表加载完
    setTimeout(() => {
      const s = suppliers.value.find(x => x.id === parseInt(poForm.supplier_id))
      if (s) {
        poForm.supplier_rebate_balance = s.rebate_balance || 0
        poForm.supplier_credit_balance = s.credit_balance || 0
      }
    }, 300)
  }
})

// 仓库变更时重置仓位并自动带入关联账套
watch(() => poForm.target_warehouse_id, (whId) => {
  poForm.target_location_id = ''
  if (whId) {
    const wh = warehouses.value.find(w => w.id === parseInt(whId))
    if (wh?.account_set_id) poForm.account_set_id = wh.account_set_id
    else poForm.account_set_id = null
  }
})

// 弹窗打开时初始化表单
watch(() => props.visible, (val) => {
  if (val) {
    const defaultWh = warehouses.value.find(w => w.is_default)
    Object.assign(poForm, {
      supplier_id: '',
      target_warehouse_id: defaultWh?.id || '',
      target_location_id: '',
      remark: '',
      items: [],
      use_rebate: false,
      supplier_rebate_balance: 0,
      use_credit: false,
      supplier_credit_balance: 0,
      credit_amount: 0,
      account_set_id: defaultWh?.account_set_id || null
    })
    poSupplierSearch.value = ''
    poAddItem()
  }
})

// ---- 供应商操作 ----

/** 加载供应商列表（按账套读取余额） */
const loadSuppliers = async () => {
  try {
    const params = {}
    if (poForm.account_set_id) params.account_set_id = poForm.account_set_id
    const { data } = await getSuppliers(params)
    suppliers.value = data
  } catch (e) {
    console.error(e)
  }
}

/** 选择供应商，填充返利/在账余额 */
const selectPoSupplier = (s) => {
  poForm.supplier_id = s.id
  poSupplierSearch.value = s.name
  poSupplierDropdown.value = false
  poForm.supplier_rebate_balance = s.rebate_balance || 0
  poForm.use_rebate = false
  poForm.supplier_credit_balance = s.credit_balance || 0
  poForm.use_credit = false
  poForm.credit_amount = 0
}

// ---- 商品明细操作 ----

/** 根据关键字过滤商品列表（最多20条） */
const poFilteredProducts = (query) => {
  const q = (query || '').trim().toLowerCase()
  if (!q) return products.value.slice(0, 20)
  return products.value.filter(p =>
    p.sku.toLowerCase().includes(q) ||
    p.name.toLowerCase().includes(q) ||
    (p.brand && p.brand.toLowerCase().includes(q))
  ).slice(0, 20)
}

/** 选中商品，填充价格 */
const poPickProduct = (item, p) => {
  item.product_id = p.id
  item._search = p.sku + ' - ' + p.name
  item._dropdownOpen = false
  item.tax_inclusive_price = p.cost_price || 0
  poCalcItem(item)
}

/** 添加一行商品明细 */
const poAddItem = () => {
  poForm.items.push({
    product_id: '', _search: '', _dropdownOpen: false,
    tax_inclusive_price: 0, tax_rate: 0.13, tax_exclusive_price: 0,
    quantity: 1, amount: 0, rebate_amount: 0
  })
}

/** 删除一行商品明细 */
const poRemoveItem = (idx) => {
  poForm.items.splice(idx, 1)
}

/** 计算商品未税单价和小计 */
const poCalcItem = (item) => {
  item.tax_exclusive_price = item.tax_rate > 0
    ? Math.round(item.tax_inclusive_price / (1 + item.tax_rate) * 100) / 100
    : item.tax_inclusive_price
  item.amount = Math.round(item.tax_inclusive_price * item.quantity * 100) / 100
}

// ---- 新建商品 ----

/** 打开新建商品弹窗（供父组件调用） */
const openProductModal = () => {
  Object.assign(productForm, { sku: '', name: '', brand: '', category: '', retail_price: null, cost_price: null })
  showProductModal.value = true
}

/** 保存新建商品 */
const saveProduct = async () => {
  if (productForm.retail_price == null || productForm.retail_price === '') {
    appStore.showToast('请输入零售价', 'error')
    return
  }
  if (productForm.cost_price == null || productForm.cost_price === '') {
    appStore.showToast('请输入成本价', 'error')
    return
  }
  try {
    await api.post('/products', productForm)
    appStore.showToast('保存成功')
    showProductModal.value = false
    productsStore.loadProducts()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}

// ---- 提交采购单 ----

/** 校验并提交采购订单 */
const savePurchaseOrder = async () => {
  if (!poForm.supplier_id) {
    appStore.showToast('请选择供应商', 'error')
    return
  }
  if (!poForm.target_warehouse_id) {
    appStore.showToast('请选择目标仓库', 'error')
    return
  }
  const validItems = poForm.items.filter(i => i.product_id && i.quantity > 0 && i.tax_inclusive_price > 0)
  if (!validItems.length) {
    appStore.showToast('请添加有效的商品明细', 'error')
    return
  }
  const totalRebate = poForm.use_rebate ? poForm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) : 0
  if (poForm.use_rebate && totalRebate > poForm.supplier_rebate_balance) {
    appStore.showToast('返利总额超过可用余额', 'error')
    return
  }
  const creditAmount = poForm.use_credit ? (poForm.credit_amount || 0) : 0
  if (poForm.use_credit && creditAmount > poForm.supplier_credit_balance) {
    appStore.showToast('在账资金抵扣超过可用余额', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const { data } = await createPurchaseOrder({
      supplier_id: parseInt(poForm.supplier_id),
      target_warehouse_id: parseInt(poForm.target_warehouse_id),
      target_location_id: poForm.target_location_id ? parseInt(poForm.target_location_id) : null,
      remark: poForm.remark || null,
      rebate_amount: totalRebate > 0 ? totalRebate : null,
      credit_amount: creditAmount > 0 ? creditAmount : null,
      account_set_id: poForm.account_set_id || null,
      items: validItems.map(i => ({
        product_id: parseInt(i.product_id),
        quantity: parseInt(i.quantity),
        tax_inclusive_price: i.tax_inclusive_price,
        tax_rate: Number(i.tax_rate),
        target_warehouse_id: null,
        target_location_id: null,
        rebate_amount: poForm.use_rebate && i.rebate_amount ? i.rebate_amount : null
      }))
    })
    appStore.showToast('采购订单创建成功: ' + data.po_no)
    close()
    // 通知父组件刷新列表和供应商
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// 组件挂载时加载供应商列表
onMounted(() => {
  loadSuppliers()
})

// 暴露给父组件的方法
defineExpose({
  /** 打开新建商品弹窗 */
  openProductModal,
  /** 刷新供应商列表 */
  loadSuppliers
})
</script>
