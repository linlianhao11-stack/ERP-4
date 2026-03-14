# 凭证系统三项修复 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复成本含税 bug、新增退货凭证生成 + AR/AP 退货单据展示、批量生成凭证支持多月选择

**Architecture:** 三个独立修复按依赖顺序串行实施。修复 1 改一行取值；修复 2 增加模型字段、service 逻辑、API 端点、前端 tab 组件；修复 3 改 service/router/前端的期间参数从单值到数组。

**Tech Stack:** FastAPI + Tortoise ORM + PostgreSQL（后端），Vue 3 + Tailwind CSS（前端）

**设计规格:** `docs/superpowers/specs/2026-03-14-voucher-fixes-design.md`

---

## Chunk 1: 修复 1 — 成本含税 bug + 数据库迁移

### Task 1: 修复采购入库 cost_price 取值

**Files:**
- Modify: `backend/app/routers/purchase_orders.py:640`

- [ ] **Step 1: 修改 cost_price 取值**

将 L640 从含税金额除以数量，改为直接使用不含税单价：

```python
# 改前
cost_price = poi.amount / poi.quantity if poi.quantity > 0 else poi.tax_inclusive_price

# 改后
cost_price = poi.tax_exclusive_price
```

注意：L786 的 `unit_amount = poi.amount / poi.quantity` 是退货退款金额（含税），语义不同，**不修改**。

- [ ] **Step 2: 验证后端启动无报错**

```bash
cd backend && python -c "from app.routers.purchase_orders import router; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/purchase_orders.py
git commit -m "fix: 采购入库 cost_price 改用不含税单价 tax_exclusive_price"
```

---

### Task 2: 数据库迁移 — Order 和 PurchaseReturn 增加凭证字段

**Files:**
- Modify: `backend/app/models/order.py`
- Modify: `backend/app/models/purchase.py`
- Create: `backend/migrations/2026-03-14-voucher-return-fields.sql`

- [ ] **Step 1: Order 模型增加 voucher 字段**

在 `backend/app/models/order.py` 的 `Order` 类中，`updated_at` 字段之前添加：

```python
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="return_order_vouchers")
    voucher_no = fields.CharField(max_length=30, null=True)
```

- [ ] **Step 2: PurchaseReturn 模型增加 voucher 字段**

在 `backend/app/models/purchase.py` 的 `PurchaseReturn` 类中，`created_at` 字段之前添加：

```python
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="purchase_return_vouchers")
    voucher_no = fields.CharField(max_length=30, null=True)
```

- [ ] **Step 3: 编写迁移 SQL**

创建 `backend/migrations/2026-03-14-voucher-return-fields.sql`：

```sql
-- Order 增加凭证关联（仅 RETURN 类型使用）
ALTER TABLE orders ADD COLUMN IF NOT EXISTS voucher_id INTEGER REFERENCES vouchers(id) ON DELETE SET NULL;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS voucher_no VARCHAR(30);
CREATE INDEX IF NOT EXISTS idx_orders_voucher_id ON orders(voucher_id);

-- PurchaseReturn 增加凭证关联
ALTER TABLE purchase_returns ADD COLUMN IF NOT EXISTS voucher_id INTEGER REFERENCES vouchers(id) ON DELETE SET NULL;
ALTER TABLE purchase_returns ADD COLUMN IF NOT EXISTS voucher_no VARCHAR(30);
CREATE INDEX IF NOT EXISTS idx_purchase_returns_voucher_id ON purchase_returns(voucher_id);
```

- [ ] **Step 4: 执行迁移**

```bash
cd backend && python -c "
import asyncio
from app.database import init_db, close_db
async def run():
    await init_db()
    from tortoise import Tortoise
    conn = Tortoise.get_connection('default')
    with open('migrations/2026-03-14-voucher-return-fields.sql') as f:
        for stmt in f.read().split(';'):
            stmt = stmt.strip()
            if stmt:
                await conn.execute_query(stmt)
    print('Migration OK')
    await close_db()
asyncio.run(run())
"
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/order.py backend/app/models/purchase.py backend/migrations/2026-03-14-voucher-return-fields.sql
git commit -m "feat: Order 和 PurchaseReturn 增加 voucher_id/voucher_no 字段"
```

---

## Chunk 2: 修复 2 — 退货凭证生成（后端）

### Task 3: AR Service — 销售退货红字出库凭证

**Files:**
- Modify: `backend/app/services/ar_service.py:186-359`（`generate_ar_vouchers` 函数）

- [ ] **Step 1: 在 generate_ar_vouchers 中增加退货凭证生成**

在 `generate_ar_vouchers` 函数末尾（`return vouchers` 之前），添加以下逻辑：

```python
    # 销售退货单 → 红字冲销出库凭证：借 发出商品1407（负数），贷 库存商品1405（负数）
    shipped_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1407", is_active=True
    ).first()
    inventory_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1405", is_active=True
    ).first()

    if shipped_acct and inventory_acct:
        return_orders = await Order.filter(
            account_set_id=account_set_id,
            order_type="RETURN",
            voucher_id=None,
            created_at__gte=period_start,
            created_at__lte=datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc),
        ).all()
        for ro in return_orders:
            cost = abs(ro.total_cost)
            if cost <= 0:
                continue
            async with transactions.in_transaction():
                p_name = f"{ro.created_at.year}-{ro.created_at.month:02d}"
                vno = await _next_voucher_no(account_set_id, "记", p_name)
                v = await Voucher.create(
                    account_set_id=account_set_id,
                    voucher_type="记",
                    voucher_no=vno,
                    period_name=p_name,
                    voucher_date=ro.created_at.date() if hasattr(ro.created_at, 'date') else ro.created_at,
                    summary=f"销售退货冲回 {ro.order_no}",
                    total_debit=-cost,
                    total_credit=-cost,
                    status="draft",
                    creator=user,
                    source_type="sales_return",
                    source_bill_id=ro.id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=1,
                    account_id=shipped_acct.id,
                    summary=f"销售退货冲回 {ro.order_no}",
                    debit_amount=-cost,
                    credit_amount=Decimal("0"),
                )
                await VoucherEntry.create(
                    voucher=v, line_no=2,
                    account_id=inventory_acct.id,
                    summary=f"销售退货冲回 {ro.order_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=-cost,
                )
                ro.voucher = v
                ro.voucher_no = vno
                await ro.save()
                vouchers.append({"id": v.id, "voucher_no": vno, "source": f"销售退货 {ro.order_no}"})
```

- [ ] **Step 2: 验证 import**

确保文件顶部已有 `from datetime import ... datetime, timezone` 和 `from app.models.order import Order`（已有）。

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/ar_service.py
git commit -m "feat: AR 批量生成凭证增加销售退货红字出库凭证"
```

---

### Task 4: AP Service — 采购退货红字入库凭证

**Files:**
- Modify: `backend/app/services/ap_service.py:154-262`（`generate_ap_vouchers` 函数）

- [ ] **Step 1: 增加 import**

在 `ap_service.py` 顶部增加：

```python
from app.models.purchase import PurchaseReturn, PurchaseReturnItem, PurchaseOrderItem
```

- [ ] **Step 2: 在 generate_ap_vouchers 中增加采购退货凭证生成**

在 `return vouchers` 之前添加：

```python
    # 采购退货单 → 红字冲销入库凭证：借 库存1405（负）+借 进项税222101（负）/ 贷 应付2202（负）
    inventory_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1405", is_active=True
    ).first()
    input_tax_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="222101", is_active=True
    ).first()

    if inventory_acct and input_tax_acct and ap_account:
        purchase_returns = await PurchaseReturn.filter(
            account_set_id=account_set_id,
            voucher_id=None,
            created_at__gte=period_start,
            created_at__lte=datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc),
        ).all()
        for pr in purchase_returns:
            if pr.total_amount <= 0:
                continue
            # 逐行计算不含税金额和税额
            pr_items = await PurchaseReturnItem.filter(purchase_return_id=pr.id).all()
            total_excl_tax = Decimal("0")
            total_tax = Decimal("0")
            for pri in pr_items:
                poi = await PurchaseOrderItem.filter(id=pri.purchase_item_id).first() if pri.purchase_item_id else None
                tax_rate = poi.tax_rate if poi else Decimal("0.13")
                item_excl = (pri.amount / (1 + tax_rate)).quantize(Decimal("0.01"))
                item_tax = pri.amount - item_excl
                total_excl_tax += item_excl
                total_tax += item_tax
            total_amount = total_excl_tax + total_tax

            async with transactions.in_transaction():
                p_name = f"{pr.created_at.year}-{pr.created_at.month:02d}"
                vno = await _next_voucher_no(account_set_id, "记", p_name)
                v = await Voucher.create(
                    account_set_id=account_set_id,
                    voucher_type="记",
                    voucher_no=vno,
                    period_name=p_name,
                    voucher_date=pr.created_at.date() if hasattr(pr.created_at, 'date') else pr.created_at,
                    summary=f"采购退货冲回 {pr.return_no}",
                    total_debit=-total_amount,
                    total_credit=-total_amount,
                    status="draft",
                    creator=user,
                    source_type="purchase_return",
                    source_bill_id=pr.id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=1,
                    account_id=inventory_acct.id,
                    summary=f"采购退货冲回 {pr.return_no}",
                    debit_amount=-total_excl_tax,
                    credit_amount=Decimal("0"),
                )
                await VoucherEntry.create(
                    voucher=v, line_no=2,
                    account_id=input_tax_acct.id,
                    summary=f"采购退货冲回 {pr.return_no} 进项税",
                    debit_amount=-total_tax,
                    credit_amount=Decimal("0"),
                )
                await VoucherEntry.create(
                    voucher=v, line_no=3,
                    account_id=ap_account.id,
                    summary=f"采购退货冲回 {pr.return_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=-total_amount,
                    aux_supplier_id=pr.supplier_id,
                )
                pr.voucher = v
                pr.voucher_no = vno
                await pr.save()
                vouchers.append({"id": v.id, "voucher_no": vno, "source": f"采购退货 {pr.return_no}"})
```

- [ ] **Step 3: 确保顶部有 datetime/timezone import**

```python
from datetime import date, datetime, timezone
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/ap_service.py
git commit -m "feat: AP 批量生成凭证增加采购退货红字入库凭证"
```

---

### Task 5: 后端 API — 销售退货列表端点

**Files:**
- Modify: `backend/app/routers/receivables.py`

- [ ] **Step 1: 增加 import**

在 receivables.py 顶部增加：

```python
from app.models.order import Order
```

- [ ] **Step 2: 添加销售退货列表 API**

在 `generate_ar_vouchers_endpoint` 之前添加：

```python
# ── 销售退货单（凭证视角） ──

@router.get("/sales-returns")
async def list_sales_returns(
    account_set_id: int = Query(...),
    customer_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ar_view")),
):
    query = Order.filter(account_set_id=account_set_id, order_type="RETURN")
    if customer_id:
        query = query.filter(customer_id=customer_id)

    total = await query.count()
    orders = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("customer")

    items = []
    for o in orders:
        items.append({
            "id": o.id,
            "order_no": o.order_no,
            "customer_id": o.customer_id,
            "customer_name": o.customer.name if o.customer else None,
            "total_amount": str(abs(o.total_amount)),
            "total_cost": str(abs(o.total_cost)),
            "return_date": o.created_at.strftime("%Y-%m-%d") if o.created_at else None,
            "voucher_no": o.voucher_no,
            "has_voucher": o.voucher_id is not None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/receivables.py
git commit -m "feat: 应收管理增加销售退货单列表 API"
```

---

### Task 6: 后端 API — 采购退货列表端点

**Files:**
- Modify: `backend/app/routers/payables.py`

- [ ] **Step 1: 增加 import**

在 payables.py 顶部增加：

```python
from app.models.purchase import PurchaseReturn
```

- [ ] **Step 2: 添加采购退货列表 API**

在 `generate_ap_vouchers_endpoint` 之前添加：

```python
# ── 采购退货单（凭证视角） ──

@router.get("/purchase-returns")
async def list_purchase_returns_for_ap(
    account_set_id: int = Query(...),
    supplier_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ap_view")),
):
    query = PurchaseReturn.filter(account_set_id=account_set_id)
    if supplier_id:
        query = query.filter(supplier_id=supplier_id)

    total = await query.count()
    returns = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("supplier", "purchase_order")

    items = []
    for pr in returns:
        items.append({
            "id": pr.id,
            "return_no": pr.return_no,
            "supplier_id": pr.supplier_id,
            "supplier_name": pr.supplier.name if pr.supplier else None,
            "purchase_order_no": pr.purchase_order.po_no if pr.purchase_order else None,
            "total_amount": str(pr.total_amount),
            "return_date": pr.created_at.strftime("%Y-%m-%d") if pr.created_at else None,
            "refund_status": pr.refund_status,
            "voucher_no": getattr(pr, 'voucher_no', None),
            "has_voucher": getattr(pr, 'voucher_id', None) is not None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/payables.py
git commit -m "feat: 应付管理增加采购退货单列表 API"
```

---

## Chunk 3: 修复 3 — 批量生成凭证支持多月

### Task 7: AR/AP Service — period_name 改 period_names

**Files:**
- Modify: `backend/app/services/ar_service.py`（`generate_ar_vouchers`）
- Modify: `backend/app/services/ap_service.py`（`generate_ap_vouchers`）

- [ ] **Step 1: 重构 generate_ar_vouchers 支持多月**

将 `generate_ar_vouchers` 的签名和逻辑改为：

```python
async def generate_ar_vouchers(account_set_id: int, period_names: list[str], user) -> dict:
```

核心改动：
1. 外层遍历 `period_names`
2. 每个月检查 `AccountingPeriod` 存在且未结账
3. 将原有的单月逻辑封装在循环内
4. 返回结构从 `list` 改为 `{"vouchers": [...], "summary": {...}}`

完整函数结构：

```python
async def generate_ar_vouchers(account_set_id: int, period_names: list[str], user) -> dict:
    vouchers = []
    summary = {}

    bank_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1002", is_active=True
    ).first()
    ar_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1122", is_active=True
    ).first()
    advance_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2203", is_active=True
    ).first()
    shipped_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1407", is_active=True
    ).first()
    inventory_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1405", is_active=True
    ).first()

    if not bank_account or not ar_account:
        raise ValueError("缺少必要科目：银行存款(1002)或应收账款(1122)")

    for period_name in period_names:
        period = await AccountingPeriod.filter(
            account_set_id=account_set_id, period_name=period_name
        ).first()
        if not period:
            summary[period_name] = {"count": 0, "skipped": True, "reason": "期间不存在"}
            continue
        if period.is_closed:
            summary[period_name] = {"count": 0, "skipped": True, "reason": "期间已结账"}
            continue

        period_start = date(period.year, period.month, 1)
        _, last_day = calendar.monthrange(period.year, period.month)
        period_end = date(period.year, period.month, last_day)
        month_vouchers = []

        # [原有的收款单/收款退款单/核销单/退货单逻辑，用 period_start/period_end 过滤]
        # ... 每种单据类型的生成逻辑保持不变，只是现在在循环内 ...
        # month_vouchers 收集当月生成的凭证

        summary[period_name] = {"count": len(month_vouchers), "skipped": False}
        vouchers.extend(month_vouchers)

    logger.info(f"AR凭证生成完成: {len(vouchers)} 张")
    return {"vouchers": vouchers, "summary": summary}
```

**实现要点（逐条落实）：**

1. 将原函数中从 `# 收款单` 到 `return vouchers` 之间的全部逻辑移入 `for period_name in period_names:` 循环内
2. **包括 Task 3 新增的销售退货凭证逻辑** —— 也需要移入循环内，使用循环变量 `period_start` / `period_end` 过滤，`p_name` 统一改用循环中的 `period_name`
3. 科目查询（`bank_account`、`ar_account`、`advance_account`、`shipped_acct`、`inventory_acct`）提取到循环外避免重复查询
4. 将各段中 `vouchers.append(...)` 改为 `month_vouchers.append(...)`，循环末尾 `vouchers.extend(month_vouchers)`
5. 每月的 `period` 校验（不存在 / 已结账）放在循环开头，跳过时记入 `summary`

- [ ] **Step 2: 同样重构 generate_ap_vouchers**

与 AR 相同的模式：签名改 `period_names: list[str]`，外层遍历月份，科目查询提到循环外，返回 `{"vouchers": [...], "summary": {...}}`。**Task 4 新增的采购退货凭证逻辑也需移入循环内**，`p_name` 改用循环变量 `period_name`。增加 `from datetime import datetime, timezone` import。

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/ar_service.py backend/app/services/ap_service.py
git commit -m "feat: AR/AP 凭证生成支持多月批量 period_names"
```

---

### Task 8: 后端路由 — 批量接口参数改多月

**Files:**
- Modify: `backend/app/routers/receivables.py`（`generate_ar_vouchers_endpoint`）
- Modify: `backend/app/routers/payables.py`（`generate_ap_vouchers_endpoint`）

- [ ] **Step 1: 修改 receivables.py 的接口**

```python
from pydantic import BaseModel

class GenerateVouchersRequest(BaseModel):
    period_names: list[str]

@router.post("/generate-ar-vouchers")
async def generate_ar_vouchers_endpoint(
    account_set_id: int = Query(...),
    data: GenerateVouchersRequest = ...,
    user: User = Depends(require_permission("accounting_ar_confirm")),
):
    try:
        result = await generate_ar_vouchers(account_set_id, data.period_names, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    total_count = len(result["vouchers"])
    return {"message": f"生成 {total_count} 张凭证", "vouchers": result["vouchers"], "summary": result["summary"]}
```

- [ ] **Step 2: 修改 payables.py 的接口**

同样的 pattern：引入 `GenerateVouchersRequest`，改为 Body 参数，返回含 summary。

```python
from pydantic import BaseModel

class GenerateVouchersRequest(BaseModel):
    period_names: list[str]

@router.post("/generate-ap-vouchers")
async def generate_ap_vouchers_endpoint(
    account_set_id: int = Query(...),
    data: GenerateVouchersRequest = ...,
    user: User = Depends(require_permission("accounting_ap_confirm")),
):
    try:
        result = await generate_ap_vouchers(account_set_id, data.period_names, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    total_count = len(result["vouchers"])
    return {"message": f"生成 {total_count} 张凭证", "vouchers": result["vouchers"], "summary": result["summary"]}
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/routers/receivables.py backend/app/routers/payables.py
git commit -m "feat: 批量凭证接口改为 Body 参数支持 period_names 数组"
```

---

## Chunk 4: 前端改动

### Task 9: 前端 API 层

**Files:**
- Modify: `frontend/src/api/accounting.js`

- [ ] **Step 1: 修改 generateArVouchers 和 generateApVouchers**

```javascript
// 改前
export const generateArVouchers = (accountSetId, periodName) =>
  api.post('/receivables/generate-ar-vouchers', null, { params: { account_set_id: accountSetId, period_name: periodName } })

// 改后
export const generateArVouchers = (accountSetId, periodNames) =>
  api.post('/receivables/generate-ar-vouchers', { period_names: periodNames }, { params: { account_set_id: accountSetId } })
```

```javascript
// 改前
export const generateApVouchers = (accountSetId, periodName) =>
  api.post('/payables/generate-ap-vouchers', null, { params: { account_set_id: accountSetId, period_name: periodName } })

// 改后
export const generateApVouchers = (accountSetId, periodNames) =>
  api.post('/payables/generate-ap-vouchers', { period_names: periodNames }, { params: { account_set_id: accountSetId } })
```

- [ ] **Step 2: 新增退货列表 API**

```javascript
// === 应收管理 - 销售退货 ===
export const getSalesReturns = (params) => api.get('/receivables/sales-returns', { params })

// === 应付管理 - 采购退货 ===
export const getPurchaseReturnsForAP = (params) => api.get('/payables/purchase-returns', { params })
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/accounting.js
git commit -m "feat: 前端 API 层适配多月批量 + 退货列表接口"
```

---

### Task 10: 销售退货 Tab 组件

**Files:**
- Create: `frontend/src/components/business/SalesReturnTab.vue`

- [ ] **Step 1: 创建组件**

参考 `ReceiptRefundBillsTab.vue` 的模式（无新增弹窗，纯只读列表），创建 `SalesReturnTab.vue`：

```vue
<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <span class="text-xs text-muted">销售退货单（用于冲抵出库凭证）</span>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2">退货单号</th>
              <th class="px-3 py-2">退货日期</th>
              <th class="px-3 py-2">客户</th>
              <th class="px-3 py-2 text-right">退货金额</th>
              <th class="px-3 py-2 text-right">退货成本</th>
              <th class="px-3 py-2">凭证号</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="6">
                <div class="text-center py-12 text-muted">
                  <p class="text-sm font-medium">暂无销售退货数据</p>
                </div>
              </td>
            </tr>
            <tr v-for="o in items" :key="o.id" class="hover:bg-elevated">
              <td class="px-3 py-2 font-mono text-[12px]">{{ o.order_no }}</td>
              <td class="px-3 py-2">{{ o.return_date }}</td>
              <td class="px-3 py-2">{{ o.customer_name }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(o.total_amount) }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(o.total_cost) }}</td>
              <td class="px-3 py-2 font-mono text-[12px]">
                <span v-if="o.voucher_no">{{ o.voucher_no }}</span>
                <span v-else class="text-muted">未生成</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import PageToolbar from '../common/PageToolbar.vue'
import { getSalesReturns } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useFormat } from '../../composables/useFormat'

const accountingStore = useAccountingStore()
const { fmtMoney } = useFormat()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const res = await getSalesReturns({
    account_set_id: accountingStore.currentAccountSetId,
    page: page.value,
    page_size: pageSize,
  })
  items.value = res.data.items
  total.value = res.data.total
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => loadList())
</script>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/business/SalesReturnTab.vue
git commit -m "feat: 新增 SalesReturnTab 销售退货列表组件"
```

---

### Task 11: 采购退货 Tab 组件

**Files:**
- Create: `frontend/src/components/business/PurchaseReturnTab.vue`

- [ ] **Step 1: 创建组件**

与 SalesReturnTab 类似，展示采购退货列表：

```vue
<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <span class="text-xs text-muted">采购退货单（用于冲抵入库凭证）</span>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2">退货单号</th>
              <th class="px-3 py-2">退货日期</th>
              <th class="px-3 py-2">供应商</th>
              <th class="px-3 py-2">采购单号</th>
              <th class="px-3 py-2 text-right">退货金额</th>
              <th class="px-3 py-2">退款状态</th>
              <th class="px-3 py-2">凭证号</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="7">
                <div class="text-center py-12 text-muted">
                  <p class="text-sm font-medium">暂无采购退货数据</p>
                </div>
              </td>
            </tr>
            <tr v-for="pr in items" :key="pr.id" class="hover:bg-elevated">
              <td class="px-3 py-2 font-mono text-[12px]">{{ pr.return_no }}</td>
              <td class="px-3 py-2">{{ pr.return_date }}</td>
              <td class="px-3 py-2">{{ pr.supplier_name }}</td>
              <td class="px-3 py-2 font-mono text-[12px]">{{ pr.purchase_order_no || '-' }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(pr.total_amount) }}</td>
              <td class="px-3 py-2">
                <span :class="pr.refund_status === 'completed' ? 'badge badge-green' : pr.refund_status === 'pending' ? 'badge badge-yellow' : 'badge badge-gray'">
                  {{ pr.refund_status === 'completed' ? '已退款' : pr.refund_status === 'pending' ? '待退款' : '无需退款' }}
                </span>
              </td>
              <td class="px-3 py-2 font-mono text-[12px]">
                <span v-if="pr.voucher_no">{{ pr.voucher_no }}</span>
                <span v-else class="text-muted">未生成</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import PageToolbar from '../common/PageToolbar.vue'
import { getPurchaseReturnsForAP } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useFormat } from '../../composables/useFormat'

const accountingStore = useAccountingStore()
const { fmtMoney } = useFormat()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const res = await getPurchaseReturnsForAP({
    account_set_id: accountingStore.currentAccountSetId,
    page: page.value,
    page_size: pageSize,
  })
  items.value = res.data.items
  total.value = res.data.total
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => loadList())
</script>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/business/PurchaseReturnTab.vue
git commit -m "feat: 新增 PurchaseReturnTab 采购退货列表组件"
```

---

### Task 12: ReceivablePanel — 集成退货 tab + 多月选择

**Files:**
- Modify: `frontend/src/components/business/ReceivablePanel.vue`

- [ ] **Step 1: 添加退货 tab 和多月选择**

完整替换 `ReceivablePanel.vue`：

```vue
<template>
  <div>
    <div class="flex items-center gap-2 mb-3 border-b pb-2">
      <AppTabs v-model="sub" :tabs="[
        { value: 'bills', label: '应收单' },
        { value: 'receipts', label: '收款单' },
        { value: 'refunds', label: '收款退款' },
        { value: 'writeoffs', label: '应收核销' },
        { value: 'delivery', label: '出库单' },
        { value: 'returns', label: '销售退货' },
      ]" container-class="" />
      <button @click="showPeriodPicker = true" :disabled="generating" class="ml-auto px-3 py-1.5 text-[12px] font-medium rounded-lg bg-purple-subtle text-purple-emphasis hover:bg-purple-subtle transition-colors shrink-0">
        {{ generating ? '生成中...' : '批量生成凭证' }}
      </button>
    </div>
    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <ReceivableBillsTab v-if="sub === 'bills'" key="bills" />
      <ReceiptBillsTab v-else-if="sub === 'receipts'" key="receipts" />
      <ReceiptRefundBillsTab v-else-if="sub === 'refunds'" key="refunds" />
      <WriteOffBillsTab v-else-if="sub === 'writeoffs'" key="writeoffs" />
      <SalesDeliveryTab v-else-if="sub === 'delivery'" key="delivery" />
      <SalesReturnTab v-else-if="sub === 'returns'" key="returns" />
    </Transition>

    <!-- 月份多选弹窗 -->
    <Transition name="fade">
      <div v-if="showPeriodPicker" class="modal-backdrop" @click.self="showPeriodPicker = false">
        <div class="modal max-w-sm">
          <div class="modal-header">
            <h3>选择生成凭证的月份</h3>
            <button @click="showPeriodPicker = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="space-y-1.5 max-h-64 overflow-y-auto">
              <label v-for="p in availablePeriods" :key="p.period_name"
                class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-elevated cursor-pointer text-sm"
                :class="{ 'opacity-50': p.is_closed }"
                :for="'ar-period-' + p.period_name">
                <input :id="'ar-period-' + p.period_name" type="checkbox" v-model="selectedPeriods" :value="p.period_name" :disabled="p.is_closed" class="rounded" />
                <span>{{ p.period_name }}</span>
                <span v-if="p.is_closed" class="text-xs text-muted ml-auto">已结账</span>
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showPeriodPicker = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handleGenerateVouchers" :disabled="!selectedPeriods.length || generating" class="btn btn-primary btn-sm">
              生成（{{ selectedPeriods.length }} 个月）
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import AppTabs from '../common/AppTabs.vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { generateArVouchers, getAccountingPeriods } from '../../api/accounting'
import ReceivableBillsTab from './ReceivableBillsTab.vue'
import ReceiptBillsTab from './ReceiptBillsTab.vue'
import ReceiptRefundBillsTab from './ReceiptRefundBillsTab.vue'
import WriteOffBillsTab from './WriteOffBillsTab.vue'
import SalesDeliveryTab from './SalesDeliveryTab.vue'
import SalesReturnTab from './SalesReturnTab.vue'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const sub = ref('bills')
const generating = ref(false)
const showPeriodPicker = ref(false)
const availablePeriods = ref([])
const selectedPeriods = ref([])

const loadPeriods = async () => {
  const setId = accountingStore.currentAccountSetId
  if (!setId) return
  const year = new Date().getFullYear()
  try {
    // 同时查询当年和上一年，支持跨年补生成
    const [res1, res2] = await Promise.all([
      getAccountingPeriods(setId, year),
      getAccountingPeriods(setId, year - 1),
    ])
    availablePeriods.value = [...(res2.data || []), ...(res1.data || [])]
    const current = accountingStore.currentAccountSet?.current_period
    if (current && !selectedPeriods.value.length) {
      selectedPeriods.value = [current]
    }
  } catch { /* ignore */ }
}

const handleGenerateVouchers = async () => {
  const setId = accountingStore.currentAccountSetId
  if (!setId || !selectedPeriods.value.length) return
  const label = selectedPeriods.value.join(', ')
  if (!await appStore.customConfirm('确认操作', `确认为 ${label} 批量生成应收凭证？`)) return
  showPeriodPicker.value = false
  generating.value = true
  try {
    const { data } = await generateArVouchers(setId, selectedPeriods.value)
    const total = data.vouchers?.length || 0
    if (total === 0) {
      appStore.showToast('无需生成凭证（已确认单据均已生成凭证）', 'info')
    } else {
      // 按月份汇总提示
      const parts = Object.entries(data.summary || {})
        .filter(([, v]) => v.count > 0)
        .map(([k, v]) => `${k}: ${v.count} 张`)
      appStore.showToast(`成功生成 ${total} 张凭证（${parts.join('，')}）`, 'success')
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '生成凭证失败', 'error')
  } finally {
    generating.value = false
  }
}

watch(() => accountingStore.currentAccountSetId, () => loadPeriods())
watch(showPeriodPicker, (v) => { if (v) loadPeriods() })
</script>
```

- [ ] **Step 2: 构建验证**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/business/ReceivablePanel.vue
git commit -m "feat: ReceivablePanel 集成销售退货 tab + 多月凭证生成"
```

---

### Task 13: PayablePanel — 集成退货 tab + 多月选择

**Files:**
- Modify: `frontend/src/components/business/PayablePanel.vue`

- [ ] **Step 1: 添加退货 tab 和多月选择**

与 ReceivablePanel 相同模式，完整替换 `PayablePanel.vue`：

```vue
<template>
  <div>
    <div class="flex items-center gap-2 mb-3 border-b pb-2">
      <AppTabs v-model="sub" :tabs="[
        { value: 'bills', label: '应付单' },
        { value: 'disbursements', label: '付款单' },
        { value: 'refunds', label: '付款退款' },
        { value: 'receipt', label: '入库单' },
        { value: 'returns', label: '采购退货' },
      ]" container-class="" />
      <button @click="showPeriodPicker = true" :disabled="generating" class="ml-auto px-3 py-1.5 text-[12px] font-medium rounded-lg bg-purple-subtle text-purple-emphasis hover:bg-purple-subtle transition-colors shrink-0">
        {{ generating ? '生成中...' : '批量生成凭证' }}
      </button>
    </div>
    <Transition name="slide-fade" mode="out-in" :duration="{ enter: 250, leave: 120 }">
      <PayableBillsTab v-if="sub === 'bills'" key="bills" />
      <DisbursementBillsTab v-else-if="sub === 'disbursements'" key="disbursements" />
      <DisbursementRefundBillsTab v-else-if="sub === 'refunds'" key="refunds" />
      <PurchaseReceiptTab v-else-if="sub === 'receipt'" key="receipt" />
      <PurchaseReturnTab v-else-if="sub === 'returns'" key="returns" />
    </Transition>

    <!-- 月份多选弹窗 -->
    <Transition name="fade">
      <div v-if="showPeriodPicker" class="modal-backdrop" @click.self="showPeriodPicker = false">
        <div class="modal max-w-sm">
          <div class="modal-header">
            <h3>选择生成凭证的月份</h3>
            <button @click="showPeriodPicker = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="space-y-1.5 max-h-64 overflow-y-auto">
              <label v-for="p in availablePeriods" :key="p.period_name"
                class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-elevated cursor-pointer text-sm"
                :class="{ 'opacity-50': p.is_closed }"
                :for="'ap-period-' + p.period_name">
                <input :id="'ap-period-' + p.period_name" type="checkbox" v-model="selectedPeriods" :value="p.period_name" :disabled="p.is_closed" class="rounded" />
                <span>{{ p.period_name }}</span>
                <span v-if="p.is_closed" class="text-xs text-muted ml-auto">已结账</span>
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showPeriodPicker = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handleGenerateVouchers" :disabled="!selectedPeriods.length || generating" class="btn btn-primary btn-sm">
              生成（{{ selectedPeriods.length }} 个月）
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import AppTabs from '../common/AppTabs.vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { generateApVouchers, getAccountingPeriods } from '../../api/accounting'
import PayableBillsTab from './PayableBillsTab.vue'
import DisbursementBillsTab from './DisbursementBillsTab.vue'
import DisbursementRefundBillsTab from './DisbursementRefundBillsTab.vue'
import PurchaseReceiptTab from './PurchaseReceiptTab.vue'
import PurchaseReturnTab from './PurchaseReturnTab.vue'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const sub = ref('bills')
const generating = ref(false)
const showPeriodPicker = ref(false)
const availablePeriods = ref([])
const selectedPeriods = ref([])

const loadPeriods = async () => {
  const setId = accountingStore.currentAccountSetId
  if (!setId) return
  const year = new Date().getFullYear()
  try {
    const [res1, res2] = await Promise.all([
      getAccountingPeriods(setId, year),
      getAccountingPeriods(setId, year - 1),
    ])
    availablePeriods.value = [...(res2.data || []), ...(res1.data || [])]
    const current = accountingStore.currentAccountSet?.current_period
    if (current && !selectedPeriods.value.length) {
      selectedPeriods.value = [current]
    }
  } catch { /* ignore */ }
}

const handleGenerateVouchers = async () => {
  const setId = accountingStore.currentAccountSetId
  if (!setId || !selectedPeriods.value.length) return
  const label = selectedPeriods.value.join(', ')
  if (!await appStore.customConfirm('确认操作', `确认为 ${label} 批量生成应付凭证？`)) return
  showPeriodPicker.value = false
  generating.value = true
  try {
    const { data } = await generateApVouchers(setId, selectedPeriods.value)
    const total = data.vouchers?.length || 0
    if (total === 0) {
      appStore.showToast('无需生成凭证（已确认单据均已生成凭证）', 'info')
    } else {
      const parts = Object.entries(data.summary || {})
        .filter(([, v]) => v.count > 0)
        .map(([k, v]) => `${k}: ${v.count} 张`)
      appStore.showToast(`成功生成 ${total} 张凭证（${parts.join('，')}）`, 'success')
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '生成凭证失败', 'error')
  } finally {
    generating.value = false
  }
}

watch(() => accountingStore.currentAccountSetId, () => loadPeriods())
watch(showPeriodPicker, (v) => { if (v) loadPeriods() })
</script>
```

- [ ] **Step 2: 构建验证**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/business/PayablePanel.vue
git commit -m "feat: PayablePanel 集成采购退货 tab + 多月凭证生成"
```

---

## Chunk 5: 最终验证

### Task 14: 全量构建 + 验证

- [ ] **Step 1: 前端全量构建**

```bash
cd frontend && npm run build
```

Expected: 编译成功，无错误。

- [ ] **Step 2: 后端启动检查**

```bash
cd backend && python -c "
from app.routers import receivables, payables, purchase_orders
print('Routers OK')
from app.services import ar_service, ap_service
print('Services OK')
"
```

- [ ] **Step 3: 最终提交（如有遗漏修复）**

```bash
git add -A && git status
# 如果有遗漏的修复，提交
```
