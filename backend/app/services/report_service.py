"""财务报表服务：资产负债表 + 利润表 + 现金流量表"""
from __future__ import annotations

from decimal import Decimal
from collections import defaultdict
from app.models.accounting import ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.logger import get_logger

logger = get_logger("report_service")


def _dec_str(d: Decimal) -> str:
    return format(d.normalize(), 'f')


async def _account_balance(account_set_id: int, code: str, end_period: str) -> Decimal:
    """查询指定科目截至指定期间的累计余额（已过账凭证）"""
    acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code=code, is_active=True
    ).first()
    if not acct:
        return Decimal("0")

    # 如果是非叶子科目，需要汇总其子科目
    if not acct.is_leaf:
        children = await ChartOfAccount.filter(
            account_set_id=account_set_id, parent_code=code, is_leaf=True, is_active=True
        ).all()
        total = Decimal("0")
        for child in children:
            total += await _leaf_balance(account_set_id, child, end_period)
        return total

    return await _leaf_balance(account_set_id, acct, end_period)


async def _leaf_balance(account_set_id: int, acct, end_period: str) -> Decimal:
    """计算叶子科目截至 end_period 的余额（方向感知）"""
    entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name__lte=end_period,
        account_id=acct.id,
    ).all()
    debit_sum = sum(e.debit_amount for e in entries)
    credit_sum = sum(e.credit_amount for e in entries)
    if acct.direction == "debit":
        return debit_sum - credit_sum
    else:
        return credit_sum - debit_sum


async def _period_amount(account_set_id: int, code: str, period_name: str) -> Decimal:
    """查询指定科目某期间的发生额（方向感知净额）"""
    acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code=code, is_active=True
    ).first()
    if not acct:
        return Decimal("0")

    if not acct.is_leaf:
        children = await ChartOfAccount.filter(
            account_set_id=account_set_id, parent_code=code, is_leaf=True, is_active=True
        ).all()
        total = Decimal("0")
        for child in children:
            total += await _leaf_period_amount(account_set_id, child, period_name)
        return total

    return await _leaf_period_amount(account_set_id, acct, period_name)


async def _leaf_period_amount(account_set_id: int, acct, period_name: str) -> Decimal:
    """计算叶子科目某期间的发生额"""
    entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name=period_name,
        account_id=acct.id,
    ).all()
    debit_sum = sum(e.debit_amount for e in entries)
    credit_sum = sum(e.credit_amount for e in entries)
    if acct.direction == "credit":
        return credit_sum - debit_sum
    else:
        return debit_sum - credit_sum


async def _ytd_amount(account_set_id: int, code: str, period_name: str) -> Decimal:
    """查询指定科目本年累计发生额"""
    year = period_name[:4]
    start = f"{year}-01"
    acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code=code, is_active=True
    ).first()
    if not acct:
        return Decimal("0")

    if not acct.is_leaf:
        children = await ChartOfAccount.filter(
            account_set_id=account_set_id, parent_code=code, is_leaf=True, is_active=True
        ).all()
        total = Decimal("0")
        for child in children:
            total += await _leaf_ytd_amount(account_set_id, child, start, period_name)
        return total

    return await _leaf_ytd_amount(account_set_id, acct, start, period_name)


async def _leaf_ytd_amount(account_set_id: int, acct, start: str, end: str) -> Decimal:
    entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name__gte=start,
        voucher__period_name__lte=end,
        account_id=acct.id,
    ).all()
    debit_sum = sum(e.debit_amount for e in entries)
    credit_sum = sum(e.credit_amount for e in entries)
    if acct.direction == "credit":
        return credit_sum - debit_sum
    else:
        return debit_sum - credit_sum


async def get_balance_sheet(account_set_id: int, period_name: str) -> dict:
    """资产负债表"""
    b = lambda code: _account_balance(account_set_id, code, period_name)

    # 资产类
    cash = await b("1001")
    bank = await b("1002")
    ar = await b("1122")
    prepaid = await b("1123")
    other_ar = await b("1221")
    raw_material = await b("1403")
    inventory = await b("1405")
    goods_in_transit = await b("1407")
    current_assets = cash + bank + ar + prepaid + other_ar + raw_material + inventory + goods_in_transit

    fixed_assets = await b("1601")
    accum_depreciation = await b("1602")  # credit 方向, 返回正值表示贷方余额
    non_current_assets = fixed_assets - accum_depreciation

    total_assets = current_assets + non_current_assets

    # 负债类
    short_loan = await b("2001")
    ap = await b("2202")
    advance_received = await b("2203")
    salary_payable = await b("2211")
    tax_payable = await b("2221")
    other_ap = await b("2241")
    current_liabilities = short_loan + ap + advance_received + salary_payable + tax_payable + other_ap

    # 所有者权益
    paid_capital = await b("4001")
    surplus_reserve = await b("4101")
    current_profit = await b("4103")
    retained_earnings = await b("4104")
    total_equity = paid_capital + surplus_reserve + current_profit + retained_earnings

    total_liabilities_equity = current_liabilities + total_equity

    return {
        "period_name": period_name,
        "assets": {
            "current": {
                "cash": _dec_str(cash),
                "bank": _dec_str(bank),
                "accounts_receivable": _dec_str(ar),
                "prepaid": _dec_str(prepaid),
                "other_receivable": _dec_str(other_ar),
                "raw_material": _dec_str(raw_material),
                "inventory": _dec_str(inventory),
                "goods_in_transit": _dec_str(goods_in_transit),
                "subtotal": _dec_str(current_assets),
            },
            "non_current": {
                "fixed_assets": _dec_str(fixed_assets),
                "accumulated_depreciation": _dec_str(accum_depreciation),
                "subtotal": _dec_str(non_current_assets),
            },
            "total": _dec_str(total_assets),
        },
        "liabilities": {
            "current": {
                "short_term_loan": _dec_str(short_loan),
                "accounts_payable": _dec_str(ap),
                "advance_received": _dec_str(advance_received),
                "salary_payable": _dec_str(salary_payable),
                "tax_payable": _dec_str(tax_payable),
                "other_payable": _dec_str(other_ap),
                "subtotal": _dec_str(current_liabilities),
            },
        },
        "equity": {
            "paid_capital": _dec_str(paid_capital),
            "surplus_reserve": _dec_str(surplus_reserve),
            "current_profit": _dec_str(current_profit),
            "retained_earnings": _dec_str(retained_earnings),
            "subtotal": _dec_str(total_equity),
        },
        "total_liabilities_equity": _dec_str(total_liabilities_equity),
        "is_balanced": total_assets == total_liabilities_equity,
    }


async def get_income_statement(account_set_id: int, period_name: str) -> dict:
    """利润表"""
    p = lambda code: _period_amount(account_set_id, code, period_name)
    y = lambda code: _ytd_amount(account_set_id, code, period_name)

    # 本期
    revenue = await p("6001")
    other_revenue = await p("6051")
    total_revenue = revenue + other_revenue

    cogs = await p("6401")
    other_cost = await p("6402")
    tax_surcharge = await p("6403")
    selling_expense = await p("6601")
    admin_expense = await p("6602")
    finance_expense = await p("6603")
    total_cost = cogs + other_cost + tax_surcharge + selling_expense + admin_expense + finance_expense

    operating_profit = total_revenue - total_cost

    non_op_income = await p("6301")
    non_op_expense = await p("6711")

    profit_before_tax = operating_profit + non_op_income - non_op_expense
    income_tax = await p("6801")
    net_profit = profit_before_tax - income_tax

    # 本年累计
    y_revenue = await y("6001")
    y_other_revenue = await y("6051")
    y_total_revenue = y_revenue + y_other_revenue
    y_cogs = await y("6401")
    y_other_cost = await y("6402")
    y_tax_surcharge = await y("6403")
    y_selling = await y("6601")
    y_admin = await y("6602")
    y_finance = await y("6603")
    y_total_cost = y_cogs + y_other_cost + y_tax_surcharge + y_selling + y_admin + y_finance
    y_operating_profit = y_total_revenue - y_total_cost
    y_non_op_income = await y("6301")
    y_non_op_expense = await y("6711")
    y_profit_before_tax = y_operating_profit + y_non_op_income - y_non_op_expense
    y_income_tax = await y("6801")
    y_net_profit = y_profit_before_tax - y_income_tax

    def row(name, current, ytd):
        return {"name": name, "current": _dec_str(current), "ytd": _dec_str(ytd)}

    return {
        "period_name": period_name,
        "rows": [
            row("一、营业收入", total_revenue, y_total_revenue),
            row("  主营业务收入", revenue, y_revenue),
            row("  其他业务收入", other_revenue, y_other_revenue),
            row("二、营业成本", total_cost, y_total_cost),
            row("  主营业务成本", cogs, y_cogs),
            row("  其他业务成本", other_cost, y_other_cost),
            row("  税金及附加", tax_surcharge, y_tax_surcharge),
            row("  销售费用", selling_expense, y_selling),
            row("  管理费用", admin_expense, y_admin),
            row("  财务费用", finance_expense, y_finance),
            row("三、营业利润", operating_profit, y_operating_profit),
            row("  营业外收入", non_op_income, y_non_op_income),
            row("  营业外支出", non_op_expense, y_non_op_expense),
            row("四、利润总额", profit_before_tax, y_profit_before_tax),
            row("  所得税费用", income_tax, y_income_tax),
            row("五、净利润", net_profit, y_net_profit),
        ],
    }


async def get_cash_flow(account_set_id: int, period_name: str) -> dict:
    """现金流量表（简易直接法）：查询银行存款+库存现金的已过账分录，按对手科目分类"""
    # 找到现金类科目
    cash_codes = ["1001", "1002"]
    cash_accounts = await ChartOfAccount.filter(
        account_set_id=account_set_id, code__in=cash_codes, is_active=True
    ).all()
    cash_account_ids = {a.id for a in cash_accounts}

    if not cash_account_ids:
        return {"period_name": period_name, "sections": [], "summary": {}}

    # 查询所有现金科目的已过账分录
    cash_entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name=period_name,
        account_id__in=list(cash_account_ids),
    ).prefetch_related("voucher").all()

    # 对手科目分类映射
    counter_mapping = {
        "1122": ("operating", "sales_received", "销售商品、提供劳务收到的现金"),
        "2202": ("operating", "purchase_paid", "购买商品、接受劳务支付的现金"),
        "2211": ("operating", "salary_paid", "支付给职工以及为职工支付的现金"),
        "2221": ("operating", "tax_paid", "支付的各项税费"),
        "222101": ("operating", "tax_paid", "支付的各项税费"),
        "222102": ("operating", "tax_paid", "支付的各项税费"),
        "2203": ("operating", "other_operating_in", "收到的其他与经营活动有关的现金"),
        "1123": ("operating", "other_operating_out", "支付的其他与经营活动有关的现金"),
        "1601": ("investing", "fixed_asset", "购建固定资产、无形资产支付的现金"),
        "1403": ("investing", "material", "购买原材料支付的现金"),
        "2001": ("financing", "loan", "借款/偿还借款"),
        "4001": ("financing", "capital", "吸收投资收到的现金"),
    }

    # 聚合
    flow = defaultdict(lambda: Decimal("0"))

    for ce in cash_entries:
        # 查找同凭证的对手分录
        voucher_entries = await VoucherEntry.filter(
            voucher_id=ce.voucher_id,
        ).exclude(id=ce.id).all()

        for counter in voucher_entries:
            if counter.account_id in cash_account_ids:
                continue
            # 查找对手科目的 code
            counter_acct = await ChartOfAccount.filter(id=counter.account_id).first()
            if not counter_acct:
                continue

            code = counter_acct.code
            # 尝试匹配
            category_key = None
            for map_code, (cat, key, _) in counter_mapping.items():
                if code == map_code or code.startswith(map_code):
                    category_key = (cat, key)
                    break
            # 6xxx 损益类
            if not category_key and code.startswith("6"):
                category_key = ("operating", "other_operating")
            # 默认经营
            if not category_key:
                category_key = ("operating", "other_operating")

            # 现金科目借方=流入，贷方=流出
            amount = ce.debit_amount - ce.credit_amount
            flow[category_key] += amount

    # 构建结果
    operating_items = []
    investing_items = []
    financing_items = []

    def add_item(items, key, label, amount):
        items.append({"key": key, "label": label, "amount": _dec_str(amount)})

    # 经营活动
    for map_code, (cat, key, label) in counter_mapping.items():
        if cat == "operating":
            val = flow.get(("operating", key), Decimal("0"))
            if val != 0 and not any(i["key"] == key for i in operating_items):
                add_item(operating_items, key, label, val)
    other_op = flow.get(("operating", "other_operating"), Decimal("0"))
    if other_op != 0:
        add_item(operating_items, "other_operating", "其他与经营活动有关的现金流量净额", other_op)

    operating_net = sum(Decimal(i["amount"]) for i in operating_items)

    # 投资活动
    for map_code, (cat, key, label) in counter_mapping.items():
        if cat == "investing":
            val = flow.get(("investing", key), Decimal("0"))
            if val != 0 and not any(i["key"] == key for i in investing_items):
                add_item(investing_items, key, label, val)
    investing_net = sum(Decimal(i["amount"]) for i in investing_items)

    # 筹资活动
    for map_code, (cat, key, label) in counter_mapping.items():
        if cat == "financing":
            val = flow.get(("financing", key), Decimal("0"))
            if val != 0 and not any(i["key"] == key for i in financing_items):
                add_item(financing_items, key, label, val)
    financing_net = sum(Decimal(i["amount"]) for i in financing_items)

    net_increase = operating_net + investing_net + financing_net

    # 期初/期末现金余额
    year = period_name[:4]
    start_period = f"{year}-01"
    opening_cash = Decimal("0")
    for ca in cash_accounts:
        prior_entries = await VoucherEntry.filter(
            voucher__account_set_id=account_set_id,
            voucher__status="posted",
            voucher__period_name__lt=start_period,
            account_id=ca.id,
        ).all()
        d = sum(e.debit_amount for e in prior_entries)
        c = sum(e.credit_amount for e in prior_entries)
        opening_cash += (d - c)

    closing_cash = opening_cash + net_increase

    return {
        "period_name": period_name,
        "operating": {
            "items": operating_items,
            "net": _dec_str(operating_net),
        },
        "investing": {
            "items": investing_items,
            "net": _dec_str(investing_net),
        },
        "financing": {
            "items": financing_items,
            "net": _dec_str(financing_net),
        },
        "net_increase": _dec_str(net_increase),
        "opening_cash": _dec_str(opening_cash),
        "closing_cash": _dec_str(closing_cash),
    }
