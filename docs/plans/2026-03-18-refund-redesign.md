# 退货退款流程重构实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将退货退款从错误的会计单据（ReceiptBill/DisbursementBill）改为正确的（ReceiptRefundBill/DisbursementRefundBill），新增财务退款管理确认环节，确认后才推送会计单据。

**Architecture:** 退货时只标记"需要退款"不生成会计单据；财务在新增的退款管理 Tab 确认后，才创建 confirmed 状态的 RefundBill 推送到会计模块。退款管理直接查询 Order/PurchaseReturn 记录，不引入新模型。

**Tech Stack:** FastAPI + Tortoise ORM (后端), Vue 3 + Tailwind CSS 4 (前端)

**设计文档:** `docs/plans/2026-03-18-refund-redesign-design.md`

---

### Task 1: 数据库模型变更 + 迁移脚本

**Files:**
- Modify: `backend/app/models/ar_ap.py`
- Modify: `backend/app/models/order.py`
- Modify: `backend/app/models/purchase.py`
- Create: `backend/app/migrations/v030_refund_redesign.py`
- Modify: `backend/app/migrations/runner.py`

**Step 1: 修改 ReceiptRefundBill 模型**

在 `backend/app/models/ar_ap.py` 的 ReceiptRefundBill 类中：
- `original_receipt` 字段添加 `null=True`（原来是 NOT NULL）
- 新增 `return_order` 外键（nullable，关联 Order）
- 新增 `refund_info` 文本字段

```python
class ReceiptRefundBill(models.Model):
    """收款退款单"""
    # ... 现有字段 ...
    original_receipt = fields.ForeignKeyField("models.ReceiptBill", null=True, on_delete=fields.SET_NULL, related_name="refund_bills")  # 改为 nullable
    # 新增字段：
    return_order = fields.ForeignKeyField("models.Order", null=True, on_delete=fields.SET_NULL, related_name="receipt_refund_bills")
    refund_info = fields.TextField(default="")
```

**Step 2: 修改 DisbursementRefundBill 模型**

同样在 `ar_ap.py` 的 DisbursementRefundBill 类中：
- `original_disbursement` 字段添加 `null=True`
- 新增 `purchase_return` 外键
- 新增 `refund_info` 文本字段

```python
class DisbursementRefundBill(models.Model):
    """付款退款单"""
    # ... 现有字段 ...
    original_disbursement = fields.ForeignKeyField("models.DisbursementBill", null=True, on_delete=fields.SET_NULL, related_name="refund_bills")  # 改为 nullable
    # 新增字段：
    purchase_return = fields.ForeignKeyField("models.PurchaseReturn", null=True, on_delete=fields.SET_NULL, related_name="disbursement_refund_bills")
    refund_info = fields.TextField(default="")
```

**Step 3: 清理 ReceiptBill 模型**

移除 `bill_type` 字段（行 43）和 `return_order` 字段（行 44）。

**Step 4: 清理 DisbursementBill 模型**

移除 `bill_type` 字段（行 138）和 `purchase_return` 字段（行 139）。

**Step 5: Order 模型新增 refund_info**

在 `backend/app/models/order.py` 中新增：
```python
refund_info = fields.TextField(default="")  # 退款备注信息
```

**Step 6: PurchaseReturn 模型新增 refund_info**

在 `backend/app/models/purchase.py` PurchaseReturn 类中新增：
```python
refund_info = fields.TextField(default="")  # 退款备注信息
```

**Step 7: 编写迁移脚本**

创建 `backend/app/migrations/v030_refund_redesign.py`：
- 为 ReceiptRefundBill 添加 return_order_id, refund_info 列
- 为 DisbursementRefundBill 添加 purchase_return_id, refund_info 列
- 将 receipt_bills 中 bill_type='return_refund' 的记录迁移到 receipt_refund_bills
- 将 disbursement_bills 中 bill_type='return_refund' 的记录迁移到 disbursement_refund_bills
- 删除迁移后的旧记录
- 删除 receipt_bills 的 bill_type, return_order_id 列
- 删除 disbursement_bills 的 bill_type, purchase_return_id 列
- 为 orders 添加 refund_info 列
- 为 purchase_returns 添加 refund_info 列
- 修改 receipt_refund_bills.original_receipt_id 为 nullable
- 修改 disbursement_refund_bills.original_disbursement_id 为 nullable

在 `runner.py` 中注册 v030。

**Step 8: 运行测试验证模型变更**

```bash
SECRET_KEY=test-secret python -m pytest tests/test_ar_ap_models.py -v
```

**Step 9: 提交**

```bash
git add backend/app/models/ar_ap.py backend/app/models/order.py backend/app/models/purchase.py backend/app/migrations/v030_refund_redesign.py backend/app/migrations/runner.py
git commit -m "refactor(models): 退货退款模型重构 — 扩展 RefundBill + 清理旧字段"
```

---

### Task 2: 后端 — 删除退货时自动创建会计单据的逻辑

**Files:**
- Modify: `backend/app/routers/orders.py:224-251` (销售退货)
- Modify: `backend/app/routers/orders.py:860-869` (订单取消)
- Modify: `backend/app/routers/orders.py:174-176` (paid_amount 设置)
- Modify: `backend/app/routers/purchase_orders.py:925-945` (采购退货)
- Modify: `backend/app/schemas/order.py` (新增 refund_info 字段)
- Modify: `backend/app/schemas/purchase.py` (新增 refund_info 字段)
- Modify: `backend/app/services/order_service.py:304-307` (不需要退款时 is_cleared=true)

**Step 1: 修改 OrderCreate schema**

在 `backend/app/schemas/order.py` 中新增：
```python
refund_info: Optional[str] = None  # 退款备注信息
```

**Step 2: 修改 PurchaseReturnRequest schema**

在 `backend/app/schemas/purchase.py` 中新增：
```python
refund_info: Optional[str] = None  # 退款备注信息
```

**Step 3: 删除销售退货时自动创建 ReceiptBill(return_refund)**

在 `backend/app/routers/orders.py` 中，删除行 223-251 整个代码块（`# 6.6 钩子`）。

**Step 4: 修改 Order 创建时保存 refund_info**

在 `orders.py` 的 Order.create 调用中，添加：
```python
refund_info=data.refund_info if data.order_type == OrderType.RETURN else "",
```

**Step 5: 修改「不需要退款」路径 — 立即结清**

在 `backend/app/services/order_service.py` 的 RETURN 分支中，添加 is_cleared 设置：
```python
elif customer and data.order_type == OrderType.RETURN:
    if not data.refunded:
        # 不需要退款：退货金额转为客户在账资金，立即结清
        await Customer.filter(id=customer.id).update(balance=F('balance') + total_amount)
        order.is_cleared = True
        await order.save()
```

**Step 6: 修改「需要退款」路径 — 不设置 paid_amount**

在 `orders.py:174-176`，删除 `if data.order_type == OrderType.RETURN and data.refunded:` 分支中设置 `paid_amount` 的逻辑（退款确认前 paid_amount 应该保持 0）。

**Step 7: 删除订单取消时创建 ReceiptBill(return_refund)**

在 `orders.py:860-869`，将创建 ReceiptBill 的代码替换为只保存退款信息到 order 上（order.refund_info, order.refunded=True 等），不创建会计单据。

**Step 8: 删除采购退货时创建 DisbursementBill(return_refund)**

在 `purchase_orders.py:925-945`，删除 DisbursementBill.create 代码块。将 refund_info 保存到 PurchaseReturn 上。

**Step 9: 清理 confirm_receipt_bill 中的旧逻辑**

在 `backend/app/services/ar_service.py:100-109`，删除 `if receipt.bill_type == "return_refund"` 分支。

**Step 10: 清理 confirm_disbursement_bill 中的旧逻辑**

在 `backend/app/services/ap_service.py:108-119`，删除 `if db.bill_type == "return_refund"` 分支。

**Step 11: 清理 pending-voucher-bills 中的 type_label**

- `receivables.py:487`：移除 `"退款" if ... "return_refund"` 判断，直接用 `"收款"`
- `payables.py:393`：同上，直接用 `"付款"`

**Step 12: npm run build 验证前端不受影响**

```bash
cd frontend && npm run build
```

**Step 13: 运行现有测试确认不 break**

```bash
SECRET_KEY=test-secret python -m pytest tests/test_return_credit.py tests/test_ar_ap_service.py -v
```

**Step 14: 提交**

```bash
git commit -m "refactor(backend): 删除退货时自动创建会计单据，改为财务确认后推送"
```

---

### Task 3: 后端 — 新增退款确认 API

**Files:**
- Create: `backend/app/routers/refunds.py`
- Modify: `backend/main.py` (注册路由)
- Create: `backend/tests/test_refund_confirm.py`

**Step 1: 创建退款确认路由**

创建 `backend/app/routers/refunds.py`，包含 3 个端点：

1. `GET /api/finance/refunds` — 待退款列表
   - 查询 Order(order_type=RETURN, refunded=True, is_cleared=False) 作为销售退款
   - 查询 PurchaseReturn(is_refunded=True, refund_status="pending") 作为采购退款（注：is_refunded 字段现在语义为"需要退款"）
   - 合并返回，标明类型（sales/purchase）
   - 权限：finance

2. `POST /api/finance/refunds/confirm-sales/{order_id}` — 确认销售退款
   - 验证订单是 RETURN 类型 + refunded=True + is_cleared=False
   - 查找关联的红字 ReceivableBill（通过 order_id）
   - 查找原销售订单的 ReceiptBill（通过 related_order_id，CASH 订单有）
   - 创建 ReceiptRefundBill(status="confirmed", return_order=order, original_receipt=找到的或null, amount=退款金额)
   - 更新红字 ReceivableBill 的 received_amount
   - 标记 order.is_cleared=True, order.paid_amount=abs(total_amount)
   - 权限：finance_confirm

3. `POST /api/finance/refunds/confirm-purchase/{return_id}` — 确认采购退款
   - 验证 PurchaseReturn(is_refunded=True, refund_status="pending")
   - 查找关联的红字 PayableBill
   - 创建 DisbursementRefundBill(status="confirmed", purchase_return=pr, original_disbursement=null, amount=退款金额)
   - 更新红字 PayableBill 的 paid_amount
   - 标记 pr.is_refunded=True, pr.refund_status="completed"
   - 权限：finance_confirm

**Step 2: 在 main.py 注册路由**

```python
from app.routers import refunds
app.include_router(refunds.router, prefix="/api/finance", tags=["退款管理"])
```

**Step 3: 编写测试**

创建 `backend/tests/test_refund_confirm.py`：
- test_confirm_sales_refund_creates_receipt_refund_bill — 确认销售退款后创建 ReceiptRefundBill(confirmed)
- test_confirm_sales_refund_clears_order — 确认后订单 is_cleared=True
- test_confirm_purchase_refund_creates_disbursement_refund_bill — 确认采购退款后创建 DisbursementRefundBill(confirmed)
- test_confirm_purchase_refund_updates_status — 确认后 refund_status=completed
- test_cannot_confirm_already_cleared — 重复确认应报错

**Step 4: 运行测试**

```bash
SECRET_KEY=test-secret python -m pytest tests/test_refund_confirm.py -v
```

**Step 5: 提交**

```bash
git commit -m "feat(backend): 新增退款确认 API — 确认后推送会计单据"
```

---

### Task 4: 前端 — 修改退货表单（销售+采购）

**Files:**
- Modify: `frontend/src/components/business/sales/OrderConfirmModal.vue:72-111`
- Modify: `frontend/src/components/business/finance/FinanceOrderDetailModal.vue:64-66,541-547`
- Modify: `frontend/src/components/business/purchase/PurchaseOrderDetail.vue:222-254,565-607`

**Step 1: 修改 OrderConfirmModal 退货表单**

将行 75-80 的文案从「已退款给客户」改为「需要退款」：
```vue
<input type="checkbox" v-model="orderConfirm.refunded" class="mr-2 w-4 h-4">
<span class="font-medium text-sm">需要退款给客户</span>
<!-- 说明文案 -->
<div class="mb-1"><b>已勾选</b>：需要退款给客户，将推送到财务退款管理确认</div>
<div><b>未勾选</b>：不退款，将形成客户的在账资金（预付款），下次购货时可以抵扣</div>
```

在退款方式选择区域新增退款信息 textarea：
```vue
<div>
  <label class="text-xs text-secondary" for="refund-info">退款信息</label>
  <textarea id="refund-info" v-model="orderConfirm.refund_info" class="input text-sm mt-0.5" rows="2" placeholder="退款备注（如银行账号、退款原因等）"></textarea>
</div>
```

在提交数据中添加 `refund_info` 字段。

**Step 2: 修改 FinanceOrderDetailModal 退货表单**

行 66 的 returnForm 新增 refund_info：
```javascript
const returnForm = reactive({ items: [], refunded: false, refund_method: '', refund_info: '' })
```

行 541-547 的 checkbox 文案改为「需要退款」，新增退款方式选择和退款信息输入。

在 submitReturn 函数中将 refund_info 传递给后端。

**Step 3: 修改 PurchaseOrderDetail 退货表单**

行 224-226 文案从「供应商已退款」改为「需要供应商退款」：
```vue
<input type="checkbox" v-model="returnForm.is_refunded" class="w-4 h-4">
<span class="text-sm">需要供应商退款</span>
```

新增退款信息 textarea。

在 confirmReturn 函数中传递 `refund_info`。

**Step 4: npm run build 验证**

```bash
cd frontend && npm run build
```

**Step 5: 提交**

```bash
git commit -m "feat(frontend): 退货表单改为「需要退款」+ 退款信息输入"
```

---

### Task 5: 前端 — 新增退款管理 Tab

**Files:**
- Create: `frontend/src/components/business/finance/FinanceRefundsPanel.vue`
- Modify: `frontend/src/views/FinanceView.vue`
- Create: `frontend/src/api/refunds.js` (或在 finance.js 中添加)

**Step 1: 创建 API 模块**

在 `frontend/src/api/finance.js` 中新增：
```javascript
export const getPendingRefunds = (params) => api.get('/finance/refunds', { params })
export const confirmSalesRefund = (orderId) => api.post(`/finance/refunds/confirm-sales/${orderId}`)
export const confirmPurchaseRefund = (returnId) => api.post(`/finance/refunds/confirm-purchase/${returnId}`)
```

**Step 2: 创建 FinanceRefundsPanel 组件**

创建 `frontend/src/components/business/finance/FinanceRefundsPanel.vue`：
- 表格显示：类型（销售退款/采购退款）、单号、客户/供应商、退款金额、退款方式、退款信息、退货日期
- 操作列：「确认已退款」按钮（需 finance_confirm 权限）
- 确认时弹出 customConfirm 二次确认
- 确认成功后刷新列表 + showToast

**Step 3: 在 FinanceView 中注册 Tab**

在 `frontend/src/views/FinanceView.vue` 中：
- Tab 列表新增「退款管理」
- 添加 FinanceRefundsPanel 组件
- 更新 financeValidTabs 数组

**Step 4: npm run build 验证**

```bash
cd frontend && npm run build
```

**Step 5: 提交**

```bash
git commit -m "feat(frontend): 新增财务退款管理 Tab — 确认后推送会计单据"
```

---

### Task 6: 前端 — 清理会计模块中的旧退款标签

**Files:**
- Modify: `frontend/src/components/business/ReceiptBillsTab.vue:53`
- Modify: `frontend/src/components/business/DisbursementBillsTab.vue:48`

**Step 1: 清理 ReceiptBillsTab**

删除行 53 的 `bill_type === 'return_refund'` 标签：
```vue
<!-- 删除这行 -->
<span v-if="b.bill_type === 'return_refund'" class="ml-1 px-1.5 py-0.5 text-xs bg-error/10 text-error rounded">退款</span>
```

**Step 2: 清理 DisbursementBillsTab**

删除行 48 的同类标签。

**Step 3: npm run build 验证**

```bash
cd frontend && npm run build
```

**Step 4: 提交**

```bash
git commit -m "fix(frontend): 清理会计模块收款单/付款单中的旧退款标签"
```

---

### Task 7: 更新测试 + 端到端验证

**Files:**
- Modify: `backend/tests/test_return_credit.py`
- Modify: `backend/tests/test_refund_confirm.py`

**Step 1: 更新 test_return_credit.py**

- 更新 test_cash_return_no_refund_creates_credit：验证 is_cleared=True（不需要退款时立即结清）
- 新增 test_cash_return_needs_refund_not_cleared：验证需要退款时 is_cleared=False

**Step 2: 运行全部相关测试**

```bash
SECRET_KEY=test-secret python -m pytest tests/test_return_credit.py tests/test_refund_confirm.py tests/test_ar_ap_service.py -v
```

**Step 3: npm run build 最终验证**

```bash
cd frontend && npm run build
```

**Step 4: 提交**

```bash
git commit -m "test: 更新退货退款相关测试用例"
```

---

### Task 8: 数据迁移脚本验证 + 文档更新

**Files:**
- 验证: `backend/app/migrations/v030_refund_redesign.py`
- Modify: `CHANGELOG.md`
- Modify: `AI_CONTEXT.md`

**Step 1: 在开发数据库上运行迁移**

重启后端服务，验证迁移脚本执行成功，无报错。

**Step 2: 验证已迁移数据**

检查 receipt_refund_bills 和 disbursement_refund_bills 表中是否有从旧表迁移过来的记录。

**Step 3: 更新 CHANGELOG**

新增 v4.30.0 条目，描述退货退款流程重构。

**Step 4: 更新 AI_CONTEXT**

更新模型数量、组件列表等。

**Step 5: 提交**

```bash
git commit -m "docs: 退货退款重构 — 迁移验证 + 文档更新"
```
