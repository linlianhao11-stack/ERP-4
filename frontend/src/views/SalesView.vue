<!--
  销售页面 - 瘦容器
  编排 ProductSelector、ShoppingCart、OrderConfirmModal 三个子组件
  管理全局状态、退货订单搜索逻辑、订单提交流程
-->
<template>
  <div class="md:flex md:gap-5 md:items-start">
    <!-- 左栏：商品选择器 -->
    <ProductSelector
      ref="productSelectorRef"
      :products="products"
      :warehouses="warehouses"
      :virtual-warehouses="virtualWarehouses"
      :filter-locations="filterLocations"
      :warehouse-id="saleForm.warehouse_id"
      :location-id="saleForm.location_id"
      :order-type="saleForm.order_type"
      :selected-return-order="selectedReturnOrder"
      :show-virtual-stock="showVirtualStock"
      :cart="cart"
      @update:warehouse-id="saleForm.warehouse_id = $event"
      @update:location-id="saleForm.location_id = $event"
      @update:show-virtual-stock="onToggleVirtualStock"
      @add-to-cart="handleAddToCart"
    />

    <!-- 右栏：购物车 -->
    <ShoppingCart
      :cart="cart"
      :order-type="saleForm.order_type"
      :customer-id="saleForm.customer_id"
      :salesperson-id="saleForm.salesperson_id"
      :customers="customers"
      :salespersons="salespersons"
      :warehouses="warehouses"
      :cart-total="cartTotal"
      :need-customer="needCustomer"
      :return-order-search="returnOrderSearch"
      :return-order-dropdown="returnOrderDropdown"
      :filtered-return-orders="filteredReturnOrders"
      :selected-return-order="selectedReturnOrder"
      :get-cart-stock="getCartStock"
      @clear="clearCart"
      @submit="submitOrder"
      @remove-item="idx => cart.splice(idx, 1)"
      @duplicate-line="idx => duplicateCartLine(idx, products)"
      @increment-quantity="item => incrementQuantity(item, saleForm.order_type, appStore)"
      @update-warehouse="(idx, wid) => updateCartWarehouse(idx)"
      @update-location="(idx, lid) => updateCartLocation(idx, lid)"
      @update:customer-id="saleForm.customer_id = $event"
      @update:salesperson-id="saleForm.salesperson_id = $event"
      @update:order-type="saleForm.order_type = $event"
      @update:return-order-search="returnOrderSearch = $event"
      @update:return-order-dropdown="returnOrderDropdown = $event"
      @search-return-orders="searchReturnOrders"
      @select-return-order="selectReturnOrder"
    />
  </div>

  <!-- 订单确认弹窗 -->
  <OrderConfirmModal
    :visible="appStore.modal.show && appStore.modal.type === 'order_confirm'"
    :order-confirm="orderConfirm"
    :salespersons="salespersons"
    :payment-methods="paymentMethods"
    :account-sets="accountSets"
    :submitting="appStore.submitting"
    @update:visible="!$event && appStore.closeModal()"
    @confirm="confirmSubmitOrder"
  />
</template>

<script setup>
/**
 * 销售页面瘦容器
 * 负责：store 初始化、状态编排、退货搜索、订单提交
 */
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'
import { useProductsStore } from '../stores/products'
import { useWarehousesStore } from '../stores/warehouses'
import { useCustomersStore } from '../stores/customers'
import { useSettingsStore } from '../stores/settings'
import { useFormat } from '../composables/useFormat'
import { useSalesCart } from '../composables/useSalesCart'
import { getOrders, getOrder, createOrder } from '../api/orders'
import { getWarehouses } from '../api/warehouses'
import { getAccountSets } from '../api/accounting'
import { fuzzyMatchAny } from '../utils/helpers'
import ProductSelector from '../components/business/sales/ProductSelector.vue'
import ShoppingCart from '../components/business/sales/ShoppingCart.vue'
import OrderConfirmModal from '../components/business/sales/OrderConfirmModal.vue'

// ---------- Store 初始化 ----------
const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const customersStore = useCustomersStore()
const settingsStore = useSettingsStore()

const { fmt } = useFormat()

// Store 别名
const products = computed(() => productsStore.products)
const warehouses = computed(() => warehousesStore.warehouses)
const locations = computed(() => warehousesStore.locations)
const customers = computed(() => customersStore.customers)
const salespersons = computed(() => settingsStore.salespersons)
const paymentMethods = computed(() => settingsStore.paymentMethods)

// ---------- 购物车 composable ----------
const {
  cart, addToCart, incrementQuantity, duplicateCartLine,
  updateCartWarehouse, updateCartLocation, getCartStock,
  cartTotal, clearCart
} = useSalesCart()

// ---------- 本地状态 ----------
const accountSets = ref([])
const showVirtualStock = ref(false)
const virtualWarehouses = ref([])
const productSelectorRef = ref(null)

const saleForm = reactive({
  order_type: 'CASH',
  warehouse_id: '',
  location_id: '',
  customer_id: '',
  salesperson_id: '',
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
  use_rebate: false, rebate_balance: 0, salesperson_id: '',
  remark: '', payment_method: 'cash', account_set_id: null
})

// ---------- 计算属性 ----------
/** 是否必须选择客户 */
const needCustomer = computed(() => ['CASH', 'CREDIT', 'CONSIGN_OUT', 'CONSIGN_SETTLE', 'RETURN'].includes(saleForm.order_type))

/** 过滤后的退货订单列表 */
const filteredReturnOrders = computed(() => {
  const kw = returnOrderSearch.value
  if (!kw) return salesOrders.value.slice(0, 20)
  return salesOrders.value.filter(o => fuzzyMatchAny([o.order_no, o.customer_name], kw)).slice(0, 20)
})

/** 筛选仓位列表（根据选中仓库） */
const filterLocations = computed(() => {
  if (!saleForm.warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(saleForm.warehouse_id)
})

// ---------- 函数 ----------

/** 切换寄售库存显示，首次开启时加载虚拟仓库 */
const onToggleVirtualStock = async (val) => {
  showVirtualStock.value = val
  if (val && !virtualWarehouses.value.length) {
    try {
      const { data } = await getWarehouses({ include_virtual: true })
      virtualWarehouses.value = data.filter(w => w.is_virtual)
    } catch (e) {
      console.error(e)
      appStore.showToast(e.response?.data?.detail || '加载数据失败', 'error')
    }
  }
}

/** 添加商品到购物车（桥接子组件事件到 composable） */
const handleAddToCart = (p) => {
  const getStock = productSelectorRef.value?.getStock || (() => 0)
  addToCart(p, saleForm.order_type, getStock, products, appStore)
}

/** 搜索退货关联订单（含请求取消） */
let _returnOrderAbort = null
const searchReturnOrders = async () => {
  if (saleForm.order_type !== 'RETURN') return
  if (_returnOrderAbort) _returnOrderAbort.abort()
  const controller = new AbortController()
  _returnOrderAbort = controller
  try {
    const { data } = await getOrders({ limit: 200 }, { signal: controller.signal })
    salesOrders.value = data.filter(o => ['CASH', 'CREDIT'].includes(o.order_type))
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
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
  }
}

/** 提交订单前校验并打开确认弹窗 */
const submitOrder = () => {
  if (!cart.value.length) return

  // 校验数量和单价
  for (const item of cart.value) {
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
    for (let i = 0; i < cart.value.length; i++) {
      if (!cart.value[i].warehouse_id || !cart.value[i].location_id) {
        const label = saleForm.order_type === 'RETURN' ? '退货仓库和仓位' : '仓库和仓位'
        appStore.showToast(`请为【${cart.value[i].name}】选择${label}`, 'error'); return
      }
    }
  }

  // 构建确认数据
  const customer = customers.value.find(c => c.id === saleForm.customer_id)
  const total = cart.value.reduce((s, i) => s + Math.round(i.quantity * i.unit_price * 100) / 100, 0)
  const availableCredit = customer && customer.balance < 0 ? Math.abs(customer.balance) : 0
  const rebateBalance = customer?.rebate_balance || 0

  // 自动检测账套
  let autoAccountSetId = null
  if (cart.value.length > 0 && cart.value[0]?.warehouse_id) {
    const firstWarehouse = warehouses.value.find(w => w.id === parseInt(cart.value[0]?.warehouse_id))
    if (firstWarehouse?.account_set_id) autoAccountSetId = firstWarehouse.account_set_id
  }

  orderConfirm.value = {
    items: cart.value.map(i => {
      const warehouse = warehouses.value.find(w => w.id === parseInt(i.warehouse_id))
      const location = locations.value.find(l => l.id === parseInt(i.location_id))
      return { ...i, warehouse_name: warehouse?.name || '-', location_code: location?.code || '-', rebate_amount: 0 }
    }),
    customer, order_type: saleForm.order_type,
    related_order_id: saleForm.related_order_id,
    total, refunded: false,
    use_credit: false, available_credit: availableCredit,
    use_rebate: false, rebate_balance: rebateBalance,
    salesperson_id: saleForm.salesperson_id || '',
    salesperson_name: salespersons.value.find(s => s.id === parseInt(saleForm.salesperson_id))?.name || '',
    remark: '', payment_method: 'cash',
    account_set_id: autoAccountSetId
  }
  appStore.openModal('order_confirm', '确认提交订单')
}

/** 确认提交订单（调用 API） */
const confirmSubmitOrder = async () => {
  if (appStore.submitting) return

  const useRebate = orderConfirm.value.use_rebate
  const totalRebate = useRebate ? orderConfirm.value.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) : 0

  // 返利校验
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

  appStore.submitting = true
  try {
    const result = await createOrder({
      order_type: saleForm.order_type,
      customer_id: saleForm.customer_id || null,
      salesperson_id: orderConfirm.value.salesperson_id ? parseInt(orderConfirm.value.salesperson_id) : null,
      warehouse_id: null, location_id: null,
      related_order_id: saleForm.related_order_id || null,
      refunded: orderConfirm.value.refunded || false,
      use_credit: orderConfirm.value.use_credit || false,
      payment_method: orderConfirm.value.payment_method || null,
      rebate_amount: totalRebate > 0 ? totalRebate : null,
      items: cart.value.map((i, idx) => ({
        product_id: i.product_id, quantity: i.quantity, unit_price: i.unit_price,
        warehouse_id: i.warehouse_id ? parseInt(i.warehouse_id) : null,
        location_id: i.location_id ? parseInt(i.location_id) : null,
        rebate_amount: useRebate && orderConfirm.value.items[idx]?.rebate_amount ? orderConfirm.value.items[idx].rebate_amount : null
      })),
      remark: orderConfirm.value.remark || null,
      account_set_id: orderConfirm.value.account_set_id || null
    })

    // 构建成功提示
    let msg = '订单创建成功'
    if (result.data.rebate_used && result.data.rebate_used > 0) msg += `，已使用返利 ¥${fmt(result.data.rebate_used)}`
    if (result.data.credit_used && result.data.credit_used > 0) msg += `，已使用在账资金 ¥${fmt(result.data.credit_used)}`
    if (result.data.amount_due > 0) msg += `，还需支付 ¥${fmt(result.data.amount_due)}`
    appStore.showToast(msg)

    // 重置状态
    clearCart()
    Object.assign(saleForm, {
      warehouse_id: '', location_id: '', salesperson_id: '',
      related_order_id: '', customer_id: '', order_type: 'CASH'
    })
    returnOrderSearch.value = ''
    selectedReturnOrder.value = null
    appStore.closeModal()

    // 重新加载数据
    productsStore.loadProducts()
    customersStore.loadCustomers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '订单创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// ---------- Watchers ----------
watch(() => saleForm.warehouse_id, () => { saleForm.location_id = '' })

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
  if (!salespersons.value.length) settingsStore.loadSalespersons()
  if (!paymentMethods.value.length) settingsStore.loadPaymentMethods()
  try {
    const { data } = await getAccountSets()
    accountSets.value = data
  } catch (e) { /* ignore */ }
})

onUnmounted(() => {
  if (_returnOrderAbort) _returnOrderAbort.abort()
})
</script>
