import {
  LayoutDashboard, ShoppingCart, Package, ShoppingBag,
  ArrowLeftRight, Truck, Wallet, Users, Settings, BookOpen
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
  accounting: BookOpen,
  settings: Settings
}

export const menuItems = [
  { key: 'dashboard', name: '首页', perm: 'dashboard', group: '业务' },
  { key: 'sales', name: '销售', perm: 'sales', group: '业务' },
  { key: 'stock', name: '库存', perm: 'stock_view', group: '业务' },
  { key: 'purchase', name: '采购', perm: 'purchase', group: '业务' },
  { key: 'consignment', name: '寄售', perm: 'consignment', group: '业务' },
  { key: 'logistics', name: '物流', perm: 'logistics', group: '业务' },
  { key: 'customers', name: '客户', perm: 'customer', group: '业务' },
  { key: 'finance', name: '财务', perm: 'finance', group: '财务' },
  { key: 'accounting', name: '会计', perm: 'accounting_view', group: '财务' },
  { key: 'settings', name: '设置', perm: '_any', group: '系统' }
]

export const bottomNavItems = [
  { key: 'dashboard', name: '首页', perm: 'dashboard' },
  { key: 'sales', name: '销售', perm: 'sales' },
  { key: 'stock', name: '库存', perm: 'stock_view' },
  { key: 'consignment', name: '寄售', perm: 'consignment' },
  { key: 'logistics', name: '物流', perm: 'logistics' },
  { key: 'finance', name: '财务', perm: 'finance' }
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
  { key: 'finance_pay', name: '确认付款' },
  { key: 'finance_rebate', name: '返利管理' },
  { key: 'logs', name: '出入库日志' },
  { key: 'settings', name: '系统设置' },
  { key: 'accounting_view', name: '会计查看' },
  { key: 'accounting_edit', name: '会计录入' },
  { key: 'accounting_approve', name: '凭证审核' },
  { key: 'accounting_post', name: '凭证过账' },
  { key: 'period_end', name: '期末处理' },
  { key: 'accounting_ar_view', name: '应收查看' },
  { key: 'accounting_ar_edit', name: '应收编辑' },
  { key: 'accounting_ar_confirm', name: '应收确认' },
  { key: 'accounting_ap_view', name: '应付查看' },
  { key: 'accounting_ap_edit', name: '应付编辑' },
  { key: 'accounting_ap_confirm', name: '应付确认' },
]

export const permissionGroups = [
  { label: '首页', icon: 'dashboard', main: 'dashboard', children: [] },
  { label: '销售管理', icon: 'sales', main: 'sales', children: [] },
  { label: '库存管理', icon: 'stock', main: 'stock_view', children: [
    { key: 'stock_edit', name: '库存操作（入库/调拨/盘点）' },
  ]},
  { label: '采购管理', icon: 'purchase', main: 'purchase', children: [
    { key: 'purchase_approve', name: '采购审核' },
    { key: 'purchase_pay', name: '采购付款' },
    { key: 'purchase_receive', name: '采购收货' },
  ]},
  { label: '寄售管理', icon: 'consignment', main: 'consignment', children: [] },
  { label: '物流管理', icon: 'logistics', main: 'logistics', children: [] },
  { label: '财务管理', icon: 'finance', main: 'finance', children: [
    { key: 'finance_confirm', name: '确认收款' },
    { key: 'finance_pay', name: '确认付款' },
    { key: 'finance_rebate', name: '返利管理' },
  ]},
  { label: '会计管理', icon: 'accounting', main: 'accounting_view', children: [
    { key: 'accounting_edit', name: '会计录入' },
    { key: 'accounting_approve', name: '凭证审核' },
    { key: 'accounting_post', name: '凭证过账' },
    { key: 'period_end', name: '期末处理' },
    { key: 'accounting_ar_view', name: '应收查看' },
    { key: 'accounting_ar_edit', name: '应收编辑' },
    { key: 'accounting_ar_confirm', name: '应收确认' },
    { key: 'accounting_ap_view', name: '应付查看' },
    { key: 'accounting_ap_edit', name: '应付编辑' },
    { key: 'accounting_ap_confirm', name: '应付确认' },
  ]},
  { label: '客户管理', icon: 'customers', main: 'customer', children: [] },
  { label: '系统设置', icon: 'settings', main: 'settings', children: [
    { key: 'logs', name: '操作日志' },
  ]},
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

export const shipmentStatusNames = {
  pending: '待发货',
  shipped: '已发货',
  in_transit: '运输中',
  signed: '已签收',
  problem: '异常'
}

export const shipmentStatusBadges = {
  pending: 'badge badge-gray',
  shipped: 'badge badge-blue',
  in_transit: 'badge badge-yellow',
  signed: 'badge badge-green',
  problem: 'badge badge-red'
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
