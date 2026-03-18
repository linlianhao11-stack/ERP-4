"""v005 — 订单明细添加仓库/仓位

给 order_items 表添加 warehouse_id 和 location_id 列。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'order_items'"
    )
    col_names = [col["name"] for col in columns]

    if "warehouse_id" not in col_names:
        await conn.execute_query(
            "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS warehouse_id INT REFERENCES warehouses(id) ON DELETE SET NULL"
        )
        logger.info("迁移: order_items 表添加 warehouse_id 列")

    if "location_id" not in col_names:
        await conn.execute_query(
            "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS location_id INT REFERENCES locations(id) ON DELETE SET NULL"
        )
        logger.info("迁移: order_items 表添加 location_id 列")
