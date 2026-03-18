"""v004 — 订单表添加 updated_at

给 orders 表添加 updated_at 列，历史数据回填为 created_at。
"""
from __future__ import annotations


async def up(conn):
    await conn.execute_query(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
    )
    await conn.execute_query(
        "UPDATE orders SET updated_at = created_at WHERE updated_at IS NULL"
    )
