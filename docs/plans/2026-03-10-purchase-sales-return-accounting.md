# 采购/销售退货会计联动 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 采购退货生成独立退货单，推送到会计模块（红字应付单+付款退款单）和收款管理；销售退货自动生成收款退款单；采购导出增加退货信息。

**Architecture:** 新增 PurchaseReturn/PurchaseReturnItem 模型，重构采购退货接口以创建退货单并联动会计，补齐销售退货的收款退款单自动生成。前端新增退货单 Tab 和详情展示。

**Tech Stack:** FastAPI + Tortoise ORM + PostgreSQL (后端), Vue 3 + Tailwind CSS (前端)

---

### Task 1: 新增 PurchaseReturn 模型

**Files:**
- Modify: `backend/app/models/purchase.py` (末尾追加两个类)
- Modify: `backend/app/models/__init__.py` (添加导入)

**Step 1: 在 `models/purchase.py` 末尾追加两个模型**

```python
class PurchaseReturn(models.Model):
    id = fields.IntField(pk=True)
    return_no = fields.CharField(max_length=30, unique=True)
    purchase_order = fields.ForeignKeyField("models.PurchaseOrder", related_name="returns", on_delete=fields.CASCADE)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="purchase_returns", on_delete=fields.RESTRICT)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="purchase_returns", null=True, on_delete=fields.SET_NULL)
    total_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_refunded = fields.BooleanField(default=False)
    refund_status = fields.CharField(max_length=20, default="pending")  # pending / confirmed
    tracking_no = fields.CharField(max_length=100, null=True)
    reason = fields.TextField(null=True)
    created_by = fields.ForeignKeyField("models.User", related_name="created_purchase_returns", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "purchase_returns"
        indexes = (("purchase_order_id",), ("supplier_id",),)


class PurchaseReturnItem(models.Model):
    id = fields.IntField(pk=True)
    purchase_return = fields.ForeignKeyField("models.PurchaseReturn", related_name="items", on_delete=fields.CASCADE)
    purchase_item = fields.ForeignKeyField("models.PurchaseOrderItem", related_name="return_items", null=True, on_delete=fields.SET_NULL)
    product = fields.ForeignKeyField("models.Product", related_name="purchase_return_items", on_delete=fields.RESTRICT)
    quantity = fields.IntField()
    unit_price = fields.DecimalField(max_digits=12, decimal_places=2)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        table = "purchase_return_items"
        indexes = (("purchase_return_id",),)
```

**Step 2: 在 `models/__init__.py` 添加导入**

在 `from app.models.purchase import PurchaseOrder, PurchaseOrderItem` 行追加:
```python
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, PurchaseReturn, PurchaseReturnItem
```

**Step 3: Commit**

```
feat: 新增 PurchaseReturn + PurchaseReturnItem 模型
```

---

### Task 2: 数据库迁移

**Files:**
- Modify: `backend/app/migrations.py`

**Step 1: 在 `run_migrations()` 函数末尾（`generate_schemas` 调用之前）添加迁移函数调用**

```python
await migrate_purchase_returns(conn)
```

**Step 2: 添加迁移函数**

遵循项目现有模式（idempotent DDL）。因为模型使用 Tortoise ORM，而项目已有 `Tortoise.generate_schemas(safe=True)` 调用，新表会被自动创建。只需确保 `generate_schemas(safe=True)` 在迁移流程中被调用即可。

检查 `run_migrations()` 末尾是否已有 `await Tortoise.generate_schemas(safe=True)` — 如果有，无需额外 DDL，ORM 会自动建表。如果没有，添加建表 SQL：

```python
async def migrate_purchase_returns(conn):
    """创建采购退货单表（如不存在）"""
    await conn.execute_script("""
        CREATE TABLE IF NOT EXISTS purchase_returns (
            id SERIAL PRIMARY KEY,
            return_no VARCHAR(30) UNIQUE NOT NULL,
            purchase_order_id INT NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
            supplier_id INT NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
            account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL,
            total_amount DECIMAL(12,2) DEFAULT 0,
            is_refunded BOOLEAN DEFAULT FALSE,
            refund_status VARCHAR(20) DEFAULT 'pending',
            tracking_no VARCHAR(100),
            reason TEXT,
            created_by_id INT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_pr_po ON purchase_returns(purchase_order_id);
        CREATE INDEX IF NOT EXISTS idx_pr_supplier ON purchase_returns(supplier_id);

        CREATE TABLE IF NOT EXISTS purchase_return_items (
            id SERIAL PRIMARY KEY,
            purchase_return_id INT NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
            purchase_item_id INT REFERENCES purchase_order_items(id) ON DELETE SET NULL,
            product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
            quantity INT NOT NULL,
            unit_price DECIMAL(12,2) NOT NULL,
            amount DECIMAL(12,2) NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pri_return ON purchase_return_items(purchase_return_id);
    """)
```

**Step 3: Commit**

```
feat: 采购退货单建表迁移
```

---

### Task 3: 重构采购退货接口

**Files:**
- Modify: `backend/app/routers/purchase_orders.py` (lines 696-799, return endpoint)
- Modify: `backend/app/services/ap_service.py` (新增 return 相关函数)

**Step 1: 在 `ap_service.py` 新增退货应付/付款退款函数**

```python
async def create_return_payable_and_refund(
    account_set_id: int,
    supplier_id: int,
    purchase_order_id: int,
    purchase_return_id: int,
    return_amount: Decimal,
    creator=None,
):
    """采购退货 → 红字应付单 + 付款退款单"""
    from datetime import date
    today = date.today()

    # 1. 红字应付单（负金额）
    bill_no = await _generate_bill_no("YF")
    payable = await PayableBill.create(
        bill_no=bill_no,
        account_set_id=account_set_id,
        supplier_id=supplier_id,
        purchase_order_id=purchase_order_id,
        bill_date=today,
        total_amount=-return_amount,   # 负数
        paid_amount=-return_amount,
        unpaid_amount=Decimal("0"),
        status="completed",
        creator=creator,
        remark=f"采购退货自动生成 (退货单关联)",
    )

    # 2. 付款退款单 — 找到原始付款单
    original_disb = await DisbursementBill.filter(
        account_set_id=account_set_id,
        supplier_id=supplier_id,
    ).order_by("-id").first()

    if original_disb:
        refund_no = await _generate_bill_no("FKTK")
        await DisbursementRefundBill.create(
            bill_no=refund_no,
            account_set_id=account_set_id,
            supplier_id=supplier_id,
            original_disbursement=original_disb,
            refund_date=today,
            amount=return_amount,
            reason="采购退货退款",
            status="draft",
            creator=creator,
        )

    return payable
```

注意：`_generate_bill_no` 是项目已有的编号生成函数，需确认其实际签名。如果不存在，参考 `create_payable_bill` 中的编号生成逻辑。

**Step 2: 重构 `purchase_orders.py` 的 return endpoint (lines 696-799)**

在现有退货逻辑中（库存扣减、PO 字段更新之后），增加：

```python
# === 新增：创建退货单记录 ===
from app.models.purchase import PurchaseReturn, PurchaseReturnItem

# 生成退货单号
today_str = datetime.now().strftime("%Y%m%d")
last = await PurchaseReturn.filter(return_no__startswith=f"PR-{today_str}").order_by("-id").first()
seq = 1
if last:
    try: seq = int(last.return_no.split("-")[-1]) + 1
    except: pass
return_no = f"PR-{today_str}-{seq:03d}"

pr = await PurchaseReturn.create(
    return_no=return_no,
    purchase_order=po,
    supplier_id=po.supplier_id,
    account_set_id=po.account_set_id,
    total_amount=total_return_amount,
    is_refunded=data.is_refunded,
    refund_status="pending" if data.is_refunded else "n/a",
    tracking_no=data.tracking_no,
    created_by=user,
)
# 退货明细
for item_data in validated_items:  # 已验证的退货行列表
    await PurchaseReturnItem.create(
        purchase_return=pr,
        purchase_item_id=item_data["item_id"],
        product_id=item_data["product_id"],
        quantity=item_data["return_quantity"],
        unit_price=item_data["unit_price"],
        amount=item_data["amount"],
    )

# === 新增：推送会计模块 ===
if po.account_set_id:
    try:
        from app.services.ap_service import create_return_payable_and_refund
        await create_return_payable_and_refund(
            account_set_id=po.account_set_id,
            supplier_id=po.supplier_id,
            purchase_order_id=po.id,
            purchase_return_id=pr.id,
            return_amount=total_return_amount,
            creator=user,
        )
    except Exception as e:
        logger.error(f"采购退货会计推送失败: {e}")

# === 新增：推送收款管理（is_refunded=true 时） ===
if data.is_refunded:
    try:
        from app.models.finance import Payment
        await Payment.create(
            customer_id=None,  # 采购退款无客户
            supplier_id=po.supplier_id,
            order_ids=[],
            amount=total_return_amount,
            payment_method="bank_transfer",
            source="PURCHASE_RETURN",
            status="pending",  # 待出纳确认
            created_by=user,
            remark=f"采购退货退款 {return_no}",
            purchase_return_id=pr.id,
        )
    except Exception as e:
        logger.error(f"采购退货收款推送失败: {e}")
```

注意：`Payment` 模型可能需要额外字段 `supplier_id`, `source`, `purchase_return_id`。需检查现有 Payment 模型并适配。如果 Payment 模型不适合，改为在 `FinancePaymentsPanel` 的后端接口中新增一个"待确认收款"记录，或复用收款管理的现有数据结构。

**Step 3: Commit**

```
feat: 采购退货创建退货单 + 推送会计/收款管理
```

---

### Task 4: 采购退货单 API（CRUD + 列表）

**Files:**
- Create: `backend/app/routers/purchase_returns.py`
- Modify: `backend/main.py` (注册路由)

**Step 1: 创建 `purchase_returns.py`**

```python
"""采购退货单路由"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.auth import get_current_user, require_permission
from app.models import User, PurchaseReturn, PurchaseReturnItem

router = APIRouter(prefix="/api/purchase-returns", tags=["purchase-returns"])


@router.get("")
async def list_purchase_returns(
    supplier_id: int | None = None,
    purchase_order_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    user: User = Depends(require_permission("purchase")),
):
    """退货单列表（分页）"""
    q = PurchaseReturn.all()
    if supplier_id:
        q = q.filter(supplier_id=supplier_id)
    if purchase_order_id:
        q = q.filter(purchase_order_id=purchase_order_id)
    total = await q.count()
    items = await q.order_by("-created_at").offset(offset).limit(limit).select_related(
        "purchase_order", "supplier", "created_by"
    )
    result = []
    for pr in items:
        pr_items = await PurchaseReturnItem.filter(purchase_return=pr).select_related("product")
        result.append({
            "id": pr.id,
            "return_no": pr.return_no,
            "purchase_order_id": pr.purchase_order_id,
            "po_no": pr.purchase_order.po_no,
            "supplier_name": pr.supplier.name,
            "total_amount": float(pr.total_amount),
            "is_refunded": pr.is_refunded,
            "refund_status": pr.refund_status,
            "tracking_no": pr.tracking_no,
            "reason": pr.reason,
            "created_by_name": pr.created_by.display_name if pr.created_by else None,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
            "items": [{
                "id": it.id,
                "product_name": it.product.name,
                "product_sku": it.product.sku,
                "quantity": it.quantity,
                "unit_price": float(it.unit_price),
                "amount": float(it.amount),
            } for it in pr_items],
        })
    return {"items": result, "total": total}


@router.get("/{return_id}")
async def get_purchase_return(return_id: int, user: User = Depends(require_permission("purchase"))):
    """退货单详情"""
    pr = await PurchaseReturn.get_or_none(id=return_id).select_related(
        "purchase_order", "supplier", "created_by"
    )
    if not pr:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="退货单不存在")
    pr_items = await PurchaseReturnItem.filter(purchase_return=pr).select_related("product")
    return {
        "id": pr.id,
        "return_no": pr.return_no,
        "purchase_order_id": pr.purchase_order_id,
        "po_no": pr.purchase_order.po_no,
        "supplier_id": pr.supplier_id,
        "supplier_name": pr.supplier.name,
        "total_amount": float(pr.total_amount),
        "is_refunded": pr.is_refunded,
        "refund_status": pr.refund_status,
        "tracking_no": pr.tracking_no,
        "reason": pr.reason,
        "created_by_name": pr.created_by.display_name if pr.created_by else None,
        "created_at": pr.created_at.isoformat() if pr.created_at else None,
        "items": [{
            "id": it.id,
            "product_name": it.product.name,
            "product_sku": it.product.sku,
            "quantity": it.quantity,
            "unit_price": float(it.unit_price),
            "amount": float(it.amount),
        } for it in pr_items],
    }
```

**Step 2: 在 `main.py` 注册路由**

```python
from app.routers import purchase_returns
app.include_router(purchase_returns.router)
```

**Step 3: Commit**

```
feat: 采购退货单 CRUD API
```

---

### Task 5: 销售退货自动生成收款退款单

**Files:**
- Modify: `backend/app/routers/orders.py` (lines 144-157, RETURN 处理)

**Step 1: 在现有红字应收单创建逻辑之后，增加 ReceiptRefundBill 自动生成**

在 `orders.py` 的 RETURN 处理块中（line 157 之后）追加：

```python
# 销售退货 + 已退款 → 自动生成收款退款单
if data.order_type == "RETURN" and data.refunded and getattr(order, "account_set_id", None):
    try:
        from app.models.ar_ap import ReceiptBill, ReceiptRefundBill
        # 查找原订单的收款单
        original_receipt = await ReceiptBill.filter(
            account_set_id=order.account_set_id,
            customer_id=order.customer_id,
        ).order_by("-id").first()

        if original_receipt:
            from app.services.ar_service import _generate_bill_no
            refund_no = await _generate_bill_no("SKTK")
            await ReceiptRefundBill.create(
                bill_no=refund_no,
                account_set_id=order.account_set_id,
                customer_id=order.customer_id,
                original_receipt=original_receipt,
                refund_date=date.today(),
                amount=abs(total_amount),
                reason=f"销售退货退款 ({order.order_no})",
                status="draft",
                creator=user,
            )
    except Exception as e:
        logger.error(f"销售退货自动生成收款退款单失败: {e}")
```

注意：`_generate_bill_no` 需确认是否存在。若不存在，参考项目中 ReceiptBill 的编号生成方式实现。

**Step 2: Commit**

```
feat: 销售退货自动生成收款退款单
```

---

### Task 6: 采购导出增加退货列

**Files:**
- Modify: `backend/app/routers/purchase_orders.py` (lines 80-159, export endpoint)

**Step 1: 在 CSV header 中增加退货列**

找到 CSV writer 的 header 行，追加：`退货数量`, `退货金额`, `退款状态`

**Step 2: 在每行数据中填充退货字段**

```python
# 在循环写每个 item 行时：
returned_qty = item.returned_quantity
return_amount = float(po.return_amount) if po.return_amount else 0
refund_status = "已退款" if po.is_refunded else ("转为在账资金" if po.return_amount and po.return_amount > 0 else "")
# 写入 row 追加这三个字段
```

**Step 3: Commit**

```
feat: 采购导出增加退货数量/金额/退款状态列
```

---

### Task 7: 前端 — 采购退货单 Tab

**Files:**
- Create: `frontend/src/components/business/purchase/PurchaseReturnTab.vue`
- Create: `frontend/src/api/purchaseReturn.js`
- Modify: `frontend/src/views/PurchaseView.vue` (添加 Tab)

**Step 1: 创建 API 模块 `api/purchaseReturn.js`**

```javascript
import api from './index'
export const getPurchaseReturns = (params) => api.get('/purchase-returns', { params })
export const getPurchaseReturn = (id) => api.get(`/purchase-returns/${id}`)
```

**Step 2: 创建 `PurchaseReturnTab.vue`**

参考 `PurchaseReceiptTab.vue` 的结构（筛选行 + 表格 + 分页 + 详情弹窗）：

- 表格列：退货单号、关联采购单号、供应商、退货金额、退款状态、退货时间
- 退款状态用 StatusBadge 显示（pending=待退款、confirmed=已到账、n/a=转为在账资金）
- 点击行弹出详情弹窗，显示退货明细（商品 SKU、名称、数量、单价、小计）
- 分页使用 `usePagination(50)`

**Step 3: 修改 `PurchaseView.vue` 添加 Tab**

在 AppTabs 的 tabs 数组中追加：
```javascript
{ value: 'returns', label: '退货单' }
```

在 Transition 块中添加条件渲染：
```html
<PurchaseReturnTab v-else-if="purchaseTab === 'returns'" key="returns" />
```

**Step 4: Commit**

```
feat: 前端采购退货单 Tab
```

---

### Task 8: 前端 — 采购单详情展示关联退货单

**Files:**
- Modify: `frontend/src/components/business/purchase/PurchaseOrderDetail.vue`
- Modify: `backend/app/routers/purchase_orders.py` (detail endpoint 返回关联退货单)

**Step 1: 后端 — 在 GET /purchase-orders/{id} 返回值中追加 returns 字段**

在详情接口的响应中追加：

```python
# 查询关联退货单
returns = await PurchaseReturn.filter(purchase_order_id=po_id).order_by("-created_at")
result["returns"] = [{
    "id": r.id,
    "return_no": r.return_no,
    "total_amount": float(r.total_amount),
    "is_refunded": r.is_refunded,
    "refund_status": r.refund_status,
    "created_at": r.created_at.isoformat() if r.created_at else None,
} for r in returns]
```

**Step 2: 前端 — 在详情弹窗中展示退货单列表**

在现有"退货信息"区块之后（或替换之），添加退货单列表区域：

```html
<div v-if="purchaseOrderDetail.returns?.length" class="mt-3">
  <h4 class="font-semibold text-sm mb-2">关联退货单</h4>
  <div v-for="r in purchaseOrderDetail.returns" :key="r.id"
       class="flex justify-between items-center p-2 bg-elevated rounded mb-1 text-sm">
    <span class="font-mono text-primary">{{ r.return_no }}</span>
    <span class="font-semibold text-warning">¥{{ fmt(r.total_amount) }}</span>
    <StatusBadge type="refundStatus" :status="r.refund_status" />
    <span class="text-muted text-xs">{{ fmtDate(r.created_at) }}</span>
  </div>
</div>
```

**Step 3: Commit**

```
feat: 采购单详情展示关联退货单
```

---

### Task 9: 构建、部署、验证

**Step 1: 前端构建**

```bash
cd frontend && npm run build
```

预期：构建成功，无编译错误。

**Step 2: 重建 Docker**

```bash
docker compose build erp && docker compose up -d erp
```

预期：容器启动健康，迁移自动执行。

**Step 3: 验证**

1. 检查 Docker 日志无报错
2. 采购模块 — 新"退货单"Tab 正常加载
3. 对已完成采购单执行退货 → 检查退货单是否创建
4. 检查应付模块是否有红字应付单
5. 检查收款管理是否有待确认收款（仅退款模式）
6. 导出 CSV 检查新增列
7. 创建销售退货（refunded=true）→ 检查收款退款单是否自动生成

**Step 4: Commit all + push**

```
checkpoint: 采购/销售退货会计联动完整实现
```
