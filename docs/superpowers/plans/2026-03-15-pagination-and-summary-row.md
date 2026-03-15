# 分页改 20 条 + 表格合计行 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将全站表格分页从 50 条改为 20 条，并在 FinanceOrdersTab 和 PurchaseOrdersPanel 表格底部添加本页合计行。

**Architecture:** 分页改动为纯机械替换（50→20）；合计行通过 computed 属性计算当前页数据求和，以 `<tfoot>` 渲染在表格底部，列的 v-if 条件与 thead/tbody 保持一致。

**Tech Stack:** Vue 3 (Composition API) + Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-15-pagination-and-summary-row-design.md`

---

## Task 1: 分页 50 → 20（全局替换）

**Files:**
- Modify: `frontend/src/composables/usePagination.js:8` — 默认参数
- Modify: `frontend/src/composables/usePurchaseOrder.js:36` — `usePagination(50)`
- Modify: `frontend/src/composables/useShipment.js:14` — `usePagination(50)`
- Modify: `frontend/src/composables/useStock.js:31` — `usePagination(50)`
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue:619` — `usePagination(50)`
- Modify: `frontend/src/components/business/purchase/PurchaseReturnTab.vue:167` — `usePagination(50)`
- Modify: `frontend/src/components/business/PurchaseReturnTab.vue:77` — `const pageSize = 50`
- Modify: `frontend/src/components/business/PayableBillsTab.vue:203` — `const pageSize = 50`
- Modify: `frontend/src/components/business/ReceivableBillsTab.vue:203` — `const pageSize = 50`
- Modify: `frontend/src/components/business/DisbursementBillsTab.vue:167` — `const pageSize = 50`
- Modify: `frontend/src/components/business/DisbursementRefundBillsTab.vue:140` — `const pageSize = 50`
- Modify: `frontend/src/components/business/ReceiptBillsTab.vue:193` — `const pageSize = 50`
- Modify: `frontend/src/components/business/ReceiptRefundBillsTab.vue:140` — `const pageSize = 50`
- Modify: `frontend/src/components/business/WriteOffBillsTab.vue:140` — `const pageSize = 50`
- Modify: `frontend/src/components/business/SalesDeliveryTab.vue:141` — `const pageSize = 50`
- Modify: `frontend/src/components/business/SalesReturnTab.vue:71` — `const pageSize = 50`
- Modify: `frontend/src/components/business/SalesInvoiceTab.vue:317` — `const pageSize = 50`
- Modify: `frontend/src/components/business/PurchaseReceiptTab.vue:145` — `const pageSize = 50`
- Modify: `frontend/src/components/business/PurchaseInvoiceTab.vue:274` — `const pageSize = 50`
- Modify: `frontend/src/components/business/VoucherListView.vue:104` — `const pageSize = 50`
- Modify: `frontend/src/components/business/VoucherEntryListView.vue:72` — `const pageSize = 50`

**注意：不改** `SalesInvoiceTab.vue:444` 的 `page_size: 200` 和 `ReceiptBillsTab.vue:241` 的 `page_size: 200`。

- [ ] **Step 1: 改 usePagination.js 默认参数**

```js
// usePagination.js:8 — 改 size = 50 为 size = 20
export function usePagination(size = 20) {
```

- [ ] **Step 2: 改 composable 调用处（3 个文件）**

```js
// usePurchaseOrder.js:36
usePagination(20)

// useShipment.js:14
usePagination(20)

// useStock.js:31
usePagination(20)
```

- [ ] **Step 3: 改 Vue 组件中 usePagination 调用（2 个文件）**

```js
// FinanceOrdersTab.vue:619
usePagination(20)

// purchase/PurchaseReturnTab.vue:167
usePagination(20)
```

- [ ] **Step 4: 改 Vue 组件中 const pageSize = 50（14 个文件）**

每个文件都是同样的改动：`const pageSize = 50` → `const pageSize = 20`

文件列表：
- `PurchaseReturnTab.vue`（business 根目录）
- `PayableBillsTab.vue`
- `ReceivableBillsTab.vue`
- `DisbursementBillsTab.vue`
- `DisbursementRefundBillsTab.vue`
- `ReceiptBillsTab.vue`
- `ReceiptRefundBillsTab.vue`
- `WriteOffBillsTab.vue`
- `SalesDeliveryTab.vue`
- `SalesReturnTab.vue`
- `SalesInvoiceTab.vue`
- `PurchaseReceiptTab.vue`
- `PurchaseInvoiceTab.vue`
- `VoucherListView.vue`
- `VoucherEntryListView.vue`

- [ ] **Step 5: 运行 build 验证**

```bash
cd frontend && npm run build
```

Expected: 编译成功，无报错。

- [ ] **Step 6: 提交**

```bash
git add -A && git commit -m "feat: 全站表格分页从 50 条改为 20 条"
```

---

## Task 2: FinanceOrdersTab 添加合计行

**Files:**
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue`
  - Script (~line 750): 添加 `pageSummary` computed
  - Template (~line 151): 在 `</tbody>` 后添加 `<tfoot>`

- [ ] **Step 1: 添加 pageSummary computed 属性**

在 `FinanceOrdersTab.vue` 的 `<script setup>` 中，`sortedOrders` computed 之后添加：

```js
/** 本页合计（基于当前排序/筛选后的数据） */
const pageSummary = computed(() => {
  const rows = sortedOrders.value
  const sum = { total_amount: 0, total_cost: 0, total_profit: 0, paid_amount: 0, rebate_used: 0 }
  for (const o of rows) {
    sum.total_amount += Number(o.total_amount) || 0
    sum.total_cost += Number(o.total_cost) || 0
    sum.total_profit += Number(o.total_profit) || 0
    sum.paid_amount += Number(o.paid_amount) || 0
    sum.rebate_used += Number(o.rebate_used) || 0
  }
  // 浮点精度修正
  for (const k in sum) sum[k] = Math.round(sum[k] * 100) / 100
  return sum
})
```

- [ ] **Step 2: 在 template 中添加 tfoot**

在 `FinanceOrdersTab.vue` 的 `</tbody>` (line 151) 之后、`</table>` (line 152) 之前插入：

```html
          <tfoot v-if="sortedOrders.length > 0" class="bg-elevated font-semibold text-sm border-t">
            <tr>
              <td v-if="financeViewMode === 'summary'" class="px-1 py-2"></td>
              <td v-if="financeIsColumnVisible('order_no')" class="px-2 py-2 text-left">本页合计</td>
              <td v-if="financeIsColumnVisible('order_type')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('customer')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('related_order')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('total_amount')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.total_amount) }}</td>
              <td v-if="financeIsColumnVisible('total_cost') && hasPermission('finance')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.total_cost) }}</td>
              <td v-if="financeIsColumnVisible('total_profit') && hasPermission('finance')" class="px-2 py-2 text-right" :class="pageSummary.total_profit >= 0 ? 'text-success' : 'text-error'">{{ fmt(pageSummary.total_profit) }}</td>
              <td v-if="financeIsColumnVisible('paid_amount')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.paid_amount) }}</td>
              <td v-if="financeIsColumnVisible('status')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('shipping_status')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('item_count')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('remark')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('warehouse')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('employee')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('creator')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('created_at')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('refunded')" class="px-2 py-2"></td>
              <td v-if="financeIsColumnVisible('rebate_used')" class="px-2 py-2 text-right">¥{{ fmt(pageSummary.rebate_used) }}</td>
              <td v-if="financeIsColumnVisible('account_set')" class="px-2 py-2"></td>
              <td></td>
            </tr>
          </tfoot>
```

**列顺序必须与 thead/tbody 完全一致**（参照 template line 58-82 和 line 88-113）。

- [ ] **Step 3: 运行 build 验证**

```bash
cd frontend && npm run build
```

Expected: 编译成功。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/business/finance/FinanceOrdersTab.vue
git commit -m "feat(FinanceOrdersTab): 添加本页合计行（tfoot）"
```

---

## Task 3: PurchaseOrdersPanel 添加合计行

**Files:**
- Modify: `frontend/src/components/business/PurchaseOrdersPanel.vue`
  - Script (~line 240): 添加 `pageSummary` computed
  - Template (~line 165): 在 `</tbody>` 后添加 `<tfoot>`

- [ ] **Step 1: 添加 pageSummary computed 属性**

在 `PurchaseOrdersPanel.vue` 的 `<script setup>` 中，`usePurchaseOrder()` 解构之后（约 line 240）添加：

```js
/** 本页合计 */
const pageSummary = computed(() => {
  const rows = sortedPurchaseOrders.value
  const sum = { total_amount: 0, tax_amount: 0, return_amount: 0, rebate_used: 0, credit_used: 0 }
  for (const o of rows) {
    sum.total_amount += Number(o.total_amount) || 0
    sum.tax_amount += Number(o.tax_amount) || 0
    sum.return_amount += Number(o.return_amount) || 0
    sum.rebate_used += Number(o.rebate_used) || 0
    sum.credit_used += Number(o.credit_used) || 0
  }
  for (const k in sum) sum[k] = Math.round(sum[k] * 100) / 100
  return sum
})
```

需要在文件顶部的 import 中补充 `computed`（检查是否已有）。

- [ ] **Step 2: 在 template 中添加 tfoot**

在 `PurchaseOrdersPanel.vue` 的 `</tbody>` (line 165) 之后、`</table>` (line 166) 之前插入：

```html
          <tfoot v-if="sortedPurchaseOrders.length > 0" class="bg-elevated font-semibold text-sm border-t">
            <tr>
              <td v-if="viewMode === 'summary'" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('po_no')" class="px-3 py-2 text-left">本页合计</td>
              <td v-if="isColumnVisible('supplier')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('date')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('total_amount')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.total_amount) }}</td>
              <td v-if="isColumnVisible('tax_amount')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.tax_amount) }}</td>
              <td v-if="isColumnVisible('item_count')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('status')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('remark')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('creator')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('account_set')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('return_amount')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.return_amount) }}</td>
              <td v-if="isColumnVisible('target_warehouse')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('target_location')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('rebate_used')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.rebate_used) }}</td>
              <td v-if="isColumnVisible('credit_used')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.credit_used) }}</td>
              <td v-if="isColumnVisible('reviewer')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('reviewed_at')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('payment_method')" class="px-3 py-2"></td>
              <td></td>
            </tr>
          </tfoot>
```

**列顺序必须与 thead/tbody 完全一致**（参照 template line 74-99 和 line 103-127）。

- [ ] **Step 3: 运行 build 验证**

```bash
cd frontend && npm run build
```

Expected: 编译成功。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/business/PurchaseOrdersPanel.vue
git commit -m "feat(PurchaseOrdersPanel): 添加本页合计行（tfoot）"
```
