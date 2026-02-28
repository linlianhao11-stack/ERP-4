# 阶段5：期末处理 + 财务报表 — 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现期末处理流程（损益结转→结账检查→期间锁定→年度结转）和三张财务报表（资产负债表、利润表、现金流量表），支持Excel和PDF双格式导出。

**Architecture:** 新建3个服务文件（period_end_service / report_service / report_export）+ 2个路由文件（period_end / financial_reports）。期末处理服务依赖现有 Voucher/VoucherEntry 模型生成"转"字凭证；报表服务复用 ledger_service 的余额计算模式；导出复用 ledger_export 的 openpyxl 样式和 pdf_print 的 reportlab 模式。前端新增2个Tab面板。

**Tech Stack:** FastAPI + Tortoise ORM + Pydantic / Vue 3 + Tailwind CSS 4 / openpyxl + reportlab

---

## 关键参考文件

| 文件 | 参考内容 |
|------|---------|
| `backend/app/services/ar_service.py` | `_next_voucher_no()` 凭证编号、`generate_ar_vouchers()` 凭证创建模式 |
| `backend/app/services/ledger_service.py` | `get_trial_balance()` 余额计算、`_dec_str()` / `_balance_display()` 工具函数 |
| `backend/app/services/ledger_export.py` | Excel 导出样式常量和布局模式 |
| `backend/app/utils/pdf_print.py` | PDF 生成、中文字体注册、`_fmt()` 格式化 |
| `backend/app/services/accounting_init.py` | 预置科目表（6xxx 损益类、4103/4104 权益类） |
| `backend/app/models/accounting.py` | AccountingPeriod（is_closed/closed_at/closed_by 已有字段） |
| `backend/app/models/voucher.py` | Voucher（source_type/source_bill_id）、VoucherEntry |
| `backend/app/routers/vouchers.py` | 路由模式、权限装饰器、分页、HTTPException |
| `backend/tests/test_ar_ap_service.py` | 测试 `_setup()` 模式、assert 模式 |
| `frontend/src/api/accounting.js` | API 函数命名模式 |
| `frontend/src/views/AccountingView.vue` | Tab 导航和面板渲染模式 |

---

## Task 1: 期末处理服务层 — 损益结转

**文件：** 创建 `backend/app/services/period_end_service.py`

**完整代码：**

```python
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
```

**验证：** `cd /Users/lin/Desktop/erp-4/backend && python3 -c "from app.services.period_end_service import preview_carry_forward; print('import ok')"`

**提交：** `feat: 期末处理服务层 — 损益结转 + 结账检查 + 结账/反结账 + 年度结转`

---

## Task 2: 财务报表服务层

**文件：** 创建 `backend/app/services/report_service.py`

**完整代码：**

```python
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
```

**验证：** `cd /Users/lin/Desktop/erp-4/backend && python3 -c "from app.services.report_service import get_balance_sheet; print('import ok')"`

**提交：** `feat: 财务报表服务层 — 资产负债表 + 利润表 + 现金流量表`

---

## Task 3: 报表导出服务（Excel + PDF）

**文件：** 创建 `backend/app/services/report_export.py`

**完整代码：**

```python
"""财务报表 Excel + PDF 导出"""
from __future__ import annotations

import io
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from reportlab.lib.units import cm, mm
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.utils.pdf_print import _ensure_font, FONT_NAME, _FONT_REGISTERED, _fmt
from app.logger import get_logger

logger = get_logger("report_export")

# ── Excel 样式常量（复用 ledger_export 模式）──
_HEADER_FONT = Font(bold=True, size=10)
_TITLE_FONT = Font(bold=True, size=14)
_SUB_TITLE_FONT = Font(bold=True, size=11)
_CENTER = Alignment(horizontal="center", vertical="center")
_RIGHT = Alignment(horizontal="right", vertical="center")
_LEFT = Alignment(horizontal="left", vertical="center")
_HEADER_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
_THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)


def _set_header_row(ws, row_num, headers):
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row_num, column=col, value=h)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _CENTER
        cell.border = _THIN_BORDER


# ═══════════════════════════════════════
# 资产负债表 Excel
# ═══════════════════════════════════════
def export_balance_sheet_excel(data: dict) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "资产负债表"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4)
    ws.cell(1, 1, value=f"资产负债表").font = _TITLE_FONT
    ws.cell(1, 1).alignment = _CENTER
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=4)
    ws.cell(2, 1, value=f"期间: {data['period_name']}").alignment = _CENTER

    # 资产侧
    _set_header_row(ws, 4, ["资产项目", "金额", "负债及所有者权益项目", "金额"])

    assets = data["assets"]
    liab = data["liabilities"]
    equity = data["equity"]

    # 构建左右对照行
    left_rows = [
        ("流动资产", ""),
        ("  库存现金", assets["current"]["cash"]),
        ("  银行存款", assets["current"]["bank"]),
        ("  应收账款", assets["current"]["accounts_receivable"]),
        ("  预付账款", assets["current"]["prepaid"]),
        ("  其他应收款", assets["current"]["other_receivable"]),
        ("  原材料", assets["current"]["raw_material"]),
        ("  库存商品", assets["current"]["inventory"]),
        ("  发出商品", assets["current"]["goods_in_transit"]),
        ("流动资产合计", assets["current"]["subtotal"]),
        ("", ""),
        ("非流动资产", ""),
        ("  固定资产", assets["non_current"]["fixed_assets"]),
        ("  累计折旧", assets["non_current"]["accumulated_depreciation"]),
        ("非流动资产合计", assets["non_current"]["subtotal"]),
        ("", ""),
        ("资产总计", assets["total"]),
    ]

    right_rows = [
        ("流动负债", ""),
        ("  短期借款", liab["current"]["short_term_loan"]),
        ("  应付账款", liab["current"]["accounts_payable"]),
        ("  预收账款", liab["current"]["advance_received"]),
        ("  应付职工薪酬", liab["current"]["salary_payable"]),
        ("  应交税费", liab["current"]["tax_payable"]),
        ("  其他应付款", liab["current"]["other_payable"]),
        ("流动负债合计", liab["current"]["subtotal"]),
        ("", ""),
        ("所有者权益", ""),
        ("  实收资本", equity["paid_capital"]),
        ("  盈余公积", equity["surplus_reserve"]),
        ("  本年利润", equity["current_profit"]),
        ("  未分配利润", equity["retained_earnings"]),
        ("所有者权益合计", equity["subtotal"]),
        ("", ""),
        ("负债和所有者权益总计", data["total_liabilities_equity"]),
    ]

    max_rows = max(len(left_rows), len(right_rows))
    for i in range(max_rows):
        row = 5 + i
        if i < len(left_rows):
            ws.cell(row, 1, value=left_rows[i][0])
            if left_rows[i][1]:
                ws.cell(row, 2, value=left_rows[i][1]).alignment = _RIGHT
            if left_rows[i][0] in ("流动资产合计", "非流动资产合计", "资产总计"):
                ws.cell(row, 1).font = _HEADER_FONT
                ws.cell(row, 2).font = _HEADER_FONT
        if i < len(right_rows):
            ws.cell(row, 3, value=right_rows[i][0])
            if right_rows[i][1]:
                ws.cell(row, 4, value=right_rows[i][1]).alignment = _RIGHT
            if right_rows[i][0] in ("流动负债合计", "所有者权益合计", "负债和所有者权益总计"):
                ws.cell(row, 3).font = _HEADER_FONT
                ws.cell(row, 4).font = _HEADER_FONT

    balanced = "平衡 ✓" if data["is_balanced"] else "不平衡 ✗"
    ws.cell(5 + max_rows + 1, 1, value=f"试算: {balanced}").font = Font(
        bold=True, color="008000" if data["is_balanced"] else "FF0000"
    )

    widths = [24, 16, 28, 16]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ═══════════════════════════════════════
# 利润表 Excel
# ═══════════════════════════════════════
def export_income_statement_excel(data: dict) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "利润表"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3)
    ws.cell(1, 1, value="利润表").font = _TITLE_FONT
    ws.cell(1, 1).alignment = _CENTER
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=3)
    ws.cell(2, 1, value=f"期间: {data['period_name']}").alignment = _CENTER

    _set_header_row(ws, 4, ["项目", "本期金额", "本年累计"])

    for i, r in enumerate(data["rows"], 5):
        ws.cell(i, 1, value=r["name"])
        ws.cell(i, 2, value=r["current"]).alignment = _RIGHT
        ws.cell(i, 3, value=r["ytd"]).alignment = _RIGHT
        if r["name"].startswith(("一", "二", "三", "四", "五")):
            ws.cell(i, 1).font = _HEADER_FONT
            ws.cell(i, 2).font = _HEADER_FONT
            ws.cell(i, 3).font = _HEADER_FONT

    widths = [30, 16, 16]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ═══════════════════════════════════════
# 现金流量表 Excel
# ═══════════════════════════════════════
def export_cash_flow_excel(data: dict) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "现金流量表"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2)
    ws.cell(1, 1, value="现金流量表").font = _TITLE_FONT
    ws.cell(1, 1).alignment = _CENTER
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=2)
    ws.cell(2, 1, value=f"期间: {data['period_name']}").alignment = _CENTER

    _set_header_row(ws, 4, ["项目", "金额"])
    row = 5

    sections = [
        ("一、经营活动产生的现金流量", data["operating"]),
        ("二、投资活动产生的现金流量", data["investing"]),
        ("三、筹资活动产生的现金流量", data["financing"]),
    ]

    for title, section in sections:
        ws.cell(row, 1, value=title).font = _SUB_TITLE_FONT
        row += 1
        for item in section["items"]:
            ws.cell(row, 1, value=f"  {item['label']}")
            ws.cell(row, 2, value=item["amount"]).alignment = _RIGHT
            row += 1
        ws.cell(row, 1, value=f"  {title[:5]}净额").font = _HEADER_FONT
        ws.cell(row, 2, value=section["net"]).alignment = _RIGHT
        ws.cell(row, 2).font = _HEADER_FONT
        row += 2

    ws.cell(row, 1, value="四、现金及现金等价物净增加额").font = _SUB_TITLE_FONT
    ws.cell(row, 2, value=data["net_increase"]).alignment = _RIGHT
    ws.cell(row, 2).font = _HEADER_FONT
    row += 1
    ws.cell(row, 1, value="  加：期初现金余额")
    ws.cell(row, 2, value=data["opening_cash"]).alignment = _RIGHT
    row += 1
    ws.cell(row, 1, value="  期末现金余额").font = _HEADER_FONT
    ws.cell(row, 2, value=data["closing_cash"]).alignment = _RIGHT
    ws.cell(row, 2).font = _HEADER_FONT

    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 18

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ═══════════════════════════════════════
# PDF 导出（A4 竖版）
# ═══════════════════════════════════════
def _pdf_font():
    _ensure_font()
    return FONT_NAME if _FONT_REGISTERED else "Helvetica"


def export_balance_sheet_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    font = _pdf_font()

    c.setFont(font, 16)
    c.drawCentredString(w / 2, h - 2 * cm, "资产负债表")
    c.setFont(font, 10)
    c.drawCentredString(w / 2, h - 2.8 * cm, f"期间: {data['period_name']}")

    y = h - 4 * cm
    c.setFont(font, 9)

    assets = data["assets"]
    liab = data["liabilities"]
    equity = data["equity"]

    left_x = 1.5 * cm
    left_val_x = 8 * cm
    right_x = 11 * cm
    right_val_x = 18 * cm

    def draw_pair(label_l, val_l, label_r, val_r, bold=False):
        nonlocal y
        if bold:
            c.setFont(font, 10)
        c.drawString(left_x, y, label_l)
        if val_l:
            c.drawRightString(left_val_x, y, _fmt(val_l))
        c.drawString(right_x, y, label_r)
        if val_r:
            c.drawRightString(right_val_x, y, _fmt(val_r))
        if bold:
            c.setFont(font, 9)
        y -= 0.5 * cm

    # 表头线
    c.line(left_x, y + 0.3 * cm, right_val_x + 1 * cm, y + 0.3 * cm)
    draw_pair("资产项目", "", "负债及所有者权益项目", "", bold=True)
    c.line(left_x, y + 0.3 * cm, right_val_x + 1 * cm, y + 0.3 * cm)

    draw_pair("流动资产", "", "流动负债", "")
    draw_pair("  库存现金", assets["current"]["cash"], "  短期借款", liab["current"]["short_term_loan"])
    draw_pair("  银行存款", assets["current"]["bank"], "  应付账款", liab["current"]["accounts_payable"])
    draw_pair("  应收账款", assets["current"]["accounts_receivable"], "  预收账款", liab["current"]["advance_received"])
    draw_pair("  预付账款", assets["current"]["prepaid"], "  应付职工薪酬", liab["current"]["salary_payable"])
    draw_pair("  其他应收款", assets["current"]["other_receivable"], "  应交税费", liab["current"]["tax_payable"])
    draw_pair("  原材料", assets["current"]["raw_material"], "  其他应付款", liab["current"]["other_payable"])
    draw_pair("  库存商品", assets["current"]["inventory"], "", "")
    draw_pair("  发出商品", assets["current"]["goods_in_transit"], "", "")
    draw_pair("流动资产合计", assets["current"]["subtotal"], "流动负债合计", liab["current"]["subtotal"], bold=True)

    draw_pair("", "", "", "")
    draw_pair("非流动资产", "", "所有者权益", "")
    draw_pair("  固定资产", assets["non_current"]["fixed_assets"], "  实收资本", equity["paid_capital"])
    draw_pair("  累计折旧", assets["non_current"]["accumulated_depreciation"], "  盈余公积", equity["surplus_reserve"])
    draw_pair("非流动资产合计", assets["non_current"]["subtotal"], "  本年利润", equity["current_profit"], bold=True)
    draw_pair("", "", "  未分配利润", equity["retained_earnings"])
    draw_pair("", "", "所有者权益合计", equity["subtotal"], bold=True)

    c.line(left_x, y + 0.3 * cm, right_val_x + 1 * cm, y + 0.3 * cm)
    draw_pair("资产总计", assets["total"], "负债和权益总计", data["total_liabilities_equity"], bold=True)
    c.line(left_x, y + 0.3 * cm, right_val_x + 1 * cm, y + 0.3 * cm)

    c.save()
    return buf.getvalue()


def export_income_statement_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    font = _pdf_font()

    c.setFont(font, 16)
    c.drawCentredString(w / 2, h - 2 * cm, "利润表")
    c.setFont(font, 10)
    c.drawCentredString(w / 2, h - 2.8 * cm, f"期间: {data['period_name']}")

    y = h - 4 * cm
    # 表头
    c.setFont(font, 10)
    c.line(2 * cm, y + 0.3 * cm, 19 * cm, y + 0.3 * cm)
    c.drawString(2 * cm, y, "项目")
    c.drawRightString(12 * cm, y, "本期金额")
    c.drawRightString(18 * cm, y, "本年累计")
    y -= 0.3 * cm
    c.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm

    c.setFont(font, 9)
    for r in data["rows"]:
        is_section = r["name"].startswith(("一", "二", "三", "四", "五"))
        if is_section:
            c.setFont(font, 10)
        c.drawString(2 * cm, y, r["name"])
        c.drawRightString(12 * cm, y, _fmt(r["current"]))
        c.drawRightString(18 * cm, y, _fmt(r["ytd"]))
        if is_section:
            c.setFont(font, 9)
        y -= 0.5 * cm

    c.line(2 * cm, y + 0.3 * cm, 19 * cm, y + 0.3 * cm)
    c.save()
    return buf.getvalue()


def export_cash_flow_pdf(data: dict) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    font = _pdf_font()

    c.setFont(font, 16)
    c.drawCentredString(w / 2, h - 2 * cm, "现金流量表")
    c.setFont(font, 10)
    c.drawCentredString(w / 2, h - 2.8 * cm, f"期间: {data['period_name']}")

    y = h - 4 * cm
    c.setFont(font, 10)
    c.line(2 * cm, y + 0.3 * cm, 19 * cm, y + 0.3 * cm)
    c.drawString(2 * cm, y, "项目")
    c.drawRightString(18 * cm, y, "金额")
    y -= 0.3 * cm
    c.line(2 * cm, y, 19 * cm, y)
    y -= 0.6 * cm

    sections = [
        ("一、经营活动产生的现金流量", data["operating"]),
        ("二、投资活动产生的现金流量", data["investing"]),
        ("三、筹资活动产生的现金流量", data["financing"]),
    ]

    c.setFont(font, 9)
    for title, section in sections:
        c.setFont(font, 10)
        c.drawString(2 * cm, y, title)
        y -= 0.5 * cm
        c.setFont(font, 9)
        for item in section["items"]:
            c.drawString(2.5 * cm, y, item["label"])
            c.drawRightString(18 * cm, y, _fmt(item["amount"]))
            y -= 0.5 * cm
        c.setFont(font, 10)
        c.drawString(2.5 * cm, y, "小计")
        c.drawRightString(18 * cm, y, _fmt(section["net"]))
        c.setFont(font, 9)
        y -= 0.8 * cm

    c.setFont(font, 10)
    c.line(2 * cm, y + 0.3 * cm, 19 * cm, y + 0.3 * cm)
    c.drawString(2 * cm, y, "四、现金及现金等价物净增加额")
    c.drawRightString(18 * cm, y, _fmt(data["net_increase"]))
    y -= 0.5 * cm
    c.setFont(font, 9)
    c.drawString(2.5 * cm, y, f"加：期初现金余额")
    c.drawRightString(18 * cm, y, _fmt(data["opening_cash"]))
    y -= 0.5 * cm
    c.setFont(font, 10)
    c.drawString(2.5 * cm, y, f"期末现金余额")
    c.drawRightString(18 * cm, y, _fmt(data["closing_cash"]))
    c.line(2 * cm, y - 0.2 * cm, 19 * cm, y - 0.2 * cm)

    c.save()
    return buf.getvalue()
```

**验证：** `cd /Users/lin/Desktop/erp-4/backend && python3 -c "from app.services.report_export import export_balance_sheet_excel; print('import ok')"`

**提交：** `feat: 报表导出服务 — 资产负债表/利润表/现金流量表 Excel+PDF`

---

## Task 4: 期末处理路由（6个端点）

**文件：**
- 创建 `backend/app/routers/period_end.py`
- 修改 `backend/main.py`（注册路由）

**period_end.py 完整代码：**

```python
"""期末处理路由"""
from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from app.services.period_end_service import (
    preview_carry_forward, execute_carry_forward,
    close_check, close_period, reopen_period, year_close,
)

router = APIRouter(prefix="/api/period-end", tags=["期末处理"])


@router.post("/carry-forward/preview")
async def api_carry_forward_preview(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("period_end")),
):
    try:
        return await preview_carry_forward(account_set_id, period_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/carry-forward")
async def api_carry_forward(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("period_end")),
):
    try:
        return await execute_carry_forward(account_set_id, period_name, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/close-check")
async def api_close_check(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("period_end")),
):
    return await close_check(account_set_id, period_name)


@router.post("/close")
async def api_close_period(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("period_end")),
):
    try:
        return await close_period(account_set_id, period_name, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reopen")
async def api_reopen_period(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("admin")),
):
    try:
        return await reopen_period(account_set_id, period_name, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/year-close")
async def api_year_close(
    account_set_id: int = Query(...),
    year: int = Query(...),
    user=Depends(require_permission("period_end")),
):
    try:
        return await year_close(account_set_id, year, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**main.py 变更：**
- 导入行追加 `period_end, financial_reports,`
- 路由注册追加 `app.include_router(period_end.router)` 和 `app.include_router(financial_reports.router)`

**验证：** `cd /Users/lin/Desktop/erp-4/backend && python3 -c "from app.routers.period_end import router; print('ok')"`

**提交：** `feat: 期末处理路由 — 6个端点`

---

## Task 5: 财务报表路由（6个端点）

**文件：** 创建 `backend/app/routers/financial_reports.py`

**完整代码：**

```python
"""财务报表路由"""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
import io
from app.auth.dependencies import get_current_user, require_permission
from app.services.report_service import get_balance_sheet, get_income_statement, get_cash_flow
from app.services.report_export import (
    export_balance_sheet_excel, export_income_statement_excel, export_cash_flow_excel,
    export_balance_sheet_pdf, export_income_statement_pdf, export_cash_flow_pdf,
)

router = APIRouter(prefix="/api/financial-reports", tags=["财务报表"])


@router.get("/balance-sheet")
async def api_balance_sheet(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("accounting_view")),
):
    return await get_balance_sheet(account_set_id, period_name)


@router.get("/income-statement")
async def api_income_statement(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("accounting_view")),
):
    return await get_income_statement(account_set_id, period_name)


@router.get("/cash-flow")
async def api_cash_flow(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("accounting_view")),
):
    return await get_cash_flow(account_set_id, period_name)


@router.get("/balance-sheet/export")
async def api_export_balance_sheet(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    format: str = Query("excel", regex="^(excel|pdf)$"),
    user=Depends(require_permission("accounting_view")),
):
    data = await get_balance_sheet(account_set_id, period_name)
    if format == "pdf":
        pdf_bytes = export_balance_sheet_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=balance_sheet_{period_name}.pdf"},
        )
    else:
        output = export_balance_sheet_excel(data)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=balance_sheet_{period_name}.xlsx"},
        )


@router.get("/income-statement/export")
async def api_export_income_statement(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    format: str = Query("excel", regex="^(excel|pdf)$"),
    user=Depends(require_permission("accounting_view")),
):
    data = await get_income_statement(account_set_id, period_name)
    if format == "pdf":
        pdf_bytes = export_income_statement_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=income_statement_{period_name}.pdf"},
        )
    else:
        output = export_income_statement_excel(data)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=income_statement_{period_name}.xlsx"},
        )


@router.get("/cash-flow/export")
async def api_export_cash_flow(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    format: str = Query("excel", regex="^(excel|pdf)$"),
    user=Depends(require_permission("accounting_view")),
):
    data = await get_cash_flow(account_set_id, period_name)
    if format == "pdf":
        pdf_bytes = export_cash_flow_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=cash_flow_{period_name}.pdf"},
        )
    else:
        output = export_cash_flow_excel(data)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=cash_flow_{period_name}.xlsx"},
        )
```

**验证：** `cd /Users/lin/Desktop/erp-4/backend && python3 -c "from app.routers.financial_reports import router; print('ok')"`

**提交：** `feat: 财务报表路由 — 资产负债表/利润表/现金流量表 查询+导出`

---

## Task 6: 后端测试 — 期末处理

**文件：** 创建 `backend/tests/test_period_end.py`

**完整代码：**

```python
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
```

**验证：** `cd /Users/lin/Desktop/erp-4/backend && python3 -m pytest tests/test_period_end.py -v`

**提交：** `test: 期末处理测试 — 10个用例`

---

## Task 7: 后端测试 — 财务报表

**文件：** 创建 `backend/tests/test_reports.py`

**完整代码：**

```python
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
    # 期初不含1月的数据（因为cash_flow只看本期间,但opening_cash看年初至period之前）
    # opening_cash = 年初之前的余额 = 0（2026-01之前没有数据）
    # 但这里我们看的是2026-02, opening_cash是2026-01之前的=0
    # 实际上该测试中1月凭证的period是2026-01, opening是<2026-01的，所以是0
    # net_increase for 2026-02 = 10000
    assert Decimal(cf["net_increase"]) == Decimal("10000")
    assert Decimal(cf["closing_cash"]) == Decimal(cf["opening_cash"]) + Decimal(cf["net_increase"])


async def test_balance_sheet_empty():
    a, u, accts = await _setup()
    bs = await get_balance_sheet(a.id, "2026-01")
    assert bs["is_balanced"] is True
    assert bs["assets"]["total"] == "0"
```

**验证：** `cd /Users/lin/Desktop/erp-4/backend && python3 -m pytest tests/test_reports.py -v`

**提交：** `test: 财务报表测试 — 8个用例`

---

## Task 8: 前端 API 层 + 迁移

**文件：**
- 修改 `frontend/src/api/accounting.js`（追加12个API函数）
- 修改 `backend/app/migrations.py`（追加 `migrate_accounting_phase5()`）

**accounting.js 追加内容：**

```javascript
// ========== 期末处理 ==========
export const previewCarryForward = (accountSetId, periodName) =>
  api.post('/period-end/carry-forward/preview', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const executeCarryForward = (accountSetId, periodName) =>
  api.post('/period-end/carry-forward', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const closeCheck = (accountSetId, periodName) =>
  api.post('/period-end/close-check', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const closePeriod = (accountSetId, periodName) =>
  api.post('/period-end/close', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const reopenPeriod = (accountSetId, periodName) =>
  api.post('/period-end/reopen', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const yearClose = (accountSetId, year) =>
  api.post('/period-end/year-close', null, { params: { account_set_id: accountSetId, year } })

// ========== 财务报表 ==========
export const getBalanceSheet = (params) => api.get('/financial-reports/balance-sheet', { params })
export const getIncomeStatement = (params) => api.get('/financial-reports/income-statement', { params })
export const getCashFlow = (params) => api.get('/financial-reports/cash-flow', { params })
export const exportBalanceSheet = (params) =>
  api.get('/financial-reports/balance-sheet/export', { params, responseType: 'blob' })
export const exportIncomeStatement = (params) =>
  api.get('/financial-reports/income-statement/export', { params, responseType: 'blob' })
export const exportCashFlow = (params) =>
  api.get('/financial-reports/cash-flow/export', { params, responseType: 'blob' })
```

**migrations.py 追加：**
- 在 `run_migrations()` 中添加 `await migrate_accounting_phase5()` 调用
- 新增 `migrate_accounting_phase5()` 函数：无新表（使用现有 AccountingPeriod 字段），仅确保 `generate_schemas(safe=True)` 和 admin 权限检查

```python
async def migrate_accounting_phase5():
    """阶段5迁移：确保 period_end 权限（幂等）"""
    admin = await User.filter(username="admin").first()
    if admin:
        current = admin.permissions or []
        # period_end 权限应该在 phase1 已添加，这里只是确认
        if "period_end" not in current:
            admin.permissions = current + ["period_end"]
            await admin.save()
            logger.info("admin 用户补充 period_end 权限")
    logger.info("阶段5迁移完成")
```

**验证：** `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`

**提交：** `feat: 前端API层 — 期末处理+财务报表12个接口 + 阶段5迁移`

---

## Task 9: 期末处理面板

**文件：** 创建 `frontend/src/components/business/PeriodEndPanel.vue`

**完整组件功能：**

1. **当前期间状态卡片** — 显示当前期间名称 + 是否已结账
2. **损益结转区域**：
   - "预览结转" 按钮 → 调用 `previewCarryForward` → 显示结转分录预览表格
   - 预览表格：科目编码、科目名称、借方、贷方、摘要
   - "确认执行" 按钮 → 调用 `executeCarryForward` → 显示结果（凭证号 + 本期利润）
   - 幂等提示：如果已存在结转凭证，显示已有凭证号
3. **结账检查区域**：
   - "执行检查" 按钮 → 调用 `closeCheck` → 显示5项检查清单
   - 每项检查：绿色 ✓ / 红色 ✗ + 详情文字
   - 全部通过后显示 "结账" 按钮 → 调用 `closePeriod`
4. **年度结转区域**（仅12月显示）：
   - "年度结转" 按钮 → 调用 `yearClose` → 显示结果
5. **反结账按钮**（admin 且期间已结账时显示）：
   - confirm 确认后调用 `reopenPeriod`
6. **期间历史列表**：当前年度所有期间 + 状态标签

**UI 模式（参考 VoucherPanel.vue / ReceivablePanel.vue）：**
- CSS 类：`.input` / `.label` / `.btn` / `.badge-green` / `.badge-red`
- 状态卡片：`bg-[#f5f5f7] rounded-xl p-4`
- 按钮：`btn btn-primary` / `btn btn-secondary`
- 表格：`.table-container > table.w-full`
- 检查清单：`space-y-2` 每项一行

**验证：** `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`

**提交：** `feat: 期末处理面板 — 损益结转+结账检查+年度结转+反结账`

---

## Task 10: 财务报表面板 + AccountingView 注册

**文件：**
- 创建 `frontend/src/components/business/FinancialReportPanel.vue`（容器 + 3子Tab）
- 创建 `frontend/src/components/business/BalanceSheetTab.vue`
- 创建 `frontend/src/components/business/IncomeStatementTab.vue`
- 创建 `frontend/src/components/business/CashFlowTab.vue`
- 修改 `frontend/src/views/AccountingView.vue`（2个新Tab）

**FinancialReportPanel.vue：**
- 顶部：期间选择器（下拉选择年+月） + 查询按钮
- 3个子Tab：资产负债表 / 利润表 / 现金流量表
- 每个子Tab 右上角：导出下拉（Excel / PDF）

**BalanceSheetTab.vue：**
- 接收 props: `data`（资产负债表数据）
- 左右两栏布局（grid-cols-2）
- 左侧：资产项目列表（流动资产 + 非流动资产 + 资产总计）
- 右侧：负债 + 所有者权益列表
- 底部：平衡状态标签

**IncomeStatementTab.vue：**
- 接收 props: `data`（利润表数据）
- 表格：项目 | 本期金额 | 本年累计
- 大类标题加粗显示

**CashFlowTab.vue：**
- 接收 props: `data`（现金流量表数据）
- 三段式布局：经营/投资/筹资
- 每段：明细行 + 小计
- 底部：净增加额 + 期初/期末余额

**AccountingView.vue 变更：**
1. 新增 import: `PeriodEndPanel`, `FinancialReportPanel`
2. Tab 导航新增: "期末处理" 和 "财务报表"
3. Panel 渲染新增: `<PeriodEndPanel v-if="tab === 'period-end'" />` 和 `<FinancialReportPanel v-if="tab === 'reports'" />`

**验证：** `cd /Users/lin/Desktop/erp-4/frontend && npx vite build`

**提交：** `feat: 财务报表面板 — 资产负债表/利润表/现金流量表 + AccountingView注册`

---

## 验证清单

```bash
# 后端全量测试
cd /Users/lin/Desktop/erp-4/backend && python3 -m pytest tests/ -v --ignore=tests/test_auth.py

# 前端构建
cd /Users/lin/Desktop/erp-4/frontend && npx vite build

# Docker 构建部署
cd /Users/lin/Desktop/erp-4 && docker compose build && docker compose up -d
```

**手动集成测试：**
1. 录入收入/成本凭证 → 过账
2. 期末处理 → 预览结转 → 确认执行 → 验证"转"字凭证
3. 结账检查 → 5项全绿 → 结账 → 期间锁定
4. 12月结账 → 年度结转（4103→4104）→ 下年期间初始化
5. 反结账（admin）→ 期间解锁
6. 资产负债表 → 左右平衡
7. 利润表 → 本期+累计
8. 现金流量表 → 经营/投资/筹资分类
9. 导出 Excel / PDF → 下载验证
