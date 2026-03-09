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
   * 添加商品到购物车
   * @param {Object} p - 商品对象
   * @param {string} orderType - 订单类型（CASH/CREDIT/RETURN 等）
   * @param {Function} getStock - 获取库存的函数
   * @param {import('vue').Ref<Array>} products - 全部商品列表 ref
   * @param {Object} appStore - 全局应用 store（用于 toast 提示）
   */
  const addToCart = (p, orderType, getStock, products, appStore) => {
    const stock = getStock(p)
    // 非退货模式下库存不足不能添加
    if (stock <= 0 && orderType !== 'RETURN') {
      appStore.showToast('库存不足', 'error')
      return
    }

    if (orderType === 'RETURN') {
      // 退货模式：检查退货上限
      const e = cart.value.find(c => c.product_id === p.id)
      const maxQty = p.max_return_qty || p.original_quantity || 0
      if (e) {
        if (e.quantity >= maxQty) {
          appStore.showToast(`最多只能退${maxQty}件`, 'error')
          return
        }
        e.quantity++
      } else {
        cart.value.push({
          _id: ++_cartIdCounter,
          product_id: p.id,
          name: p.name,
          unit_price: p.retail_price,
          quantity: 1,
          max_return_qty: maxQty,
          warehouse_id: p.warehouse_id || '',
          location_id: p.location_id || '',
          stocks: p.stocks || []
        })
      }
    } else {
      // 普通模式：先找无仓库行，再找同商品最后一行
      const e = cart.value.find(c => c.product_id === p.id && (!c.warehouse_id || c.warehouse_id === ''))
      if (e) {
        e.quantity++
      } else {
        const hasLine = cart.value.some(c => c.product_id === p.id)
        if (hasLine) {
          const last = cart.value.filter(c => c.product_id === p.id).pop()
          last.quantity++
        } else {
          const fullProduct = products.value.find(prod => prod.id === p.id)
          cart.value.push({
            _id: ++_cartIdCounter,
            product_id: p.id,
            name: p.name,
            unit_price: p.retail_price,
            quantity: 1,
            warehouse_id: '',
            location_id: '',
            stocks: fullProduct?.stocks || []
          })
        }
      }
    }
  }

  /**
   * 增加数量（含退货上限检查）
   * @param {Object} item - 购物车行
   * @param {string} orderType - 订单类型
   * @param {Object} appStore - 全局应用 store
   */
  const incrementQuantity = (item, orderType, appStore) => {
    if (orderType === 'RETURN' && item.max_return_qty && item.quantity >= item.max_return_qty) {
      appStore.showToast('最多只能退' + item.max_return_qty + '件', 'error')
    } else {
      item.quantity++
    }
  }

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

  /**
   * 更新购物车商品仓库（同时清空仓位）
   * @param {number} idx - 行索引
   */
  const updateCartWarehouse = (idx) => {
    cart.value[idx].location_id = ''
  }

  /**
   * 更新购物车商品仓位
   * @param {number} idx - 行索引
   * @param {string|number} locationId - 仓位 ID
   */
  const updateCartLocation = (idx, locationId) => {
    cart.value[idx].location_id = locationId
  }

  /**
   * 获取购物车商品在指定仓库/仓位的可用库存
   * @param {Object} item - 购物车行
   * @returns {number} 可用库存数量
   */
  const getCartStock = (item) => {
    if (!item.warehouse_id || !item.location_id) return 0
    const stock = item.stocks?.find(
      s => s.warehouse_id === parseInt(item.warehouse_id) && s.location_id === parseInt(item.location_id)
    )
    return stock ? (stock.available_qty ?? stock.quantity) : 0
  }

  /** 购物车合计金额 */
  const cartTotal = computed(() =>
    cart.value.reduce((s, i) => s + Math.round(i.quantity * i.unit_price * 100) / 100, 0)
  )

  /** 清空购物车 */
  const clearCart = () => {
    cart.value = []
  }

  return {
    cart,
    addToCart,
    incrementQuantity,
    duplicateCartLine,
    updateCartWarehouse,
    updateCartLocation,
    getCartStock,
    cartTotal,
    clearCart
  }
}
