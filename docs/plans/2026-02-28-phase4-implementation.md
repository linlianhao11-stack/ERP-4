# 阶段4：发票 + 出入库单 + PDF套打 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立发票管理体系（销项/进项）和出入库单据体系（销售出库单/采购入库单），与现有发货/收货流程自动衔接，并提供 PDF 套打功能。

**Architecture:** 新建6个模型（2文件）+ 2个服务（delivery_service + invoice_service）+ 3个路由（invoices/sales-delivery/purchase-receipt）+ PDF工具。通过钩子嵌入 logistics.py（发货→出库单+凭证）和 purchase_orders.py（收货→入库单+凭证）。发票从应收单手动推送生成，确认时生成复合凭证（收入确认+成本结转）。

**Tech Stack:** FastAPI + Tortoise ORM + Pydantic / Vue 3 + Tailwind CSS 4 / reportlab（PDF）

---

## 关键设计决策

| 决策 | 选择 |
|------|------|
| 发票生成 | 手动从应收单推送，税率从产品带入可修改 |
| 进项发票 | 手工录入，关联应付单 |
| 凭证拆税 | 专票/普票统一拆税（不含税收入+税额） |
| 出入库单 | 正式财务单据，独立编号，发货/收货时自动生成 |
| 出库单凭证 | 借 发出商品1407 / 贷 库存商品1405 |
| 入库单凭证 | 借 库存商品1405 + 借 进项税222101 / 贷 应付账款2202 |
| 销项发票凭证 | 借 应收1122 + 借 成本6401 / 贷 收入6001 + 贷 销项税222102 + 贷 发出商品1407 |
| 进项发票 | 不生成凭证，仅税务记录 |
| PDF | 3种（凭证/出库单/入库单），24×14cm，reportlab + WenQuanYi Zen Hei |

## 凭证分录明细

### 出库单凭证
```
借：发出商品     1407    （total_cost = Σ quantity × cost_price）
贷：库存商品     1405    （同上）
```

### 入库单凭证
```
借：库存商品         1405    （total_amount_without_tax）
借：应交税费-进项税   222101  （total_tax）
贷：应付账款         2202    （total_amount，辅助：supplier_id）
```

### 销项发票凭证（5条分录）
```
借：应收账款         1122    （price_tax_total，辅助：customer_id）
贷：主营业务收入     6001    （amount_without_tax）
贷：应交税费-销项税   222102  （tax_amount）
借：主营业务成本     6401    （cost_total，从关联出库单获取）
贷：发出商品         1407    （同上）
```

---

## 文件总览

### 新建文件（18个）

| 文件 | 用途 |
|------|------|
| `backend/app/models/invoice.py` | Invoice + InvoiceItem（2个模型） |
| `backend/app/models/delivery.py` | SalesDeliveryBill/Item + PurchaseReceiptBill/Item（4个模型） |
| `backend/app/schemas/invoice.py` | 发票 schemas |
| `backend/app/schemas/delivery.py` | 出入库单 schemas |
| `backend/app/services/delivery_service.py` | 出入库单创建 + 自动凭证 |
| `backend/app/services/invoice_service.py` | 发票推送 + 确认 + 凭证 |
| `backend/app/routers/invoices.py` | 发票路由（7端点） |
| `backend/app/routers/sales_delivery.py` | 出库单路由（4端点） |
| `backend/app/routers/purchase_receipt.py` | 入库单路由（4端点） |
| `backend/app/utils/pdf_print.py` | PDF套打工具（3种模板） |
| `backend/tests/test_phase4_models.py` | 模型测试 |
| `backend/tests/test_phase4_service.py` | 服务测试 |
| `frontend/src/components/business/InvoicePanel.vue` | 发票管理容器 |
| `frontend/src/components/business/SalesInvoiceTab.vue` | 销项发票Tab |
| `frontend/src/components/business/PurchaseInvoiceTab.vue` | 进项发票Tab |
| `frontend/src/components/business/SalesDeliveryTab.vue` | 出库单Tab |
| `frontend/src/components/business/PurchaseReceiptTab.vue` | 入库单Tab |

### 修改文件（10个）

| 文件 | 变更 |
|------|------|
| `backend/app/models/__init__.py` | 导入6个新模型 |
| `backend/app/migrations.py` | 新增 migrate_accounting_phase4() |
| `backend/app/services/accounting_init.py` | 新增预置科目 1407发出商品 |
| `backend/main.py` | 注册3个新路由 |
| `backend/app/routers/logistics.py` | 钩子：发货→出库单+凭证 |
| `backend/app/routers/purchase_orders.py` | 钩子：收货→入库单+凭证 |
| `backend/app/routers/vouchers.py` | 新增凭证PDF下载端点 |
| `backend/requirements.txt` | 追加 reportlab |
| `Dockerfile` | 安装 fonts-wqy-zenhei |
| `frontend/src/api/accounting.js` | 新增API函数 |
| `frontend/src/views/AccountingView.vue` | 新增发票Tab + 出入库Tab入口 |

---

## Task 1: 出入库单模型（4个模型）

**文件：**
- 创建：`backend/app/models/delivery.py`
- 修改：`backend/app/models/__init__.py`

**delivery.py 完整代码：**

```python
"""出入库单模型"""
from tortoise import fields, models


class SalesDeliveryBill(models.Model):
    """销售出库单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="sales_delivery_bills", on_delete=fields.CASCADE)
    customer = fields.ForeignKeyField("models.Customer", related_name="sales_delivery_bills", on_delete=fields.RESTRICT)
    order = fields.ForeignKeyField("models.Order", related_name="sales_delivery_bills", null=True, on_delete=fields.SET_NULL)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="sales_delivery_bills", null=True, on_delete=fields.SET_NULL)
    bill_date = fields.DateField()
    total_cost = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = fields.CharField(max_length=20, default="confirmed")
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="sales_delivery_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_sales_deliveries", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "sales_delivery_bills"
        indexes = (("account_set_id", "customer_id"),)


class SalesDeliveryItem(models.Model):
    """出库单明细"""
    id = fields.IntField(pk=True)
    delivery_bill = fields.ForeignKeyField("models.SalesDeliveryBill", related_name="items", on_delete=fields.CASCADE)
    order_item = fields.ForeignKeyField("models.OrderItem", null=True, on_delete=fields.SET_NULL, related_name="delivery_items")
    product = fields.ForeignKeyField("models.Product", on_delete=fields.RESTRICT, related_name="delivery_items")
    product_name = fields.CharField(max_length=200)
    quantity = fields.IntField()
    cost_price = fields.DecimalField(max_digits=18, decimal_places=2)
    sale_price = fields.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        table = "sales_delivery_items"


class PurchaseReceiptBill(models.Model):
    """采购入库单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="purchase_receipt_bills", on_delete=fields.CASCADE)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="purchase_receipt_bills", on_delete=fields.RESTRICT)
    purchase_order = fields.ForeignKeyField("models.PurchaseOrder", related_name="purchase_receipt_bills", null=True, on_delete=fields.SET_NULL)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="purchase_receipt_bills", null=True, on_delete=fields.SET_NULL)
    bill_date = fields.DateField()
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount_without_tax = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_tax = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = fields.CharField(max_length=20, default="confirmed")
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="purchase_receipt_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_purchase_receipts", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "purchase_receipt_bills"
        indexes = (("account_set_id", "supplier_id"),)


class PurchaseReceiptItem(models.Model):
    """入库单明细"""
    id = fields.IntField(pk=True)
    receipt_bill = fields.ForeignKeyField("models.PurchaseReceiptBill", related_name="items", on_delete=fields.CASCADE)
    purchase_order_item = fields.ForeignKeyField("models.PurchaseOrderItem", null=True, on_delete=fields.SET_NULL, related_name="receipt_items")
    product = fields.ForeignKeyField("models.Product", on_delete=fields.RESTRICT, related_name="receipt_items")
    product_name = fields.CharField(max_length=200)
    quantity = fields.IntField()
    tax_inclusive_price = fields.DecimalField(max_digits=18, decimal_places=2)
    tax_exclusive_price = fields.DecimalField(max_digits=18, decimal_places=2)
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13)

    class Meta:
        table = "purchase_receipt_items"
```

**`__init__.py` 新增导入（追加到现有 ar_ap 导入之后）：**
```python
from app.models.delivery import (
    SalesDeliveryBill, SalesDeliveryItem, PurchaseReceiptBill, PurchaseReceiptItem
)
```

**`__all__` 列表追加：**
```python
"SalesDeliveryBill", "SalesDeliveryItem", "PurchaseReceiptBill", "PurchaseReceiptItem",
```

**验证：** `cd backend && python -c "from app.models import SalesDeliveryBill, PurchaseReceiptBill; print('OK')"`

**提交：** `feat: 新增4个出入库单模型`

---

## Task 2: 发票模型（2个模型）

**文件：** 创建 `backend/app/models/invoice.py`

**invoice.py 完整代码：**

```python
"""发票模型"""
from tortoise import fields, models


class Invoice(models.Model):
    """发票"""
    id = fields.IntField(pk=True)
    invoice_no = fields.CharField(max_length=30, unique=True)
    invoice_type = fields.CharField(max_length=20)  # special / normal
    direction = fields.CharField(max_length=10)  # output（销项）/ input（进项）
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="invoices", on_delete=fields.CASCADE)
    customer = fields.ForeignKeyField("models.Customer", related_name="invoices", null=True, on_delete=fields.RESTRICT)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="invoices", null=True, on_delete=fields.RESTRICT)
    receivable_bill = fields.ForeignKeyField("models.ReceivableBill", related_name="invoices", null=True, on_delete=fields.SET_NULL)
    payable_bill = fields.ForeignKeyField("models.PayableBill", related_name="invoices", null=True, on_delete=fields.SET_NULL)
    invoice_date = fields.DateField()
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    amount_without_tax = fields.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    status = fields.CharField(max_length=20, default="draft")  # draft / confirmed / cancelled
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="invoice")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_invoices", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "invoices"
        indexes = (("account_set_id", "direction"), ("account_set_id", "status"),)


class InvoiceItem(models.Model):
    """发票明细行"""
    id = fields.IntField(pk=True)
    invoice = fields.ForeignKeyField("models.Invoice", related_name="items", on_delete=fields.CASCADE)
    product = fields.ForeignKeyField("models.Product", null=True, on_delete=fields.SET_NULL, related_name="invoice_items")
    product_name = fields.CharField(max_length=200)
    quantity = fields.IntField()
    unit_price = fields.DecimalField(max_digits=18, decimal_places=2)  # 不含税单价
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13)
    tax_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    amount_without_tax = fields.DecimalField(max_digits=18, decimal_places=2)
    amount = fields.DecimalField(max_digits=18, decimal_places=2)  # 价税合计

    class Meta:
        table = "invoice_items"
```

**`__init__.py` 追加导入：**
```python
from app.models.invoice import Invoice, InvoiceItem
```

**`__all__` 追加：** `"Invoice", "InvoiceItem",`

**验证：** `cd backend && python -c "from app.models import Invoice, InvoiceItem; print('OK')"`

**提交：** `feat: 新增发票模型 Invoice + InvoiceItem`

---

## Task 3: 迁移 + 预置科目

**文件：**
- 修改：`backend/app/migrations.py`
- 修改：`backend/app/services/accounting_init.py`

**accounting_init.py — PRESET_ACCOUNTS 列表追加（在 `("1405", "库存商品", ...)` 之后）：**
```python
("1407", "发出商品", None, 1, "asset", "debit", True, False, False),
```

**migrations.py — 新增函数 `migrate_accounting_phase4()`：**

```python
async def migrate_accounting_phase4():
    """阶段4迁移：出入库单+发票 6表 + 索引 + 科目补充"""
    conn = connections.get("default")
    from tortoise import Tortoise
    await Tortoise.generate_schemas(safe=True)

    # 创建索引（IF NOT EXISTS）
    indexes = [
        ("idx_sdb_account_customer", "sales_delivery_bills", "account_set_id, customer_id"),
        ("idx_sdb_order", "sales_delivery_bills", "order_id"),
        ("idx_sdi_bill", "sales_delivery_items", "delivery_bill_id"),
        ("idx_prb_account_supplier", "purchase_receipt_bills", "account_set_id, supplier_id"),
        ("idx_prb_po", "purchase_receipt_bills", "purchase_order_id"),
        ("idx_pri_bill", "purchase_receipt_items", "receipt_bill_id"),
        ("idx_inv_account_direction", "invoices", "account_set_id, direction"),
        ("idx_inv_account_status", "invoices", "account_set_id, status"),
        ("idx_inv_receivable", "invoices", "receivable_bill_id"),
        ("idx_inv_payable", "invoices", "payable_bill_id"),
        ("idx_inv_items_invoice", "invoice_items", "invoice_id"),
    ]
    for idx_name, table, columns in indexes:
        try:
            await conn.execute_query(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})"
            )
        except Exception:
            pass

    # 补充预置科目 1407发出商品（已有账套）
    try:
        from app.models.accounting import AccountSet, ChartOfAccount
        account_sets = await AccountSet.all()
        for a in account_sets:
            exists = await ChartOfAccount.filter(account_set_id=a.id, code="1407").exists()
            if not exists:
                await ChartOfAccount.create(
                    account_set_id=a.id, code="1407", name="发出商品",
                    level=1, category="asset", direction="debit", is_leaf=True
                )
    except Exception:
        pass

    logger.info("阶段4迁移完成：出入库单+发票表 + 索引 + 1407科目")
```

**run_migrations() 中追加调用（在 `await migrate_accounting_phase3()` 之后）：**
```python
await migrate_accounting_phase4()
```

**验证：** `cd backend && python -m pytest tests/ -v --ignore=tests/test_auth.py`

**提交：** `feat: 阶段4迁移 — 6表索引 + 预置科目1407发出商品`

---

## Task 4: Pydantic 请求模型

**文件：**
- 创建：`backend/app/schemas/delivery.py`
- 创建：`backend/app/schemas/invoice.py`

**delivery.py：**

```python
"""出入库单请求模型"""
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from typing import Optional


class SalesDeliveryItemCreate(BaseModel):
    order_item_id: Optional[int] = None
    product_id: int
    product_name: str
    quantity: int
    cost_price: Decimal = Field(max_digits=18, decimal_places=2)
    sale_price: Decimal = Field(max_digits=18, decimal_places=2)


class SalesDeliveryBillCreate(BaseModel):
    customer_id: int
    order_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    bill_date: Optional[date] = None
    remark: str = ""
    items: list[SalesDeliveryItemCreate]


class PurchaseReceiptItemCreate(BaseModel):
    purchase_order_item_id: Optional[int] = None
    product_id: int
    product_name: str
    quantity: int
    tax_inclusive_price: Decimal = Field(max_digits=18, decimal_places=2)
    tax_exclusive_price: Decimal = Field(max_digits=18, decimal_places=2)
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2, default=Decimal("13"))


class PurchaseReceiptBillCreate(BaseModel):
    supplier_id: int
    purchase_order_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    bill_date: Optional[date] = None
    remark: str = ""
    items: list[PurchaseReceiptItemCreate]
```

**invoice.py：**

```python
"""发票请求模型"""
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from typing import Optional


class InvoiceItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity: int
    unit_price: Decimal = Field(max_digits=18, decimal_places=2)
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2, default=Decimal("13"))


class InvoiceFromReceivable(BaseModel):
    """从应收单推送生成销项发票"""
    receivable_bill_id: int
    invoice_type: str = "special"  # special / normal
    invoice_date: Optional[date] = None
    items: list[InvoiceItemCreate]
    remark: str = ""


class InvoiceCreate(BaseModel):
    """手工创建进项发票"""
    invoice_type: str = "special"
    supplier_id: int
    payable_bill_id: Optional[int] = None
    invoice_date: Optional[date] = None
    items: list[InvoiceItemCreate]
    remark: str = ""


class InvoiceUpdate(BaseModel):
    """修改草稿发票"""
    invoice_type: Optional[str] = None
    invoice_date: Optional[date] = None
    items: Optional[list[InvoiceItemCreate]] = None
    remark: Optional[str] = None
```

**提交：** `feat: 新增阶段4 Pydantic 请求模型`

---

## Task 5: 出入库单服务层

**文件：** 创建 `backend/app/services/delivery_service.py`

**核心函数：**

```python
"""出入库单服务层"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from tortoise import transactions
from app.models.delivery import SalesDeliveryBill, SalesDeliveryItem, PurchaseReceiptBill, PurchaseReceiptItem
from app.models.accounting import AccountSet, ChartOfAccount
from app.models.voucher import Voucher, VoucherEntry
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("delivery_service")


async def _next_voucher_no(account_set_id: int, voucher_type: str, period_name: str) -> str:
    account_set = await AccountSet.filter(id=account_set_id).first()
    prefix = f"{account_set.code}-{voucher_type}-{period_name.replace('-', '')}-"
    last = await Voucher.filter(
        account_set_id=account_set_id, voucher_type=voucher_type, period_name=period_name,
    ).order_by("-voucher_no").first()
    if last and last.voucher_no.startswith(prefix):
        seq = int(last.voucher_no[len(prefix):]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


async def create_sales_delivery(
    account_set_id: int,
    customer_id: int,
    order_id: int | None,
    warehouse_id: int | None,
    items: list[dict],
    creator=None,
    remark: str = "",
    bill_date: date | None = None,
) -> SalesDeliveryBill:
    """创建销售出库单 + 自动生成凭证（借发出商品/贷库存商品）"""
    if bill_date is None:
        bill_date = date.today()

    total_cost = sum(Decimal(str(it["quantity"])) * Decimal(str(it["cost_price"])) for it in items)
    total_amount = sum(Decimal(str(it["quantity"])) * Decimal(str(it["sale_price"])) for it in items)

    async with transactions.in_transaction():
        bill = await SalesDeliveryBill.create(
            bill_no=generate_order_no("CK"),
            account_set_id=account_set_id,
            customer_id=customer_id,
            order_id=order_id,
            warehouse_id=warehouse_id,
            bill_date=bill_date,
            total_cost=total_cost,
            total_amount=total_amount,
            status="confirmed",
            remark=remark,
            creator=creator,
        )

        for it in items:
            await SalesDeliveryItem.create(
                delivery_bill=bill,
                order_item_id=it.get("order_item_id"),
                product_id=it["product_id"],
                product_name=it["product_name"],
                quantity=it["quantity"],
                cost_price=Decimal(str(it["cost_price"])),
                sale_price=Decimal(str(it["sale_price"])),
            )

        # 自动生成凭证：借 发出商品1407 / 贷 库存商品1405
        shipped_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="1407", is_active=True
        ).first()
        inventory_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="1405", is_active=True
        ).first()

        if shipped_acct and inventory_acct and total_cost > 0:
            period_name = f"{bill_date.year}-{bill_date.month:02d}"
            vno = await _next_voucher_no(account_set_id, "记", period_name)
            v = await Voucher.create(
                account_set_id=account_set_id,
                voucher_type="记",
                voucher_no=vno,
                period_name=period_name,
                voucher_date=bill_date,
                summary=f"销售出库 {bill.bill_no}",
                total_debit=total_cost,
                total_credit=total_cost,
                status="draft",
                creator=creator,
                source_type="sales_delivery",
                source_bill_id=bill.id,
            )
            await VoucherEntry.create(
                voucher=v, line_no=1,
                account_id=shipped_acct.id,
                summary=f"销售出库 {bill.bill_no}",
                debit_amount=total_cost,
                credit_amount=Decimal("0"),
            )
            await VoucherEntry.create(
                voucher=v, line_no=2,
                account_id=inventory_acct.id,
                summary=f"销售出库 {bill.bill_no}",
                debit_amount=Decimal("0"),
                credit_amount=total_cost,
            )
            bill.voucher = v
            bill.voucher_no = vno
            await bill.save()

    logger.info(f"创建销售出库单: {bill.bill_no}, 成本: {total_cost}")
    return bill


async def create_purchase_receipt(
    account_set_id: int,
    supplier_id: int,
    purchase_order_id: int | None,
    warehouse_id: int | None,
    items: list[dict],
    creator=None,
    remark: str = "",
    bill_date: date | None = None,
) -> PurchaseReceiptBill:
    """创建采购入库单 + 自动生成凭证（借库存+借进项税/贷应付）"""
    if bill_date is None:
        bill_date = date.today()

    total_amount = Decimal("0")
    total_without_tax = Decimal("0")
    total_tax = Decimal("0")
    for it in items:
        qty = Decimal(str(it["quantity"]))
        incl = Decimal(str(it["tax_inclusive_price"]))
        excl = Decimal(str(it["tax_exclusive_price"]))
        line_amount = (qty * incl).quantize(Decimal("0.01"))
        line_without = (qty * excl).quantize(Decimal("0.01"))
        total_amount += line_amount
        total_without_tax += line_without
        total_tax += line_amount - line_without

    async with transactions.in_transaction():
        bill = await PurchaseReceiptBill.create(
            bill_no=generate_order_no("RK"),
            account_set_id=account_set_id,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            warehouse_id=warehouse_id,
            bill_date=bill_date,
            total_amount=total_amount,
            total_amount_without_tax=total_without_tax,
            total_tax=total_tax,
            status="confirmed",
            remark=remark,
            creator=creator,
        )

        for it in items:
            await PurchaseReceiptItem.create(
                receipt_bill=bill,
                purchase_order_item_id=it.get("purchase_order_item_id"),
                product_id=it["product_id"],
                product_name=it["product_name"],
                quantity=it["quantity"],
                tax_inclusive_price=Decimal(str(it["tax_inclusive_price"])),
                tax_exclusive_price=Decimal(str(it["tax_exclusive_price"])),
                tax_rate=Decimal(str(it.get("tax_rate", "13"))),
            )

        # 自动生成凭证：借库存1405+借进项税222101 / 贷应付2202
        inventory_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="1405", is_active=True
        ).first()
        input_tax_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="222101", is_active=True
        ).first()
        ap_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="2202", is_active=True
        ).first()

        if inventory_acct and input_tax_acct and ap_acct and total_amount > 0:
            period_name = f"{bill_date.year}-{bill_date.month:02d}"
            vno = await _next_voucher_no(account_set_id, "记", period_name)
            total_debit = total_without_tax + total_tax  # == total_amount
            v = await Voucher.create(
                account_set_id=account_set_id,
                voucher_type="记",
                voucher_no=vno,
                period_name=period_name,
                voucher_date=bill_date,
                summary=f"采购入库 {bill.bill_no}",
                total_debit=total_debit,
                total_credit=total_amount,
                status="draft",
                creator=creator,
                source_type="purchase_receipt",
                source_bill_id=bill.id,
            )
            await VoucherEntry.create(
                voucher=v, line_no=1,
                account_id=inventory_acct.id,
                summary=f"采购入库 {bill.bill_no}",
                debit_amount=total_without_tax,
                credit_amount=Decimal("0"),
            )
            await VoucherEntry.create(
                voucher=v, line_no=2,
                account_id=input_tax_acct.id,
                summary=f"采购入库 {bill.bill_no} 进项税",
                debit_amount=total_tax,
                credit_amount=Decimal("0"),
            )
            await VoucherEntry.create(
                voucher=v, line_no=3,
                account_id=ap_acct.id,
                summary=f"采购入库 {bill.bill_no}",
                debit_amount=Decimal("0"),
                credit_amount=total_amount,
                aux_supplier_id=supplier_id,
            )
            bill.voucher = v
            bill.voucher_no = vno
            await bill.save()

    logger.info(f"创建采购入库单: {bill.bill_no}, 含税: {total_amount}, 税额: {total_tax}")
    return bill
```

**验证：** `cd backend && python -c "from app.services.delivery_service import create_sales_delivery, create_purchase_receipt; print('OK')"`

**提交：** `feat: 新增出入库单服务层 — 创建 + 自动凭证生成`

---

## Task 6: 发票服务层

**文件：** 创建 `backend/app/services/invoice_service.py`

**核心函数：**

```python
"""发票服务层"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from tortoise import transactions
from app.models.invoice import Invoice, InvoiceItem
from app.models.ar_ap import ReceivableBill
from app.models.delivery import SalesDeliveryBill
from app.models.accounting import AccountSet, ChartOfAccount
from app.models.voucher import Voucher, VoucherEntry
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("invoice_service")


async def _next_voucher_no(account_set_id: int, voucher_type: str, period_name: str) -> str:
    account_set = await AccountSet.filter(id=account_set_id).first()
    prefix = f"{account_set.code}-{voucher_type}-{period_name.replace('-', '')}-"
    last = await Voucher.filter(
        account_set_id=account_set_id, voucher_type=voucher_type, period_name=period_name,
    ).order_by("-voucher_no").first()
    if last and last.voucher_no.startswith(prefix):
        seq = int(last.voucher_no[len(prefix):]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


def _calc_item_amounts(unit_price: Decimal, quantity: int, tax_rate: Decimal) -> tuple:
    """计算明细行金额：返回 (不含税金额, 税额, 价税合计)"""
    without_tax = (unit_price * quantity).quantize(Decimal("0.01"))
    tax = (without_tax * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
    total = without_tax + tax
    return without_tax, tax, total


async def push_invoice_from_receivable(
    account_set_id: int,
    receivable_bill_id: int,
    invoice_type: str,
    items: list[dict],
    creator=None,
    invoice_date: date | None = None,
    remark: str = "",
) -> Invoice:
    """从应收单推送生成销项发票（草稿状态）"""
    rb = await ReceivableBill.filter(id=receivable_bill_id, account_set_id=account_set_id).first()
    if not rb:
        raise ValueError("应收单不存在或不属于当前账套")

    if invoice_date is None:
        invoice_date = date.today()

    total_without_tax = Decimal("0")
    total_tax = Decimal("0")
    total_amount = Decimal("0")
    item_data = []
    for it in items:
        unit_price = Decimal(str(it["unit_price"]))
        quantity = int(it["quantity"])
        tax_rate = Decimal(str(it.get("tax_rate", "13")))
        without_tax, tax, amount = _calc_item_amounts(unit_price, quantity, tax_rate)
        total_without_tax += without_tax
        total_tax += tax
        total_amount += amount
        item_data.append({**it, "amount_without_tax": without_tax, "tax_amount": tax, "amount": amount})

    invoice = await Invoice.create(
        invoice_no=generate_order_no("XS"),
        invoice_type=invoice_type,
        direction="output",
        account_set_id=account_set_id,
        customer_id=rb.customer_id,
        receivable_bill_id=receivable_bill_id,
        invoice_date=invoice_date,
        total_amount=total_amount,
        amount_without_tax=total_without_tax,
        tax_amount=total_tax,
        status="draft",
        remark=remark,
        creator=creator,
    )

    for it in item_data:
        await InvoiceItem.create(
            invoice=invoice,
            product_id=it.get("product_id"),
            product_name=it["product_name"],
            quantity=it["quantity"],
            unit_price=Decimal(str(it["unit_price"])),
            tax_rate=Decimal(str(it.get("tax_rate", "13"))),
            tax_amount=it["tax_amount"],
            amount_without_tax=it["amount_without_tax"],
            amount=it["amount"],
        )

    logger.info(f"从应收单 {rb.bill_no} 推送生成销项发票: {invoice.invoice_no}")
    return invoice


async def create_input_invoice(
    account_set_id: int,
    supplier_id: int,
    invoice_type: str,
    items: list[dict],
    payable_bill_id: int | None = None,
    creator=None,
    invoice_date: date | None = None,
    remark: str = "",
) -> Invoice:
    """手工创建进项发票"""
    if invoice_date is None:
        invoice_date = date.today()

    total_without_tax = Decimal("0")
    total_tax = Decimal("0")
    total_amount = Decimal("0")
    item_data = []
    for it in items:
        unit_price = Decimal(str(it["unit_price"]))
        quantity = int(it["quantity"])
        tax_rate = Decimal(str(it.get("tax_rate", "13")))
        without_tax, tax, amount = _calc_item_amounts(unit_price, quantity, tax_rate)
        total_without_tax += without_tax
        total_tax += tax
        total_amount += amount
        item_data.append({**it, "amount_without_tax": without_tax, "tax_amount": tax, "amount": amount})

    invoice = await Invoice.create(
        invoice_no=generate_order_no("JX"),
        invoice_type=invoice_type,
        direction="input",
        account_set_id=account_set_id,
        supplier_id=supplier_id,
        payable_bill_id=payable_bill_id,
        invoice_date=invoice_date,
        total_amount=total_amount,
        amount_without_tax=total_without_tax,
        tax_amount=total_tax,
        status="draft",
        remark=remark,
        creator=creator,
    )

    for it in item_data:
        await InvoiceItem.create(
            invoice=invoice,
            product_id=it.get("product_id"),
            product_name=it["product_name"],
            quantity=it["quantity"],
            unit_price=Decimal(str(it["unit_price"])),
            tax_rate=Decimal(str(it.get("tax_rate", "13"))),
            tax_amount=it["tax_amount"],
            amount_without_tax=it["amount_without_tax"],
            amount=it["amount"],
        )

    logger.info(f"创建进项发票: {invoice.invoice_no}")
    return invoice


async def confirm_invoice(invoice_id: int, user) -> Invoice:
    """确认发票。销项发票生成复合凭证（收入确认+成本结转），进项发票不生成凭证。"""
    async with transactions.in_transaction():
        inv = await Invoice.filter(id=invoice_id).select_for_update().first()
        if not inv:
            raise ValueError("发票不存在")
        if inv.status != "draft":
            raise ValueError("只有草稿状态的发票可以确认")

        inv.status = "confirmed"
        await inv.save()

        # 销项发票 → 生成复合凭证
        if inv.direction == "output":
            ar_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="1122", is_active=True
            ).first()
            revenue_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="6001", is_active=True
            ).first()
            output_tax_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="222102", is_active=True
            ).first()
            cogs_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="6401", is_active=True
            ).first()
            shipped_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="1407", is_active=True
            ).first()

            if ar_acct and revenue_acct and output_tax_acct and cogs_acct and shipped_acct:
                # 获取关联的出库单成本
                cost_total = Decimal("0")
                if inv.receivable_bill_id:
                    rb = await ReceivableBill.filter(id=inv.receivable_bill_id).first()
                    if rb and rb.order_id:
                        delivery = await SalesDeliveryBill.filter(order_id=rb.order_id, account_set_id=inv.account_set_id).first()
                        if delivery:
                            cost_total = delivery.total_cost

                bill_date = inv.invoice_date
                period_name = f"{bill_date.year}-{bill_date.month:02d}"
                total_debit = inv.total_amount + cost_total
                total_credit = inv.amount_without_tax + inv.tax_amount + cost_total

                vno = await _next_voucher_no(inv.account_set_id, "记", period_name)
                v = await Voucher.create(
                    account_set_id=inv.account_set_id,
                    voucher_type="记",
                    voucher_no=vno,
                    period_name=period_name,
                    voucher_date=bill_date,
                    summary=f"销项发票 {inv.invoice_no} 收入确认",
                    total_debit=total_debit,
                    total_credit=total_credit,
                    status="draft",
                    creator=user,
                    source_type="invoice",
                    source_bill_id=inv.id,
                )
                line = 1
                # 借：应收账款
                await VoucherEntry.create(
                    voucher=v, line_no=line,
                    account_id=ar_acct.id,
                    summary=f"销项发票 {inv.invoice_no}",
                    debit_amount=inv.total_amount,
                    credit_amount=Decimal("0"),
                    aux_customer_id=inv.customer_id,
                )
                line += 1
                # 贷：主营业务收入
                await VoucherEntry.create(
                    voucher=v, line_no=line,
                    account_id=revenue_acct.id,
                    summary=f"销项发票 {inv.invoice_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=inv.amount_without_tax,
                )
                line += 1
                # 贷：应交税费-销项税
                await VoucherEntry.create(
                    voucher=v, line_no=line,
                    account_id=output_tax_acct.id,
                    summary=f"销项发票 {inv.invoice_no} 销项税",
                    debit_amount=Decimal("0"),
                    credit_amount=inv.tax_amount,
                )
                line += 1
                # 借：主营业务成本
                if cost_total > 0:
                    await VoucherEntry.create(
                        voucher=v, line_no=line,
                        account_id=cogs_acct.id,
                        summary=f"销售成本结转 {inv.invoice_no}",
                        debit_amount=cost_total,
                        credit_amount=Decimal("0"),
                    )
                    line += 1
                    # 贷：发出商品
                    await VoucherEntry.create(
                        voucher=v, line_no=line,
                        account_id=shipped_acct.id,
                        summary=f"销售成本结转 {inv.invoice_no}",
                        debit_amount=Decimal("0"),
                        credit_amount=cost_total,
                    )

                inv.voucher = v
                inv.voucher_no = vno
                await inv.save()

        # 进项发票：不生成凭证

    logger.info(f"确认发票: {inv.invoice_no}, 方向: {inv.direction}")
    return inv


async def cancel_invoice(invoice_id: int) -> Invoice:
    """作废发票"""
    inv = await Invoice.filter(id=invoice_id).first()
    if not inv:
        raise ValueError("发票不存在")
    if inv.status == "cancelled":
        raise ValueError("发票已作废")
    inv.status = "cancelled"
    await inv.save()
    logger.info(f"作废发票: {inv.invoice_no}")
    return inv
```

**验证：** `cd backend && python -c "from app.services.invoice_service import push_invoice_from_receivable, confirm_invoice; print('OK')"`

**提交：** `feat: 新增发票服务层 — 推送/创建/确认/作废 + 销项凭证生成`

---

## Task 7: 出库单路由 + 入库单路由

**文件：**
- 创建：`backend/app/routers/sales_delivery.py`
- 创建：`backend/app/routers/purchase_receipt.py`
- 修改：`backend/main.py`

**sales_delivery.py（4个端点）：**
- `GET /api/sales-delivery` — 列表（account_set_id, customer_id, order_id, 日期范围, 分页）
- `GET /api/sales-delivery/{id}` — 详情（含明细行 items）
- `GET /api/sales-delivery/{id}/pdf` — 单张PDF下载
- `POST /api/sales-delivery/batch-pdf` — 批量PDF下载

**purchase_receipt.py（4个端点）：**
- `GET /api/purchase-receipt` — 列表（account_set_id, supplier_id, purchase_order_id, 日期范围, 分页）
- `GET /api/purchase-receipt/{id}` — 详情（含明细行 items）
- `GET /api/purchase-receipt/{id}/pdf` — 单张PDF下载
- `POST /api/purchase-receipt/batch-pdf` — 批量PDF下载

**关键模式：** 参考 `receivables.py`，使用 `account_set_id: int = Query(...)` 必需参数、`require_permission("accounting_view")` 权限、分页响应 `{"items": [...], "total": N, "page": P, "page_size": S}`。

**PDF端点：** 返回 `StreamingResponse(content_type="application/pdf")`，调用 `pdf_print.py` 中的函数。PDF 功能在 Task 10 实现，此处先返回占位 404。

**main.py 追加：**
```python
# 导入行追加
sales_delivery, purchase_receipt,

# 注册
app.include_router(sales_delivery.router)
app.include_router(purchase_receipt.router)
```

**验证：** `cd backend && python -m pytest tests/ -v --ignore=tests/test_auth.py`

**提交：** `feat: 新增出库单/入库单路由 — 各4个端点`

---

## Task 8: 发票路由（7个端点）

**文件：**
- 创建：`backend/app/routers/invoices.py`
- 修改：`backend/main.py`

**端点（prefix `/api/invoices`）：**

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/` | accounting_view | 列表（筛选：account_set_id, direction, status, customer_id, supplier_id, 日期范围, 分页） |
| GET | `/{id}` | accounting_view | 详情（含明细行 items） |
| POST | `/from-receivable` | accounting_edit | 从应收单推送生成销项发票 |
| POST | `/` | accounting_edit | 手工创建进项发票 |
| PUT | `/{id}` | accounting_edit | 修改草稿发票（更新明细行：先删后建） |
| POST | `/{id}/confirm` | accounting_approve | 确认发票（销项生成凭证） |
| POST | `/{id}/cancel` | accounting_edit | 作废发票 |

**main.py 追加：**
```python
# 导入行追加
invoices,

# 注册
app.include_router(invoices.router)
```

**验证：** `cd backend && python -m pytest tests/ -v --ignore=tests/test_auth.py`

**提交：** `feat: 新增发票路由 — 7个端点`

---

## Task 9: 业务流程钩子

**文件：**
- 修改：`backend/app/routers/logistics.py`
- 修改：`backend/app/routers/purchase_orders.py`

**logistics.py — 发货完成 → 自动生成出库单（在现有应收单钩子之后追加）：**

插入位置：`logistics.py` 第443行（`except Exception as e: logger.warning(f"自动生成应收单失败: {e}")` 之后），仍在 `if order.shipping_status == "completed" and getattr(order, "account_set_id", None):` 块内。

```python
        # 钩子：发货完成 → 自动生成出库单
        try:
            from app.services.delivery_service import create_sales_delivery
            # 收集已发货的明细
            shipped_items = []
            for oi in all_items:
                if oi.shipped_qty > 0:
                    product = await Product.filter(id=oi.product_id).first()
                    shipped_items.append({
                        "order_item_id": oi.id,
                        "product_id": oi.product_id,
                        "product_name": product.name if product else str(oi.product_id),
                        "quantity": oi.shipped_qty,
                        "cost_price": str(oi.cost_price),
                        "sale_price": str(oi.unit_price),
                    })
            if shipped_items:
                await create_sales_delivery(
                    account_set_id=order.account_set_id,
                    customer_id=order.customer_id,
                    order_id=order.id,
                    warehouse_id=order.warehouse_id,
                    items=shipped_items,
                    creator=user,
                )
        except Exception as e:
            logger.warning(f"自动生成出库单失败: {e}")
```

**purchase_orders.py — 收货 → 自动生成入库单（在现有应付单钩子之后追加）：**

插入位置：`purchase_orders.py` 第557行（应付单钩子的 except 之后），仍在事务内。

```python
        # 钩子：采购收货 → 自动生成入库单
        if getattr(po, "account_set_id", None):
            try:
                from app.services.delivery_service import create_purchase_receipt
                from app.models.delivery import PurchaseReceiptBill as PRB
                prb_exists = await PRB.filter(
                    account_set_id=po.account_set_id, purchase_order_id=po.id
                ).exists()
                if not prb_exists:
                    receipt_items = []
                    received_pois = await PurchaseOrderItem.filter(
                        purchase_order_id=po.id, received_quantity__gt=0
                    ).select_related("product").all()
                    for poi in received_pois:
                        receipt_items.append({
                            "purchase_order_item_id": poi.id,
                            "product_id": poi.product_id,
                            "product_name": poi.product.name if poi.product else str(poi.product_id),
                            "quantity": poi.received_quantity,
                            "tax_inclusive_price": str(poi.tax_inclusive_price),
                            "tax_exclusive_price": str(poi.tax_exclusive_price),
                            "tax_rate": str(poi.tax_rate) if hasattr(poi, "tax_rate") else "13",
                        })
                    if receipt_items:
                        wh_id = po.target_warehouse_id
                        await create_purchase_receipt(
                            account_set_id=po.account_set_id,
                            supplier_id=po.supplier_id,
                            purchase_order_id=po.id,
                            warehouse_id=wh_id,
                            items=receipt_items,
                            creator=user,
                        )
            except Exception as e:
                from app.logger import get_logger as _gl
                _gl("purchase_orders").warning(f"自动生成入库单失败: {e}")
```

**验证：** `cd backend && python -m pytest tests/ -v --ignore=tests/test_auth.py`

**提交：** `feat: 业务钩子 — 发货→出库单 + 收货→入库单`

---

## Task 10: PDF 套打工具 + Docker/依赖

**文件：**
- 创建：`backend/app/utils/pdf_print.py`
- 修改：`backend/requirements.txt`
- 修改：`Dockerfile`

**requirements.txt 追加：**
```
reportlab==4.1.0
```

**Dockerfile — 在 `apt-get install` 行增加字体包：**

修改第26行，在 `postgresql-client-16 tzdata` 后追加 `fonts-wqy-zenhei`：
```
&& apt-get install -y --no-install-recommends postgresql-client-16 tzdata fonts-wqy-zenhei \
```

**pdf_print.py 完整代码：**

```python
"""PDF 套打工具 — 凭证 / 出库单 / 入库单（24cm × 14cm）"""
from __future__ import annotations

import io
import os
from decimal import Decimal
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app.logger import get_logger

logger = get_logger("pdf_print")

PAGE_W, PAGE_H = 24 * cm, 14 * cm

# 注册中文字体
_FONT_REGISTERED = False
FONT_NAME = "WenQuanYi"


def _ensure_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, fp))
                _FONT_REGISTERED = True
                return
            except Exception:
                continue
    # 回退到 Helvetica（无中文支持，但不报错）
    logger.warning("未找到中文字体，PDF 中文可能显示异常")


def _fmt(val) -> str:
    """格式化金额"""
    if val is None:
        return ""
    if isinstance(val, Decimal):
        return f"{val:,.2f}"
    return str(val)


def generate_voucher_pdf(voucher: dict, entries: list[dict]) -> bytes:
    """生成记账凭证 PDF"""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    font = FONT_NAME if _FONT_REGISTERED else "Helvetica"

    # 标题
    c.setFont(font, 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.2 * cm, "记 账 凭 证")

    # 凭证信息行
    c.setFont(font, 9)
    c.drawString(1 * cm, PAGE_H - 2 * cm, f"凭证字号: {voucher.get('voucher_no', '')}")
    c.drawString(10 * cm, PAGE_H - 2 * cm, f"日期: {voucher.get('voucher_date', '')}")
    c.drawString(18 * cm, PAGE_H - 2 * cm, f"附件: {voucher.get('attachment_count', 0)} 张")

    # 表头
    y = PAGE_H - 2.8 * cm
    headers = [("摘要", 1), ("科目", 6.5), ("借方金额", 13), ("贷方金额", 18)]
    c.setFont(font, 9)
    c.line(1 * cm, y + 0.3 * cm, 23 * cm, y + 0.3 * cm)
    for text, x in headers:
        c.drawString(x * cm, y, text)
    c.line(1 * cm, y - 0.2 * cm, 23 * cm, y - 0.2 * cm)

    # 分录行
    c.setFont(font, 8)
    row_y = y - 0.8 * cm
    for entry in entries:
        if row_y < 2 * cm:
            break
        c.drawString(1 * cm, row_y, str(entry.get("summary", ""))[:20])
        c.drawString(6.5 * cm, row_y, str(entry.get("account_name", "")))
        if entry.get("debit_amount") and Decimal(str(entry["debit_amount"])) > 0:
            c.drawRightString(16.5 * cm, row_y, _fmt(entry["debit_amount"]))
        if entry.get("credit_amount") and Decimal(str(entry["credit_amount"])) > 0:
            c.drawRightString(22 * cm, row_y, _fmt(entry["credit_amount"]))
        row_y -= 0.6 * cm

    # 合计行
    c.line(1 * cm, row_y + 0.3 * cm, 23 * cm, row_y + 0.3 * cm)
    c.setFont(font, 9)
    c.drawString(1 * cm, row_y, "合 计")
    c.drawRightString(16.5 * cm, row_y, _fmt(voucher.get("total_debit")))
    c.drawRightString(22 * cm, row_y, _fmt(voucher.get("total_credit")))
    c.line(1 * cm, row_y - 0.2 * cm, 23 * cm, row_y - 0.2 * cm)

    # 签章行
    footer_y = 1 * cm
    c.setFont(font, 8)
    c.drawString(1 * cm, footer_y, f"制单: {voucher.get('creator_name', '')}")
    c.drawString(8 * cm, footer_y, f"审核: {voucher.get('approved_by_name', '')}")
    c.drawString(15 * cm, footer_y, f"记账: {voucher.get('posted_by_name', '')}")

    c.save()
    return buf.getvalue()


def generate_delivery_pdf(bill: dict, items: list[dict], title: str = "销售出库单") -> bytes:
    """生成出库单/入库单 PDF"""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    font = FONT_NAME if _FONT_REGISTERED else "Helvetica"

    # 标题
    c.setFont(font, 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.2 * cm, title)

    # 信息行
    c.setFont(font, 9)
    c.drawString(1 * cm, PAGE_H - 2 * cm, f"单号: {bill.get('bill_no', '')}")
    c.drawString(8 * cm, PAGE_H - 2 * cm, f"日期: {bill.get('bill_date', '')}")
    partner_label = "客户" if "customer_name" in bill else "供应商"
    partner_name = bill.get("customer_name") or bill.get("supplier_name", "")
    c.drawString(15 * cm, PAGE_H - 2 * cm, f"{partner_label}: {partner_name}")

    # 表头
    y = PAGE_H - 2.8 * cm
    if title == "销售出库单":
        headers = [("商品名称", 1), ("数量", 10), ("成本单价", 13), ("销售单价", 17), ("成本小计", 20)]
    else:
        headers = [("商品名称", 1), ("数量", 10), ("含税单价", 13), ("不含税单价", 17), ("税率", 20.5)]
    c.setFont(font, 9)
    c.line(1 * cm, y + 0.3 * cm, 23 * cm, y + 0.3 * cm)
    for text, x in headers:
        c.drawString(x * cm, y, text)
    c.line(1 * cm, y - 0.2 * cm, 23 * cm, y - 0.2 * cm)

    # 明细行
    c.setFont(font, 8)
    row_y = y - 0.8 * cm
    for it in items:
        if row_y < 2 * cm:
            break
        c.drawString(1 * cm, row_y, str(it.get("product_name", ""))[:30])
        c.drawRightString(12 * cm, row_y, str(it.get("quantity", "")))
        if title == "销售出库单":
            c.drawRightString(16 * cm, row_y, _fmt(it.get("cost_price")))
            c.drawRightString(19.5 * cm, row_y, _fmt(it.get("sale_price")))
            cost_sub = Decimal(str(it.get("quantity", 0))) * Decimal(str(it.get("cost_price", 0)))
            c.drawRightString(22.5 * cm, row_y, _fmt(cost_sub.quantize(Decimal("0.01"))))
        else:
            c.drawRightString(16 * cm, row_y, _fmt(it.get("tax_inclusive_price")))
            c.drawRightString(19.5 * cm, row_y, _fmt(it.get("tax_exclusive_price")))
            c.drawRightString(22 * cm, row_y, f"{it.get('tax_rate', 13)}%")
        row_y -= 0.6 * cm

    # 合计行
    c.line(1 * cm, row_y + 0.3 * cm, 23 * cm, row_y + 0.3 * cm)
    c.setFont(font, 9)
    if title == "销售出库单":
        c.drawString(1 * cm, row_y, f"成本合计: {_fmt(bill.get('total_cost'))}    销售合计: {_fmt(bill.get('total_amount'))}")
    else:
        c.drawString(1 * cm, row_y, f"含税合计: {_fmt(bill.get('total_amount'))}    不含税: {_fmt(bill.get('total_amount_without_tax'))}    税额: {_fmt(bill.get('total_tax'))}")

    # 签章
    footer_y = 1 * cm
    c.setFont(font, 8)
    c.drawString(1 * cm, footer_y, f"制单: {bill.get('creator_name', '')}")
    c.drawString(12 * cm, footer_y, f"凭证号: {bill.get('voucher_no', '')}")

    c.save()
    return buf.getvalue()


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    """合并多个 PDF 为一个"""
    from reportlab.lib.utils import ImageReader
    # 使用 reportlab 原生方式：每个 PDF 独立生成，简单拼接
    # 实际使用 PyPDF2 或 pikepdf 更好，但为减少依赖用简单方案
    if len(pdf_bytes_list) == 1:
        return pdf_bytes_list[0]
    # 简单拼接：每个 PDF 已是完整文件，用 io 拼接
    from io import BytesIO
    try:
        from PyPDF2 import PdfMerger
        merger = PdfMerger()
        for pdf in pdf_bytes_list:
            merger.append(BytesIO(pdf))
        output = BytesIO()
        merger.write(output)
        return output.getvalue()
    except ImportError:
        # 没有 PyPDF2 则返回第一个
        return pdf_bytes_list[0]
```

**requirements.txt 最终：**
```
reportlab==4.1.0
```
追加到末尾。

**验证：** `cd backend && pip install reportlab==4.1.0 && python -c "from app.utils.pdf_print import generate_voucher_pdf, generate_delivery_pdf; print('OK')"`

**提交：** `feat: PDF套打工具 + reportlab依赖 + Docker中文字体`

---

## Task 11: 凭证/出库/入库 PDF 端点实现

**文件：**
- 修改：`backend/app/routers/vouchers.py`（新增凭证PDF端点）
- 修改：`backend/app/routers/sales_delivery.py`（实现PDF端点）
- 修改：`backend/app/routers/purchase_receipt.py`（实现PDF端点）

**vouchers.py 追加2个端点：**
- `GET /api/vouchers/{id}/pdf` — 单张凭证PDF
- `POST /api/vouchers/batch-pdf` — 批量凭证PDF（请求体 `{"ids": [1,2,3]}`）

**sales_delivery.py / purchase_receipt.py — 实现 PDF 端点：**
- 从 DB 查询单据+明细，组装 dict，调用 `generate_delivery_pdf()`
- 返回 `StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={bill_no}.pdf"})`
- 批量：遍历 ids，每张生成 PDF，用 `merge_pdfs()` 合并

**验证：** `cd backend && python -m pytest tests/ -v --ignore=tests/test_auth.py`

**提交：** `feat: 凭证/出库单/入库单 PDF 下载端点`

---

## Task 12: 后端测试 — 模型 + 服务

**文件：**
- 创建：`backend/tests/test_phase4_models.py`
- 创建：`backend/tests/test_phase4_service.py`

**test_phase4_models.py（8个用例）：**
1. SalesDeliveryBill CRUD
2. SalesDeliveryItem CRUD
3. PurchaseReceiptBill CRUD
4. PurchaseReceiptItem CRUD
5. Invoice CRUD（销项）
6. Invoice CRUD（进项）
7. InvoiceItem CRUD
8. bill_no 唯一约束

**test_phase4_service.py（10个用例）：**
1. 创建出库单 + 验证凭证（借发出商品/贷库存）
2. 创建入库单 + 验证凭证（借库存+借进项税/贷应付）
3. 从应收单推送生成销项发票
4. 创建进项发票
5. 确认销项发票 + 验证复合凭证（5条分录）
6. 确认进项发票不生成凭证
7. 作废发票
8. 修改草稿发票
9. 重复确认发票报错
10. 出库单成本计算准确性

**测试数据 `_setup()` 需预创建：** AccountSet + ChartOfAccount（1002/1122/1405/1407/2202/6001/6401/222101/222102）+ AccountingPeriod + Customer + Supplier + User + Product + Order + OrderItem

**验证：** `cd backend && python -m pytest tests/test_phase4_models.py tests/test_phase4_service.py -v`

**提交：** `test: 阶段4模型+服务测试 — 18个用例`

---

## Task 13: 前端 API + 发票面板

**文件：**
- 修改：`frontend/src/api/accounting.js`（追加~20个API函数）
- 创建：`frontend/src/components/business/InvoicePanel.vue`
- 创建：`frontend/src/components/business/SalesInvoiceTab.vue`
- 创建：`frontend/src/components/business/PurchaseInvoiceTab.vue`

**accounting.js 新增函数（按命名模式）：**

```javascript
// ========== 出入库单 ==========
export const getSalesDeliveries = (params) => api.get('/sales-delivery', { params })
export const getSalesDelivery = (id) => api.get(`/sales-delivery/${id}`)
export const getSalesDeliveryPdf = (id) => api.get(`/sales-delivery/${id}/pdf`, { responseType: 'blob' })
export const batchSalesDeliveryPdf = (ids) => api.post('/sales-delivery/batch-pdf', { ids }, { responseType: 'blob' })

export const getPurchaseReceipts = (params) => api.get('/purchase-receipt', { params })
export const getPurchaseReceipt = (id) => api.get(`/purchase-receipt/${id}`)
export const getPurchaseReceiptPdf = (id) => api.get(`/purchase-receipt/${id}/pdf`, { responseType: 'blob' })
export const batchPurchaseReceiptPdf = (ids) => api.post('/purchase-receipt/batch-pdf', { ids }, { responseType: 'blob' })

// ========== 发票管理 ==========
export const getInvoices = (params) => api.get('/invoices', { params })
export const getInvoice = (id) => api.get(`/invoices/${id}`)
export const pushInvoiceFromReceivable = (data) => api.post('/invoices/from-receivable', data)
export const createInputInvoice = (data) => api.post('/invoices', data)
export const updateInvoice = (id, data) => api.put(`/invoices/${id}`, data)
export const confirmInvoice = (id) => api.post(`/invoices/${id}/confirm`)
export const cancelInvoice = (id) => api.post(`/invoices/${id}/cancel`)

// ========== 凭证 PDF ==========
export const getVoucherPdf = (id) => api.get(`/vouchers/${id}/pdf`, { responseType: 'blob' })
export const batchVoucherPdf = (ids) => api.post('/vouchers/batch-pdf', { ids }, { responseType: 'blob' })
```

**InvoicePanel.vue** — 容器组件，2个子Tab：销项发票/进项发票

**SalesInvoiceTab.vue** — 销项发票列表 + 从应收单推送弹窗 + 确认/作废操作
- 筛选：状态(draft/confirmed/cancelled) + 客户 + 日期范围
- 表格列：发票号/日期/客户/类型(专票/普票)/不含税金额/税额/价税合计/状态/凭证号/操作
- 推送弹窗：选择应收单 → 自动填充明细行（从OrderItem获取产品+数量+单价）→ 用户可修改税率 → 确认推送

**PurchaseInvoiceTab.vue** — 进项发票列表 + 手工录入弹窗
- 筛选：状态 + 供应商 + 日期范围
- 表格列：发票号/日期/供应商/类型/不含税金额/税额/价税合计/状态/操作
- 录入弹窗：选择供应商 + 可选关联应付单 + 手动添加明细行

**验证：** `cd frontend && npx vite build`

**提交：** `feat: 前端发票管理 — API层 + InvoicePanel + 销项/进项Tab`

---

## Task 14: 前端出入库Tab + AccountingView注册

**文件：**
- 创建：`frontend/src/components/business/SalesDeliveryTab.vue`
- 创建：`frontend/src/components/business/PurchaseReceiptTab.vue`
- 修改：`frontend/src/views/AccountingView.vue`

**SalesDeliveryTab.vue** — 出库单列表（只读）
- 筛选：客户 + 日期范围
- 表格列：单号/日期/客户/仓库/成本合计/销售合计/凭证号/操作(PDF下载)
- 操作：单张PDF下载 + 批量PDF下载

**PurchaseReceiptTab.vue** — 入库单列表（只读）
- 筛选：供应商 + 日期范围
- 表格列：单号/日期/供应商/仓库/含税合计/不含税/税额/凭证号/操作(PDF下载)

**AccountingView.vue 变更：**
1. import InvoicePanel, SalesDeliveryTab, PurchaseReceiptTab
2. Tab 导航新增：「发票管理」
3. 应收管理面板（ReceivablePanel）内新增子Tab「出库单」→ SalesDeliveryTab
4. 应付管理面板（PayablePanel）内新增子Tab「入库单」→ PurchaseReceiptTab
5. `<InvoicePanel v-if="tab === 'invoices'" />`
6. VoucherPanel 凭证列表行增加「打印」按钮（调用 getVoucherPdf）

**验证：** `cd frontend && npx vite build`

**提交：** `feat: 出入库Tab + AccountingView注册发票/出入库`

---

## 验证清单

```bash
# 后端全量测试
cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/ -v --ignore=tests/test_auth.py

# 前端构建
cd /Users/lin/Desktop/erp-4/frontend && npx vite build

# Docker 构建部署
cd /Users/lin/Desktop/erp-4 && docker compose build && docker compose up -d
```

**手动集成测试：**
1. CREDIT 订单 → 全部发货 → 自动生成应收单 + 出库单（+凭证：借发出商品/贷库存）
2. 从应收单推送 → 生成销项发票草稿 → 确认 → 生成复合凭证（5条分录）
3. 采购收货 → 自动生成应付单 + 入库单（+凭证：借库存+借进项税/贷应付）
4. 手工录入进项发票 → 确认 → 不生成凭证
5. 出库单/入库单 PDF 下载 → 24×14cm，中文正常
6. 凭证 PDF 下载 → 分录正确，合计正确
7. 批量 PDF → 多张合并为一个文件
