"""会计初始化服务：预置科目、期间自动创建"""
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod

# 预置贸易企业标准科目：(code, name, parent_code, level, category, direction, is_leaf, aux_customer, aux_supplier)
PRESET_ACCOUNTS = [
    # 资产类
    ("1001", "库存现金", None, 1, "asset", "debit", True, False, False),
    ("1002", "银行存款", None, 1, "asset", "debit", True, False, False),
    ("1122", "应收账款", None, 1, "asset", "debit", True, True, False),
    ("1123", "预付账款", None, 1, "asset", "debit", True, False, True),
    ("1221", "其他应收款", None, 1, "asset", "debit", True, False, False),
    ("1403", "原材料", None, 1, "asset", "debit", True, False, False),
    ("1405", "库存商品", None, 1, "asset", "debit", True, False, False),
    ("1407", "发出商品", None, 1, "asset", "debit", True, False, False),
    ("1601", "固定资产", None, 1, "asset", "debit", True, False, False),
    ("1602", "累计折旧", None, 1, "asset", "credit", True, False, False),
    # 负债类
    ("2001", "短期借款", None, 1, "liability", "credit", True, False, False),
    ("2202", "应付账款", None, 1, "liability", "credit", True, False, True),
    ("2203", "预收账款", None, 1, "liability", "credit", True, True, False),
    ("2211", "应付职工薪酬", None, 1, "liability", "credit", True, False, False),
    ("2221", "应交税费", None, 1, "liability", "credit", False, False, False),
    ("222101", "应交增值税-进项税额", "2221", 2, "liability", "debit", True, False, False),
    ("222102", "应交增值税-销项税额", "2221", 2, "liability", "credit", True, False, False),
    ("2241", "其他应付款", None, 1, "liability", "credit", True, False, False),
    # 所有者权益类
    ("4001", "实收资本", None, 1, "equity", "credit", True, False, False),
    ("4101", "盈余公积", None, 1, "equity", "credit", True, False, False),
    ("4103", "本年利润", None, 1, "equity", "credit", True, False, False),
    ("4104", "利润分配-未分配利润", None, 1, "equity", "credit", True, False, False),
    # 损益类
    ("6001", "主营业务收入", None, 1, "profit_loss", "credit", True, False, False),
    ("6051", "其他业务收入", None, 1, "profit_loss", "credit", True, False, False),
    ("6301", "营业外收入", None, 1, "profit_loss", "credit", True, False, False),
    ("6401", "主营业务成本", None, 1, "profit_loss", "debit", True, False, False),
    ("6402", "其他业务成本", None, 1, "profit_loss", "debit", True, False, False),
    ("6403", "税金及附加", None, 1, "profit_loss", "debit", True, False, False),
    ("6601", "销售费用", None, 1, "profit_loss", "debit", True, False, False),
    ("6602", "管理费用", None, 1, "profit_loss", "debit", True, False, False),
    ("6603", "财务费用", None, 1, "profit_loss", "debit", True, False, False),
    ("6711", "营业外支出", None, 1, "profit_loss", "debit", True, False, False),
    ("6801", "所得税费用", None, 1, "profit_loss", "debit", True, False, False),
]


async def init_chart_of_accounts(account_set_id: int) -> int:
    """为账套初始化预置科目，返回新创建的科目数量（幂等）"""
    existing = await ChartOfAccount.filter(account_set_id=account_set_id).values_list("code", flat=True)
    existing_codes = set(existing)

    created = 0
    for code, name, parent_code, level, category, direction, is_leaf, aux_cust, aux_sup in PRESET_ACCOUNTS:
        if code in existing_codes:
            continue
        await ChartOfAccount.create(
            account_set_id=account_set_id,
            code=code, name=name, parent_code=parent_code,
            level=level, category=category, direction=direction,
            is_leaf=is_leaf, aux_customer=aux_cust, aux_supplier=aux_sup
        )
        created += 1
    return created


async def init_accounting_periods(account_set_id: int, start_year: int, start_month: int) -> int:
    """为账套创建从 start_month 到 12 月的会计期间，返回新建数量（幂等）"""
    periods = await AccountingPeriod.filter(account_set_id=account_set_id).values_list("period_name", flat=True)
    existing = set(periods)

    created = 0
    for m in range(start_month, 13):
        period_name = f"{start_year}-{m:02d}"
        if period_name in existing:
            continue
        await AccountingPeriod.create(
            account_set_id=account_set_id,
            period_name=period_name,
            year=start_year, month=m
        )
        created += 1
    return created
