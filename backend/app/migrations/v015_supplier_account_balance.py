"""v015 — 供应商返利按账套隔离迁移

新表 + RebateLog 新列 + 数据迁移 + 预置科目 5401/2221。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise

    try:
        await Tortoise.generate_schemas(safe=True)
    except Exception:
        pass  # Column already exists from init_db()

    # RebateLog 增加 account_set_id 列
    rl_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'rebate_logs'"
    )
    if "account_set_id" not in [c["name"] for c in rl_cols]:
        await conn.execute_query(
            "ALTER TABLE rebate_logs ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: rebate_logs 表添加 account_set_id 列")

    # 索引
    sab_indexes = [
        ("idx_supplier_account_balances_supplier", "supplier_account_balances", "supplier_id"),
        ("idx_supplier_account_balances_account_set", "supplier_account_balances", "account_set_id"),
        ("idx_rebate_logs_account_set", "rebate_logs", "account_set_id"),
    ]
    for name, table, columns in sab_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败（可忽略）: {e}")

    # 迁移现有余额数据到第一个活跃账套
    from app.models.accounting import AccountSet, ChartOfAccount
    from app.models.supplier_balance import SupplierAccountBalance

    first_set = await AccountSet.filter(is_active=True).order_by("id").first()
    if first_set:
        # 查找有非零余额的供应商
        rows = await conn.execute_query_dict(
            "SELECT id, name, rebate_balance, credit_balance FROM suppliers "
            "WHERE (rebate_balance > 0 OR credit_balance > 0)"
        )
        for row in rows:
            result = await conn.execute_query(
                "INSERT INTO supplier_account_balances (supplier_id, account_set_id, rebate_balance, credit_balance) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT (supplier_id, account_set_id) DO NOTHING",
                [row["id"], first_set.id, row["rebate_balance"], row["credit_balance"]]
            )
            if result[0] > 0:
                logger.info(f"迁移: 供应商 {row['name']} 余额已迁移到账套 {first_set.name}")

    # 确保凭证所需科目存在（ON CONFLICT 防竞态）
    for aset in await AccountSet.all():
        try:
            result = await conn.execute_query(
                "INSERT INTO chart_of_accounts (account_set_id, code, name, level, category, direction, is_leaf) "
                "VALUES ($1, '5401', '主营业务成本', 1, 'cost', 'debit', TRUE) "
                "ON CONFLICT (account_set_id, code) DO NOTHING",
                [aset.id]
            )
            if result[0] > 0:
                logger.info(f"账套 {aset.name} 创建科目 5401 主营业务成本")
        except Exception as e:
            logger.warning(f"创建科目 5401 失败（可忽略）: {e}")
        try:
            result = await conn.execute_query(
                "INSERT INTO chart_of_accounts (account_set_id, code, name, level, category, direction, is_leaf) "
                "VALUES ($1, '2221', '应交税费', 1, 'liability', 'credit', TRUE) "
                "ON CONFLICT (account_set_id, code) DO NOTHING",
                [aset.id]
            )
            if result[0] > 0:
                logger.info(f"账套 {aset.name} 创建科目 2221 应交税费")
        except Exception as e:
            logger.warning(f"创建科目 2221 失败（可忽略）: {e}")

    logger.info("供应商返利账套隔离迁移完成")
