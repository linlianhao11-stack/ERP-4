"""期末处理测试"""
from decimal import Decimal
from datetime import date
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.models import User
from app.services.period_end_service import (
    preview_carry_forward, execute_carry_forward,
    close_check, close_period, reopen_period, year_close,
)


async def _setup():
    """创建基础数据"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    u = await User.create(username="testuser", password_hash="x", display_name="测试")
    # 必要科目
    accts = {}
    for code, name, cat, direction in [
        ("1001", "库存现金", "asset", "debit"),
        ("1002", "银行存款", "asset", "debit"),
        ("1122", "应收账款", "asset", "debit"),
        ("1405", "库存商品", "asset", "debit"),
        ("2202", "应付账款", "liability", "credit"),
        ("4001", "实收资本", "equity", "credit"),
        ("4103", "本年利润", "equity", "credit"),
        ("4104", "利润分配-未分配利润", "equity", "credit"),
        ("6001", "主营业务收入", "profit_loss", "credit"),
        ("6401", "主营业务成本", "profit_loss", "debit"),
        ("6602", "管理费用", "profit_loss", "debit"),
    ]:
        accts[code] = await ChartOfAccount.create(
            account_set=a, code=code, name=name,
            level=1, category=cat, direction=direction, is_leaf=True
        )
    # 创建期间
    await AccountingPeriod.create(account_set=a, period_name="2026-01", year=2026, month=1)
    return a, u, accts


async def _post_voucher(a, u, accts, period, entries_data):
    """创建并过账一张凭证"""
    from datetime import datetime, timezone
    total = sum(e[2] for e in entries_data)
    v = await Voucher.create(
        account_set=a, voucher_type="记",
        voucher_no=f"QL-记-{period.replace('-','')}-{await Voucher.all().count() + 1:03d}",
        period_name=period,
        voucher_date=date(int(period[:4]), int(period[5:7]), 15),
        summary="测试凭证", total_debit=total, total_credit=total,
        status="posted", creator=u,
        posted_by=u, posted_at=datetime.now(timezone.utc),
    )
    for i, (code, direction, amount) in enumerate(entries_data, 1):
        await VoucherEntry.create(
            voucher=v, line_no=i, account_id=accts[code].id,
            summary="测试",
            debit_amount=amount if direction == "debit" else Decimal("0"),
            credit_amount=amount if direction == "credit" else Decimal("0"),
        )
    return v


async def test_preview_carry_forward():
    a, u, accts = await _setup()
    # 记录收入和成本
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("10000")),
        ("6001", "credit", Decimal("10000")),
    ])
    await _post_voucher(a, u, accts, "2026-01", [
        ("6401", "debit", Decimal("6000")),
        ("1405", "credit", Decimal("6000")),
    ])
    result = await preview_carry_forward(a.id, "2026-01")
    assert result["already_exists"] is False
    assert len(result["entries"]) == 2
    assert result["total_profit"] == "4000"


async def test_execute_carry_forward():
    a, u, accts = await _setup()
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("10000")),
        ("6001", "credit", Decimal("10000")),
    ])
    await _post_voucher(a, u, accts, "2026-01", [
        ("6401", "debit", Decimal("6000")),
        ("1405", "credit", Decimal("6000")),
    ])
    result = await execute_carry_forward(a.id, "2026-01", u)
    assert result["voucher_no"] is not None
    assert result["total_profit"] == "4000"

    # 验证凭证
    v = await Voucher.filter(id=result["voucher_id"]).first()
    assert v.voucher_type == "转"
    assert v.source_type == "period_end_carry_forward"
    assert v.status == "posted"

    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").all()
    assert len(entries) == 3  # 收入结转 + 成本结转 + 本年利润


async def test_carry_forward_idempotent():
    a, u, accts = await _setup()
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("5000")),
        ("6001", "credit", Decimal("5000")),
    ])
    r1 = await execute_carry_forward(a.id, "2026-01", u)
    r2 = await execute_carry_forward(a.id, "2026-01", u)
    assert r1["voucher_id"] is not None
    assert r2["already_existed"] is True


async def test_close_check_all_pass():
    a, u, accts = await _setup()
    # 创建凭证 + 损益结转
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("5000")),
        ("6001", "credit", Decimal("5000")),
    ])
    await execute_carry_forward(a.id, "2026-01", u)
    checks = await close_check(a.id, "2026-01")
    assert all(c["passed"] for c in checks)


async def test_close_check_unposted_fail():
    a, u, accts = await _setup()
    # 创建未过账凭证
    await Voucher.create(
        account_set=a, voucher_type="记", voucher_no="QL-记-202601-001",
        period_name="2026-01", voucher_date=date(2026, 1, 15),
        summary="草稿", total_debit=Decimal("100"), total_credit=Decimal("100"),
        status="draft", creator=u,
    )
    checks = await close_check(a.id, "2026-01")
    assert checks[0]["passed"] is False
    assert "未过账" in checks[0]["detail"]


async def test_close_period_success():
    a, u, accts = await _setup()
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("5000")),
        ("6001", "credit", Decimal("5000")),
    ])
    await execute_carry_forward(a.id, "2026-01", u)
    result = await close_period(a.id, "2026-01", u)
    assert result["already_closed"] is False

    period = await AccountingPeriod.filter(account_set=a, period_name="2026-01").first()
    assert period.is_closed is True


async def test_reopen_period():
    a, u, accts = await _setup()
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("5000")),
        ("6001", "credit", Decimal("5000")),
    ])
    await execute_carry_forward(a.id, "2026-01", u)
    await close_period(a.id, "2026-01", u)
    result = await reopen_period(a.id, "2026-01", u)
    assert result["reopened"] is True

    period = await AccountingPeriod.filter(account_set=a, period_name="2026-01").first()
    assert period.is_closed is False


async def test_year_close():
    a, u, accts = await _setup()
    # 创建12月期间
    await AccountingPeriod.create(account_set=a, period_name="2026-12", year=2026, month=12)
    # 模拟年度利润（直接在4103上记录）
    await _post_voucher(a, u, accts, "2026-12", [
        ("6001", "credit", Decimal("20000")),
        ("1002", "debit", Decimal("20000")),
    ])
    await _post_voucher(a, u, accts, "2026-12", [
        ("6401", "debit", Decimal("12000")),
        ("1405", "credit", Decimal("12000")),
    ])
    await execute_carry_forward(a.id, "2026-12", u)

    result = await year_close(a.id, 2026, u)
    assert result["voucher_no"] is not None
    assert result["next_year_periods_created"] == 12

    # 验证凭证
    v = await Voucher.filter(id=result["voucher_id"]).first()
    assert v.source_type == "year_end_close"
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").all()
    assert len(entries) == 2
    # 借 4103 / 贷 4104
    assert entries[0].account_id == accts["4103"].id
    assert entries[1].account_id == accts["4104"].id


async def test_year_close_idempotent():
    a, u, accts = await _setup()
    await AccountingPeriod.create(account_set=a, period_name="2026-12", year=2026, month=12)
    await _post_voucher(a, u, accts, "2026-12", [
        ("1002", "debit", Decimal("5000")),
        ("6001", "credit", Decimal("5000")),
    ])
    await execute_carry_forward(a.id, "2026-12", u)
    r1 = await year_close(a.id, 2026, u)
    r2 = await year_close(a.id, 2026, u)
    assert r1["voucher_id"] is not None
    assert r2["already_existed"] is True
