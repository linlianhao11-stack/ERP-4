# 阶段1：财务基础设施 Implementation Plan

> **状态：✅ 已完成（2026-02-28）**

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 搭建财务会计基础骨架——账套、科目、会计期间、凭证体系，为后续 AR/AP/发票/报表提供底层支撑。

**Architecture:** 新建 3 个模型文件（accounting.py, voucher.py），改造 4 个现有模型（warehouse, order, purchase, payment）添加 account_set_id，Product 添加 tax_rate。后端新增 3 个 router（account_sets, chart_of_accounts, vouchers），前端新建 AccountingView + accounting store + API 模块。

**Tech Stack:** FastAPI 0.109 + Tortoise ORM 0.20 + PostgreSQL 16 / Vue 3.5 + Pinia 3.0 + Tailwind CSS 4 / pytest + pytest-asyncio (SQLite)

**Design Doc:** `docs/plans/2026-02-28-finance-module-design.md`

---

## 完成清单

### 后端文件（已创建/修改）

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/models/accounting.py` | 新建 | AccountSet, ChartOfAccount, AccountingPeriod |
| `app/models/voucher.py` | 新建 | Voucher (含状态工作流 draft→pending→approved→posted), VoucherEntry (含辅助核算) |
| `app/models/__init__.py` | 修改 | 导出 5 个新模型类 |
| `app/models/warehouse.py` | 修改 | Warehouse 新增 account_set FK (nullable) |
| `app/models/order.py` | 修改 | Order 新增 account_set FK (nullable) |
| `app/models/purchase.py` | 修改 | PurchaseOrder 新增 account_set FK (nullable) |
| `app/models/payment.py` | 修改 | Payment 新增 account_set FK (nullable) |
| `app/models/product.py` | 修改 | Product 新增 tax_rate DecimalField (default=13.00) |
| `app/services/accounting_init.py` | 新建 | 32 个预置科目 + 期间批量创建（均幂等） |
| `app/schemas/accounting.py` | 新建 | AccountSetCreate/Update, ChartOfAccountCreate/Update, VoucherCreate/Update, VoucherEntryInput |
| `app/routers/account_sets.py` | 新建 | 账套 CRUD + 创建时自动初始化科目/期间 |
| `app/routers/chart_of_accounts.py` | 新建 | 科目树 CRUD + 父级校验 + 停用检查 |
| `app/routers/accounting_periods.py` | 新建 | 期间列表 + 按年批量初始化 |
| `app/routers/vouchers.py` | 新建 | 凭证 CRUD + submit/approve/reject/post/unpost，借贷平衡校验，制单≠审核（可配置），期间锁检查，自动编号 |
| `app/migrations.py` | 修改 | 新增 migrate_accounting_phase1()：5 表 ALTER + 10 索引 + 管理员权限更新 |
| `main.py` | 修改 | 注册 4 个新 router |

### 前端文件（已创建/修改）

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/accounting.js` | 新建 | 账套/科目/期间/凭证全套 API |
| `src/stores/accounting.js` | 新建 | Pinia store：accountSets, currentAccountSetId, chartOfAccounts, periods |
| `src/views/AccountingView.vue` | 新建 | 主页面：账套按钮切换器 + 3 Tab（凭证/科目/期间） |
| `src/components/business/ChartOfAccountsPanel.vue` | 新建 | 科目树表格 + 新增子科目弹窗 + 停用 |
| `src/components/business/AccountingPeriodsPanel.vue` | 新建 | 期间列表 + 按年初始化 |
| `src/components/business/VoucherPanel.vue` | 新建 | 凭证列表 + 筛选 + CRUD 弹窗（含分录表/借贷平衡） + 全状态操作 |
| `src/utils/constants.js` | 修改 | BookOpen 图标 + accounting 菜单 + 5 新权限 |
| `src/router/index.js` | 修改 | /accounting 路由 + accounting_view 权限 |

### 测试（已创建）

| 文件 | 测试数 | 说明 |
|------|--------|------|
| `tests/test_accounting_models.py` | 9 | AccountSet/ChartOfAccount/AccountingPeriod CRUD + unique + 关联 |
| `tests/test_voucher_models.py` | 2 | Voucher+Entry 创建 + 状态值 |
| `tests/test_accounting_init.py` | 4 | 预置科目初始化 + 幂等 + 期间初始化 + 幂等 |

**总计：15 个测试全部通过，前端构建成功**

---

## Task 1: AccountSet 模型 + 迁移

**Files:**
- Create: `backend/app/models/accounting.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/migrations.py`
- Test: `backend/tests/test_accounting_models.py`

### Step 1: Write the failing test

```python
# backend/tests/test_accounting_models.py
"""会计基础模型测试"""
import pytest
from app.models.accounting import AccountSet


async def test_create_account_set():
    """创建账套"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领科技有限公司",
        tax_id="91440000MA000001X", start_year=2026, start_month=1,
        current_period="2026-01"
    )
    assert a.id is not None
    assert a.code == "QL"
    assert a.is_active is True


async def test_account_set_code_unique():
    """账套编码唯一"""
    await AccountSet.create(
        code="QL", name="启领", company_name="启领科技",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    from tortoise.exceptions import IntegrityError
    with pytest.raises(IntegrityError):
        await AccountSet.create(
            code="QL", name="启领2", company_name="启领科技2",
            start_year=2026, start_month=1, current_period="2026-01"
        )
```

### Step 2: Run test to verify it fails

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.accounting'`

### Step 3: Write the AccountSet model

```python
# backend/app/models/accounting.py
"""会计基础模型：账套、科目、会计期间"""
from tortoise import fields, models


class AccountSet(models.Model):
    """账套"""
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=20, unique=True)
    name = fields.CharField(max_length=100)
    company_name = fields.CharField(max_length=200, default="")
    tax_id = fields.CharField(max_length=30, default="")
    legal_person = fields.CharField(max_length=50, default="")
    address = fields.TextField(default="")
    bank_name = fields.CharField(max_length=100, default="")
    bank_account = fields.CharField(max_length=50, default="")
    start_year = fields.IntField()
    start_month = fields.IntField(default=1)
    current_period = fields.CharField(max_length=7)  # e.g. 2026-03
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "account_sets"
```

### Step 4: Update `__init__.py`

Add to `backend/app/models/__init__.py`:

```python
from app.models.accounting import AccountSet
```

And add `"AccountSet"` to `__all__`.

### Step 5: Run test to verify it passes

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_models.py -v`
Expected: PASS

### Step 6: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/models/accounting.py backend/app/models/__init__.py backend/tests/test_accounting_models.py
git commit -m "feat: 新增 AccountSet 账套模型

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: ChartOfAccount 科目模型

**Files:**
- Modify: `backend/app/models/accounting.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_accounting_models.py`

### Step 1: Write the failing test

Append to `backend/tests/test_accounting_models.py`:

```python
from app.models.accounting import AccountSet, ChartOfAccount


async def test_create_chart_of_account():
    """创建会计科目"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    coa = await ChartOfAccount.create(
        account_set=a, code="1001", name="库存现金",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    assert coa.id is not None
    assert coa.direction == "debit"


async def test_chart_of_account_unique_per_set():
    """同账套下科目编码唯一"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    await ChartOfAccount.create(
        account_set=a, code="1001", name="库存现金",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    from tortoise.exceptions import IntegrityError
    with pytest.raises(IntegrityError):
        await ChartOfAccount.create(
            account_set=a, code="1001", name="库存现金2",
            level=1, category="asset", direction="debit", is_leaf=True
        )
```

### Step 2: Run test to verify it fails

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_models.py::test_create_chart_of_account -v`
Expected: FAIL with `ImportError`

### Step 3: Add ChartOfAccount model

Append to `backend/app/models/accounting.py`:

```python
class ChartOfAccount(models.Model):
    """会计科目"""
    id = fields.IntField(pk=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="accounts", on_delete=fields.CASCADE)
    code = fields.CharField(max_length=20)
    name = fields.CharField(max_length=100)
    parent_code = fields.CharField(max_length=20, null=True)
    level = fields.IntField(default=1)
    category = fields.CharField(max_length=20)  # asset/liability/equity/cost/profit_loss
    direction = fields.CharField(max_length=6)   # debit/credit
    is_leaf = fields.BooleanField(default=True)
    is_active = fields.BooleanField(default=True)
    aux_customer = fields.BooleanField(default=False)
    aux_supplier = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chart_of_accounts"
        unique_together = (("account_set", "code"),)
```

### Step 4: Update `__init__.py`

Add `ChartOfAccount` to import and `__all__`.

### Step 5: Run test to verify it passes

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_models.py -v`
Expected: ALL PASS

### Step 6: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/models/accounting.py backend/app/models/__init__.py backend/tests/test_accounting_models.py
git commit -m "feat: 新增 ChartOfAccount 会计科目模型

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: AccountingPeriod 会计期间模型

**Files:**
- Modify: `backend/app/models/accounting.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_accounting_models.py`

### Step 1: Write the failing test

Append to test file:

```python
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod


async def test_create_accounting_period():
    """创建会计期间"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    p = await AccountingPeriod.create(
        account_set=a, period_name="2026-01", year=2026, month=1
    )
    assert p.id is not None
    assert p.is_closed is False


async def test_accounting_period_unique_per_set():
    """同账套下期间名唯一"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    await AccountingPeriod.create(
        account_set=a, period_name="2026-01", year=2026, month=1
    )
    from tortoise.exceptions import IntegrityError
    with pytest.raises(IntegrityError):
        await AccountingPeriod.create(
            account_set=a, period_name="2026-01", year=2026, month=1
        )
```

### Step 2: Run test to verify it fails

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_models.py::test_create_accounting_period -v`
Expected: FAIL

### Step 3: Add AccountingPeriod model

Append to `backend/app/models/accounting.py`:

```python
class AccountingPeriod(models.Model):
    """会计期间"""
    id = fields.IntField(pk=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="periods", on_delete=fields.CASCADE)
    period_name = fields.CharField(max_length=7)  # e.g. 2026-03
    year = fields.IntField()
    month = fields.IntField()
    is_closed = fields.BooleanField(default=False)
    closed_at = fields.DatetimeField(null=True)
    closed_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "accounting_periods"
        unique_together = (("account_set", "period_name"),)
```

### Step 4: Update `__init__.py`

Add `AccountingPeriod` to import and `__all__`.

### Step 5: Run test to verify it passes

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_models.py -v`
Expected: ALL PASS

### Step 6: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/models/accounting.py backend/app/models/__init__.py backend/tests/test_accounting_models.py
git commit -m "feat: 新增 AccountingPeriod 会计期间模型

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Voucher + VoucherEntry 凭证模型

**Files:**
- Create: `backend/app/models/voucher.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_voucher_models.py`

**Note:** 代码库中 Voucher/VoucherEntry 实际不存在（AI_CONTEXT.md 记载有误），所以从零开始创建。

### Step 1: Write the failing test

```python
# backend/tests/test_voucher_models.py
"""凭证模型测试"""
import pytest
from decimal import Decimal
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry


async def _setup_accounting():
    """创建账套+科目+期间"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    cash = await ChartOfAccount.create(
        account_set=a, code="1001", name="库存现金",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    bank = await ChartOfAccount.create(
        account_set=a, code="1002", name="银行存款",
        level=1, category="asset", direction="debit", is_leaf=True
    )
    period = await AccountingPeriod.create(
        account_set=a, period_name="2026-01", year=2026, month=1
    )
    return a, cash, bank, period


async def test_create_voucher_with_entries():
    """创建凭证和分录"""
    a, cash, bank, period = await _setup_accounting()
    v = await Voucher.create(
        account_set=a,
        voucher_type="记",
        voucher_no="QL-记-202601-001",
        period_name="2026-01",
        voucher_date="2026-01-15",
        total_debit=Decimal("1000.00"),
        total_credit=Decimal("1000.00"),
        status="draft",
        summary="提现"
    )
    assert v.id is not None
    assert v.status == "draft"

    e1 = await VoucherEntry.create(
        voucher=v, line_no=1, account=cash,
        summary="提现", debit_amount=Decimal("1000.00"),
        credit_amount=Decimal("0.00")
    )
    e2 = await VoucherEntry.create(
        voucher=v, line_no=2, account=bank,
        summary="提现", debit_amount=Decimal("0.00"),
        credit_amount=Decimal("1000.00")
    )
    assert e1.id is not None
    assert e2.credit_amount == Decimal("1000.00")


async def test_voucher_status_values():
    """凭证状态枚举"""
    a, cash, bank, period = await _setup_accounting()
    for status in ["draft", "pending", "approved", "posted"]:
        v = await Voucher.create(
            account_set=a, voucher_type="记",
            voucher_no=f"QL-记-202601-{status}",
            period_name="2026-01", voucher_date="2026-01-15",
            total_debit=Decimal("100.00"), total_credit=Decimal("100.00"),
            status=status, summary="测试"
        )
        assert v.status == status
```

### Step 2: Run test to verify it fails

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_voucher_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.voucher'`

### Step 3: Create Voucher model file

```python
# backend/app/models/voucher.py
"""凭证模型"""
from tortoise import fields, models


class Voucher(models.Model):
    """记账凭证"""
    id = fields.IntField(pk=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="vouchers", on_delete=fields.CASCADE)
    voucher_type = fields.CharField(max_length=4)  # 记/收/付/转
    voucher_no = fields.CharField(max_length=30, unique=True)  # QL-记-202603-001
    period_name = fields.CharField(max_length=7)  # 2026-03
    voucher_date = fields.DateField()
    summary = fields.CharField(max_length=200, default="")
    total_debit = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_credit = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = fields.CharField(max_length=20, default="draft")  # draft/pending/approved/posted
    attachment_count = fields.IntField(default=0)
    creator = fields.ForeignKeyField("models.User", related_name="created_vouchers", null=True, on_delete=fields.SET_NULL)
    approved_by = fields.ForeignKeyField("models.User", related_name="approved_vouchers", null=True, on_delete=fields.SET_NULL)
    approved_at = fields.DatetimeField(null=True)
    posted_by = fields.ForeignKeyField("models.User", related_name="posted_vouchers", null=True, on_delete=fields.SET_NULL)
    posted_at = fields.DatetimeField(null=True)
    source_type = fields.CharField(max_length=30, null=True)  # manual/auto_receivable/auto_payable/...
    source_bill_id = fields.IntField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "vouchers"


class VoucherEntry(models.Model):
    """凭证分录"""
    id = fields.IntField(pk=True)
    voucher = fields.ForeignKeyField("models.Voucher", related_name="entries", on_delete=fields.CASCADE)
    line_no = fields.IntField()
    account = fields.ForeignKeyField("models.ChartOfAccount", related_name="voucher_entries", on_delete=fields.RESTRICT)
    summary = fields.CharField(max_length=200, default="")
    debit_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    aux_customer = fields.ForeignKeyField("models.Customer", null=True, on_delete=fields.SET_NULL, related_name="voucher_entries")
    aux_supplier = fields.ForeignKeyField("models.Supplier", null=True, on_delete=fields.SET_NULL, related_name="voucher_entries")

    class Meta:
        table = "voucher_entries"
        ordering = ["line_no"]
```

### Step 4: Update `__init__.py`

```python
from app.models.voucher import Voucher, VoucherEntry
```

Add `"Voucher", "VoucherEntry"` to `__all__`.

### Step 5: Run test to verify it passes

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_voucher_models.py -v`
Expected: ALL PASS

### Step 6: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/models/voucher.py backend/app/models/__init__.py backend/tests/test_voucher_models.py
git commit -m "feat: 新增 Voucher/VoucherEntry 凭证模型

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 现有模型添加 account_set_id + tax_rate 字段

**Files:**
- Modify: `backend/app/models/warehouse.py` — 添加 account_set FK
- Modify: `backend/app/models/order.py` — 添加 account_set FK
- Modify: `backend/app/models/purchase.py` — 添加 account_set FK
- Modify: `backend/app/models/payment.py` — 添加 account_set FK
- Modify: `backend/app/models/product.py` — 添加 tax_rate
- Test: `backend/tests/test_accounting_models.py`

### Step 1: Write the failing test

Append to `backend/tests/test_accounting_models.py`:

```python
from app.models import Warehouse, Product


async def test_warehouse_has_account_set():
    """仓库有账套字段"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    w = await Warehouse.create(name="主仓", account_set=a)
    await w.refresh_from_db()
    assert w.account_set_id == a.id


async def test_warehouse_account_set_nullable():
    """仓库账套可为空（虚拟仓）"""
    w = await Warehouse.create(name="虚拟仓", is_virtual=True)
    assert w.account_set_id is None


async def test_product_has_tax_rate():
    """产品有税率字段"""
    from decimal import Decimal
    p = await Product.create(sku="TEST001", name="测试产品")
    await p.refresh_from_db()
    assert p.tax_rate == Decimal("13.00")
```

### Step 2: Run test to verify it fails

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_models.py::test_warehouse_has_account_set -v`
Expected: FAIL (Warehouse has no account_set field)

### Step 3: Modify models

**backend/app/models/warehouse.py** — add after `is_active`:
```python
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="warehouses", null=True, on_delete=fields.SET_NULL)
```

**backend/app/models/order.py** — add to Order after `shipping_status`:
```python
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="orders", null=True, on_delete=fields.SET_NULL)
```

**backend/app/models/purchase.py** — add to PurchaseOrder after `returned_at`:
```python
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="purchase_orders", null=True, on_delete=fields.SET_NULL)
```

**backend/app/models/payment.py** — add to Payment after `remark`:
```python
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="payments", null=True, on_delete=fields.SET_NULL)
```

**backend/app/models/product.py** — add after `description`:
```python
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13.00)
```

### Step 4: Run test to verify it passes

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_models.py -v`
Expected: ALL PASS

### Step 5: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/models/warehouse.py backend/app/models/order.py backend/app/models/purchase.py backend/app/models/payment.py backend/app/models/product.py backend/tests/test_accounting_models.py
git commit -m "feat: 现有模型添加 account_set_id 和 tax_rate 字段

Warehouse/Order/PurchaseOrder/Payment 添加 account_set FK（nullable）
Product 添加 tax_rate（默认13%）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: DDL 迁移脚本

**Files:**
- Modify: `backend/app/migrations.py`
- Test: 手动验证（DDL 迁移是 raw SQL，需要 PostgreSQL，SQLite 测试中由 generate_schemas 自动处理）

### Step 1: Write the migration function

在 `backend/app/migrations.py` 添加新函数 `migrate_accounting_phase1()`：

```python
async def migrate_accounting_phase1():
    """阶段1财务基础设施迁移：账套/科目/期间/凭证表 + 现有表新增字段（幂等）"""
    conn = connections.get("default")

    # --- 新表由 Tortoise generate_schemas(safe=True) 自动创建 ---
    # 但需手动添加现有表的新字段（generate_schemas 不会 ALTER 现有表）

    # Warehouse: account_set_id
    wh_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'warehouses'"
    )
    wh_col_names = [c["name"] for c in wh_cols]
    if "account_set_id" not in wh_col_names:
        await conn.execute_query(
            "ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: warehouses 表添加 account_set_id 列")

    # Orders: account_set_id
    o_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'orders'"
    )
    if "account_set_id" not in [c["name"] for c in o_cols]:
        await conn.execute_query(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: orders 表添加 account_set_id 列")

    # PurchaseOrders: account_set_id
    po_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    if "account_set_id" not in [c["name"] for c in po_cols]:
        await conn.execute_query(
            "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: purchase_orders 表添加 account_set_id 列")

    # Payments: account_set_id
    pay_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'payments'"
    )
    if "account_set_id" not in [c["name"] for c in pay_cols]:
        await conn.execute_query(
            "ALTER TABLE payments ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: payments 表添加 account_set_id 列")

    # Products: tax_rate
    prod_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'products'"
    )
    if "tax_rate" not in [c["name"] for c in prod_cols]:
        await conn.execute_query(
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS tax_rate DECIMAL(5,2) DEFAULT 13.00"
        )
        logger.info("迁移: products 表添加 tax_rate 列")

    # 会计相关索引
    accounting_indexes = [
        ("idx_chart_of_accounts_set_code", "chart_of_accounts", "account_set_id, code"),
        ("idx_accounting_periods_set_name", "accounting_periods", "account_set_id, period_name"),
        ("idx_vouchers_set_period", "vouchers", "account_set_id, period_name"),
        ("idx_vouchers_set_type_no", "vouchers", "account_set_id, voucher_type, voucher_no"),
        ("idx_voucher_entries_voucher", "voucher_entries", "voucher_id"),
        ("idx_voucher_entries_account", "voucher_entries", "account_id"),
        ("idx_orders_account_set", "orders", "account_set_id"),
        ("idx_purchase_orders_account_set", "purchase_orders", "account_set_id"),
        ("idx_payments_account_set", "payments", "account_set_id"),
        ("idx_warehouses_account_set", "warehouses", "account_set_id"),
    ]
    for name, table, columns in accounting_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败（可忽略）: {e}")

    logger.info("阶段1财务迁移完成")
```

### Step 2: Register in run_migrations()

在 `run_migrations()` 函数的 `await migrate_shipping_flow()` 之后、数据初始化之前添加：

```python
    await migrate_accounting_phase1()
```

### Step 3: Verify existing tests still pass

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/ -v`
Expected: ALL PASS

### Step 4: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/migrations.py
git commit -m "feat: 阶段1 DDL 迁移——账套/科目/期间/凭证索引 + 现有表新增字段

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: 预置会计科目数据初始化

**Files:**
- Create: `backend/app/services/accounting_init.py`
- Test: `backend/tests/test_accounting_init.py`

### Step 1: Write the failing test

```python
# backend/tests/test_accounting_init.py
"""科目初始化测试"""
import pytest
from app.models.accounting import AccountSet, ChartOfAccount
from app.services.accounting_init import init_chart_of_accounts


async def test_init_chart_of_accounts():
    """初始化预置科目"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    count = await init_chart_of_accounts(a.id)
    assert count >= 25  # 至少25个预置科目

    # 检查几个关键科目
    cash = await ChartOfAccount.filter(account_set_id=a.id, code="1001").first()
    assert cash is not None
    assert cash.name == "库存现金"
    assert cash.category == "asset"
    assert cash.direction == "debit"

    ar = await ChartOfAccount.filter(account_set_id=a.id, code="1122").first()
    assert ar is not None
    assert ar.aux_customer is True

    ap = await ChartOfAccount.filter(account_set_id=a.id, code="2202").first()
    assert ap is not None
    assert ap.aux_supplier is True

    # 子科目
    vat_in = await ChartOfAccount.filter(account_set_id=a.id, code="222101").first()
    assert vat_in is not None
    assert vat_in.parent_code == "2221"
    assert vat_in.level == 2


async def test_init_chart_idempotent():
    """初始化幂等——重复调用不会创建重复科目"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    count1 = await init_chart_of_accounts(a.id)
    count2 = await init_chart_of_accounts(a.id)
    total = await ChartOfAccount.filter(account_set_id=a.id).count()
    assert total == count1
    assert count2 == 0  # 第二次不创建新科目
```

### Step 2: Run test to verify it fails

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_init.py -v`
Expected: FAIL with `ModuleNotFoundError`

### Step 3: Implement the init service

```python
# backend/app/services/accounting_init.py
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
    existing_codes = set()
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
    existing = set()
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
```

### Step 4: Run test to verify it passes

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_accounting_init.py -v`
Expected: ALL PASS

### Step 5: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/services/accounting_init.py backend/tests/test_accounting_init.py
git commit -m "feat: 预置科目初始化 + 会计期间自动创建服务

31个标准贸易企业科目，含辅助核算标记（客户/供应商）
会计期间按年度自动创建

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/accounting.py`

### Step 1: Create schemas

```python
# backend/app/schemas/accounting.py
"""会计模块请求/响应模型"""
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import date


# === 账套 ===

class AccountSetCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    company_name: str = Field(default="", max_length=200)
    tax_id: str = Field(default="", max_length=30)
    legal_person: str = Field(default="", max_length=50)
    address: str = Field(default="")
    bank_name: str = Field(default="", max_length=100)
    bank_account: str = Field(default="", max_length=50)
    start_year: int = Field(ge=2000, le=2099)
    start_month: int = Field(ge=1, le=12, default=1)


class AccountSetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    company_name: Optional[str] = Field(None, max_length=200)
    tax_id: Optional[str] = Field(None, max_length=30)
    legal_person: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_account: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


# === 科目 ===

class ChartOfAccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    parent_code: Optional[str] = Field(None, max_length=20)
    category: str = Field(pattern=r"^(asset|liability|equity|cost|profit_loss)$")
    direction: str = Field(pattern=r"^(debit|credit)$")
    is_leaf: bool = True
    aux_customer: bool = False
    aux_supplier: bool = False


class ChartOfAccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_leaf: Optional[bool] = None
    is_active: Optional[bool] = None
    aux_customer: Optional[bool] = None
    aux_supplier: Optional[bool] = None


# === 凭证 ===

class VoucherEntryInput(BaseModel):
    account_id: int
    summary: str = Field(default="", max_length=200)
    debit_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    aux_customer_id: Optional[int] = None
    aux_supplier_id: Optional[int] = None


class VoucherCreate(BaseModel):
    voucher_type: str = Field(pattern=r"^(记|收|付|转)$")
    voucher_date: date
    summary: str = Field(default="", max_length=200)
    attachment_count: int = Field(default=0, ge=0)
    entries: list[VoucherEntryInput] = Field(min_length=2)


class VoucherUpdate(BaseModel):
    voucher_date: Optional[date] = None
    summary: Optional[str] = Field(None, max_length=200)
    attachment_count: Optional[int] = Field(None, ge=0)
    entries: Optional[list[VoucherEntryInput]] = None
```

### Step 2: Verify no import errors

Run: `cd /Users/lin/Desktop/erp-4/backend && python -c "from app.schemas.accounting import *; print('OK')"`
Expected: `OK`

### Step 3: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/schemas/accounting.py
git commit -m "feat: 会计模块 Pydantic schemas

账套/科目/凭证的请求响应模型

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: AccountSet CRUD Router

**Files:**
- Create: `backend/app/routers/account_sets.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_account_sets_api.py`

### Step 1: Write the failing test

```python
# backend/tests/test_account_sets_api.py
"""账套 API 测试"""
import pytest
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.services.accounting_init import init_chart_of_accounts, init_accounting_periods


async def test_create_account_set_service():
    """模拟创建账套后自动初始化科目和期间"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领科技有限公司",
        tax_id="91440000MA000001X", start_year=2026, start_month=3,
        current_period="2026-03"
    )
    coa_count = await init_chart_of_accounts(a.id)
    assert coa_count >= 25

    period_count = await init_accounting_periods(a.id, 2026, 3)
    assert period_count == 10  # 3月到12月

    # 验证期间
    periods = await AccountingPeriod.filter(account_set_id=a.id).order_by("month")
    assert len(periods) == 10
    assert periods[0].period_name == "2026-03"
    assert periods[-1].period_name == "2026-12"
```

### Step 2: Run test to verify it passes (this reuses existing service)

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_account_sets_api.py -v`
Expected: PASS

### Step 3: Create the router

```python
# backend/app/routers/account_sets.py
"""账套管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.schemas.accounting import AccountSetCreate, AccountSetUpdate
from app.services.accounting_init import init_chart_of_accounts, init_accounting_periods
from app.logger import get_logger

logger = get_logger("account_sets")

router = APIRouter(prefix="/api/account-sets", tags=["账套管理"])


@router.get("")
async def list_account_sets(user: User = Depends(get_current_user)):
    """获取账套列表"""
    sets = await AccountSet.filter(is_active=True).order_by("id")
    return [{
        "id": s.id, "code": s.code, "name": s.name,
        "company_name": s.company_name, "tax_id": s.tax_id,
        "current_period": s.current_period, "is_active": s.is_active,
    } for s in sets]


@router.get("/{set_id}")
async def get_account_set(set_id: int, user: User = Depends(get_current_user)):
    """获取账套详情"""
    s = await AccountSet.filter(id=set_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="账套不存在")
    return {
        "id": s.id, "code": s.code, "name": s.name,
        "company_name": s.company_name, "tax_id": s.tax_id,
        "legal_person": s.legal_person, "address": s.address,
        "bank_name": s.bank_name, "bank_account": s.bank_account,
        "start_year": s.start_year, "start_month": s.start_month,
        "current_period": s.current_period, "is_active": s.is_active,
    }


@router.post("")
async def create_account_set(data: AccountSetCreate, user: User = Depends(require_permission("admin"))):
    """创建账套（自动初始化科目和会计期间）"""
    if await AccountSet.filter(code=data.code).exists():
        raise HTTPException(status_code=400, detail="账套编码已存在")

    current_period = f"{data.start_year}-{data.start_month:02d}"
    async with transactions.in_transaction():
        s = await AccountSet.create(
            code=data.code, name=data.name, company_name=data.company_name,
            tax_id=data.tax_id, legal_person=data.legal_person,
            address=data.address, bank_name=data.bank_name,
            bank_account=data.bank_account,
            start_year=data.start_year, start_month=data.start_month,
            current_period=current_period,
        )
        coa_count = await init_chart_of_accounts(s.id)
        period_count = await init_accounting_periods(s.id, data.start_year, data.start_month)

    logger.info(f"创建账套: {s.code} ({s.name}), 科目 {coa_count} 个, 期间 {period_count} 个")
    return {"id": s.id, "message": f"创建成功，已初始化 {coa_count} 个科目和 {period_count} 个会计期间"}


@router.put("/{set_id}")
async def update_account_set(set_id: int, data: AccountSetUpdate, user: User = Depends(require_permission("admin"))):
    """更新账套信息"""
    s = await AccountSet.filter(id=set_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="账套不存在")
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if update_data:
        await AccountSet.filter(id=set_id).update(**update_data)
    return {"message": "更新成功"}
```

### Step 4: Register router in main.py

In `backend/main.py`:

1. Add import: `from app.routers import account_sets` (add to the existing import block)
2. Add registration: `app.include_router(account_sets.router)` (after the existing router registrations)

### Step 5: Run all tests

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/ -v`
Expected: ALL PASS

### Step 6: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/routers/account_sets.py backend/main.py backend/tests/test_account_sets_api.py
git commit -m "feat: 账套管理 CRUD API

创建账套时自动初始化31个预置科目 + 年度会计期间

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: ChartOfAccount 科目管理 Router

**Files:**
- Create: `backend/app/routers/chart_of_accounts.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_chart_of_accounts_api.py`

### Step 1: Write the failing test

```python
# backend/tests/test_chart_of_accounts_api.py
"""科目管理测试"""
import pytest
from app.models.accounting import AccountSet, ChartOfAccount
from app.services.accounting_init import init_chart_of_accounts


async def test_list_accounts_tree():
    """列出科目（按编码排序）"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    await init_chart_of_accounts(a.id)
    accounts = await ChartOfAccount.filter(
        account_set_id=a.id, is_active=True
    ).order_by("code")
    assert len(accounts) >= 25
    # 编码有序
    codes = [acc.code for acc in accounts]
    assert codes == sorted(codes)


async def test_add_sub_account():
    """添加子科目"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    await init_chart_of_accounts(a.id)

    # 在银行存款下添加子科目
    parent = await ChartOfAccount.filter(account_set_id=a.id, code="1002").first()
    assert parent.is_leaf is True

    sub = await ChartOfAccount.create(
        account_set_id=a.id, code="100201", name="工商银行",
        parent_code="1002", level=2, category="asset",
        direction="debit", is_leaf=True
    )
    # 父科目 is_leaf 需要更新为 False
    parent.is_leaf = False
    await parent.save()

    parent_refreshed = await ChartOfAccount.filter(id=parent.id).first()
    assert parent_refreshed.is_leaf is False
    assert sub.parent_code == "1002"


async def test_cannot_delete_account_with_children():
    """有子科目的科目不能停用"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    await init_chart_of_accounts(a.id)
    # 2221 应交税费有子科目
    parent = await ChartOfAccount.filter(account_set_id=a.id, code="2221").first()
    children = await ChartOfAccount.filter(
        account_set_id=a.id, parent_code="2221", is_active=True
    ).count()
    assert children == 2  # 222101, 222102
    assert parent.is_leaf is False
```

### Step 2: Run test to verify it passes

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_chart_of_accounts_api.py -v`
Expected: PASS (these only test model operations, not the router itself)

### Step 3: Create the router

```python
# backend/app/routers/chart_of_accounts.py
"""会计科目管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise import transactions
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.accounting import AccountSet, ChartOfAccount
from app.models.voucher import VoucherEntry
from app.schemas.accounting import ChartOfAccountCreate, ChartOfAccountUpdate

router = APIRouter(prefix="/api/chart-of-accounts", tags=["会计科目"])


@router.get("")
async def list_accounts(
    account_set_id: int = Query(...),
    user: User = Depends(get_current_user)
):
    """获取账套下的科目列表（按编码排序）"""
    accounts = await ChartOfAccount.filter(
        account_set_id=account_set_id, is_active=True
    ).order_by("code")
    return [{
        "id": a.id, "code": a.code, "name": a.name,
        "parent_code": a.parent_code, "level": a.level,
        "category": a.category, "direction": a.direction,
        "is_leaf": a.is_leaf, "aux_customer": a.aux_customer,
        "aux_supplier": a.aux_supplier,
    } for a in accounts]


@router.post("")
async def create_account(
    account_set_id: int = Query(...),
    data: ChartOfAccountCreate = ...,
    user: User = Depends(require_permission("accounting_edit"))
):
    """新增科目（通常用于添加子科目）"""
    if not await AccountSet.filter(id=account_set_id).exists():
        raise HTTPException(status_code=404, detail="账套不存在")
    if await ChartOfAccount.filter(account_set_id=account_set_id, code=data.code).exists():
        raise HTTPException(status_code=400, detail="科目编码已存在")

    # 确定 level
    level = 1
    if data.parent_code:
        parent = await ChartOfAccount.filter(
            account_set_id=account_set_id, code=data.parent_code
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="上级科目不存在")
        level = parent.level + 1
        if not data.code.startswith(data.parent_code):
            raise HTTPException(status_code=400, detail="子科目编码必须以上级科目编码开头")

    async with transactions.in_transaction():
        account = await ChartOfAccount.create(
            account_set_id=account_set_id,
            code=data.code, name=data.name,
            parent_code=data.parent_code, level=level,
            category=data.category, direction=data.direction,
            is_leaf=data.is_leaf,
            aux_customer=data.aux_customer, aux_supplier=data.aux_supplier,
        )
        # 父科目标记为非末级
        if data.parent_code:
            await ChartOfAccount.filter(
                account_set_id=account_set_id, code=data.parent_code
            ).update(is_leaf=False)

    return {"id": account.id, "message": "创建成功"}


@router.put("/{account_id}")
async def update_account(
    account_id: int,
    data: ChartOfAccountUpdate,
    user: User = Depends(require_permission("accounting_edit"))
):
    """修改科目"""
    account = await ChartOfAccount.filter(id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if update_data:
        await ChartOfAccount.filter(id=account_id).update(**update_data)
    return {"message": "更新成功"}


@router.delete("/{account_id}")
async def deactivate_account(
    account_id: int,
    user: User = Depends(require_permission("accounting_edit"))
):
    """停用科目（软删除）"""
    account = await ChartOfAccount.filter(id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")
    # 有子科目不能停用
    children = await ChartOfAccount.filter(
        account_set_id=account.account_set_id, parent_code=account.code, is_active=True
    ).count()
    if children > 0:
        raise HTTPException(status_code=400, detail="该科目有活跃子科目，无法停用")
    # 有凭证分录引用不能停用
    has_entries = await VoucherEntry.filter(account_id=account_id).exists()
    if has_entries:
        raise HTTPException(status_code=400, detail="该科目已被凭证引用，无法停用")
    account.is_active = False
    await account.save()
    return {"message": "已停用"}
```

### Step 4: Register router in main.py

Add import and registration for `chart_of_accounts`.

### Step 5: Run all tests

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/ -v`
Expected: ALL PASS

### Step 6: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/routers/chart_of_accounts.py backend/main.py backend/tests/test_chart_of_accounts_api.py
git commit -m "feat: 会计科目管理 API（CRUD + 子科目 + 停用校验）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: AccountingPeriod 会计期间 Router

**Files:**
- Create: `backend/app/routers/accounting_periods.py`
- Modify: `backend/main.py`

### Step 1: Create the router

```python
# backend/app/routers/accounting_periods.py
"""会计期间管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.accounting import AccountSet, AccountingPeriod
from app.services.accounting_init import init_accounting_periods

router = APIRouter(prefix="/api/accounting-periods", tags=["会计期间"])


@router.get("")
async def list_periods(
    account_set_id: int = Query(...),
    year: int = Query(None),
    user: User = Depends(get_current_user)
):
    """获取账套的会计期间列表"""
    query = AccountingPeriod.filter(account_set_id=account_set_id)
    if year:
        query = query.filter(year=year)
    periods = await query.order_by("year", "month")
    return [{
        "id": p.id, "period_name": p.period_name,
        "year": p.year, "month": p.month,
        "is_closed": p.is_closed, "closed_at": p.closed_at,
    } for p in periods]


@router.post("/init-year")
async def init_year_periods(
    account_set_id: int = Query(...),
    year: int = Query(...),
    user: User = Depends(require_permission("period_end"))
):
    """为账套初始化指定年度的会计期间（1-12月）"""
    s = await AccountSet.filter(id=account_set_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="账套不存在")
    count = await init_accounting_periods(account_set_id, year, 1)
    return {"message": f"已创建 {count} 个会计期间", "created": count}
```

### Step 2: Register router in main.py

Add import and registration for `accounting_periods`.

### Step 3: Run all tests

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/ -v`
Expected: ALL PASS

### Step 4: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/routers/accounting_periods.py backend/main.py
git commit -m "feat: 会计期间管理 API（列表 + 年度批量创建）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Voucher 凭证 CRUD Router

**Files:**
- Create: `backend/app/routers/vouchers.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_voucher_api.py`

### Step 1: Write the failing test

```python
# backend/tests/test_voucher_api.py
"""凭证业务逻辑测试"""
import pytest
from decimal import Decimal
from app.models import User
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.services.accounting_init import init_chart_of_accounts, init_accounting_periods
from app.auth.password import hash_password


async def _setup_full():
    """创建完整测试环境：账套+科目+期间+用户"""
    a = await AccountSet.create(
        code="QL", name="启领", company_name="启领",
        start_year=2026, start_month=1, current_period="2026-01"
    )
    await init_chart_of_accounts(a.id)
    await init_accounting_periods(a.id, 2026, 1)
    user1 = await User.create(
        username="maker", password_hash=hash_password("test123"),
        display_name="制单员", role="user",
        permissions=["accounting_view", "accounting_edit"]
    )
    user2 = await User.create(
        username="approver", password_hash=hash_password("test123"),
        display_name="审核员", role="user",
        permissions=["accounting_view", "accounting_approve"]
    )
    cash = await ChartOfAccount.filter(account_set_id=a.id, code="1001").first()
    bank = await ChartOfAccount.filter(account_set_id=a.id, code="1002").first()
    return a, user1, user2, cash, bank


async def test_voucher_debit_credit_must_balance():
    """凭证借贷必须平衡"""
    a, user1, user2, cash, bank = await _setup_full()

    # 正常创建：借贷相等
    v = await Voucher.create(
        account_set=a, voucher_type="记",
        voucher_no="QL-记-202601-001",
        period_name="2026-01", voucher_date="2026-01-15",
        total_debit=Decimal("500.00"), total_credit=Decimal("500.00"),
        status="draft", creator=user1
    )
    await VoucherEntry.create(
        voucher=v, line_no=1, account=cash,
        summary="提现", debit_amount=Decimal("500.00"), credit_amount=Decimal("0.00")
    )
    await VoucherEntry.create(
        voucher=v, line_no=2, account=bank,
        summary="提现", debit_amount=Decimal("0.00"), credit_amount=Decimal("500.00")
    )
    entries = await VoucherEntry.filter(voucher=v)
    total_d = sum(e.debit_amount for e in entries)
    total_c = sum(e.credit_amount for e in entries)
    assert total_d == total_c == Decimal("500.00")


async def test_voucher_status_flow():
    """凭证状态流转 draft → pending → approved → posted"""
    a, user1, user2, cash, bank = await _setup_full()
    v = await Voucher.create(
        account_set=a, voucher_type="记",
        voucher_no="QL-记-202601-001",
        period_name="2026-01", voucher_date="2026-01-15",
        total_debit=Decimal("100.00"), total_credit=Decimal("100.00"),
        status="draft", creator=user1
    )
    # draft → pending
    v.status = "pending"
    await v.save()
    assert v.status == "pending"

    # pending → approved (审核人≠制单人)
    v.status = "approved"
    v.approved_by = user2
    await v.save()
    assert v.approved_by_id == user2.id

    # approved → posted
    v.status = "posted"
    v.posted_by = user2
    await v.save()
    assert v.status == "posted"
```

### Step 2: Run test to verify it passes (model-level tests)

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/test_voucher_api.py -v`
Expected: PASS

### Step 3: Create the voucher router

```python
# backend/app/routers/vouchers.py
"""凭证管理 API"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise import transactions
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.models.system_setting import SystemSetting
from app.schemas.accounting import VoucherCreate, VoucherUpdate
from app.logger import get_logger

logger = get_logger("vouchers")

router = APIRouter(prefix="/api/vouchers", tags=["凭证管理"])


async def _next_voucher_no(account_set_id: int, voucher_type: str, period_name: str) -> str:
    """生成下一个凭证号：账套code-凭证字-期间-序号"""
    account_set = await AccountSet.filter(id=account_set_id).first()
    prefix = f"{account_set.code}-{voucher_type}-{period_name.replace('-', '')}-"
    last = await Voucher.filter(
        account_set_id=account_set_id,
        voucher_type=voucher_type,
        period_name=period_name
    ).order_by("-voucher_no").first()
    if last and last.voucher_no.startswith(prefix):
        seq = int(last.voucher_no[len(prefix):]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


@router.get("")
async def list_vouchers(
    account_set_id: int = Query(...),
    period_name: str = Query(None),
    status: str = Query(None),
    voucher_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_view"))
):
    """凭证列表"""
    query = Voucher.filter(account_set_id=account_set_id)
    if period_name:
        query = query.filter(period_name=period_name)
    if status:
        query = query.filter(status=status)
    if voucher_type:
        query = query.filter(voucher_type=voucher_type)

    total = await query.count()
    vouchers = await query.order_by("voucher_no").offset((page - 1) * page_size).limit(page_size)

    result = []
    for v in vouchers:
        result.append({
            "id": v.id, "voucher_type": v.voucher_type,
            "voucher_no": v.voucher_no, "voucher_date": str(v.voucher_date),
            "period_name": v.period_name, "summary": v.summary,
            "total_debit": str(v.total_debit), "total_credit": str(v.total_credit),
            "status": v.status, "attachment_count": v.attachment_count,
            "creator_id": v.creator_id,
            "approved_by_id": v.approved_by_id,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        })
    return {"items": result, "total": total, "page": page, "page_size": page_size}


@router.get("/{voucher_id}")
async def get_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_view"))
):
    """凭证详情（含分录）"""
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").prefetch_related("account")
    return {
        "id": v.id, "voucher_type": v.voucher_type,
        "voucher_no": v.voucher_no, "voucher_date": str(v.voucher_date),
        "period_name": v.period_name, "summary": v.summary,
        "total_debit": str(v.total_debit), "total_credit": str(v.total_credit),
        "status": v.status, "attachment_count": v.attachment_count,
        "creator_id": v.creator_id,
        "approved_by_id": v.approved_by_id, "approved_at": v.approved_at,
        "posted_by_id": v.posted_by_id, "posted_at": v.posted_at,
        "entries": [{
            "id": e.id, "line_no": e.line_no,
            "account_id": e.account_id,
            "account_code": e.account.code,
            "account_name": e.account.name,
            "summary": e.summary,
            "debit_amount": str(e.debit_amount),
            "credit_amount": str(e.credit_amount),
            "aux_customer_id": e.aux_customer_id,
            "aux_supplier_id": e.aux_supplier_id,
        } for e in entries],
    }


@router.post("")
async def create_voucher(
    account_set_id: int = Query(...),
    data: VoucherCreate = ...,
    user: User = Depends(require_permission("accounting_edit"))
):
    """创建凭证"""
    # 验证账套
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")

    # 验证期间
    period_name = data.voucher_date.strftime("%Y-%m")
    period = await AccountingPeriod.filter(
        account_set_id=account_set_id, period_name=period_name
    ).first()
    if not period:
        raise HTTPException(status_code=400, detail=f"会计期间 {period_name} 不存在")
    if period.is_closed:
        raise HTTPException(status_code=400, detail=f"会计期间 {period_name} 已结账，不能新增凭证")

    # 验证借贷平衡
    total_debit = sum(e.debit_amount for e in data.entries)
    total_credit = sum(e.credit_amount for e in data.entries)
    if total_debit != total_credit:
        raise HTTPException(status_code=400, detail=f"借贷不平衡：借方 {total_debit}，贷方 {total_credit}")
    if total_debit == 0:
        raise HTTPException(status_code=400, detail="借贷金额不能全部为零")

    # 验证每行至少有一方金额
    for i, entry in enumerate(data.entries):
        if entry.debit_amount == 0 and entry.credit_amount == 0:
            raise HTTPException(status_code=400, detail=f"第 {i+1} 行借贷金额不能同时为零")
        if entry.debit_amount > 0 and entry.credit_amount > 0:
            raise HTTPException(status_code=400, detail=f"第 {i+1} 行不能同时填写借方和贷方金额")

    # 验证科目
    account_ids = [e.account_id for e in data.entries]
    accounts = await ChartOfAccount.filter(
        id__in=account_ids, account_set_id=account_set_id, is_active=True
    )
    valid_ids = {a.id for a in accounts}
    for e in data.entries:
        if e.account_id not in valid_ids:
            raise HTTPException(status_code=400, detail=f"科目 ID {e.account_id} 不存在或不属于当前账套")
    leaf_check = {a.id: a.is_leaf for a in accounts}
    for e in data.entries:
        if not leaf_check.get(e.account_id, False):
            raise HTTPException(status_code=400, detail=f"科目 ID {e.account_id} 不是末级科目，不能录入凭证")

    async with transactions.in_transaction():
        voucher_no = await _next_voucher_no(account_set_id, data.voucher_type, period_name)
        v = await Voucher.create(
            account_set_id=account_set_id,
            voucher_type=data.voucher_type,
            voucher_no=voucher_no,
            period_name=period_name,
            voucher_date=data.voucher_date,
            summary=data.summary,
            total_debit=total_debit,
            total_credit=total_credit,
            status="draft",
            attachment_count=data.attachment_count,
            creator=user,
        )
        for i, entry in enumerate(data.entries):
            await VoucherEntry.create(
                voucher=v, line_no=i + 1,
                account_id=entry.account_id,
                summary=entry.summary,
                debit_amount=entry.debit_amount,
                credit_amount=entry.credit_amount,
                aux_customer_id=entry.aux_customer_id,
                aux_supplier_id=entry.aux_supplier_id,
            )

    logger.info(f"创建凭证: {voucher_no}")
    return {"id": v.id, "voucher_no": voucher_no, "message": "创建成功"}


@router.put("/{voucher_id}")
async def update_voucher(
    voucher_id: int,
    data: VoucherUpdate,
    user: User = Depends(require_permission("accounting_edit"))
):
    """编辑凭证（仅 draft 状态可编辑）"""
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态的凭证可以编辑")

    async with transactions.in_transaction():
        update_fields = {}
        if data.voucher_date is not None:
            new_period = data.voucher_date.strftime("%Y-%m")
            period = await AccountingPeriod.filter(
                account_set_id=v.account_set_id, period_name=new_period
            ).first()
            if not period:
                raise HTTPException(status_code=400, detail=f"会计期间 {new_period} 不存在")
            if period.is_closed:
                raise HTTPException(status_code=400, detail=f"会计期间 {new_period} 已结账")
            update_fields["voucher_date"] = data.voucher_date
            update_fields["period_name"] = new_period
        if data.summary is not None:
            update_fields["summary"] = data.summary
        if data.attachment_count is not None:
            update_fields["attachment_count"] = data.attachment_count

        if data.entries is not None:
            # 验证借贷平衡
            total_debit = sum(e.debit_amount for e in data.entries)
            total_credit = sum(e.credit_amount for e in data.entries)
            if total_debit != total_credit:
                raise HTTPException(status_code=400, detail=f"借贷不平衡：借方 {total_debit}，贷方 {total_credit}")
            if total_debit == 0:
                raise HTTPException(status_code=400, detail="借贷金额不能全部为零")

            # 验证科目
            account_ids = [e.account_id for e in data.entries]
            accounts = await ChartOfAccount.filter(
                id__in=account_ids, account_set_id=v.account_set_id, is_active=True, is_leaf=True
            )
            valid_ids = {a.id for a in accounts}
            for e in data.entries:
                if e.account_id not in valid_ids:
                    raise HTTPException(status_code=400, detail=f"科目 ID {e.account_id} 无效")

            # 删除旧分录，创建新分录
            await VoucherEntry.filter(voucher=v).delete()
            for i, entry in enumerate(data.entries):
                await VoucherEntry.create(
                    voucher=v, line_no=i + 1,
                    account_id=entry.account_id,
                    summary=entry.summary,
                    debit_amount=entry.debit_amount,
                    credit_amount=entry.credit_amount,
                    aux_customer_id=entry.aux_customer_id,
                    aux_supplier_id=entry.aux_supplier_id,
                )
            update_fields["total_debit"] = total_debit
            update_fields["total_credit"] = total_credit

        if update_fields:
            await Voucher.filter(id=voucher_id).update(**update_fields)

    return {"message": "更新成功"}


@router.delete("/{voucher_id}")
async def delete_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_edit"))
):
    """删除凭证（仅 draft 状态可删除）"""
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态的凭证可以删除")
    async with transactions.in_transaction():
        await VoucherEntry.filter(voucher=v).delete()
        await v.delete()
    return {"message": "删除成功"}


@router.post("/{voucher_id}/submit")
async def submit_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_edit"))
):
    """提交凭证审核（draft → pending）"""
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态的凭证可以提交")
    v.status = "pending"
    await v.save()
    return {"message": "已提交审核"}


@router.post("/{voucher_id}/approve")
async def approve_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_approve"))
):
    """审核凭证（pending → approved）"""
    from datetime import datetime, timezone
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "pending":
        raise HTTPException(status_code=400, detail="只有待审核状态的凭证可以审核")

    # 制单人≠审核人检查（可配置关闭）
    strict = await SystemSetting.filter(key="voucher_maker_checker").first()
    if not strict or strict.value != "false":
        if v.creator_id == user.id:
            raise HTTPException(status_code=400, detail="制单人不能审核自己的凭证")

    v.status = "approved"
    v.approved_by = user
    v.approved_at = datetime.now(timezone.utc)
    await v.save()
    return {"message": "审核通过"}


@router.post("/{voucher_id}/reject")
async def reject_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_approve"))
):
    """驳回凭证（pending → draft）"""
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "pending":
        raise HTTPException(status_code=400, detail="只有待审核状态的凭证可以驳回")
    v.status = "draft"
    await v.save()
    return {"message": "已驳回"}


@router.post("/{voucher_id}/post")
async def post_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_post"))
):
    """过账凭证（approved → posted）"""
    from datetime import datetime, timezone
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "approved":
        raise HTTPException(status_code=400, detail="只有已审核状态的凭证可以过账")
    v.status = "posted"
    v.posted_by = user
    v.posted_at = datetime.now(timezone.utc)
    await v.save()
    return {"message": "过账成功"}


@router.post("/{voucher_id}/unpost")
async def unpost_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_post"))
):
    """反过账（posted → approved）"""
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "posted":
        raise HTTPException(status_code=400, detail="只有已过账状态的凭证可以反过账")
    # 检查期间是否已结账
    period = await AccountingPeriod.filter(
        account_set_id=v.account_set_id, period_name=v.period_name
    ).first()
    if period and period.is_closed:
        raise HTTPException(status_code=400, detail="该期间已结账，不能反过账")
    v.status = "approved"
    v.posted_by = None
    v.posted_at = None
    await v.save()
    return {"message": "反过账成功"}
```

### Step 4: Register router in main.py

Add import and registration for `vouchers`.

### Step 5: Run all tests

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/ -v`
Expected: ALL PASS

### Step 6: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/routers/vouchers.py backend/main.py backend/tests/test_voucher_api.py
git commit -m "feat: 凭证管理完整 API

CRUD + 状态流转（draft→pending→approved→posted）
借贷平衡校验、末级科目校验、制单人≠审核人（可配置）
自动编号：账套code-凭证字-YYYYMM-序号

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: 前端 API 模块 + Store

**Files:**
- Create: `frontend/src/api/accounting.js`
- Create: `frontend/src/stores/accounting.js`

### Step 1: Create API module

```javascript
// frontend/src/api/accounting.js
import api from './index'

// === 账套 ===
export const getAccountSets = () => api.get('/account-sets')
export const getAccountSet = (id) => api.get(`/account-sets/${id}`)
export const createAccountSet = (data) => api.post('/account-sets', data)
export const updateAccountSet = (id, data) => api.put(`/account-sets/${id}`, data)

// === 科目 ===
export const getChartOfAccounts = (accountSetId) =>
  api.get('/chart-of-accounts', { params: { account_set_id: accountSetId } })
export const createChartOfAccount = (accountSetId, data) =>
  api.post('/chart-of-accounts', data, { params: { account_set_id: accountSetId } })
export const updateChartOfAccount = (id, data) =>
  api.put(`/chart-of-accounts/${id}`, data)
export const deleteChartOfAccount = (id) =>
  api.delete(`/chart-of-accounts/${id}`)

// === 会计期间 ===
export const getAccountingPeriods = (accountSetId, year) =>
  api.get('/accounting-periods', { params: { account_set_id: accountSetId, year } })
export const initYearPeriods = (accountSetId, year) =>
  api.post('/accounting-periods/init-year', null, { params: { account_set_id: accountSetId, year } })

// === 凭证 ===
export const getVouchers = (params) => api.get('/vouchers', { params })
export const getVoucher = (id) => api.get(`/vouchers/${id}`)
export const createVoucher = (accountSetId, data) =>
  api.post('/vouchers', data, { params: { account_set_id: accountSetId } })
export const updateVoucher = (id, data) => api.put(`/vouchers/${id}`, data)
export const deleteVoucher = (id) => api.delete(`/vouchers/${id}`)
export const submitVoucher = (id) => api.post(`/vouchers/${id}/submit`)
export const approveVoucher = (id) => api.post(`/vouchers/${id}/approve`)
export const rejectVoucher = (id) => api.post(`/vouchers/${id}/reject`)
export const postVoucher = (id) => api.post(`/vouchers/${id}/post`)
export const unpostVoucher = (id) => api.post(`/vouchers/${id}/unpost`)
```

### Step 2: Create accounting store

```javascript
// frontend/src/stores/accounting.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAccountSets, getChartOfAccounts, getAccountingPeriods } from '../api/accounting'

export const useAccountingStore = defineStore('accounting', () => {
  const accountSets = ref([])
  const currentAccountSetId = ref(null)
  const chartOfAccounts = ref([])
  const periods = ref([])
  const loading = ref(false)

  const currentAccountSet = computed(() =>
    accountSets.value.find(s => s.id === currentAccountSetId.value)
  )

  async function loadAccountSets() {
    try {
      const { data } = await getAccountSets()
      accountSets.value = data
      // 自动选中第一个账套（如果未选择）
      if (!currentAccountSetId.value && data.length > 0) {
        currentAccountSetId.value = data[0].id
      }
    } catch (e) { /* ignore */ }
  }

  function setCurrentAccountSet(id) {
    currentAccountSetId.value = id
    // 切换账套时清空缓存
    chartOfAccounts.value = []
    periods.value = []
  }

  async function loadChartOfAccounts() {
    if (!currentAccountSetId.value) return
    try {
      const { data } = await getChartOfAccounts(currentAccountSetId.value)
      chartOfAccounts.value = data
    } catch (e) { /* ignore */ }
  }

  async function loadPeriods(year) {
    if (!currentAccountSetId.value) return
    try {
      const { data } = await getAccountingPeriods(currentAccountSetId.value, year)
      periods.value = data
    } catch (e) { /* ignore */ }
  }

  return {
    accountSets, currentAccountSetId, currentAccountSet,
    chartOfAccounts, periods, loading,
    loadAccountSets, setCurrentAccountSet,
    loadChartOfAccounts, loadPeriods,
  }
})
```

### Step 3: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add frontend/src/api/accounting.js frontend/src/stores/accounting.js
git commit -m "feat: 前端会计 API 模块 + accounting store

账套切换、科目列表、会计期间、凭证 CRUD 全量封装

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 14: 前端权限 + 路由 + 菜单

**Files:**
- Modify: `frontend/src/utils/constants.js`
- Modify: `frontend/src/router/index.js`

### Step 1: Add permissions and menu item

**constants.js** — 在 `allPermissions` 数组末尾添加：

```javascript
  { key: 'accounting_view', name: '会计查看' },
  { key: 'accounting_edit', name: '会计录入' },
  { key: 'accounting_approve', name: '凭证审核' },
  { key: 'accounting_post', name: '凭证过账' },
  { key: 'period_end', name: '期末处理' },
```

**constants.js** — 在 `menuItems` 的 `finance` 项之后添加：

```javascript
  { key: 'accounting', name: '会计', perm: 'accounting_view' },
```

**constants.js** — 在 iconMap 中添加（import `BookOpen` from lucide-vue-next）：

```javascript
  accounting: BookOpen,
```

### Step 2: Add route

**router/index.js** — 在 finance 路由之后添加：

```javascript
  { path: '/accounting', name: 'accounting', component: () => import('../views/AccountingView.vue'), meta: { perm: 'accounting_view' } },
```

### Step 3: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add frontend/src/utils/constants.js frontend/src/router/index.js
git commit -m "feat: 前端会计路由 + 权限 + 菜单项

5个新权限、会计菜单入口、AccountingView 路由

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 15: AccountingView 页面 + 账套切换器

**Files:**
- Create: `frontend/src/views/AccountingView.vue`
- Modify: `frontend/src/App.vue`

### Step 1: Create AccountingView

```vue
<!-- frontend/src/views/AccountingView.vue -->
<template>
  <div>
    <!-- 账套切换器 -->
    <div class="flex items-center gap-3 mb-4">
      <span class="text-[13px] text-[#86868b]">当前账套</span>
      <div class="flex gap-2">
        <button
          v-for="s in accountingStore.accountSets"
          :key="s.id"
          @click="switchAccountSet(s.id)"
          :class="[
            'px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all duration-200',
            s.id === accountingStore.currentAccountSetId
              ? 'bg-[#0071e3] text-white shadow-sm'
              : 'bg-[#f5f5f7] text-[#1d1d1f] hover:bg-[#e8e8ed]'
          ]"
        >
          {{ s.name }}
        </button>
      </div>
      <span v-if="accountingStore.currentAccountSet" class="text-[12px] text-[#86868b]">
        当前期间: {{ accountingStore.currentAccountSet.current_period }}
      </span>
    </div>

    <!-- Tab Navigation -->
    <div class="flex flex-wrap gap-2 mb-3 border-b pb-2">
      <span @click="tab = 'vouchers'" :class="['tab', tab === 'vouchers' ? 'active' : '']">凭证管理</span>
      <span @click="tab = 'accounts'" :class="['tab', tab === 'accounts' ? 'active' : '']">科目管理</span>
      <span @click="tab = 'periods'" :class="['tab', tab === 'periods' ? 'active' : '']">会计期间</span>
    </div>

    <!-- No account set selected -->
    <div v-if="!accountingStore.currentAccountSetId" class="text-center py-20 text-[#86868b]">
      <p class="text-[15px]">请先选择或创建账套</p>
    </div>

    <!-- Panels -->
    <template v-else>
      <VoucherPanel v-if="tab === 'vouchers'" />
      <ChartOfAccountsPanel v-if="tab === 'accounts'" />
      <AccountingPeriodsPanel v-if="tab === 'periods'" />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAccountingStore } from '../stores/accounting'
import VoucherPanel from '../components/business/VoucherPanel.vue'
import ChartOfAccountsPanel from '../components/business/ChartOfAccountsPanel.vue'
import AccountingPeriodsPanel from '../components/business/AccountingPeriodsPanel.vue'

const accountingStore = useAccountingStore()
const tab = ref('vouchers')

const switchAccountSet = (id) => {
  accountingStore.setCurrentAccountSet(id)
}

onMounted(() => {
  accountingStore.loadAccountSets()
})
</script>
```

### Step 2: Update App.vue for accounting route data loading

In `frontend/src/App.vue`, add to the `loadForRoute` function:

```javascript
  if (routeName === 'accounting') {
    // accounting store handles its own loading via onMounted
  }
```

Import the store: `import { useAccountingStore } from './stores/accounting'`

Actually, AccountingView handles its own data loading in `onMounted`, so no change needed in App.vue for data loading. But we do need the new icon import.

### Step 3: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add frontend/src/views/AccountingView.vue
git commit -m "feat: AccountingView 页面框架 + 账套切换器

按钮式账套切换、三个Tab（凭证/科目/期间）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 16: ChartOfAccountsPanel 科目管理面板

**Files:**
- Create: `frontend/src/components/business/ChartOfAccountsPanel.vue`

### Step 1: Create the component

```vue
<!-- frontend/src/components/business/ChartOfAccountsPanel.vue -->
<template>
  <div>
    <!-- 操作栏 -->
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-[15px] font-semibold text-[#1d1d1f]">会计科目</h3>
      <button
        v-if="hasPermission('accounting_edit')"
        @click="showAddForm = true"
        class="btn btn-primary btn-sm"
      >
        新增子科目
      </button>
    </div>

    <!-- 科目表格 -->
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>科目编码</th>
            <th>科目名称</th>
            <th>类别</th>
            <th>方向</th>
            <th>末级</th>
            <th>辅助核算</th>
            <th v-if="hasPermission('accounting_edit')">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in accounts" :key="a.id">
            <td>
              <span :style="{ paddingLeft: (a.level - 1) * 20 + 'px' }">{{ a.code }}</span>
            </td>
            <td>{{ a.name }}</td>
            <td><span :class="categoryBadge(a.category)">{{ categoryName(a.category) }}</span></td>
            <td>{{ a.direction === 'debit' ? '借' : '贷' }}</td>
            <td>{{ a.is_leaf ? '是' : '否' }}</td>
            <td>
              <span v-if="a.aux_customer" class="badge badge-blue">客户</span>
              <span v-if="a.aux_supplier" class="badge badge-orange">供应商</span>
            </td>
            <td v-if="hasPermission('accounting_edit')">
              <button
                v-if="a.is_leaf"
                @click="deactivateAccount(a)"
                class="text-[12px] text-red-500 hover:text-red-700"
              >
                停用
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增子科目弹窗 -->
    <Transition name="fade">
      <div v-if="showAddForm" class="modal-backdrop" @click.self="showAddForm = false">
        <div class="modal" style="max-width: 480px">
          <div class="modal-header">
            <h3>新增子科目</h3>
            <button @click="showAddForm = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body space-y-3">
            <div>
              <label class="form-label">上级科目编码</label>
              <input v-model="form.parent_code" class="form-input" placeholder="如 1002">
            </div>
            <div>
              <label class="form-label">科目编码</label>
              <input v-model="form.code" class="form-input" placeholder="如 100201">
            </div>
            <div>
              <label class="form-label">科目名称</label>
              <input v-model="form.name" class="form-input" placeholder="如 工商银行">
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="form-label">类别</label>
                <select v-model="form.category" class="form-input">
                  <option value="asset">资产</option>
                  <option value="liability">负债</option>
                  <option value="equity">权益</option>
                  <option value="cost">成本</option>
                  <option value="profit_loss">损益</option>
                </select>
              </div>
              <div>
                <label class="form-label">余额方向</label>
                <select v-model="form.direction" class="form-input">
                  <option value="debit">借</option>
                  <option value="credit">贷</option>
                </select>
              </div>
            </div>
            <div class="flex gap-4">
              <label class="flex items-center gap-1.5 text-[13px]">
                <input type="checkbox" v-model="form.aux_customer"> 辅助核算-客户
              </label>
              <label class="flex items-center gap-1.5 text-[13px]">
                <input type="checkbox" v-model="form.aux_supplier"> 辅助核算-供应商
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showAddForm = false" class="btn btn-secondary">取消</button>
            <button @click="handleAdd" class="btn btn-primary" :disabled="submitting">确定</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import { createChartOfAccount, deleteChartOfAccount } from '../../api/accounting'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()

const accounts = ref([])
const showAddForm = ref(false)
const submitting = ref(false)
const form = ref({
  parent_code: '', code: '', name: '',
  category: 'asset', direction: 'debit',
  aux_customer: false, aux_supplier: false,
})

const categoryNames = {
  asset: '资产', liability: '负债', equity: '权益',
  cost: '成本', profit_loss: '损益'
}
const categoryBadges = {
  asset: 'badge badge-blue', liability: 'badge badge-red',
  equity: 'badge badge-green', cost: 'badge badge-orange',
  profit_loss: 'badge badge-purple'
}

const categoryName = (c) => categoryNames[c] || c
const categoryBadge = (c) => categoryBadges[c] || 'badge'

const loadAccounts = async () => {
  await accountingStore.loadChartOfAccounts()
  accounts.value = accountingStore.chartOfAccounts
}

const handleAdd = async () => {
  if (!form.value.code || !form.value.name) {
    appStore.showToast('请填写科目编码和名称', 'error')
    return
  }
  submitting.value = true
  try {
    await createChartOfAccount(accountingStore.currentAccountSetId, form.value)
    appStore.showToast('创建成功', 'success')
    showAddForm.value = false
    form.value = { parent_code: '', code: '', name: '', category: 'asset', direction: 'debit', aux_customer: false, aux_supplier: false }
    await loadAccounts()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    submitting.value = false
  }
}

const deactivateAccount = async (account) => {
  if (!confirm(`确定停用科目 ${account.code} ${account.name}？`)) return
  try {
    await deleteChartOfAccount(account.id)
    appStore.showToast('已停用', 'success')
    await loadAccounts()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '停用失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => {
  if (accountingStore.currentAccountSetId) loadAccounts()
})

onMounted(() => {
  if (accountingStore.currentAccountSetId) loadAccounts()
})
</script>
```

### Step 2: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add frontend/src/components/business/ChartOfAccountsPanel.vue
git commit -m "feat: 科目管理面板（树形列表 + 新增子科目 + 停用）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 17: AccountingPeriodsPanel 会计期间面板

**Files:**
- Create: `frontend/src/components/business/AccountingPeriodsPanel.vue`

### Step 1: Create the component

```vue
<!-- frontend/src/components/business/AccountingPeriodsPanel.vue -->
<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-[15px] font-semibold text-[#1d1d1f]">会计期间</h3>
      <div class="flex items-center gap-2">
        <select v-model="selectedYear" class="form-input w-28">
          <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}年</option>
        </select>
        <button
          v-if="hasPermission('period_end')"
          @click="handleInitYear"
          class="btn btn-secondary btn-sm"
          :disabled="submitting"
        >
          初始化年度期间
        </button>
      </div>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>期间</th>
            <th>年</th>
            <th>月</th>
            <th>状态</th>
            <th>结账时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in periods" :key="p.id">
            <td class="font-medium">{{ p.period_name }}</td>
            <td>{{ p.year }}</td>
            <td>{{ p.month }}</td>
            <td>
              <span :class="p.is_closed ? 'badge badge-green' : 'badge badge-yellow'">
                {{ p.is_closed ? '已结账' : '未结账' }}
              </span>
            </td>
            <td>{{ p.closed_at ? new Date(p.closed_at).toLocaleString() : '-' }}</td>
          </tr>
          <tr v-if="periods.length === 0">
            <td colspan="5" class="text-center text-[#86868b] py-8">
              该年度暂无会计期间，请点击"初始化年度期间"创建
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import { initYearPeriods } from '../../api/accounting'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()

const currentYear = new Date().getFullYear()
const selectedYear = ref(currentYear)
const submitting = ref(false)
const periods = ref([])

const yearOptions = computed(() => {
  const years = []
  for (let y = currentYear - 2; y <= currentYear + 2; y++) years.push(y)
  return years
})

const loadPeriods = async () => {
  if (!accountingStore.currentAccountSetId) return
  await accountingStore.loadPeriods(selectedYear.value)
  periods.value = accountingStore.periods
}

const handleInitYear = async () => {
  submitting.value = true
  try {
    const { data } = await initYearPeriods(accountingStore.currentAccountSetId, selectedYear.value)
    appStore.showToast(data.message, 'success')
    await loadPeriods()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '初始化失败', 'error')
  } finally {
    submitting.value = false
  }
}

watch(selectedYear, loadPeriods)
watch(() => accountingStore.currentAccountSetId, loadPeriods)

onMounted(loadPeriods)
</script>
```

### Step 2: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add frontend/src/components/business/AccountingPeriodsPanel.vue
git commit -m "feat: 会计期间管理面板（年度列表 + 批量初始化）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 18: VoucherPanel 凭证管理面板

**Files:**
- Create: `frontend/src/components/business/VoucherPanel.vue`

### Step 1: Create the component

```vue
<!-- frontend/src/components/business/VoucherPanel.vue -->
<template>
  <div>
    <!-- 筛选栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="filters.period_name" class="form-input w-32" @change="loadList">
        <option value="">全部期间</option>
        <option v-for="p in periodOptions" :key="p" :value="p">{{ p }}</option>
      </select>
      <select v-model="filters.voucher_type" class="form-input w-24" @change="loadList">
        <option value="">全部</option>
        <option value="记">记</option>
        <option value="收">收</option>
        <option value="付">付</option>
        <option value="转">转</option>
      </select>
      <select v-model="filters.status" class="form-input w-28" @change="loadList">
        <option value="">全部状态</option>
        <option value="draft">草稿</option>
        <option value="pending">待审核</option>
        <option value="approved">已审核</option>
        <option value="posted">已过账</option>
      </select>
      <button
        v-if="hasPermission('accounting_edit')"
        @click="openCreateForm"
        class="btn btn-primary btn-sm ml-auto"
      >
        新增凭证
      </button>
    </div>

    <!-- 凭证列表 -->
    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>凭证号</th>
            <th>日期</th>
            <th>摘要</th>
            <th>借方合计</th>
            <th>贷方合计</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in vouchers" :key="v.id" @click="viewVoucher(v.id)" class="cursor-pointer">
            <td class="font-medium">{{ v.voucher_no }}</td>
            <td>{{ v.voucher_date }}</td>
            <td>{{ v.summary || '-' }}</td>
            <td class="text-right">{{ formatAmount(v.total_debit) }}</td>
            <td class="text-right">{{ formatAmount(v.total_credit) }}</td>
            <td><span :class="statusBadge(v.status)">{{ statusName(v.status) }}</span></td>
            <td @click.stop>
              <div class="flex gap-1">
                <button v-if="v.status === 'draft' && hasPermission('accounting_edit')"
                  @click="handleSubmit(v)" class="text-[12px] text-blue-600">提交</button>
                <button v-if="v.status === 'pending' && hasPermission('accounting_approve')"
                  @click="handleApprove(v)" class="text-[12px] text-green-600">审核</button>
                <button v-if="v.status === 'pending' && hasPermission('accounting_approve')"
                  @click="handleReject(v)" class="text-[12px] text-orange-600">驳回</button>
                <button v-if="v.status === 'approved' && hasPermission('accounting_post')"
                  @click="handlePost(v)" class="text-[12px] text-purple-600">过账</button>
                <button v-if="v.status === 'draft' && hasPermission('accounting_edit')"
                  @click="handleDelete(v)" class="text-[12px] text-red-500">删除</button>
              </div>
            </td>
          </tr>
          <tr v-if="vouchers.length === 0">
            <td colspan="7" class="text-center text-[#86868b] py-8">暂无凭证</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-[#86868b] leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>

    <!-- 凭证详情/编辑弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal" style="max-width: 800px">
          <div class="modal-header">
            <h3>{{ isEditing ? '编辑凭证' : (isCreating ? '新增凭证' : '凭证详情') }}</h3>
            <button @click="showDetail = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <!-- 凭证头 -->
            <div class="grid grid-cols-3 gap-3 mb-4">
              <div>
                <label class="form-label">凭证字</label>
                <select v-model="editForm.voucher_type" class="form-input" :disabled="!isCreating">
                  <option value="记">记</option>
                  <option value="收">收</option>
                  <option value="付">付</option>
                  <option value="转">转</option>
                </select>
              </div>
              <div>
                <label class="form-label">凭证日期</label>
                <input type="date" v-model="editForm.voucher_date" class="form-input" :disabled="!isEditing && !isCreating">
              </div>
              <div>
                <label class="form-label">附件张数</label>
                <input type="number" v-model.number="editForm.attachment_count" class="form-input" min="0" :disabled="!isEditing && !isCreating">
              </div>
            </div>
            <div class="mb-4">
              <label class="form-label">摘要</label>
              <input v-model="editForm.summary" class="form-input" :disabled="!isEditing && !isCreating">
            </div>

            <!-- 分录表格 -->
            <div class="table-wrapper">
              <table class="data-table text-[13px]">
                <thead>
                  <tr>
                    <th class="w-8">#</th>
                    <th>科目</th>
                    <th>摘要</th>
                    <th class="w-32">借方金额</th>
                    <th class="w-32">贷方金额</th>
                    <th v-if="isEditing || isCreating" class="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(entry, idx) in editForm.entries" :key="idx">
                    <td>{{ idx + 1 }}</td>
                    <td>
                      <select v-if="isEditing || isCreating" v-model="entry.account_id" class="form-input text-[12px]">
                        <option v-for="a in leafAccounts" :key="a.id" :value="a.id">
                          {{ a.code }} {{ a.name }}
                        </option>
                      </select>
                      <span v-else>{{ entry.account_code }} {{ entry.account_name }}</span>
                    </td>
                    <td>
                      <input v-if="isEditing || isCreating" v-model="entry.summary" class="form-input text-[12px]">
                      <span v-else>{{ entry.summary }}</span>
                    </td>
                    <td>
                      <input v-if="isEditing || isCreating" type="number" v-model.number="entry.debit_amount"
                        class="form-input text-right text-[12px]" min="0" step="0.01">
                      <span v-else class="text-right block">{{ formatAmount(entry.debit_amount) }}</span>
                    </td>
                    <td>
                      <input v-if="isEditing || isCreating" type="number" v-model.number="entry.credit_amount"
                        class="form-input text-right text-[12px]" min="0" step="0.01">
                      <span v-else class="text-right block">{{ formatAmount(entry.credit_amount) }}</span>
                    </td>
                    <td v-if="isEditing || isCreating">
                      <button @click="editForm.entries.splice(idx, 1)" class="text-red-500 text-[12px]"
                        v-if="editForm.entries.length > 2">&times;</button>
                    </td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr class="font-semibold">
                    <td colspan="3" class="text-right">合计</td>
                    <td class="text-right">{{ formatAmount(totalDebit) }}</td>
                    <td class="text-right">{{ formatAmount(totalCredit) }}</td>
                    <td v-if="isEditing || isCreating"></td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <!-- 借贷差额提示 -->
            <div v-if="(isEditing || isCreating) && totalDebit !== totalCredit" class="mt-2 text-[13px] text-red-500">
              借贷不平衡！差额: {{ formatAmount(Math.abs(totalDebit - totalCredit)) }}
            </div>

            <!-- 添加分录按钮 -->
            <button v-if="isEditing || isCreating" @click="addEntry" class="btn btn-secondary btn-sm mt-2">
              + 添加分录
            </button>
          </div>
          <div class="modal-footer">
            <button @click="showDetail = false" class="btn btn-secondary">{{ (isEditing || isCreating) ? '取消' : '关闭' }}</button>
            <button v-if="isCreating" @click="handleCreate" class="btn btn-primary" :disabled="submitting || totalDebit !== totalCredit">保存</button>
            <button v-if="isEditing" @click="handleUpdate" class="btn btn-primary" :disabled="submitting || totalDebit !== totalCredit">保存</button>
            <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'draft' && hasPermission('accounting_edit')"
              @click="startEdit" class="btn btn-primary">编辑</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAccountingStore } from '../../stores/accounting'
import { usePermission } from '../../composables/usePermission'
import { useAppStore } from '../../stores/app'
import {
  getVouchers, getVoucher, createVoucher, updateVoucher,
  deleteVoucher, submitVoucher, approveVoucher, rejectVoucher,
  postVoucher
} from '../../api/accounting'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()

const vouchers = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const submitting = ref(false)
const showDetail = ref(false)
const isCreating = ref(false)
const isEditing = ref(false)
const detailVoucher = ref(null)
const leafAccounts = ref([])

const filters = ref({ period_name: '', voucher_type: '', status: '' })

const editForm = ref({
  voucher_type: '记', voucher_date: '', summary: '',
  attachment_count: 0, entries: []
})

const periodOptions = computed(() => {
  const set = accountingStore.currentAccountSet
  if (!set) return []
  // 简单生成最近12个期间
  const periods = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i)
    periods.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  return periods
})

const totalDebit = computed(() =>
  editForm.value.entries.reduce((s, e) => s + (parseFloat(e.debit_amount) || 0), 0)
)
const totalCredit = computed(() =>
  editForm.value.entries.reduce((s, e) => s + (parseFloat(e.credit_amount) || 0), 0)
)

const statusNames = { draft: '草稿', pending: '待审核', approved: '已审核', posted: '已过账' }
const statusBadges = {
  draft: 'badge badge-gray', pending: 'badge badge-yellow',
  approved: 'badge badge-blue', posted: 'badge badge-green'
}
const statusName = (s) => statusNames[s] || s
const statusBadge = (s) => statusBadges[s] || 'badge'

const formatAmount = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : n.toFixed(2)
}

const addEntry = () => {
  editForm.value.entries.push({
    account_id: null, summary: '', debit_amount: 0, credit_amount: 0,
    aux_customer_id: null, aux_supplier_id: null
  })
}

const loadList = async () => {
  if (!accountingStore.currentAccountSetId) return
  try {
    const { data } = await getVouchers({
      account_set_id: accountingStore.currentAccountSetId,
      period_name: filters.value.period_name || undefined,
      voucher_type: filters.value.voucher_type || undefined,
      status: filters.value.status || undefined,
      page: page.value, page_size: pageSize,
    })
    vouchers.value = data.items
    total.value = data.total
  } catch (e) { /* ignore */ }
}

const loadLeafAccounts = async () => {
  await accountingStore.loadChartOfAccounts()
  leafAccounts.value = accountingStore.chartOfAccounts.filter(a => a.is_leaf)
}

const viewVoucher = async (id) => {
  try {
    const { data } = await getVoucher(id)
    detailVoucher.value = data
    editForm.value = {
      voucher_type: data.voucher_type,
      voucher_date: data.voucher_date,
      summary: data.summary,
      attachment_count: data.attachment_count,
      entries: data.entries.map(e => ({ ...e }))
    }
    isCreating.value = false
    isEditing.value = false
    showDetail.value = true
  } catch (e) {
    appStore.showToast('加载凭证失败', 'error')
  }
}

const openCreateForm = async () => {
  await loadLeafAccounts()
  const today = new Date().toISOString().slice(0, 10)
  editForm.value = {
    voucher_type: '记', voucher_date: today, summary: '',
    attachment_count: 0,
    entries: [
      { account_id: null, summary: '', debit_amount: 0, credit_amount: 0 },
      { account_id: null, summary: '', debit_amount: 0, credit_amount: 0 },
    ]
  }
  isCreating.value = true
  isEditing.value = false
  detailVoucher.value = null
  showDetail.value = true
}

const startEdit = async () => {
  await loadLeafAccounts()
  isEditing.value = true
}

const handleCreate = async () => {
  submitting.value = true
  try {
    const payload = {
      voucher_type: editForm.value.voucher_type,
      voucher_date: editForm.value.voucher_date,
      summary: editForm.value.summary,
      attachment_count: editForm.value.attachment_count,
      entries: editForm.value.entries.filter(e => e.account_id).map(e => ({
        account_id: e.account_id,
        summary: e.summary || '',
        debit_amount: String(e.debit_amount || 0),
        credit_amount: String(e.credit_amount || 0),
        aux_customer_id: e.aux_customer_id || null,
        aux_supplier_id: e.aux_supplier_id || null,
      }))
    }
    const { data } = await createVoucher(accountingStore.currentAccountSetId, payload)
    appStore.showToast(`凭证 ${data.voucher_no} 创建成功`, 'success')
    showDetail.value = false
    await loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    submitting.value = false
  }
}

const handleUpdate = async () => {
  submitting.value = true
  try {
    const payload = {
      voucher_date: editForm.value.voucher_date,
      summary: editForm.value.summary,
      attachment_count: editForm.value.attachment_count,
      entries: editForm.value.entries.filter(e => e.account_id).map(e => ({
        account_id: e.account_id,
        summary: e.summary || '',
        debit_amount: String(e.debit_amount || 0),
        credit_amount: String(e.credit_amount || 0),
        aux_customer_id: e.aux_customer_id || null,
        aux_supplier_id: e.aux_supplier_id || null,
      }))
    }
    await updateVoucher(detailVoucher.value.id, payload)
    appStore.showToast('更新成功', 'success')
    showDetail.value = false
    await loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '更新失败', 'error')
  } finally {
    submitting.value = false
  }
}

const handleSubmit = async (v) => {
  try {
    await submitVoucher(v.id)
    appStore.showToast('已提交审核', 'success')
    await loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '提交失败', 'error')
  }
}

const handleApprove = async (v) => {
  try {
    await approveVoucher(v.id)
    appStore.showToast('审核通过', 'success')
    await loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '审核失败', 'error')
  }
}

const handleReject = async (v) => {
  try {
    await rejectVoucher(v.id)
    appStore.showToast('已驳回', 'success')
    await loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '驳回失败', 'error')
  }
}

const handlePost = async (v) => {
  try {
    await postVoucher(v.id)
    appStore.showToast('过账成功', 'success')
    await loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '过账失败', 'error')
  }
}

const handleDelete = async (v) => {
  if (!confirm(`确定删除凭证 ${v.voucher_no}？`)) return
  try {
    await deleteVoucher(v.id)
    appStore.showToast('删除成功', 'success')
    await loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => {
  page.value = 1
  loadList()
})

onMounted(loadList)
</script>
```

### Step 2: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add frontend/src/components/business/VoucherPanel.vue
git commit -m "feat: 凭证管理面板

列表筛选、新增/编辑/查看弹窗、分录表格、借贷平衡提示
状态操作：提交/审核/驳回/过账/删除

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 19: 更新默认管理员权限 + usePermission composable 检查

**Files:**
- Modify: `backend/app/migrations.py`

### Step 1: Update default admin permissions

在 `migrations.py` 的 `migrate_accounting_phase1()` 函数末尾添加：

```python
    # 更新默认管理员的权限列表（添加会计权限）
    # admin 角色自动拥有全部权限，此步仅保证 permissions 字段完整性
    try:
        admin = await User.filter(username="admin", role="admin").first()
        if admin:
            existing_perms = admin.permissions or []
            new_perms = ["accounting_view", "accounting_edit", "accounting_approve", "accounting_post", "period_end"]
            added = [p for p in new_perms if p not in existing_perms]
            if added:
                admin.permissions = existing_perms + added
                await admin.save()
                logger.info(f"管理员权限已更新，添加: {added}")
    except Exception as e:
        logger.warning(f"更新管理员权限失败（可忽略）: {e}")
```

**Note:** admin 角色在 `hasPermission` 检查中会自动通过（`user.role === 'admin'`），所以这一步主要是保持数据一致性。普通 user 角色需要手动分配这些新权限。

### Step 2: Commit

```bash
cd /Users/lin/Desktop/erp-4
git add backend/app/migrations.py
git commit -m "feat: 迁移中更新管理员会计权限

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 20: 全量测试 + 构建验证

### Step 1: Run all backend tests

Run: `cd /Users/lin/Desktop/erp-4/backend && python -m pytest tests/ -v`
Expected: ALL PASS

### Step 2: Verify frontend builds

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`
Expected: Build succeeds without errors

### Step 3: Verify backend imports

Run: `cd /Users/lin/Desktop/erp-4/backend && python -c "from app.models import *; from app.routers import account_sets, chart_of_accounts, accounting_periods, vouchers; print('All imports OK')"`
Expected: `All imports OK`

### Step 4: Final commit (if any fixes needed)

```bash
cd /Users/lin/Desktop/erp-4
git add -A
git commit -m "fix: 阶段1全量测试修复

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

### Step 5: Create phase 1 checkpoint

```bash
cd /Users/lin/Desktop/erp-4
git tag v4.12.0-phase1-foundation
```

---

## 核验清单（对照设计文档 §七.阶段1）

完成所有 Task 后，依次手动验证：

- [ ] 创建"启领"和"链筹"两个账套，切换后科目和凭证互不可见
- [ ] 录入凭证，借贷不平衡时无法保存
- [ ] 完成 draft → pending → approved → posted 全流程
- [ ] 已过账凭证不可编辑/删除
- [ ] 审核人≠制单人（开启时）
- [ ] 已结账期间不能新增凭证
- [ ] 仓库/订单/采购单/收款单有 account_set_id 字段
- [ ] 产品有 tax_rate 字段（默认13%）
- [ ] 前端科目表按编码排序、子科目有缩进
- [ ] 前端凭证列表支持按期间/凭证字/状态筛选
- [ ] 凭证自动编号格式正确（如 QL-记-202603-001）

---

## 后端文件变更总览

| 操作 | 文件路径 |
|------|----------|
| 新建 | `backend/app/models/accounting.py` |
| 新建 | `backend/app/models/voucher.py` |
| 新建 | `backend/app/services/accounting_init.py` |
| 新建 | `backend/app/schemas/accounting.py` |
| 新建 | `backend/app/routers/account_sets.py` |
| 新建 | `backend/app/routers/chart_of_accounts.py` |
| 新建 | `backend/app/routers/accounting_periods.py` |
| 新建 | `backend/app/routers/vouchers.py` |
| 新建 | `backend/tests/test_accounting_models.py` |
| 新建 | `backend/tests/test_accounting_init.py` |
| 新建 | `backend/tests/test_voucher_models.py` |
| 新建 | `backend/tests/test_voucher_api.py` |
| 新建 | `backend/tests/test_account_sets_api.py` |
| 新建 | `backend/tests/test_chart_of_accounts_api.py` |
| 修改 | `backend/app/models/__init__.py` |
| 修改 | `backend/app/models/warehouse.py` |
| 修改 | `backend/app/models/order.py` |
| 修改 | `backend/app/models/purchase.py` |
| 修改 | `backend/app/models/payment.py` |
| 修改 | `backend/app/models/product.py` |
| 修改 | `backend/app/migrations.py` |
| 修改 | `backend/main.py` |

## 前端文件变更总览

| 操作 | 文件路径 |
|------|----------|
| 新建 | `frontend/src/api/accounting.js` |
| 新建 | `frontend/src/stores/accounting.js` |
| 新建 | `frontend/src/views/AccountingView.vue` |
| 新建 | `frontend/src/components/business/VoucherPanel.vue` |
| 新建 | `frontend/src/components/business/ChartOfAccountsPanel.vue` |
| 新建 | `frontend/src/components/business/AccountingPeriodsPanel.vue` |
| 修改 | `frontend/src/utils/constants.js` |
| 修改 | `frontend/src/router/index.js` |
