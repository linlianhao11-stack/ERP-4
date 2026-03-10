# 取消订单退款流程优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 优化取消订单流程，未收款订单直接取消，已收款订单走退款确认流程并推送会计模块。

**Architecture:** 前端根据 cancel-preview 返回的 paid_amount/rebate_used/is_partial 三个维度决定向导步数。后端现金退款时额外创建 ReceiptRefundBill（收款退款单）推送会计模块，出纳在收款管理确认退款。

**Tech Stack:** Vue 3 (Composition API) / FastAPI + Tortoise ORM

---

### Task 1: 后端 — cancel-preview 增加 has_payment 标志

**Files:**
- Modify: `backend/app/routers/orders.py:474-490` (cancel_preview return)

**Step 1: 修改 cancel-preview 响应**

在 cancel_preview 函数的返回值中增加 `has_payment` 字段：

```python
# backend/app/routers/orders.py — cancel_preview 返回值
return {
    "order_id": order.id,
    "order_no": order.order_no,
    "order_type": order.order_type,
    "customer_name": order.customer.name if order.customer else None,
    "total_amount": float(total),
    "paid_amount": float(paid),
    "rebate_used": float(rebate),
    "shipped_items": shipped_items,
    "cancel_items": cancel_items,
    "new_order_amount": float(new_order_amount),
    "default_new_paid": float(default_new_paid),
    "default_new_rebate": float(default_new_rebate),
    "default_refund": float(default_refund),
    "default_refund_rebate": float(default_refund_rebate),
    "is_partial": is_partial,
    "has_payment": float(paid) > 0 or float(rebate) > 0  # 新增
}
```

**Step 2: 验证**

```bash
cd /Users/lin/Desktop/erp-4 && cd frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 2: 后端 — cancel 接口增加 ReceiptRefundBill 创建 + 健壮性修复

**Files:**
- Modify: `backend/app/routers/orders.py:493-666` (cancel_order 函数)

**Step 1: 在现金退款分支（`refund_method == "cash"`）后，增加 ReceiptRefundBill 创建**

在现有 Payment.create 之后（约 line 641 后）加入：

```python
# 在 else (cash refund) 分支内，Payment.create 之后添加：
# 推送会计模块：创建收款退款单
if order.account_set_id:
    try:
        from app.models.ar_ap import ReceiptBill, ReceiptRefundBill
        original_receipt = await ReceiptBill.filter(
            account_set_id=order.account_set_id,
            customer_id=customer.id,
            status="confirmed",
        ).order_by("-id").first()
        if original_receipt:
            await ReceiptRefundBill.create(
                bill_no=generate_order_no("SKTK"),
                account_set_id=order.account_set_id,
                customer_id=customer.id,
                original_receipt=original_receipt,
                refund_date=date.today(),
                amount=refund_amount,
                reason=f"取消订单 {order.order_no} 退款",
                status="draft",
                creator=user,
            )
    except Exception as e:
        logger.error(f"取消订单自动生成收款退款单失败: {e}")
```

**Step 2: 修复边界问题 — CREDIT 订单取消时 new_order 可能为 None**

检查 line 643-648，确保 `new_order` 为 None 时不报错。当前代码已有三元表达式保护，但需确认 `abs()` 对 None 的处理。

当前代码（已安全）：
```python
cancel_balance_amount = abs(order.total_amount) - (abs(new_order.total_amount) if new_order else Decimal("0"))
```

**Step 3: 确保 `date` 导入存在**

在文件头部检查是否已有 `from datetime import date`。如缺失则添加。

**Step 4: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4 && python -c "import ast; ast.parse(open('backend/app/routers/orders.py').read()); print('OK')"
```

---

### Task 3: 前端 — 重写取消向导流程

**Files:**
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue`

这是最关键的改动，需要修改 4 处逻辑：

**Step 1: 重写 `cancelStepCount` 计算逻辑**

找到 `cancelStepCount` computed（约 line 522-528），替换为：

```javascript
/** 取消向导总步数（基于发货+收款状态） */
const cancelStepCount = computed(() => {
  const preview = cancelPreviewData.value
  if (!preview) return 1
  // 寄卖订单：无向导，直接确认
  if (preview.order_type === 'CONSIGN_OUT') return 0
  const hasPaid = preview.paid_amount > 0 || preview.rebate_used > 0
  // 未发货 + 未收款：无向导，走 confirm 对话框
  if (!preview.is_partial && !hasPaid) return 0
  // 未发货 + 已收款：1步（退款方式）
  if (!preview.is_partial && hasPaid) return 1
  // 部分发货 + 未收款：1步（商品确认）
  if (preview.is_partial && !hasPaid) return 1
  // 部分发货 + 已收款：3步（商品→分配→退款）
  return 3
})
```

**Step 2: 重写 `handleCancelOrder` — 未收款未发货走 confirm 对话框**

找到 `handleCancelOrder` 函数（约 line 622-646），替换为：

```javascript
/** 发起取消订单——先获取预览数据，根据情况决定流程 */
const handleCancelOrder = async (orderId) => {
  try {
    const { data } = await cancelPreview(orderId)
    cancelPreviewData.value = data
    const hasPaid = data.paid_amount > 0 || data.rebate_used > 0

    // 寄卖 或 (未发货+未收款)：直接 confirm 对话框
    if (data.order_type === 'CONSIGN_OUT' || (!data.is_partial && !hasPaid)) {
      const confirmed = await appStore.customConfirm('确认取消', `确认取消订单 ${data.order_no}？`)
      if (!confirmed) return
      // 直接提交取消
      cancelForm.refund_amount = 0
      cancelForm.refund_rebate = 0
      cancelForm.refund_method = 'balance'
      cancelForm.refund_payment_method = 'cash'
      cancelForm.new_order_paid_amount = 0
      cancelForm.new_order_rebate_used = 0
      cancelForm.item_allocations = []
      await confirmCancel()
      return
    }

    // 需要向导：初始化表单数据
    cancelForm.new_order_paid_amount = data.default_new_paid
    cancelForm.new_order_rebate_used = data.default_new_rebate
    cancelForm.item_allocations = (data.shipped_items || []).map(si => ({
      order_item_id: si.order_item_id,
      product_name: si.product_name,
      product_sku: si.product_sku,
      shipped_qty: si.shipped_qty,
      amount: si.amount,
      paid: si.default_paid || si.amount,
      rebate: si.default_rebate || 0
    }))
    cancelForm.refund_amount = data.default_refund
    cancelForm.refund_rebate = data.default_refund_rebate
    cancelForm.refund_method = 'balance'
    cancelForm.refund_payment_method = 'cash'
    cancelStep.value = 1
    showCancelModal.value = true
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '获取取消预览失败', 'error')
  }
}
```

**Step 3: 重写 `nextCancelStep` — 适配新的步数逻辑**

找到 `nextCancelStep` 函数（约 line 678-700），替换为：

```javascript
/** 取消向导下一步 */
const nextCancelStep = () => {
  const preview = cancelPreviewData.value
  if (!preview) return
  const hasPaid = preview.paid_amount > 0 || preview.rebate_used > 0
  const steps = cancelStepCount.value

  if (steps === 1) {
    // 1步向导：直接确认
    confirmCancel()
    return
  }

  // 3步向导：部分发货+已收款
  if (cancelStep.value === 1) {
    cancelStep.value = 2
  } else if (cancelStep.value === 2) {
    const sum = cancelForm.new_order_paid_amount + cancelForm.new_order_rebate_used
    if (Math.abs(sum - preview.new_order_amount) > 0.01) {
      appStore.showToast('付款 + 返利必须等于新订单金额 ¥' + preview.new_order_amount.toFixed(2), 'error')
      return
    }
    cancelStep.value = 3
  }
}
```

**Step 4: 重写 `prevCancelStep`**

找到 `prevCancelStep` 函数（约 line 702-715），替换为：

```javascript
/** 取消向导上一步 */
const prevCancelStep = () => {
  if (cancelStep.value === 3) {
    cancelStep.value = 2
  } else if (cancelStep.value === 2) {
    cancelStep.value = 1
  }
}
```

**Step 5: 修改向导 template — 适配新的 step 映射**

向导模板中 3 个 step 的 v-show 条件需要修改。当 `cancelStepCount === 1` 时，需要根据场景显示正确的内容：

在取消向导 template 区域（约 line 271-417），需要重构 step 显示逻辑。核心变化：

1. `cancelStepCount === 1 && is_partial && !hasPaid`：显示 Step 1（商品确认）
2. `cancelStepCount === 1 && !is_partial && hasPaid`：显示 Step 3（退款方式）
3. `cancelStepCount === 3`：3 步完整流程

修改 v-show 条件：

```html
<!-- 第1步：确认商品（仅 is_partial 时显示） -->
<div v-show="cancelStep === 1 && cancelPreviewData?.is_partial" class="space-y-4">
  <!-- 保持现有内容不变 -->
</div>

<!-- 第2步：逐商品财务分配（仅 3步向导的 step 2） -->
<div v-show="cancelStep === 2" class="space-y-4">
  <!-- 保持现有内容不变 -->
</div>

<!-- 第3步/唯一步：退款方式（有收款时显示） -->
<div v-show="(cancelStepCount === 3 && cancelStep === 3) || (cancelStepCount === 1 && !cancelPreviewData?.is_partial)" class="space-y-4">
  <!-- 保持现有内容不变 -->
</div>
```

**Step 6: 修改向导步骤指示器**

步骤指示器已根据 `cancelStepCount` 自动适配（`v-for="s in cancelStepCount"`），当 `cancelStepCount === 1` 时只显示一个圆点。添加一个条件不显示单步指示器：

```html
<div v-if="cancelStepCount > 1" class="flex items-center justify-center gap-2 mb-4">
```

这行已存在，无需修改。

**Step 7: 修改导航按钮**

导航按钮区域需适配：单步向导直接显示「确认取消」不显示「下一步」：

```html
<!-- 导航按钮 -->
<div class="flex gap-3 pt-4 mt-4 border-t">
  <button v-if="cancelStep > 1" @click="prevCancelStep" class="btn btn-secondary flex-1">&larr; 上一步</button>
  <button v-else @click="showCancelModal = false" class="btn btn-secondary flex-1">取消</button>
  <button v-if="cancelStep < cancelStepCount" @click="nextCancelStep" class="btn btn-primary flex-1">下一步 &rarr;</button>
  <button v-else @click="confirmCancel" class="btn flex-1" style="background:#ff3b30;color:#fff">确认取消订单</button>
</div>
```

这段逻辑已正确：当 `cancelStepCount === 1` 且 `cancelStep === 1` 时，`cancelStep < cancelStepCount` 为 false，直接显示「确认取消订单」。无需修改。

**Step 8: 验证前端编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 4: 构建部署 + 验证

**Step 1: 前端构建**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static
```

**Step 2: Docker 重建部署**

```bash
cd /Users/lin/Desktop/erp-4 && docker compose build erp && docker compose up -d erp
```

**Step 3: 验证场景**

在 8090 端口测试以下场景：
1. 未发货+未收款订单 → 点取消 → 应弹 confirm 对话框 → 直接取消
2. 未发货+已收款订单 → 点取消 → 应弹 1 步向导（退款方式）→ 确认取消
3. 部分发货+未收款 → 点取消 → 应弹 1 步向导（商品确认）→ 直接取消
4. 部分发货+已收款 → 点取消 → 应弹 3 步向导 → 完整流程

**Step 4: 提交**

```bash
git add -A && git commit -m "fix: optimize cancel order flow based on payment status"
```
