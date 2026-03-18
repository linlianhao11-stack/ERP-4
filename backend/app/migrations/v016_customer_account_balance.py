"""v016 — 客户返利按账套隔离迁移

新表 + 数据迁移。
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

    # 索引
    cab_indexes = [
        ("idx_customer_account_balances_customer", "customer_account_balances", "customer_id"),
        ("idx_customer_account_balances_account_set", "customer_account_balances", "account_set_id"),
    ]
    for name, table, columns in cab_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败（可忽略）: {e}")

    # 迁移现有余额数据到第一个活跃账套
    from app.models.accounting import AccountSet

    first_set = await AccountSet.filter(is_active=True).order_by("id").first()
    if first_set:
        rows = await conn.execute_query_dict(
            "SELECT id, name, rebate_balance FROM customers "
            "WHERE rebate_balance > 0"
        )
        for row in rows:
            result = await conn.execute_query(
                "INSERT INTO customer_account_balances (customer_id, account_set_id, rebate_balance) "
                "VALUES ($1, $2, $3) ON CONFLICT (customer_id, account_set_id) DO NOTHING",
                [row["id"], first_set.id, row["rebate_balance"]]
            )
            if result[0] > 0:
                logger.info(f"迁移: 客户 {row['name']} 返利余额已迁移到账套 {first_set.name}")

    logger.info("客户返利账套隔离迁移完成")
