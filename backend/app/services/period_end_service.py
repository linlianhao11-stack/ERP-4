"""期末处理服务：损益结转 + 结账检查 + 结账 + 年度结转"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from tortoise import transactions
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.models.ar_ap import ReceiptBill, ReceiptRefundBill, ReceivableWriteOff, DisbursementBill, DisbursementRefundBill
from app.logger import get_logger

logger = get_logger("period_end_service")


def _dec_str(d: Decimal) -> str:
    return format(d.normalize(), 'f')


async def _next_voucher_no(account_set_id: int, voucher_type: str, period_name: str) -> str:
    account_set = await AccountSet.filter(id=account_set_id).first()
    prefix = f"{account_set.code}-{voucher_type}-{period_name.replace('-', '')}-"
    last = await Voucher.filter(
        account_set_id=account_set_id,
        voucher_type=voucher_type,
        period_name=period_name,
    ).order_by("-voucher_no").first()
    if last and last.voucher_no.startswith(prefix):
        seq = int(last.voucher_no[len(prefix):]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


async def preview_carry_forward(account_set_id: int, period_name: str) -> dict:
    """损益结转预览：返回将要生成的分录明细"""
    # 检查是否已有结转凭证
    existing = await Voucher.filter(
        account_set_id=account_set_id,
        period_name=period_name,
        source_type="period_end_carry_forward",
    ).first()
    if existing:
        return {"already_exists": True, "voucher_no": existing.voucher_no, "entries": []}

    # 查询本年利润科目
    profit_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="4103", is_active=True
    ).first()
    if not profit_account:
        raise ValueError("缺少科目: 4103 本年利润")

    # 查询所有损益类叶子科目
    pl_accounts = await ChartOfAccount.filter(
        account_set_id=account_set_id, category="profit_loss", is_leaf=True, is_active=True
    ).order_by("code").all()

    if not pl_accounts:
        return {"already_exists": False, "entries": [], "total_profit": "0"}

    # 计算每个损益科目的本期已过账发生额
    entries = []
    total_profit = Decimal("0")  # 贷方净额 = 收入-成本

    for acct in pl_accounts:
        period_entries = await VoucherEntry.filter(
            voucher__account_set_id=account_set_id,
            voucher__status="posted",
            voucher__period_name=period_name,
            account_id=acct.id,
        ).all()
        debit_sum = sum(e.debit_amount for e in period_entries)
        credit_sum = sum(e.credit_amount for e in period_entries)

        if debit_sum == 0 and credit_sum == 0:
            continue

        if acct.direction == "credit":
            # 收入类：贷方净额 → 借方转出, 贷方转入4103
            net = credit_sum - debit_sum
            if net != 0:
                entries.append({
                    "account_code": acct.code,
                    "account_name": acct.name,
                    "direction": acct.direction,
                    "debit_amount": _dec_str(abs(net)) if net > 0 else "0",
                    "credit_amount": _dec_str(abs(net)) if net < 0 else "0",
                    "summary": f"结转{acct.name}",
                })
                total_profit += net
        else:
            # 成本费用类：借方净额 → 贷方转出, 借方转入4103
            net = debit_sum - credit_sum
            if net != 0:
                entries.append({
                    "account_code": acct.code,
                    "account_name": acct.name,
                    "direction": acct.direction,
                    "debit_amount": _dec_str(abs(net)) if net < 0 else "0",
                    "credit_amount": _dec_str(abs(net)) if net > 0 else "0",
                    "summary": f"结转{acct.name}",
                })
                total_profit -= net

    return {
        "already_exists": False,
        "entries": entries,
        "total_profit": _dec_str(total_profit),
        "profit_account": {"code": "4103", "name": "本年利润"},
    }


async def execute_carry_forward(account_set_id: int, period_name: str, user) -> dict:
    """执行损益结转：生成转字凭证"""
    # 幂等检查
    existing = await Voucher.filter(
        account_set_id=account_set_id,
        period_name=period_name,
        source_type="period_end_carry_forward",
    ).first()
    if existing:
        return {"voucher_id": existing.id, "voucher_no": existing.voucher_no, "already_existed": True}

    profit_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="4103", is_active=True
    ).first()
    if not profit_account:
        raise ValueError("缺少科目: 4103 本年利润")

    pl_accounts = await ChartOfAccount.filter(
        account_set_id=account_set_id, category="profit_loss", is_leaf=True, is_active=True
    ).order_by("code").all()

    voucher_entries = []
    total_profit = Decimal("0")

    for acct in pl_accounts:
        period_entries = await VoucherEntry.filter(
            voucher__account_set_id=account_set_id,
            voucher__status="posted",
            voucher__period_name=period_name,
            account_id=acct.id,
        ).all()
        debit_sum = sum(e.debit_amount for e in period_entries)
        credit_sum = sum(e.credit_amount for e in period_entries)

        if debit_sum == 0 and credit_sum == 0:
            continue

        if acct.direction == "credit":
            net = credit_sum - debit_sum
            if net != 0:
                # 收入结转：借 收入科目 / 贷 本年利润 (net>0)
                # 或 借 本年利润 / 贷 收入科目 (net<0)
                voucher_entries.append({
                    "account_id": acct.id,
                    "summary": f"结转{acct.name}",
                    "debit_amount": abs(net) if net > 0 else Decimal("0"),
                    "credit_amount": abs(net) if net < 0 else Decimal("0"),
                })
                total_profit += net
        else:
            net = debit_sum - credit_sum
            if net != 0:
                # 成本结转：贷 成本科目 / 借 本年利润 (net>0)
                # 或 贷 本年利润 / 借 成本科目 (net<0)
                voucher_entries.append({
                    "account_id": acct.id,
                    "summary": f"结转{acct.name}",
                    "debit_amount": abs(net) if net < 0 else Decimal("0"),
                    "credit_amount": abs(net) if net > 0 else Decimal("0"),
                })
                total_profit -= net

    if not voucher_entries:
        return {"voucher_id": None, "voucher_no": None, "message": "本期无损益发生额"}

    # 添加本年利润汇总分录
    if total_profit > 0:
        voucher_entries.append({
            "account_id": profit_account.id,
            "summary": "结转本期损益",
            "debit_amount": Decimal("0"),
            "credit_amount": total_profit,
        })
    elif total_profit < 0:
        voucher_entries.append({
            "account_id": profit_account.id,
            "summary": "结转本期损益",
            "debit_amount": abs(total_profit),
            "credit_amount": Decimal("0"),
        })

    # 计算借贷合计
    total_debit = sum(e["debit_amount"] for e in voucher_entries)
    total_credit = sum(e["credit_amount"] for e in voucher_entries)

    async with transactions.in_transaction():
        vno = await _next_voucher_no(account_set_id, "转", period_name)

        # 获取期间最后一天作为凭证日期
        period = await AccountingPeriod.filter(
            account_set_id=account_set_id, period_name=period_name
        ).first()
        if period:
            import calendar
            last_day = calendar.monthrange(period.year, period.month)[1]
            v_date = date(period.year, period.month, last_day)
        else:
            v_date = date.today()

        voucher = await Voucher.create(
            account_set_id=account_set_id,
            voucher_type="转",
            voucher_no=vno,
            period_name=period_name,
            voucher_date=v_date,
            summary="期末损益结转",
            total_debit=total_debit,
            total_credit=total_credit,
            status="posted",
            creator=user,
            posted_by=user,
            posted_at=datetime.now(timezone.utc),
            source_type="period_end_carry_forward",
        )

        for i, entry in enumerate(voucher_entries, 1):
            await VoucherEntry.create(
                voucher=voucher,
                line_no=i,
                account_id=entry["account_id"],
                summary=entry["summary"],
                debit_amount=entry["debit_amount"],
                credit_amount=entry["credit_amount"],
            )

    logger.info(f"损益结转完成: {vno}, 本期利润: {total_profit}")
    return {"voucher_id": voucher.id, "voucher_no": vno, "total_profit": _dec_str(total_profit)}


async def close_check(account_set_id: int, period_name: str) -> list[dict]:
    """结账5项检查，返回检查结果列表"""
    results = []

    # 1. 凭证已过账
    unposted = await Voucher.filter(
        account_set_id=account_set_id,
        period_name=period_name,
    ).exclude(status="posted").count()
    results.append({
        "item": "凭证已过账",
        "passed": unposted == 0,
        "detail": f"本期有 {unposted} 张凭证未过账" if unposted > 0 else "所有凭证已过账",
    })

    # 2. 试算平衡
    entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name=period_name,
    ).all()
    total_debit = sum(e.debit_amount for e in entries)
    total_credit = sum(e.credit_amount for e in entries)
    balanced = total_debit == total_credit
    results.append({
        "item": "试算平衡",
        "passed": balanced,
        "detail": f"借方合计: {_dec_str(total_debit)}, 贷方合计: {_dec_str(total_credit)}" if not balanced else "借贷平衡",
    })

    # 3. 损益已结转
    pl_accounts = await ChartOfAccount.filter(
        account_set_id=account_set_id, category="profit_loss", is_leaf=True, is_active=True
    ).all()
    pl_has_balance = False
    for acct in pl_accounts:
        acct_entries = await VoucherEntry.filter(
            voucher__account_set_id=account_set_id,
            voucher__status="posted",
            voucher__period_name=period_name,
            account_id=acct.id,
        ).all()
        d = sum(e.debit_amount for e in acct_entries)
        c = sum(e.credit_amount for e in acct_entries)
        if d != c:
            pl_has_balance = True
            break
    results.append({
        "item": "损益已结转",
        "passed": not pl_has_balance,
        "detail": "损益类科目本期借贷不平，请先执行损益结转" if pl_has_balance else "损益科目已结转",
    })

    # 4. 无草稿AR/AP凭证（已确认但未生成凭证的单据）
    draft_count = 0
    draft_count += await ReceiptBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None
    ).count()
    draft_count += await ReceiptRefundBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None
    ).count()
    draft_count += await ReceivableWriteOff.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None
    ).count()
    draft_count += await DisbursementBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None
    ).count()
    draft_count += await DisbursementRefundBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None
    ).count()
    results.append({
        "item": "AR/AP凭证已生成",
        "passed": draft_count == 0,
        "detail": f"有 {draft_count} 张已确认单据未生成凭证" if draft_count > 0 else "所有已确认单据已生成凭证",
    })

    # 5. 上期已结账
    year, month = int(period_name[:4]), int(period_name[5:7])
    if month == 1:
        prev_period = f"{year - 1}-12"
    else:
        prev_period = f"{year}-{month - 1:02d}"
    prev = await AccountingPeriod.filter(
        account_set_id=account_set_id, period_name=prev_period
    ).first()
    # 首期免检
    account_set = await AccountSet.filter(id=account_set_id).first()
    first_period = f"{account_set.start_year}-{account_set.start_month:02d}"
    if period_name == first_period:
        prev_ok = True
        prev_detail = "首个会计期间，无需检查上期"
    elif not prev:
        prev_ok = True
        prev_detail = "上期不存在，视为通过"
    else:
        prev_ok = prev.is_closed
        prev_detail = f"上期 {prev_period} {'已结账' if prev.is_closed else '未结账'}"
    results.append({
        "item": "上期已结账",
        "passed": prev_ok,
        "detail": prev_detail,
    })

    return results


async def close_period(account_set_id: int, period_name: str, user) -> dict:
    """执行结账：锁定期间"""
    # 先执行检查
    checks = await close_check(account_set_id, period_name)
    failed = [c for c in checks if not c["passed"]]
    if failed:
        raise ValueError(f"结账检查未通过: {'; '.join(c['detail'] for c in failed)}")

    period = await AccountingPeriod.filter(
        account_set_id=account_set_id, period_name=period_name
    ).first()
    if not period:
        raise ValueError(f"会计期间 {period_name} 不存在")
    if period.is_closed:
        return {"period_name": period_name, "already_closed": True}

    period.is_closed = True
    period.closed_at = datetime.now(timezone.utc)
    period.closed_by = user
    await period.save()

    logger.info(f"期间 {period_name} 已结账")
    return {"period_name": period_name, "already_closed": False, "closed_at": str(period.closed_at)}


async def reopen_period(account_set_id: int, period_name: str, user) -> dict:
    """反结账：解锁期间（仅admin）"""
    period = await AccountingPeriod.filter(
        account_set_id=account_set_id, period_name=period_name
    ).first()
    if not period:
        raise ValueError(f"会计期间 {period_name} 不存在")
    if not period.is_closed:
        return {"period_name": period_name, "message": "该期间未结账"}

    # 如果是12月反结账，需要删除年度结转凭证
    if period.month == 12:
        year_close_voucher = await Voucher.filter(
            account_set_id=account_set_id,
            period_name=period_name,
            source_type="year_end_close",
        ).first()
        if year_close_voucher:
            await VoucherEntry.filter(voucher=year_close_voucher).delete()
            await year_close_voucher.delete()
            logger.info(f"已删除年度结转凭证: {year_close_voucher.voucher_no}")

    period.is_closed = False
    period.closed_at = None
    period.closed_by = None
    await period.save()

    logger.info(f"期间 {period_name} 已反结账")
    return {"period_name": period_name, "reopened": True}


async def year_close(account_set_id: int, year: int, user) -> dict:
    """年度结转：4103本年利润 → 4104利润分配-未分配利润 + 初始化下年期间"""
    period_name = f"{year}-12"
    period = await AccountingPeriod.filter(
        account_set_id=account_set_id, period_name=period_name
    ).first()
    if not period:
        raise ValueError(f"会计期间 {period_name} 不存在")

    # 幂等检查
    existing = await Voucher.filter(
        account_set_id=account_set_id,
        period_name=period_name,
        source_type="year_end_close",
    ).first()
    if existing:
        return {"voucher_id": existing.id, "voucher_no": existing.voucher_no, "already_existed": True}

    # 查询4103本年利润的年度累计余额
    profit_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="4103", is_active=True
    ).first()
    retained_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="4104", is_active=True
    ).first()
    if not profit_account or not retained_account:
        raise ValueError("缺少科目: 4103 本年利润 或 4104 利润分配-未分配利润")

    # 计算4103年度累计净额（credit方向）
    year_entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name__gte=f"{year}-01",
        voucher__period_name__lte=f"{year}-12",
        account_id=profit_account.id,
    ).all()
    total_debit = sum(e.debit_amount for e in year_entries)
    total_credit = sum(e.credit_amount for e in year_entries)
    net_profit = total_credit - total_debit  # 4103 是 credit 方向

    if net_profit == 0:
        result = {"voucher_id": None, "message": "本年利润为零，无需结转"}
    else:
        async with transactions.in_transaction():
            vno = await _next_voucher_no(account_set_id, "转", period_name)
            import calendar
            last_day = calendar.monthrange(year, 12)[1]
            v_date = date(year, 12, last_day)

            abs_profit = abs(net_profit)
            if net_profit > 0:
                # 盈利：借 本年利润 / 贷 利润分配
                d_acct, c_acct = profit_account.id, retained_account.id
            else:
                # 亏损：借 利润分配 / 贷 本年利润
                d_acct, c_acct = retained_account.id, profit_account.id

            voucher = await Voucher.create(
                account_set_id=account_set_id,
                voucher_type="转",
                voucher_no=vno,
                period_name=period_name,
                voucher_date=v_date,
                summary=f"{year}年度利润结转",
                total_debit=abs_profit,
                total_credit=abs_profit,
                status="posted",
                creator=user,
                posted_by=user,
                posted_at=datetime.now(timezone.utc),
                source_type="year_end_close",
            )
            await VoucherEntry.create(
                voucher=voucher, line_no=1,
                account_id=d_acct,
                summary=f"{year}年度利润结转",
                debit_amount=abs_profit,
                credit_amount=Decimal("0"),
            )
            await VoucherEntry.create(
                voucher=voucher, line_no=2,
                account_id=c_acct,
                summary=f"{year}年度利润结转",
                debit_amount=Decimal("0"),
                credit_amount=abs_profit,
            )
        result = {"voucher_id": voucher.id, "voucher_no": vno, "net_profit": _dec_str(net_profit)}

    # 初始化下一年度12个会计期间
    next_year = year + 1
    created_periods = 0
    for m in range(1, 13):
        pn = f"{next_year}-{m:02d}"
        exists = await AccountingPeriod.filter(
            account_set_id=account_set_id, period_name=pn
        ).exists()
        if not exists:
            await AccountingPeriod.create(
                account_set_id=account_set_id,
                period_name=pn,
                year=next_year,
                month=m,
            )
            created_periods += 1

    if created_periods > 0:
        logger.info(f"已初始化 {next_year} 年度 {created_periods} 个会计期间")

    result["next_year_periods_created"] = created_periods
    logger.info(f"年度结转完成: {year}")
    return result
