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

### 2. 合计行（方案 A — tfoot）

在 `<table>` 的 `</tbody>` 之后、`</table>` 之前添加 `<tfoot>`，随表格自然滚动。

#### FinanceOrdersTab

computed 属性 `pageSummary`，遍历 `sortedOrders` 求和：
- `total_amount` — 金额
- `total_cost` — 成本（需 finance 权限才显示）
- `total_profit` — 毛利（需 finance 权限才显示）
- `paid_amount` — 已付
- `rebate_used` — 返利已用

模板：
```html
<tfoot class="bg-elevated font-semibold text-sm border-t">
  <tr>
    <!-- 非数字列留空，第一个可见列显示"本页合计" -->
    <td ...>本页合计</td>
    ...
    <td class="text-right">¥{{ fmt(pageSummary.total_amount) }}</td>
    <td class="text-right">¥{{ fmt(pageSummary.total_cost) }}</td>
    <td class="text-right">{{ fmt(pageSummary.total_profit) }}</td>
    <td class="text-right">¥{{ fmt(pageSummary.paid_amount) }}</td>
    <td class="text-right">¥{{ fmt(pageSummary.rebate_used) }}</td>
    ...
  </tr>
</tfoot>
```

#### PurchaseOrdersPanel

computed 属性 `pageSummary`，遍历 `sortedPurchaseOrders` 求和：
- `total_amount` — 总金额
- `tax_amount` — 含税金额

模板结构同上，第一个可见列显示"本页合计"。

### 样式规范
- `<tfoot>` 行使用 `bg-elevated` 背景 + `font-semibold` + `border-t`
- 数字列右对齐，使用 `fmt()` 格式化 + `¥` 前缀
- 毛利列保留正负色：正值 `text-success`，负值 `text-error`
- 非数字列 `<td>` 内容为空
- 动态列配置（ColumnMenu 隐藏的列）在 tfoot 中同步使用 `v-if` 控制
