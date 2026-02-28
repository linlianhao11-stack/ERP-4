"""会计基础模型测试"""
import pytest
from decimal import Decimal
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod


async def test_create_account_set():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领科技有限公司",
        tax_id="91440000MA000001X", start_year=2026, start_month=1,
        current_period="2026-01"
    )
    assert a.id is not None
    assert a.code == "QL"
    assert a.is_active is True


async def test_account_set_code_unique():
    await AccountSet.create(
        code="QL", name="启领", company_name="启领科技",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    from tortoise.exceptions import IntegrityError
    with pytest.raises(IntegrityError):
        await AccountSet.create(
            code="QL", name="启领2", company_name="启领科技2",
            start_year=2026, start_month=1, current_period="2026-01"
        )


async def test_create_chart_of_account():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    coa = await ChartOfAccount.create(
        account_set=a, code="1001", name="库存现金",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    assert coa.id is not None
    assert coa.direction == "debit"


async def test_chart_of_account_unique_per_set():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    await ChartOfAccount.create(
        account_set=a, code="1001", name="库存现金",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    from tortoise.exceptions import IntegrityError
    with pytest.raises(IntegrityError):
        await ChartOfAccount.create(
            account_set=a, code="1001", name="库存现金2",
            level=1, category="asset", direction="debit", is_leaf=True
        )


async def test_create_accounting_period():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    p = await AccountingPeriod.create(
        account_set=a, period_name="2026-01", year=2026, month=1
    )
    assert p.id is not None
    assert p.is_closed is False


async def test_accounting_period_unique_per_set():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    await AccountingPeriod.create(
        account_set=a, period_name="2026-01", year=2026, month=1
    )
    from tortoise.exceptions import IntegrityError
    with pytest.raises(IntegrityError):
        await AccountingPeriod.create(
            account_set=a, period_name="2026-01", year=2026, month=1
        )


from app.models import Warehouse, Product


async def test_warehouse_has_account_set():
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    w = await Warehouse.create(name="主仓", account_set=a)
    await w.refresh_from_db()
    assert w.account_set_id == a.id


async def test_warehouse_account_set_nullable():
    w = await Warehouse.create(name="虚拟仓", is_virtual=True)
    assert w.account_set_id is None


async def test_product_has_tax_rate():
    p = await Product.create(sku="TEST001", name="测试产品")
    await p.refresh_from_db()
    assert p.tax_rate == Decimal("13.00")
