<template>
  <!-- 新建/编辑代采代发订单弹窗 -->
  <div v-if="visible" class="modal-overlay active" @click.self="close">
    <div class="modal-content" style="max-width:780px">
      <div class="modal-header">
        <h3 class="modal-title">{{ isEdit ? '编辑代采代发订单' : '新建代采代发订单' }}</h3>
        <button @click="close" class="modal-close">&times;</button>
      </div>
      <div class="modal-body"><div class="space-y-4">

        <!-- 账套选择 -->
        <div v-if="accountSets.length">
          <label class="label">财务账套</label>
          <select v-model="form.account_set_id" class="input">
            <option :value="null">不指定</option>
            <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>

        <!-- 采购信息区 -->
        <div class="border-t pt-3">
          <div class="text-sm font-semibold mb-3">采购信息</div>
          <div class="grid form-grid grid-cols-2 gap-3">
            <!-- 供应商搜索 -->
            <div class="relative">
              <label class="label">供应商 *</label>
              <input
                v-model="supplierSearch"
                @input="supplierDropdown = true"
                @focus="supplierDropdown = true"
                @blur="hideSupplierDropdown"
                class="input"
                placeholder="输入供应商名称搜索..."
                autocomplete="off"
              >
              <div v-if="supplierDropdown && filteredSuppliers.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
                <div v-for="s in filteredSuppliers" :key="s.id" @mousedown.prevent="selectSupplier(s)" class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm">
                  {{ s.name }}
                  <span v-if="s.contact_person" class="text-muted text-xs ml-1">({{ s.contact_person }})</span>
                </div>
              </div>
              <!-- 快速新建供应商 -->
              <div v-if="supplierDropdown && supplierSearch.trim() && !filteredSuppliers.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg mt-1">
                <div @mousedown.prevent="quickCreateSupplier" class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm text-primary">
                  + 新建供应商「{{ supplierSearch.trim() }}」
                </div>
              </div>
            </div>
            <!-- 发票类型 -->
            <div>
              <label class="label">发票类型 *</label>
              <div class="flex items-center gap-4 mt-1.5">
                <label class="flex items-center gap-1.5 cursor-pointer text-sm">
                  <input type="radio" v-model="form.invoice_type" value="special" class="w-4 h-4"> 专票
                </label>
                <label class="flex items-center gap-1.5 cursor-pointer text-sm">
                  <input type="radio" v-model="form.invoice_type" value="normal" class="w-4 h-4"> 普票
                </label>
              </div>
            </div>
          </div>
          <div class="grid form-grid grid-cols-2 gap-3 mt-3">
            <!-- 商品名称 -->
            <div class="col-span-2">
              <label class="label">商品名称 *</label>
              <input v-model="form.product_name" class="input" placeholder="输入商品名称">
            </div>
          </div>
          <div class="grid form-grid grid-cols-3 gap-3 mt-3">
            <!-- 采购单价 -->
            <div>
              <label class="label">采购单价（含税）*</label>
              <input v-model.number="form.purchase_price" type="number" step="0.01" min="0" class="input" placeholder="0.00">
            </div>
            <!-- 采购税率 -->
            <div>
              <label class="label">采购税率（%）</label>
              <input v-model.number="form.purchase_tax_rate" type="number" step="0.01" min="0" max="100" class="input" placeholder="13">
            </div>
            <!-- 数量 -->
            <div>
              <label class="label">数量 *</label>
              <input v-model.number="form.quantity" type="number" min="1" class="input" placeholder="1">
            </div>
          </div>
          <!-- 采购总额 -->
          <div class="mt-2 text-sm text-muted">
            采购总额: <span class="font-semibold text-foreground">¥{{ purchaseTotal.toFixed(2) }}</span>
          </div>
        </div>

        <!-- 销售信息区 -->
        <div class="border-t pt-3">
          <div class="text-sm font-semibold mb-3">销售信息</div>
          <div class="grid form-grid grid-cols-2 gap-3">
            <!-- 客户搜索 -->
            <div class="relative">
              <label class="label">客户 *</label>
              <input
                v-model="customerSearch"
                @input="customerDropdown = true"
                @focus="customerDropdown = true"
                @blur="hideCustomerDropdown"
                class="input"
                placeholder="输入客户名称搜索..."
                autocomplete="off"
              >
              <div v-if="customerDropdown && filteredCustomers.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
                <div v-for="c in filteredCustomers" :key="c.id" @mousedown.prevent="selectCustomer(c)" class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm">
                  {{ c.name }}
                  <span v-if="c.contact_person" class="text-muted text-xs ml-1">({{ c.contact_person }})</span>
                </div>
              </div>
            </div>
            <!-- 平台合约订单编号 -->
            <div>
              <label class="label">平台合约订单编号 *</label>
              <input v-model="form.platform_order_no" class="input" placeholder="平台合约订单编号">
            </div>
          </div>
          <div class="grid form-grid grid-cols-3 gap-3 mt-3">
            <!-- 销售单价 -->
            <div>
              <label class="label">销售单价 *</label>
              <input v-model.number="form.sale_price" type="number" step="0.01" min="0" class="input" placeholder="0.00">
            </div>
            <!-- 销售税率 -->
            <div>
              <label class="label">销售税率（%）</label>
              <input v-model.number="form.sale_tax_rate" type="number" step="0.01" min="0" max="100" class="input" placeholder="13">
            </div>
            <!-- 数量（只读，与采购同步） -->
            <div>
              <label class="label">数量</label>
              <input :value="form.quantity" type="number" class="input bg-elevated" readonly disabled>
            </div>
          </div>
          <!-- 销售总额 -->
          <div class="mt-2 text-sm text-muted">
            销售总额: <span class="font-semibold text-foreground">¥{{ saleTotal.toFixed(2) }}</span>
          </div>
        </div>

        <!-- 毛利显示区 -->
        <div class="border rounded-lg p-3 bg-elevated">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold">毛利预览</div>
            <div class="flex items-center gap-4">
              <span class="text-sm">
                毛利金额:
                <span class="text-lg font-bold" :class="Number(grossProfit) >= 0 ? 'text-success' : 'text-error'">
                  ¥{{ grossProfit }}
                </span>
              </span>
              <span class="text-sm">
                毛利率:
                <span class="font-bold" :class="Number(grossMargin) >= 0 ? 'text-success' : 'text-error'">
                  {{ grossMargin }}%
                </span>
              </span>
            </div>
          </div>
        </div>

        <!-- 结算方式 -->
        <div class="border-t pt-3">
          <div class="grid form-grid grid-cols-2 gap-3">
            <div>
              <label class="label">结算方式</label>
              <div class="flex items-center gap-4 mt-1.5">
                <label class="flex items-center gap-1.5 cursor-pointer text-sm">
                  <input type="radio" v-model="form.settlement_type" value="prepaid" class="w-4 h-4"> 先款后货
                </label>
                <label class="flex items-center gap-1.5 cursor-pointer text-sm">
                  <input type="radio" v-model="form.settlement_type" value="credit" class="w-4 h-4"> 赊销
                </label>
              </div>
            </div>
            <!-- 发货方式 -->
            <div>
              <label class="label">发货方式</label>
              <div class="flex items-center gap-4 mt-1.5">
                <label class="flex items-center gap-1.5 cursor-pointer text-sm" title="供应商直接发货给客户，货物不经过我方仓库">
                  <input type="radio" v-model="form.shipping_mode" value="direct" class="w-4 h-4"> 供应商直发
                </label>
                <label class="flex items-center gap-1.5 cursor-pointer text-sm" title="货物先到我方仓库，再由我方转发给客户，会产生虚拟入库和出库记录">
                  <input type="radio" v-model="form.shipping_mode" value="transit" class="w-4 h-4"> 过手转发
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- 备注 -->
        <div>
          <label class="label">备注</label>
          <textarea v-model="form.note" class="input" rows="2" placeholder="可选"></textarea>
        </div>

      </div></div>

      <!-- 底部按钮 -->
      <div class="modal-footer">
        <button type="button" @click="close" class="btn btn-sm btn-secondary">取消</button>
        <button v-if="!isEdit" type="button" @click="handleSave(false)" class="btn btn-sm btn-secondary" :disabled="appStore.submitting">
          {{ appStore.submitting ? '保存中...' : '保存草稿' }}
        </button>
        <button type="button" @click="handleSave(true)" class="btn btn-sm btn-primary" :disabled="appStore.submitting">
          {{ appStore.submitting ? '提交中...' : (isEdit ? '保存' : '提交') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 代采代发订单新建/编辑表单弹窗
 * 包含供应商/客户搜索、采购销售信息录入、毛利实时计算
 */
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useFormat } from '../../../composables/useFormat'
import { createDropshipOrder, updateDropshipOrder } from '../../../api/dropship'
import { getSuppliers } from '../../../api/purchase'
import { getCustomers } from '../../../api/customers'
import { getAccountSets } from '../../../api/accounting'

const props = defineProps({
  /** 弹窗是否可见 */
  visible: Boolean,
  /** 编辑模式时传入订单数据 */
  editData: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'saved'])

const appStore = useAppStore()
const { fmt } = useFormat()

// 是否编辑模式
const isEdit = computed(() => !!props.editData?.id)

// 账套列表
const accountSets = ref([])

// 供应商
const suppliers = ref([])
const supplierSearch = ref('')
const supplierDropdown = ref(false)

// 客户
const customers = ref([])
const customerSearch = ref('')
const customerDropdown = ref(false)

// 下拉菜单延时隐藏（每个下拉单独封装，避免模板 ref 自动展开问题）
let _blurTimer = null
const hideSupplierDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { supplierDropdown.value = false }, 200)
}
const hideCustomerDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { customerDropdown.value = false }, 200)
}
onUnmounted(() => clearTimeout(_blurTimer))

// 表单数据
const form = reactive({
  account_set_id: null,
  supplier_id: '',
  product_name: '',
  invoice_type: 'special',
  purchase_price: null,
  purchase_tax_rate: 13,
  quantity: 1,
  customer_id: '',
  platform_order_no: '',
  sale_price: null,
  sale_tax_rate: 13,
  settlement_type: 'prepaid',
  shipping_mode: 'direct',
  note: '',
})

/** 关闭弹窗 */
const close = () => {
  emit('update:visible', false)
}

// ---- 计算属性 ----

/** 采购总额 */
const purchaseTotal = computed(() => {
  const price = Number(form.purchase_price) || 0
  const qty = Number(form.quantity) || 0
  return Math.round(price * qty * 100) / 100
})

/** 销售总额 */
const saleTotal = computed(() => {
  const price = Number(form.sale_price) || 0
  const qty = Number(form.quantity) || 0
  return Math.round(price * qty * 100) / 100
})

/** 不含税金额（提取公共计算逻辑） */
const exclTaxAmounts = computed(() => {
  const saleTaxRate = Number(form.sale_tax_rate) || 0
  const purchaseTaxRate = Number(form.purchase_tax_rate) || 0
  const saleExclTax = saleTotal.value / (1 + saleTaxRate / 100)
  const costExclTax = form.invoice_type === 'special'
    ? purchaseTotal.value / (1 + purchaseTaxRate / 100)
    : purchaseTotal.value // 普票不可抵扣，含税价即成本
  return { saleExclTax, costExclTax }
})

/** 毛利计算（不含税比较） */
const grossProfit = computed(() => {
  const { saleExclTax, costExclTax } = exclTaxAmounts.value
  return (saleExclTax - costExclTax).toFixed(2)
})

/** 毛利率 */
const grossMargin = computed(() => {
  const { saleExclTax, costExclTax } = exclTaxAmounts.value
  if (saleExclTax <= 0) return '0.00'
  return ((saleExclTax - costExclTax) / saleExclTax * 100).toFixed(2)
})

/** 供应商模糊搜索过滤 */
const filteredSuppliers = computed(() => {
  const q = supplierSearch.value.trim().toLowerCase()
  if (!q) return suppliers.value.slice(0, 20)
  return suppliers.value.filter(s =>
    s.name.toLowerCase().includes(q) ||
    (s.contact_person && s.contact_person.toLowerCase().includes(q))
  ).slice(0, 20)
})

/** 客户模糊搜索过滤 */
const filteredCustomers = computed(() => {
  const q = customerSearch.value.trim().toLowerCase()
  if (!q) return customers.value.slice(0, 20)
  return customers.value.filter(c =>
    c.name.toLowerCase().includes(q) ||
    (c.contact_person && c.contact_person.toLowerCase().includes(q))
  ).slice(0, 20)
})

// ---- 选择操作 ----

/** 选择供应商 */
const selectSupplier = (s) => {
  form.supplier_id = s.id
  supplierSearch.value = s.name
  supplierDropdown.value = false
}

/** 快速新建供应商（仅填入名称） */
const quickCreateSupplier = () => {
  // 标记为新建，提交时由后端自动创建
  form.supplier_id = ''
  form._new_supplier_name = supplierSearch.value.trim()
  supplierDropdown.value = false
}

/** 选择客户 */
const selectCustomer = (c) => {
  form.customer_id = c.id
  customerSearch.value = c.name
  customerDropdown.value = false
}

// ---- 加载数据 ----

/** 加载供应商列表 */
const loadSuppliers = async () => {
  try {
    const params = {}
    if (form.account_set_id) params.account_set_id = form.account_set_id
    const { data } = await getSuppliers(params)
    suppliers.value = data.items || data
  } catch (e) {
    console.error('加载供应商失败:', e)
  }
}

/** 加载客户列表 */
const loadCustomers = async () => {
  try {
    const { data } = await getCustomers()
    customers.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载客户失败:', e)
  }
}

/** 加载账套列表 */
const loadAccountSets = async () => {
  try {
    const { data } = await getAccountSets()
    accountSets.value = data.items || data
  } catch (e) {
    /* 静默失败 */
  }
}

// ---- 初始化 ----

/** 重置表单 */
const resetForm = () => {
  Object.assign(form, {
    account_set_id: null,
    supplier_id: '',
    product_name: '',
    invoice_type: 'special',
    purchase_price: null,
    purchase_tax_rate: 13,
    quantity: 1,
    customer_id: '',
    platform_order_no: '',
    sale_price: null,
    sale_tax_rate: 13,
    settlement_type: 'prepaid',
    shipping_mode: 'direct',
    note: '',
  })
  form._new_supplier_name = ''
  supplierSearch.value = ''
  customerSearch.value = ''
}

/** 填充编辑数据 */
const fillEditData = (data) => {
  Object.assign(form, {
    account_set_id: data.account_set_id || null,
    supplier_id: data.supplier_id || '',
    product_name: data.product_name || '',
    invoice_type: data.invoice_type || 'special',
    purchase_price: data.purchase_price ?? null,
    purchase_tax_rate: data.purchase_tax_rate ?? 13,
    quantity: data.quantity ?? 1,
    customer_id: data.customer_id || '',
    platform_order_no: data.platform_order_no || '',
    sale_price: data.sale_price ?? null,
    sale_tax_rate: data.sale_tax_rate ?? 13,
    settlement_type: data.settlement_type || 'prepaid',
    shipping_mode: data.shipping_mode || 'direct',
    note: data.note || '',
  })
  supplierSearch.value = data.supplier_name || ''
  customerSearch.value = data.customer_name || ''
}

// 弹窗打开时初始化
watch(() => props.visible, (val) => {
  if (val) {
    if (props.editData) {
      fillEditData(props.editData)
    } else {
      resetForm()
    }
  }
})

// 账套变更时重新加载供应商
watch(() => form.account_set_id, () => {
  loadSuppliers()
})

// ---- 提交 ----

/** 校验表单 */
const validate = (submit) => {
  if (!form.supplier_id && !form._new_supplier_name) {
    appStore.showToast('请选择供应商', 'error')
    return false
  }
  if (!form.product_name?.trim()) {
    appStore.showToast('请输入商品名称', 'error')
    return false
  }
  if (!form.quantity || form.quantity <= 0) {
    appStore.showToast('请输入有效数量', 'error')
    return false
  }
  if (submit) {
    if (!form.purchase_price || form.purchase_price <= 0) {
      appStore.showToast('请输入采购单价', 'error')
      return false
    }
    if (!form.customer_id) {
      appStore.showToast('请选择客户', 'error')
      return false
    }
    if (!form.platform_order_no?.trim()) {
      appStore.showToast('请输入平台合约订单编号', 'error')
      return false
    }
    if (!form.sale_price || form.sale_price <= 0) {
      appStore.showToast('请输入销售单价', 'error')
      return false
    }
  }
  return true
}

/** 保存/提交订单 */
const handleSave = async (submit) => {
  if (!validate(submit)) return
  if (appStore.submitting) return
  appStore.submitting = true

  try {
    const payload = {
      supplier_id: form.supplier_id ? parseInt(form.supplier_id) : null,
      supplier_name: form._new_supplier_name || null,
      product_name: form.product_name.trim(),
      invoice_type: form.invoice_type,
      purchase_price: form.purchase_price,
      purchase_tax_rate: form.purchase_tax_rate,
      quantity: parseInt(form.quantity),
      customer_id: form.customer_id ? parseInt(form.customer_id) : null,
      platform_order_no: form.platform_order_no?.trim() || null,
      sale_price: form.sale_price,
      sale_tax_rate: form.sale_tax_rate,
      settlement_type: form.settlement_type,
      shipping_mode: form.shipping_mode,
      note: form.note?.trim() || null,
      account_set_id: form.account_set_id || null,
    }

    if (isEdit.value) {
      await updateDropshipOrder(props.editData.id, payload)
      appStore.showToast('代采代发订单更新成功')
    } else {
      const { data } = await createDropshipOrder(payload, submit)
      appStore.showToast(submit ? '代采代发订单提交成功: ' + data.ds_no : '草稿已保存: ' + data.ds_no)
    }
    close()
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

onMounted(() => {
  loadSuppliers()
  loadCustomers()
  loadAccountSets()
})

// 暴露给父组件
defineExpose({
  loadSuppliers,
})
</script>
