# FinanceOrdersTab 组件拆分设计

## 背景

`FinanceOrdersTab.vue` 当前 1226 行，包含订单列表、订单详情弹窗、取消订单向导、退货表单、导出逻辑。取消和退货流程后续还会扩展（审批流、更多退款方式、批量取消等），需要拆分以支持独立演进。

## 方案

按弹窗边界拆分为 3 个组件：

```
frontend/src/components/business/finance/
├── FinanceOrdersTab.vue          (~650 行，列表+筛选+表格+导出+取消预览判断)
├── FinanceOrderDetailModal.vue   (~350 行，订单详情+退货表单)
└── FinanceOrderCancelWizard.vue  (~230 行，多步取消向导)
```

## 组件通信

```
FinanceOrdersTab (父组件)
│
│  持有状态：
│    selectedOrderId, showDetail
│    cancelPreviewData, showCancel
│
│  handleCancelOrder(orderId):
│    1. 调用 cancelPreview API
│    2. 简单路径 → customConfirm → cancelOrder → 关闭详情 → 刷新
│    3. 复杂路径 → 关闭详情 → 设置 previewData → showCancel = true
│
├─ <FinanceOrderDetailModal
│     :order-id="selectedOrderId"
│     v-model:visible="showDetail"
│     @cancel-order="handleCancelOrder"
│     @data-changed="loadOrders"
│     @open-payment="emit('open-payment', $event)"
│   />
│
└─ <FinanceOrderCancelWizard
      :preview-data="cancelPreviewData"
      v-model:visible="showCancel"
      @cancelled="onCancelDone"
      @data-changed="emit('data-changed')"
    />
```

## 各组件职责

### FinanceOrdersTab.vue（主组件 ~650 行）

**保留：**
- 筛选工具栏（移动端日期预设 + 桌面端筛选栏）
- 桌面端表格 + 行展开商品明细
- 移动端卡片列表
- 分页 + 排序 + 列配置
- 导出逻辑
- 取消预览判断（简单/复杂路径分流）

**状态：**
- 列表相关：`allOrders`, `orderFilter`, `orderSort`, `expandedRows`, `expandedItems`
- 弹窗控制：`selectedOrderId`, `showDetail`, `cancelPreviewData`, `showCancel`

**暴露方法不变：** `defineExpose({ refresh, viewOrder })`

`viewOrder(id)` 实现改为：设置 `selectedOrderId = id`，`showDetail = true`

### FinanceOrderDetailModal.vue（新组件 ~350 行）

**Props：**
- `orderId: Number` — 要查看的订单 ID
- `visible: Boolean` — v-model 双向绑定

**内部状态：**
- `orderDetail` — reactive，详情数据
- `isDetailExpanded` — 弹窗展开/收起
- `showReturnForm`, `returnForm`, `returnSubmitting` — 退货相关

**数据加载：** watch `visible`，当变为 true 时调用 `getOrder(orderId)` 加载详情

**Emits：**
- `update:visible` — 关闭弹窗
- `cancel-order, orderId` — 请求取消订单（转发给父组件处理）
- `data-changed` — 退货成功后通知刷新
- `open-payment, customerId` — 转发收款请求

**包含逻辑：**
- 订单基本信息展示
- 商品明细按账套分组（`detailItemsByAccountSet` 计算属性）
- 关联应收单、物流卡片
- 退货表单（`openReturnForm`, `submitReturn`, `cancelReturnForm`）
- `canReturn`, `canSubmitReturn` 计算属性

### FinanceOrderCancelWizard.vue（新组件 ~230 行）

**Props：**
- `previewData: Object` — 父组件传入的 cancelPreview 结果
- `visible: Boolean` — v-model 双向绑定

**内部状态：**
- `cancelStep` — 当前步骤 (1/2/3)
- `cancelForm` — reactive，表单数据（refund_amount, refund_method 等）

**数据初始化：** watch `visible`，当变为 true 时根据 `previewData` 初始化 `cancelForm`（设置 item_allocations、默认金额等）

**Emits：**
- `update:visible` — 关闭向导
- `cancelled` — 取消成功，父组件关闭所有弹窗并刷新
- `data-changed` — 通知上层数据变更

**包含逻辑：**
- 3 步向导 UI（确认商品 → 财务分配 → 退款方式）
- `onItemPaidChange`, `onItemRebateChange`, `recalcCancelTotals`
- `nextCancelStep`, `prevCancelStep`
- `confirmCancel`（提交 cancelOrder API）
- `cancelStepCount` 计算属性

**不包含：** 简单取消路径的判断逻辑（留在父组件）

## 已识别的风险点及解法

| 风险 | 解法 |
|------|------|
| 详情弹窗中"取消订单"按钮需跨组件触发向导 | 详情 emit `cancel-order` → 父组件判断路径 → 复杂时打开向导 |
| 同一订单重复打开不触发 watch(orderId) | watch `visible` 而非 `orderId`，visible 变 true 时加载 |
| 取消向导有"简单取消"分支不需要弹窗 | 简单路径逻辑留在父组件，向导只处理多步流程 |
| 取消成功后需同时关闭详情弹窗 | 向导 emit `cancelled` → 父组件统一关闭两个弹窗 |
| 取消向导重复调 cancelPreview API | 父组件传 `previewData` prop，向导不重复调 API |
