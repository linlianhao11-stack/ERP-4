# 样机管理模块实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在库存模块下新增样机管理功能，支持样机台账、借还流程、处置退出和 Excel 导出。

**Architecture:** 台账 + 借还记录两层模型。样机（DemoUnit）是长期存在的资产实体，借还记录（DemoLoan）是每次借出归还的事务，处置记录（DemoDisposal）记录退出操作。前端放在 StockView 下作为二级 tab，复用 AppTabs/AppModal/AppTable 等通用组件。

**Tech Stack:** FastAPI + Tortoise ORM + PostgreSQL（后端）；Vue 3 Composition API + Tailwind CSS 4（前端）；openpyxl（Excel 导出）

**设计文档:** `docs/plans/2026-03-18-demo-unit-management-design.md`

---

## Task 1: 数据库迁移

**Files:**
- Create: `backend/migrations/2026-03-18-demo-unit-init.sql`

**Step 1: 编写迁移 SQL**

```sql
-- 样机管理模块初始化

-- 1. 样机台账
CREATE TABLE IF NOT EXISTS demo_units (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) NOT NULL UNIQUE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    sn_code_id INTEGER REFERENCES sn_codes(id) ON DELETE SET NULL,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'in_stock',
    condition VARCHAR(10) NOT NULL DEFAULT 'new',
    cost_price DECIMAL(12,2) NOT NULL DEFAULT 0,
    current_holder_type VARCHAR(10),
    current_holder_id INTEGER,
    total_loan_count INTEGER NOT NULL DEFAULT 0,
    total_loan_days INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demo_units_status ON demo_units(status);
CREATE INDEX IF NOT EXISTS idx_demo_units_product ON demo_units(product_id);
CREATE INDEX IF NOT EXISTS idx_demo_units_warehouse ON demo_units(warehouse_id);

-- 2. 借还记录
CREATE TABLE IF NOT EXISTS demo_loans (
    id SERIAL PRIMARY KEY,
    loan_no VARCHAR(30) NOT NULL UNIQUE,
    demo_unit_id INTEGER NOT NULL REFERENCES demo_units(id) ON DELETE RESTRICT,
    loan_type VARCHAR(20) NOT NULL,
    borrower_type VARCHAR(10) NOT NULL,
    borrower_id INTEGER NOT NULL,
    handler_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending_approval',
    loan_date DATE,
    expected_return_date DATE NOT NULL,
    actual_return_date DATE,
    condition_on_loan VARCHAR(10) NOT NULL,
    condition_on_return VARCHAR(10),
    return_notes TEXT,
    approved_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    purpose TEXT,
    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demo_loans_unit ON demo_loans(demo_unit_id);
CREATE INDEX IF NOT EXISTS idx_demo_loans_status ON demo_loans(status);
CREATE INDEX IF NOT EXISTS idx_demo_loans_borrower ON demo_loans(borrower_type, borrower_id);

-- 3. 处置记录
CREATE TABLE IF NOT EXISTS demo_disposals (
    id SERIAL PRIMARY KEY,
    demo_unit_id INTEGER NOT NULL REFERENCES demo_units(id) ON DELETE RESTRICT,
    disposal_type VARCHAR(20) NOT NULL,
    amount DECIMAL(12,2),
    refurbish_cost DECIMAL(12,2),
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    receivable_bill_id INTEGER,
    voucher_id INTEGER,
    target_warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE SET NULL,
    target_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    reason TEXT,
    approved_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demo_disposals_unit ON demo_disposals(demo_unit_id);
```

**Step 2: 执行迁移**

```bash
cd /Users/lin/Desktop/erp-4
orb start
docker exec -i erp4-db psql -U erp4 -d erp4 < backend/migrations/2026-03-18-demo-unit-init.sql
```

**Step 3: 验证表创建成功**

```bash
docker exec erp4-db psql -U erp4 -d erp4 -c "\dt demo_*"
```

Expected: 看到 demo_units, demo_loans, demo_disposals 三张表。

**Step 4: Commit**

```bash
git add backend/migrations/2026-03-18-demo-unit-init.sql
git commit -m "feat(demo): 样机管理模块数据库迁移"
```

---

## Task 2: 后端模型层

**Files:**
- Create: `backend/app/models/demo.py`
- Modify: `backend/app/models/__init__.py` — 注册新模型

**Step 1: 创建 Tortoise ORM 模型**

`backend/app/models/demo.py`:

```python
from __future__ import annotations

from tortoise import fields, models


class DemoUnit(models.Model):
    """样机台账"""

    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=30, unique=True)

    product = fields.ForeignKeyField(
        "models.Product", related_name="demo_units", on_delete=fields.RESTRICT,
    )
    sn_code = fields.ForeignKeyField(
        "models.SnCode", related_name="demo_units", null=True, on_delete=fields.SET_NULL,
    )
    warehouse = fields.ForeignKeyField(
        "models.Warehouse", related_name="demo_units", on_delete=fields.RESTRICT,
    )

    status = fields.CharField(max_length=20, default="in_stock")
    condition = fields.CharField(max_length=10, default="new")
    cost_price = fields.DecimalField(max_digits=12, decimal_places=2, default=0)

    current_holder_type = fields.CharField(max_length=10, null=True)
    current_holder_id = fields.IntField(null=True)

    total_loan_count = fields.IntField(default=0)
    total_loan_days = fields.IntField(default=0)
    notes = fields.TextField(null=True)

    created_by = fields.ForeignKeyField(
        "models.User", related_name="created_demo_units", null=True, on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "demo_units"
        ordering = ["-created_at"]


class DemoLoan(models.Model):
    """样机借还记录"""

    id = fields.IntField(pk=True)
    loan_no = fields.CharField(max_length=30, unique=True)

    demo_unit = fields.ForeignKeyField(
        "models.DemoUnit", related_name="loans", on_delete=fields.RESTRICT,
    )

    loan_type = fields.CharField(max_length=20)
    borrower_type = fields.CharField(max_length=10)
    borrower_id = fields.IntField()
    handler = fields.ForeignKeyField(
        "models.Employee", related_name="demo_loans", null=True, on_delete=fields.SET_NULL,
    )

    status = fields.CharField(max_length=20, default="pending_approval")

    loan_date = fields.DateField(null=True)
    expected_return_date = fields.DateField()
    actual_return_date = fields.DateField(null=True)

    condition_on_loan = fields.CharField(max_length=10)
    condition_on_return = fields.CharField(max_length=10, null=True)
    return_notes = fields.TextField(null=True)

    approved_by = fields.ForeignKeyField(
        "models.User", related_name="approved_demo_loans", null=True, on_delete=fields.SET_NULL,
    )
    approved_at = fields.DatetimeField(null=True)
    purpose = fields.TextField(null=True)

    created_by = fields.ForeignKeyField(
        "models.User", related_name="created_demo_loans", null=True, on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "demo_loans"
        ordering = ["-created_at"]


class DemoDisposal(models.Model):
    """样机处置记录"""

    id = fields.IntField(pk=True)

    demo_unit = fields.ForeignKeyField(
        "models.DemoUnit", related_name="disposals", on_delete=fields.RESTRICT,
    )

    disposal_type = fields.CharField(max_length=20)
    amount = fields.DecimalField(max_digits=12, decimal_places=2, null=True)
    refurbish_cost = fields.DecimalField(max_digits=12, decimal_places=2, null=True)

    order_id = fields.IntField(null=True)
    receivable_bill_id = fields.IntField(null=True)
    voucher_id = fields.IntField(null=True)

    target_warehouse_id = fields.IntField(null=True)
    target_location_id = fields.IntField(null=True)

    reason = fields.TextField(null=True)

    approved_by = fields.ForeignKeyField(
        "models.User", related_name="approved_demo_disposals", null=True, on_delete=fields.SET_NULL,
    )
    created_by = fields.ForeignKeyField(
        "models.User", related_name="created_demo_disposals", null=True, on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "demo_disposals"
        ordering = ["-created_at"]
```

**Step 2: 在 `__init__.py` 中注册模型**

在 `backend/app/models/__init__.py` 末尾的 import 区和 `__all__` 中添加：

```python
from app.models.demo import DemoUnit, DemoLoan, DemoDisposal
```

`__all__` 列表中追加 `"DemoUnit"`, `"DemoLoan"`, `"DemoDisposal"`。

**Step 3: 验证模型加载**

```bash
cd /Users/lin/Desktop/erp-4/backend && python -c "from app.models.demo import DemoUnit, DemoLoan, DemoDisposal; print('Models OK')"
```

**Step 4: Commit**

```bash
git add backend/app/models/demo.py backend/app/models/__init__.py
git commit -m "feat(demo): 添加样机台账/借还/处置 Tortoise ORM 模型"
```

---

## Task 3: 后端 Schema 层

**Files:**
- Create: `backend/app/schemas/demo.py`

**Step 1: 创建 Pydantic 请求/响应模型**

`backend/app/schemas/demo.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Literal

from pydantic import BaseModel, Field


# ── 样机常量 ──

DEMO_UNIT_STATUSES = ("in_stock", "lent_out", "repairing", "sold", "scrapped", "lost", "converted")
DEMO_CONDITIONS = ("new", "good", "fair", "poor")
DEMO_LOAN_TYPES = ("customer_trial", "salesperson", "exhibition")
DEMO_LOAN_STATUSES = ("pending_approval", "approved", "rejected", "lent_out", "returned", "closed")
DEMO_DISPOSAL_TYPES = ("sale", "scrap", "loss_compensation", "conversion")

DemoUnitStatus = Literal["in_stock", "lent_out", "repairing", "sold", "scrapped", "lost", "converted"]
DemoCondition = Literal["new", "good", "fair", "poor"]
DemoLoanType = Literal["customer_trial", "salesperson", "exhibition"]
DemoLoanStatus = Literal["pending_approval", "approved", "rejected", "lent_out", "returned", "closed"]


# ── 样机台账 ──

class DemoUnitCreate(BaseModel):
    """新增样机（两种来源共用）"""
    source: Literal["stock_transfer", "new_purchase"]
    product_id: int
    sn_code: str = Field(max_length=200)
    warehouse_id: int  # 目标样机仓
    condition: DemoCondition = "new"
    notes: Optional[str] = None
    # stock_transfer 专用
    source_warehouse_id: Optional[int] = None
    source_location_id: Optional[int] = None
    # new_purchase 专用
    cost_price: Optional[Decimal] = Field(default=None, gt=0)


class DemoUnitUpdate(BaseModel):
    condition: Optional[DemoCondition] = None
    notes: Optional[str] = None


# ── 借还记录 ──

class DemoLoanCreate(BaseModel):
    demo_unit_id: int
    loan_type: DemoLoanType
    borrower_type: Literal["customer", "employee"]
    borrower_id: int
    handler_id: Optional[int] = None
    expected_return_date: date
    purpose: Optional[str] = None


class DemoLoanReturn(BaseModel):
    condition_on_return: DemoCondition
    return_notes: Optional[str] = None


# ── 处置 ──

class DemoSellRequest(BaseModel):
    """转销售"""
    customer_id: int
    sale_price: Decimal = Field(gt=0)
    account_set_id: int
    employee_id: Optional[int] = None
    remark: Optional[str] = None


class DemoConvertRequest(BaseModel):
    """翻新转良品"""
    target_warehouse_id: int
    target_location_id: Optional[int] = None
    refurbish_cost: Optional[Decimal] = Field(default=None, ge=0)


class DemoScrapRequest(BaseModel):
    """报废"""
    reason: str
    residual_value: Optional[Decimal] = Field(default=None, ge=0)
    account_set_id: int


class DemoLossRequest(BaseModel):
    """丢失赔偿"""
    description: str
    compensation_amount: Decimal = Field(gt=0)
    account_set_id: int
```

**Step 2: Commit**

```bash
git add backend/app/schemas/demo.py
git commit -m "feat(demo): 添加样机管理 Pydantic Schema"
```

---

## Task 4: 后端服务层

**Files:**
- Create: `backend/app/services/demo_service.py`

**Step 1: 实现核心业务逻辑**

`backend/app/services/demo_service.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from tortoise import transactions

from app.logger import get_logger
from app.models import (
    User, Product, Warehouse, Location, WarehouseStock, StockLog,
    Customer, Employee, Order, OrderItem, SnCode,
)
from app.models.demo import DemoUnit, DemoLoan, DemoDisposal
from app.schemas.demo import (
    DemoUnitCreate, DemoLoanCreate, DemoLoanReturn,
    DemoSellRequest, DemoConvertRequest, DemoScrapRequest, DemoLossRequest,
)
from app.services.stock_service import update_weighted_entry_date
from app.services.ar_service import create_receivable_bill
from app.utils.generators import generate_sequential_no
from app.utils.time import now

logger = get_logger("demo_service")


# ── 辅助 ──

TERMINAL_STATUSES = {"sold", "scrapped", "lost", "converted"}


def _require_status(unit: DemoUnit, *allowed: str):
    if unit.status not in allowed:
        label = {"in_stock": "在库", "lent_out": "借出中", "repairing": "维修中"}
        raise HTTPException(
            status_code=400,
            detail=f"当前状态「{label.get(unit.status, unit.status)}」不允许此操作",
        )


async def _get_unit(unit_id: int) -> DemoUnit:
    unit = await DemoUnit.filter(id=unit_id).select_related("product", "warehouse").first()
    if not unit:
        raise HTTPException(status_code=404, detail="样机不存在")
    return unit


async def _resolve_sn(sn_code_str: str, product_id: int, warehouse_id: int,
                       source_warehouse_id: Optional[int], user: User) -> SnCode:
    """解析或创建 SN 码"""
    if source_warehouse_id:
        # 从库存转入：尝试匹配来源仓库已有的 SN
        existing = await SnCode.filter(
            sn_code=sn_code_str, product_id=product_id,
            warehouse_id=source_warehouse_id, status="in_stock",
        ).first()
        if existing:
            # 转移 SN 归属到样机仓
            existing.warehouse_id = warehouse_id
            await existing.save()
            return existing

    # 不存在则新建
    sn = await SnCode.create(
        sn_code=sn_code_str,
        product_id=product_id,
        warehouse_id=warehouse_id,
        status="in_stock",
        entry_type="demo_intake",
        entry_date=now(),
        entry_user=user,
    )
    return sn


# ── 样机入库 ──

@transactions.atomic()
async def create_demo_unit(data: DemoUnitCreate, user: User) -> DemoUnit:
    """新增样机（从库存转入 或 新采购入库）"""

    product = await Product.filter(id=data.product_id, is_active=True).first()
    if not product:
        raise HTTPException(status_code=400, detail="商品不存在")

    warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True).first()
    if not warehouse:
        raise HTTPException(status_code=400, detail="样机仓不存在")

    # SN 码去重检查
    if await SnCode.filter(sn_code=data.sn_code).exclude(
        warehouse_id=data.source_warehouse_id or 0, product_id=data.product_id, status="in_stock",
    ).exists():
        dup = await SnCode.filter(sn_code=data.sn_code).first()
        if dup and not (data.source == "stock_transfer" and dup.warehouse_id == data.source_warehouse_id
                        and dup.product_id == data.product_id and dup.status == "in_stock"):
            raise HTTPException(status_code=400, detail=f"SN 码 {data.sn_code} 已被使用")

    if data.source == "stock_transfer":
        cost_price = await _handle_stock_transfer(data, product, warehouse, user)
    else:
        cost_price = await _handle_new_purchase(data, product, warehouse, user)

    sn = await _resolve_sn(data.sn_code, product.id, warehouse.id, data.source_warehouse_id, user)

    code = await generate_sequential_no("DM", "demo_units", "code")
    unit = await DemoUnit.create(
        code=code,
        product=product,
        sn_code=sn,
        warehouse=warehouse,
        status="in_stock",
        condition=data.condition,
        cost_price=cost_price,
        notes=data.notes,
        created_by=user,
    )
    logger.info(f"样机入库: {code}, product={product.name}, sn={data.sn_code}")
    return unit


async def _handle_stock_transfer(data: DemoUnitCreate, product, target_wh, user) -> Decimal:
    """从库存转入：扣源仓库、加样机仓"""
    if not data.source_warehouse_id:
        raise HTTPException(status_code=400, detail="从库存转入时必须指定来源仓库")

    source_wh = await Warehouse.filter(id=data.source_warehouse_id, is_active=True).first()
    if not source_wh:
        raise HTTPException(status_code=400, detail="来源仓库不存在")

    # 查来源库存
    stock = await WarehouseStock.filter(
        warehouse_id=source_wh.id, product_id=product.id,
    ).select_for_update().first()

    if not stock or stock.quantity - stock.reserved_qty < 1:
        raise HTTPException(status_code=400, detail="来源仓库可用库存不足")

    cost_price = stock.weighted_cost or product.cost_price or Decimal("0")

    # 扣源仓库
    before_qty = stock.quantity
    stock.quantity -= 1
    await stock.save()
    await StockLog.create(
        product_id=product.id, warehouse_id=source_wh.id,
        change_type="DEMO_TRANSFER_OUT", quantity=-1,
        before_qty=before_qty, after_qty=stock.quantity,
        reference_type="DEMO_UNIT", remark="样机转入",
        creator=user,
    )

    # 加样机仓
    await update_weighted_entry_date(target_wh.id, product.id, 1, cost_price)
    return cost_price


async def _handle_new_purchase(data: DemoUnitCreate, product, target_wh, user) -> Decimal:
    """新采购入库：直接在样机仓建库存"""
    cost_price = data.cost_price or product.cost_price or Decimal("0")
    await update_weighted_entry_date(target_wh.id, product.id, 1, cost_price)
    await StockLog.create(
        product_id=product.id, warehouse_id=target_wh.id,
        change_type="DEMO_PURCHASE", quantity=1,
        before_qty=0, after_qty=1,
        reference_type="DEMO_UNIT", remark="样机采购入库",
        creator=user,
    )
    return cost_price


# ── 借出流程 ──

@transactions.atomic()
async def create_demo_loan(data: DemoLoanCreate, user: User) -> DemoLoan:
    """创建借出申请"""
    unit = await _get_unit(data.demo_unit_id)
    _require_status(unit, "in_stock")

    # 校验借用人存在
    if data.borrower_type == "customer":
        if not await Customer.filter(id=data.borrower_id).exists():
            raise HTTPException(status_code=400, detail="客户不存在")
    else:
        if not await Employee.filter(id=data.borrower_id).exists():
            raise HTTPException(status_code=400, detail="员工不存在")

    loan_no = await generate_sequential_no("DL", "demo_loans", "loan_no")
    loan = await DemoLoan.create(
        loan_no=loan_no,
        demo_unit=unit,
        loan_type=data.loan_type,
        borrower_type=data.borrower_type,
        borrower_id=data.borrower_id,
        handler_id=data.handler_id,
        expected_return_date=data.expected_return_date,
        condition_on_loan=unit.condition,
        purpose=data.purpose,
        created_by=user,
    )
    return loan


async def approve_demo_loan(loan_id: int, user: User) -> DemoLoan:
    """审批通过"""
    loan = await DemoLoan.filter(id=loan_id).select_related("demo_unit").first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    if loan.status != "pending_approval":
        raise HTTPException(status_code=400, detail="只能审批待审批的记录")

    loan.status = "approved"
    loan.approved_by = user
    loan.approved_at = now()
    await loan.save()
    return loan


async def reject_demo_loan(loan_id: int, user: User) -> DemoLoan:
    """审批拒绝"""
    loan = await DemoLoan.filter(id=loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    if loan.status != "pending_approval":
        raise HTTPException(status_code=400, detail="只能拒绝待审批的记录")

    loan.status = "rejected"
    loan.approved_by = user
    loan.approved_at = now()
    await loan.save()
    return loan


@transactions.atomic()
async def lend_demo_unit(loan_id: int, user: User) -> DemoLoan:
    """确认出库"""
    loan = await DemoLoan.filter(id=loan_id).select_related("demo_unit").first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    if loan.status != "approved":
        raise HTTPException(status_code=400, detail="只能对已审批的记录执行出库")

    unit = await DemoUnit.filter(id=loan.demo_unit_id).select_for_update().first()
    _require_status(unit, "in_stock")

    loan.status = "lent_out"
    loan.loan_date = date.today()
    await loan.save()

    unit.status = "lent_out"
    unit.current_holder_type = loan.borrower_type
    unit.current_holder_id = loan.borrower_id
    await unit.save()

    # SN 码状态同步
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(status="shipped")

    return loan


@transactions.atomic()
async def return_demo_unit(loan_id: int, data: DemoLoanReturn, user: User) -> DemoLoan:
    """归还"""
    loan = await DemoLoan.filter(id=loan_id).select_related("demo_unit").first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    if loan.status != "lent_out":
        raise HTTPException(status_code=400, detail="只能对借出中的记录执行归还")

    unit = await DemoUnit.filter(id=loan.demo_unit_id).select_for_update().first()

    today = date.today()
    loan_days = (today - loan.loan_date).days if loan.loan_date else 0

    loan.status = "returned"
    loan.actual_return_date = today
    loan.condition_on_return = data.condition_on_return
    loan.return_notes = data.return_notes
    await loan.save()

    unit.status = "in_stock"
    unit.condition = data.condition_on_return
    unit.current_holder_type = None
    unit.current_holder_id = None
    unit.total_loan_count += 1
    unit.total_loan_days += loan_days
    await unit.save()

    # SN 码状态恢复
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(status="in_stock")

    return loan


# ── 处置操作 ──

@transactions.atomic()
async def sell_demo_unit(unit_id: int, data: DemoSellRequest, user: User) -> DemoDisposal:
    """转销售"""
    unit = await _get_unit(unit_id)
    _require_status(unit, "in_stock", "lent_out")

    customer = await Customer.filter(id=data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=400, detail="客户不存在")

    # 如果借出中，先关闭借还记录
    if unit.status == "lent_out":
        active_loan = await DemoLoan.filter(
            demo_unit_id=unit.id, status="lent_out",
        ).first()
        if active_loan:
            active_loan.status = "closed"
            active_loan.actual_return_date = date.today()
            active_loan.return_notes = "样机转销售，自动关闭借出记录"
            await active_loan.save()

    # 生成销售订单
    from app.utils.generators import generate_order_no
    order_no = generate_order_no("ORD")
    order = await Order.create(
        order_no=order_no,
        order_type="CASH",
        customer=customer,
        warehouse_id=unit.warehouse_id,
        total_amount=data.sale_price,
        total_cost=unit.cost_price,
        total_profit=data.sale_price - unit.cost_price,
        employee_id=data.employee_id,
        account_set_id=data.account_set_id,
        remark=data.remark or f"样机转销售 {unit.code}",
        creator=user,
    )
    await OrderItem.create(
        order=order,
        product_id=unit.product_id,
        warehouse_id=unit.warehouse_id,
        quantity=1,
        unit_price=data.sale_price,
        cost_price=unit.cost_price,
        amount=data.sale_price,
        profit=data.sale_price - unit.cost_price,
    )

    # 生成应收单
    bill = await create_receivable_bill(
        account_set_id=data.account_set_id,
        customer_id=customer.id,
        order_id=order.id,
        total_amount=data.sale_price,
        creator=user,
        remark=f"样机转销售 {unit.code}",
    )

    # 样机仓出库
    stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
    ).select_for_update().first()
    if stock and stock.quantity > 0:
        before = stock.quantity
        stock.quantity -= 1
        await stock.save()
        await StockLog.create(
            product_id=unit.product_id, warehouse_id=unit.warehouse_id,
            change_type="DEMO_SOLD", quantity=-1,
            before_qty=before, after_qty=stock.quantity,
            reference_type="ORDER", reference_id=order.id,
            remark=f"样机转销售 {unit.code}", creator=user,
        )

    unit.status = "sold"
    unit.current_holder_type = None
    unit.current_holder_id = None
    await unit.save()

    disposal = await DemoDisposal.create(
        demo_unit=unit,
        disposal_type="sale",
        amount=data.sale_price,
        order_id=order.id,
        receivable_bill_id=bill.id,
        created_by=user,
    )
    logger.info(f"样机转销售: {unit.code} → 订单 {order_no}")
    return disposal


@transactions.atomic()
async def convert_demo_unit(unit_id: int, data: DemoConvertRequest, user: User) -> DemoDisposal:
    """翻新转良品"""
    unit = await _get_unit(unit_id)
    _require_status(unit, "in_stock")

    target_wh = await Warehouse.filter(id=data.target_warehouse_id, is_active=True).first()
    if not target_wh:
        raise HTTPException(status_code=400, detail="目标仓库不存在")

    if data.target_location_id:
        loc = await Location.filter(id=data.target_location_id, warehouse_id=target_wh.id).first()
        if not loc:
            raise HTTPException(status_code=400, detail="目标仓位不存在")

    refurbish = data.refurbish_cost or Decimal("0")
    new_cost = unit.cost_price + refurbish

    # 样机仓出库
    stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
    ).select_for_update().first()
    if stock and stock.quantity > 0:
        before = stock.quantity
        stock.quantity -= 1
        await stock.save()
        await StockLog.create(
            product_id=unit.product_id, warehouse_id=unit.warehouse_id,
            change_type="DEMO_CONVERT_OUT", quantity=-1,
            before_qty=before, after_qty=stock.quantity,
            remark=f"样机翻新转良品 {unit.code}", creator=user,
        )

    # 目标仓库入库
    await update_weighted_entry_date(
        target_wh.id, unit.product_id, 1, new_cost, data.target_location_id,
    )
    await StockLog.create(
        product_id=unit.product_id, warehouse_id=target_wh.id,
        change_type="DEMO_CONVERT_IN", quantity=1,
        before_qty=0, after_qty=1,
        remark=f"样机翻新转良品 {unit.code}, 翻新费 {refurbish}", creator=user,
    )

    # SN 码转移
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(
            warehouse_id=target_wh.id, status="in_stock",
        )

    unit.status = "converted"
    unit.current_holder_type = None
    unit.current_holder_id = None
    await unit.save()

    disposal = await DemoDisposal.create(
        demo_unit=unit,
        disposal_type="conversion",
        amount=new_cost,
        refurbish_cost=refurbish,
        target_warehouse_id=target_wh.id,
        target_location_id=data.target_location_id,
        created_by=user,
    )
    logger.info(f"样机翻新转良品: {unit.code} → {target_wh.name}")
    return disposal


@transactions.atomic()
async def scrap_demo_unit(unit_id: int, data: DemoScrapRequest, user: User) -> DemoDisposal:
    """报废"""
    unit = await _get_unit(unit_id)
    _require_status(unit, "in_stock", "repairing")

    # 样机仓出库
    stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
    ).select_for_update().first()
    if stock and stock.quantity > 0:
        before = stock.quantity
        stock.quantity -= 1
        await stock.save()
        await StockLog.create(
            product_id=unit.product_id, warehouse_id=unit.warehouse_id,
            change_type="DEMO_SCRAPPED", quantity=-1,
            before_qty=before, after_qty=stock.quantity,
            remark=f"样机报废 {unit.code}: {data.reason}", creator=user,
        )

    unit.status = "scrapped"
    unit.current_holder_type = None
    unit.current_holder_id = None
    await unit.save()

    disposal = await DemoDisposal.create(
        demo_unit=unit,
        disposal_type="scrap",
        amount=data.residual_value,
        reason=data.reason,
        created_by=user,
    )
    logger.info(f"样机报废: {unit.code}, 原因: {data.reason}")
    return disposal


@transactions.atomic()
async def report_loss_demo_unit(unit_id: int, data: DemoLossRequest, user: User) -> DemoDisposal:
    """丢失赔偿"""
    unit = await _get_unit(unit_id)
    _require_status(unit, "lent_out")

    # 关闭借还记录
    active_loan = await DemoLoan.filter(
        demo_unit_id=unit.id, status="lent_out",
    ).first()
    borrower_customer_id = None
    if active_loan:
        active_loan.status = "closed"
        active_loan.actual_return_date = date.today()
        active_loan.return_notes = f"样机丢失: {data.description}"
        await active_loan.save()
        if active_loan.borrower_type == "customer":
            borrower_customer_id = active_loan.borrower_id

    # 生成应收单（如果借用人是客户）
    bill = None
    if borrower_customer_id:
        bill = await create_receivable_bill(
            account_set_id=data.account_set_id,
            customer_id=borrower_customer_id,
            total_amount=data.compensation_amount,
            creator=user,
            remark=f"样机丢失赔偿 {unit.code}: {data.description}",
        )

    # 样机仓出库
    stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
    ).select_for_update().first()
    if stock and stock.quantity > 0:
        before = stock.quantity
        stock.quantity -= 1
        await stock.save()
        await StockLog.create(
            product_id=unit.product_id, warehouse_id=unit.warehouse_id,
            change_type="DEMO_LOST", quantity=-1,
            before_qty=before, after_qty=stock.quantity,
            remark=f"样机丢失 {unit.code}", creator=user,
        )

    unit.status = "lost"
    unit.current_holder_type = None
    unit.current_holder_id = None
    await unit.save()

    disposal = await DemoDisposal.create(
        demo_unit=unit,
        disposal_type="loss_compensation",
        amount=data.compensation_amount,
        receivable_bill_id=bill.id if bill else None,
        reason=data.description,
        created_by=user,
    )
    logger.info(f"样机丢失: {unit.code}")
    return disposal


# ── 统计 ──

async def get_demo_stats(warehouse_id: Optional[int] = None) -> dict:
    """统计概览"""
    q = DemoUnit.filter()
    if warehouse_id:
        q = q.filter(warehouse_id=warehouse_id)

    all_units = await q.all()
    total = len(all_units)
    in_stock = sum(1 for u in all_units if u.status == "in_stock")
    lent_out = sum(1 for u in all_units if u.status == "lent_out")

    # 超期：借出中且超过预计归还日
    overdue = 0
    if lent_out > 0:
        lent_ids = [u.id for u in all_units if u.status == "lent_out"]
        overdue = await DemoLoan.filter(
            demo_unit_id__in=lent_ids, status="lent_out",
            expected_return_date__lt=date.today(),
        ).count()

    total_value = sum(u.cost_price for u in all_units if u.status not in TERMINAL_STATUSES)

    return {
        "total": total,
        "in_stock": in_stock,
        "lent_out": lent_out,
        "overdue": overdue,
        "total_value": float(total_value),
    }
```

**Step 2: Commit**

```bash
git add backend/app/services/demo_service.py
git commit -m "feat(demo): 样机管理服务层（入库/借还/处置/统计）"
```

---

## Task 5: 后端路由层 + Excel 导出

**Files:**
- Create: `backend/app/routers/demo.py`
- Modify: `backend/main.py` — 注册路由

**Step 1: 实现 API 路由（含 Excel 导出）**

`backend/app/routers/demo.py`:

```python
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from tortoise.queryset import Q

from app.auth.dependencies import require_permission
from app.models import User, Customer, Employee
from app.models.demo import DemoUnit, DemoLoan, DemoDisposal
from app.schemas.demo import (
    DemoUnitCreate, DemoUnitUpdate,
    DemoLoanCreate, DemoLoanReturn,
    DemoSellRequest, DemoConvertRequest, DemoScrapRequest, DemoLossRequest,
)
from app.services.demo_service import (
    create_demo_unit, create_demo_loan,
    approve_demo_loan, reject_demo_loan, lend_demo_unit, return_demo_unit,
    sell_demo_unit, convert_demo_unit, scrap_demo_unit, report_loss_demo_unit,
    get_demo_stats,
)
from app.logger import get_logger

logger = get_logger("demo_router")

router = APIRouter(prefix="/api/demo", tags=["样机管理"])

STATUS_LABELS = {
    "in_stock": "在库", "lent_out": "借出中", "repairing": "维修中",
    "sold": "已转销售", "scrapped": "已报废", "lost": "已丢失", "converted": "已转良品",
}
CONDITION_LABELS = {"new": "全新", "good": "良好", "fair": "一般", "poor": "较差"}
LOAN_TYPE_LABELS = {"customer_trial": "客户试用", "salesperson": "业务员携带", "exhibition": "展会"}
LOAN_STATUS_LABELS = {
    "pending_approval": "待审批", "approved": "已审批", "rejected": "已拒绝",
    "lent_out": "借出中", "returned": "已归还", "closed": "已关闭",
}


async def _serialize_unit(u) -> dict:
    product = u.product if hasattr(u, "product") and u.product else await u.product
    warehouse = u.warehouse if hasattr(u, "warehouse") and u.warehouse else await u.warehouse
    sn = None
    if u.sn_code_id:
        from app.models import SnCode
        sn_obj = await SnCode.filter(id=u.sn_code_id).first()
        sn = sn_obj.sn_code if sn_obj else None

    holder_name = ""
    if u.current_holder_type == "customer" and u.current_holder_id:
        c = await Customer.filter(id=u.current_holder_id).first()
        holder_name = c.name if c else ""
    elif u.current_holder_type == "employee" and u.current_holder_id:
        e = await Employee.filter(id=u.current_holder_id).first()
        holder_name = e.name if e else ""

    return {
        "id": u.id,
        "code": u.code,
        "product_id": product.id,
        "product_name": product.name,
        "product_sku": product.sku,
        "sn_code": sn,
        "warehouse_id": warehouse.id,
        "warehouse_name": warehouse.name,
        "status": u.status,
        "status_label": STATUS_LABELS.get(u.status, u.status),
        "condition": u.condition,
        "condition_label": CONDITION_LABELS.get(u.condition, u.condition),
        "cost_price": float(u.cost_price),
        "current_holder_type": u.current_holder_type,
        "current_holder_id": u.current_holder_id,
        "current_holder_name": holder_name,
        "total_loan_count": u.total_loan_count,
        "total_loan_days": u.total_loan_days,
        "notes": u.notes,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


async def _serialize_loan(l) -> dict:
    unit = l.demo_unit if hasattr(l, "demo_unit") and l.demo_unit else await l.demo_unit

    borrower_name = ""
    if l.borrower_type == "customer":
        c = await Customer.filter(id=l.borrower_id).first()
        borrower_name = c.name if c else ""
    else:
        e = await Employee.filter(id=l.borrower_id).first()
        borrower_name = e.name if e else ""

    handler_name = ""
    if l.handler_id:
        h = await Employee.filter(id=l.handler_id).first()
        handler_name = h.name if h else ""

    is_overdue = (
        l.status == "lent_out"
        and l.expected_return_date
        and l.expected_return_date < date.today()
    )

    return {
        "id": l.id,
        "loan_no": l.loan_no,
        "demo_unit_id": unit.id,
        "demo_unit_code": unit.code,
        "loan_type": l.loan_type,
        "loan_type_label": LOAN_TYPE_LABELS.get(l.loan_type, l.loan_type),
        "borrower_type": l.borrower_type,
        "borrower_id": l.borrower_id,
        "borrower_name": borrower_name,
        "handler_name": handler_name,
        "status": l.status,
        "status_label": LOAN_STATUS_LABELS.get(l.status, l.status),
        "loan_date": l.loan_date.isoformat() if l.loan_date else None,
        "expected_return_date": l.expected_return_date.isoformat() if l.expected_return_date else None,
        "actual_return_date": l.actual_return_date.isoformat() if l.actual_return_date else None,
        "condition_on_loan": l.condition_on_loan,
        "condition_on_return": l.condition_on_return,
        "return_notes": l.return_notes,
        "purpose": l.purpose,
        "is_overdue": is_overdue,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


# ── 统计 ──

@router.get("/stats")
async def stats(
    warehouse_id: Optional[int] = None,
    user: User = Depends(require_permission("stock_view")),
):
    return await get_demo_stats(warehouse_id)


# ── 样机台账 CRUD ──

@router.get("/units")
async def list_units(
    status: Optional[str] = None,
    search: Optional[str] = None,
    warehouse_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 50,
    user: User = Depends(require_permission("stock_view")),
):
    q = Q()
    if status:
        q &= Q(status=status)
    if warehouse_id:
        q &= Q(warehouse_id=warehouse_id)
    if search:
        q &= (
            Q(code__icontains=search)
            | Q(product__name__icontains=search)
            | Q(product__sku__icontains=search)
        )

    total = await DemoUnit.filter(q).count()
    units = await DemoUnit.filter(q).select_related("product", "warehouse").offset(offset).limit(limit)
    items = [await _serialize_unit(u) for u in units]
    return {"items": items, "total": total}


@router.post("/units")
async def create_unit(
    data: DemoUnitCreate,
    user: User = Depends(require_permission("stock_edit")),
):
    unit = await create_demo_unit(data, user)
    await unit.fetch_related("product", "warehouse")
    return await _serialize_unit(unit)


@router.get("/units/{unit_id}")
async def get_unit(
    unit_id: int,
    user: User = Depends(require_permission("stock_view")),
):
    unit = await DemoUnit.filter(id=unit_id).select_related("product", "warehouse").first()
    if not unit:
        raise HTTPException(status_code=404, detail="样机不存在")

    result = await _serialize_unit(unit)
    # 附带借还历史
    loans = await DemoLoan.filter(demo_unit_id=unit.id).order_by("-created_at").limit(50)
    result["loans"] = [await _serialize_loan(l) for l in loans]
    # 附带处置记录
    disposals = await DemoDisposal.filter(demo_unit_id=unit.id).order_by("-created_at")
    result["disposals"] = [
        {
            "id": d.id,
            "disposal_type": d.disposal_type,
            "amount": float(d.amount) if d.amount else None,
            "refurbish_cost": float(d.refurbish_cost) if d.refurbish_cost else None,
            "reason": d.reason,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in disposals
    ]
    return result


@router.put("/units/{unit_id}")
async def update_unit(
    unit_id: int,
    data: DemoUnitUpdate,
    user: User = Depends(require_permission("stock_edit")),
):
    unit = await DemoUnit.filter(id=unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="样机不存在")
    await unit.update_from_dict(data.dict(exclude_unset=True))
    await unit.save()
    await unit.fetch_related("product", "warehouse")
    return await _serialize_unit(unit)


@router.delete("/units/{unit_id}")
async def delete_unit(
    unit_id: int,
    user: User = Depends(require_permission("stock_edit")),
):
    unit = await DemoUnit.filter(id=unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="样机不存在")
    if unit.status != "in_stock":
        raise HTTPException(status_code=400, detail="只能删除在库样机")
    if await DemoLoan.filter(demo_unit_id=unit.id).exists():
        raise HTTPException(status_code=400, detail="该样机有借还记录，不能删除")
    await unit.delete()
    return {"ok": True}


# ── 借还操作 ──

@router.get("/loans")
async def list_loans(
    status: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    user: User = Depends(require_permission("stock_view")),
):
    q = Q()
    if status:
        if status == "overdue":
            q &= Q(status="lent_out", expected_return_date__lt=date.today())
        else:
            q &= Q(status=status)
    if search:
        q &= Q(loan_no__icontains=search) | Q(demo_unit__code__icontains=search)
    if start_date:
        q &= Q(created_at__gte=start_date)
    if end_date:
        q &= Q(created_at__lte=end_date + "T23:59:59")

    total = await DemoLoan.filter(q).count()
    loans = await DemoLoan.filter(q).select_related("demo_unit").offset(offset).limit(limit)
    items = [await _serialize_loan(l) for l in loans]
    return {"items": items, "total": total}


@router.post("/loans")
async def create_loan(
    data: DemoLoanCreate,
    user: User = Depends(require_permission("stock_edit")),
):
    loan = await create_demo_loan(data, user)
    await loan.fetch_related("demo_unit")
    return await _serialize_loan(loan)


@router.get("/loans/{loan_id}")
async def get_loan(
    loan_id: int,
    user: User = Depends(require_permission("stock_view")),
):
    loan = await DemoLoan.filter(id=loan_id).select_related("demo_unit").first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    return await _serialize_loan(loan)


@router.post("/loans/{loan_id}/approve")
async def approve_loan(
    loan_id: int,
    user: User = Depends(require_permission("stock_edit")),
):
    loan = await approve_demo_loan(loan_id, user)
    await loan.fetch_related("demo_unit")
    return await _serialize_loan(loan)


@router.post("/loans/{loan_id}/reject")
async def reject_loan(
    loan_id: int,
    user: User = Depends(require_permission("stock_edit")),
):
    loan = await reject_demo_loan(loan_id, user)
    await loan.fetch_related("demo_unit")
    return await _serialize_loan(loan)


@router.post("/loans/{loan_id}/lend")
async def lend(
    loan_id: int,
    user: User = Depends(require_permission("stock_edit")),
):
    loan = await lend_demo_unit(loan_id, user)
    await loan.fetch_related("demo_unit")
    return await _serialize_loan(loan)


@router.post("/loans/{loan_id}/return")
async def return_unit(
    loan_id: int,
    data: DemoLoanReturn,
    user: User = Depends(require_permission("stock_edit")),
):
    loan = await return_demo_unit(loan_id, data, user)
    await loan.fetch_related("demo_unit")
    return await _serialize_loan(loan)


# ── 处置操作 ──

@router.post("/units/{unit_id}/sell")
async def sell(unit_id: int, data: DemoSellRequest, user: User = Depends(require_permission("stock_edit"))):
    disposal = await sell_demo_unit(unit_id, data, user)
    return {"ok": True, "disposal_id": disposal.id}


@router.post("/units/{unit_id}/convert")
async def convert(unit_id: int, data: DemoConvertRequest, user: User = Depends(require_permission("stock_edit"))):
    disposal = await convert_demo_unit(unit_id, data, user)
    return {"ok": True, "disposal_id": disposal.id}


@router.post("/units/{unit_id}/scrap")
async def scrap(unit_id: int, data: DemoScrapRequest, user: User = Depends(require_permission("stock_edit"))):
    disposal = await scrap_demo_unit(unit_id, data, user)
    return {"ok": True, "disposal_id": disposal.id}


@router.post("/units/{unit_id}/report-loss")
async def report_loss(unit_id: int, data: DemoLossRequest, user: User = Depends(require_permission("stock_edit"))):
    disposal = await report_loss_demo_unit(unit_id, data, user)
    return {"ok": True, "disposal_id": disposal.id}


# ── Excel 导出 ──

@router.get("/units/export")
async def export_units(
    status: Optional[str] = None,
    warehouse_id: Optional[int] = None,
    user: User = Depends(require_permission("stock_view")),
):
    """导出样机台账 Excel"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    q = Q()
    if status:
        q &= Q(status=status)
    if warehouse_id:
        q &= Q(warehouse_id=warehouse_id)

    units = await DemoUnit.filter(q).select_related("product", "warehouse").order_by("code")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "样机台账"

    # 表头样式
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="E8E8E8", end_color="E8E8E8", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    headers = ["样机编号", "商品名称", "SKU", "SN码", "所属仓库", "状态", "成色",
               "成本价", "当前持有人", "累计借出次数", "累计借出天数", "备注", "入库时间"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center")

    for row_idx, u in enumerate(units, 2):
        sn = ""
        if u.sn_code_id:
            from app.models import SnCode
            sn_obj = await SnCode.filter(id=u.sn_code_id).first()
            sn = sn_obj.sn_code if sn_obj else ""

        holder_name = ""
        if u.current_holder_type == "customer" and u.current_holder_id:
            c = await Customer.filter(id=u.current_holder_id).first()
            holder_name = c.name if c else ""
        elif u.current_holder_type == "employee" and u.current_holder_id:
            e = await Employee.filter(id=u.current_holder_id).first()
            holder_name = e.name if e else ""

        values = [
            u.code,
            u.product.name,
            u.product.sku,
            sn,
            u.warehouse.name,
            STATUS_LABELS.get(u.status, u.status),
            CONDITION_LABELS.get(u.condition, u.condition),
            float(u.cost_price),
            holder_name,
            u.total_loan_count,
            u.total_loan_days,
            u.notes or "",
            u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
        ]
        for col, v in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=v)
            cell.border = thin_border

    # 列宽
    col_widths = [14, 24, 16, 20, 12, 10, 8, 12, 14, 12, 12, 20, 18]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"样机台账_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
```

**Step 2: 在 main.py 中注册路由**

在 `backend/main.py` 的 import 区和 `include_router` 区域添加：

```python
from app.routers import demo
# ...
app.include_router(demo.router)
```

**Step 3: 启动后端验证无报错**

```bash
cd /Users/lin/Desktop/erp-4/backend && python -c "from app.routers.demo import router; print('Router OK:', len(router.routes), 'routes')"
```

**Step 4: Commit**

```bash
git add backend/app/routers/demo.py backend/main.py
git commit -m "feat(demo): 样机管理 API 路由 + Excel 导出"
```

---

## Task 6: 前端 API 模块

**Files:**
- Create: `frontend/src/api/demo.js`

**Step 1: 创建 API 模块**

`frontend/src/api/demo.js`:

```javascript
/**
 * 样机管理模块 API
 */
import api from './index'

// 统计
export const getDemoStats = (params) => api.get('/demo/stats', { params })

// 样机台账
export const getDemoUnits = (params) => api.get('/demo/units', { params })
export const getDemoUnit = (id) => api.get('/demo/units/' + id)
export const createDemoUnit = (data) => api.post('/demo/units', data)
export const updateDemoUnit = (id, data) => api.put('/demo/units/' + id, data)
export const deleteDemoUnit = (id) => api.delete('/demo/units/' + id)
export const exportDemoUnits = (params) => api.get('/demo/units/export', { params, responseType: 'blob' })

// 借还记录
export const getDemoLoans = (params) => api.get('/demo/loans', { params })
export const getDemoLoan = (id) => api.get('/demo/loans/' + id)
export const createDemoLoan = (data) => api.post('/demo/loans', data)
export const approveDemoLoan = (id) => api.post('/demo/loans/' + id + '/approve')
export const rejectDemoLoan = (id) => api.post('/demo/loans/' + id + '/reject')
export const lendDemoLoan = (id) => api.post('/demo/loans/' + id + '/lend')
export const returnDemoLoan = (id, data) => api.post('/demo/loans/' + id + '/return', data)

// 处置
export const sellDemoUnit = (id, data) => api.post('/demo/units/' + id + '/sell', data)
export const convertDemoUnit = (id, data) => api.post('/demo/units/' + id + '/convert', data)
export const scrapDemoUnit = (id, data) => api.post('/demo/units/' + id + '/scrap', data)
export const reportLossDemoUnit = (id, data) => api.post('/demo/units/' + id + '/report-loss', data)
```

**Step 2: Commit**

```bash
git add frontend/src/api/demo.js
git commit -m "feat(demo): 前端样机管理 API 模块"
```

---

## Task 7: 前端 Composable

**Files:**
- Create: `frontend/src/composables/useDemoUnit.js`

**Step 1: 创建列表管理 composable**

`frontend/src/composables/useDemoUnit.js`:

```javascript
import { ref, computed, onUnmounted } from 'vue'
import { getDemoUnits, getDemoLoans, getDemoStats } from '../api/demo'
import { usePagination } from './usePagination'
import { useSort } from './useSort'

export function useDemoUnit() {
  const { page, pageSize, total, totalPages, hasPagination, paginationParams,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage } = usePagination(50)
  const { sortState, toggleSort, genericSort } = useSort()

  const units = ref([])
  const loading = ref(false)
  const statusFilter = ref('')
  const warehouseFilter = ref('')
  const search = ref('')

  let _timer = null
  const debouncedLoad = () => {
    clearTimeout(_timer)
    resetPage()
    _timer = setTimeout(loadUnits, 300)
  }

  const loadUnits = async () => {
    loading.value = true
    try {
      const params = { ...paginationParams.value }
      if (statusFilter.value) params.status = statusFilter.value
      if (warehouseFilter.value) params.warehouse_id = warehouseFilter.value
      if (search.value) params.search = search.value
      const { data } = await getDemoUnits(params)
      units.value = data.items || []
      total.value = data.total ?? 0
    } catch (e) {
      console.error('加载样机列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  const sortedUnits = computed(() =>
    genericSort(units.value, {
      code: i => i.code,
      product_name: i => i.product_name || '',
      status: i => i.status || '',
      cost_price: i => Number(i.cost_price) || 0,
      total_loan_count: i => i.total_loan_count || 0,
    })
  )

  onUnmounted(() => clearTimeout(_timer))

  return {
    units, loading, statusFilter, warehouseFilter, search,
    loadUnits, debouncedLoad, sortedUnits,
    sortState, toggleSort,
    page, pageSize, total, totalPages, hasPagination,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage,
  }
}

export function useDemoLoan() {
  const { page, pageSize, total, totalPages, hasPagination, paginationParams,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage } = usePagination(50)

  const loans = ref([])
  const loading = ref(false)
  const statusFilter = ref('')
  const search = ref('')
  const dateStart = ref('')
  const dateEnd = ref('')

  let _timer = null
  const debouncedLoad = () => {
    clearTimeout(_timer)
    resetPage()
    _timer = setTimeout(loadLoans, 300)
  }

  const loadLoans = async () => {
    loading.value = true
    try {
      const params = { ...paginationParams.value }
      if (statusFilter.value) params.status = statusFilter.value
      if (search.value) params.search = search.value
      if (dateStart.value) params.start_date = dateStart.value
      if (dateEnd.value) params.end_date = dateEnd.value
      const { data } = await getDemoLoans(params)
      loans.value = data.items || []
      total.value = data.total ?? 0
    } catch (e) {
      console.error('加载借还记录失败:', e)
    } finally {
      loading.value = false
    }
  }

  onUnmounted(() => clearTimeout(_timer))

  return {
    loans, loading, statusFilter, search, dateStart, dateEnd,
    loadLoans, debouncedLoad,
    page, pageSize, total, totalPages, hasPagination,
    visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage,
  }
}

export function useDemoStats() {
  const stats = ref({ total: 0, in_stock: 0, lent_out: 0, overdue: 0, total_value: 0 })

  const loadStats = async (warehouseId) => {
    try {
      const params = {}
      if (warehouseId) params.warehouse_id = warehouseId
      const { data } = await getDemoStats(params)
      stats.value = data
    } catch (e) {
      console.error('加载统计失败:', e)
    }
  }

  return { stats, loadStats }
}
```

**Step 2: Commit**

```bash
git add frontend/src/composables/useDemoUnit.js
git commit -m "feat(demo): 前端样机管理 composable"
```

---

## Task 8: 前端业务组件 — DemoManagementPanel + DemoUnitList

**Files:**
- Create: `frontend/src/components/business/demo/DemoManagementPanel.vue`
- Create: `frontend/src/components/business/demo/DemoUnitList.vue`

**Step 1: DemoManagementPanel — 样机管理容器**

`frontend/src/components/business/demo/DemoManagementPanel.vue`:

这是样机管理的顶层容器，包含统计卡片和内部 tab（样机台账 / 借还记录）。

关键要素：
- 使用 `AppTabs` 切换子 tab
- 使用 `useDemoStats()` 加载统计数字
- `refreshKey` 机制让子组件触发父级刷新统计

**Step 2: DemoUnitList — 样机台账列表**

`frontend/src/components/business/demo/DemoUnitList.vue`:

关键要素：
- 使用 `useDemoUnit()` composable
- 工具栏：新增按钮 + 状态筛选 + 搜索框 + 导出按钮
- 桌面 `AppTable` + 移动端卡片
- 操作列根据 `unit.status` 动态显示可用操作（借出/归还/转销售/翻新/报废/丢失）
- 导出复用 `downloadBlob` 工具函数

**代码规范要点：**
- 状态筛选使用 `<select class="input text-sm">`，与 StockView 保持一致
- 按钮使用 `btn btn-primary btn-sm` / `btn btn-secondary btn-sm` 等系统样式
- 操作按钮用 `<button>` 不用 `<div @click>`
- 超期行用 `class="text-error"` 高亮
- 金额列用 `font-mono tabular-nums text-right`
- 移动端视图 `class="md:hidden space-y-2"` + 桌面视图 `class="hidden md:block"`

---

## Task 9: 前端业务组件 — DemoLoanList

**Files:**
- Create: `frontend/src/components/business/demo/DemoLoanList.vue`

关键要素：
- 使用 `useDemoLoan()` composable
- 工具栏：状态筛选（全部/待审批/借出中/超期/已归还）+ `DateRangePicker` + 搜索
- 超期记录行高亮 `class="text-error"`
- 操作列根据 `loan.status` 显示：审批/拒绝（pending_approval）、确认出库（approved）、归还（lent_out）

---

## Task 10: 前端业务组件 — 弹窗组件

**Files:**
- Create: `frontend/src/components/business/demo/DemoUnitForm.vue`
- Create: `frontend/src/components/business/demo/DemoLoanForm.vue`
- Create: `frontend/src/components/business/demo/DemoReturnModal.vue`
- Create: `frontend/src/components/business/demo/DemoDisposalModal.vue`

### DemoUnitForm.vue（新增样机）

关键要素：
- 使用 `AppModal` 包裹
- 来源切换：`stock_transfer` / `new_purchase`，用 radio 切换
- 商品选择：复用 `SearchableSelect` 或下拉搜索模式（参考 DropshipOrderForm 的 supplier 选择器）
- SN 码输入：统一用 `<input>`
  - 来源仓库有 SN 管理时：`@input` 触发防抖搜索匹配来源仓库已有 SN
  - 来源仓库无 SN 管理时：普通文本输入
- 仓库选择：筛选现有仓库列表，只显示样机仓
- `watch(() => props.visible)` 重置表单
- 表单验证参考 DropshipOrderForm 的 `validate()` 模式

### DemoLoanForm.vue（借出申请）

关键要素：
- 使用 `AppModal`
- 样机选择：下拉搜索，只显示 `status=in_stock` 的样机
- 借用类型：`<select>` 三选一
- 借用人：根据 `borrower_type` 切换客户列表/员工列表
- 预计归还日期：`<input type="date">`
- 经办人：员工下拉

### DemoReturnModal.vue（归还）

关键要素：
- 使用 `AppModal`
- 归还成色：`<select>` 四选一（全新/良好/一般/较差）
- 归还备注：`<textarea>`
- 显示借出信息（借出日期、已借天数）

### DemoDisposalModal.vue（通用处置弹窗）

关键要素：
- 使用 `AppModal`
- `props.type` 区分四种处置：`sale` / `conversion` / `scrap` / `loss`
- 根据 type 动态渲染不同表单字段：
  - `sale`: 客户选择器 + 售价 + 账套
  - `conversion`: 目标仓库/仓位 + 翻新费用
  - `scrap`: 报废原因 + 残值 + 账套
  - `loss`: 丢失说明 + 赔偿金额 + 账套
- `computed` title 根据 type 切换

---

## Task 11: 修改 StockView 加入样机管理 Tab

**Files:**
- Modify: `frontend/src/views/StockView.vue`

**改造方式：**

1. 在 `<template>` 最外层加 `AppTabs`：

```vue
<template>
  <div>
    <AppTabs v-model="topTab" :tabs="[
      { value: 'stock', label: '库存' },
      { value: 'demo', label: '样机管理' },
    ]" />

    <!-- 原有库存内容 -->
    <template v-if="topTab === 'stock'">
      <!-- ... 现有全部内容不动 ... -->
    </template>

    <!-- 样机管理 -->
    <DemoManagementPanel v-else-if="topTab === 'demo'" />
  </div>
</template>
```

2. `<script setup>` 中添加：

```javascript
import AppTabs from '../components/common/AppTabs.vue'
import DemoManagementPanel from '../components/business/demo/DemoManagementPanel.vue'

const topTab = ref('stock')
```

**注意事项：**
- 现有库存内容完全不动，只是包了一层 `<template v-if>`
- `DemoManagementPanel` 使用 `v-else-if` 懒加载，切到样机 tab 时才渲染
- `topTab` 默认值 `'stock'`，保持现有用户习惯

---

## Task 12: 构建验证 + 集成测试

**Step 1: 前端构建**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npm run build
```

Expected: 编译通过，无错误。

**Step 2: 后端启动验证**

启动后端，确认无 import 错误：

```bash
cd /Users/lin/Desktop/erp-4/backend && python -c "from main import app; print('App OK')"
```

**Step 3: 用 preview 工具验证页面结构**

- 启动 dev server
- 导航到 `/stock`
- `preview_snapshot` 验证顶层 tab 出现「库存」和「样机管理」
- 点击「样机管理」tab
- `preview_snapshot` 验证统计卡片和内部 tab 出现
- `preview_console_logs` 确认无 JS 错误

**Step 4: API 测试**

```bash
# 统计接口
curl -s http://localhost:8000/api/demo/stats -H "Authorization: Bearer $TOKEN" | python -m json.tool

# 列表接口
curl -s http://localhost:8000/api/demo/units -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Step 5: 最终 Commit**

```bash
git add -A
git commit -m "feat(demo): 样机管理模块完整实现

- 数据库: demo_units / demo_loans / demo_disposals 三张表
- 后端: 模型 + Schema + 服务层 + API 路由 + Excel 导出
- 前端: 台账列表 + 借还记录 + 入库/借出/归还/处置弹窗
- 集成: 库存联动 + SN 码追踪 + 应收单生成
- 放在库存页面下作为二级 tab"
```

---

## 注意事项（贯穿所有 Task）

### 代码质量
- **DRY**: `_require_status` / `_get_unit` / `_serialize_unit` 等辅助函数避免重复
- **YAGNI**: 不加审批流引擎、不加通知系统、不加附件上传——这些后续迭代再加
- **可扩展**: 状态用字符串枚举不用数字，新增状态只需加常量；处置弹窗用 `props.type` 一个组件覆盖四种操作

### UI 一致性
- 所有弹窗用 `AppModal`，表格用 `AppTable`，tab 用 `AppTabs`
- 按钮样式：主操作 `btn btn-primary btn-sm`，次要 `btn btn-secondary btn-sm`，危险 `btn btn-error btn-sm`
- 状态标签用项目的 badge 样式
- 金额用 `font-mono tabular-nums`
- 移动端/桌面端双视图
- 不硬编码颜色值，全部用 CSS 变量 / Tailwind token

### 权限
- 查看：`stock_view`
- 编辑（入库/借出/归还/处置）：`stock_edit`
- 不新增权限项
