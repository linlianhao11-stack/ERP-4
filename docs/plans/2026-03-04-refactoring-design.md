# API 索引 + 大组件重构 设计文档

**日期**: 2026-03-04
**版本**: v4.14.0 → v4.15.0

---

## Part 1: API 端点索引文档

**目标**: 在 `docs/API_INDEX.md` 生成完整 API 端点索引，按模块列出全部 ~167 个端点

**格式**: 每个模块一个表格，列：`方法 | 路径 | 说明 | 权限`

**数据来源**: 直接从 35 个 router 文件的装饰器和 docstring 提取

---

## Part 2: 6 大组件全面拆分

### 设计原则

- 每个原始组件变为**瘦容器**（<150行），只负责组合子组件和顶层状态
- 业务逻辑抽到 **composable**（`useXxx.js`），子组件通过 props/emits 通信
- 弹窗全部提取为独立组件，通过 `v-model:visible` 控制
- 复用已有的 `useTable.js`、`useSort.js`、`useModal.js`
- 所有新文件添加中文注释说明用途

### 拆分方案

#### 1. SettingsView.vue (1083行) → 1容器 + 5子组件

```
SettingsView.vue (~80行)  ← Tab容器
├── WarehouseSettings.vue (~280行)  ← 仓库+仓位CRUD（含accordion）
├── PaymentMethodSettings.vue (~120行)
├── SalespersonSettings.vue (~120行)
├── CarrierSettings.vue (~120行)
├── PermissionSettings.vue (~200行)  ← 权限矩阵
└── LogsSettings.vue (~100行)
```

#### 2. SalesView.vue (939行) → 1容器 + 3子组件 + 1composable

```
SalesView.vue (~100行)  ← 双栏布局容器
├── ProductSelector.vue (~250行)  ← 左栏：商品表格+筛选
├── ShoppingCart.vue (~250行)  ← 右栏：购物车列表
├── OrderConfirmModal.vue (~200行)  ← 下单确认弹窗
└── composables/useSalesCart.js (~80行)  ← 购物车增删改算逻辑
```

#### 3. PurchaseOrdersPanel.vue (1087行) → 1容器 + 2子组件 + 1composable

```
PurchaseOrdersPanel.vue (~150行)  ← 列表+筛选
├── PurchaseOrderDetail.vue (~350行)  ← 详情弹窗（含行编辑+状态操作）
├── PurchaseOrderForm.vue (~250行)  ← 新建/编辑PO表单
└── composables/usePurchaseOrder.js (~80行)  ← 加载/筛选/排序逻辑
```

#### 4. FinanceOrdersPanel.vue (876行) → 1容器 + 3子组件

```
FinanceOrdersPanel.vue (~60行)  ← Tab容器
├── FinanceOrdersTab.vue (~300行)  ← 订单列表+详情弹窗+收款
├── FinanceInvoicesTab.vue (~280行)  ← 发票列表+详情弹窗
└── FinanceStatementsTab.vue (~200行)  ← 应收应付账龄报表
```

#### 5. LogisticsView.vue (873行) → 1容器 + 3子组件 + 1composable

```
LogisticsView.vue (~150行)  ← 发货列表+筛选
├── ShipmentDetailModal.vue (~300行)  ← 详情弹窗（含发货记录卡片）
├── ShipForm.vue (~180行)  ← 新建发货表单
├── TrackingTimeline.vue (~80行)  ← 物流时间线（可复用）
└── composables/useShipment.js (~60行)  ← 发货数据加载/操作
```

#### 6. StockView.vue (841行) → 1容器 + 5子组件 + 1composable

```
StockView.vue (~120行)  ← 工具栏+库存表格
├── ProductFormModal.vue (~150行)  ← 商品新建/编辑
├── RestockModal.vue (~150行)  ← 入库（含SN码）
├── TransferModal.vue (~150行)  ← 调拨
├── ImportModal.vue (~100行)  ← 导入上传
├── ImportPreviewModal.vue (~100行)  ← 导入预览
└── composables/useStock.js (~70行)  ← 库存加载/筛选/虚拟库存
```

### 文件组织

```
frontend/src/
├── views/
│   ├── SalesView.vue          (瘦容器)
│   ├── StockView.vue          (瘦容器)
│   ├── LogisticsView.vue      (瘦容器)
│   └── SettingsView.vue       (瘦容器)
├── components/business/
│   ├── sales/
│   │   ├── ProductSelector.vue
│   │   ├── ShoppingCart.vue
│   │   └── OrderConfirmModal.vue
│   ├── purchase/
│   │   ├── PurchaseOrdersPanel.vue  (瘦容器)
│   │   ├── PurchaseOrderDetail.vue
│   │   └── PurchaseOrderForm.vue
│   ├── finance/
│   │   ├── FinanceOrdersPanel.vue   (瘦容器)
│   │   ├── FinanceOrdersTab.vue
│   │   ├── FinanceInvoicesTab.vue
│   │   └── FinanceStatementsTab.vue
│   ├── logistics/
│   │   ├── ShipmentDetailModal.vue
│   │   ├── ShipForm.vue
│   │   └── TrackingTimeline.vue
│   ├── stock/
│   │   ├── ProductFormModal.vue
│   │   ├── RestockModal.vue
│   │   ├── TransferModal.vue
│   │   ├── ImportModal.vue
│   │   └── ImportPreviewModal.vue
│   └── settings/
│       ├── WarehouseSettings.vue
│       ├── PaymentMethodSettings.vue
│       ├── SalespersonSettings.vue
│       ├── CarrierSettings.vue
│       ├── PermissionSettings.vue
│       └── LogsSettings.vue
└── composables/
    ├── useSalesCart.js
    ├── usePurchaseOrder.js
    ├── useShipment.js
    └── useStock.js
```

### 总结

| 原组件 | 原行数 | 拆为 | 容器行数 |
|--------|--------|------|---------|
| SettingsView | 1083 | 1+5 | ~80 |
| PurchaseOrdersPanel | 1087 | 1+2+composable | ~150 |
| SalesView | 939 | 1+3+composable | ~100 |
| FinanceOrdersPanel | 876 | 1+3 | ~60 |
| LogisticsView | 873 | 1+3+composable | ~150 |
| StockView | 841 | 1+5+composable | ~120 |

新增 **22 个子组件 + 4 个 composable**，所有原始组件降到 150 行以下。
