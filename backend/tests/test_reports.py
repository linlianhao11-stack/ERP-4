"""财务报表测试"""
from decimal import Decimal
from datetime import date, datetime, timezone
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.models import User
from app.services.report_service import get_balance_sheet, get_income_statement, get_cash_flow


async def _setup():
    """创建基础数据"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    u = await User.create(username="testuser", password_hash="x", display_name="测试")
    accts = {}
    for code, name, cat, direction, aux_c, aux_s in [
        ("1001", "库存现金", "asset", "debit", False, False),
        ("1002", "银行存款", "asset", "debit", False, False),
        ("1122", "应收账款", "asset", "debit", True, False),
        ("1123", "预付账款", "asset", "debit", False, True),
        ("1221", "其他应收款", "asset", "debit", False, False),
        ("1403", "原材料", "asset", "debit", False, False),
        ("1405", "库存商品", "asset", "debit", False, False),
        ("1407", "发出商品", "asset", "debit", False, False),
        ("1601", "固定资产", "asset", "debit", False, False),
        ("1602", "累计折旧", "asset", "credit", False, False),
        ("2001", "短期借款", "liability", "credit", False, False),
        ("2202", "应付账款", "liability", "credit", False, True),
        ("2203", "预收账款", "liability", "credit", True, False),
        ("2211", "应付职工薪酬", "liability", "credit", False, False),
        ("2221", "应交税费", "liability", "credit", False, False),
        ("2241", "其他应付款", "liability", "credit", False, False),
        ("4001", "实收资本", "equity", "credit", False, False),
        ("4101", "盈余公积", "equity", "credit", False, False),
        ("4103", "本年利润", "equity", "credit", False, False),
        ("4104", "利润分配-未分配利润", "equity", "credit", False, False),
        ("6001", "主营业务收入", "profit_loss", "credit", False, False),
        ("6051", "其他业务收入", "profit_loss", "credit", False, False),
        ("6301", "营业外收入", "profit_loss", "credit", False, False),
        ("6401", "主营业务成本", "profit_loss", "debit", False, False),
        ("6402", "其他业务成本", "profit_loss", "debit", False, False),
        ("6403", "税金及附加", "profit_loss", "debit", False, False),
        ("6601", "销售费用", "profit_loss", "debit", False, False),
        ("6602", "管理费用", "profit_loss", "debit", False, False),
        ("6603", "财务费用", "profit_loss", "debit", False, False),
        ("6711", "营业外支出", "profit_loss", "debit", False, False),
        ("6801", "所得税费用", "profit_loss", "debit", False, False),
    ]:
        accts[code] = await ChartOfAccount.create(
            account_set=a, code=code, name=name,
            level=1, category=cat, direction=direction, is_leaf=True,
            aux_customer=aux_c, aux_supplier=aux_s,
        )
    await AccountingPeriod.create(account_set=a, period_name="2026-01", year=2026, month=1)
    return a, u, accts


async def _post_voucher(a, u, accts, period, entries_data):
    total = sum(e[2] for e in entries_data)
    v = await Voucher.create(
        account_set=a, voucher_type="记",
        voucher_no=f"QL-记-{period.replace('-','')}-{await Voucher.all().count() + 1:03d}",
        period_name=period, voucher_date=date(int(period[:4]), int(period[5:7]), 15),
        summary="测试", total_debit=total, total_credit=total,
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


async def test_balance_sheet_basic():
    a, u, accts = await _setup()
    # 投入资本
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("100000")),
        ("4001", "credit", Decimal("100000")),
    ])
    bs = await get_balance_sheet(a.id, "2026-01")
    assert bs["assets"]["current"]["bank"] == "100000"
    assert bs["equity"]["paid_capital"] == "100000"
    assert bs["is_balanced"] is True


async def test_balance_sheet_balanced():
    a, u, accts = await _setup()
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("50000")),
        ("4001", "credit", Decimal("50000")),
    ])
    await _post_voucher(a, u, accts, "2026-01", [
        ("1405", "debit", Decimal("20000")),
        ("2202", "credit", Decimal("20000")),
    ])
    bs = await get_balance_sheet(a.id, "2026-01")
    assert bs["is_balanced"] is True
    assert bs["assets"]["total"] == bs["total_liabilities_equity"]


async def test_income_statement():
    a, u, accts = await _setup()
    # 收入 10000
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("10000")),
        ("6001", "credit", Decimal("10000")),
    ])
    # 成本 6000
    await _post_voucher(a, u, accts, "2026-01", [
        ("6401", "debit", Decimal("6000")),
        ("1405", "credit", Decimal("6000")),
    ])
    # 管理费用 1000
    await _post_voucher(a, u, accts, "2026-01", [
        ("6602", "debit", Decimal("1000")),
        ("1002", "credit", Decimal("1000")),
    ])
    stmt = await get_income_statement(a.id, "2026-01")
    rows = {r["name"]: r for r in stmt["rows"]}
    assert rows["  主营业务收入"]["current"] == "10000"
    assert rows["  主营业务成本"]["current"] == "6000"
    assert rows["  管理费用"]["current"] == "1000"
    assert rows["三、营业利润"]["current"] == "3000"
    assert rows["五、净利润"]["current"] == "3000"


async def test_income_statement_ytd():
    a, u, accts = await _setup()
    await AccountingPeriod.create(account_set=a, period_name="2026-02", year=2026, month=2)
    # 1月收入
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("8000")),
        ("6001", "credit", Decimal("8000")),
    ])
    # 2月收入
    await _post_voucher(a, u, accts, "2026-02", [
        ("1002", "debit", Decimal("12000")),
        ("6001", "credit", Decimal("12000")),
    ])
    stmt = await get_income_statement(a.id, "2026-02")
    rows = {r["name"]: r for r in stmt["rows"]}
    assert rows["  主营业务收入"]["current"] == "12000"
    assert rows["  主营业务收入"]["ytd"] == "20000"


async def test_cash_flow_basic():
    a, u, accts = await _setup()
    # 销售收款
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("10000")),
        ("1122", "credit", Decimal("10000")),
    ])
    # 支付工资
    await _post_voucher(a, u, accts, "2026-01", [
        ("2211", "debit", Decimal("3000")),
        ("1002", "credit", Decimal("3000")),
    ])
    cf = await get_cash_flow(a.id, "2026-01")
    assert cf["operating"]["net"] != "0"
    assert Decimal(cf["net_increase"]) == Decimal("7000")


async def test_cash_flow_opening_closing():
    a, u, accts = await _setup()
    await AccountingPeriod.create(account_set=a, period_name="2026-02", year=2026, month=2)
    # 1月投入资金
    await _post_voucher(a, u, accts, "2026-01", [
        ("1002", "debit", Decimal("50000")),
        ("4001", "credit", Decimal("50000")),
    ])
    # 2月销售
    await _post_voucher(a, u, accts, "2026-02", [
        ("1002", "debit", Decimal("10000")),
        ("1122", "credit", Decimal("10000")),
    ])
    cf = await get_cash_flow(a.id, "2026-02")
    # opening_cash = 年初之前的余额 = 0（2026-01之前没有数据）
    # net_increase for 2026-02 = 10000
    assert Decimal(cf["net_increase"]) == Decimal("10000")
    assert Decimal(cf["closing_cash"]) == Decimal(cf["opening_cash"]) + Decimal(cf["net_increase"])


async def test_balance_sheet_empty():
    a, u, accts = await _setup()
    bs = await get_balance_sheet(a.id, "2026-01")
    assert bs["is_balanced"] is True
    assert bs["assets"]["total"] == "0"
