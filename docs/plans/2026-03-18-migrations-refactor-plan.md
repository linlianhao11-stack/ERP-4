# 迁移系统版本化改造 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 1201 行单文件 `app/migrations.py` 拆分为版本化迁移系统，每个迁移独立文件，通过 `migration_history` 表追踪执行状态，只执行增量迁移。

**Architecture:** 自研轻量版本化迁移运行器（~80 行），迁移文件按 `vNNN_name.py` 编号存放在 `app/migrations/` 目录下，每个文件导出 `async def up(conn)` 函数。运行器启动时扫描文件、对比已执行列表、只跑新的。已有数据库通过基线检测自动标记历史迁移为已执行。

**Tech Stack:** Python 3.9+, asyncpg (raw connection), Tortoise ORM, PostgreSQL 16

**设计文档:** `docs/plans/2026-03-18-migrations-refactor-design.md`

---

## 重要上下文

- `main.py:18` 和 `app/routers/backup.py:28` 两处 import `from app.migrations import run_migrations`
- 改造后 `app/migrations/` 变成 package，`__init__.py` 导出 `run_migrations()`，两处 import 不用改
- 测试用 SQLite 内存数据库（`tests/conftest.py`），迁移运行器只在 PostgreSQL 下运行
- `app/ai/schema_registry.py:9` 有个 `aerich` 在 EXCLUDED_TABLES 里，不影响
- 现有 28 个迁移函数的执行顺序很重要（DDL 在前，ORM 查询在后），拆分时必须保持

---

### Task 1: 创建迁移运行器 runner.py

**Files:**
- Create: `app/migrations/__init__.py`
- Create: `app/migrations/runner.py`

**Step 1: 创建 `app/migrations/` 目录和 `__init__.py`**

```python
# app/migrations/__init__.py
"""版本化迁移系统"""
from app.migrations.runner import run_migrations

__all__ = ["run_migrations"]
```

**Step 2: 实现 `runner.py`**

```python
"""版本化迁移运行器

启动时：
1. 获取 pg_advisory_lock 防并发
2. 确保 migration_history 表存在
3. 扫描 v*.py 文件，对比已执行列表
4. 已有数据库：自动标记基线迁移为已执行
5. 按版本号顺序执行未运行的迁移
"""
from __future__ import annotations

import importlib
import os
import re
from datetime import datetime, timezone

from tortoise import connections

from app.logger import get_logger

logger = get_logger("migrations")

# 匹配 vNNN_name.py 格式
_VERSION_RE = re.compile(r"^(v\d{3})_.+\.py$")

# 基线版本：v001-v028 是从旧 migrations.py 拆分出的，已有数据库不需要重新执行
_BASELINE_MAX = "v028"


async def run_migrations():
    """迁移入口（与旧 API 保持一致）"""
    pool = connections.get("default")
    raw_conn = await pool._pool.acquire()
    try:
        await raw_conn.execute("SELECT pg_advisory_lock(20260315)")
        try:
            await _run_versioned_migrations()
        finally:
            await raw_conn.execute("SELECT pg_advisory_unlock(20260315)")
    finally:
        await pool._pool.release(raw_conn)


async def _ensure_history_table(conn):
    """确保 migration_history 表存在"""
    await conn.execute_query("""
        CREATE TABLE IF NOT EXISTS migration_history (
            id SERIAL PRIMARY KEY,
            version VARCHAR(10) NOT NULL UNIQUE,
            name VARCHAR(200) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


async def _get_applied_versions(conn) -> set[str]:
    """获取已执行的迁移版本号集合"""
    rows = await conn.execute_query_dict(
        "SELECT version FROM migration_history"
    )
    return {row["version"] for row in rows}


def _discover_migrations() -> list[tuple[str, str]]:
    """扫描 migrations/ 目录，返回 [(version, module_name), ...] 按版本排序"""
    migrations_dir = os.path.dirname(__file__)
    results = []
    for filename in os.listdir(migrations_dir):
        match = _VERSION_RE.match(filename)
        if match:
            version = match.group(1)
            module_name = filename[:-3]  # 去掉 .py
            results.append((version, module_name))
    results.sort(key=lambda x: x[0])
    return results


async def _is_existing_database(conn) -> bool:
    """检测是否为已有数据库（基线标志：users.password_changed_at 列存在）"""
    rows = await conn.execute_query_dict(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'password_changed_at'"
    )
    return len(rows) > 0


async def _mark_baseline(conn, migrations: list[tuple[str, str]]):
    """将基线迁移（v001-v028）标记为已执行"""
    baseline = [(v, name) for v, name in migrations if v <= _BASELINE_MAX]
    if not baseline:
        return
    for version, name in baseline:
        await conn.execute_query(
            "INSERT INTO migration_history (version, name) VALUES ($1, $2) "
            "ON CONFLICT (version) DO NOTHING",
            [version, name]
        )
    logger.info(f"基线迁移已标记: {baseline[0][0]}-{baseline[-1][0]} ({len(baseline)} 个)")


async def _run_versioned_migrations():
    """执行版本化迁移"""
    conn = connections.get("default")

    await _ensure_history_table(conn)

    all_migrations = _discover_migrations()
    if not all_migrations:
        logger.info("无迁移文件")
        return

    applied = await _get_applied_versions(conn)

    # 已有数据库 + history 表为空 → 标记基线
    if not applied and await _is_existing_database(conn):
        await _mark_baseline(conn, all_migrations)
        applied = await _get_applied_versions(conn)

    # 筛选未执行的迁移
    pending = [(v, name) for v, name in all_migrations if v not in applied]
    if not pending:
        logger.info(f"数据库迁移已是最新 ({len(all_migrations)} 个迁移)")
        return

    logger.info(f"发现 {len(pending)} 个待执行迁移")
    for version, module_name in pending:
        logger.info(f"执行迁移: {module_name}")
        try:
            mod = importlib.import_module(f"app.migrations.{module_name}")
            await mod.up(conn)
            await conn.execute_query(
                "INSERT INTO migration_history (version, name) VALUES ($1, $2)",
                [version, module_name]
            )
            logger.info(f"迁移完成: {module_name}")
        except Exception as e:
            logger.error(f"迁移失败: {module_name} — {e}")
            raise  # 迁移失败应阻止启动

    logger.info(f"所有迁移执行完成 (新执行 {len(pending)} 个)")
```

**Step 3: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && python -c "import ast; ast.parse(open('app/migrations/runner.py').read()); print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add app/migrations/__init__.py app/migrations/runner.py
git commit -m "feat: 创建版本化迁移运行器 runner.py"
```

---

### Task 2: 拆分迁移文件 v001-v009（种子数据 + 用户/订单字段 + 发货流程）

**Files:**
- Create: `app/migrations/v001_init_seeds.py`
- Create: `app/migrations/v002_location_warehouse.py`
- Create: `app/migrations/v003_user_fields.py`
- Create: `app/migrations/v004_order_fields.py`
- Create: `app/migrations/v005_order_item_warehouse.py`
- Create: `app/migrations/v006_purchase_order_fields.py`
- Create: `app/migrations/v007_purchase_return_fields.py`
- Create: `app/migrations/v008_timestamp_columns.py`
- Create: `app/migrations/v009_shipping_flow.py`

**Step 1: 创建 v001（种子数据 — 从 `_run_migrations_inner` L51-96 提取）**

```python
"""v001: 初始化种子数据（管理员、收款/付款方式、默认仓库）"""
from app.auth.password import hash_password
from app.models import User, Warehouse, PaymentMethod, DisbursementMethod


async def up(conn):
    # 初始化默认收款方式
    if not await PaymentMethod.exists():
        defaults = [
            ("cash", "现金", 1),
            ("bank_public", "对公转账", 2),
            ("bank_private", "对私转账", 3),
            ("wechat", "微信", 4),
            ("alipay", "支付宝", 5),
        ]
        for code, name, sort in defaults:
            await PaymentMethod.create(code=code, name=name, sort_order=sort)

    # 初始化默认付款方式
    if not await DisbursementMethod.exists():
        defaults = [
            ("bank_public", "对公转账", 1),
            ("bank_private", "对私转账", 2),
            ("wechat", "微信", 3),
            ("alipay", "支付宝", 4),
            ("cash", "现金", 5),
        ]
        for code, name, sort in defaults:
            await DisbursementMethod.create(code=code, name=name, sort_order=sort)

    # 创建默认管理员
    admin = await User.filter(username="admin").first()
    if not admin:
        await User.create(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="系统管理员",
            role="admin",
            must_change_password=True,
            permissions=["dashboard", "sales", "stock_view", "stock_edit", "finance",
                         "logs", "admin", "purchase", "purchase_pay", "purchase_receive",
                         "purchase_approve"]
        )

    # 创建默认仓库
    if not await Warehouse.filter(is_default=True).exists():
        await Warehouse.create(name="默认仓库", is_default=True)
```

**Step 2: 创建 v002（仓位关联仓库 — 从 `migrate_location_warehouse` L131-176 提取）**

```python
"""v002: 仓位关联仓库"""
from app.models import Warehouse
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    default_wh = await Warehouse.filter(is_default=True).first()
    if not default_wh:
        return

    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'locations'"
    )
    has_warehouse_id = any(col["name"] == "warehouse_id" for col in columns)

    if not has_warehouse_id:
        wh_id = int(default_wh.id)
        await conn.execute_query(
            f"ALTER TABLE locations ADD COLUMN IF NOT EXISTS warehouse_id INT REFERENCES warehouses(id) DEFAULT {wh_id}"
        )
        await conn.execute_query(
            "UPDATE locations SET warehouse_id = $1 WHERE warehouse_id IS NULL", [wh_id]
        )
        try:
            await conn.execute_query("DROP INDEX IF EXISTS uid_locations_code_91776a")
        except Exception:
            pass
        try:
            await conn.execute_query("ALTER TABLE locations DROP CONSTRAINT IF EXISTS locations_code_key")
        except Exception:
            pass
        try:
            await conn.execute_query(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_location_warehouse_code ON locations(warehouse_id, code)"
            )
        except Exception:
            pass
        logger.info("迁移完成: 现有仓位已归入默认仓库")
    else:
        null_count = await conn.execute_query_dict(
            "SELECT COUNT(*) as cnt FROM locations WHERE warehouse_id IS NULL"
        )
        if null_count and null_count[0]["cnt"] > 0:
            await conn.execute_query(
                "UPDATE locations SET warehouse_id = $1 WHERE warehouse_id IS NULL", [int(default_wh.id)]
            )
```

**Step 3: 创建 v003（用户字段 — 从 `migrate_user_must_change_password` L379-391 + `migrate_user_token_version` L444-449 + `migrate_user_password_changed_at` L1153-1160 提取）**

```python
"""v003: 用户表新增字段（must_change_password, token_version, password_changed_at）"""


async def up(conn):
    # must_change_password
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'users'"
    )
    col_names = [col["name"] for col in columns]

    if "must_change_password" not in col_names:
        await conn.execute_query(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE"
        )

    # token_version
    await conn.execute_query(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INT DEFAULT 0"
    )

    # password_changed_at
    try:
        await conn.execute_query("ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMPTZ")
    except Exception:
        pass  # 列已存在
```

**Step 4: 创建 v004（订单字段 — 从 `migrate_order_updated_at` L452-460 提取）**

```python
"""v004: orders 表新增 updated_at 列"""


async def up(conn):
    await conn.execute_query(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
    )
    await conn.execute_query(
        "UPDATE orders SET updated_at = created_at WHERE updated_at IS NULL"
    )
```

**Step 5: 创建 v005（订单行仓库字段 — 从 `migrate_order_item_warehouse` L179-198 提取）**

```python
"""v005: order_items 表新增 warehouse_id 和 location_id 列"""


async def up(conn):
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'order_items'"
    )
    col_names = [col["name"] for col in columns]

    if "warehouse_id" not in col_names:
        await conn.execute_query(
            "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS warehouse_id INT REFERENCES warehouses(id) ON DELETE SET NULL"
        )

    if "location_id" not in col_names:
        await conn.execute_query(
            "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS location_id INT REFERENCES locations(id) ON DELETE SET NULL"
        )
```

**Step 6: 创建 v006（采购单付款方式 — 从 `migrate_purchase_order_payment_method` L294-306 提取）**

```python
"""v006: purchase_orders 表新增 payment_method 列"""


async def up(conn):
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    col_names = [col["name"] for col in columns]

    if "payment_method" not in col_names:
        await conn.execute_query(
            "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50)"
        )
```

**Step 7: 创建 v007（采购退货字段 — 从 `migrate_purchase_return_fields` L309-356 提取）**

```python
"""v007: 采购相关表新增退货字段"""
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # purchase_orders 表
    po_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    po_col_names = [col["name"] for col in po_columns]

    po_new_cols = [
        ("return_tracking_no", "VARCHAR(100)"),
        ("is_refunded", "BOOLEAN DEFAULT FALSE"),
        ("return_amount", "DECIMAL(12,2) DEFAULT 0"),
        ("credit_used", "DECIMAL(12,2) DEFAULT 0"),
        ("returned_by_id", "INT REFERENCES users(id)"),
        ("returned_at", "TIMESTAMPTZ"),
    ]
    for col_name, col_type in po_new_cols:
        if col_name not in po_col_names:
            await conn.execute_query(f"ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS {col_name} {col_type}")

    # purchase_order_items 表
    poi_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_order_items'"
    )
    poi_col_names = [col["name"] for col in poi_columns]

    if "returned_quantity" not in poi_col_names:
        await conn.execute_query("ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS returned_quantity INT DEFAULT 0")

    # suppliers 表
    sup_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'suppliers'"
    )
    sup_col_names = [col["name"] for col in sup_columns]

    if "credit_balance" not in sup_col_names:
        await conn.execute_query("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS credit_balance DECIMAL(12,2) DEFAULT 0")

    # rebate_logs.type 列扩展到 20 字符
    try:
        await conn.execute_query("ALTER TABLE rebate_logs ALTER COLUMN type TYPE VARCHAR(20)")
    except Exception:
        pass
```

**Step 8: 创建 v008（时间戳列 — 从 `migrate_add_timestamp_columns` L359-376 提取）**

```python
"""v008: 为缺少时间戳的表添加 updated_at / created_at 列"""


async def up(conn):
    additions = [
        ("customers", "updated_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("suppliers", "updated_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("employees", "updated_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("purchase_order_items", "created_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("shipment_items", "created_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("payment_orders", "created_at", "TIMESTAMPTZ DEFAULT NOW()"),
    ]
    for table, col, col_type in additions:
        try:
            await conn.execute_query(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
            )
        except Exception:
            pass
```

**Step 9: 创建 v009（发货流程 — 从 `migrate_shipping_flow` L394-441 提取）**

```python
"""v009: 发货流程重构迁移（reserved_qty, shipping_status, shipped_qty, shipment_items 表）"""
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # warehouse_stocks.reserved_qty
    ws_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'warehouse_stocks'"
    )
    if "reserved_qty" not in [c["name"] for c in ws_columns]:
        await conn.execute_query("ALTER TABLE warehouse_stocks ADD COLUMN IF NOT EXISTS reserved_qty INT DEFAULT 0")

    # orders.shipping_status
    o_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'orders'"
    )
    if "shipping_status" not in [c["name"] for c in o_columns]:
        await conn.execute_query(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_status VARCHAR(20) DEFAULT 'completed'"
        )

    # order_items.shipped_qty
    oi_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'order_items'"
    )
    if "shipped_qty" not in [c["name"] for c in oi_columns]:
        await conn.execute_query("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS shipped_qty INT DEFAULT 0")
        await conn.execute_query("UPDATE order_items SET shipped_qty = ABS(quantity) WHERE shipped_qty = 0")

    # shipment_items 表
    tables = await conn.execute_query_dict(
        "SELECT table_name as name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'shipment_items'"
    )
    if not any(t["name"] == "shipment_items" for t in tables):
        await conn.execute_query("""
            CREATE TABLE shipment_items (
                id SERIAL PRIMARY KEY,
                shipment_id INT NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
                order_item_id INT NOT NULL REFERENCES order_items(id) ON DELETE RESTRICT,
                product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
                quantity INT NOT NULL,
                sn_codes TEXT
            )
        """)
        await conn.execute_query("CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment ON shipment_items(shipment_id)")
        await conn.execute_query("CREATE INDEX IF NOT EXISTS idx_shipment_items_order_item ON shipment_items(order_item_id)")
```

**Step 10: 验证所有文件语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && for f in app/migrations/v00{1..9}_*.py; do python -c "import ast; ast.parse(open('$f').read())"; done && echo "ALL OK"`
Expected: `ALL OK`

**Step 11: Commit**

```bash
git add app/migrations/v001_init_seeds.py app/migrations/v002_location_warehouse.py app/migrations/v003_user_fields.py app/migrations/v004_order_fields.py app/migrations/v005_order_item_warehouse.py app/migrations/v006_purchase_order_fields.py app/migrations/v007_purchase_return_fields.py app/migrations/v008_timestamp_columns.py app/migrations/v009_shipping_flow.py
git commit -m "refactor: 拆分迁移文件 v001-v009（种子数据/用户/订单/发货）"
```

---

### Task 3: 拆分迁移文件 v010-v019（索引 + 会计模块 + 采购退货 + 发票）

**Files:**
- Create: `app/migrations/v010_performance_indexes.py`
- Create: `app/migrations/v011_accounting_phase1.py`
- Create: `app/migrations/v012_accounting_phase3.py`
- Create: `app/migrations/v013_accounting_phase4.py`
- Create: `app/migrations/v014_accounting_phase5.py`
- Create: `app/migrations/v015_supplier_account_balance.py`
- Create: `app/migrations/v016_customer_account_balance.py`
- Create: `app/migrations/v017_purchase_returns_table.py`
- Create: `app/migrations/v018_invoice_pdf_files.py`
- Create: `app/migrations/v019_shipment_no.py`

**Step 1: 创建 v010（性能索引 — 从 `migrate_add_indexes` L200-291 提取）**

```python
"""v010: 性能索引 + warehouses.customer_id FK + 部分索引"""
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    indexes = [
        ("idx_stock_logs_type_date", "stock_logs", "change_type, created_at"),
        ("idx_stock_logs_product", "stock_logs", "product_id"),
        ("idx_orders_type_date", "orders", "order_type, created_at"),
        ("idx_orders_customer_date", "orders", "customer_id, created_at"),
        ("idx_order_items_order", "order_items", "order_id"),
        ("idx_order_items_product", "order_items", "product_id"),
        ("idx_payments_customer_confirmed", "payments", "customer_id, is_confirmed"),
        ("idx_sn_codes_status", "sn_codes", "status"),
        ("idx_rebate_logs_target", "rebate_logs", "target_type, target_id"),
        ("idx_shipments_order", "shipments", "order_id"),
        ("idx_warehouse_stocks_product", "warehouse_stocks", "product_id"),
        ("idx_payment_orders_payment", "payment_orders", "payment_id"),
        ("idx_payment_orders_order", "payment_orders", "order_id"),
        ("idx_customers_name", "customers", "name"),
        ("idx_suppliers_name", "suppliers", "name"),
        ("idx_products_name", "products", "name"),
        ("idx_products_sku", "products", "sku"),
        ("idx_shipments_tracking_no", "shipments", "tracking_no"),
        ("idx_operation_logs_target", "operation_logs", "target_type, target_id"),
        ("idx_operation_logs_created_at", "operation_logs", "created_at"),
        ("idx_sn_codes_warehouse_product", "sn_codes", "warehouse_id, product_id, status"),
        ("idx_stock_logs_warehouse_product", "stock_logs", "warehouse_id, product_id"),
        ("idx_purchase_orders_status", "purchase_orders", "status"),
        ("idx_purchase_orders_supplier_created", "purchase_orders", "supplier_id, created_at"),
        ("idx_products_is_active", "products", "is_active"),
        ("idx_customers_is_active", "customers", "is_active"),
        ("idx_suppliers_is_active", "suppliers", "is_active"),
        ("idx_orders_shipping_status", "orders", "shipping_status"),
        ("idx_warehouse_stocks_wh_product", "warehouse_stocks", "warehouse_id, product_id"),
        ("idx_vouchers_status", "vouchers", "status"),
        ("idx_shipments_status_date", "shipments", "status, created_at"),
        ("idx_operation_logs_operator_date", "operation_logs", "operator_id, created_at"),
        ("idx_orders_is_cleared", "orders", "is_cleared"),
        ("idx_orders_created_desc", "orders", "created_at DESC, id DESC"),
        ("idx_orders_updated_desc", "orders", "updated_at DESC, id DESC"),
        ("idx_stock_logs_created_desc", "stock_logs", "created_at DESC, id DESC"),
        ("idx_operation_logs_created_desc", "operation_logs", "created_at DESC, id DESC"),
        ("idx_payments_is_confirmed", "payments", "is_confirmed"),
        ("idx_orders_account_set", "orders", "account_set_id"),
        ("idx_orders_order_type", "orders", "order_type"),
        ("idx_stock_logs_change_ref", "stock_logs", "change_type, reference_type, reference_id"),
        ("idx_warehouse_stocks_qty", "warehouse_stocks", "quantity"),
    ]
    for name, table, columns in indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败: {e}")

    # warehouses.customer_id FK
    try:
        await conn.execute_query(
            "ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS customer_id INT REFERENCES customers(id) ON DELETE SET NULL"
        )
    except Exception:
        pass

    # 部分唯一索引：虚拟仓库每个客户只能有一个
    try:
        await conn.execute_query(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouse_customer_virtual ON warehouses(customer_id) WHERE is_virtual = TRUE AND customer_id IS NOT NULL"
        )
    except Exception:
        pass

    # 商品分类/品牌部分索引
    try:
        await conn.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category) WHERE category IS NOT NULL AND category != ''"
        )
    except Exception:
        pass

    try:
        await conn.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand) WHERE brand IS NOT NULL AND brand != ''"
        )
    except Exception:
        pass
```

**Step 2: 创建 v011（会计阶段1 — 从 `migrate_accounting_phase1` L463-568 提取）**

```python
"""v011: 阶段1财务基础设施迁移（现有表新增字段 + 会计索引）"""
from app.models import User
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise

    # 凭证表结构升级（旧表→新表）
    v_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'vouchers'"
    )
    v_col_names = [c["name"] for c in v_cols]
    if "company_name" in v_col_names or ("account_set_id" not in v_col_names and v_cols):
        await conn.execute_query("DROP TABLE IF EXISTS voucher_entries CASCADE")
        await conn.execute_query("DROP TABLE IF EXISTS vouchers CASCADE")
        try:
            await Tortoise.generate_schemas(safe=True)
        except Exception:
            pass

    # Warehouse: account_set_id
    wh_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'warehouses'"
    )
    if "account_set_id" not in [c["name"] for c in wh_cols]:
        await conn.execute_query(
            "ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )

    # Orders: account_set_id
    o_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'orders'"
    )
    if "account_set_id" not in [c["name"] for c in o_cols]:
        await conn.execute_query(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )

    # PurchaseOrders: account_set_id
    po_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    if "account_set_id" not in [c["name"] for c in po_cols]:
        await conn.execute_query(
            "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )

    # Payments: account_set_id
    pay_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'payments'"
    )
    if "account_set_id" not in [c["name"] for c in pay_cols]:
        await conn.execute_query(
            "ALTER TABLE payments ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )

    # Products: tax_rate
    prod_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'products'"
    )
    if "tax_rate" not in [c["name"] for c in prod_cols]:
        await conn.execute_query(
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS tax_rate DECIMAL(5,2) DEFAULT 13.00"
        )

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
        except Exception:
            pass

    # 更新管理员权限
    try:
        admin = await User.filter(username="admin", role="admin").first()
        if admin:
            existing_perms = admin.permissions or []
            new_perms = ["accounting_view", "accounting_edit", "accounting_approve", "accounting_post", "period_end"]
            added = [p for p in new_perms if p not in existing_perms]
            if added:
                admin.permissions = existing_perms + added
                await admin.save()
    except Exception:
        pass
```

**Step 3: 创建 v012（会计阶段3 — 从 `migrate_accounting_phase3` L571-614 提取）**

```python
"""v012: 阶段3应收应付迁移（7张新表 + 索引 + AR/AP权限）"""
from app.models import User
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise
    try:
        await Tortoise.generate_schemas(safe=True)
    except Exception:
        pass

    ar_ap_indexes = [
        ("idx_receivable_bills_set_customer", "receivable_bills", "account_set_id, customer_id"),
        ("idx_receivable_bills_set_status", "receivable_bills", "account_set_id, status"),
        ("idx_receipt_bills_customer", "receipt_bills", "customer_id"),
        ("idx_receipt_bills_receivable", "receipt_bills", "receivable_bill_id"),
        ("idx_receipt_refund_bills_original", "receipt_refund_bills", "original_receipt_id"),
        ("idx_receivable_write_offs_receivable", "receivable_write_offs", "receivable_bill_id"),
        ("idx_payable_bills_set_supplier", "payable_bills", "account_set_id, supplier_id"),
        ("idx_payable_bills_set_status", "payable_bills", "account_set_id, status"),
        ("idx_disbursement_bills_payable", "disbursement_bills", "payable_bill_id"),
        ("idx_disbursement_refund_bills_original", "disbursement_refund_bills", "original_disbursement_id"),
    ]
    for name, table, columns in ar_ap_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception:
            pass

    # admin 用户添加 AR/AP 权限
    new_perms = [
        "accounting_ar_view", "accounting_ar_edit", "accounting_ar_confirm",
        "accounting_ap_view", "accounting_ap_edit", "accounting_ap_confirm",
    ]
    admin = await User.filter(username="admin").first()
    if admin:
        current = admin.permissions or []
        added = [p for p in new_perms if p not in current]
        if added:
            admin.permissions = current + added
            await admin.save()
```

**Step 4: 创建 v013（会计阶段4 — 从 `migrate_accounting_phase4` L617-660 提取）**

```python
"""v013: 阶段4迁移（出入库单+发票 6表 + 索引 + 科目补充）"""
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise
    try:
        await Tortoise.generate_schemas(safe=True)
    except Exception:
        pass

    indexes = [
        ("idx_sdb_account_customer", "sales_delivery_bills", "account_set_id, customer_id"),
        ("idx_sdb_order", "sales_delivery_bills", "order_id"),
        ("idx_sdi_bill", "sales_delivery_items", "delivery_bill_id"),
        ("idx_prb_account_supplier", "purchase_receipt_bills", "account_set_id, supplier_id"),
        ("idx_prb_po", "purchase_receipt_bills", "purchase_order_id"),
        ("idx_pri_bill", "purchase_receipt_items", "receipt_bill_id"),
        ("idx_inv_account_direction", "invoices", "account_set_id, direction"),
        ("idx_inv_account_status", "invoices", "account_set_id, status"),
        ("idx_inv_receivable", "invoices", "receivable_bill_id"),
        ("idx_inv_payable", "invoices", "payable_bill_id"),
        ("idx_inv_items_invoice", "invoice_items", "invoice_id"),
    ]
    for idx_name, table, columns in indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
        except Exception:
            pass

    # 补充 1407 发出商品科目
    try:
        from app.models.accounting import AccountSet, ChartOfAccount
        account_sets = await AccountSet.all()
        for a in account_sets:
            exists = await ChartOfAccount.filter(account_set_id=a.id, code="1407").exists()
            if not exists:
                await ChartOfAccount.create(
                    account_set_id=a.id, code="1407", name="发出商品",
                    level=1, category="asset", direction="debit", is_leaf=True
                )
    except Exception:
        pass
```

**Step 5: 创建 v014（会计阶段5 — 从 `migrate_accounting_phase5` L663-673 提取）**

```python
"""v014: 阶段5迁移（确保 period_end 权限）"""
from app.models import User


async def up(conn):
    admin = await User.filter(username="admin").first()
    if admin:
        current = admin.permissions or []
        if "period_end" not in current:
            admin.permissions = current + ["period_end"]
            await admin.save()
```

**Step 6: 创建 v015（供应商账套余额 — 从 `migrate_supplier_account_balance` L676-753 提取）**

```python
"""v015: 供应商返利按账套隔离（新表 + RebateLog 新列 + 数据迁移 + 预置科目）"""
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise
    try:
        await Tortoise.generate_schemas(safe=True)
    except Exception:
        pass

    # RebateLog 增加 account_set_id 列
    rl_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'rebate_logs'"
    )
    if "account_set_id" not in [c["name"] for c in rl_cols]:
        await conn.execute_query(
            "ALTER TABLE rebate_logs ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )

    # 索引
    sab_indexes = [
        ("idx_supplier_account_balances_supplier", "supplier_account_balances", "supplier_id"),
        ("idx_supplier_account_balances_account_set", "supplier_account_balances", "account_set_id"),
        ("idx_rebate_logs_account_set", "rebate_logs", "account_set_id"),
    ]
    for name, table, columns in sab_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception:
            pass

    # 迁移现有余额数据到第一个活跃账套
    from app.models.accounting import AccountSet, ChartOfAccount
    from app.models.supplier_balance import SupplierAccountBalance

    first_set = await AccountSet.filter(is_active=True).order_by("id").first()
    if first_set:
        rows = await conn.execute_query_dict(
            "SELECT id, name, rebate_balance, credit_balance FROM suppliers "
            "WHERE (rebate_balance > 0 OR credit_balance > 0)"
        )
        for row in rows:
            await conn.execute_query(
                "INSERT INTO supplier_account_balances (supplier_id, account_set_id, rebate_balance, credit_balance) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT (supplier_id, account_set_id) DO NOTHING",
                [row["id"], first_set.id, row["rebate_balance"], row["credit_balance"]]
            )

    # 确保凭证所需科目存在
    for aset in await AccountSet.all():
        try:
            await conn.execute_query(
                "INSERT INTO chart_of_accounts (account_set_id, code, name, level, category, direction, is_leaf) "
                "VALUES ($1, '5401', '主营业务成本', 1, 'cost', 'debit', TRUE) "
                "ON CONFLICT (account_set_id, code) DO NOTHING",
                [aset.id]
            )
        except Exception:
            pass
        try:
            await conn.execute_query(
                "INSERT INTO chart_of_accounts (account_set_id, code, name, level, category, direction, is_leaf) "
                "VALUES ($1, '2221', '应交税费', 1, 'liability', 'credit', TRUE) "
                "ON CONFLICT (account_set_id, code) DO NOTHING",
                [aset.id]
            )
        except Exception:
            pass
```

**Step 7: 创建 v016（客户账套余额 — 从 `migrate_customer_account_balance` L756-795 提取）**

```python
"""v016: 客户返利按账套隔离（新表 + 数据迁移）"""
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise
    try:
        await Tortoise.generate_schemas(safe=True)
    except Exception:
        pass

    cab_indexes = [
        ("idx_customer_account_balances_customer", "customer_account_balances", "customer_id"),
        ("idx_customer_account_balances_account_set", "customer_account_balances", "account_set_id"),
    ]
    for name, table, columns in cab_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception:
            pass

    from app.models.accounting import AccountSet

    first_set = await AccountSet.filter(is_active=True).order_by("id").first()
    if first_set:
        rows = await conn.execute_query_dict(
            "SELECT id, name, rebate_balance FROM customers WHERE rebate_balance > 0"
        )
        for row in rows:
            await conn.execute_query(
                "INSERT INTO customer_account_balances (customer_id, account_set_id, rebate_balance) "
                "VALUES ($1, $2, $3) ON CONFLICT (customer_id, account_set_id) DO NOTHING",
                [row["id"], first_set.id, row["rebate_balance"]]
            )
```

**Step 8: 创建 v017（采购退货单表 — 从 `migrate_purchase_returns` L798-830 提取）**

```python
"""v017: 创建采购退货单表"""


async def up(conn):
    await conn.execute_script("""
        CREATE TABLE IF NOT EXISTS purchase_returns (
            id SERIAL PRIMARY KEY,
            return_no VARCHAR(30) UNIQUE NOT NULL,
            purchase_order_id INT NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
            supplier_id INT NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
            account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL,
            total_amount DECIMAL(12,2) DEFAULT 0,
            is_refunded BOOLEAN DEFAULT FALSE,
            refund_status VARCHAR(20) DEFAULT 'pending',
            tracking_no VARCHAR(100),
            reason TEXT,
            created_by_id INT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_pr_po ON purchase_returns(purchase_order_id);
        CREATE INDEX IF NOT EXISTS idx_pr_supplier ON purchase_returns(supplier_id);

        CREATE TABLE IF NOT EXISTS purchase_return_items (
            id SERIAL PRIMARY KEY,
            purchase_return_id INT NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
            purchase_item_id INT REFERENCES purchase_order_items(id) ON DELETE SET NULL,
            product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
            quantity INT NOT NULL,
            unit_price DECIMAL(12,2) NOT NULL,
            amount DECIMAL(12,2) NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pri_return ON purchase_return_items(purchase_return_id);
    """)
```

**Step 9: 创建 v018（发票 PDF — 从 `migrate_invoice_pdf_files` L833-843 提取）**

```python
"""v018: invoices 表新增 pdf_files 列"""


async def up(conn):
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'invoices'"
    )
    if not any(col["name"] == "pdf_files" for col in columns):
        await conn.execute_query(
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS pdf_files JSONB DEFAULT '[]'"
        )
```

**Step 10: 创建 v019（物流单号 — 从 `migrate_shipment_no` L846-857 提取）**

```python
"""v019: shipments 表新增 shipment_no 列"""


async def up(conn):
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'shipments'"
    )
    if not any(col["name"] == "shipment_no" for col in columns):
        await conn.execute_query(
            "ALTER TABLE shipments ADD COLUMN shipment_no VARCHAR(30) UNIQUE"
        )
```

**Step 11: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && for f in app/migrations/v01{0..9}_*.py; do python -c "import ast; ast.parse(open('$f').read())"; done && echo "ALL OK"`

**Step 12: Commit**

```bash
git add app/migrations/v01*.py
git commit -m "refactor: 拆分迁移文件 v010-v019（索引/会计/采购退货/发票）"
```

---

### Task 4: 拆分迁移文件 v020-v028（AI/物流/代采/权限/约束）

**Files:**
- Create: `app/migrations/v020_ai_readonly_user.py`
- Create: `app/migrations/v021_stock_last_activity.py`
- Create: `app/migrations/v022_dropship_module.py`
- Create: `app/migrations/v023_dropship_phone.py`
- Create: `app/migrations/v024_tracking_refresh.py`
- Create: `app/migrations/v025_warehouse_color.py`
- Create: `app/migrations/v026_permission_migrations.py`
- Create: `app/migrations/v027_missing_indexes.py`
- Create: `app/migrations/v028_check_constraints.py`

**Step 1: 创建 v020（AI只读用户 — 从 `migrate_ai_readonly_user` L860-917 提取）**

```python
"""v020: 创建 AI 只读数据库用户 + 语义视图"""
import os
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # 检查用户是否已存在
    result = await conn.execute_query_dict(
        "SELECT 1 FROM pg_roles WHERE rolname = 'erp_ai_readonly'"
    )
    if not result:
        from app.config import AI_DB_PASSWORD
        if not AI_DB_PASSWORD:
            logger.warning("AI_DB_PASSWORD 未设置，跳过创建 AI 只读用户")
            return
        try:
            safe_password = AI_DB_PASSWORD.replace("'", "''")
            await conn.execute_query(f"CREATE USER erp_ai_readonly WITH PASSWORD '{safe_password}'")
            db_name_rows = await conn.execute_query_dict("SELECT current_database() AS db")
            db_name = db_name_rows[0]["db"] if db_name_rows else "erp"
            await conn.execute_query(f"GRANT CONNECT ON DATABASE {db_name} TO erp_ai_readonly")
            await conn.execute_query("GRANT USAGE ON SCHEMA public TO erp_ai_readonly")
            await conn.execute_query("GRANT SELECT ON ALL TABLES IN SCHEMA public TO erp_ai_readonly")
            await conn.execute_query("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO erp_ai_readonly")
            await conn.execute_query("REVOKE SELECT ON users FROM erp_ai_readonly")
            await conn.execute_query("REVOKE SELECT ON system_settings FROM erp_ai_readonly")
            await conn.execute_query("ALTER USER erp_ai_readonly SET statement_timeout = '30s'")
            await conn.execute_query("ALTER USER erp_ai_readonly SET work_mem = '16MB'")
            await conn.execute_query("ALTER USER erp_ai_readonly SET temp_file_limit = '100MB'")
            await conn.execute_query("ALTER USER erp_ai_readonly CONNECTION LIMIT 5")
        except Exception as e:
            logger.warning(f"创建 AI 只读用户失败: {e}")

    # 创建/更新语义视图
    try:
        views_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai", "views.sql")
        if os.path.exists(views_path):
            with open(views_path, "r", encoding="utf-8") as f:
                views_sql = f.read()
            for stmt in views_sql.split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                non_comment_lines = [l for l in stmt.split("\n")
                                     if l.strip() and not l.strip().startswith("--")]
                if not non_comment_lines:
                    continue
                try:
                    await conn.execute_query(stmt)
                except Exception as ve:
                    logger.warning(f"视图语句执行失败: {ve}")
    except Exception as e:
        logger.warning(f"语义视图创建失败: {e}")
```

**Step 2: 创建 v021（库存活动时间 — 从 `migrate_stock_last_activity` L920-957 提取）**

```python
"""v021: warehouse_stocks 新增 last_activity_at 字段 + 触发器"""


async def up(conn):
    await conn.execute_query(
        "ALTER TABLE warehouse_stocks ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ"
    )
    await conn.execute_query(
        "UPDATE warehouse_stocks SET last_activity_at = updated_at WHERE last_activity_at IS NULL"
    )
    await conn.execute_query("""
        CREATE OR REPLACE FUNCTION trg_update_last_activity()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.last_activity_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    await conn.execute_query(
        "DROP TRIGGER IF EXISTS trg_stock_last_activity_update ON warehouse_stocks"
    )
    await conn.execute_query("""
        CREATE TRIGGER trg_stock_last_activity_update
        BEFORE UPDATE ON warehouse_stocks
        FOR EACH ROW
        WHEN (OLD.quantity IS DISTINCT FROM NEW.quantity
              OR OLD.reserved_qty IS DISTINCT FROM NEW.reserved_qty)
        EXECUTE FUNCTION trg_update_last_activity()
    """)
    await conn.execute_query(
        "DROP TRIGGER IF EXISTS trg_stock_last_activity_insert ON warehouse_stocks"
    )
    await conn.execute_query("""
        CREATE TRIGGER trg_stock_last_activity_insert
        BEFORE INSERT ON warehouse_stocks
        FOR EACH ROW
        EXECUTE FUNCTION trg_update_last_activity()
    """)
```

**Step 3: 创建 v022（代采代发 — 从 `migrate_dropship_module` L960-1062 提取）**

```python
"""v022: 代采代发模块（dropship_orders 表 + receivable_bills 新列 + 种子数据）"""
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # 1. 创建 dropship_orders 表
    await conn.execute_script("""
        CREATE TABLE IF NOT EXISTS dropship_orders (
            id SERIAL PRIMARY KEY,
            ds_no VARCHAR(30) UNIQUE NOT NULL,
            account_set_id INT NOT NULL REFERENCES account_sets(id) ON DELETE RESTRICT,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            supplier_id INT NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
            product_id INT REFERENCES products(id) ON DELETE SET NULL,
            product_name VARCHAR(200) NOT NULL,
            purchase_price DECIMAL(12,2) NOT NULL,
            quantity INT NOT NULL,
            purchase_total DECIMAL(12,2) NOT NULL,
            invoice_type VARCHAR(10) NOT NULL DEFAULT 'special',
            purchase_tax_rate DECIMAL(5,2) NOT NULL DEFAULT 13,
            customer_id INT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            platform_order_no VARCHAR(100) NOT NULL,
            sale_price DECIMAL(12,2) NOT NULL,
            sale_total DECIMAL(12,2) NOT NULL,
            sale_tax_rate DECIMAL(5,2) NOT NULL DEFAULT 13,
            settlement_type VARCHAR(10) NOT NULL DEFAULT 'credit',
            advance_receipt_id INT REFERENCES receipt_bills(id) ON DELETE SET NULL,
            gross_profit DECIMAL(12,2) NOT NULL DEFAULT 0,
            gross_margin DECIMAL(5,2) NOT NULL DEFAULT 0,
            shipping_mode VARCHAR(10) NOT NULL DEFAULT 'direct',
            carrier_code VARCHAR(30),
            carrier_name VARCHAR(50),
            tracking_no VARCHAR(100),
            kd100_subscribed BOOLEAN NOT NULL DEFAULT FALSE,
            last_tracking_info TEXT,
            urged_at TIMESTAMPTZ,
            cancel_reason VARCHAR(200),
            note TEXT,
            payable_bill_id INT REFERENCES payable_bills(id) ON DELETE SET NULL,
            disbursement_bill_id INT REFERENCES disbursement_bills(id) ON DELETE SET NULL,
            receivable_bill_id INT REFERENCES receivable_bills(id) ON DELETE SET NULL,
            payment_method VARCHAR(50),
            payment_employee_id INT REFERENCES employees(id) ON DELETE SET NULL,
            creator_id INT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_account_set ON dropship_orders(account_set_id);
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_supplier ON dropship_orders(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_customer ON dropship_orders(customer_id);
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_status ON dropship_orders(status);
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_created_desc ON dropship_orders(created_at DESC, id DESC);
    """)

    # 2. receivable_bills 新列
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE receivable_bills ADD COLUMN platform_order_no VARCHAR(100);
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE receivable_bills ADD COLUMN dropship_order_id INT REFERENCES dropship_orders(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)

    # 3. dropship_orders.shipped_at
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE dropship_orders ADD COLUMN shipped_at TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)

    # 4. 冲减借支付款方式
    await conn.execute_query("""
        INSERT INTO disbursement_methods (code, name, sort_order, is_active)
        SELECT 'employee_advance', '冲减借支', 10, TRUE
        WHERE NOT EXISTS (
            SELECT 1 FROM disbursement_methods WHERE code = 'employee_advance'
        )
    """)
```

**Step 4: 创建 v023（代采手机号 — 从 `migrate_dropship_phone` L1065-1074 提取）**

```python
"""v023: dropship_orders 新增 phone 字段"""


async def up(conn):
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE dropship_orders ADD COLUMN phone VARCHAR(11);
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
```

**Step 5: 创建 v024（物流刷新 — 从 `migrate_tracking_refresh_fields` L1077-1092 提取）**

```python
"""v024: dropship_orders 和 shipments 新增 last_tracking_refresh 字段"""


async def up(conn):
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE dropship_orders ADD COLUMN last_tracking_refresh TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE shipments ADD COLUMN last_tracking_refresh TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
```

**Step 6: 创建 v025（仓位颜色 — 从 `migrate_warehouse_color` L1095-1107 提取）**

```python
"""v025: locations 表新增 color 字段"""


async def up(conn):
    loc_cols = [r["name"] for r in (await conn.execute_query(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name='locations'"
    ))[1]]
    if "color" not in loc_cols:
        await conn.execute_query(
            "ALTER TABLE locations ADD COLUMN color VARCHAR(20) DEFAULT 'blue'"
        )
```

**Step 7: 创建 v026（权限迁移 — 从 `_migrate_ai_permissions` L1110-1129 + `_migrate_dropship_permissions` L1132-1150 提取）**

```python
"""v026: 一次性权限迁移（AI + 代采代发）"""
from app.models import User, SystemSetting
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # AI 权限
    flag = await SystemSetting.filter(key="ai.permissions_migrated").first()
    if not flag:
        from app.ai.view_permissions import AI_PERMISSION_KEYS

        users = await User.filter(is_active=True).exclude(role="admin").all()
        migrated = 0
        for user in users:
            perms = user.permissions or []
            if "ai_chat" not in perms:
                perms.extend(AI_PERMISSION_KEYS)
                user.permissions = list(set(perms))
                await user.save()
                migrated += 1
        if migrated:
            logger.info(f"AI 权限迁移完成，已为 {migrated} 个用户添加 AI 权限")
        await SystemSetting.get_or_create(key="ai.permissions_migrated", defaults={"value": "1"})

    # 代采代发权限
    flag2 = await SystemSetting.filter(key="dropship.permissions_migrated").first()
    if not flag2:
        dropship_perms = ["dropship", "dropship_pay"]
        users = await User.filter(is_active=True).exclude(role="admin").all()
        migrated = 0
        for user in users:
            perms = user.permissions or []
            if "dropship" not in perms:
                perms.extend(dropship_perms)
                user.permissions = list(set(perms))
                await user.save()
                migrated += 1
        if migrated:
            logger.info(f"代采代发权限迁移完成，已为 {migrated} 个用户添加权限")
        await SystemSetting.get_or_create(key="dropship.permissions_migrated", defaults={"value": "1"})
```

**Step 8: 创建 v027（缺失索引 — 从 `migrate_add_missing_indexes` L1163-1180 提取）**

```python
"""v027: 审查发现的缺失复合索引"""


async def up(conn):
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_voucher_as_period ON vouchers(account_set_id, period_name)",
        "CREATE INDEX IF NOT EXISTS idx_receivable_bill_as_status ON receivable_bills(account_set_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_receivable_bill_date ON receivable_bills(bill_date)",
        "CREATE INDEX IF NOT EXISTS idx_payable_bill_as_status ON payable_bills(account_set_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_order_item_wh_loc ON order_items(warehouse_id, location_id)",
        "CREATE INDEX IF NOT EXISTS idx_shipment_tracking ON shipments(tracking_no)",
        "CREATE INDEX IF NOT EXISTS idx_stock_log_wh_date ON stock_logs(warehouse_id, created_at DESC)",
    ]
    for sql in indexes:
        try:
            await conn.execute_query(sql)
        except Exception:
            pass
```

**Step 9: 创建 v028（CHECK 约束 — 从 `migrate_add_check_constraints` L1183-1200 提取）**

```python
"""v028: 数据库级 CHECK 约束"""
from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    constraints = [
        ("order_items", "chk_oi_qty_positive", "quantity > 0"),
        ("orders", "chk_order_total_nonneg", "total_amount >= 0"),
        ("warehouse_stocks", "chk_ws_reserved_nonneg", "reserved_qty >= 0"),
        ("invoice_items", "chk_ii_tax_rate_range", "tax_rate >= 0 AND tax_rate <= 100"),
        ("purchase_order_items", "chk_poi_tax_rate_range", "tax_rate >= 0 AND tax_rate <= 100"),
    ]
    for table, name, check_expr in constraints:
        try:
            await conn.execute_query(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({check_expr})"
            )
        except Exception as e:
            if "already exists" not in str(e):
                logger.warning(f"CHECK 约束 {name} 创建失败: {e}")
```

**Step 10: 验证所有文件语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && for f in app/migrations/v0{20..28}_*.py; do python -c "import ast; ast.parse(open('$f').read())"; done && echo "ALL OK"`

**Step 11: Commit**

```bash
git add app/migrations/v02*.py
git commit -m "refactor: 拆分迁移文件 v020-v028（AI/物流/代采/权限/约束）"
```

---

### Task 5: 删除旧文件 + 更新入口 + README

**Files:**
- Delete: `app/migrations.py`
- Create: `app/migrations/README.md`

**Step 1: 删除旧 `migrations.py`**

```bash
git rm app/migrations.py
```

注意：`main.py:18` 的 `from app.migrations import run_migrations` 和 `app/routers/backup.py:28` 的相同 import 现在会走 `app/migrations/__init__.py`，无需修改。

**Step 2: 创建 `README.md`**

```markdown
# 数据库迁移

## 如何添加新迁移

1. 创建文件 `vNNN_描述.py`（编号递增，如 `v029_add_xxx.py`）
2. 实现 `up(conn)` 函数：

```python
"""v029: 描述"""

async def up(conn):
    await conn.execute_query("ALTER TABLE ...")
```

3. 完成。下次启动时自动执行。

## 工作原理

- `runner.py` 启动时扫描所有 `v*.py` 文件
- 对比 `migration_history` 表，只执行未运行的迁移
- 用 `pg_advisory_lock` 防止多 worker 并发执行
- 已有数据库首次升级时，v001-v028 自动标记为已执行

## 注意事项

- 文件编号必须递增且唯一
- 已提交的迁移文件不要修改（已在生产执行过）
- DDL 操作建议用 `IF NOT EXISTS` 作为防御性编程
- 迁移失败会阻止应用启动（fail-fast）
```

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: 删除旧 migrations.py，添加 README"
```

---

### Task 6: Docker 验证

**Step 1: 重建 Docker 并验证启动**

```bash
cd /Users/lin/Desktop/erp-4
orb start
docker compose down
docker compose build --no-cache backend
docker compose up -d
```

**Step 2: 检查迁移日志**

```bash
docker compose logs backend 2>&1 | grep -i "migrat"
```

Expected: 看到 `基线迁移已标记: v001-v028 (28 个)` 和 `数据库迁移已是最新 (28 个迁移)`

**Step 3: 验证 migration_history 表**

```bash
docker compose exec db psql -U erp -d erp -c "SELECT version, name, applied_at FROM migration_history ORDER BY version;"
```

Expected: 28 行记录，v001-v028 全部标记

**Step 4: 验证 health 端点**

```bash
curl -s http://localhost:8090/health | python3 -m json.tool
```

Expected: `{"status": "ok", "database": "connected"}`

**Step 5: Commit 最终确认**

```bash
git add -A
git commit -m "chore: 迁移系统版本化改造完成，Docker 验证通过"
```

---

## 交接记录格式

每个 Task 完成后在此记录：

### Task 1 交接
- [ ] runner.py 创建完成
- [ ] 语法检查通过
- [ ] 已提交

### Task 2 交接
- [ ] v001-v009 共 9 个文件创建完成
- [ ] 语法检查通过
- [ ] 已提交

### Task 3 交接
- [ ] v010-v019 共 10 个文件创建完成
- [ ] 语法检查通过
- [ ] 已提交

### Task 4 交接
- [ ] v020-v028 共 9 个文件创建完成
- [ ] 语法检查通过
- [ ] 已提交

### Task 5 交接
- [ ] 旧 `migrations.py` 已删除
- [ ] README.md 已创建
- [ ] import 路径验证通过
- [ ] 已提交

### Task 6 交接
- [ ] Docker 构建成功
- [ ] migration_history 表有 28 条记录
- [ ] health 端点正常
- [ ] 全部功能正常
