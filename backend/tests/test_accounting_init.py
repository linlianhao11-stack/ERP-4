"""科目初始化测试"""
import pytest
from decimal import Decimal
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.services.accounting_init import init_chart_of_accounts, init_accounting_periods


async def test_init_chart_of_accounts():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    count = await init_chart_of_accounts(a.id)
    assert count >= 25

    cash = await ChartOfAccount.filter(account_set_id=a.id, code="1001").first()
    assert cash is not None
    assert cash.name == "库存现金"
    assert cash.category == "asset"
    assert cash.direction == "debit"

    ar = await ChartOfAccount.filter(account_set_id=a.id, code="1122").first()
    assert ar is not None
    assert ar.aux_customer is True

    ap = await ChartOfAccount.filter(account_set_id=a.id, code="2202").first()
    assert ap is not None
    assert ap.aux_supplier is True

    vat_in = await ChartOfAccount.filter(account_set_id=a.id, code="222101").first()
    assert vat_in is not None
    assert vat_in.parent_code == "2221"
    assert vat_in.level == 2


async def test_init_chart_idempotent():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    count1 = await init_chart_of_accounts(a.id)
    count2 = await init_chart_of_accounts(a.id)
    total = await ChartOfAccount.filter(account_set_id=a.id).count()
    assert total == count1
    assert count2 == 0


async def test_init_accounting_periods():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=3, current_period="2026-03"
    )
    count = await init_accounting_periods(a.id, 2026, 3)
    assert count == 10  # 3月到12月

    periods = await AccountingPeriod.filter(account_set_id=a.id).order_by("month")
    assert len(periods) == 10
    assert periods[0].period_name == "2026-03"
    assert periods[-1].period_name == "2026-12"


async def test_init_periods_idempotent():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    count1 = await init_accounting_periods(a.id, 2026, 1)
    count2 = await init_accounting_periods(a.id, 2026, 1)
    assert count1 == 12
    assert count2 == 0
