/**
 * 销售购物车 composable
 * 管理购物车的增删改查和金额计算
 * 依赖通过参数注入，保持纯逻辑性和可测试性
 */
import { ref, computed } from 'vue'

export function useSalesCart() {
  /** 购物车数据 */
  const cart = ref([])
  /** 购物车行唯一 ID 计数器 */
  let _cartIdCounter = 0

  /**
   * 复制购物车行（从其他仓库再出一行）
   * @param {number} idx - 行索引
   * @param {import('vue').Ref<Array>} products - 全部商品列表 ref
   */
  const duplicateCartLine = (idx, products) => {
    const item = cart.value[idx]
    const fullProduct = products.value.find(prod => prod.id === item.product_id)
    cart.value.splice(idx + 1, 0, {
      _id: ++_cartIdCounter,
      product_id: item.product_id,
      name: item.name,
      unit_price: item.unit_price,
      quantity: 1,
      warehouse_id: '',
      location_id: '',
      stocks: fullProduct?.stocks || item.stocks || []
    })
  }

  /** 购物车合计金额 */
  const cartTotal = computed(() =>
    cart.value.reduce((s, i) => s + Math.round(i.quantity * i.unit_price * 100) / 100, 0)
  )

  /**
   * 从搜索下拉添加商品到购物车（工作台模式）
   * @param {Object} product - 商品对象（含 id/name/sku/retail_price/cost_price/stocks）
   * @param {Object} stockRow - 搜索下拉中选中的仓库/仓位行
   * @param {string} orderType - 订单类型
   * @param {Object} appStore - 全局应用 store
   */
  const addFromSearch = (product, stockRow, orderType, appStore) => {
    if (orderType !== 'CREDIT' && stockRow.available_qty <= 0) {
      appStore.showToast('库存不足', 'error')
      return
    }
    const existing = cart.value.find(
      c => c.product_id === product.id &&
           c.warehouse_id == stockRow.warehouse_id &&
           c.location_id == stockRow.location_id
    )
    if (existing) {
      existing.quantity++
      return existing
    }
    const item = {
      _id: ++_cartIdCounter,
      product_id: product.id,
      name: product.name,
      sku: product.sku || '',
      unit_price: product.retail_price,
      cost_price: product.cost_price || 0,
      quantity: 1,
      warehouse_id: stockRow.warehouse_id,
      warehouse_name: stockRow.warehouse_name || '',
      location_id: stockRow.location_id,
      location_code: stockRow.location_code || '',
      location_color: stockRow.location_color || 'blue',
      is_virtual_stock: !!stockRow.is_virtual,
      stocks: product.stocks || []
    }
    cart.value.push(item)
    return item
  }

  /**
   * 退货模式：从原始订单填充可退商品到购物车
   * @param {Object} orderData - 原始订单详情（含 items）
   * @param {import('vue').Ref<Array>} products - 全部商品列表 ref
   */
  const populateReturnItems = (orderData, products) => {
    cart.value = []
    if (!orderData?.items) return
    orderData.items.forEach(item => {
      const availableQty = item.available_return_quantity || 0
      if (availableQty <= 0) return
      const product = products.value.find(p => p.id === item.product_id)
      if (!product) return
      cart.value.push({
        _id: ++_cartIdCounter,
        product_id: item.product_id,
        name: product.name,
        sku: product.sku || '',
        unit_price: Math.abs(item.unit_price),
        cost_price: product.cost_price || 0,
        quantity: 0,
        max_return_qty: availableQty,
        original_quantity: Math.abs(item.quantity),
        returned_quantity: item.returned_quantity || 0,
        warehouse_id: '',
        warehouse_name: '',
        location_id: '',
        location_code: '',
        location_color: 'blue',
        stocks: product.stocks || []
      })
    })
  }

  /** 清空购物车 */
  const clearCart = () => {
    cart.value = []
  }

  return {
    cart,
    addFromSearch,
    populateReturnItems,
    duplicateCartLine,
    cartTotal,
    clearCart
  }
}
