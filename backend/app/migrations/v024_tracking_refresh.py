"""v024 — 物流刷新时间字段

为 dropship_orders 和 shipments 添加 last_tracking_refresh 字段。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


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
    logger.info("迁移: last_tracking_refresh 字段已添加")
