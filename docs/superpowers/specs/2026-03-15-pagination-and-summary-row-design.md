# 分页改 20 条 + 表格合计行

## 背景
- 当前所有表格分页为 50 条/页，超出屏幕可视范围
- 财务订单明细和采购订单列表缺少本页数据合计

## 变更范围

### 1. 分页 50 → 20

**统一入口** `usePagination.js`：默认参数 `size = 50` → `size = 20`

**所有调用处**（显式传参的也统一改）：

| 文件 | 改动 |
|------|------|
| `composables/usePagination.js` | 默认参数 50 → 20 |
| `composables/usePurchaseOrder.js` | `usePagination(50)` → `usePagination(20)` |
| `composables/useShipment.js` | `usePagination(50)` → `usePagination(20)` |
| `composables/useStock.js` | `usePagination(50)` → `usePagination(20)` |
| `finance/FinanceOrdersTab.vue` | `usePagination(50)` → `usePagination(20)` |
| `purchase/PurchaseReturnTab.vue` | `usePagination(50)` → `usePagination(20)` |
| `PurchaseReturnTab.vue`（business 根目录） | `const pageSize = 50` → `20` |
| `PayableBillsTab.vue` | `const pageSize = 50` → `20` |
| `ReceivableBillsTab.vue` | 同上 |
| `DisbursementBillsTab.vue` | 同上 |
| `DisbursementRefundBillsTab.vue` | 同上 |
| `ReceiptBillsTab.vue` | 同上 |
| `ReceiptRefundBillsTab.vue` | 同上 |
| `WriteOffBillsTab.vue` | 同上 |
| `SalesDeliveryTab.vue` | 同上 |
| `SalesReturnTab.vue` | 同上 |
| `SalesInvoiceTab.vue` | 同上 |
| `PurchaseReceiptTab.vue` | 同上 |
| `PurchaseInvoiceTab.vue` | 同上 |
| `VoucherListView.vue` | 同上 |
| `VoucherEntryListView.vue` | 同上 |

**注意**：`SalesInvoiceTab.vue:444` 和 `ReceiptBillsTab.vue:241` 有 `page_size: 200` 的特殊调用（用于下拉加载全量），不受此次变更影响。

### 2. 合计行（方案 A — tfoot）

在 `<table>` 的 `</tbody>` 之后、`</table>` 之前添加 `<tfoot>`，随表格自然滚动。

**合计仅为当前页数据合计**，不是跨页全量合计。

#### FinanceOrdersTab

computed 属性 `pageSummary`，遍历 `sortedOrders` 求和：
- `total_amount` — 金额
- `total_cost` — 成本（需 `financeIsColumnVisible('total_cost') && hasPermission('finance')`）
- `total_profit` — 毛利（需 `financeIsColumnVisible('total_profit') && hasPermission('finance')`）
- `paid_amount` — 已付
- `rebate_used` — 返利已用

#### PurchaseOrdersPanel

computed 属性 `pageSummary`，遍历 `sortedPurchaseOrders` 求和：
- `total_amount` — 总金额
- `tax_amount` — 含税金额
- `return_amount` — 退货金额
- `rebate_used` — 返利已用
- `credit_used` — 在账资金

### tfoot 模板要点

1. **空数据不显示**：`<tfoot v-if="sortedOrders.length > 0">`
2. **展开箭头列占位**：汇总模式下 `<td v-if="viewMode === 'summary'"></td>`
3. **ColumnMenu 尾部占位**：末尾加空 `<td></td>`
4. **动态列 v-if**：每个 `<td>` 使用与 thead/tbody 完全相同的 `v-if` 条件（含权限判断）
5. **第一个可见列**显示"本页合计"文字

### 样式规范
- `<tfoot>` 行使用 `bg-elevated` 背景 + `font-semibold` + `border-t`
- 数字列右对齐，使用 `fmt()` 格式化 + `¥` 前缀
- 毛利列正负色：`>= 0` 时 `text-success`，`< 0` 时 `text-error`
- 非数字列 `<td>` 内容为空
- 求和结果做 `Math.round(sum * 100) / 100` 避免浮点精度问题
