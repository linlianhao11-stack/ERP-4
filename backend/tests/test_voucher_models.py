"""凭证模型测试"""
import pytest
from decimal import Decimal
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry


async def _setup_accounting():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    cash = await ChartOfAccount.create(
        account_set=a, code="1001", name="库存现金",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    bank = await ChartOfAccount.create(
        account_set=a, code="1002", name="银行存款",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    period = await AccountingPeriod.create(
        account_set=a, period_name="2026-01", year=2026, month=1
    )
    return a, cash, bank, period


async def test_create_voucher_with_entries():
    a, cash, bank, period = await _setup_accounting()
    v = await Voucher.create(
        account_set=a,
        voucher_type="记",
        voucher_no="QL-记-202601-001",
        period_name="2026-01",
        voucher_date="2026-01-15",
        total_debit=Decimal("1000.00"),
        total_credit=Decimal("1000.00"),
        status="draft",
        summary="提现"
    )
    assert v.id is not None
    assert v.status == "draft"

    e1 = await VoucherEntry.create(
        voucher=v, line_no=1, account=cash,
        summary="提现", debit_amount=Decimal("1000.00"),
        credit_amount=Decimal("0.00")
    )
    e2 = await VoucherEntry.create(
        voucher=v, line_no=2, account=bank,
        summary="提现", debit_amount=Decimal("0.00"),
        credit_amount=Decimal("1000.00")
    )
    assert e1.id is not None
    assert e2.credit_amount == Decimal("1000.00")


async def test_voucher_status_values():
    a, cash, bank, period = await _setup_accounting()
    for status in ["draft", "pending", "approved", "posted"]:
        v = await Voucher.create(
            account_set=a, voucher_type="记",
            voucher_no=f"QL-记-202601-{status}",
            period_name="2026-01", voucher_date="2026-01-15",
            total_debit=Decimal("100.00"), total_credit=Decimal("100.00"),
            status=status, summary="测试"
        )
        assert v.status == status
