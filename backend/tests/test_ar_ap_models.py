"""应收应付模型测试"""
import pytest
from decimal import Decimal
from datetime import date
from tortoise.exceptions import IntegrityError
from app.models.accounting import AccountSet
from app.models import Customer, Supplier, Order, Warehouse, PurchaseOrder
from app.models.ar_ap import (
    ReceivableBill, ReceiptBill, ReceiptRefundBill, ReceivableWriteOff,
    PayableBill, DisbursementBill, DisbursementRefundBill,
)


async def _create_base():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    c = await Customer.create(name="测试客户")
    s = await Supplier.create(name="测试供应商")
    return a, c, s


async def test_create_receivable_bill():
    a, c, _ = await _create_base()
    rb = await ReceivableBill.create(
        bill_no="YS0001", account_set=a, customer=c,
        bill_date=date(2026, 2, 1), total_amount=Decimal("1000.00"),
        received_amount=Decimal("0"), unreceived_amount=Decimal("1000.00"),
        status="pending",
    )
    assert rb.id is not None
    assert rb.status == "pending"
    assert rb.total_amount == Decimal("1000.00")


async def test_create_receipt_bill():
    a, c, _ = await _create_base()
    rb = await ReceivableBill.create(
        bill_no="YS0001", account_set=a, customer=c,
        bill_date=date(2026, 2, 1), total_amount=Decimal("1000.00"),
        received_amount=Decimal("0"), unreceived_amount=Decimal("1000.00"),
    )
    receipt = await ReceiptBill.create(
        bill_no="SK0001", account_set=a, customer=c,
        receivable_bill=rb, receipt_date=date(2026, 2, 2),
        amount=Decimal("500.00"), payment_method="银行转账",
    )
    assert receipt.id is not None
    assert receipt.status == "draft"
    assert receipt.is_advance is False


async def test_create_receipt_refund_bill():
    a, c, _ = await _create_base()
    receipt = await ReceiptBill.create(
        bill_no="SK0001", account_set=a, customer=c,
        receipt_date=date(2026, 2, 2),
        amount=Decimal("500.00"), payment_method="银行转账",
        status="confirmed",
    )
    refund = await ReceiptRefundBill.create(
        bill_no="SKTK0001", account_set=a, customer=c,
        original_receipt=receipt, refund_date=date(2026, 2, 3),
        amount=Decimal("200.00"), reason="部分退款",
    )
    assert refund.id is not None
    assert refund.status == "draft"


async def test_create_receivable_write_off():
    a, c, _ = await _create_base()
    rb = await ReceivableBill.create(
        bill_no="YS0001", account_set=a, customer=c,
        bill_date=date(2026, 2, 1), total_amount=Decimal("1000.00"),
        received_amount=Decimal("0"), unreceived_amount=Decimal("1000.00"),
    )
    advance = await ReceiptBill.create(
        bill_no="SK0001", account_set=a, customer=c,
        receipt_date=date(2026, 1, 15),
        amount=Decimal("1000.00"), payment_method="银行转账",
        is_advance=True, status="confirmed",
    )
    wo = await ReceivableWriteOff.create(
        bill_no="YSHX0001", account_set=a, customer=c,
        advance_receipt=advance, receivable_bill=rb,
        write_off_date=date(2026, 2, 5), amount=Decimal("500.00"),
    )
    assert wo.id is not None
    assert wo.status == "draft"


async def test_create_payable_bill():
    a, _, s = await _create_base()
    pb = await PayableBill.create(
        bill_no="YF0001", account_set=a, supplier=s,
        bill_date=date(2026, 2, 1), total_amount=Decimal("5000.00"),
        paid_amount=Decimal("0"), unpaid_amount=Decimal("5000.00"),
    )
    assert pb.id is not None
    assert pb.status == "pending"


async def test_create_disbursement_bill():
    a, _, s = await _create_base()
    pb = await PayableBill.create(
        bill_no="YF0001", account_set=a, supplier=s,
        bill_date=date(2026, 2, 1), total_amount=Decimal("5000.00"),
        paid_amount=Decimal("0"), unpaid_amount=Decimal("5000.00"),
    )
    db = await DisbursementBill.create(
        bill_no="FK0001", account_set=a, supplier=s,
        payable_bill=pb, disbursement_date=date(2026, 2, 5),
        amount=Decimal("2000.00"), disbursement_method="对公转账",
    )
    assert db.id is not None
    assert db.status == "draft"


async def test_create_disbursement_refund_bill():
    a, _, s = await _create_base()
    db = await DisbursementBill.create(
        bill_no="FK0001", account_set=a, supplier=s,
        disbursement_date=date(2026, 2, 5),
        amount=Decimal("2000.00"), disbursement_method="对公转账",
        status="confirmed",
    )
    refund = await DisbursementRefundBill.create(
        bill_no="FKTK0001", account_set=a, supplier=s,
        original_disbursement=db, refund_date=date(2026, 2, 10),
        amount=Decimal("500.00"), reason="部分退款",
    )
    assert refund.id is not None
    assert refund.status == "draft"


async def test_bill_no_unique_constraint():
    a, c, _ = await _create_base()
    await ReceivableBill.create(
        bill_no="YS_UNIQUE", account_set=a, customer=c,
        bill_date=date(2026, 2, 1), total_amount=Decimal("100.00"),
        received_amount=Decimal("0"), unreceived_amount=Decimal("100.00"),
    )
    with pytest.raises(IntegrityError):
        await ReceivableBill.create(
            bill_no="YS_UNIQUE", account_set=a, customer=c,
            bill_date=date(2026, 2, 2), total_amount=Decimal("200.00"),
            received_amount=Decimal("0"), unreceived_amount=Decimal("200.00"),
        )


async def test_negative_amount_red_bill():
    a, c, _ = await _create_base()
    rb = await ReceivableBill.create(
        bill_no="YS_RED", account_set=a, customer=c,
        bill_date=date(2026, 2, 1), total_amount=Decimal("-500.00"),
        received_amount=Decimal("-500.00"), unreceived_amount=Decimal("0"),
        status="completed",
    )
    assert rb.total_amount == Decimal("-500.00")
    assert rb.status == "completed"


async def test_payable_bill_no_unique():
    a, _, s = await _create_base()
    await PayableBill.create(
        bill_no="YF_UNIQUE", account_set=a, supplier=s,
        bill_date=date(2026, 2, 1), total_amount=Decimal("100.00"),
        paid_amount=Decimal("0"), unpaid_amount=Decimal("100.00"),
    )
    with pytest.raises(IntegrityError):
        await PayableBill.create(
            bill_no="YF_UNIQUE", account_set=a, supplier=s,
            bill_date=date(2026, 2, 2), total_amount=Decimal("200.00"),
            paid_amount=Decimal("0"), unpaid_amount=Decimal("200.00"),
        )
