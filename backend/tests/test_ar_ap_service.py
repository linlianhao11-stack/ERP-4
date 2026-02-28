"""应收应付服务层测试"""
from decimal import Decimal
from datetime import date
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models import Customer, Supplier, User
from app.models.ar_ap import ReceivableBill, ReceiptBill, PayableBill, DisbursementBill
from app.models.voucher import Voucher, VoucherEntry
from app.services.ar_service import (
    create_receivable_bill, create_receipt_bill_for_payment,
    confirm_receipt_bill, confirm_write_off, generate_ar_vouchers,
)
from app.services.ap_service import (
    create_payable_bill, create_disbursement_for_po_payment,
    confirm_disbursement_bill, generate_ap_vouchers,
)


async def _setup():
    """创建基础数据：账套 + 科目 + 期间 + 客户 + 供应商 + 用户"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    # 预置必要科目
    await ChartOfAccount.create(
        account_set=a, code="1002", name="银行存款",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    await ChartOfAccount.create(
        account_set=a, code="1122", name="应收账款",
        level=1, category="asset", direction="debit", is_leaf=True, aux_customer=True
    )
    await ChartOfAccount.create(
        account_set=a, code="2202", name="应付账款",
        level=1, category="liability", direction="credit", is_leaf=True, aux_supplier=True
    )
    await ChartOfAccount.create(
        account_set=a, code="2203", name="预收账款",
        level=1, category="liability", direction="credit", is_leaf=True, aux_customer=True
    )
    await AccountingPeriod.create(
        account_set=a, period_name="2026-02", year=2026, month=2
    )
    c = await Customer.create(name="测试客户")
    s = await Supplier.create(name="测试供应商")
    u = await User.create(username="testuser", password_hash="x", display_name="测试")
    return a, c, s, u


async def test_create_receivable_pending():
    a, c, _, u = await _setup()
    rb = await create_receivable_bill(
        account_set_id=a.id, customer_id=c.id,
        total_amount=Decimal("1000.00"), status="pending", creator=u,
    )
    assert rb.bill_no.startswith("YS")
    assert rb.status == "pending"
    assert rb.received_amount == Decimal("0")
    assert rb.unreceived_amount == Decimal("1000.00")


async def test_create_receivable_completed():
    a, c, _, u = await _setup()
    rb = await create_receivable_bill(
        account_set_id=a.id, customer_id=c.id,
        total_amount=Decimal("2000.00"), status="completed", creator=u,
    )
    assert rb.status == "completed"
    assert rb.received_amount == Decimal("2000.00")
    assert rb.unreceived_amount == Decimal("0")


async def test_create_receivable_negative():
    a, c, _, u = await _setup()
    rb = await create_receivable_bill(
        account_set_id=a.id, customer_id=c.id,
        total_amount=Decimal("-500.00"), status="completed", creator=u,
    )
    assert rb.total_amount == Decimal("-500.00")
    assert rb.received_amount == Decimal("-500.00")


async def test_confirm_receipt_partial():
    a, c, _, u = await _setup()
    rb = await create_receivable_bill(
        account_set_id=a.id, customer_id=c.id,
        total_amount=Decimal("1000.00"), status="pending", creator=u,
    )
    receipt = await ReceiptBill.create(
        bill_no="SK_TEST1", account_set_id=a.id, customer_id=c.id,
        receivable_bill=rb, receipt_date=date(2026, 2, 5),
        amount=Decimal("400.00"), payment_method="银行转账",
        status="draft", creator=u,
    )
    result = await confirm_receipt_bill(receipt.id, u)
    assert result.status == "confirmed"

    await rb.refresh_from_db()
    assert rb.received_amount == Decimal("400.00")
    assert rb.unreceived_amount == Decimal("600.00")
    assert rb.status == "partial"


async def test_confirm_receipt_full():
    a, c, _, u = await _setup()
    rb = await create_receivable_bill(
        account_set_id=a.id, customer_id=c.id,
        total_amount=Decimal("1000.00"), status="pending", creator=u,
    )
    receipt = await ReceiptBill.create(
        bill_no="SK_TEST2", account_set_id=a.id, customer_id=c.id,
        receivable_bill=rb, receipt_date=date(2026, 2, 5),
        amount=Decimal("1000.00"), payment_method="银行转账",
        status="draft", creator=u,
    )
    await confirm_receipt_bill(receipt.id, u)

    await rb.refresh_from_db()
    assert rb.received_amount == Decimal("1000.00")
    assert rb.unreceived_amount == Decimal("0")
    assert rb.status == "completed"


async def test_create_payable_and_confirm_disbursement():
    a, _, s, u = await _setup()
    pb = await create_payable_bill(
        account_set_id=a.id, supplier_id=s.id,
        total_amount=Decimal("5000.00"), status="pending", creator=u,
    )
    assert pb.bill_no.startswith("YF")
    assert pb.unpaid_amount == Decimal("5000.00")

    db = await DisbursementBill.create(
        bill_no="FK_TEST1", account_set_id=a.id, supplier_id=s.id,
        payable_bill=pb, disbursement_date=date(2026, 2, 10),
        amount=Decimal("3000.00"), disbursement_method="对公转账",
        status="draft", creator=u,
    )
    result = await confirm_disbursement_bill(db.id, u)
    assert result.status == "confirmed"

    await pb.refresh_from_db()
    assert pb.paid_amount == Decimal("3000.00")
    assert pb.unpaid_amount == Decimal("2000.00")
    assert pb.status == "partial"


async def test_confirm_disbursement_full():
    a, _, s, u = await _setup()
    pb = await create_payable_bill(
        account_set_id=a.id, supplier_id=s.id,
        total_amount=Decimal("2000.00"), status="pending", creator=u,
    )
    db = await DisbursementBill.create(
        bill_no="FK_TEST2", account_set_id=a.id, supplier_id=s.id,
        payable_bill=pb, disbursement_date=date(2026, 2, 10),
        amount=Decimal("2000.00"), disbursement_method="对公转账",
        status="draft", creator=u,
    )
    await confirm_disbursement_bill(db.id, u)
    await pb.refresh_from_db()
    assert pb.status == "completed"


async def test_generate_ar_vouchers():
    a, c, _, u = await _setup()
    rb = await create_receivable_bill(
        account_set_id=a.id, customer_id=c.id,
        total_amount=Decimal("1000.00"), status="completed", creator=u,
    )
    await create_receipt_bill_for_payment(
        account_set_id=a.id, customer_id=c.id,
        receivable_bill=rb, payment_id=None,
        amount=Decimal("1000.00"), payment_method="银行转账", creator=u,
    )
    vouchers = await generate_ar_vouchers(a.id, "2026-02", u)
    assert len(vouchers) == 1
    assert vouchers[0]["source"].startswith("收款单")

    # 验证分录
    v = await Voucher.filter(id=vouchers[0]["id"]).first()
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").all()
    assert len(entries) == 2
    assert entries[0].debit_amount == Decimal("1000.00")  # 借 银行存款
    assert entries[1].credit_amount == Decimal("1000.00")  # 贷 应收账款


async def test_generate_ap_vouchers():
    a, _, s, u = await _setup()
    pb = await create_payable_bill(
        account_set_id=a.id, supplier_id=s.id,
        total_amount=Decimal("5000.00"), status="pending", creator=u,
    )
    await create_disbursement_for_po_payment(
        account_set_id=a.id, supplier_id=s.id,
        payable_bill=pb, amount=Decimal("5000.00"),
        disbursement_method="对公转账", creator=u,
    )
    vouchers = await generate_ap_vouchers(a.id, "2026-02", u)
    assert len(vouchers) == 1
    assert vouchers[0]["source"].startswith("付款单")

    v = await Voucher.filter(id=vouchers[0]["id"]).first()
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").all()
    assert len(entries) == 2
    assert entries[0].debit_amount == Decimal("5000.00")  # 借 应付账款
    assert entries[1].credit_amount == Decimal("5000.00")  # 贷 银行存款


async def test_voucher_generation_idempotent():
    a, c, _, u = await _setup()
    rb = await create_receivable_bill(
        account_set_id=a.id, customer_id=c.id,
        total_amount=Decimal("500.00"), status="completed", creator=u,
    )
    await create_receipt_bill_for_payment(
        account_set_id=a.id, customer_id=c.id,
        receivable_bill=rb, payment_id=None,
        amount=Decimal("500.00"), payment_method="现金", creator=u,
    )
    v1 = await generate_ar_vouchers(a.id, "2026-02", u)
    v2 = await generate_ar_vouchers(a.id, "2026-02", u)
    assert len(v1) == 1
    assert len(v2) == 0  # 已生成凭证的不会重复生成
