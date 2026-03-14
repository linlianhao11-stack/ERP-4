import pytest
from app.models.payment import PaymentMethod, DisbursementMethod
from app.models.accounting import AccountSet


@pytest.mark.anyio
async def test_payment_method_per_account_set():
    as1 = await AccountSet.create(code="QL", name="启领", start_year=2026, start_month=1, current_period="2026-03")
    as2 = await AccountSet.create(code="LW", name="链雾", start_year=2026, start_month=1, current_period="2026-03")
    pm1 = await PaymentMethod.create(code="CASH", name="现金", account_set=as1)
    pm2 = await PaymentMethod.create(code="CASH", name="现金", account_set=as2)
    assert pm1.id != pm2.id  # Same code, different account sets → allowed


@pytest.mark.anyio
async def test_payment_method_unique_within_account_set():
    from tortoise.exceptions import IntegrityError
    as1 = await AccountSet.create(code="QL", name="启领", start_year=2026, start_month=1, current_period="2026-03")
    await PaymentMethod.create(code="CASH", name="现金", account_set=as1)
    with pytest.raises(IntegrityError):
        await PaymentMethod.create(code="CASH", name="现金2", account_set=as1)
