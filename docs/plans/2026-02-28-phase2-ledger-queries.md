# Phase 2: 账簿查询 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于已过账凭证，提供总分类账、明细分类账和科目余额表三种专业财务查询视图，支持 Excel 导出。

**Architecture:** 新建 `services/ledger_service.py` 封装三种账簿的核心计算逻辑（期初余额、本期发生、期末余额），新建 `routers/ledgers.py` 提供 6 个 API（3 查询 + 3 导出），前端在 AccountingView 新增"账簿查询" Tab，内含三个子面板。所有查询仅基于 `status="posted"` 的凭证分录。

**Tech Stack:** FastAPI + Tortoise ORM + openpyxl (Excel) / Vue 3.5 + Pinia + Tailwind CSS 4

**关键设计决策：**
- 余额计算：`期初余额 = 该科目所有已过账分录在起始期间之前的净额`
- 余额方向：借方科目 net = debit - credit（正=借余额）；贷方科目 net = credit - debit（正=贷余额）
- 科目余额表含父科目汇总（子科目金额向上累加）
- 试算平衡验证：期初借合计=贷合计、本期借发生=贷发生、期末借合计=贷合计
- 导出格式：Excel（openpyxl），保持与现有 stock/products 导出模式一致

---

### Task 1: Backend — 账簿服务核心计算

**Files:**
- Create: `backend/app/services/ledger_service.py`

**Context:**
- 凭证模型在 `app/models/voucher.py`：Voucher（含 account_set_id, period_name, status）和 VoucherEntry（含 account_id, debit_amount, credit_amount, aux_customer_id, aux_supplier_id）
- 科目模型在 `app/models/accounting.py`：ChartOfAccount（含 code, name, direction, is_leaf, parent_code, category, level, aux_customer, aux_supplier）
- 所有查询只看 `status="posted"` 的凭证
- Tortoise ORM 使用 `prefetch_related("voucher")` 来预加载外键关系（参考 `routers/vouchers.py:78`）

**Implementation:**

```python
"""账簿查询服务：总分类账、明细分类账、科目余额表"""
from decimal import Decimal
from collections import defaultdict
from app.models.accounting import ChartOfAccount
from app.models.voucher import Voucher, VoucherEntry


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
            "debit": str(e.debit_amount),
            "credit": str(e.credit_amount),
            "direction": _direction_label(running, account.direction),
            "balance": str(abs(running)),
        })

    closing_net = opening_net
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
        "opening_balance": str(abs(opening_net)),
        "entries": rows,
        "period_debit_total": str(period_debit_total),
        "period_credit_total": str(period_credit_total),
        "closing_direction": _direction_label(closing_net, account.direction),
        "closing_balance": str(abs(closing_net)),
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
            "debit": str(e.debit_amount),
            "credit": str(e.credit_amount),
            "direction": _direction_label(running, account.direction),
            "balance": str(abs(running)),
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
        "opening_balance": str(abs(opening_net)),
        "entries": rows,
        "period_debit_total": str(period_debit_total),
        "period_credit_total": str(period_credit_total),
        "closing_direction": _direction_label(closing_net, account.direction),
        "closing_balance": str(abs(closing_net)),
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

    # 批量获取期初分录（period_name 之前的所有已过账分录）
    prior_entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name__lt=period_name,
    ).all()

    # 批量获取本期分录
    current_entries = await VoucherEntry.filter(
        voucher__account_set_id=account_set_id,
        voucher__status="posted",
        voucher__period_name=period_name,
    ).all()

    # 按 account_id 汇总
    opening_by_acct = defaultdict(lambda: {"debit": Decimal("0"), "credit": Decimal("0")})
    for e in prior_entries:
        opening_by_acct[e.account_id]["debit"] += e.debit_amount
        opening_by_acct[e.account_id]["credit"] += e.credit_amount

    period_by_acct = defaultdict(lambda: {"debit": Decimal("0"), "credit": Decimal("0")})
    for e in current_entries:
        period_by_acct[e.account_id]["debit"] += e.debit_amount
        period_by_acct[e.account_id]["credit"] += e.credit_amount

    # 构建 account 映射
    account_map = {a.id: a for a in accounts}
    code_to_account = {a.code: a for a in accounts}

    # 叶子科目余额
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

    # 向上汇总到父科目
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

    # 格式化输出
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
            "opening_debit": str(o_debit),
            "opening_credit": str(o_credit),
            "period_debit": str(bal["period_debit"]),
            "period_credit": str(bal["period_credit"]),
            "closing_debit": str(c_debit),
            "closing_credit": str(c_credit),
        })

        # 只统计叶子科目的合计（避免与父科目重复）
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
        "totals": {k: str(v) for k, v in totals.items()},
        "is_balanced": is_balanced,
    }
```

---

### Task 2: Backend — 账簿服务测试

**Files:**
- Create: `backend/tests/test_ledger_service.py`

**Context:**
- 测试配置在 `tests/conftest.py`：使用 SQLite 内存 DB，`autouse=True` 的 `setup_db` fixture 自动初始化/清理
- 需要创建 AccountSet、ChartOfAccount、AccountingPeriod、Voucher（status="posted"）、VoucherEntry 作为测试数据
- 模型导入：`from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod`
- 模型导入：`from app.models.voucher import Voucher, VoucherEntry`

**Implementation:**

```python
"""账簿查询服务测试"""
import pytest
from decimal import Decimal
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.services.ledger_service import (
    get_general_ledger, get_detail_ledger, get_trial_balance,
    _direction_label, _balance_display,
)


async def _create_ledger_test_data():
    """创建账簿查询测试数据"""
    acc_set = await AccountSet.create(
        code="TEST", name="测试账套", start_year=2026, start_month=1,
        current_period="2026-03"
    )
    # 创建科目
    bank = await ChartOfAccount.create(
        account_set=acc_set, code="1002", name="银行存款",
        category="asset", direction="debit", is_leaf=True, level=1
    )
    ar = await ChartOfAccount.create(
        account_set=acc_set, code="1122", name="应收账款",
        category="asset", direction="debit", is_leaf=True, level=1,
        aux_customer=True
    )
    revenue = await ChartOfAccount.create(
        account_set=acc_set, code="6001", name="主营业务收入",
        category="profit_loss", direction="credit", is_leaf=True, level=1
    )
    # 创建期间
    for m in range(1, 4):
        await AccountingPeriod.create(
            account_set=acc_set, period_name=f"2026-{m:02d}", year=2026, month=m
        )
    # 凭证1: 2026-01 销售 — 借:应收10000 贷:收入10000
    v1 = await Voucher.create(
        account_set=acc_set, voucher_type="记",
        voucher_no="TEST-记-202601-001", period_name="2026-01",
        voucher_date="2026-01-15", total_debit=Decimal("10000"),
        total_credit=Decimal("10000"), status="posted"
    )
    await VoucherEntry.create(
        voucher=v1, line_no=1, account=ar,
        debit_amount=Decimal("10000"), credit_amount=Decimal("0"), summary="应收款"
    )
    await VoucherEntry.create(
        voucher=v1, line_no=2, account=revenue,
        debit_amount=Decimal("0"), credit_amount=Decimal("10000"), summary="销售收入"
    )
    # 凭证2: 2026-02 收款 — 借:银行5000 贷:应收5000
    v2 = await Voucher.create(
        account_set=acc_set, voucher_type="收",
        voucher_no="TEST-收-202602-001", period_name="2026-02",
        voucher_date="2026-02-10", total_debit=Decimal("5000"),
        total_credit=Decimal("5000"), status="posted"
    )
    await VoucherEntry.create(
        voucher=v2, line_no=1, account=bank,
        debit_amount=Decimal("5000"), credit_amount=Decimal("0"), summary="收款"
    )
    await VoucherEntry.create(
        voucher=v2, line_no=2, account=ar,
        debit_amount=Decimal("0"), credit_amount=Decimal("5000"), summary="冲应收"
    )
    # 凭证3: 2026-03 再销售 — 借:应收8000 贷:收入8000（draft，不应出现在查询中）
    v3 = await Voucher.create(
        account_set=acc_set, voucher_type="记",
        voucher_no="TEST-记-202603-001", period_name="2026-03",
        voucher_date="2026-03-05", total_debit=Decimal("8000"),
        total_credit=Decimal("8000"), status="draft"
    )
    await VoucherEntry.create(
        voucher=v3, line_no=1, account=ar,
        debit_amount=Decimal("8000"), credit_amount=Decimal("0")
    )
    await VoucherEntry.create(
        voucher=v3, line_no=2, account=revenue,
        debit_amount=Decimal("0"), credit_amount=Decimal("8000")
    )
    return acc_set, bank, ar, revenue


# --- 辅助函数测试 ---

async def test_direction_label():
    assert _direction_label(Decimal("0"), "debit") == "平"
    assert _direction_label(Decimal("100"), "debit") == "借"
    assert _direction_label(Decimal("-50"), "debit") == "贷"
    assert _direction_label(Decimal("100"), "credit") == "贷"
    assert _direction_label(Decimal("-50"), "credit") == "借"


async def test_balance_display():
    assert _balance_display(Decimal("100"), "debit") == (Decimal("100"), Decimal("0"))
    assert _balance_display(Decimal("-50"), "debit") == (Decimal("0"), Decimal("50"))
    assert _balance_display(Decimal("100"), "credit") == (Decimal("0"), Decimal("100"))
    assert _balance_display(Decimal("-50"), "credit") == (Decimal("50"), Decimal("0"))


# --- 总分类账测试 ---

async def test_general_ledger_opening_balance():
    """查询2026-02应收账款：期初=10000(来自01月), 本期贷方5000, 期末=5000"""
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_general_ledger(acc_set.id, ar.id, "2026-02", "2026-02")

    assert result is not None
    assert result["account_code"] == "1122"
    assert result["opening_balance"] == "10000"
    assert result["opening_direction"] == "借"
    assert len(result["entries"]) == 1
    assert result["entries"][0]["credit"] == "5000"
    assert result["entries"][0]["voucher_no"] == "TEST-收-202602-001"
    assert result["closing_balance"] == "5000"
    assert result["closing_direction"] == "借"


async def test_general_ledger_no_prior():
    """查询2026-01银行存款：期初=0, 无分录"""
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_general_ledger(acc_set.id, bank.id, "2026-01", "2026-01")

    assert result["opening_balance"] == "0"
    assert result["opening_direction"] == "平"
    assert len(result["entries"]) == 0


async def test_general_ledger_ignores_draft():
    """draft 凭证不应出现在查询结果中"""
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_general_ledger(acc_set.id, ar.id, "2026-03", "2026-03")

    assert len(result["entries"]) == 0
    assert result["opening_balance"] == "5000"  # 01月+10000, 02月-5000


async def test_general_ledger_credit_direction():
    """贷方科目（收入）余额方向正确"""
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_general_ledger(acc_set.id, revenue.id, "2026-02", "2026-02")

    assert result["opening_balance"] == "10000"  # 01月贷方10000
    assert result["opening_direction"] == "贷"
    assert len(result["entries"]) == 0  # 02月收入无发生
    assert result["closing_balance"] == "10000"


# --- 明细分类账测试 ---

async def test_detail_ledger_basic():
    """明细账基本查询"""
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_detail_ledger(acc_set.id, ar.id, "2026-01", "2026-02")

    assert result is not None
    assert len(result["entries"]) == 2  # 01月借+02月贷
    assert result["opening_balance"] == "0"
    assert result["closing_balance"] == "5000"


# --- 科目余额表测试 ---

async def test_trial_balance_is_balanced():
    """试算平衡验证"""
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_trial_balance(acc_set.id, "2026-02")

    assert result["is_balanced"] is True
    totals = result["totals"]
    assert totals["opening_debit"] == totals["opening_credit"]
    assert totals["period_debit"] == totals["period_credit"]
    assert totals["closing_debit"] == totals["closing_credit"]


async def test_trial_balance_accounts():
    """余额表科目数据正确"""
    acc_set, bank, ar, revenue = await _create_ledger_test_data()
    result = await get_trial_balance(acc_set.id, "2026-02")

    acct_map = {a["code"]: a for a in result["accounts"]}
    # 应收账款: 期初借10000, 本期贷5000, 期末借5000
    assert "1122" in acct_map
    ar_row = acct_map["1122"]
    assert ar_row["opening_debit"] == "10000"
    assert ar_row["period_credit"] == "5000"
    assert ar_row["closing_debit"] == "5000"
    # 银行存款: 期初0, 本期借5000, 期末借5000
    assert "1002" in acct_map
    bank_row = acct_map["1002"]
    assert bank_row["period_debit"] == "5000"
    assert bank_row["closing_debit"] == "5000"


async def test_trial_balance_empty():
    """无凭证时余额表为空"""
    acc_set = await AccountSet.create(
        code="EMPTY", name="空账套", start_year=2026, start_month=1,
        current_period="2026-01"
    )
    result = await get_trial_balance(acc_set.id, "2026-01")
    assert result["accounts"] == []
    assert result["is_balanced"] is True
```

**Run:** `source .venv/bin/activate && python -m pytest tests/test_ledger_service.py -v`

---

### Task 3: Backend — Excel 导出服务

**Files:**
- Create: `backend/app/services/ledger_export.py`

**Context:**
- 项目已安装 openpyxl 3.1.2（见 requirements.txt）
- 现有导出模式参考 `routers/stock.py:242`（CSV + StreamingResponse）
- 账簿导出用 openpyxl 生成 Excel 文件，返回 BytesIO 对象

**Implementation:**

```python
"""账簿 Excel 导出"""
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


_HEADER_FONT = Font(bold=True, size=10)
_TITLE_FONT = Font(bold=True, size=13)
_CENTER = Alignment(horizontal="center", vertical="center")
_RIGHT = Alignment(horizontal="right")
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


def export_general_ledger_excel(data: dict) -> io.BytesIO:
    """总分类账导出"""
    wb = Workbook()
    ws = wb.active
    ws.title = "总分类账"

    # 标题
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=7)
    title_cell = ws.cell(1, 1, value=f"总分类账 — {data['account_code']} {data['account_name']}")
    title_cell.font = _TITLE_FONT
    title_cell.alignment = _CENTER

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=7)
    ws.cell(2, 1, value=f"期间: {data['start_period']} 至 {data['end_period']}").alignment = _CENTER

    # 表头
    headers = ["日期", "凭证号", "摘要", "借方", "贷方", "方向", "余额"]
    _set_header_row(ws, 4, headers)

    # 期初余额行
    row = 5
    ws.cell(row, 3, value="期初余额")
    ws.cell(row, 6, value=data["opening_direction"])
    ws.cell(row, 7, value=data["opening_balance"]).alignment = _RIGHT
    row += 1

    # 分录
    for e in data["entries"]:
        ws.cell(row, 1, value=e["date"])
        ws.cell(row, 2, value=e["voucher_no"])
        ws.cell(row, 3, value=e["summary"])
        ws.cell(row, 4, value=e["debit"]).alignment = _RIGHT
        ws.cell(row, 5, value=e["credit"]).alignment = _RIGHT
        ws.cell(row, 6, value=e["direction"])
        ws.cell(row, 7, value=e["balance"]).alignment = _RIGHT
        row += 1

    # 本期合计
    ws.cell(row, 3, value="本期合计").font = _HEADER_FONT
    ws.cell(row, 4, value=data["period_debit_total"]).alignment = _RIGHT
    ws.cell(row, 5, value=data["period_credit_total"]).alignment = _RIGHT
    row += 1

    # 期末余额
    ws.cell(row, 3, value="期末余额").font = _HEADER_FONT
    ws.cell(row, 6, value=data["closing_direction"])
    ws.cell(row, 7, value=data["closing_balance"]).alignment = _RIGHT

    # 列宽
    widths = [12, 26, 30, 15, 15, 6, 15]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_detail_ledger_excel(data: dict) -> io.BytesIO:
    """明细分类账导出"""
    wb = Workbook()
    ws = wb.active
    ws.title = "明细分类账"

    has_aux = data.get("aux_customer") or data.get("aux_supplier")
    extra_headers = []
    if data.get("aux_customer"):
        extra_headers.append("客户")
    if data.get("aux_supplier"):
        extra_headers.append("供应商")

    col_count = 7 + len(extra_headers)

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=col_count)
    ws.cell(1, 1, value=f"明细分类账 — {data['account_code']} {data['account_name']}").font = _TITLE_FONT
    ws.cell(1, 1).alignment = _CENTER

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=col_count)
    ws.cell(2, 1, value=f"期间: {data['start_period']} 至 {data['end_period']}").alignment = _CENTER

    headers = ["日期", "凭证号", "摘要"] + extra_headers + ["借方", "贷方", "方向", "余额"]
    _set_header_row(ws, 4, headers)

    row = 5
    ws.cell(row, 3, value="期初余额")
    ws.cell(row, col_count - 1, value=data["opening_direction"])
    ws.cell(row, col_count, value=data["opening_balance"]).alignment = _RIGHT
    row += 1

    for e in data["entries"]:
        col = 1
        ws.cell(row, col, value=e["date"]); col += 1
        ws.cell(row, col, value=e["voucher_no"]); col += 1
        ws.cell(row, col, value=e["summary"]); col += 1
        if data.get("aux_customer"):
            ws.cell(row, col, value=e.get("customer_name") or ""); col += 1
        if data.get("aux_supplier"):
            ws.cell(row, col, value=e.get("supplier_name") or ""); col += 1
        ws.cell(row, col, value=e["debit"]).alignment = _RIGHT; col += 1
        ws.cell(row, col, value=e["credit"]).alignment = _RIGHT; col += 1
        ws.cell(row, col, value=e["direction"]); col += 1
        ws.cell(row, col, value=e["balance"]).alignment = _RIGHT
        row += 1

    offset = len(extra_headers)
    ws.cell(row, 3, value="本期合计").font = _HEADER_FONT
    ws.cell(row, 4 + offset, value=data["period_debit_total"]).alignment = _RIGHT
    ws.cell(row, 5 + offset, value=data["period_credit_total"]).alignment = _RIGHT
    row += 1
    ws.cell(row, 3, value="期末余额").font = _HEADER_FONT
    ws.cell(row, 6 + offset, value=data["closing_direction"])
    ws.cell(row, 7 + offset, value=data["closing_balance"]).alignment = _RIGHT

    widths = [12, 26, 30] + [14] * len(extra_headers) + [15, 15, 6, 15]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_trial_balance_excel(data: dict) -> io.BytesIO:
    """科目余额表导出"""
    wb = Workbook()
    ws = wb.active
    ws.title = "科目余额表"

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)
    ws.cell(1, 1, value=f"科目余额表 — {data['period_name']}").font = _TITLE_FONT
    ws.cell(1, 1).alignment = _CENTER

    # 两层表头
    ws.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    ws.cell(3, 1, value="科目编码").font = _HEADER_FONT
    ws.merge_cells(start_row=3, start_column=2, end_row=4, end_column=2)
    ws.cell(3, 2, value="科目名称").font = _HEADER_FONT

    ws.merge_cells(start_row=3, start_column=3, end_row=3, end_column=4)
    ws.cell(3, 3, value="期初余额").font = _HEADER_FONT
    ws.cell(3, 3).alignment = _CENTER
    ws.cell(4, 3, value="借方").font = _HEADER_FONT
    ws.cell(4, 4, value="贷方").font = _HEADER_FONT

    ws.merge_cells(start_row=3, start_column=5, end_row=3, end_column=6)
    ws.cell(3, 5, value="本期发生额").font = _HEADER_FONT
    ws.cell(3, 5).alignment = _CENTER
    ws.cell(4, 5, value="借方").font = _HEADER_FONT
    ws.cell(4, 6, value="贷方").font = _HEADER_FONT

    ws.merge_cells(start_row=3, start_column=7, end_row=3, end_column=8)
    ws.cell(3, 7, value="期末余额").font = _HEADER_FONT
    ws.cell(3, 7).alignment = _CENTER
    ws.cell(4, 7, value="借方").font = _HEADER_FONT
    ws.cell(4, 8, value="贷方").font = _HEADER_FONT

    for c in range(1, 9):
        ws.cell(3, c).fill = _HEADER_FILL
        ws.cell(4, c).fill = _HEADER_FILL

    row = 5
    for a in data["accounts"]:
        indent = "  " * (a["level"] - 1)
        ws.cell(row, 1, value=a["code"])
        ws.cell(row, 2, value=f"{indent}{a['name']}")
        ws.cell(row, 3, value=a["opening_debit"]).alignment = _RIGHT
        ws.cell(row, 4, value=a["opening_credit"]).alignment = _RIGHT
        ws.cell(row, 5, value=a["period_debit"]).alignment = _RIGHT
        ws.cell(row, 6, value=a["period_credit"]).alignment = _RIGHT
        ws.cell(row, 7, value=a["closing_debit"]).alignment = _RIGHT
        ws.cell(row, 8, value=a["closing_credit"]).alignment = _RIGHT
        if not a["is_leaf"]:
            for c in range(1, 9):
                ws.cell(row, c).font = _HEADER_FONT
        row += 1

    # 合计行
    t = data["totals"]
    ws.cell(row, 2, value="合  计").font = Font(bold=True, size=11)
    ws.cell(row, 3, value=t["opening_debit"]).alignment = _RIGHT
    ws.cell(row, 4, value=t["opening_credit"]).alignment = _RIGHT
    ws.cell(row, 5, value=t["period_debit"]).alignment = _RIGHT
    ws.cell(row, 6, value=t["period_credit"]).alignment = _RIGHT
    ws.cell(row, 7, value=t["closing_debit"]).alignment = _RIGHT
    ws.cell(row, 8, value=t["closing_credit"]).alignment = _RIGHT
    for c in range(1, 9):
        ws.cell(row, c).font = _HEADER_FONT

    row += 1
    balanced_text = "试算平衡" if data["is_balanced"] else "试算不平衡！"
    ws.cell(row, 2, value=balanced_text).font = Font(
        bold=True, color="008000" if data["is_balanced"] else "FF0000"
    )

    widths = [12, 24, 14, 14, 14, 14, 14, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
```

---

### Task 4: Backend — 账簿路由 + 注册

**Files:**
- Create: `backend/app/routers/ledgers.py`
- Modify: `backend/main.py:19-26` — 添加 ledgers 导入
- Modify: `backend/main.py:120-123` — 添加 `app.include_router(ledgers.router)`

**Context:**
- 路由权限：所有账簿查询使用 `require_permission("accounting_view")`
- 导出返回 StreamingResponse，Content-Disposition 使用 UTF-8 编码的文件名
- 参考现有 router 模式：`routers/vouchers.py`

**Implementation — `routers/ledgers.py`:**

```python
"""账簿查询 API"""
import io
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.auth.dependencies import require_permission
from app.models import User
from app.services.ledger_service import (
    get_general_ledger, get_detail_ledger, get_trial_balance,
)
from app.services.ledger_export import (
    export_general_ledger_excel, export_detail_ledger_excel,
    export_trial_balance_excel,
)
from app.logger import get_logger

logger = get_logger("ledgers")

router = APIRouter(prefix="/api/ledgers", tags=["账簿查询"])

_EXCEL_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/general-ledger")
async def general_ledger_api(
    account_set_id: int = Query(...),
    account_id: int = Query(...),
    start_period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    end_period: str = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_general_ledger(
        account_set_id, account_id, start_period, end_period or start_period
    )
    if not result:
        raise HTTPException(status_code=404, detail="科目不存在")
    return result


@router.get("/detail-ledger")
async def detail_ledger_api(
    account_set_id: int = Query(...),
    account_id: int = Query(...),
    start_period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    end_period: str = Query(None, pattern=r"^\d{4}-\d{2}$"),
    customer_id: int = Query(None),
    supplier_id: int = Query(None),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_detail_ledger(
        account_set_id, account_id, start_period, end_period or start_period,
        customer_id=customer_id, supplier_id=supplier_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="科目不存在")
    return result


@router.get("/trial-balance")
async def trial_balance_api(
    account_set_id: int = Query(...),
    period_name: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(require_permission("accounting_view")),
):
    return await get_trial_balance(account_set_id, period_name)


@router.get("/general-ledger/export")
async def export_general_ledger_api(
    account_set_id: int = Query(...),
    account_id: int = Query(...),
    start_period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    end_period: str = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_general_ledger(
        account_set_id, account_id, start_period, end_period or start_period
    )
    if not result:
        raise HTTPException(status_code=404, detail="科目不存在")
    output = export_general_ledger_excel(result)
    fname = f"总分类账_{result['account_code']}_{start_period}.xlsx"
    return StreamingResponse(
        output, media_type=_EXCEL_MEDIA,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )


@router.get("/detail-ledger/export")
async def export_detail_ledger_api(
    account_set_id: int = Query(...),
    account_id: int = Query(...),
    start_period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    end_period: str = Query(None, pattern=r"^\d{4}-\d{2}$"),
    customer_id: int = Query(None),
    supplier_id: int = Query(None),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_detail_ledger(
        account_set_id, account_id, start_period, end_period or start_period,
        customer_id=customer_id, supplier_id=supplier_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="科目不存在")
    output = export_detail_ledger_excel(result)
    fname = f"明细分类账_{result['account_code']}_{start_period}.xlsx"
    return StreamingResponse(
        output, media_type=_EXCEL_MEDIA,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )


@router.get("/trial-balance/export")
async def export_trial_balance_api(
    account_set_id: int = Query(...),
    period_name: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_trial_balance(account_set_id, period_name)
    output = export_trial_balance_excel(result)
    fname = f"科目余额表_{period_name}.xlsx"
    return StreamingResponse(
        output, media_type=_EXCEL_MEDIA,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )
```

**Modify `main.py` — imports (line ~26):** 在 import 行末尾加 `, ledgers`

**Modify `main.py` — include_router (after line 123):** 添加 `app.include_router(ledgers.router)`

---

### Task 5: Frontend — API 模块 + Store 更新

**Files:**
- Modify: `frontend/src/api/accounting.js` — 添加 ledger API 函数
- Modify: `frontend/src/stores/accounting.js` — 无需修改（数据在组件内管理）

**Context:**
- 现有 API 模块在 `frontend/src/api/accounting.js`
- 导出 API 使用 `responseType: 'blob'` 下载文件
- 参考现有 API 导出写法

**在 `api/accounting.js` 末尾添加：**

```javascript
// === 账簿查询 ===
export const getGeneralLedger = (params) =>
  api.get('/ledgers/general-ledger', { params })
export const getDetailLedger = (params) =>
  api.get('/ledgers/detail-ledger', { params })
export const getTrialBalance = (params) =>
  api.get('/ledgers/trial-balance', { params })
export const exportGeneralLedger = (params) =>
  api.get('/ledgers/general-ledger/export', { params, responseType: 'blob' })
export const exportDetailLedger = (params) =>
  api.get('/ledgers/detail-ledger/export', { params, responseType: 'blob' })
export const exportTrialBalance = (params) =>
  api.get('/ledgers/trial-balance/export', { params, responseType: 'blob' })
```

---

### Task 6: Frontend — 总分类账面板

**Files:**
- Create: `frontend/src/components/business/GeneralLedgerTab.vue`

**Context:**
- 传统中式总分类账格式：日期 / 凭证号 / 摘要 / 借方 / 贷方 / 方向 / 余额
- 第一行显示"期初余额"，最后两行显示"本期合计"和"期末余额"
- 凭证号可点击跳转到凭证详情（emit 事件）
- 需要科目选择器（下拉）和期间选择器
- 使用 `useAccountingStore` 获取当前账套 ID 和科目列表
- 样式参考 VoucherPanel.vue 的 table/select/button 样式

**Implementation:**

```vue
<template>
  <div>
    <!-- 查询条件 -->
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="selectedAccountId" class="form-input w-64" @change="query">
        <option :value="null" disabled>选择科目</option>
        <option v-for="a in leafAccounts" :key="a.id" :value="a.id">
          {{ a.code }} {{ a.name }}
        </option>
      </select>
      <input type="month" v-model="startPeriod" class="form-input w-36" @change="query">
      <span class="text-[13px] text-[#86868b]">至</span>
      <input type="month" v-model="endPeriod" class="form-input w-36" @change="query">
      <button @click="query" class="btn btn-primary btn-sm" :disabled="!selectedAccountId">查询</button>
      <button v-if="data" @click="handleExport" class="btn btn-secondary btn-sm">导出 Excel</button>
    </div>

    <!-- 账簿表格 -->
    <div v-if="data" class="table-wrapper">
      <div class="text-center text-[15px] font-semibold mb-2">
        总分类账 — {{ data.account_code }} {{ data.account_name }}
      </div>
      <table class="data-table text-[13px]">
        <thead>
          <tr>
            <th class="w-24">日期</th>
            <th class="w-48">凭证号</th>
            <th>摘要</th>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
            <th class="w-12 text-center">方向</th>
            <th class="w-28 text-right">余额</th>
          </tr>
        </thead>
        <tbody>
          <!-- 期初余额 -->
          <tr class="bg-[#f9f9fb]">
            <td></td><td></td>
            <td class="font-medium">期初余额</td>
            <td></td><td></td>
            <td class="text-center">{{ data.opening_direction }}</td>
            <td class="text-right">{{ fmt(data.opening_balance) }}</td>
          </tr>
          <!-- 分录 -->
          <tr v-for="(e, idx) in data.entries" :key="idx">
            <td>{{ e.date }}</td>
            <td class="text-blue-600 cursor-pointer hover:underline" @click="$emit('viewVoucher', e.voucher_id)">{{ e.voucher_no }}</td>
            <td>{{ e.summary }}</td>
            <td class="text-right">{{ fmt(e.debit) }}</td>
            <td class="text-right">{{ fmt(e.credit) }}</td>
            <td class="text-center">{{ e.direction }}</td>
            <td class="text-right">{{ fmt(e.balance) }}</td>
          </tr>
          <!-- 本期合计 -->
          <tr class="bg-[#f9f9fb] font-semibold">
            <td></td><td></td>
            <td>本期合计</td>
            <td class="text-right">{{ fmt(data.period_debit_total) }}</td>
            <td class="text-right">{{ fmt(data.period_credit_total) }}</td>
            <td></td><td></td>
          </tr>
          <!-- 期末余额 -->
          <tr class="bg-[#f9f9fb] font-semibold">
            <td></td><td></td>
            <td>期末余额</td>
            <td></td><td></td>
            <td class="text-center">{{ data.closing_direction }}</td>
            <td class="text-right">{{ fmt(data.closing_balance) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="data.entries.length === 0" class="text-center text-[#86868b] py-4 text-[13px]">
        本期无发生额
      </div>
    </div>
    <div v-else class="text-center text-[#86868b] py-12 text-[14px]">
      请选择科目和期间后点击查询
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { getGeneralLedger, exportGeneralLedger } from '../../api/accounting'

defineEmits(['viewVoucher'])

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const selectedAccountId = ref(null)
const now = new Date()
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const startPeriod = ref(currentMonth)
const endPeriod = ref(currentMonth)
const data = ref(null)

const leafAccounts = computed(() =>
  accountingStore.chartOfAccounts.filter(a => a.is_leaf)
)

const fmt = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const query = async () => {
  if (!selectedAccountId.value || !accountingStore.currentAccountSetId) return
  try {
    const { data: res } = await getGeneralLedger({
      account_set_id: accountingStore.currentAccountSetId,
      account_id: selectedAccountId.value,
      start_period: startPeriod.value,
      end_period: endPeriod.value,
    })
    data.value = res
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  }
}

const handleExport = async () => {
  try {
    const res = await exportGeneralLedger({
      account_set_id: accountingStore.currentAccountSetId,
      account_id: selectedAccountId.value,
      start_period: startPeriod.value,
      end_period: endPeriod.value,
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `总分类账_${data.value.account_code}_${startPeriod.value}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}

onMounted(() => accountingStore.loadChartOfAccounts())
</script>
```

---

### Task 7: Frontend — 明细分类账面板

**Files:**
- Create: `frontend/src/components/business/DetailLedgerTab.vue`

**Context:**
- 与总分类账类似，增加客户/供应商辅助核算筛选
- 只在科目有 `aux_customer` 或 `aux_supplier` 标记时才显示筛选项
- 需要从 `/api/customers`（已有）获取客户列表、`/api/suppliers`（已有）获取供应商列表
- 参考 `api/index.js` 已有 `api.get('/customers')` 等 API

**Implementation:**

```vue
<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="selectedAccountId" class="form-input w-64" @change="onAccountChange">
        <option :value="null" disabled>选择科目</option>
        <option v-for="a in leafAccounts" :key="a.id" :value="a.id">
          {{ a.code }} {{ a.name }}
        </option>
      </select>
      <input type="month" v-model="startPeriod" class="form-input w-36">
      <span class="text-[13px] text-[#86868b]">至</span>
      <input type="month" v-model="endPeriod" class="form-input w-36">
      <select v-if="showCustomerFilter" v-model="customerId" class="form-input w-40">
        <option :value="null">全部客户</option>
        <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <select v-if="showSupplierFilter" v-model="supplierId" class="form-input w-40">
        <option :value="null">全部供应商</option>
        <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button @click="query" class="btn btn-primary btn-sm" :disabled="!selectedAccountId">查询</button>
      <button v-if="data" @click="handleExport" class="btn btn-secondary btn-sm">导出 Excel</button>
    </div>

    <div v-if="data" class="table-wrapper">
      <div class="text-center text-[15px] font-semibold mb-2">
        明细分类账 — {{ data.account_code }} {{ data.account_name }}
      </div>
      <table class="data-table text-[13px]">
        <thead>
          <tr>
            <th class="w-24">日期</th>
            <th class="w-48">凭证号</th>
            <th>摘要</th>
            <th v-if="data.aux_customer" class="w-28">客户</th>
            <th v-if="data.aux_supplier" class="w-28">供应商</th>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
            <th class="w-12 text-center">方向</th>
            <th class="w-28 text-right">余额</th>
          </tr>
        </thead>
        <tbody>
          <tr class="bg-[#f9f9fb]">
            <td></td><td></td>
            <td class="font-medium">期初余额</td>
            <td v-if="data.aux_customer"></td>
            <td v-if="data.aux_supplier"></td>
            <td></td><td></td>
            <td class="text-center">{{ data.opening_direction }}</td>
            <td class="text-right">{{ fmt(data.opening_balance) }}</td>
          </tr>
          <tr v-for="(e, idx) in data.entries" :key="idx">
            <td>{{ e.date }}</td>
            <td class="text-blue-600 cursor-pointer hover:underline" @click="$emit('viewVoucher', e.voucher_id)">{{ e.voucher_no }}</td>
            <td>{{ e.summary }}</td>
            <td v-if="data.aux_customer">{{ e.customer_name || '' }}</td>
            <td v-if="data.aux_supplier">{{ e.supplier_name || '' }}</td>
            <td class="text-right">{{ fmt(e.debit) }}</td>
            <td class="text-right">{{ fmt(e.credit) }}</td>
            <td class="text-center">{{ e.direction }}</td>
            <td class="text-right">{{ fmt(e.balance) }}</td>
          </tr>
          <tr class="bg-[#f9f9fb] font-semibold">
            <td></td><td></td>
            <td>本期合计</td>
            <td v-if="data.aux_customer"></td>
            <td v-if="data.aux_supplier"></td>
            <td class="text-right">{{ fmt(data.period_debit_total) }}</td>
            <td class="text-right">{{ fmt(data.period_credit_total) }}</td>
            <td></td><td></td>
          </tr>
          <tr class="bg-[#f9f9fb] font-semibold">
            <td></td><td></td>
            <td>期末余额</td>
            <td v-if="data.aux_customer"></td>
            <td v-if="data.aux_supplier"></td>
            <td></td><td></td>
            <td class="text-center">{{ data.closing_direction }}</td>
            <td class="text-right">{{ fmt(data.closing_balance) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="text-center text-[#86868b] py-12 text-[14px]">
      请选择科目和期间后点击查询
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { getDetailLedger, exportDetailLedger } from '../../api/accounting'
import api from '../../api/index'

defineEmits(['viewVoucher'])

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const selectedAccountId = ref(null)
const now = new Date()
const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const startPeriod = ref(currentMonth)
const endPeriod = ref(currentMonth)
const customerId = ref(null)
const supplierId = ref(null)
const data = ref(null)
const customers = ref([])
const suppliers = ref([])

const leafAccounts = computed(() =>
  accountingStore.chartOfAccounts.filter(a => a.is_leaf)
)

const selectedAccount = computed(() =>
  leafAccounts.value.find(a => a.id === selectedAccountId.value)
)
const showCustomerFilter = computed(() => selectedAccount.value?.aux_customer)
const showSupplierFilter = computed(() => selectedAccount.value?.aux_supplier)

const fmt = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const onAccountChange = () => {
  customerId.value = null
  supplierId.value = null
  data.value = null
}

const query = async () => {
  if (!selectedAccountId.value || !accountingStore.currentAccountSetId) return
  try {
    const params = {
      account_set_id: accountingStore.currentAccountSetId,
      account_id: selectedAccountId.value,
      start_period: startPeriod.value,
      end_period: endPeriod.value,
    }
    if (customerId.value) params.customer_id = customerId.value
    if (supplierId.value) params.supplier_id = supplierId.value
    const { data: res } = await getDetailLedger(params)
    data.value = res
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  }
}

const handleExport = async () => {
  try {
    const params = {
      account_set_id: accountingStore.currentAccountSetId,
      account_id: selectedAccountId.value,
      start_period: startPeriod.value,
      end_period: endPeriod.value,
    }
    if (customerId.value) params.customer_id = customerId.value
    if (supplierId.value) params.supplier_id = supplierId.value
    const res = await exportDetailLedger(params)
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `明细分类账_${data.value.account_code}_${startPeriod.value}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}

onMounted(async () => {
  await accountingStore.loadChartOfAccounts()
  try {
    const [custRes, supRes] = await Promise.all([
      api.get('/customers'), api.get('/suppliers')
    ])
    customers.value = custRes.data?.items || custRes.data || []
    suppliers.value = supRes.data?.items || supRes.data || []
  } catch (e) { /* ignore */ }
})
</script>
```

---

### Task 8: Frontend — 科目余额表面板

**Files:**
- Create: `frontend/src/components/business/TrialBalanceTab.vue`

**Context:**
- 科目余额表格式：科目编码 / 科目名称 / 期初余额(借/贷) / 本期发生额(借/贷) / 期末余额(借/贷)
- 非叶子科目（父科目）加粗显示
- 最后合计行 + 试算平衡指示器（绿色"试算平衡" / 红色"不平衡"）
- 科目名称按 level 缩进

**Implementation:**

```vue
<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <input type="month" v-model="periodName" class="form-input w-36">
      <button @click="query" class="btn btn-primary btn-sm">查询</button>
      <button v-if="data" @click="handleExport" class="btn btn-secondary btn-sm">导出 Excel</button>
      <span v-if="data" :class="data.is_balanced ? 'text-green-600' : 'text-red-500'" class="text-[13px] font-medium ml-2">
        {{ data.is_balanced ? '试算平衡' : '试算不平衡！' }}
      </span>
    </div>

    <div v-if="data" class="table-wrapper">
      <table class="data-table text-[13px]">
        <thead>
          <tr>
            <th rowspan="2" class="w-24">科目编码</th>
            <th rowspan="2">科目名称</th>
            <th colspan="2" class="text-center border-b-0">期初余额</th>
            <th colspan="2" class="text-center border-b-0">本期发生额</th>
            <th colspan="2" class="text-center border-b-0">期末余额</th>
          </tr>
          <tr>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
            <th class="w-28 text-right">借方</th>
            <th class="w-28 text-right">贷方</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in data.accounts" :key="a.code" :class="{ 'font-semibold bg-[#f9f9fb]': !a.is_leaf }">
            <td>{{ a.code }}</td>
            <td :style="{ paddingLeft: (a.level - 1) * 16 + 8 + 'px' }">{{ a.name }}</td>
            <td class="text-right">{{ fmt(a.opening_debit) }}</td>
            <td class="text-right">{{ fmt(a.opening_credit) }}</td>
            <td class="text-right">{{ fmt(a.period_debit) }}</td>
            <td class="text-right">{{ fmt(a.period_credit) }}</td>
            <td class="text-right">{{ fmt(a.closing_debit) }}</td>
            <td class="text-right">{{ fmt(a.closing_credit) }}</td>
          </tr>
          <tr v-if="data.accounts.length === 0">
            <td colspan="8" class="text-center text-[#86868b] py-8">暂无数据</td>
          </tr>
        </tbody>
        <tfoot v-if="data.accounts.length > 0">
          <tr class="font-bold bg-[#f5f5f7]">
            <td></td>
            <td>合  计</td>
            <td class="text-right">{{ fmt(data.totals.opening_debit) }}</td>
            <td class="text-right">{{ fmt(data.totals.opening_credit) }}</td>
            <td class="text-right">{{ fmt(data.totals.period_debit) }}</td>
            <td class="text-right">{{ fmt(data.totals.period_credit) }}</td>
            <td class="text-right">{{ fmt(data.totals.closing_debit) }}</td>
            <td class="text-right">{{ fmt(data.totals.closing_credit) }}</td>
          </tr>
        </tfoot>
      </table>
    </div>
    <div v-else class="text-center text-[#86868b] py-12 text-[14px]">
      选择期间后点击查询
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { getTrialBalance, exportTrialBalance } from '../../api/accounting'

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const now = new Date()
const periodName = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const data = ref(null)

const fmt = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const query = async () => {
  if (!accountingStore.currentAccountSetId) return
  try {
    const { data: res } = await getTrialBalance({
      account_set_id: accountingStore.currentAccountSetId,
      period_name: periodName.value,
    })
    data.value = res
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '查询失败', 'error')
  }
}

const handleExport = async () => {
  try {
    const res = await exportTrialBalance({
      account_set_id: accountingStore.currentAccountSetId,
      period_name: periodName.value,
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `科目余额表_${periodName.value}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}
</script>
```

---

### Task 9: Frontend — LedgerPanel + AccountingView 集成

**Files:**
- Create: `frontend/src/components/business/LedgerPanel.vue`
- Modify: `frontend/src/views/AccountingView.vue` — 添加"账簿查询"Tab

**Context:**
- AccountingView 当前有 3 个 tab：凭证管理 / 科目管理 / 会计期间
- 新增第 4 个 tab："账簿查询"，渲染 LedgerPanel
- LedgerPanel 内部含 3 个子 tab：总分类账 / 明细分类账 / 科目余额表
- 子 tab 切换用 span 按钮，与 AccountingView 主 tab 样式一致

**Implementation — `LedgerPanel.vue`:**

```vue
<template>
  <div>
    <div class="flex gap-2 mb-3 border-b pb-2">
      <span @click="sub = 'general'" :class="['tab', sub === 'general' ? 'active' : '']">总分类账</span>
      <span @click="sub = 'detail'" :class="['tab', sub === 'detail' ? 'active' : '']">明细分类账</span>
      <span @click="sub = 'trial'" :class="['tab', sub === 'trial' ? 'active' : '']">科目余额表</span>
    </div>
    <GeneralLedgerTab v-if="sub === 'general'" @viewVoucher="$emit('viewVoucher', $event)" />
    <DetailLedgerTab v-if="sub === 'detail'" @viewVoucher="$emit('viewVoucher', $event)" />
    <TrialBalanceTab v-if="sub === 'trial'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import GeneralLedgerTab from './GeneralLedgerTab.vue'
import DetailLedgerTab from './DetailLedgerTab.vue'
import TrialBalanceTab from './TrialBalanceTab.vue'

defineEmits(['viewVoucher'])
const sub = ref('general')
</script>
```

**Modify `AccountingView.vue`:**

1. 在 Tab Navigation 中添加"账簿查询"：在 `<span @click="tab = 'periods'"...>会计期间</span>` 后添加：
```html
<span @click="tab = 'ledgers'" :class="['tab', tab === 'ledgers' ? 'active' : '']">账簿查询</span>
```

2. 在 Panels 区域中添加 LedgerPanel：在 `<AccountingPeriodsPanel v-if="tab === 'periods'" />` 后添加：
```html
<LedgerPanel v-if="tab === 'ledgers'" />
```

3. 在 script 导入中添加：
```javascript
import LedgerPanel from '../components/business/LedgerPanel.vue'
```

---

### Task 10: 全量测试 + 构建验证

**Steps:**

1. 运行后端测试：
```bash
source .venv/bin/activate && python -m pytest tests/ --ignore=tests/test_auth.py -v
```
Expected: 所有测试通过（原有 15 + 新增 ~10）

2. 验证后端导入：
```bash
source .venv/bin/activate && python -c "
from app.services.ledger_service import get_general_ledger, get_detail_ledger, get_trial_balance
from app.services.ledger_export import export_general_ledger_excel, export_detail_ledger_excel, export_trial_balance_excel
from app.routers.ledgers import router
print('所有账簿模块导入成功')
print(f'路由数量: {len(router.routes)}')
"
```

3. 前端构建：
```bash
cd ../frontend && npm run build
```
Expected: 构建成功，无错误

4. 验证前端文件存在：
```bash
ls -la src/components/business/GeneralLedgerTab.vue \
       src/components/business/DetailLedgerTab.vue \
       src/components/business/TrialBalanceTab.vue \
       src/components/business/LedgerPanel.vue
```

---

## 子代理分批建议

| 批次 | Tasks | 说明 |
|------|-------|------|
| 1 | 1-4 | 后端：服务 + 测试 + 导出 + 路由 |
| 2 | 5-9 | 前端：API + 4个组件 + 集成 |
| 3 | 10 | 全量验证 |
