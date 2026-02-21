import {
  LayoutDashboard, ShoppingCart, Package, ShoppingBag,
  ArrowLeftRight, Truck, Wallet, Users, Settings
} from 'lucide-vue-next'

export const iconMap = {
  dashboard: LayoutDashboard,
  sales: ShoppingCart,
  stock: Package,
  purchase: ShoppingBag,
  consignment: ArrowLeftRight,
  logistics: Truck,
  finance: Wallet,
  customers: Users,
  settings: Settings
}

export const menuItems = [
  { key: 'dashboard', name: '首页', icon: '📊', perm: 'dashboard' },
  { key: 'sales', name: '销售', icon: '🛒', perm: 'sales' },
  { key: 'stock', name: '库存', icon: '📦', perm: 'stock_view' },
  { key: 'purchase', name: '采购', icon: '🛍️', perm: 'purchase' },
  { key: 'consignment', name: '寄售', icon: '🔄', perm: 'consignment' },
  { key: 'logistics', name: '物流', icon: '🚚', perm: 'logistics' },
  { key: 'finance', name: '财务', icon: '💰', perm: 'finance' },
  { key: 'customers', name: '客户', icon: '👥', perm: 'customer' },
  { key: 'settings', name: '设置', icon: '⚙️', perm: '_any' }
]

export const bottomNavItems = [
  { key: 'dashboard', name: '首页', icon: '📊', perm: 'dashboard' },
  { key: 'sales', name: '销售', icon: '🛒', perm: 'sales' },
  { key: 'stock', name: '库存', icon: '📦', perm: 'stock_view' },
  { key: 'consignment', name: '寄售', icon: '🔄', perm: 'consignment' },
  { key: 'logistics', name: '物流', icon: '🚚', perm: 'logistics' },
  { key: 'finance', name: '财务', icon: '💰', perm: 'finance' }
]

export const allPermissions = [
  { key: 'dashboard', name: '首页' },
  { key: 'sales', name: '销售开单' },
  { key: 'logistics', name: '物流管理' },
  { key: 'consignment', name: '寄售管理' },
  { key: 'stock_view', name: '查看库存' },
  { key: 'stock_edit', name: '库存操作' },
  { key: 'purchase', name: '采购下单' },
  { key: 'purchase_approve', name: '采购审核' },
  { key: 'purchase_pay', name: '采购付款' },
  { key: 'purchase_receive', name: '采购收货' },
  { key: 'customer', name: '客户管理' },
  { key: 'finance', name: '财务查看' },
  { key: 'finance_confirm', name: '确认收款' },
  { key: 'logs', name: '出入库日志' },
  { key: 'settings', name: '系统设置' }
]

export const orderTypeNames = {
  CASH: '现款', CREDIT: '账期',
  CONSIGN_OUT: '寄售调拨', CONSIGN_SETTLE: '寄售结算',
  CONSIGN_RETURN: '寄售退货', RETURN: '退货'
}

export const orderTypeBadges = {
  CASH: 'badge badge-green', CREDIT: 'badge badge-yellow',
  CONSIGN_OUT: 'badge badge-purple', CONSIGN_SETTLE: 'badge badge-blue',
  CONSIGN_RETURN: 'badge badge-orange', RETURN: 'badge badge-red'
}

export const logTypeNames = {
  RESTOCK: '入库', SALE: '销售出库', RETURN: '退货入库',
  CONSIGN_OUT: '寄售调拨', CONSIGN_SETTLE: '寄售结算', CONSIGN_RETURN: '寄售退货',
  ADJUST: '库存调整', PURCHASE_IN: '采购入库', PURCHASE_RETURN: '采购退货',
  TRANSFER_OUT: '调拨出库', TRANSFER_IN: '调拨入库',
  RESERVE: '库存预留', RESERVE_CANCEL: '取消预留'
}

export const logTypeBadges = {
  RESTOCK: 'badge badge-green', SALE: 'badge badge-blue',
  RETURN: 'badge badge-yellow', CONSIGN_OUT: 'badge badge-purple',
  CONSIGN_SETTLE: 'badge badge-blue', CONSIGN_RETURN: 'badge badge-orange',
  ADJUST: 'badge badge-gray', PURCHASE_IN: 'badge badge-green',
  PURCHASE_RETURN: 'badge badge-red', TRANSFER_OUT: 'badge badge-orange',
  TRANSFER_IN: 'badge badge-green', RESERVE: 'badge badge-yellow',
  RESERVE_CANCEL: 'badge badge-gray'
}

export const purchaseStatusNames = {
  pending_review: '待审核', pending: '待付款', paid: '在途',
  partial: '部分到货', completed: '已完成', cancelled: '已取消', rejected: '已拒绝',
  returned: '已退货'
}

export const purchaseStatusBadges = {
  pending_review: 'badge badge-purple', pending: 'badge badge-yellow',
  paid: 'badge badge-blue', partial: 'badge badge-orange',
  completed: 'badge badge-green', cancelled: 'badge badge-gray', rejected: 'badge badge-red',
  returned: 'badge badge-orange'
}

export const shipmentStatusBadges = {
  pending: 'bg-[#f5f5f7] text-[#6e6e73]',
  shipped: 'bg-[#e8f4fd] text-[#0071e3]',
  in_transit: 'bg-[#fff8e1] text-[#ff9f0a]',
  signed: 'bg-[#e8f8ee] text-[#34c759]',
  problem: 'bg-[#ffeaee] text-[#ff3b30]'
}

export const shippingStatusNames = {
  pending: '待发货', partial: '部分发货',
  completed: '已完成', cancelled: '已取消'
}

export const shippingStatusBadges = {
  pending: 'badge badge-yellow', partial: 'badge badge-orange',
  completed: 'badge badge-green', cancelled: 'badge badge-gray'
}

export const IDLE_TIMEOUT = 4 * 60 * 60 * 1000
