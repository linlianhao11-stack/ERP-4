# API 索引 + 大组件重构 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 生成完整 API 端点索引文档 + 将 6 个 800+ 行大组件全面拆分为子组件和 composable

**Architecture:** Part 1 从 35 个 router 文件提取端点信息写入 `docs/API_INDEX.md`。Part 2 对 6 个大组件做全面拆分：提取弹窗为独立组件、按功能区域拆分子组件、业务逻辑抽到 composable，父组件保持 <150 行的瘦容器。所有新文件加中文注释。

**Tech Stack:** Vue 3 (Composition API, `<script setup>`) + Tailwind CSS 4 + Vite 7

**设计文档:** `docs/plans/2026-03-04-refactoring-design.md`

---

## Task 1: 生成 API 端点索引文档

**Files:**
- Create: `docs/API_INDEX.md`
- Read: `backend/app/routers/*.py` (35 个文件)

**Step 1: 从所有 router 文件提取端点信息**

遍历 `backend/app/routers/` 下所有 `.py` 文件，提取每个 `@router.get/post/put/delete/patch` 装饰器的：
- HTTP 方法
- 路径（含路由前缀）
- docstring 说明
- 权限要求（从 `Depends(require_permission(...))` 提取）

**Step 2: 写入 `docs/API_INDEX.md`**

按模块分组，每个模块一个表格，格式：

```markdown
# ERP-4 API 端点索引

> 自动生成于 2026-03-04，共 ~170 个端点

## 认证 (`/api/auth`)
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | /api/auth/login | 登录 | 无 |
...
```

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功（此 Task 无前端改动，仅文档）

---

## Task 2: 拆分 SettingsView.vue — 提取 WarehouseSettings

**Files:**
- Create: `frontend/src/components/business/settings/WarehouseSettings.vue`
- Modify: `frontend/src/views/SettingsView.vue`

**当前结构:** SettingsView.vue (1083行) 包含 4 个 Tab（常规/财务/日志/权限），其中"常规设置"Tab 内含仓库+仓位管理、收款方式、销售员、承运商 4 个模块。

**Step 1: 创建 WarehouseSettings.vue**

从 SettingsView.vue 提取"仓库与仓位管理"模块（template 约行16-170，script 中 warehouses/locations/expandedWarehouse 相关状态和函数）。

组件接口：
```vue
<!-- 仓库与仓位管理组件 -->
<script setup>
// Props: 无（组件内部从 store 加载数据）
// Emits: data-changed（仓库/仓位变更后通知父组件）
</script>
```

包含的状态和函数（从 SettingsView 迁出）：
- `warehouses`, `expandedWarehouse`, `warehouseForm`, `locationForm`
- `toggleExpandWarehouse()`, `saveWarehouse()`, `updateWarehouse()`, `deleteWarehouse()`
- `saveLocation()`, `updateLocation()`, `deleteLocation()`
- `linkAccountSet()` 相关逻辑

**Step 2: 在 SettingsView 中导入并替换**

```vue
import WarehouseSettings from '../components/business/settings/WarehouseSettings.vue'
<!-- 替换原来的仓库模块 -->
<WarehouseSettings v-if="hasPermission('settings') || hasPermission('stock_edit')" @data-changed="onWarehouseChanged" />
```

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功

---

## Task 3: 拆分 SettingsView.vue — 提取 PaymentMethodSettings + SalespersonSettings + CarrierSettings

**Files:**
- Create: `frontend/src/components/business/settings/PaymentMethodSettings.vue`
- Create: `frontend/src/components/business/settings/SalespersonSettings.vue`
- Create: `frontend/src/components/business/settings/CarrierSettings.vue`
- Modify: `frontend/src/views/SettingsView.vue`

**Step 1: 创建三个 CRUD 子组件**

每个组件从 SettingsView 提取对应的 template 块和 script 逻辑：

**PaymentMethodSettings.vue** (~120行):
- 状态: `paymentMethods`, `paymentMethodForm`, `showPaymentMethodModal`
- 函数: `loadPaymentMethods()`, `savePaymentMethod()`, `updatePaymentMethod()`, `deletePaymentMethod()`

**SalespersonSettings.vue** (~120行):
- 状态: `salespersons`, `salespersonForm`, `showSalespersonModal`
- 函数: `loadSalespersons()`, `saveSalesperson()`, `updateSalesperson()`, `deleteSalesperson()`

**CarrierSettings.vue** (~120行):
- 状态: `carriers`, `carrierForm`, `showCarrierModal`
- 函数: `loadCarriers()`, `saveCarrier()`, `updateCarrier()`, `deleteCarrier()`

**Step 2: 在 SettingsView 中导入并替换**

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功

---

## Task 4: 拆分 SettingsView.vue — 提取 PermissionSettings + LogsSettings

**Files:**
- Create: `frontend/src/components/business/settings/PermissionSettings.vue`
- Create: `frontend/src/components/business/settings/LogsSettings.vue`
- Modify: `frontend/src/views/SettingsView.vue`

**Step 1: 创建 PermissionSettings.vue**

从 SettingsView 提取"权限管理"Tab 的全部内容（template + script）：
- 状态: `users`, `permissionGroups`, `selectedUser`, `userPermissions`
- 函数: `loadUsers()`, `selectUser()`, `togglePermission()`, `savePermissions()`

**Step 2: 创建 LogsSettings.vue**

从 SettingsView 提取"系统日志"Tab：
- 状态: `logs`, `logFilter`, `logPage`
- 函数: `loadLogs()`, `exportLogs()`

**Step 3: 在 SettingsView 中导入并替换**

此时 SettingsView.vue 应缩减为 ~80 行的纯 Tab 容器。

**Step 4: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功，SettingsView 降至 ~80 行

---

## Task 5: 拆分 SalesView.vue — 创建 useSalesCart composable

**Files:**
- Create: `frontend/src/composables/useSalesCart.js`
- Modify: `frontend/src/views/SalesView.vue`

**Step 1: 创建 useSalesCart.js**

从 SalesView.vue 提取购物车核心逻辑（约80行）：

```javascript
/**
 * 销售购物车逻辑
 * 管理购物车的增删改查和计算
 */
import { ref, computed } from 'vue'

export function useSalesCart(products, warehouses) {
  const cart = ref([])
  let _cartIdCounter = 0

  // 添加商品到购物车
  const addToCart = (p, orderType, getStock) => { ... }

  // 增加数量（含退货上限检查）
  const incrementQuantity = (item, orderType) => { ... }

  // 复制购物车行（从其他仓库出货）
  const duplicateCartLine = (idx) => { ... }

  // 更新购物车商品仓库
  const updateCartWarehouse = (idx, warehouseId) => { ... }

  // 更新购物车商品仓位
  const updateCartLocation = (idx, locationId) => { ... }

  // 获取购物车商品可用库存
  const getCartStock = (item) => { ... }

  // 购物车合计金额
  const cartTotal = computed(() => cart.value.reduce(...))

  // 清空购物车
  const clearCart = () => { cart.value = [] }

  return { cart, addToCart, incrementQuantity, duplicateCartLine, updateCartWarehouse, updateCartLocation, getCartStock, cartTotal, clearCart }
}
```

**Step 2: 在 SalesView.vue 中使用 composable**

替换原来的 `cart` ref 和所有购物车相关函数为 composable 调用。

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功

---

## Task 6: 拆分 SalesView.vue — 提取 ProductSelector + ShoppingCart + OrderConfirmModal

**Files:**
- Create: `frontend/src/components/business/sales/ProductSelector.vue`
- Create: `frontend/src/components/business/sales/ShoppingCart.vue`
- Create: `frontend/src/components/business/sales/OrderConfirmModal.vue`
- Modify: `frontend/src/views/SalesView.vue`

**Step 1: 创建 ProductSelector.vue** (~250行)

从 SalesView.vue 提取左栏商品列表（template 行1-94，script 中 filteredProducts/displayProducts/productSearch 等）。

组件接口：
```vue
<script setup>
// Props
const props = defineProps({
  warehouseId: [String, Number],    // 当前筛选仓库
  locationId: [String, Number],      // 当前筛选仓位
  orderType: String,                  // 订单类型
  selectedReturnOrder: Object,        // 退货关联订单
  showVirtualStock: Boolean,          // 是否显示寄售库存
  cart: Array                         // 购物车（用于高亮已选商品）
})
// Emits
const emit = defineEmits(['add-to-cart'])
</script>
```

**Step 2: 创建 ShoppingCart.vue** (~250行)

从 SalesView.vue 提取右栏购物车（template 行96-240）。

组件接口：
```vue
<script setup>
const props = defineProps({
  cart: Array,                 // 购物车数据（v-model）
  orderType: String,
  customers: Array,
  salespersons: Array,
  warehouses: Array
})
const emit = defineEmits([
  'update:cart', 'submit', 'clear',
  'update:customerId', 'update:salespersonId', 'update:orderType',
  'duplicate-line', 'update-warehouse', 'update-location',
  'search-return-orders', 'select-return-order'
])
</script>
```

**Step 3: 创建 OrderConfirmModal.vue** (~200行)

从 SalesView.vue 提取确认弹窗（template 行243-419, script 中 orderConfirm/confirmSubmitOrder 等）。

组件接口：
```vue
<script setup>
const props = defineProps({
  visible: Boolean,
  orderConfirm: Object,
  salespersons: Array,
  paymentMethods: Array,
  accountSets: Array
})
const emit = defineEmits(['update:visible', 'confirm'])
</script>
```

**Step 4: 改造 SalesView.vue 为瘦容器**

SalesView.vue 保留：
- store 初始化、accountSets 加载
- saleForm reactive
- 退货订单搜索逻辑
- submitOrder 验证和弹窗打开
- confirmSubmitOrder API 调用
- 三个子组件编排

**Step 5: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功，SalesView 降至 ~100 行

---

## Task 7: 拆分 PurchaseOrdersPanel.vue — 创建 usePurchaseOrder composable + PurchaseOrderForm

**Files:**
- Create: `frontend/src/composables/usePurchaseOrder.js`
- Create: `frontend/src/components/business/purchase/PurchaseOrderForm.vue`
- Modify: `frontend/src/components/business/PurchaseOrdersPanel.vue`

**Step 1: 创建 usePurchaseOrder.js** (~80行)

从 PurchaseOrdersPanel 提取列表加载、筛选、排序逻辑：

```javascript
/**
 * 采购订单列表逻辑
 * 管理采购单的加载、筛选、搜索
 */
export function usePurchaseOrder() {
  // 状态: purchaseOrders, filters, search, accountSets
  // 函数: loadPurchaseOrders, debouncedLoad, handleExport
  return { ... }
}
```

**Step 2: 创建 PurchaseOrderForm.vue** (~280行)

从 PurchaseOrdersPanel 提取新建采购单弹窗（template 中 showPOCreateModal 部分 + showProductModal 部分）。

包含：供应商搜索、商品行编辑、返利/在账资金抵扣、账套选择。

组件接口：
```vue
<script setup>
const props = defineProps({
  visible: Boolean,
  suppliers: Array,
  products: Array,
  warehouses: Array,
  accountSets: Array
})
const emit = defineEmits(['update:visible', 'saved'])
</script>
```

**Step 3: 在 PurchaseOrdersPanel 中使用**

**Step 4: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功

---

## Task 8: 拆分 PurchaseOrdersPanel.vue — 提取 PurchaseOrderDetail

**Files:**
- Create: `frontend/src/components/business/purchase/PurchaseOrderDetail.vue`
- Modify: `frontend/src/components/business/PurchaseOrdersPanel.vue`
- Modify: `frontend/src/views/PurchaseView.vue` (更新导入路径)

**Step 1: 创建 PurchaseOrderDetail.vue** (~400行)

从 PurchaseOrdersPanel 提取详情弹窗、收货弹窗、退货弹窗。

组件接口：
```vue
<script setup>
const props = defineProps({
  visible: Boolean,
  purchaseOrderId: Number,
  warehouses: Array,
  accountSets: Array
})
const emit = defineEmits(['update:visible', 'data-changed', 'open-receive'])
// 内部管理：详情加载、审核/拒绝、收货表单、退货表单
</script>
```

收货流程（initReceiveItems/confirmReceive/splits 逻辑）和退货流程（openReturnModal/confirmReturn）也包含在此组件内。

**Step 2: 改造 PurchaseOrdersPanel 为瘦容器**

PurchaseOrdersPanel 保留：
- 列表 + 筛选栏（使用 usePurchaseOrder composable）
- 导入两个子组件（PurchaseOrderForm + PurchaseOrderDetail）
- defineExpose 保持不变（refresh/viewPurchaseOrder/openPurchaseReceive）

**Step 3: 更新 PurchaseView.vue 导入路径**

PurchaseOrdersPanel 位置不变（仍在 `components/business/`），PurchaseView 导入无需改。

**Step 4: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功，PurchaseOrdersPanel 降至 ~150 行

---

## Task 9: 拆分 FinanceOrdersPanel.vue — 提取三个 Tab 子组件

**Files:**
- Create: `frontend/src/components/business/finance/FinanceOrdersTab.vue`
- Create: `frontend/src/components/business/finance/FinanceUnpaidTab.vue`
- Modify: `frontend/src/components/business/FinanceOrdersPanel.vue`
- Modify: `frontend/src/views/FinanceView.vue` (更新导入路径如需要)

**Step 1: 创建 FinanceOrdersTab.vue** (~350行)

从 FinanceOrdersPanel 提取"订单明细"Tab 的全部内容：
- 订单筛选栏（类型/账套/日期/搜索）
- 订单表格（桌面 + 移动端）
- 订单详情弹窗
- 取消订单弹窗（多步向导）
- 导出功能

组件接口：
```vue
<script setup>
const props = defineProps({
  active: Boolean  // 当前是否激活（控制数据加载）
})
const emit = defineEmits(['data-changed'])
// Expose: refresh(), viewOrder(id)
</script>
```

**Step 2: 创建 FinanceUnpaidTab.vue** (~200行)

从 FinanceOrdersPanel 提取"欠款明细"Tab + 收款弹窗：
- 欠款列表
- 收款表单弹窗

组件接口：
```vue
<script setup>
const props = defineProps({
  active: Boolean
})
const emit = defineEmits(['data-changed'])
// Expose: refresh()
</script>
```

**Step 3: 改造 FinanceOrdersPanel 为瘦容器**

FinanceOrdersPanel 变为纯代理，将 props.tab 传递给对应子组件，转发 expose 方法。

**Step 4: 更新 FinanceView.vue**

确保 FinanceView 对 FinanceOrdersPanel 的 ref 调用（`viewOrder`, `refresh`）仍然正常工作。

**Step 5: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功，FinanceOrdersPanel 降至 ~60 行

---

## Task 10: 拆分 LogisticsView.vue — 创建 useShipment composable + ShipmentDetailModal

**Files:**
- Create: `frontend/src/composables/useShipment.js`
- Create: `frontend/src/components/business/logistics/ShipmentDetailModal.vue`
- Modify: `frontend/src/views/LogisticsView.vue`

**Step 1: 创建 useShipment.js** (~60行)

从 LogisticsView 提取数据加载和排序逻辑：

```javascript
/**
 * 物流数据管理
 * 管理发货列表的加载、筛选、排序
 */
export function useShipment() {
  // 状态: shipments, shipmentFilter, carriers
  // 函数: loadShipments, debouncedLoadShipments, loadCarriers
  // 计算: sortedShipments
  return { ... }
}
```

**Step 2: 创建 ShipmentDetailModal.vue** (~450行)

从 LogisticsView 提取详情弹窗（template 行176-427, script 中 shipmentDetail/shipForm/shipmentForm 等全部）。

组件接口：
```vue
<script setup>
const props = defineProps({
  visible: Boolean,
  orderId: Number,    // 打开时传入订单ID
  carriers: Array
})
const emit = defineEmits(['update:visible', 'data-changed'])
// 内部管理：详情加载、发货表单、编辑表单、SN码编辑、复制功能、物流轨迹
</script>
```

**Step 3: 改造 LogisticsView 为瘦容器**

LogisticsView 保留：
- 状态筛选 Tabs
- 搜索栏 + 列设置菜单
- 桌面表格 + 移动卡片列表
- 使用 useShipment composable
- 导入 ShipmentDetailModal

**Step 4: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功，LogisticsView 降至 ~200 行

---

## Task 11: 拆分 StockView.vue — 创建 useStock composable

**Files:**
- Create: `frontend/src/composables/useStock.js`
- Modify: `frontend/src/views/StockView.vue`

**Step 1: 创建 useStock.js** (~70行)

从 StockView 提取库存数据逻辑：

```javascript
/**
 * 库存数据管理
 * 管理库存列表的加载、筛选、排序、虚拟库存切换
 */
export function useStock() {
  // 状态: stockWarehouseFilter, showVirtualStock, virtualWarehouses, productSearch, stockSort
  // 函数: loadProductsData, onToggleVirtualStock, toggleStockSort, handleExportStock
  // 计算: filteredProducts, sortedStockRows, hasStockProducts
  return { ... }
}
```

**Step 2: 在 StockView 中使用**

替换原来散落的状态和函数。

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功

---

## Task 12: 拆分 StockView.vue — 提取 5 个弹窗组件

**Files:**
- Create: `frontend/src/components/business/stock/ProductFormModal.vue`
- Create: `frontend/src/components/business/stock/RestockModal.vue`
- Create: `frontend/src/components/business/stock/TransferModal.vue`
- Create: `frontend/src/components/business/stock/ImportModal.vue`
- Create: `frontend/src/components/business/stock/ImportPreviewModal.vue`
- Modify: `frontend/src/views/StockView.vue`

**Step 1: 创建 ProductFormModal.vue** (~150行)

组件接口：
```vue
<script setup>
const props = defineProps({
  visible: Boolean,
  product: Object  // null=新增，有值=编辑
})
const emit = defineEmits(['update:visible', 'saved'])
</script>
```

包含：SKU/名称/品牌/分类/零售价/成本价表单 + 验证 + API调用

**Step 2: 创建 RestockModal.vue** (~150行)

组件接口：
```vue
<script setup>
const props = defineProps({
  visible: Boolean
})
const emit = defineEmits(['update:visible', 'saved'])
</script>
```

包含：仓库/仓位/商品选择 + 数量/成本 + SN码区域 + 验证 + API调用

**Step 3: 创建 TransferModal.vue** (~150行)

组件接口：
```vue
<script setup>
const props = defineProps({
  visible: Boolean,
  product: Object,   // 调拨商品信息
  fromStock: Object   // 源库存信息(warehouse_id, location_id, qty)
})
const emit = defineEmits(['update:visible', 'saved'])
</script>
```

包含：调出信息展示 + 调入仓库/仓位选择 + 数量 + 验证 + API调用

**Step 4: 创建 ImportModal.vue** (~100行)

组件接口：
```vue
<script setup>
const props = defineProps({ visible: Boolean })
const emit = defineEmits(['update:visible', 'preview'])
</script>
```

包含：导入说明 + 下载模板 + 文件选择

**Step 5: 创建 ImportPreviewModal.vue** (~100行)

组件接口：
```vue
<script setup>
const props = defineProps({
  visible: Boolean,
  previewData: Object,
  file: [Object, File]
})
const emit = defineEmits(['update:visible', 'confirmed', 'cancelled'])
</script>
```

包含：预览表格 + 统计信息 + 确认/取消

**Step 6: 改造 StockView.vue 为瘦容器**

StockView 保留：
- 工具栏 + 搜索框
- 移动端卡片 + 桌面表格
- 使用 useStock composable
- 导入 5 个弹窗组件，通过 v-model:visible 控制

**Step 7: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功，StockView 降至 ~180 行

---

## Task 13: 最终验证 + 更新文档

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `AI_CONTEXT.md`

**Step 1: 全量前端构建**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`
Expected: 构建成功，0 errors

**Step 2: 后端测试**

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/ -v --ignore=tests/test_auth.py`
Expected: 79 tests passed（后端无改动，确认不受影响）

**Step 3: 检查组件行数**

Run: `wc -l` 验证所有 6 个原始组件已降至目标行数：
- SettingsView.vue: ~80 行
- SalesView.vue: ~100 行
- PurchaseOrdersPanel.vue: ~150 行
- FinanceOrdersPanel.vue: ~60 行
- LogisticsView.vue: ~200 行
- StockView.vue: ~180 行

**Step 4: 更新 CHANGELOG.md 和 AI_CONTEXT.md**

在 CHANGELOG.md 添加 v4.15.0 section。
在 AI_CONTEXT.md 更新目录结构，添加新组件和 composable。

---

## 涉及文件汇总

| 文件 | 操作 | Task |
|------|------|------|
| `docs/API_INDEX.md` | 新建 | 1 |
| `components/business/settings/WarehouseSettings.vue` | 新建 | 2 |
| `components/business/settings/PaymentMethodSettings.vue` | 新建 | 3 |
| `components/business/settings/SalespersonSettings.vue` | 新建 | 3 |
| `components/business/settings/CarrierSettings.vue` | 新建 | 3 |
| `components/business/settings/PermissionSettings.vue` | 新建 | 4 |
| `components/business/settings/LogsSettings.vue` | 新建 | 4 |
| `views/SettingsView.vue` | 重写 | 2,3,4 |
| `composables/useSalesCart.js` | 新建 | 5 |
| `components/business/sales/ProductSelector.vue` | 新建 | 6 |
| `components/business/sales/ShoppingCart.vue` | 新建 | 6 |
| `components/business/sales/OrderConfirmModal.vue` | 新建 | 6 |
| `views/SalesView.vue` | 重写 | 5,6 |
| `composables/usePurchaseOrder.js` | 新建 | 7 |
| `components/business/purchase/PurchaseOrderForm.vue` | 新建 | 7 |
| `components/business/purchase/PurchaseOrderDetail.vue` | 新建 | 8 |
| `components/business/PurchaseOrdersPanel.vue` | 重写 | 7,8 |
| `components/business/finance/FinanceOrdersTab.vue` | 新建 | 9 |
| `components/business/finance/FinanceUnpaidTab.vue` | 新建 | 9 |
| `components/business/FinanceOrdersPanel.vue` | 重写 | 9 |
| `composables/useShipment.js` | 新建 | 10 |
| `components/business/logistics/ShipmentDetailModal.vue` | 新建 | 10 |
| `views/LogisticsView.vue` | 重写 | 10 |
| `composables/useStock.js` | 新建 | 11 |
| `components/business/stock/ProductFormModal.vue` | 新建 | 12 |
| `components/business/stock/RestockModal.vue` | 新建 | 12 |
| `components/business/stock/TransferModal.vue` | 新建 | 12 |
| `components/business/stock/ImportModal.vue` | 新建 | 12 |
| `components/business/stock/ImportPreviewModal.vue` | 新建 | 12 |
| `views/StockView.vue` | 重写 | 11,12 |
| `views/FinanceView.vue` | 可能微调 | 9 |
| `views/PurchaseView.vue` | 可能微调 | 8 |

共 **新建 22 个文件**，**重写 6 个大组件**，**微调 2 个父视图**。
