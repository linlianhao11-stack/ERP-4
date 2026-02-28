"""阶段4模型CRUD测试 — 出入库单 + 发票"""
import pytest
from decimal import Decimal
from datetime import date
from tortoise.exceptions import IntegrityError
from app.models.accounting import AccountSet
from app.models import Customer, Supplier, Product
from app.models.delivery import SalesDeliveryBill, SalesDeliveryItem, PurchaseReceiptBill, PurchaseReceiptItem
from app.models.invoice import Invoice, InvoiceItem


async def _create_base():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-02"
    )
    c = await Customer.create(name="测试客户")
    s = await Supplier.create(name="测试供应商")
    p = await Product.create(sku="P001", name="测试商品", retail_price=Decimal("100.00"),
                             cost_price=Decimal("60.00"), tax_rate=Decimal("13"))
    return a, c, s, p


async def test_sales_delivery_bill_crud():
    a, c, _, p = await _create_base()
    bill = await SalesDeliveryBill.create(
        bill_no="CK0001", account_set=a, customer=c,
        bill_date=date(2026, 2, 15),
        total_cost=Decimal("600.00"), total_amount=Decimal("1000.00"),
        status="confirmed",
    )
    assert bill.id is not None
    assert bill.bill_no == "CK0001"
    assert bill.total_cost == Decimal("600.00")
    assert bill.total_amount == Decimal("1000.00")
    assert bill.status == "confirmed"


async def test_sales_delivery_item_crud():
    a, c, _, p = await _create_base()
    bill = await SalesDeliveryBill.create(
        bill_no="CK0002", account_set=a, customer=c,
        bill_date=date(2026, 2, 15),
        total_cost=Decimal("120.00"), total_amount=Decimal("200.00"),
    )
    item = await SalesDeliveryItem.create(
        delivery_bill=bill, product=p,
        product_name="测试商品", quantity=2,
        cost_price=Decimal("60.00"), sale_price=Decimal("100.00"),
    )
    assert item.id is not None
    assert item.quantity == 2
    assert item.cost_price == Decimal("60.00")
    assert item.sale_price == Decimal("100.00")


async def test_purchase_receipt_bill_crud():
    a, _, s, p = await _create_base()
    bill = await PurchaseReceiptBill.create(
        bill_no="RK0001", account_set=a, supplier=s,
        bill_date=date(2026, 2, 16),
        total_amount=Decimal("1130.00"),
        total_amount_without_tax=Decimal("1000.00"),
        total_tax=Decimal("130.00"),
        status="confirmed",
    )
    assert bill.id is not None
    assert bill.bill_no == "RK0001"
    assert bill.total_amount == Decimal("1130.00")
    assert bill.total_amount_without_tax == Decimal("1000.00")
    assert bill.total_tax == Decimal("130.00")


async def test_purchase_receipt_item_crud():
    a, _, s, p = await _create_base()
    bill = await PurchaseReceiptBill.create(
        bill_no="RK0002", account_set=a, supplier=s,
        bill_date=date(2026, 2, 16),
        total_amount=Decimal("1130.00"),
        total_amount_without_tax=Decimal("1000.00"),
        total_tax=Decimal("130.00"),
    )
    item = await PurchaseReceiptItem.create(
        receipt_bill=bill, product=p,
        product_name="测试商品", quantity=10,
        tax_inclusive_price=Decimal("113.00"),
        tax_exclusive_price=Decimal("100.00"),
        tax_rate=Decimal("13"),
    )
    assert item.id is not None
    assert item.quantity == 10
    assert item.tax_inclusive_price == Decimal("113.00")
    assert item.tax_exclusive_price == Decimal("100.00")


async def test_invoice_output_crud():
    a, c, _, p = await _create_base()
    inv = await Invoice.create(
        invoice_no="XS0001", invoice_type="special", direction="output",
        account_set=a, customer=c,
        invoice_date=date(2026, 2, 17),
        total_amount=Decimal("1130.00"),
        amount_without_tax=Decimal("1000.00"),
        tax_amount=Decimal("130.00"),
        status="draft",
    )
    assert inv.id is not None
    assert inv.direction == "output"
    assert inv.invoice_type == "special"
    assert inv.status == "draft"
    assert inv.total_amount == Decimal("1130.00")


async def test_invoice_input_crud():
    a, _, s, p = await _create_base()
    inv = await Invoice.create(
        invoice_no="JX0001", invoice_type="normal", direction="input",
        account_set=a, supplier=s,
        invoice_date=date(2026, 2, 17),
        total_amount=Decimal("5650.00"),
        amount_without_tax=Decimal("5000.00"),
        tax_amount=Decimal("650.00"),
        status="draft",
    )
    assert inv.id is not None
    assert inv.direction == "input"
    assert inv.invoice_type == "normal"
    assert inv.total_amount == Decimal("5650.00")
    assert inv.amount_without_tax == Decimal("5000.00")
    assert inv.tax_amount == Decimal("650.00")


async def test_invoice_item_crud():
    a, c, _, p = await _create_base()
    inv = await Invoice.create(
        invoice_no="XS0002", invoice_type="special", direction="output",
        account_set=a, customer=c,
        invoice_date=date(2026, 2, 17),
        total_amount=Decimal("1130.00"),
        amount_without_tax=Decimal("1000.00"),
        tax_amount=Decimal("130.00"),
    )
    item = await InvoiceItem.create(
        invoice=inv, product=p,
        product_name="测试商品", quantity=10,
        unit_price=Decimal("100.00"), tax_rate=Decimal("13"),
        tax_amount=Decimal("130.00"),
        amount_without_tax=Decimal("1000.00"),
        amount=Decimal("1130.00"),
    )
    assert item.id is not None
    assert item.quantity == 10
    assert item.unit_price == Decimal("100.00")
    assert item.tax_amount == Decimal("130.00")
    assert item.amount == Decimal("1130.00")


async def test_bill_no_unique():
    a, c, _, _ = await _create_base()
    await SalesDeliveryBill.create(
        bill_no="CK_UNIQUE", account_set=a, customer=c,
        bill_date=date(2026, 2, 15),
        total_cost=Decimal("100.00"), total_amount=Decimal("200.00"),
    )
    with pytest.raises(IntegrityError):
        await SalesDeliveryBill.create(
            bill_no="CK_UNIQUE", account_set=a, customer=c,
            bill_date=date(2026, 2, 16),
            total_cost=Decimal("200.00"), total_amount=Decimal("400.00"),
        )
