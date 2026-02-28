"""阶段4服务层测试 — 出入库单服务 + 发票服务"""
import pytest
from decimal import Decimal
from datetime import date
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models import Customer, Supplier, User, Product, Order, OrderItem
from app.models.ar_ap import ReceivableBill
from app.models.delivery import SalesDeliveryBill, SalesDeliveryItem
from app.models.voucher import Voucher, VoucherEntry
from app.models.invoice import Invoice, InvoiceItem
from app.services.delivery_service import create_sales_delivery, create_purchase_receipt
from app.services.invoice_service import push_invoice_from_receivable, create_input_invoice, confirm_invoice, cancel_invoice


async def _setup():
    """创建基础数据：账套 + 科目 + 期间 + 客户 + 供应商 + 用户 + 产品 + 订单"""
    a = await AccountSet.create(
        code="TEST", name="测试账套", company_name="测试公司",
        start_year=2026, start_month=1, current_period="2026-02"
    )
    # 预置必要科目
    acct_defs = [
        ("1002", "银行存款", "asset", "debit", False, False),
        ("1122", "应收账款", "asset", "debit", True, False),
        ("1405", "库存商品", "asset", "debit", False, False),
        ("1407", "发出商品", "asset", "debit", False, False),
        ("2202", "应付账款", "liability", "credit", False, True),
        ("6001", "主营业务收入", "profit_loss", "credit", False, False),
        ("6401", "主营业务成本", "profit_loss", "debit", False, False),
        ("222101", "应交增值税-进项税额", "liability", "debit", False, False),
        ("222102", "应交增值税-销项税额", "liability", "credit", False, False),
    ]
    for code, name, cat, direction, aux_c, aux_s in acct_defs:
        await ChartOfAccount.create(
            account_set=a, code=code, name=name,
            level=1, category=cat, direction=direction,
            is_leaf=True, is_active=True,
            aux_customer=aux_c, aux_supplier=aux_s,
        )

    await AccountingPeriod.create(
        account_set=a, period_name="2026-02", year=2026, month=2
    )
    c = await Customer.create(name="测试客户")
    s = await Supplier.create(name="测试供应商")
    u = await User.create(username="testuser", password_hash="x", display_name="测试")
    p = await Product.create(
        sku="TP001", name="测试产品", retail_price=Decimal("100.00"),
        cost_price=Decimal("60.00"), tax_rate=Decimal("13"),
    )
    # 订单（用于应收单关联）
    order = await Order.create(
        order_no="SO20260201001", order_type="sales", customer=c,
        total_amount=Decimal("1000.00"), total_cost=Decimal("600.00"),
        total_profit=Decimal("400.00"), account_set=a,
    )
    oi = await OrderItem.create(
        order=order, product=p, quantity=10,
        unit_price=Decimal("100.00"), cost_price=Decimal("60.00"),
        amount=Decimal("1000.00"), profit=Decimal("400.00"),
    )
    return a, c, s, u, p, order, oi


async def test_create_sales_delivery_with_voucher():
    a, c, s, u, p, order, oi = await _setup()
    bill = await create_sales_delivery(
        account_set_id=a.id, customer_id=c.id,
        order_id=order.id, warehouse_id=None,
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 10, "cost_price": "60.00", "sale_price": "100.00",
        }],
        creator=u, bill_date=date(2026, 2, 15),
    )
    assert bill.id is not None
    assert bill.bill_no.startswith("CK")
    assert bill.total_cost == Decimal("600.00")
    assert bill.total_amount == Decimal("1000.00")

    # 验证凭证
    assert bill.voucher_no is not None
    v = await Voucher.filter(id=bill.voucher_id).first()
    assert v is not None
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").all()
    assert len(entries) == 2
    assert entries[0].debit_amount == Decimal("600.00")   # 借 发出商品1407
    assert entries[1].credit_amount == Decimal("600.00")  # 贷 库存商品1405


async def test_create_purchase_receipt_with_voucher():
    a, c, s, u, p, order, oi = await _setup()
    bill = await create_purchase_receipt(
        account_set_id=a.id, supplier_id=s.id,
        purchase_order_id=None, warehouse_id=None,
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 10, "tax_inclusive_price": "113.00",
            "tax_exclusive_price": "100.00", "tax_rate": "13",
        }],
        creator=u, bill_date=date(2026, 2, 16),
    )
    assert bill.id is not None
    assert bill.bill_no.startswith("RK")
    assert bill.total_amount == Decimal("1130.00")
    assert bill.total_amount_without_tax == Decimal("1000.00")
    assert bill.total_tax == Decimal("130.00")

    # 验证凭证
    assert bill.voucher_no is not None
    v = await Voucher.filter(id=bill.voucher_id).first()
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").all()
    assert len(entries) == 3
    assert entries[0].debit_amount == Decimal("1000.00")   # 借 库存商品1405
    assert entries[1].debit_amount == Decimal("130.00")    # 借 进项税222101
    assert entries[2].credit_amount == Decimal("1130.00")  # 贷 应付账款2202


async def test_push_invoice_from_receivable():
    a, c, s, u, p, order, oi = await _setup()
    # 先创建应收单
    rb = await ReceivableBill.create(
        bill_no="YS_INV01", account_set=a, customer=c, order=order,
        bill_date=date(2026, 2, 15), total_amount=Decimal("1130.00"),
        received_amount=Decimal("0"), unreceived_amount=Decimal("1130.00"),
        status="pending",
    )
    # 从应收单推送发票
    inv = await push_invoice_from_receivable(
        account_set_id=a.id, receivable_bill_id=rb.id,
        invoice_type="special",
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 10, "unit_price": "100.00", "tax_rate": "13",
        }],
        creator=u, invoice_date=date(2026, 2, 17),
    )
    assert inv.id is not None
    assert inv.direction == "output"
    assert inv.status == "draft"
    assert inv.total_amount == Decimal("1130.00")
    assert inv.amount_without_tax == Decimal("1000.00")
    assert inv.tax_amount == Decimal("130.00")

    # 验证明细行
    items = await InvoiceItem.filter(invoice=inv).all()
    assert len(items) == 1
    assert items[0].quantity == 10
    assert items[0].amount == Decimal("1130.00")


async def test_create_input_invoice():
    a, c, s, u, p, order, oi = await _setup()
    inv = await create_input_invoice(
        account_set_id=a.id, supplier_id=s.id,
        invoice_type="special",
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 5, "unit_price": "200.00", "tax_rate": "13",
        }],
        creator=u, invoice_date=date(2026, 2, 18),
    )
    assert inv.id is not None
    assert inv.direction == "input"
    assert inv.status == "draft"
    assert inv.amount_without_tax == Decimal("1000.00")
    assert inv.tax_amount == Decimal("130.00")
    assert inv.total_amount == Decimal("1130.00")

    items = await InvoiceItem.filter(invoice=inv).all()
    assert len(items) == 1
    assert items[0].quantity == 5


async def test_confirm_output_invoice_voucher():
    a, c, s, u, p, order, oi = await _setup()
    # 先创建出库单（提供成本数据）
    delivery = await create_sales_delivery(
        account_set_id=a.id, customer_id=c.id,
        order_id=order.id, warehouse_id=None,
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 10, "cost_price": "60.00", "sale_price": "100.00",
        }],
        creator=u, bill_date=date(2026, 2, 15),
    )
    # 创建应收单（关联订单）
    rb = await ReceivableBill.create(
        bill_no="YS_CONF01", account_set=a, customer=c, order=order,
        bill_date=date(2026, 2, 15), total_amount=Decimal("1130.00"),
        received_amount=Decimal("0"), unreceived_amount=Decimal("1130.00"),
        status="pending",
    )
    # 推送发票
    inv = await push_invoice_from_receivable(
        account_set_id=a.id, receivable_bill_id=rb.id,
        invoice_type="special",
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 10, "unit_price": "100.00", "tax_rate": "13",
        }],
        creator=u, invoice_date=date(2026, 2, 17),
    )
    # 确认发票 → 生成复合凭证
    confirmed = await confirm_invoice(inv.id, u)
    assert confirmed.status == "confirmed"
    assert confirmed.voucher_no is not None

    v = await Voucher.filter(id=confirmed.voucher_id).first()
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").all()
    assert len(entries) == 5
    # 借 应收账款1122 1130
    assert entries[0].debit_amount == Decimal("1130.00")
    # 贷 主营业务收入6001 1000
    assert entries[1].credit_amount == Decimal("1000.00")
    # 贷 销项税222102 130
    assert entries[2].credit_amount == Decimal("130.00")
    # 借 主营业务成本6401 600
    assert entries[3].debit_amount == Decimal("600.00")
    # 贷 发出商品1407 600
    assert entries[4].credit_amount == Decimal("600.00")


async def test_confirm_input_invoice_no_voucher():
    a, c, s, u, p, order, oi = await _setup()
    inv = await create_input_invoice(
        account_set_id=a.id, supplier_id=s.id,
        invoice_type="special",
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 5, "unit_price": "200.00", "tax_rate": "13",
        }],
        creator=u, invoice_date=date(2026, 2, 18),
    )
    confirmed = await confirm_invoice(inv.id, u)
    assert confirmed.status == "confirmed"
    # 进项发票确认不生成凭证
    assert confirmed.voucher_no is None


async def test_cancel_invoice():
    a, c, s, u, p, order, oi = await _setup()
    inv = await create_input_invoice(
        account_set_id=a.id, supplier_id=s.id,
        invoice_type="normal",
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 3, "unit_price": "50.00", "tax_rate": "13",
        }],
        creator=u, invoice_date=date(2026, 2, 19),
    )
    cancelled = await cancel_invoice(inv.id)
    assert cancelled.status == "cancelled"


async def test_cannot_confirm_non_draft():
    a, c, s, u, p, order, oi = await _setup()
    inv = await create_input_invoice(
        account_set_id=a.id, supplier_id=s.id,
        invoice_type="special",
        items=[{
            "product_id": p.id, "product_name": "测试产品",
            "quantity": 1, "unit_price": "100.00", "tax_rate": "13",
        }],
        creator=u, invoice_date=date(2026, 2, 20),
    )
    await confirm_invoice(inv.id, u)
    with pytest.raises(ValueError, match="只有草稿状态的发票可以确认"):
        await confirm_invoice(inv.id, u)


async def test_delivery_cost_accuracy():
    a, c, s, u, p, order, oi = await _setup()
    bill = await create_sales_delivery(
        account_set_id=a.id, customer_id=c.id,
        order_id=None, warehouse_id=None,
        items=[
            {"product_id": p.id, "product_name": "产品A", "quantity": 5, "cost_price": "30.50", "sale_price": "50.00"},
            {"product_id": p.id, "product_name": "产品B", "quantity": 3, "cost_price": "45.20", "sale_price": "80.00"},
        ],
        creator=u, bill_date=date(2026, 2, 21),
    )
    # 5*30.50 + 3*45.20 = 152.50 + 135.60 = 288.10
    assert bill.total_cost == Decimal("288.10")
    # 5*50.00 + 3*80.00 = 250.00 + 240.00 = 490.00
    assert bill.total_amount == Decimal("490.00")


async def test_receipt_tax_calculation():
    a, c, s, u, p, order, oi = await _setup()
    bill = await create_purchase_receipt(
        account_set_id=a.id, supplier_id=s.id,
        purchase_order_id=None, warehouse_id=None,
        items=[
            {
                "product_id": p.id, "product_name": "产品A",
                "quantity": 10, "tax_inclusive_price": "113.00",
                "tax_exclusive_price": "100.00", "tax_rate": "13",
            },
            {
                "product_id": p.id, "product_name": "产品B",
                "quantity": 5, "tax_inclusive_price": "226.00",
                "tax_exclusive_price": "200.00", "tax_rate": "13",
            },
        ],
        creator=u, bill_date=date(2026, 2, 22),
    )
    # 10*113=1130, 5*226=1130 → total_amount=2260
    assert bill.total_amount == Decimal("2260.00")
    # 10*100=1000, 5*200=1000 → total_without_tax=2000
    assert bill.total_amount_without_tax == Decimal("2000.00")
    # total_tax = 2260 - 2000 = 260
    assert bill.total_tax == Decimal("260.00")
