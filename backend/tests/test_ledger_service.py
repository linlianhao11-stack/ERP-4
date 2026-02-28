"""账簿查询服务测试"""
import pytest
from decimal import Decimal
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.services.ledger_service import (
    get_general_ledger, get_detail_ledger, get_trial_balance,
    _direction_label, _balance_display,
)


async def _create_ledger_test_data():
    """创建账簿查询测试数据"""
    acc_set = await AccountSet.create(
        code="TEST", name="测试账套", start_year=2026, start_month=1,
        current_period="2026-03"
    )
    bank = await ChartOfAccount.create(
        account_set=acc_set, code="1002", name="银行存款",
        category="asset", direction="debit", is_leaf=True, level=1
    )
    ar = await ChartOfAccount.create(
        account_set=acc_set, code="1122", name="应收账款",
        category="asset", direction="debit", is_leaf=True, level=1,
        aux_customer=True
    )
    revenue = await ChartOfAccount.create(
        account_set=acc_set, code="6001", name="主营业务收入",
        category="profit_loss", direction="credit", is_leaf=True, level=1
    )
    for m in range(1, 4):
        await AccountingPeriod.create(
            account_set=acc_set, period_name=f"2026-{m:02d}", year=2026, month=m
        )
    # 凭证1: 2026-01 销售 — 借:应收10000 贷:收入10000
    v1 = await Voucher.create(
        account_set=acc_set, voucher_type="记",
        voucher_no="TEST-记-202601-001", period_name="2026-01",
        voucher_date="2026-01-15", total_debit=Decimal("10000"),
        total_credit=Decimal("10000"), status="posted"
    )
    await VoucherEntry.create(
        voucher=v1, line_no=1, account=ar,
        debit_amount=Decimal("10000"), credit_amount=Decimal("0"), summary="应收款"
    )
    await VoucherEntry.create(
        voucher=v1, line_no=2, account=revenue,
        debit_amount=Decimal("0"), credit_amount=Decimal("10000"), summary="销售收入"
    )
    # 凭证2: 2026-02 收款 — 借:银行5000 贷:应收5000
    v2 = await Voucher.create(
        account_set=acc_set, voucher_type="收",
        voucher_no="TEST-收-202602-001", period_name="2026-02",
        voucher_date="2026-02-10", total_debit=Decimal("5000"),
        total_credit=Decimal("5000"), status="posted"
    )
    await VoucherEntry.create(
        voucher=v2, line_no=1, account=bank,
        debit_amount=Decimal("5000"), credit_amount=Decimal("0"), summary="收款"
    )
    await VoucherEntry.create(
        voucher=v2, line_no=2, account=ar,
        debit_amount=Decimal("0"), credit_amount=Decimal("5000"), summary="冲应收"
    )
    # 凭证3: 2026-03 draft — 不应出现
    v3 = await Voucher.create(
        account_set=acc_set, voucher_type="记",
        voucher_no="TEST-记-202603-001", period_name="2026-03",
        voucher_date="2026-03-05", total_debit=Decimal("8000"),
        total_credit=Decimal("8000"), status="draft"
    )
    await VoucherEntry.create(
        voucher=v3, line_no=1, account=ar,
        debit_amount=Decimal("8000"), credit_amount=Decimal("0")
    )
    await VoucherEntry.create(
        voucher=v3, line_no=2, account=revenue,
        debit_amount=Decimal("0"), credit_amount=Decimal("8000")
    )
    return acc_set, bank, ar, revenue


async def test_direction_label():
    assert _direction_label(Decimal("0"), "debit") == "平"
    assert _direction_label(Decimal("100"), "debit") == "借"
    assert _direction_label(Decimal("-50"), "debit") == "贷"
    assert _direction_label(Decimal("100"), "credit") == "贷"
    assert _direction_label(Decimal("-50"), "credit") == "借"


async def test_balance_display():
    assert _balance_display(Decimal("100"), "debit") == (Decimal("100"), Decimal("0"))
    assert _balance_display(Decimal("-50"), "debit") == (Decimal("0"), Decimal("50"))
    assert _balance_display(Decimal("100"), "credit") == (Decimal("0"), Decimal("100"))
    assert _balance_display(Decimal("-50"), "credit") == (Decimal("50"), Decimal("0"))


async def test_general_ledger_opening_balance():
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_general_ledger(acc_set.id, ar.id, "2026-02", "2026-02")
    assert result is not None
    assert result["account_code"] == "1122"
    assert result["opening_balance"] == "10000"
    assert result["opening_direction"] == "借"
    assert len(result["entries"]) == 1
    assert result["entries"][0]["credit"] == "5000"
    assert result["entries"][0]["voucher_no"] == "TEST-收-202602-001"
    assert result["closing_balance"] == "5000"
    assert result["closing_direction"] == "借"


async def test_general_ledger_no_prior():
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_general_ledger(acc_set.id, bank.id, "2026-01", "2026-01")
    assert result["opening_balance"] == "0"
    assert result["opening_direction"] == "平"
    assert len(result["entries"]) == 0


async def test_general_ledger_ignores_draft():
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_general_ledger(acc_set.id, ar.id, "2026-03", "2026-03")
    assert len(result["entries"]) == 0
    assert result["opening_balance"] == "5000"


async def test_general_ledger_credit_direction():
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_general_ledger(acc_set.id, revenue.id, "2026-02", "2026-02")
    assert result["opening_balance"] == "10000"
    assert result["opening_direction"] == "贷"
    assert len(result["entries"]) == 0
    assert result["closing_balance"] == "10000"


async def test_detail_ledger_basic():
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_detail_ledger(acc_set.id, ar.id, "2026-01", "2026-02")
    assert result is not None
    assert len(result["entries"]) == 2
    assert result["opening_balance"] == "0"
    assert result["closing_balance"] == "5000"


async def test_trial_balance_is_balanced():
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_trial_balance(acc_set.id, "2026-02")
    assert result["is_balanced"] is True
    totals = result["totals"]
    assert totals["opening_debit"] == totals["opening_credit"]
    assert totals["period_debit"] == totals["period_credit"]
    assert totals["closing_debit"] == totals["closing_credit"]


async def test_trial_balance_accounts():
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_trial_balance(acc_set.id, "2026-02")
    acct_map = {a["code"]: a for a in result["accounts"]}
    assert "1122" in acct_map
    ar_row = acct_map["1122"]
    assert ar_row["opening_debit"] == "10000"
    assert ar_row["period_credit"] == "5000"
    assert ar_row["closing_debit"] == "5000"
    assert "1002" in acct_map
    bank_row = acct_map["1002"]
    assert bank_row["period_debit"] == "5000"
    assert bank_row["closing_debit"] == "5000"


async def test_trial_balance_empty():
    acc_set = await AccountSet.create(
        code="EMPTY", name="空账套", start_year=2026, start_month=1,
        current_period="2026-01"
    )
    result = await get_trial_balance(acc_set.id, "2026-01")
    assert result["accounts"] == []
    assert result["is_balanced"] is True
