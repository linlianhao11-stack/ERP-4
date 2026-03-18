"""v008 — 补充时间戳列

为缺少时间戳的表添加 updated_at / created_at 列。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


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
        except Exception as e:
            logger.warning(f"添加 {table}.{col} 失败（可忽略）: {e}")
