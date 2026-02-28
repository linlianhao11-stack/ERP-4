"""账簿查询服务：总分类账、明细分类账、科目余额表"""
from __future__ import annotations
from decimal import Decimal
from collections import defaultdict
from typing import Optional
from app.models.accounting import ChartOfAccount
from app.models.voucher import Voucher, VoucherEntry


def _dec_str(d: Decimal) -> str:
    """将 Decimal 转为不含科学计数法的字符串"""
    return format(d.normalize(), 'f')


def _direction_label(net: Decimal, direction: str) -> str:
    """返回余额方向标签：借/贷/平"""
    if net == 0:
        return "平"
    if direction == "debit":
        return "借" if net > 0 else "贷"
    else:
        return "贷" if net > 0 else "借"


def _balance_display(net: Decimal, direction: str) -> tuple:
    """将净额转换为(借方余额, 贷方余额)对，用于科目余额表"""
    if direction == "debit":
        return (net, Decimal("0")) if net >= 0 else (Decimal("0"), abs(net))
    else:
        return (Decimal("0"), net) if net >= 0 else (abs(net), Decimal("0"))


async def get_general_ledger(
    account_set_id: int,
    account_id: int,
    start_period: str,
    end_period: str,
) -> dict | None:
    """总分类账：期初余额 + 逐笔分录 + 期末余额"""
    account = await ChartOfAccount.filter(
        id=account_id, account_set_id=account_set_id
    ).first()
    if not account:
        return None

    # 期初余额：start_period 之前所有已过账分录净额
    prior_entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name__lt=start_period,
        account_id=account_id,
    ).all()
    opening_debit = Decimal("0")
    opening_credit = Decimal("0")
    for e in prior_entries:
        opening_debit += e.debit_amount
        opening_credit += e.credit_amount

    if account.direction == "debit":
        opening_net = opening_debit - opening_credit
    else:
        opening_net = opening_credit - opening_debit

    # 本期分录
    period_entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name__gte=start_period,
        voucher__period_name__lte=end_period,
        account_id=account_id,
    ).order_by(
        "voucher__voucher_date", "voucher__voucher_no", "line_no"
    ).prefetch_related("voucher")

    running = opening_net
    rows = []
    period_debit_total = Decimal("0")
    period_credit_total = Decimal("0")

    for e in period_entries:
        if account.direction == "debit":
            running = running + e.debit_amount - e.credit_amount
        else:
            running = running + e.credit_amount - e.debit_amount
        period_debit_total += e.debit_amount
        period_credit_total += e.credit_amount
        rows.append({
            "date": str(e.voucher.voucher_date),
            "period_name": e.voucher.period_name,
            "voucher_no": e.voucher.voucher_no,
            "voucher_id": e.voucher.id,
            "summary": e.summary or e.voucher.summary,
            "debit": _dec_str(e.debit_amount),
            "credit": _dec_str(e.credit_amount),
            "direction": _direction_label(running, account.direction),
            "balance": _dec_str(abs(running)),
        })

    if account.direction == "debit":
        closing_net = opening_net + period_debit_total - period_credit_total
    else:
        closing_net = opening_net + period_credit_total - period_debit_total

    return {
        "account_id": account.id,
        "account_code": account.code,
        "account_name": account.name,
        "direction": account.direction,
        "start_period": start_period,
        "end_period": end_period,
        "opening_direction": _direction_label(opening_net, account.direction),
        "opening_balance": _dec_str(abs(opening_net)),
        "entries": rows,
        "period_debit_total": _dec_str(period_debit_total),
        "period_credit_total": _dec_str(period_credit_total),
        "closing_direction": _direction_label(closing_net, account.direction),
        "closing_balance": _dec_str(abs(closing_net)),
    }


async def get_detail_ledger(
    account_set_id: int,
    account_id: int,
    start_period: str,
    end_period: str,
    customer_id: int = None,
    supplier_id: int = None,
) -> dict | None:
    """明细分类账：与总分类账类似，支持辅助核算筛选"""
    account = await ChartOfAccount.filter(
        id=account_id, account_set_id=account_set_id
    ).first()
    if not account:
        return None

    base_filter = {
        "voucher__account_set_id": account_set_id,
        "voucher__status": "posted",
        "account_id": account_id,
    }
    if customer_id:
        base_filter["aux_customer_id"] = customer_id
    if supplier_id:
        base_filter["aux_supplier_id"] = supplier_id

    # 期初余额
    prior_entries = await VoucherEntry.filter(
        **base_filter, voucher__period_name__lt=start_period
    ).all()
    opening_debit = Decimal("0")
    opening_credit = Decimal("0")
    for e in prior_entries:
        opening_debit += e.debit_amount
        opening_credit += e.credit_amount
    if account.direction == "debit":
        opening_net = opening_debit - opening_credit
    else:
        opening_net = opening_credit - opening_debit

    # 本期分录
    period_entries = await VoucherEntry.filter(
        **base_filter,
        voucher__period_name__gte=start_period,
        voucher__period_name__lte=end_period,
    ).order_by(
        "voucher__voucher_date", "voucher__voucher_no", "line_no"
    ).prefetch_related("voucher", "aux_customer", "aux_supplier")

    running = opening_net
    rows = []
    period_debit_total = Decimal("0")
    period_credit_total = Decimal("0")

    for e in period_entries:
        if account.direction == "debit":
            running = running + e.debit_amount - e.credit_amount
        else:
            running = running + e.credit_amount - e.debit_amount
        period_debit_total += e.debit_amount
        period_credit_total += e.credit_amount
        row = {
            "date": str(e.voucher.voucher_date),
            "period_name": e.voucher.period_name,
            "voucher_no": e.voucher.voucher_no,
            "voucher_id": e.voucher.id,
            "summary": e.summary or e.voucher.summary,
            "debit": _dec_str(e.debit_amount),
            "credit": _dec_str(e.credit_amount),
            "direction": _direction_label(running, account.direction),
            "balance": _dec_str(abs(running)),
            "customer_name": e.aux_customer.name if e.aux_customer_id and e.aux_customer else None,
            "supplier_name": e.aux_supplier.name if e.aux_supplier_id and e.aux_supplier else None,
        }
        rows.append(row)

    if account.direction == "debit":
        closing_net = opening_net + period_debit_total - period_credit_total
    else:
        closing_net = opening_net + period_credit_total - period_debit_total

    return {
        "account_id": account.id,
        "account_code": account.code,
        "account_name": account.name,
        "direction": account.direction,
        "aux_customer": account.aux_customer,
        "aux_supplier": account.aux_supplier,
        "start_period": start_period,
        "end_period": end_period,
        "opening_direction": _direction_label(opening_net, account.direction),
        "opening_balance": _dec_str(abs(opening_net)),
        "entries": rows,
        "period_debit_total": _dec_str(period_debit_total),
        "period_credit_total": _dec_str(period_credit_total),
        "closing_direction": _direction_label(closing_net, account.direction),
        "closing_balance": _dec_str(abs(closing_net)),
    }


async def get_trial_balance(account_set_id: int, period_name: str) -> dict:
    """科目余额表：所有科目的期初、本期、期末余额 + 试算平衡"""
    accounts = await ChartOfAccount.filter(
        account_set_id=account_set_id, is_active=True
    ).order_by("code").all()

    if not accounts:
        return {
            "period_name": period_name, "accounts": [],
            "totals": {k: "0" for k in [
                "opening_debit", "opening_credit",
                "period_debit", "period_credit",
                "closing_debit", "closing_credit",
            ]},
            "is_balanced": True,
        }

    prior_entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name__lt=period_name,
    ).all()

    current_entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name=period_name,
    ).all()

    opening_by_acct = defaultdict(lambda: {"debit": Decimal("0"), "credit": Decimal("0")})
    for e in prior_entries:
        opening_by_acct[e.account_id]["debit"] += e.debit_amount
        opening_by_acct[e.account_id]["credit"] += e.credit_amount

    period_by_acct = defaultdict(lambda: {"debit": Decimal("0"), "credit": Decimal("0")})
    for e in current_entries:
        period_by_acct[e.account_id]["debit"] += e.debit_amount
        period_by_acct[e.account_id]["credit"] += e.credit_amount

    account_map = {a.id: a for a in accounts}

    leaf_balances = {}
    for a in accounts:
        if not a.is_leaf:
            continue
        opening = opening_by_acct.get(a.id, {"debit": Decimal("0"), "credit": Decimal("0")})
        period = period_by_acct.get(a.id, {"debit": Decimal("0"), "credit": Decimal("0")})
        if a.direction == "debit":
            opening_net = opening["debit"] - opening["credit"]
        else:
            opening_net = opening["credit"] - opening["debit"]
        period_debit = period["debit"]
        period_credit = period["credit"]
        if a.direction == "debit":
            closing_net = opening_net + period_debit - period_credit
        else:
            closing_net = opening_net + period_credit - period_debit
        leaf_balances[a.code] = {
            "opening_net": opening_net,
            "period_debit": period_debit,
            "period_credit": period_credit,
            "closing_net": closing_net,
        }

    all_balances = dict(leaf_balances)
    for a in sorted(accounts, key=lambda x: -len(x.code)):
        if a.parent_code and a.code in all_balances:
            if a.parent_code not in all_balances:
                all_balances[a.parent_code] = {
                    "opening_net": Decimal("0"),
                    "period_debit": Decimal("0"),
                    "period_credit": Decimal("0"),
                    "closing_net": Decimal("0"),
                }
            parent = all_balances[a.parent_code]
            child = all_balances[a.code]
            parent["opening_net"] += child["opening_net"]
            parent["period_debit"] += child["period_debit"]
            parent["period_credit"] += child["period_credit"]
            parent["closing_net"] += child["closing_net"]

    result_accounts = []
    totals = {
        "opening_debit": Decimal("0"), "opening_credit": Decimal("0"),
        "period_debit": Decimal("0"), "period_credit": Decimal("0"),
        "closing_debit": Decimal("0"), "closing_credit": Decimal("0"),
    }

    for a in accounts:
        bal = all_balances.get(a.code)
        if not bal:
            continue
        if all(v == 0 for v in bal.values()):
            continue
        o_debit, o_credit = _balance_display(bal["opening_net"], a.direction)
        c_debit, c_credit = _balance_display(bal["closing_net"], a.direction)
        result_accounts.append({
            "code": a.code,
            "name": a.name,
            "level": a.level,
            "is_leaf": a.is_leaf,
            "direction": a.direction,
            "opening_debit": _dec_str(o_debit),
            "opening_credit": _dec_str(o_credit),
            "period_debit": _dec_str(bal["period_debit"]),
            "period_credit": _dec_str(bal["period_credit"]),
            "closing_debit": _dec_str(c_debit),
            "closing_credit": _dec_str(c_credit),
        })
        if a.is_leaf:
            totals["opening_debit"] += o_debit
            totals["opening_credit"] += o_credit
            totals["period_debit"] += bal["period_debit"]
            totals["period_credit"] += bal["period_credit"]
            totals["closing_debit"] += c_debit
            totals["closing_credit"] += c_credit

    is_balanced = (
        totals["opening_debit"] == totals["opening_credit"]
        and totals["period_debit"] == totals["period_credit"]
        and totals["closing_debit"] == totals["closing_credit"]
    )

    return {
        "period_name": period_name,
        "accounts": result_accounts,
        "totals": {k: _dec_str(v) for k, v in totals.items()},
        "is_balanced": is_balanced,
    }
