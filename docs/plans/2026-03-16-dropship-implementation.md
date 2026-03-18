# 代采代发模块实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现代采代发模块，业务员一张表单录单，财务付款工作台批量确认，系统自动生成全套财务单据。

**Architecture:** 独立 DropshipOrder 模型，不复用 Order/PurchaseOrder。在各状态变更时直接生成 PayableBill/DisbursementBill/ReceivableBill 等财务单据。扩展现有发票确认逻辑以支持代采代发成本结转。

**Tech Stack:** FastAPI + Tortoise ORM + PostgreSQL (后端) / Vue 3 + Tailwind CSS 4 (前端)

**Design Doc:** `docs/plans/2026-03-16-dropship-module-design.md`

**UI 要求:** 所有前端界面必须与现有项目风格完全统一。使用现有的 AppTabs、badge、表格、modal 等组件模式。参考 PurchaseView.vue / LogisticsView.vue 的实现方式。

---

## Task 1: 后端模型 — DropshipOrder

**Files:**
- Create: `backend/app/models/dropship.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: 创建 DropshipOrder 模型**

在 `backend/app/models/dropship.py` 中定义模型：

```python
from tortoise import fields, models


class DropshipOrder(models.Model):
    id = fields.IntField(pk=True)
    ds_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="dropship_orders", on_delete=fields.RESTRICT)
    status = fields.CharField(max_length=20, default="draft")
    # draft | pending_payment | paid_pending_ship | shipped | completed | cancelled

    # 采购信息
    supplier = fields.ForeignKeyField("models.Supplier", related_name="dropship_orders", on_delete=fields.RESTRICT)
    product = fields.ForeignKeyField("models.Product", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)
    product_name = fields.CharField(max_length=200)
    purchase_price = fields.DecimalField(max_digits=12, decimal_places=2)
    quantity = fields.IntField()
    purchase_total = fields.DecimalField(max_digits=12, decimal_places=2)
    invoice_type = fields.CharField(max_length=10, default="special")  # special | normal
    purchase_tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13)

    # 销售信息
    customer = fields.ForeignKeyField("models.Customer", related_name="dropship_orders", on_delete=fields.RESTRICT)
    platform_order_no = fields.CharField(max_length=100)
    sale_price = fields.DecimalField(max_digits=12, decimal_places=2)
    sale_total = fields.DecimalField(max_digits=12, decimal_places=2)
    sale_tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13)
    settlement_type = fields.CharField(max_length=10, default="credit")  # prepaid | credit
    advance_receipt = fields.ForeignKeyField("models.ReceiptBill", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)

    # 毛利
    gross_profit = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_margin = fields.DecimalField(max_digits=5, decimal_places=2, default=0)

    # 物流信息
    shipping_mode = fields.CharField(max_length=10, default="direct")  # direct | transit
    carrier_code = fields.CharField(max_length=30, null=True)
    carrier_name = fields.CharField(max_length=50, null=True)
    tracking_no = fields.CharField(max_length=100, null=True)
    kd100_subscribed = fields.BooleanField(default=False)
    last_tracking_info = fields.TextField(null=True)

    # 状态管理
    urged_at = fields.DatetimeField(null=True)
    cancel_reason = fields.CharField(max_length=200, null=True)
    note = fields.TextField(null=True)

    # 关联财务单据
    payable_bill = fields.ForeignKeyField("models.PayableBill", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)
    disbursement_bill = fields.ForeignKeyField("models.DisbursementBill", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)
    receivable_bill = fields.ForeignKeyField("models.ReceivableBill", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)

    # 付款信息
    payment_method = fields.CharField(max_length=50, null=True)
    payment_employee = fields.ForeignKeyField("models.Employee", related_name="dropship_payments", null=True, on_delete=fields.SET_NULL)

    creator = fields.ForeignKeyField("models.User", related_name="created_dropships", on_delete=fields.SET_NULL, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "dropship_orders"
        ordering = ["-created_at"]
```

**Step 2: 注册模型到 `__init__.py`**

在 `backend/app/models/__init__.py` 中添加：

```python
from app.models.dropship import DropshipOrder
```

并在 `__all__` 列表中加入 `"DropshipOrder"`。

**Step 3: 创建数据库迁移**

在 `backend/app/migrations.py` 的 `_run_migrations_inner()` 函数末尾添加调用 `await migrate_dropship_module()`，然后实现迁移函数：

```python
async def migrate_dropship_module():
    """代采代发模块 DDL 迁移"""
    conn = connections.get("default")
    # 建表
    await conn.execute_query("""
        CREATE TABLE IF NOT EXISTS dropship_orders (
            id SERIAL PRIMARY KEY,
            ds_no VARCHAR(30) UNIQUE NOT NULL,
            account_set_id INTEGER NOT NULL REFERENCES account_sets(id),
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
            product_id INTEGER REFERENCES products(id),
            product_name VARCHAR(200) NOT NULL,
            purchase_price DECIMAL(12,2) NOT NULL,
            quantity INTEGER NOT NULL,
            purchase_total DECIMAL(12,2) NOT NULL,
            invoice_type VARCHAR(10) NOT NULL DEFAULT 'special',
            purchase_tax_rate DECIMAL(5,2) NOT NULL DEFAULT 13,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            platform_order_no VARCHAR(100) NOT NULL,
            sale_price DECIMAL(12,2) NOT NULL,
            sale_total DECIMAL(12,2) NOT NULL,
            sale_tax_rate DECIMAL(5,2) NOT NULL DEFAULT 13,
            settlement_type VARCHAR(10) NOT NULL DEFAULT 'credit',
            advance_receipt_id INTEGER REFERENCES receipt_bills(id),
            gross_profit DECIMAL(12,2) NOT NULL DEFAULT 0,
            gross_margin DECIMAL(5,2) NOT NULL DEFAULT 0,
            shipping_mode VARCHAR(10) NOT NULL DEFAULT 'direct',
            carrier_code VARCHAR(30),
            carrier_name VARCHAR(50),
            tracking_no VARCHAR(100),
            kd100_subscribed BOOLEAN NOT NULL DEFAULT FALSE,
            last_tracking_info TEXT,
            urged_at TIMESTAMPTZ,
            cancel_reason VARCHAR(200),
            note TEXT,
            payable_bill_id INTEGER REFERENCES payable_bills(id),
            disbursement_bill_id INTEGER REFERENCES disbursement_bills(id),
            receivable_bill_id INTEGER REFERENCES receivable_bills(id),
            payment_method VARCHAR(50),
            payment_employee_id INTEGER REFERENCES employees(id),
            creator_id INTEGER REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ReceivableBill 新增字段
    for col, typ in [
        ("platform_order_no", "VARCHAR(100)"),
        ("dropship_order_id", "INTEGER REFERENCES dropship_orders(id)"),
    ]:
        await conn.execute_query(f"""
            DO $$ BEGIN
                ALTER TABLE receivable_bills ADD COLUMN {col} {typ};
            EXCEPTION WHEN duplicate_column THEN NULL;
            END $$
        """)

    # 初始化 "冲减借支" 付款方式（如不存在）
    exists = await conn.execute_query(
        "SELECT 1 FROM disbursement_methods WHERE code = 'employee_advance' LIMIT 1"
    )
    if not exists[1]:
        max_sort = await conn.execute_query(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM disbursement_methods"
        )
        sort = max_sort[1][0].get("coalesce", 6) if max_sort[1] else 6
        await conn.execute_query(
            "INSERT INTO disbursement_methods (code, name, sort_order, is_active) VALUES ('employee_advance', '冲减借支', $1, TRUE)",
            [sort]
        )
    logger.info("代采代发模块迁移完成")
```

**Step 4: 更新 ReceivableBill 模型**

在 `backend/app/models/ar_ap.py` 的 ReceivableBill 类中添加字段：

```python
platform_order_no = fields.CharField(max_length=100, null=True)
dropship_order = fields.ForeignKeyField("models.DropshipOrder", related_name="linked_receivables", null=True, on_delete=fields.SET_NULL)
```

**Step 5: 运行验证**

```bash
cd /Users/lin/Desktop/erp-4 && orb start && docker compose up -d postgres && cd backend && python -c "from app.models.dropship import DropshipOrder; print('Model OK')"
```

**Step 6: Commit**

```bash
git add backend/app/models/dropship.py backend/app/models/__init__.py backend/app/models/ar_ap.py backend/app/migrations.py
git commit -m "feat(代采代发): 添加 DropshipOrder 模型 + 数据库迁移"
```

---

## Task 2: 后端 Schema + 基础路由

**Files:**
- Create: `backend/app/schemas/dropship.py`
- Create: `backend/app/routers/dropship.py`
- Modify: `backend/main.py`

**Step 1: 创建 Pydantic Schema**

```python
# backend/app/schemas/dropship.py
from __future__ import annotations
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class DropshipOrderCreate(BaseModel):
    account_set_id: int
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None  # 快速新建供应商
    product_id: Optional[int] = None
    product_name: str
    purchase_price: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)
    invoice_type: str = "special"  # special | normal
    purchase_tax_rate: Decimal = Decimal("13")
    customer_id: int
    platform_order_no: str
    sale_price: Decimal = Field(gt=0)
    sale_tax_rate: Decimal = Decimal("13")
    settlement_type: str = "credit"  # prepaid | credit
    advance_receipt_id: Optional[int] = None
    shipping_mode: str = "direct"  # direct | transit
    note: Optional[str] = None


class DropshipOrderUpdate(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    quantity: Optional[int] = None
    invoice_type: Optional[str] = None
    purchase_tax_rate: Optional[Decimal] = None
    customer_id: Optional[int] = None
    platform_order_no: Optional[str] = None
    sale_price: Optional[Decimal] = None
    sale_tax_rate: Optional[Decimal] = None
    settlement_type: Optional[str] = None
    advance_receipt_id: Optional[int] = None
    shipping_mode: Optional[str] = None
    note: Optional[str] = None


class DropshipShipRequest(BaseModel):
    carrier_code: str
    carrier_name: str
    tracking_no: str


class DropshipPaymentRequest(BaseModel):
    order_ids: list[int] = Field(min_length=1)
    payment_method: str
    employee_id: Optional[int] = None  # 冲减借支时必填


class DropshipCancelRequest(BaseModel):
    reason: Optional[str] = None
```

**Step 2: 创建路由文件**

```python
# backend/app/routers/dropship.py
"""代采代发路由"""
from __future__ import annotations
from decimal import Decimal
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.queryset import Q

from app.auth.dependencies import require_permission
from app.logger import get_logger
from app.models import User
from app.models.dropship import DropshipOrder
from app.schemas.dropship import (
    DropshipOrderCreate, DropshipOrderUpdate,
    DropshipShipRequest, DropshipPaymentRequest, DropshipCancelRequest,
)
from app.utils.errors import parse_date

logger = get_logger("dropship")

router = APIRouter(prefix="/api/dropship", tags=["代采代发"])
```

然后逐步添加以下端点骨架（详细业务逻辑在 Task 3-7 实现）：

- `GET /api/dropship` — 列表（支持状态/日期/搜索筛选）
- `GET /api/dropship/{id}` — 详情
- `POST /api/dropship` — 创建（草稿/直接提交）
- `PUT /api/dropship/{id}` — 编辑草稿
- `POST /api/dropship/{id}/submit` — 提交（草稿→待付款）
- `POST /api/dropship/{id}/urge` — 催付款
- `POST /api/dropship/batch-pay` — 批量付款（待付款→已付待发）
- `POST /api/dropship/{id}/ship` — 确认发货（已付待发→已发货）
- `POST /api/dropship/{id}/complete` — 手动确认完成
- `POST /api/dropship/{id}/cancel` — 取消
- `GET /api/dropship/payment-workbench` — 付款工作台数据
- `GET /api/dropship/reports/summary` — 月度汇总
- `GET /api/dropship/reports/profit` — 毛利报表
- `GET /api/dropship/reports/receivable` — 应收未收

**Step 3: 注册路由到 main.py**

在 `backend/main.py` 中添加：

```python
from app.routers import (
    ..., dropship,
)
...
app.include_router(dropship.router)
```

**Step 4: Commit**

```bash
git add backend/app/schemas/dropship.py backend/app/routers/dropship.py backend/main.py
git commit -m "feat(代采代发): Schema 定义 + 路由骨架 + 注册"
```

---

## Task 3: 后端服务 — 创建 + 提交

**Files:**
- Create: `backend/app/services/dropship_service.py`
- Modify: `backend/app/routers/dropship.py`

**Step 1: 实现创建/提交服务**

`backend/app/services/dropship_service.py`：

核心逻辑：
1. **创建**: 计算 purchase_total / sale_total / gross_profit / gross_margin（拆税后）
2. **提交**:
   - 如需新建供应商（supplier_name 有值但 supplier_id 为空）→ 创建 Supplier（仅名称）
   - 如需新建产品（product_id 为空）→ 创建 Product（category='代采代发'）
   - 创建 PayableBill（金额=purchase_total，挂到 account_set + supplier）
   - 状态 draft → pending_payment
3. **毛利计算**:
   - 不含税售价 = sale_total / (1 + sale_tax_rate/100)
   - 不含税成本 = purchase_total / (1 + purchase_tax_rate/100) （专票） 或 purchase_total（普票）
   - gross_profit = 不含税售价 - 不含税成本
   - gross_margin = gross_profit / 不含税售价 × 100

关键注意：
- 单号生成复用 `generate_sequential_no` 函数，前缀 `DS`
- PayableBill 创建参照现有采购收货时的逻辑（`backend/app/routers/purchase_orders.py` 中 receive 端点的 PayableBill 创建方式）
- 事务保证：用 `@transactions.in_transaction()` 包裹

**Step 2: 在路由中接入服务**

实现 `POST /api/dropship`（创建）和 `POST /api/dropship/{id}/submit`（提交）两个端点。

权限：`require_permission("dropship")`

**Step 3: 验证**

启动后端，用 curl 测试创建和提交流程。

**Step 4: Commit**

```bash
git add backend/app/services/dropship_service.py backend/app/routers/dropship.py
git commit -m "feat(代采代发): 创建+提交逻辑 — 自动建供应商/产品/应付单"
```

---

## Task 4: 后端服务 — 付款工作台 + 凭证A

**Files:**
- Modify: `backend/app/services/dropship_service.py`
- Modify: `backend/app/routers/dropship.py`

**Step 1: 实现付款工作台查询**

`GET /api/dropship/payment-workbench`:
- 查询 status='pending_payment' 的所有 DropshipOrder
- 按 supplier 分组
- 每单返回：ds_no, product_name, quantity, purchase_total, sale_total, gross_profit, customer_name, settlement_type, urged_at
- 汇总：总笔数、总金额、已预付笔数

**Step 2: 实现批量付款**

`POST /api/dropship/batch-pay` (DropshipPaymentRequest):
1. 校验所有 order_ids 状态为 pending_payment
2. 如果 payment_method == 'employee_advance'，校验 employee_id 不为空
3. 对每单：
   - 创建 DisbursementBill（金额=purchase_total，method=payment_method）
   - 更新 PayableBill 的 paid_amount / status
   - 状态 pending_payment → paid_pending_ship
4. 按 supplier 分组生成凭证A：
   - 查找科目：预付账款(1123)、银行存款(1002) 或 其他应收款(1221)
   - 合并金额，摘要含供应商名 + 所有DS单号
   - 凭证类型 `付`

```python
# 凭证A 核心逻辑伪代码
voucher_groups = {}  # supplier_id → [orders]
for order in orders:
    voucher_groups.setdefault(order.supplier_id, []).append(order)

for supplier_id, group_orders in voucher_groups.items():
    supplier = await Supplier.get(id=supplier_id)
    total_amount = sum(o.purchase_total for o in group_orders)
    ds_nos = "/".join(o.ds_no for o in group_orders)
    summary = f"代采代发付款 {supplier.name} {ds_nos}"

    # 借: 预付账款-供应商
    # 贷: 银行存款 or 其他应收款-员工借支
    credit_acct = bank_acct if method != 'employee_advance' else other_receivable_acct
    # ... 创建 Voucher + VoucherEntry
```

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 付款工作台 + 批量付款 + 凭证A生成"
```

---

## Task 5: 后端服务 — 确认发货

**Files:**
- Modify: `backend/app/services/dropship_service.py`
- Modify: `backend/app/routers/dropship.py`

**Step 1: 实现确认发货**

`POST /api/dropship/{id}/ship` (DropshipShipRequest):
1. 校验状态为 paid_pending_ship
2. 更新 carrier_code / carrier_name / tracking_no
3. 创建 ReceivableBill:
   - 金额 = sale_total
   - customer = order.customer
   - platform_order_no = order.platform_order_no
   - dropship_order_id = order.id
   - account_set_id = order.account_set_id
4. 如果 shipping_mode == 'transit'（过手转发）:
   - 查找/创建"代采代发中转仓"虚拟仓库
   - 创建 PurchaseReceiptBill（入库）
   - 创建 SalesDeliveryBill（出库）
   - 更新 WarehouseStock
5. 订阅快递100:
   - 复用现有 `logistics.py` 中的 KD100 订阅逻辑
   - 设置 kd100_subscribed = True
6. 状态 paid_pending_ship → shipped

**Step 2: 实现 KD100 回调处理**

扩展现有的 KD100 回调逻辑（在 `backend/app/routers/logistics.py` 中），当签收时检查是否有关联的 DropshipOrder，自动标记 completed。

或者在 `dropship.py` 路由中添加专用回调端点。

**Step 3: 实现手动确认完成**

`POST /api/dropship/{id}/complete`:
- 校验状态为 shipped
- 状态 shipped → completed

**Step 4: Commit**

```bash
git commit -m "feat(代采代发): 确认发货 — 应收单+出入库+KD100订阅"
```

---

## Task 6: 后端服务 — 扩展发票确认（凭证B）

**Files:**
- Modify: `backend/app/services/invoice_service.py`

**Step 1: 在 confirm_invoice 中增加代采代发分支**

在 `confirm_invoice` 函数中，当 `inv.direction == "output"` 时，检查关联的 ReceivableBill 是否有 `dropship_order_id`：

```python
# 在现有 output 分支内添加
if inv.direction == "output":
    # 查找是否有代采代发来源
    dropship_order = None
    if inv.receivable_bill_id:
        rb = await ReceivableBill.filter(id=inv.receivable_bill_id).first()
        if rb and rb.dropship_order_id:
            from app.models.dropship import DropshipOrder
            dropship_order = await DropshipOrder.get(id=rb.dropship_order_id)

    if dropship_order:
        # 代采代发专用凭证B
        await _generate_dropship_invoice_voucher(inv, dropship_order, user)
    else:
        # 常规发票凭证（现有逻辑不动）
        ...
```

**Step 2: 实现 `_generate_dropship_invoice_voucher`**

```python
async def _generate_dropship_invoice_voucher(inv: Invoice, ds: DropshipOrder, user):
    """代采代发发票确认 → 生成凭证B（收入确认+成本结转）"""
    acct_set_id = inv.account_set_id

    # 查找科目
    ar_acct = await ChartOfAccount.filter(account_set_id=acct_set_id, code="1122").first()
    output_tax_acct = await ChartOfAccount.filter(account_set_id=acct_set_id, code="222102").first()
    # 代采专用收入/成本科目（优先找 6001-XX 子科目，fallback 到 6001）
    revenue_acct = await ChartOfAccount.filter(
        account_set_id=acct_set_id, code__startswith="6001", name__contains="代采"
    ).first() or await ChartOfAccount.filter(account_set_id=acct_set_id, code="6001").first()
    cogs_acct = await ChartOfAccount.filter(
        account_set_id=acct_set_id, code__startswith="6401", name__contains="代采"
    ).first() or await ChartOfAccount.filter(account_set_id=acct_set_id, code="6401").first()
    prepaid_acct = await ChartOfAccount.filter(account_set_id=acct_set_id, code="1123").first()
    input_tax_acct = await ChartOfAccount.filter(account_set_id=acct_set_id, code="222101").first()

    # 计算金额
    sale_without_tax = (ds.sale_total / (1 + ds.sale_tax_rate / 100)).quantize(Decimal("0.01"))
    sale_tax = ds.sale_total - sale_without_tax

    if ds.invoice_type == "special":
        # 专票: 成本不含税
        cost_without_tax = (ds.purchase_total / (1 + ds.purchase_tax_rate / 100)).quantize(Decimal("0.01"))
        input_tax = ds.purchase_total - cost_without_tax
    else:
        # 普票: 含税全额入成本
        cost_without_tax = ds.purchase_total
        input_tax = Decimal("0")

    # 创建凭证
    bill_date = inv.invoice_date
    period_name = f"{bill_date.year}-{bill_date.month:02d}"
    total = ds.sale_total + input_tax + cost_without_tax
    vno = await _next_voucher_no(acct_set_id, "记", period_name)

    v = await Voucher.create(
        account_set_id=acct_set_id, voucher_type="记", voucher_no=vno,
        period_name=period_name, voucher_date=bill_date,
        summary=f"代采代发收入确认 {ds.ds_no}",
        total_debit=total, total_credit=total,
        status="draft", creator=user,
        source_type="invoice", source_bill_id=inv.id,
    )

    line = 1
    # 借: 应收账款
    await VoucherEntry.create(voucher=v, line_no=line, account_id=ar_acct.id,
        summary=f"代采代发收入 {ds.ds_no}", debit_amount=ds.sale_total,
        credit_amount=Decimal("0"), aux_customer_id=ds.customer_id)
    line += 1
    # 贷: 销项税额
    await VoucherEntry.create(voucher=v, line_no=line, account_id=output_tax_acct.id,
        summary=f"代采代发销项税 {ds.ds_no}", debit_amount=Decimal("0"),
        credit_amount=sale_tax)
    line += 1
    # 贷: 主营业务收入-代采
    await VoucherEntry.create(voucher=v, line_no=line, account_id=revenue_acct.id,
        summary=f"代采代发收入 {ds.ds_no}", debit_amount=Decimal("0"),
        credit_amount=sale_without_tax)

    # 专票: 借进项税额
    if ds.invoice_type == "special" and input_tax > 0 and input_tax_acct:
        line += 1
        await VoucherEntry.create(voucher=v, line_no=line, account_id=input_tax_acct.id,
            summary=f"代采代发进项税 {ds.ds_no}", debit_amount=input_tax,
            credit_amount=Decimal("0"))

    line += 1
    # 借: 主营业务成本-代采
    await VoucherEntry.create(voucher=v, line_no=line, account_id=cogs_acct.id,
        summary=f"代采代发成本 {ds.ds_no}", debit_amount=cost_without_tax,
        credit_amount=Decimal("0"))
    line += 1
    # 贷: 预付账款
    await VoucherEntry.create(voucher=v, line_no=line, account_id=prepaid_acct.id,
        summary=f"代采代发成本 {ds.ds_no}", debit_amount=Decimal("0"),
        credit_amount=ds.purchase_total, aux_supplier_id=ds.supplier_id)

    inv.voucher = v
    inv.voucher_no = vno
    await inv.save()
```

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 扩展发票确认 — 凭证B(收入确认+成本结转+税)"
```

---

## Task 7: 后端服务 — 取消 + 催付款

**Files:**
- Modify: `backend/app/services/dropship_service.py`
- Modify: `backend/app/routers/dropship.py`

**Step 1: 实现取消逻辑**

`POST /api/dropship/{id}/cancel` (DropshipCancelRequest):

按取消时的状态分别处理：
- **pending_payment**: 冲销 PayableBill（status→cancelled）
- **paid_pending_ship**: 冲销 PayableBill + DisbursementBill，红冲凭证A（创建一张负数凭证），如果 payment_method 是 employee_advance 则恢复借支

核心：创建红冲凭证时参照现有凭证，所有金额取反。

**Step 2: 实现催付款**

`POST /api/dropship/{id}/urge`:
- 更新 urged_at = now()
- 返回成功提示

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 取消+冲销+催付款逻辑"
```

---

## Task 8: 后端 — 列表查询 + 报表 API

**Files:**
- Modify: `backend/app/routers/dropship.py`

**Step 1: 实现列表查询**

`GET /api/dropship`:
- 参数：status, start_date, end_date, search, account_set_id, offset, limit
- search 模糊匹配：ds_no, product_name, customer.name, supplier.name, platform_order_no
- select_related: supplier, customer, product, creator, payment_employee
- 返回格式参照 purchase_orders 列表

**Step 2: 实现报表端点**

三个报表端点：
1. `GET /api/dropship/reports/summary` — 按 account_set_id + 月份筛选，返回按客户/按供应商两个维度的汇总
2. `GET /api/dropship/reports/profit` — 每单毛利明细 + 汇总
3. `GET /api/dropship/reports/receivable` — 已发货但未回款的单据列表（关联 ReceivableBill 状态）

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 列表查询+报表API"
```

---

## Task 9: 后端 — 供应商批量导入

**Files:**
- Modify: `backend/app/routers/suppliers.py` (或 `dropship.py`)

**Step 1: 添加 Excel 导入端点**

`POST /api/suppliers/import`:
- 接收上传的 .xlsx 文件
- 解析第一列为名称（必填），其他列可选（联系人、电话、地址等）
- 按名称去重（已存在则跳过）
- 返回导入结果：成功数、跳过数、失败明细

`GET /api/suppliers/import-template`:
- 返回模板 .xlsx 文件下载

使用 openpyxl 读取 Excel。

**Step 2: Commit**

```bash
git commit -m "feat(代采代发): 供应商批量导入(Excel)"
```

---

## Task 10: 前端 — 导航 + 路由 + 视图框架

**Files:**
- Modify: `frontend/src/utils/constants.js`
- Modify: `frontend/src/router/index.js`
- Create: `frontend/src/views/DropshipView.vue`
- Create: `frontend/src/api/dropship.js`

**Step 1: 添加菜单项和权限**

在 `constants.js` 中：

```javascript
// iconMap 添加
import { ..., Repeat } from 'lucide-vue-next'
export const iconMap = {
  ...,
  dropship: Repeat,
}

// menuItems 添加（放在 consignment 后面）
{ key: 'dropship', name: '代采代发', perm: 'dropship', group: '业务' },

// allPermissions 添加
{ key: 'dropship', name: '代采代发' },
{ key: 'dropship_pay', name: '代采代发付款' },

// permissionGroups 添加
{ label: '代采代发', icon: 'dropship', main: 'dropship', children: [
  { key: 'dropship_pay', name: '代采代发付款' },
]},

// 新增状态映射
export const dropshipStatusNames = {
  draft: '草稿', pending_payment: '待付款', paid_pending_ship: '已付待发',
  shipped: '已发货', completed: '已完成', cancelled: '已取消'
}
export const dropshipStatusBadges = {
  draft: 'badge badge-gray', pending_payment: 'badge badge-yellow',
  paid_pending_ship: 'badge badge-blue', shipped: 'badge badge-green',
  completed: 'badge badge-green', cancelled: 'badge badge-gray'
}
```

**Step 2: 添加路由**

在 `router/index.js` 中添加：

```javascript
{ path: '/dropship', name: 'dropship', component: () => import('../views/DropshipView.vue'), meta: { perm: 'dropship' } },
```

**Step 3: 创建 API 模块**

```javascript
// frontend/src/api/dropship.js
import api from './index'

export const getDropshipOrders = (params) => api.get('/dropship', { params })
export const getDropshipOrder = (id) => api.get('/dropship/' + id)
export const createDropshipOrder = (data) => api.post('/dropship', data)
export const updateDropshipOrder = (id, data) => api.put('/dropship/' + id, data)
export const submitDropshipOrder = (id) => api.post('/dropship/' + id + '/submit')
export const urgeDropshipOrder = (id) => api.post('/dropship/' + id + '/urge')
export const batchPayDropship = (data) => api.post('/dropship/batch-pay', data)
export const shipDropshipOrder = (id, data) => api.post('/dropship/' + id + '/ship', data)
export const completeDropshipOrder = (id) => api.post('/dropship/' + id + '/complete')
export const cancelDropshipOrder = (id, data) => api.post('/dropship/' + id + '/cancel', data)
export const getPaymentWorkbench = (params) => api.get('/dropship/payment-workbench', { params })
export const getDropshipSummary = (params) => api.get('/dropship/reports/summary', { params })
export const getDropshipProfit = (params) => api.get('/dropship/reports/profit', { params })
export const getDropshipReceivable = (params) => api.get('/dropship/reports/receivable', { params })
```

**Step 4: 创建视图框架**

```vue
<!-- frontend/src/views/DropshipView.vue -->
<template>
  <div>
    <AppTabs v-model="activeTab" :tabs="tabs" container-class="mb-4" />
    <DropshipListPanel v-if="activeTab === 'orders'" key="orders" />
    <DropshipPaymentPanel v-else-if="activeTab === 'payment'" key="payment" />
    <DropshipReportsPanel v-else-if="activeTab === 'reports'" key="reports" />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppTabs from '../components/common/AppTabs.vue'
// Panels will be created in subsequent tasks

const tabs = [
  { value: 'orders', label: '代采代发单' },
  { value: 'payment', label: '付款工作台' },
  { value: 'reports', label: '报表' },
]
const route = useRoute()
const router = useRouter()
const validTabs = tabs.map(t => t.value)
const activeTab = ref(validTabs.includes(route.query.tab) ? route.query.tab : 'orders')
watch(activeTab, val =>
  router.replace({ query: { ...route.query, tab: val === 'orders' ? undefined : val } })
)
</script>
```

**Step 5: `npm run build` 验证编译通过**

**Step 6: Commit**

```bash
git commit -m "feat(代采代发): 前端导航+路由+API+视图框架"
```

---

## Task 11: 前端 — 代采代发列表面板

**Files:**
- Create: `frontend/src/components/business/DropshipListPanel.vue`
- Modify: `frontend/src/views/DropshipView.vue`

**Step 1: 实现列表面板**

参照 `PurchaseOrdersPanel.vue` 的模式实现，包含：

- **顶部**: 账套选择 + [新建代采代发单] 按钮
- **状态筛选 tabs**: 全部 / 待付款 / 已付待发 / 已发货 / 已完成 / 已取消（带计数）
- **搜索 + 时间筛选**
- **表格**: ds_no / 状态(badge) / 供应商 / 商品×数量 / 客户 / 采购额 / 售价 / 毛利
- **每行操作按钮**: 根据状态显示（编辑/催付款/填快递/查看物流/确认完成/取消）
- **底部汇总**: 本月笔数 / 采购总额 / 销售总额 / 总毛利 / 平均毛利率
- **游标分页**: 复用现有分页模式

关键 UI 要求：
- 使用现有的 badge class（`badge badge-yellow` 等）
- 表格样式完全对齐现有页面（`table-auto w-full` + `th/td` 类名）
- 弹窗使用统一 modal 模式
- 催付款按钮点击后弹 toast + 调 urge API

**Step 2: `npm run build` 验证**

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 列表面板 — 状态筛选+操作按钮+汇总"
```

---

## Task 12: 前端 — 新建/编辑表单

**Files:**
- Create: `frontend/src/components/business/DropshipFormModal.vue`
- Modify: `frontend/src/components/business/DropshipListPanel.vue`

**Step 1: 实现录单表单 Modal**

表单分区：
1. **基本信息**: 账套选择 + 单号显示
2. **采购信息**: 供应商搜索(+快速新建) / 商品名称(模糊匹配) / 发票类型(专票/普票) / 采购单价 / 数量 / 采购总额
3. **销售信息**: 客户选择 / 平台合约订单编号 / 税率 / 销售单价 / 数量(锁定) / 销售总额 / 毛利实时计算
4. **结算方式**: 先款后货/赊销 + 关联收款单（先款后货时显示）
5. **物流信息**: 发货方式(供应商直发/过手转发) / 快递公司+单号(可空)
6. **备注**
7. **操作按钮**: 保存草稿 / 提交

关键实现：
- 供应商搜索下拉：输入关键字调 `/api/suppliers?search=XXX`，底部显示"+ 快速新建供应商 XXX"
- 商品名模糊匹配：输入关键字调 `/api/products?search=XXX`，显示匹配结果 + "创建新产品"选项
- 毛利实时计算（拆税后）：watch 采购价/售价/数量/发票类型，实时显示
- 先款后货关联收款单：调已有的 ReceiptBill API 查询客户预收款

**Step 2: `npm run build` 验证**

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 录单表单 — 供应商搜索+商品匹配+毛利计算"
```

---

## Task 13: 前端 — 付款工作台面板

**Files:**
- Create: `frontend/src/components/business/DropshipPaymentPanel.vue`
- Modify: `frontend/src/views/DropshipView.vue`

**Step 1: 实现付款工作台**

布局：
- **顶部**: 账套选择 + 汇总信息（今日待付笔数/金额/已预付笔数）
- **主体**: 按供应商分组的卡片列表
  - 分组标题：供应商名（N笔，小计 ¥XXX）
  - 每单：checkbox + ds_no / 商品 / 采购额+售价+毛利 / 客户 / 回款状态(✅/⏳) / 催标记
- **底部操作栏**: 已勾选 N 笔 / 合计 ¥XXX / 付款方式下拉 / [批量确认付款] 按钮
  - 选"冲减借支"时，额外显示员工下拉框

参照现有 FinancePayablesPanel.vue 的交互模式。

**Step 2: `npm run build` 验证**

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 付款工作台 — 供应商分组+批量付款+冲减借支"
```

---

## Task 14: 前端 — 发货弹窗 + 取消弹窗

**Files:**
- Create: `frontend/src/components/business/DropshipShipModal.vue`
- Create: `frontend/src/components/business/DropshipCancelModal.vue`
- Modify: `frontend/src/components/business/DropshipListPanel.vue`

**Step 1: 发货弹窗**

显示：单据摘要 + 快递公司下拉 + 快递单号输入 + [确认发货] 按钮。

快递公司列表复用现有 `logistics.js` 的 carriers API。

**Step 2: 取消弹窗**

显示：
- 单据摘要 + 当前状态
- 如果已付待发，提示"已付款 ¥XXX，取消后生成退款单"
- 取消原因输入
- [再想想] [确认取消] 按钮

**Step 3: `npm run build` 验证**

**Step 4: Commit**

```bash
git commit -m "feat(代采代发): 发货弹窗+取消弹窗"
```

---

## Task 15: 前端 — 报表面板

**Files:**
- Create: `frontend/src/components/business/DropshipReportsPanel.vue`
- Modify: `frontend/src/views/DropshipView.vue`

**Step 1: 实现报表面板**

三个子 tab：
1. **月度汇总**: 按客户/按供应商两个维度的表格，支持月份切换
2. **毛利报表**: 每单毛利明细表 + 底部汇总行
3. **应收未收**: 已发货未回款的列表

使用现有的表格样式和筛选器模式。

**Step 2: `npm run build` 验证**

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 报表面板 — 月度汇总+毛利+应收"
```

---

## Task 16: 前端 — 供应商批量导入

**Files:**
- Modify: `frontend/src/components/business/DropshipListPanel.vue` 或新建导入组件

**Step 1: 添加导入功能**

在列表面板或供应商管理中增加：
- [下载模板] 按钮 → 调 `/api/suppliers/import-template`
- [批量导入] 按钮 → 打开文件选择器 → 上传 .xlsx → 显示导入结果

**Step 2: `npm run build` 验证**

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 供应商批量导入(Excel)"
```

---

## Task 17: 权限迁移 + 最终集成

**Files:**
- Modify: `backend/app/migrations.py`
- Modify: `backend/main.py`

**Step 1: 添加权限迁移**

在 migrations.py 中为现有活跃用户追加 `dropship` + `dropship_pay` 权限（参照 `_migrate_ai_permissions` 模式）。

**Step 2: 全流程验证**

1. 启动前后端
2. 创建代采代发单 → 提交 → 付款工作台确认付款 → 填快递号发货 → 确认完成
3. 检查自动生成的：应付单、付款单、凭证A、应收单
4. 在发票管理从应收单推发票 → 确认发票 → 检查凭证B
5. 取消流程测试
6. 报表数据验证

**Step 3: Commit**

```bash
git commit -m "feat(代采代发): 权限迁移+全流程集成"
```

---

## Task 18: 收尾 — build + 代码检查

**Step 1: 前端完整构建**

```bash
cd frontend && npm run build
```

确保无编译错误。

**Step 2: 后端启动验证**

```bash
cd backend && python main.py
```

确保无启动错误，迁移正常执行。

**Step 3: 最终 Commit**

```bash
git commit -m "chore(代采代发): 构建验证通过"
```

---

## 文件清单总览

| 类型 | 路径 | 操作 |
|------|------|------|
| 后端模型 | `backend/app/models/dropship.py` | 新建 |
| 后端模型注册 | `backend/app/models/__init__.py` | 修改 |
| 后端迁移 | `backend/app/migrations.py` | 修改 |
| 后端 Schema | `backend/app/schemas/dropship.py` | 新建 |
| 后端路由 | `backend/app/routers/dropship.py` | 新建 |
| 后端服务 | `backend/app/services/dropship_service.py` | 新建 |
| 后端发票扩展 | `backend/app/services/invoice_service.py` | 修改 |
| 后端主入口 | `backend/main.py` | 修改 |
| 后端供应商导入 | `backend/app/routers/suppliers.py` | 修改 |
| 后端 AR 模型 | `backend/app/models/ar_ap.py` | 修改 |
| 前端视图 | `frontend/src/views/DropshipView.vue` | 新建 |
| 前端 API | `frontend/src/api/dropship.js` | 新建 |
| 前端列表 | `frontend/src/components/business/DropshipListPanel.vue` | 新建 |
| 前端表单 | `frontend/src/components/business/DropshipFormModal.vue` | 新建 |
| 前端付款台 | `frontend/src/components/business/DropshipPaymentPanel.vue` | 新建 |
| 前端发货弹窗 | `frontend/src/components/business/DropshipShipModal.vue` | 新建 |
| 前端取消弹窗 | `frontend/src/components/business/DropshipCancelModal.vue` | 新建 |
| 前端报表 | `frontend/src/components/business/DropshipReportsPanel.vue` | 新建 |
| 前端常量 | `frontend/src/utils/constants.js` | 修改 |
| 前端路由 | `frontend/src/router/index.js` | 修改 |
