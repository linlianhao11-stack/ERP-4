"""v011 — 阶段1财务基础设施迁移

凭证表结构升级，现有表新增 account_set_id，products.tax_rate，
会计索引，admin 权限更新。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise
    from app.models import User

    # ── 凭证表结构升级（旧表→新表）──
    # 检测旧版 vouchers 表（有 company_name 列 = 旧表结构）
    v_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'vouchers'"
    )
    v_col_names = [c["name"] for c in v_cols]
    if "company_name" in v_col_names or ("account_set_id" not in v_col_names and v_cols):
        logger.info("迁移: 检测到旧版 vouchers 表结构，重建为新版")
        await conn.execute_query("DROP TABLE IF EXISTS voucher_entries CASCADE")
        await conn.execute_query("DROP TABLE IF EXISTS vouchers CASCADE")
        try:
            await Tortoise.generate_schemas(safe=True)
        except Exception:
            pass
        logger.info("迁移: vouchers / voucher_entries 表已重建")

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

    # 更新默认管理员的权限列表（添加会计权限）
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

    logger.info("阶段1财务迁移完成")
