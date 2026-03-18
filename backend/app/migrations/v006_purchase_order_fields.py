"""v006 — 采购单添加付款方式

给 purchase_orders 表添加 payment_method 列。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    col_names = [col["name"] for col in columns]

    if "payment_method" not in col_names:
        await conn.execute_query(
            "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50)"
        )
        logger.info("迁移: purchase_orders 表添加 payment_method 列")
