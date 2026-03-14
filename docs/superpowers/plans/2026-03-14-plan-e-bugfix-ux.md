# Plan E: Bug 修复与体验优化 - 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复应付单付款状态 bug、为所有单据界面补全搜索筛选、确认期末结账功能可用

**Architecture:** E1 通过 emit 事件实现跨 Tab 数据刷新修复状态不同步 bug；E2 统一为 11 个后端列表 API 添加 `search` 参数 + 为 12 个前端 Tab 组件添加搜索框；E3 确认 PeriodEndPanel 已正常集成

**Tech Stack:** FastAPI (Tortoise ORM Q 查询), Vue 3 Composition API, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-14-financial-ux-improvements-design.md` — Plan E 章节

---

## Chunk 1: E1 Bug 修复 + E3 期末确认

### Task 1: E1 — PayablePanel 跨 Tab 刷新修复

**问题根因：** 后端 `confirm_disbursement_bill` (ap_service.py:84-121) 已正确更新 PayableBill 的 `paid_amount`、`unpaid_amount`、`status`。Bug 在前端：DisbursementBillsTab 确认付款后只刷新自身列表，PayableBillsTab 的数据未同步刷新。

**Files:**
- Modify: `frontend/src/components/business/DisbursementBillsTab.vue` — 确认后 emit 事件
- Modify: `frontend/src/components/business/DisbursementRefundBillsTab.vue` — 确认后 emit 事件
- Modify: `frontend/src/components/business/PayablePanel.vue` — 监听事件，传递 refreshKey
- Modify: `frontend/src/components/business/PayableBillsTab.vue` — watch refreshKey 重新加载

**修复方案：** refreshKey 模式 — 子 Tab emit `data-changed` → 父 Panel 递增 `refreshKey` → 相关子 Tab watch prop 重新加载。

- [ ] **Step 1: DisbursementBillsTab 添加 emit**

在 `confirmBill` 函数成功后添加 emit：

```javascript
// DisbursementBillsTab.vue
const emit = defineEmits(['data-changed'])

async function confirmBill(b) {
  if (!await appStore.customConfirm('确认操作', `确认付款单 ${b.bill_no}？`)) return
  try {
    await confirmDisbursementBill(b.id)
    appStore.showToast('确认成功', 'success')
    loadList()
    emit('data-changed')  // 通知父组件刷新关联数据
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}
```

同样修改 DisbursementRefundBillsTab.vue 中的确认函数。

- [ ] **Step 2: PayablePanel 监听事件，管理 refreshKey**

```javascript
// PayablePanel.vue <script setup>
const payableRefreshKey = ref(0)

function onSubTabDataChanged() {
  payableRefreshKey.value++
}
```

模板中为 DisbursementBillsTab 和 DisbursementRefundBillsTab 绑定事件，为 PayableBillsTab 传递 prop：

```vue
<PayableBillsTab v-if="sub === 'payable-bills'" :refresh-key="payableRefreshKey" />
<DisbursementBillsTab v-if="sub === 'disbursement-bills'" @data-changed="onSubTabDataChanged" />
<DisbursementRefundBillsTab v-if="sub === 'disbursement-refunds'" @data-changed="onSubTabDataChanged" />
```

- [ ] **Step 3: PayableBillsTab watch refreshKey**

```javascript
// PayableBillsTab.vue
const props = defineProps({
  refreshKey: { type: Number, default: 0 }
})

watch(() => props.refreshKey, () => {
  loadList()
})
```

- [ ] **Step 4: 验证修复**

Run: `cd frontend && npm run build`
Expected: 编译通过，无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/business/DisbursementBillsTab.vue \
        frontend/src/components/business/DisbursementRefundBillsTab.vue \
        frontend/src/components/business/PayablePanel.vue \
        frontend/src/components/business/PayableBillsTab.vue
git commit -m "fix: PayablePanel 跨 Tab 刷新——确认付款后应付单状态同步更新"
```

---

### Task 2: E1 — ReceivablePanel 跨 Tab 刷新修复

**同理修复应收侧：** 确认收款单、收款退款、核销后，ReceivableBillsTab 也应刷新。

**Files:**
- Modify: `frontend/src/components/business/ReceiptBillsTab.vue` — emit
- Modify: `frontend/src/components/business/ReceiptRefundBillsTab.vue` — emit
- Modify: `frontend/src/components/business/WriteOffBillsTab.vue` — emit
- Modify: `frontend/src/components/business/ReceivablePanel.vue` — refreshKey
- Modify: `frontend/src/components/business/ReceivableBillsTab.vue` — watch

- [ ] **Step 1: 三个子 Tab 添加 emit**

ReceiptBillsTab.vue、ReceiptRefundBillsTab.vue、WriteOffBillsTab.vue 中：
- 添加 `const emit = defineEmits(['data-changed'])`
- 在确认操作成功后添加 `emit('data-changed')`

- [ ] **Step 2: ReceivablePanel 监听 + 传递 refreshKey**

与 PayablePanel 相同模式：

```javascript
const receivableRefreshKey = ref(0)
function onSubTabDataChanged() { receivableRefreshKey.value++ }
```

模板绑定事件和 prop。

- [ ] **Step 3: ReceivableBillsTab watch refreshKey**

```javascript
const props = defineProps({ refreshKey: { type: Number, default: 0 } })
watch(() => props.refreshKey, () => { loadList() })
```

- [ ] **Step 4: 验证并提交**

Run: `cd frontend && npm run build`

```bash
git add frontend/src/components/business/ReceiptBillsTab.vue \
        frontend/src/components/business/ReceiptRefundBillsTab.vue \
        frontend/src/components/business/WriteOffBillsTab.vue \
        frontend/src/components/business/ReceivablePanel.vue \
        frontend/src/components/business/ReceivableBillsTab.vue
git commit -m "fix: ReceivablePanel 跨 Tab 刷新——确认收款/退款/核销后应收单状态同步更新"
```

---

### Task 3: E3 — 期末结账功能确认

**现状：** PeriodEndPanel 已完整集成到会计模块，通过 AccountingView 的 `period-end` Tab 访问，包含损益结转、结账检查、期间结账/开启、年度结账等全部功能。

**Files:**
- Read only: `frontend/src/components/business/PeriodEndPanel.vue`
- Read only: `frontend/src/views/AccountingView.vue`

- [ ] **Step 1: 确认 PeriodEndPanel 可正常访问**

检查 AccountingView.vue 中 `period-end` tab 已注册：
- `accountingTabs` 数组包含 `{ value: 'period-end', label: '期末处理' }`
- `panelMap['period-end']` 映射到 PeriodEndPanel 组件

验证导航路径：侧边栏 "会计" → Tab "期末处理" → PeriodEndPanel

- [ ] **Step 2: 确认功能完整性**

PeriodEndPanel 应包含以下功能区：
- ✅ 损益结转（预览 + 执行）
- ✅ 结账检查（余额平衡）
- ✅ 期间结账 / 开启
- ✅ 年度结账

结论：PeriodEndPanel 功能完整，无需代码改动。记录确认结果即可。

---

## Chunk 2: E2 后端搜索参数支持

### Task 4: E2 — receivables.py 添加 search 参数（5 个 API）

**Files:**
- Modify: `backend/app/routers/receivables.py`

**需修改的 API：**
1. `GET /receivable-bills` — 搜索 bill_no, customer.name
2. `GET /receipt-bills` — 搜索 bill_no, customer.name
3. `GET /receipt-refund-bills` — 搜索 bill_no, customer.name
4. `GET /receivable-write-offs` — 搜索 bill_no, customer.name
5. `GET /sales-returns` — 搜索 order_no, customer.name

**通用模式：**

```python
from tortoise.expressions import Q

# 在每个列表 API 的参数中添加：
search: str = Query(None),

# 在查询构建中添加：
if search:
    query = query.filter(
        Q(bill_no__icontains=search) | Q(customer__name__icontains=search)
    )
```

- [ ] **Step 1: 修改 list_receivable_bills**

添加 `search: str = Query(None)` 参数，添加 Q 过滤：
```python
if search:
    query = query.filter(
        Q(bill_no__icontains=search) | Q(customer__name__icontains=search)
    )
```

- [ ] **Step 2: 修改 list_receipt_bills**

同上模式，搜索 `bill_no` 和 `customer__name`。

- [ ] **Step 3: 修改 list_receipt_refund_bills**

同上模式。

- [ ] **Step 4: 修改 list_receivable_write_offs**

同上模式。

- [ ] **Step 5: 修改 list_sales_returns**

注意：销售退货单的单据号字段可能是 `order_no` 而非 `bill_no`，需确认模型字段名。

```python
if search:
    query = query.filter(
        Q(order_no__icontains=search) | Q(customer__name__icontains=search)
    )
```

- [ ] **Step 6: 验证并提交**

Run: `cd backend && python -c "from app.routers.receivables import router; print('OK')"`
Expected: 无导入错误

```bash
git add backend/app/routers/receivables.py
git commit -m "feat: receivables 5 个列表 API 添加 search 模糊搜索参数"
```

---

### Task 5: E2 — payables.py 添加 search 参数（4 个 API）

**Files:**
- Modify: `backend/app/routers/payables.py`

**需修改的 API：**
1. `GET /payable-bills` — 搜索 bill_no, supplier.name
2. `GET /disbursement-bills` — 搜索 bill_no, supplier.name
3. `GET /disbursement-refund-bills` — 搜索 bill_no, supplier.name
4. `GET /purchase-returns` — 搜索 return_no, supplier.name

**通用模式：**

```python
if search:
    query = query.filter(
        Q(bill_no__icontains=search) | Q(supplier__name__icontains=search)
    )
```

- [ ] **Step 1: 修改 list_payable_bills**

添加 `search` 参数和 Q 过滤。

- [ ] **Step 2: 修改 list_disbursement_bills**

同上模式。

- [ ] **Step 3: 修改 list_disbursement_refund_bills**

同上模式。

- [ ] **Step 4: 修改 list_purchase_returns**

注意字段名可能是 `return_no`：
```python
if search:
    query = query.filter(
        Q(return_no__icontains=search) | Q(supplier__name__icontains=search)
    )
```

- [ ] **Step 5: 验证并提交**

Run: `cd backend && python -c "from app.routers.payables import router; print('OK')"`

```bash
git add backend/app/routers/payables.py
git commit -m "feat: payables 4 个列表 API 添加 search 模糊搜索参数"
```

---

### Task 6: E2 — invoices.py + sales_delivery.py + purchase_receipt.py 添加 search 参数

**Files:**
- Modify: `backend/app/routers/invoices.py`
- Modify: `backend/app/routers/sales_delivery.py`
- Modify: `backend/app/routers/purchase_receipt.py`

- [ ] **Step 1: 修改 invoices 列表 API**

```python
if search:
    q_filter = Q(invoice_no__icontains=search)
    if direction == 'output':
        q_filter = q_filter | Q(customer__name__icontains=search)
    elif direction == 'input':
        q_filter = q_filter | Q(supplier__name__icontains=search)
    else:
        q_filter = q_filter | Q(customer__name__icontains=search) | Q(supplier__name__icontains=search)
    query = query.filter(q_filter)
```

- [ ] **Step 2: 修改 sales_delivery 列表 API**

```python
if search:
    query = query.filter(
        Q(bill_no__icontains=search) | Q(customer__name__icontains=search)
    )
```

- [ ] **Step 3: 修改 purchase_receipt 列表 API**

```python
if search:
    query = query.filter(
        Q(bill_no__icontains=search) | Q(supplier__name__icontains=search)
    )
```

- [ ] **Step 4: 验证并提交**

```bash
git add backend/app/routers/invoices.py backend/app/routers/sales_delivery.py backend/app/routers/purchase_receipt.py
git commit -m "feat: invoices + sales_delivery + purchase_receipt 列表 API 添加 search 模糊搜索参数"
```

---

## Chunk 3: E2 前端搜索框补全

### Task 7: E2 — 应收管理 5 个 Tab 添加搜索框

**参考实现：** `business/purchase/PurchaseReturnTab.vue` 的搜索模式（toolbar-search-wrapper + debounced loadList）

**Files:**
- Modify: `frontend/src/components/business/ReceivableBillsTab.vue`
- Modify: `frontend/src/components/business/ReceiptBillsTab.vue`
- Modify: `frontend/src/components/business/ReceiptRefundBillsTab.vue`
- Modify: `frontend/src/components/business/WriteOffBillsTab.vue`
- Modify: `frontend/src/components/business/SalesReturnTab.vue`

**每个组件统一添加的代码：**

**script setup 部分：**
```javascript
import { Search } from 'lucide-vue-next'

const searchQuery = ref('')
let _searchTimer

function debouncedSearch() {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => {
    page.value = 1
    loadList()
  }, 300)
}
```

**loadList 中添加：**
```javascript
if (searchQuery.value) params.search = searchQuery.value
```

**template 中 PageToolbar #filters 插槽内添加：**
```html
<div class="toolbar-search-wrapper">
  <Search :size="14" class="toolbar-search-icon" />
  <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索单号/客户...">
</div>
```

- [ ] **Step 1: ReceivableBillsTab 添加搜索**

- 导入 Search 图标
- 添加 searchQuery ref + debouncedSearch 函数
- loadList() 中加入 `if (searchQuery.value) params.search = searchQuery.value`
- 在 PageToolbar #filters 中添加搜索框 HTML
- placeholder: "搜索单号/客户..."

- [ ] **Step 2: ReceiptBillsTab 添加搜索**

同上模式，placeholder: "搜索单号/客户..."

- [ ] **Step 3: ReceiptRefundBillsTab 添加搜索**

同上模式，placeholder: "搜索单号/客户..."

- [ ] **Step 4: WriteOffBillsTab 添加搜索**

同上模式，placeholder: "搜索单号/客户..."

- [ ] **Step 5: SalesReturnTab 添加搜索**

同上模式，placeholder: "搜索单号/客户..."。注意：当前 SalesReturnTab 的 #filters 插槽中只有说明文字，搜索框要和说明文字并排。

- [ ] **Step 6: 验证并提交**

Run: `cd frontend && npm run build`

```bash
git add frontend/src/components/business/ReceivableBillsTab.vue \
        frontend/src/components/business/ReceiptBillsTab.vue \
        frontend/src/components/business/ReceiptRefundBillsTab.vue \
        frontend/src/components/business/WriteOffBillsTab.vue \
        frontend/src/components/business/SalesReturnTab.vue
git commit -m "feat: 应收管理 5 个 Tab 添加搜索框"
```

---

### Task 8: E2 — 应付管理 5 个 Tab 添加搜索框

**Files:**
- Modify: `frontend/src/components/business/PayableBillsTab.vue`
- Modify: `frontend/src/components/business/DisbursementBillsTab.vue`
- Modify: `frontend/src/components/business/DisbursementRefundBillsTab.vue`
- Modify: `frontend/src/components/business/PurchaseReceiptTab.vue`
- Modify: `frontend/src/components/business/PurchaseReturnTab.vue`

注意：`business/PurchaseReturnTab.vue` 无搜索（与 `business/purchase/PurchaseReturnTab.vue` 是不同组件）。`PurchaseReceiptTab` 也无搜索。两者都需要添加。

- [ ] **Step 1: PayableBillsTab 添加搜索**

同 Task 7 模式，placeholder: "搜索单号/供应商..."

- [ ] **Step 2: DisbursementBillsTab 添加搜索**

同上模式，placeholder: "搜索单号/供应商..."

- [ ] **Step 3: DisbursementRefundBillsTab 添加搜索**

同上模式，placeholder: "搜索单号/供应商..."

- [ ] **Step 4: PurchaseReceiptTab 添加搜索**

同上模式，placeholder: "搜索单号/供应商..."

- [ ] **Step 5: PurchaseReturnTab 添加搜索**

同上模式，placeholder: "搜索退货单号/供应商..."。注意：修改的是 `business/PurchaseReturnTab.vue`（PayablePanel 使用的那个），不是 `business/purchase/PurchaseReturnTab.vue`。

- [ ] **Step 6: 验证并提交**

Run: `cd frontend && npm run build`

```bash
git add frontend/src/components/business/PayableBillsTab.vue \
        frontend/src/components/business/DisbursementBillsTab.vue \
        frontend/src/components/business/DisbursementRefundBillsTab.vue \
        frontend/src/components/business/PurchaseReceiptTab.vue \
        frontend/src/components/business/PurchaseReturnTab.vue
git commit -m "feat: 应付管理 5 个 Tab 组件添加搜索框"
```

---

### Task 9: E2 — 发票管理 + 出库单 Tab 添加搜索框

**Files:**
- Modify: `frontend/src/components/business/SalesInvoiceTab.vue`
- Modify: `frontend/src/components/business/PurchaseInvoiceTab.vue`
- Modify: `frontend/src/components/business/SalesDeliveryTab.vue`

- [ ] **Step 1: SalesInvoiceTab 添加搜索**

同上模式，placeholder: "搜索发票号/客户..."

- [ ] **Step 2: PurchaseInvoiceTab 添加搜索**

同上模式，placeholder: "搜索发票号/供应商..."

- [ ] **Step 3: SalesDeliveryTab 添加搜索**

同上模式，placeholder: "搜索单号/客户..."

- [ ] **Step 4: 验证并提交**

Run: `cd frontend && npm run build`

```bash
git add frontend/src/components/business/SalesInvoiceTab.vue \
        frontend/src/components/business/PurchaseInvoiceTab.vue \
        frontend/src/components/business/SalesDeliveryTab.vue
git commit -m "feat: 发票管理 + 出库单 Tab 添加搜索框"
```

---

## 验证清单

完成所有 Task 后，执行最终验证：

- [ ] `cd frontend && npm run build` — 前端构建通过
- [ ] 启动开发服务器，检查所有搜索框均正常显示
- [ ] 测试 E1：确认付款单后切换到应付单 Tab，状态应已更新
- [ ] 测试 E2：在任意 Tab 输入搜索关键字，列表应正确过滤
- [ ] 确认 E3：期末处理 Tab 可正常访问

---

## 注意事项

1. **VoucherPanel 搜索**：Plan A (A2) 会添加更完整的搜索功能（凭证号、科目名称、摘要），E2 阶段跳过 VoucherPanel
2. **后端字段名确认**：各模型的单据号字段名可能不同（bill_no / order_no / return_no / invoice_no），需实际读取模型确认
3. **Tortoise ORM Q 查询**：使用 `from tortoise.expressions import Q` 而非 `from tortoise.queryset import Q`
4. **搜索不影响分页**：搜索时重置 page=1，搜索参数通过 API 传递，后端在分页前过滤
5. **PurchaseReturnTab 注意区分**：项目中有两个同名组件——`business/PurchaseReturnTab.vue`（PayablePanel 使用，无搜索）和 `business/purchase/PurchaseReturnTab.vue`（采购模块使用，已有搜索）。本计划修改的是前者
6. **跨 Tab 刷新与 v-if**：当前 Tab 使用 `v-if` 渲染，切换 Tab 时组件重建会触发 onMounted 重新加载。refreshKey 机制作为额外保障，确保即使未来改为 KeepAlive 也能正确刷新
