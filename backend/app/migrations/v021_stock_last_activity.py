"""v021 — 库存最后活动时间

新增 last_activity_at 字段 + 触发器自动维护。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


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
