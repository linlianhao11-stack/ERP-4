<!--
  销售页面 - 瘦容器
  编排 SalesToolbar、SalesWorksheet、SalesFooter、OrderConfirmModal
  管理全局状态、退货订单搜索逻辑、订单提交流程
-->
<template>
  <div class="flex flex-col" style="height: calc(100vh - 72px)">
    <!-- 顶栏 -->
    <SalesToolbar
      :order-type="saleForm.order_type"
      :customer-id="saleForm.customer_id"
      :employee-id="saleForm.employee_id"
      :customers="customers"
      :employees="salespersonEmployees"
      :need-customer="needCustomer"
      :return-order-search="returnOrderSearch"
      :return-order-dropdown="returnOrderDropdown"
      :filtered-return-orders="filteredReturnOrders"
      :selected-return-order="selectedReturnOrder"
      :remark="saleForm.remark"
      @update:order-type="saleForm.order_type = $event"
      @update:customer-id="saleForm.customer_id = $event"
      @update:employee-id="saleForm.employee_id = $event"
      @update:return-order-search="returnOrderSearch = $event"
      @update:return-order-dropdown="returnOrderDropdown = $event"
      @search-return-orders="searchReturnOrders"
      @select-return-order="selectReturnOrder"
      @update:remark="saleForm.remark = $event"
    />

    <!-- 工作台表格 -->
    <SalesWorksheet class="flex-1 min-h-0 overflow-y-auto"
      :cart="cart"
      :order-type="saleForm.order_type"
      :warehouses="warehouses"
      :products="products"
      :is-multi-account-set="isMultiAccountSet"
      @remove-item="idx => cart.splice(idx, 1)"
      @duplicate-line="handleDuplicateLine"
      @add-from-search="handleAddFromSearch"
    />

    <!-- 底栏（固定底部） -->
    <SalesFooter
      :cart-total="cartTotal"
      :cart-length="cart.length"
      :account-set-groups="accountSetGroups"
      :is-multi-account-set="isMultiAccountSet"
      @clear="clearCart"
      @submit="submitOrder"
    />

    <!-- 订单确认弹窗（保持不变） -->
    <OrderConfirmModal
      :visible="appStore.modal.show && appStore.modal.type === 'order_confirm'"
      :order-confirm="orderConfirm"
      :employees="salespersonEmployees"
      :payment-methods="paymentMethods"
      :submitting="appStore.submitting"
      @update:visible="!$event && appStore.closeModal()"
      @confirm="confirmSubmitOrder"
    />
  </div>
</template>

<script setup>
/**
 * 销售页面瘦容器
 * 负责：store 初始化、状态编排、退货搜索、订单提交
 */
import { ref, reactive, computed, watch, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import { useAppStore } from '../stores/app'
import { useProductsStore } from '../stores/products'
import { useWarehousesStore } from '../stores/warehouses'
import { useCustomersStore } from '../stores/customers'
import { useSettingsStore } from '../stores/settings'
import { useFormat } from '../composables/useFormat'
import { useSalesCart } from '../composables/useSalesCart'
import { getOrders, getOrder, createOrder } from '../api/orders'
import { getAccountSets } from '../api/accounting'
import { getPaymentMethods as getPaymentMethodsApi } from '../api/settings'
import { fuzzyMatchAny } from '../utils/helpers'
import SalesToolbar from '../components/business/sales/SalesToolbar.vue'
import SalesWorksheet from '../components/business/sales/SalesWorksheet.vue'
import SalesFooter from '../components/business/sales/SalesFooter.vue'
const OrderConfirmModal = defineAsyncComponent(() => import('../components/business/sales/OrderConfirmModal.vue'))

// ---------- Store ----------
const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const customersStore = useCustomersStore()
const settingsStore = useSettingsStore()

const { fmt } = useFormat()

const products = computed(() => productsStore.products)
const warehouses = computed(() => warehousesStore.warehouses)
const locations = computed(() => warehousesStore.locations)
const customers = computed(() => customersStore.customers)
const salespersonEmployees = computed(() => settingsStore.employees.filter(e => e.is_salesperson))
const allPaymentMethods = computed(() => settingsStore.paymentMethods)

// 按账套过滤的收款方式
const filteredPaymentMethodsList = ref([])
async function loadFilteredPaymentMethods(accountSetId) {
  if (!accountSetId) { filteredPaymentMethodsList.value = []; return }
  try {
    const { data } = await getPaymentMethodsApi({ account_set_id: accountSetId })
    filteredPaymentMethodsList.value = data.items || data
  } catch { filteredPaymentMethodsList.value = [] }
}
const paymentMethods = computed(() =>
  filteredPaymentMethodsList.value.length ? filteredPaymentMethodsList.value : allPaymentMethods.value
)

// ---------- 购物车 ----------
const {
  cart, addFromSearch, populateReturnItems, duplicateCartLine,
  cartTotal, clearCart
} = useSalesCart()

// ---------- 本地状态 ----------

const saleForm = reactive({
  order_type: 'CASH',
  customer_id: '',
  employee_id: '',
  related_order_id: '',
  remark: ''
})

// 退货相关
const returnOrderSearch = ref('')
const returnOrderDropdown = ref(false)
const salesOrders = ref([])
const selectedReturnOrder = ref(null)

// 订单确认数据
const orderConfirm = ref({
  items: [], customer: null, total: 0, order_type: '',
  refunded: false, use_credit: false, available_credit: 0,
  use_rebate: false, rebate_balance: 0, employee_id: '',
  remark: '', payment_method: 'cash', account_set_id: null
})

// ---------- 计算属性 ----------
const needCustomer = computed(() =>
  ['CASH', 'CREDIT', 'CONSIGN_OUT', 'CONSIGN_SETTLE', 'RETURN'].includes(saleForm.order_type)
)

const filteredReturnOrders = computed(() => {
  const kw = returnOrderSearch.value
  if (!kw) return salesOrders.value.slice(0, 20)
  return salesOrders.value.filter(o => fuzzyMatchAny([o.order_no, o.customer_name], kw)).slice(0, 20)
})

/** 按账套分组 */
const accountSetGroups = computed(() => {
  const groups = new Map()
  for (const item of cart.value) {
    const wh = warehouses.value.find(w => w.id === parseInt(item.warehouse_id))
    const asId = wh?.account_set_id || 0
    const asName = wh?.account_set_name || '未关联账套'
    if (!groups.has(asId)) groups.set(asId, { key: asId, name: asName, subtotal: 0 })
    groups.get(asId).subtotal += Math.round(item.unit_price * item.quantity * 100) / 100
  }
  return [...groups.values()]
})

const isMultiAccountSet = computed(() => accountSetGroups.value.length > 1)

// ---------- 函数 ----------

/** 内联搜索添加商品 */
const handleAddFromSearch = (product, stockRow) => {
  addFromSearch(product, stockRow, saleForm.order_type, appStore)
}

/** 复制购物车行 */
const handleDuplicateLine = (idx) => duplicateCartLine(idx, products)

/** 搜索退货关联订单 */
let _returnOrderAbort = null
const searchReturnOrders = async () => {
  if (saleForm.order_type !== 'RETURN') return
  if (_returnOrderAbort) _returnOrderAbort.abort()
  const controller = new AbortController()
  _returnOrderAbort = controller
  try {
    const { data } = await getOrders({ limit: 200 }, { signal: controller.signal })
    salesOrders.value = (data.items || data).filter(o => ['CASH', 'CREDIT'].includes(o.order_type))
  } catch (e) {
    if (e?.code === 'ERR_CANCELED') return
    appStore.showToast(e.response?.data?.detail || '加载订单失败', 'error')
  } finally {
    if (_returnOrderAbort === controller) _returnOrderAbort = null
  }
}

/** 选中退货关联订单 */
const selectReturnOrder = async (o) => {
  returnOrderSearch.value = o.order_no + ' - ' + o.customer_name
  saleForm.related_order_id = o.id
  saleForm.customer_id = o.customer_id
  returnOrderDropdown.value = false
  try {
    const { data } = await getOrder(o.id)
    selectedReturnOrder.value = data
    populateReturnItems(data, products)
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
  }
}

/** 提交订单前校验并打开确认弹窗 */
const submitOrder = () => {
  // 退货模式过滤掉数量为0的行
  const activeItems = saleForm.order_type === 'RETURN'
    ? cart.value.filter(i => i.quantity > 0)
    : cart.value

  if (!activeItems.length) {
    appStore.showToast('请至少添加一件商品', 'error')
    return
  }

  // 校验数量和单价
  for (const item of activeItems) {
    if (!item.quantity || item.quantity <= 0) {
      appStore.showToast(`【${item.name}】数量必须大于0`, 'error'); return
    }
    if (saleForm.order_type !== 'RETURN' && item.unit_price <= 0) {
      appStore.showToast(`【${item.name}】单价必须大于0`, 'error'); return
    }
    if (saleForm.order_type === 'RETURN' && item.unit_price < 0) {
      appStore.showToast(`【${item.name}】单价不能为负数`, 'error'); return
    }
  }

  if (needCustomer.value && !saleForm.customer_id) {
    appStore.showToast('请选择客户', 'error'); return
  }
  if (saleForm.order_type === 'RETURN' && !saleForm.related_order_id) {
    appStore.showToast('退货请选择原始销售订单', 'error'); return
  }

  // 校验仓库/仓位
  if (saleForm.order_type !== 'CONSIGN_SETTLE') {
    for (const item of activeItems) {
      if (!item.warehouse_id || !item.location_id) {
        const label = saleForm.order_type === 'RETURN' ? '退货仓库和仓位' : '仓库和仓位'
        appStore.showToast(`请为【${item.name}】选择${label}`, 'error'); return
      }
    }
  }

  // 构建确认数据
  const customer = customers.value.find(c => c.id === saleForm.customer_id)
  const total = activeItems.reduce((s, i) => s + Math.round(i.quantity * i.unit_price * 100) / 100, 0)
  const availableCredit = customer && customer.balance < 0 ? Math.abs(customer.balance) : 0
  const rebateBalance = customer?.rebate_balance || 0

  // 自动检测账套
  let autoAccountSetId = null
  if (activeItems.length > 0 && activeItems[0]?.warehouse_id) {
    const firstWarehouse = warehouses.value.find(w => w.id === parseInt(activeItems[0]?.warehouse_id))
    if (firstWarehouse?.account_set_id) autoAccountSetId = firstWarehouse.account_set_id
  }

  orderConfirm.value = {
    items: activeItems.map(i => {
      const warehouse = warehouses.value.find(w => w.id === parseInt(i.warehouse_id))
      const location = locations.value.find(l => l.id === parseInt(i.location_id))
      return {
        ...i,
        warehouse_name: warehouse?.name || i.warehouse_name || '-',
        location_code: location?.code || i.location_code || '-',
        account_set_id: warehouse?.account_set_id || null,
        account_set_name: warehouse?.account_set_name || null,
        rebate_amount: 0
      }
    }),
    customer, order_type: saleForm.order_type,
    related_order_id: saleForm.related_order_id,
    total, refunded: false,
    refund_method: 'cash',
    refund_amount: Math.abs(total),
    use_credit: false, available_credit: availableCredit,
    use_rebate: false, rebate_balance: rebateBalance,
    employee_id: saleForm.employee_id || '',
    employee_name: salespersonEmployees.value.find(s => s.id === parseInt(saleForm.employee_id))?.name || '',
    remark: saleForm.remark || '',
    payment_method: 'cash',
    account_set_id: autoAccountSetId
  }
  if (orderConfirm.value.account_set_id) {
    loadFilteredPaymentMethods(orderConfirm.value.account_set_id)
  }
  appStore.openModal('order_confirm', '确认提交订单')
}

/** 确认提交订单 */
const confirmSubmitOrder = async () => {
  if (appStore.submitting) return

  const useRebate = orderConfirm.value.use_rebate
  const totalRebate = useRebate ? orderConfirm.value.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) : 0

  if (useRebate) {
    for (const item of orderConfirm.value.items) {
      if (item.rebate_amount && item.rebate_amount > item.unit_price * item.quantity) {
        appStore.showToast(`${item.name} 的返利金额不能超过商品小计`, 'error'); return
      }
    }
  }
  if (useRebate && totalRebate > orderConfirm.value.rebate_balance) {
    appStore.showToast('返利总额超过可用余额', 'error'); return
  }

  // 退货模式过滤0数量行
  const submitItems = saleForm.order_type === 'RETURN'
    ? cart.value.filter(i => i.quantity > 0)
    : cart.value

  appStore.submitting = true
  try {
    const result = await createOrder({
      order_type: saleForm.order_type,
      customer_id: saleForm.customer_id || null,
      employee_id: orderConfirm.value.employee_id ? parseInt(orderConfirm.value.employee_id) : null,
      warehouse_id: null, location_id: null,
      related_order_id: saleForm.related_order_id || null,
      refunded: orderConfirm.value.refunded || false,
      refund_method: saleForm.order_type === 'RETURN' && orderConfirm.value.refunded ? (orderConfirm.value.refund_method || null) : null,
      refund_amount: saleForm.order_type === 'RETURN' && orderConfirm.value.refunded ? (orderConfirm.value.refund_amount || null) : null,
      use_credit: orderConfirm.value.use_credit || false,
      payment_method: orderConfirm.value.payment_method || null,
      rebate_amount: totalRebate > 0 ? totalRebate : null,
      items: submitItems.map((i, idx) => ({
        product_id: i.product_id, quantity: i.quantity, unit_price: i.unit_price,
        warehouse_id: i.warehouse_id ? parseInt(i.warehouse_id) : null,
        location_id: i.location_id ? parseInt(i.location_id) : null,
        rebate_amount: useRebate && orderConfirm.value.items[idx]?.rebate_amount ? orderConfirm.value.items[idx].rebate_amount : null
      })),
      remark: orderConfirm.value.remark || null,
      account_set_id: orderConfirm.value.account_set_id || null
    })

    let msg = '订单创建成功'
    if (result.data.rebate_used && result.data.rebate_used > 0) msg += `，已使用返利 ¥${fmt(result.data.rebate_used)}`
    if (result.data.credit_used && result.data.credit_used > 0) msg += `，已使用在账资金 ¥${fmt(result.data.credit_used)}`
    if (result.data.amount_due > 0) msg += `，还需支付 ¥${fmt(result.data.amount_due)}`
    appStore.showToast(msg)

    clearCart()
    Object.assign(saleForm, {
      employee_id: '', related_order_id: '',
      customer_id: '', order_type: 'CASH', remark: ''
    })
    returnOrderSearch.value = ''
    selectedReturnOrder.value = null
    appStore.closeModal()

    productsStore.loadProducts()
    customersStore.loadCustomers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '订单创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// ---------- Watchers ----------
watch(() => orderConfirm.value.account_set_id, (newId) => {
  loadFilteredPaymentMethods(newId)
})

watch(() => saleForm.order_type, (newType, oldType) => {
  if ((newType === 'RETURN' && oldType !== 'RETURN') || (oldType === 'RETURN' && newType !== 'RETURN')) {
    clearCart()
  }
  if (newType === 'RETURN') {
    searchReturnOrders()
  } else {
    returnOrderSearch.value = ''
    saleForm.related_order_id = ''
    selectedReturnOrder.value = null
  }
})

// ---------- 生命周期 ----------
onMounted(async () => {
  if (!products.value.length) productsStore.loadProducts()
  if (!warehouses.value.length) warehousesStore.loadWarehouses()
  if (!locations.value.length) warehousesStore.loadLocations()
  if (!customers.value.length) customersStore.loadCustomers()
  if (!salespersonEmployees.value.length) settingsStore.loadEmployees()
  if (!paymentMethods.value.length) settingsStore.loadPaymentMethods()
  try { await getAccountSets() } catch { /* ignore */ }
})

onUnmounted(() => {
  if (_returnOrderAbort) _returnOrderAbort.abort()
})
</script>
