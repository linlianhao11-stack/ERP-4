"""供应商返利按账套隔离测试"""
import pytest
from decimal import Decimal
from app.models import Supplier, RebateLog, User, Customer
from app.models.accounting import AccountSet
from app.models.supplier_balance import SupplierAccountBalance
from app.models.customer_balance import CustomerAccountBalance


@pytest.mark.asyncio
async def test_supplier_account_balance_create():
    """测试 SupplierAccountBalance 创建"""
    supplier = await Supplier.create(name="测试供应商A")
    aset = await AccountSet.create(
        code="TEST01", name="测试账套1", start_year=2026, current_period="2026-01"
    )
    bal = await SupplierAccountBalance.create(
        supplier=supplier, account_set=aset,
        rebate_balance=Decimal("1000"), credit_balance=Decimal("500")
    )
    assert bal.rebate_balance == Decimal("1000")
    assert bal.credit_balance == Decimal("500")
    assert bal.supplier_id == supplier.id
    assert bal.account_set_id == aset.id


@pytest.mark.asyncio
async def test_supplier_balance_isolation():
    """测试不同账套的余额隔离"""
    supplier = await Supplier.create(name="测试供应商B")
    aset1 = await AccountSet.create(
        code="SET_A", name="账套A", start_year=2026, current_period="2026-01"
    )
    aset2 = await AccountSet.create(
        code="SET_B", name="账套B", start_year=2026, current_period="2026-01"
    )
    await SupplierAccountBalance.create(
        supplier=supplier, account_set=aset1,
        rebate_balance=Decimal("1000"), credit_balance=0
    )
    await SupplierAccountBalance.create(
        supplier=supplier, account_set=aset2,
        rebate_balance=Decimal("2000"), credit_balance=Decimal("300")
    )
    b1 = await SupplierAccountBalance.filter(
        supplier=supplier, account_set=aset1
    ).first()
    b2 = await SupplierAccountBalance.filter(
        supplier=supplier, account_set=aset2
    ).first()
    assert b1.rebate_balance == Decimal("1000")
    assert b2.rebate_balance == Decimal("2000")
    assert b2.credit_balance == Decimal("300")


@pytest.mark.asyncio
async def test_rebate_log_with_account_set():
    """测试 RebateLog 记录 account_set_id"""
    user = await User.create(
        username="test_rebate_user", password_hash="x", display_name="Test"
    )
    supplier = await Supplier.create(name="供应商C")
    aset = await AccountSet.create(
        code="SET_C", name="账套C", start_year=2026, current_period="2026-01"
    )
    log = await RebateLog.create(
        target_type="supplier", target_id=supplier.id,
        type="charge", amount=Decimal("500"),
        balance_after=Decimal("500"),
        account_set_id=aset.id,
        creator=user
    )
    assert log.account_set_id == aset.id


@pytest.mark.asyncio
async def test_rebate_log_without_account_set():
    """测试无账套的 RebateLog（客户返利兼容）"""
    user = await User.create(
        username="test_rebate_user2", password_hash="x", display_name="Test2"
    )
    log = await RebateLog.create(
        target_type="customer", target_id=1,
        type="charge", amount=Decimal("100"),
        balance_after=Decimal("100"),
        creator=user
    )
    assert log.account_set_id is None


@pytest.mark.asyncio
async def test_customer_account_balance_create():
    """测试 CustomerAccountBalance 创建"""
    customer = await Customer.create(name="测试客户A")
    aset = await AccountSet.create(
        code="CTEST01", name="客户测试账套1", start_year=2026, current_period="2026-01"
    )
    bal = await CustomerAccountBalance.create(
        customer=customer, account_set=aset,
        rebate_balance=Decimal("800")
    )
    assert bal.rebate_balance == Decimal("800")
    assert bal.customer_id == customer.id
    assert bal.account_set_id == aset.id


@pytest.mark.asyncio
async def test_customer_balance_isolation():
    """测试不同账套的客户返利余额隔离"""
    customer = await Customer.create(name="测试客户B")
    aset1 = await AccountSet.create(
        code="CSET_A", name="客户账套A", start_year=2026, current_period="2026-01"
    )
    aset2 = await AccountSet.create(
        code="CSET_B", name="客户账套B", start_year=2026, current_period="2026-01"
    )
    await CustomerAccountBalance.create(
        customer=customer, account_set=aset1,
        rebate_balance=Decimal("500")
    )
    await CustomerAccountBalance.create(
        customer=customer, account_set=aset2,
        rebate_balance=Decimal("1200")
    )
    b1 = await CustomerAccountBalance.filter(
        customer=customer, account_set=aset1
    ).first()
    b2 = await CustomerAccountBalance.filter(
        customer=customer, account_set=aset2
    ).first()
    assert b1.rebate_balance == Decimal("500")
    assert b2.rebate_balance == Decimal("1200")
