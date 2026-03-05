# 供应商返利按账套隔离 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将供应商返利余额和在账资金按账套隔离，并在采购付款确认时生成含返利分录的会计凭证。

**Architecture:** 新增 `SupplierAccountBalance` 联合表存储按账套隔离的余额，替代 `Supplier` 上的全局字段。采购流程和返利路由改为操作新表。付款确认时通过 `ap_service` 生成含返利红冲分录的凭证。

**Tech Stack:** FastAPI / Tortoise ORM / PostgreSQL / Vue 3 / Pinia

---

### Task 1: 新增 SupplierAccountBalance 模型

**Files:**
- Create: `backend/app/models/supplier_balance.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/rebate.py`

**Step 1: 创建模型文件**

```python
# backend/app/models/supplier_balance.py
from tortoise import fields, models


class SupplierAccountBalance(models.Model):
    id = fields.IntField(pk=True)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="account_balances", on_delete=fields.RESTRICT)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="supplier_balances", on_delete=fields.RESTRICT)
    rebate_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        table = "supplier_account_balances"
        unique_together = (("supplier", "account_set"),)
```

**Step 2: 给 RebateLog 增加 account_set_id 字段**

在 `backend/app/models/rebate.py` 的 `RebateLog` 类中添加：

```python
account_set = fields.ForeignKeyField("models.AccountSet", related_name="rebate_logs", null=True, on_delete=fields.SET_NULL)
```

**Step 3: 更新 `__init__.py` 导出**

在 `backend/app/models/__init__.py` 添加：

```python
from app.models.supplier_balance import SupplierAccountBalance
```

并将 `"SupplierAccountBalance"` 添加到 `__all__` 列表。

**Step 4: 验证模型加载**

Run: `cd ~/Desktop/erp-4/backend && python -c "from app.models import SupplierAccountBalance; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add backend/app/models/supplier_balance.py backend/app/models/__init__.py backend/app/models/rebate.py
git commit -m "feat: add SupplierAccountBalance model and RebateLog.account_set_id"
```

---

### Task 2: 数据库迁移

**Files:**
- Modify: `backend/app/migrations.py`

**Step 1: 添加迁移函数**

在 `migrations.py` 末尾添加新函数 `migrate_supplier_account_balance()`：

```python
async def migrate_supplier_account_balance():
    """供应商返利按账套隔离迁移：新表 + RebateLog 新列（幂等）"""
    from tortoise import Tortoise
    await Tortoise.generate_schemas(safe=True)

    conn = connections.get("default")

    # RebateLog 增加 account_set_id 列
    rl_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'rebate_logs'"
    )
    if "account_set_id" not in [c["name"] for c in rl_cols]:
        await conn.execute_query(
            "ALTER TABLE rebate_logs ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: rebate_logs 表添加 account_set_id 列")

    # 索引
    try:
        await conn.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_supplier_account_balances_supplier ON supplier_account_balances(supplier_id)"
        )
        await conn.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_rebate_logs_account_set ON rebate_logs(account_set_id)"
        )
    except Exception as e:
        logger.warning(f"创建索引失败（可忽略）: {e}")

    # 迁移现有余额数据：将 Supplier 上非零余额迁移到第一个账套
    from app.models.accounting import AccountSet
    from app.models.supplier_balance import SupplierAccountBalance
    first_set = await AccountSet.filter(is_active=True).order_by("id").first()
    if first_set:
        suppliers_with_balance = await Supplier.filter(
            models.Q(rebate_balance__gt=0) | models.Q(credit_balance__gt=0)
        ).all()
        for s in suppliers_with_balance:
            exists = await SupplierAccountBalance.filter(
                supplier_id=s.id, account_set_id=first_set.id
            ).exists()
            if not exists:
                await SupplierAccountBalance.create(
                    supplier_id=s.id,
                    account_set_id=first_set.id,
                    rebate_balance=s.rebate_balance,
                    credit_balance=s.credit_balance,
                )
                logger.info(f"迁移: 供应商 {s.name} 余额已迁移到账套 {first_set.name}")

    logger.info("供应商返利账套隔离迁移完成")
```

注意：需要在文件头部 import 中添加 `models`（来自 tortoise）以支持 `models.Q`。实际上已有 `from tortoise import connections`，需要改为 `from tortoise import connections, models as tortoise_models` 或在函数内使用 `from tortoise.queryset import Q`。

更简洁的方式是在函数内部使用原始 SQL 查询来查找非零余额的供应商，避免引入新的 import。

**Step 2: 在 `run_migrations()` 中调用**

在 `run_migrations()` 函数中，`await migrate_add_indexes()` 之后添加：

```python
await migrate_supplier_account_balance()
```

**Step 3: 验证迁移脚本语法**

Run: `cd ~/Desktop/erp-4/backend && python -c "from app.migrations import run_migrations; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/app/migrations.py
git commit -m "feat: add migration for supplier_account_balances table"
```

---

### Task 3: 改造返利路由

**Files:**
- Modify: `backend/app/routers/rebates.py`
- Modify: `backend/app/schemas/rebate.py`

**Step 1: 更新 Schema**

`backend/app/schemas/rebate.py` — `RebateChargeRequest` 增加 `account_set_id` 字段：

```python
class RebateChargeRequest(BaseModel):
    target_type: Literal["customer", "supplier"]
    target_id: int
    amount: Decimal = Field(gt=0)
    account_set_id: Optional[int] = None  # supplier 类型必填
    remark: Optional[str] = None
```

需要在顶部加 `from typing import Optional, Literal`（已有 `Literal`）。

**Step 2: 改造 `rebates.py` 三个端点**

`GET /summary`：
- 增加参数 `account_set_id: Optional[int] = None`
- supplier 类型：从 `SupplierAccountBalance` 读余额（需 JOIN supplier 拿 name）
- customer 类型：保持不变（customer 返利不分账套）

`POST /charge`：
- supplier 类型：充值到 `SupplierAccountBalance`（若不存在则创建）
- `RebateLog` 写入 `account_set_id`
- customer 类型：保持不变

`GET /logs`：
- 增加可选参数 `account_set_id`
- supplier 类型自动加 `account_set_id` 过滤

完整改造后的 `rebates.py`：

```python
"""返利管理路由"""
from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.expressions import F

from app.auth.dependencies import require_permission
from app.models import User, Customer, Supplier, RebateLog
from app.models.supplier_balance import SupplierAccountBalance
from app.schemas.rebate import RebateChargeRequest
from app.services.operation_log_service import log_operation

router = APIRouter(prefix="/api/rebates", tags=["返利管理"])


@router.get("/summary")
async def get_rebate_summary(target_type: str, account_set_id: int = None, user: User = Depends(require_permission("finance"))):
    """返利汇总"""
    if target_type == "customer":
        items = await Customer.filter(is_active=True).order_by("name")
        return [{"id": c.id, "name": c.name, "rebate_balance": float(c.rebate_balance)} for c in items]
    elif target_type == "supplier":
        if not account_set_id:
            raise HTTPException(status_code=400, detail="供应商返利需要指定账套")
        balances = await SupplierAccountBalance.filter(
            account_set_id=account_set_id
        ).select_related("supplier").all()
        # 也返回没有余额记录的活跃供应商（余额为0）
        balance_map = {b.supplier_id: b for b in balances}
        suppliers = await Supplier.filter(is_active=True).order_by("-created_at")
        return [{
            "id": s.id, "name": s.name,
            "rebate_balance": float(balance_map[s.id].rebate_balance) if s.id in balance_map else 0,
            "credit_balance": float(balance_map[s.id].credit_balance) if s.id in balance_map else 0,
        } for s in suppliers]
    else:
        raise HTTPException(status_code=400, detail="target_type 必须是 customer 或 supplier")


@router.get("/logs")
async def get_rebate_logs(target_type: str, target_id: int, account_set_id: int = None, user: User = Depends(require_permission("finance"))):
    """返利流水明细"""
    query = RebateLog.filter(target_type=target_type, target_id=target_id)
    if account_set_id:
        query = query.filter(account_set_id=account_set_id)
    logs = await query.order_by("-created_at").select_related("creator")
    return [{
        "id": l.id, "type": l.type, "amount": float(l.amount),
        "balance_after": float(l.balance_after),
        "reference_type": l.reference_type, "reference_id": l.reference_id,
        "remark": l.remark,
        "creator_name": l.creator.display_name if l.creator else None,
        "created_at": l.created_at.isoformat()
    } for l in logs]


@router.post("/charge")
async def charge_rebate(data: RebateChargeRequest, user: User = Depends(require_permission("finance_rebate"))):
    """返利充值"""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="充值金额必须大于0")
    async with transactions.in_transaction():
        if data.target_type == "customer":
            target = await Customer.filter(id=data.target_id, is_active=True).first()
            if not target:
                raise HTTPException(status_code=404, detail="客户不存在")
            await Customer.filter(id=data.target_id).update(rebate_balance=F('rebate_balance') + data.amount)
            await target.refresh_from_db()
            target_name = target.name
            balance_after = target.rebate_balance
            account_set_id = None
        elif data.target_type == "supplier":
            if not data.account_set_id:
                raise HTTPException(status_code=400, detail="供应商返利充值需要指定账套")
            target = await Supplier.filter(id=data.target_id, is_active=True).first()
            if not target:
                raise HTTPException(status_code=404, detail="供应商不存在")
            target_name = target.name
            # 获取或创建 SupplierAccountBalance
            bal = await SupplierAccountBalance.filter(
                supplier_id=data.target_id, account_set_id=data.account_set_id
            ).first()
            if not bal:
                bal = await SupplierAccountBalance.create(
                    supplier_id=data.target_id, account_set_id=data.account_set_id,
                    rebate_balance=0, credit_balance=0
                )
            await SupplierAccountBalance.filter(id=bal.id).update(
                rebate_balance=F('rebate_balance') + data.amount
            )
            await bal.refresh_from_db()
            balance_after = bal.rebate_balance
            account_set_id = data.account_set_id
        else:
            raise HTTPException(status_code=400, detail="target_type 必须是 customer 或 supplier")

        await RebateLog.create(
            target_type=data.target_type, target_id=data.target_id,
            type="charge", amount=data.amount,
            balance_after=balance_after,
            account_set_id=account_set_id,
            remark=data.remark, creator=user
        )
        await log_operation(user, "REBATE_CHARGE", data.target_type.upper(), data.target_id,
            f"返利充值 {target_name} ¥{float(data.amount):.2f}，余额 ¥{float(balance_after):.2f}")
    return {"message": "充值成功", "balance": float(balance_after)}
```

**Step 3: 验证语法**

Run: `cd ~/Desktop/erp-4/backend && python -c "from app.routers.rebates import router; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/app/routers/rebates.py backend/app/schemas/rebate.py
git commit -m "feat: refactor rebates router for account set isolation"
```

---

### Task 4: 改造采购单创建/取消/退货

**Files:**
- Modify: `backend/app/routers/purchase_orders.py`

**Step 1: 改造 `create_purchase_order` (L162-252)**

关键改动：
- 在事务开始时，如果有返利/在账资金使用，检查 `account_set_id` 必须存在
- `Supplier.rebate_balance` → `SupplierAccountBalance.rebate_balance`（按 account_set_id）
- `Supplier.credit_balance` → `SupplierAccountBalance.credit_balance`（按 account_set_id）
- `RebateLog.create()` 增加 `account_set_id` 参数

在文件顶部 import 区增加：
```python
from app.models.supplier_balance import SupplierAccountBalance
```

返利抵扣逻辑改造（L211-227 区域）：
```python
if total_rebate > 0:
    if not account_set_id:
        raise HTTPException(status_code=400, detail="使用返利抵扣时必须选择财务账套")
    bal = await SupplierAccountBalance.filter(
        supplier_id=supplier.id, account_set_id=account_set_id
    ).select_for_update().first()
    if not bal or bal.rebate_balance < total_rebate:
        available = float(bal.rebate_balance) if bal else 0
        raise HTTPException(status_code=400, detail=f"供应商返利余额不足，可用 ¥{available:.2f}，需要 ¥{float(total_rebate):.2f}")
    await SupplierAccountBalance.filter(id=bal.id).update(rebate_balance=F('rebate_balance') - total_rebate)
    await bal.refresh_from_db()
    po.rebate_used = total_rebate
    rebate_remark = f"[返利抵扣] 使用返利 ¥{float(total_rebate):.2f}"
    po.remark = f"{po.remark}\n{rebate_remark}" if po.remark else rebate_remark
    await RebateLog.create(
        target_type="supplier", target_id=supplier.id,
        type="use", amount=total_rebate,
        balance_after=bal.rebate_balance,
        account_set_id=account_set_id,
        reference_type="PURCHASE_ORDER", reference_id=po.id,
        remark=f"采购单 {po_no} 使用返利", creator=user
    )
```

在账资金抵扣逻辑改造（L229-246 区域）：
```python
if credit_amount > 0:
    if not account_set_id:
        raise HTTPException(status_code=400, detail="使用在账资金时必须选择财务账套")
    bal = await SupplierAccountBalance.filter(
        supplier_id=supplier.id, account_set_id=account_set_id
    ).select_for_update().first()
    if not bal or bal.credit_balance < credit_amount:
        available = float(bal.credit_balance) if bal else 0
        raise HTTPException(status_code=400, detail=f"供应商在账资金不足，可用 ¥{available:.2f}，需要 ¥{float(credit_amount):.2f}")
    await SupplierAccountBalance.filter(id=bal.id).update(credit_balance=F('credit_balance') - credit_amount)
    await bal.refresh_from_db()
    po.credit_used = credit_amount
    credit_remark = f"[在账资金抵扣] 使用在账资金 ¥{float(credit_amount):.2f}"
    po.remark = f"{po.remark}\n{credit_remark}" if po.remark else credit_remark
    await RebateLog.create(
        target_type="supplier", target_id=supplier.id,
        type="credit_use", amount=-credit_amount,
        balance_after=bal.credit_balance,
        account_set_id=account_set_id,
        reference_type="PURCHASE_ORDER", reference_id=po.id,
        remark=f"采购单 {po_no} 使用在账资金", creator=user
    )
```

**Step 2: 改造 `cancel_purchase_order` (L421-458)**

返利退还改造（L432-441）：
```python
if po.rebate_used and po.rebate_used > 0:
    if po.account_set_id:
        bal = await SupplierAccountBalance.filter(
            supplier_id=po.supplier_id, account_set_id=po.account_set_id
        ).first()
        if not bal:
            bal = await SupplierAccountBalance.create(
                supplier_id=po.supplier_id, account_set_id=po.account_set_id,
                rebate_balance=0, credit_balance=0
            )
        await SupplierAccountBalance.filter(id=bal.id).update(
            rebate_balance=F('rebate_balance') + po.rebate_used
        )
        await bal.refresh_from_db()
        await RebateLog.create(
            target_type="supplier", target_id=po.supplier_id,
            type="refund", amount=po.rebate_used,
            balance_after=bal.rebate_balance,
            account_set_id=po.account_set_id,
            reference_type="PURCHASE_ORDER", reference_id=po.id,
            remark=f"取消采购单 {po.po_no} 退还返利", creator=user
        )
```

在账资金退还改造（L443-452）同理操作 `SupplierAccountBalance.credit_balance`。

**Step 3: 改造 `return_purchase_order` (L649-742)**

在账资金增加改造（L726-737）：
```python
if not data.is_refunded:
    if po.account_set_id:
        bal = await SupplierAccountBalance.filter(
            supplier_id=po.supplier_id, account_set_id=po.account_set_id
        ).first()
        if not bal:
            bal = await SupplierAccountBalance.create(
                supplier_id=po.supplier_id, account_set_id=po.account_set_id,
                rebate_balance=0, credit_balance=0
            )
        await SupplierAccountBalance.filter(id=bal.id).update(
            credit_balance=F('credit_balance') + total_return_amount
        )
        await bal.refresh_from_db()
        await RebateLog.create(
            target_type="supplier", target_id=po.supplier_id,
            type="credit_charge", amount=total_return_amount,
            balance_after=bal.credit_balance,
            account_set_id=po.account_set_id,
            reference_type="PURCHASE_ORDER", reference_id=po.id,
            remark=f"采购退货 {po.po_no}，退货金额 ¥{float(total_return_amount):.2f} 转为在账资金",
            creator=user
        )
```

**Step 4: 验证语法**

Run: `cd ~/Desktop/erp-4/backend && python -c "from app.routers.purchase_orders import router; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add backend/app/routers/purchase_orders.py
git commit -m "feat: purchase orders use SupplierAccountBalance for rebate/credit"
```

---

### Task 5: 付款确认生成含返利分录的凭证

**Files:**
- Modify: `backend/app/routers/purchase_orders.py` (`confirm_purchase_payment`)
- Modify: `backend/app/services/ap_service.py`

**Step 1: 新增凭证生成函数**

在 `backend/app/services/ap_service.py` 末尾添加：

```python
async def create_rebate_payment_voucher(
    account_set_id: int,
    po,
    disbursement_bill,
    creator,
) -> Voucher | None:
    """采购付款时生成含返利分录的凭证（返利红冲主营业务成本+进项税）"""
    if not po.rebate_used or po.rebate_used <= 0:
        return None

    rebate = po.rebate_used
    total_with_rebate = po.total_amount + rebate  # 原始应付（未扣返利）
    actual_paid = po.total_amount  # 实付 = total_amount（已扣返利后）

    # 返利按13%税率拆分
    rebate_excl_tax = (rebate / Decimal("1.13")).quantize(Decimal("0.01"))
    rebate_tax = rebate - rebate_excl_tax

    # 查找科目
    ap_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2202", is_active=True
    ).first()
    bank_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1002", is_active=True
    ).first()
    # 主营业务成本-采购返利：使用 5401 或现有成本科目
    cost_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="5401", is_active=True
    ).first()
    # 结转进项税金：使用 2221 应交税费
    tax_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2221", is_active=True
    ).first()

    if not all([ap_account, bank_account, cost_account, tax_account]):
        logger.warning("缺少凭证科目(2202/1002/5401/2221)，跳过返利凭证生成")
        return None

    from app.models.accounting import AccountingPeriod
    from datetime import date
    today = date.today()
    period_name = f"{today.year}-{today.month:02d}"

    vno = await _next_voucher_no(account_set_id, "付", period_name)
    v = await Voucher.create(
        account_set_id=account_set_id,
        voucher_type="付",
        voucher_no=vno,
        period_name=period_name,
        voucher_date=today,
        summary=f"采购付款(含返利) {po.po_no}",
        total_debit=actual_paid,
        total_credit=actual_paid,
        status="draft",
        creator=creator,
        source_type="purchase_payment",
        source_bill_id=po.id,
    )

    line = 0
    # 借：应付账款（原始应付全额）
    line += 1
    await VoucherEntry.create(
        voucher=v, line_no=line,
        account_id=ap_account.id,
        summary=f"采购付款 {po.po_no}",
        debit_amount=total_with_rebate,
        credit_amount=Decimal("0"),
        aux_supplier_id=po.supplier_id,
    )
    # 借：主营业务成本-采购返利（负数红冲）
    line += 1
    await VoucherEntry.create(
        voucher=v, line_no=line,
        account_id=cost_account.id,
        summary=f"采购返利红冲 {po.po_no}",
        debit_amount=-rebate_excl_tax,
        credit_amount=Decimal("0"),
    )
    # 借：结转进项税金（负数红冲）
    line += 1
    await VoucherEntry.create(
        voucher=v, line_no=line,
        account_id=tax_account.id,
        summary=f"采购返利税金红冲 {po.po_no}",
        debit_amount=-rebate_tax,
        credit_amount=Decimal("0"),
    )
    # 贷：银行存款（实付金额）
    line += 1
    await VoucherEntry.create(
        voucher=v, line_no=line,
        account_id=bank_account.id,
        summary=f"采购付款 {po.po_no}",
        debit_amount=Decimal("0"),
        credit_amount=actual_paid,
    )

    # 关联付款单
    if disbursement_bill:
        disbursement_bill.voucher = v
        disbursement_bill.voucher_no = vno
        await disbursement_bill.save()

    logger.info(f"生成采购付款凭证(含返利): {vno}, 应付={total_with_rebate}, 返利={rebate}, 实付={actual_paid}")
    return v
```

**Step 2: 修改 `confirm_purchase_payment` 调用凭证生成**

在 `purchase_orders.py` 的 `confirm_purchase_payment` 中，在付款单生成钩子之后，添加凭证生成：

```python
# 现有的付款单生成代码之后...
disbursement_bill = None
if getattr(po, "account_set_id", None):
    try:
        from app.services.ap_service import create_disbursement_for_po_payment
        from app.models.ar_ap import PayableBill
        payable = await PayableBill.filter(
            account_set_id=po.account_set_id, purchase_order_id=po.id
        ).first()
        disbursement_bill = await create_disbursement_for_po_payment(
            account_set_id=po.account_set_id,
            supplier_id=po.supplier_id,
            payable_bill=payable,
            amount=po.total_amount,
            disbursement_method=data.payment_method or "对公转账",
            creator=user,
        )
    except Exception as e:
        logger.warning(f"自动生成付款单失败: {e}")

    # 含返利的凭证生成
    if po.rebate_used and po.rebate_used > 0:
        try:
            from app.services.ap_service import create_rebate_payment_voucher
            await create_rebate_payment_voucher(
                account_set_id=po.account_set_id,
                po=po,
                disbursement_bill=disbursement_bill,
                creator=user,
            )
        except Exception as e:
            logger.warning(f"生成返利凭证失败: {e}")
```

**Step 3: 验证语法**

Run: `cd ~/Desktop/erp-4/backend && python -c "from app.services.ap_service import create_rebate_payment_voucher; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/app/services/ap_service.py backend/app/routers/purchase_orders.py
git commit -m "feat: generate payment voucher with rebate deduction entries"
```

---

### Task 6: 供应商余额查询端点（供前端建单时读取按账套的余额）

**Files:**
- Modify: `backend/app/routers/suppliers.py`

**Step 1: 修改供应商列表和详情端点**

在供应商列表响应中增加 `account_balances` 字段，或提供一个独立端点。

更简洁的方式：在现有 `GET /suppliers` 响应中，如果请求带 `account_set_id` 参数，从 `SupplierAccountBalance` 读取对应账套的余额覆盖 `rebate_balance` / `credit_balance`。

在 `suppliers.py` 的列表端点添加可选参数 `account_set_id: int = None`：

```python
@router.get("")
async def list_suppliers(account_set_id: int = None, user: User = Depends(require_permission(...))):
    suppliers = await Supplier.filter(is_active=True).order_by(...)

    # 如果指定账套，从 SupplierAccountBalance 读取余额
    balance_map = {}
    if account_set_id:
        from app.models.supplier_balance import SupplierAccountBalance
        balances = await SupplierAccountBalance.filter(account_set_id=account_set_id).all()
        balance_map = {b.supplier_id: b for b in balances}

    result = []
    for s in suppliers:
        bal = balance_map.get(s.id)
        result.append({
            ...,
            "rebate_balance": float(bal.rebate_balance) if bal else 0,
            "credit_balance": float(bal.credit_balance) if bal else 0,
        })
    return result
```

同样修改 `GET /suppliers/{id}` 详情端点。

**Step 2: 修改供应商在账资金退款端点**

`POST /suppliers/{id}/credit-refund` 也需要改为操作 `SupplierAccountBalance`，需要增加 `account_set_id` 参数。

**Step 3: Commit**

```bash
git add backend/app/routers/suppliers.py
git commit -m "feat: supplier endpoints support account_set_id for balance queries"
```

---

### Task 7: 预置科目初始化

**Files:**
- Modify: `backend/app/migrations.py` (或 `backend/app/services/accounting_init.py`)

**Step 1: 确保科目 5401 和 2221 存在**

在迁移函数 `migrate_supplier_account_balance` 末尾，为每个账套检查并创建所需科目：

```python
# 确保凭证所需科目存在
from app.models.accounting import AccountSet, ChartOfAccount
for aset in await AccountSet.all():
    # 5401 主营业务成本（如果不存在）
    if not await ChartOfAccount.filter(account_set_id=aset.id, code="5401").exists():
        await ChartOfAccount.create(
            account_set_id=aset.id, code="5401", name="主营业务成本",
            level=1, category="cost", direction="debit", is_leaf=True
        )
    # 2221 应交税费（如果不存在）
    if not await ChartOfAccount.filter(account_set_id=aset.id, code="2221").exists():
        await ChartOfAccount.create(
            account_set_id=aset.id, code="2221", name="应交税费",
            level=1, category="liability", direction="credit", is_leaf=True
        )
```

**Step 2: Commit**

```bash
git add backend/app/migrations.py
git commit -m "feat: ensure chart of accounts 5401/2221 exist for rebate vouchers"
```

---

### Task 8: 前端 — 返利面板增加账套选择器

**Files:**
- Modify: `frontend/src/components/business/FinanceRebatesPanel.vue`
- Modify: `frontend/src/api/rebates.js`

**Step 1: 修改 API 模块**

`frontend/src/api/rebates.js`：所有调用增加 `account_set_id` 参数传递（已通过 params 传递，无需改函数签名，只需确保调用时传入）。

**Step 2: 修改 FinanceRebatesPanel.vue**

template 顶部 tab 栏旁增加账套选择器（仅供应商 tab 时显示）：

```html
<select v-if="rebateTab === 'supplier'" v-model="selectedAccountSetId" class="input text-sm w-40" @change="loadRebateSummaryData('supplier')">
  <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
</select>
```

script 中：
- 增加 props: `accountSets: Array`
- 增加 `selectedAccountSetId` ref，默认取 `accountSets[0]?.id`
- `loadRebateSummaryData('supplier')` 时传入 `account_set_id: selectedAccountSetId.value`
- `chargeRebate` 时传入 `account_set_id: selectedAccountSetId.value`
- `getRebateLogs` 时传入 `account_set_id: selectedAccountSetId.value`
- 汇总表格增加 `credit_balance` 列（在账资金）

**Step 3: 父组件传入 accountSets**

确认 `FinanceView.vue` 传入 `accountSets` props（如果还没有的话）。

**Step 4: Commit**

```bash
git add frontend/src/components/business/FinanceRebatesPanel.vue frontend/src/api/rebates.js
git commit -m "feat: rebates panel with account set selector"
```

---

### Task 9: 前端 — 采购单建单余额读取改造

**Files:**
- Modify: `frontend/src/components/business/purchase/PurchaseOrderForm.vue`

**Step 1: 修改 `selectPoSupplier` 方法**

选择供应商时，根据当前选中的 `account_set_id` 从供应商数据中读取对应账套的余额。

由于供应商列表 API 已支持 `account_set_id` 参数，需要在加载供应商时传入：

```javascript
const loadSuppliers = async () => {
  try {
    const params = {}
    if (poForm.account_set_id) params.account_set_id = poForm.account_set_id
    const { data } = await getSuppliers(params)
    suppliers.value = data
  } catch (e) {
    console.error(e)
  }
}
```

`getSuppliers` API 函数需要支持 params：

```javascript
// api/purchase.js
export const getSuppliers = (params) => api.get('/suppliers', { params })
```

**Step 2: 账套变更时重新加载供应商余额**

添加 watcher：当 `poForm.account_set_id` 变化时，重新加载供应商列表（带新 account_set_id），并重置已选供应商的余额显示：

```javascript
watch(() => poForm.account_set_id, () => {
  loadSuppliers()
  // 如果已选供应商，更新余额
  if (poForm.supplier_id) {
    const s = suppliers.value.find(x => x.id === parseInt(poForm.supplier_id))
    if (s) {
      poForm.supplier_rebate_balance = s.rebate_balance || 0
      poForm.supplier_credit_balance = s.credit_balance || 0
    }
  }
})
```

**Step 3: Commit**

```bash
git add frontend/src/components/business/purchase/PurchaseOrderForm.vue frontend/src/api/purchase.js
git commit -m "feat: purchase order form reads balance from account set"
```

---

### Task 10: 前端 — 采购单详情展示优化

**Files:**
- Modify: `frontend/src/components/business/purchase/PurchaseOrderDetail.vue`

**Step 1: 增强金额展示区域**

在详情弹窗的基本信息 grid 中，调整金额显示逻辑：

```html
<!-- 当有返利或在账资金时显示原价 -->
<div v-if="purchaseOrderDetail.rebate_used > 0 || purchaseOrderDetail.credit_used > 0">
  <span class="text-[#86868b]">原价合计:</span>
  <span class="font-semibold">¥{{ fmt(purchaseOrderDetail.total_amount + purchaseOrderDetail.rebate_used + (purchaseOrderDetail.credit_used || 0)) }}</span>
</div>
<div v-if="purchaseOrderDetail.rebate_used > 0">
  <span class="text-[#86868b]">返利抵扣:</span>
  <span class="text-[#34c759] font-semibold">-¥{{ fmt(purchaseOrderDetail.rebate_used) }}</span>
</div>
<div v-if="purchaseOrderDetail.credit_used > 0">
  <span class="text-[#86868b]">在账资金抵扣:</span>
  <span class="text-[#0071e3] font-semibold">-¥{{ fmt(purchaseOrderDetail.credit_used) }}</span>
</div>
<div>
  <span class="text-[#86868b]">实付金额:</span>
  <span class="font-semibold text-[#0071e3]">¥{{ fmt(purchaseOrderDetail.total_amount) }}</span>
</div>
```

**Step 2: Commit**

```bash
git add frontend/src/components/business/purchase/PurchaseOrderDetail.vue
git commit -m "feat: purchase order detail shows rebate/credit breakdown"
```

---

### Task 11: 测试

**Files:**
- Create: `backend/tests/test_supplier_balance.py`

**Step 1: 编写模型测试**

```python
"""供应商返利按账套隔离测试"""
import pytest
from decimal import Decimal
from app.models import Supplier, RebateLog
from app.models.accounting import AccountSet
from app.models.supplier_balance import SupplierAccountBalance


@pytest.mark.asyncio
async def test_supplier_account_balance_create():
    """测试 SupplierAccountBalance 创建和唯一约束"""
    supplier = await Supplier.create(name="测试供应商")
    aset = await AccountSet.create(
        code="TEST01", name="测试账套", start_year=2026, current_period="2026-01"
    )
    bal = await SupplierAccountBalance.create(
        supplier=supplier, account_set=aset,
        rebate_balance=Decimal("1000"), credit_balance=Decimal("500")
    )
    assert bal.rebate_balance == Decimal("1000")
    assert bal.credit_balance == Decimal("500")


@pytest.mark.asyncio
async def test_supplier_balance_isolation():
    """测试不同账套的余额隔离"""
    supplier = await Supplier.create(name="测试供应商2")
    aset1 = await AccountSet.create(
        code="SET_A", name="账套A", start_year=2026, current_period="2026-01"
    )
    aset2 = await AccountSet.create(
        code="SET_B", name="账套B", start_year=2026, current_period="2026-01"
    )
    await SupplierAccountBalance.create(
        supplier=supplier, account_set=aset1,
        rebate_balance=Decimal("1000"), credit_balance=0
    )
    await SupplierAccountBalance.create(
        supplier=supplier, account_set=aset2,
        rebate_balance=Decimal("2000"), credit_balance=0
    )
    b1 = await SupplierAccountBalance.filter(
        supplier=supplier, account_set=aset1
    ).first()
    b2 = await SupplierAccountBalance.filter(
        supplier=supplier, account_set=aset2
    ).first()
    assert b1.rebate_balance == Decimal("1000")
    assert b2.rebate_balance == Decimal("2000")


@pytest.mark.asyncio
async def test_rebate_log_with_account_set():
    """测试 RebateLog 记录 account_set_id"""
    from app.models import User
    user = await User.create(
        username="test_rebate_user", password_hash="x", display_name="Test"
    )
    supplier = await Supplier.create(name="供应商3")
    aset = await AccountSet.create(
        code="SET_C", name="账套C", start_year=2026, current_period="2026-01"
    )
    log = await RebateLog.create(
        target_type="supplier", target_id=supplier.id,
        type="charge", amount=Decimal("500"),
        balance_after=Decimal("500"),
        account_set_id=aset.id,
        creator=user
    )
    assert log.account_set_id == aset.id
    # 无账套的日志也应正常
    log2 = await RebateLog.create(
        target_type="customer", target_id=1,
        type="charge", amount=Decimal("100"),
        balance_after=Decimal("100"),
        creator=user
    )
    assert log2.account_set_id is None
```

**Step 2: 运行测试**

Run: `cd ~/Desktop/erp-4/backend && python -m pytest tests/test_supplier_balance.py -v`
Expected: 3 tests PASS

**Step 3: 运行全量测试确保无回归**

Run: `cd ~/Desktop/erp-4/backend && python -m pytest tests/ -v`
Expected: 所有测试 PASS（84+ tests）

**Step 4: Commit**

```bash
git add backend/tests/test_supplier_balance.py
git commit -m "test: add supplier account balance isolation tests"
```

---

### Task 12: Docker 部署验证

**Step 1: 构建并启动**

Run: `cd ~/Desktop/erp-4 && docker compose up --build -d`

**Step 2: 检查迁移日志**

Run: `docker compose logs erp | grep -i "供应商返利\|supplier_account"`

Expected: 看到迁移完成日志

**Step 3: 功能冒烟测试**

1. 打开返利面板 → 切换到供应商tab → 应该看到账套选择器
2. 选择账套 → 给供应商充值返利
3. 新建采购单 → 选择同一账套+供应商 → 应看到可用返利余额
4. 使用返利创建采购单 → 审核 → 付款确认
5. 检查凭证管理 → 应看到含返利分录的付款凭证
6. 查看返利明细 → 应看到充值和使用记录

**Step 4: Commit（如有修复）**
